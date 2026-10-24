from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.gateway import get_gateway_service
from app.main import app
from app.schemas import ActionRequest, ActorContext, Decision, EvaluationRequest
from app.services.gateway import GatewayService
from app.services.identity import IdentityResolver, TrustedIdentity
from app.services.parking import MockParkingService
from app.services.policy import DevMockPolicyEngine


def _identity(role="operator"):
    return TrustedIdentity(user_id="role_probe", role=role, district_id="district_north")


def _action(operation="reserve_spot", domain="parking"):
    return ActionRequest(
        request_id="req-role-check",
        domain=domain,
        operation=operation,
        resource_id="park_south_1",
        resource_district_id="district_south",
    )


@pytest.mark.parametrize("role", ["guest", "auditor", "ADMIN", " admin", "admin\x00"])
def test_unknown_role_defaults_to_deny(role):
    engine = DevMockPolicyEngine()
    for operation in ("read", "reserve_spot", "close_zone"):
        result = engine.evaluate(_identity(role), _action(operation))
        assert result.decision == Decision.DENY
        assert result.reason_code == "ROLE_NOT_AUTHORIZED"


@pytest.mark.parametrize("role", ["", " ", "\t\n"])
def test_empty_role_defaults_to_deny(role):
    result = DevMockPolicyEngine().evaluate(_identity(role), _action())
    assert result.decision == Decision.DENY
    assert result.reason_code == "ROLE_NOT_AUTHORIZED"


@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
def test_unsupported_operation_defaults_to_deny(role):
    engine = DevMockPolicyEngine()
    for domain, operation in (("parking", "delete_lot"), ("grid", "read")):
        result = engine.evaluate(_identity(role), _action(operation, domain))
        assert result.decision == Decision.DENY
        assert result.reason_code == "UNKNOWN_OPERATION"


def _missing_role_identity():
    identity = _identity()
    object.__delattr__(identity, "role")  # Simulate an incomplete deserialized dataclass.
    return identity


MALFORMED_IDENTITIES = [
    pytest.param(None, id="missing-identity"),
    pytest.param({}, id="mapping-not-identity"),
    pytest.param(SimpleNamespace(role="admin"), id="wrong-identity-type"),
    pytest.param(_missing_role_identity(), id="missing-role"),
    pytest.param(replace(_identity(), role=None), id="null-role"),
    pytest.param(replace(_identity(), role=[]), id="list-role"),
    pytest.param(replace(_identity(), role={}), id="dict-role"),
    pytest.param(replace(_identity(), role=42), id="numeric-role"),
    pytest.param(replace(_identity(), user_id=None), id="invalid-user-id"),
    pytest.param(replace(_identity(), district_id=None), id="missing-district"),
    pytest.param(replace(_identity(), district_id=" "), id="empty-district"),
    pytest.param(replace(_identity(), is_authenticated="false"), id="string-auth-flag"),
    pytest.param(replace(_identity(), is_authenticated=1), id="numeric-auth-flag"),
]


@pytest.mark.parametrize("identity", MALFORMED_IDENTITIES)
def test_malformed_identity_fails_safely(identity):
    result = DevMockPolicyEngine().evaluate(identity, _action())
    assert result.decision == Decision.DENY
    assert result.reason_code == "UNAUTHENTICATED_ACTOR"


def test_admin_permissions_remain_unchanged():
    engine = DevMockPolicyEngine()
    admin = IdentityResolver().resolve(auth_token="token_admin")
    assert admin is not None
    approval_operations = {
        "reroute_power", "isolate_substation", "emergency_stop",
        "open_valve", "broadcast_alert", "close_zone",
    }
    for domain, operations in engine.VALID_DOMAINS.items():
        for operation in operations:
            result = engine.evaluate(admin, _action(operation, domain))
            if operation in approval_operations:
                assert result.decision == Decision.APPROVAL_REQUIRED, (domain, operation)
                assert result.reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"
            else:
                assert result.decision == Decision.ALLOW, (domain, operation)
                assert result.reason_code == "POLICY_ALLOW"


@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
def test_registered_action_without_role_permission_is_denied(monkeypatch, role):
    engine = DevMockPolicyEngine()
    domains = {domain: set(operations) for domain, operations in engine.VALID_DOMAINS.items()}
    domains["parking"].add("delete_lot")
    domains["new_domain"] = {"read"}
    monkeypatch.setattr(engine, "VALID_DOMAINS", domains)
    for domain, operation in (("parking", "delete_lot"), ("new_domain", "read")):
        action = _action(operation, domain).model_copy(update={"resource_district_id": "district_north"})
        result = engine.evaluate(_identity(role), action)
        assert result.decision == Decision.DENY
        assert result.reason_code == "ROLE_NOT_AUTHORIZED"


def _assert_gateway_denial(monkeypatch, identity, expected_reason):
    resolver = Mock(spec=IdentityResolver)
    resolver.resolve.return_value = identity
    parking = MockParkingService()
    before = deepcopy(parking.records)
    gateway = GatewayService(identity_resolver=resolver, parking_service=parking)
    monkeypatch.setitem(app.dependency_overrides, get_gateway_service, lambda: gateway)
    request = EvaluationRequest(
        request_id="req-role-check",
        actor=ActorContext(user_id="user_admin", role="admin", district_id="district_south"),
        action=_action().model_copy(update={"resource_district_id": "district_north"}),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/requests/evaluate", json=request.model_dump(),
            headers={"Authorization": "Bearer synthetic-role-test-credential"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == request.request_id
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == expected_reason
    assert data["executed"] is False
    assert data["result"] is None
    assert parking.call_count == 0
    assert parking.records == before
    events = gateway.audit_service.get_events()
    assert len(events) == 1
    event = events[0]
    assert event.audit_id == data["audit_id"]
    assert event.request_id == request.request_id
    assert event.decision == Decision.DENY
    assert event.reason_code == expected_reason
    assert event.executed is False
    assert event.execution_status == "not_attempted"
    assert event.user_id == (identity.user_id if expected_reason == "ROLE_NOT_AUTHORIZED" else None)
    assert "synthetic-role-test-credential" not in event.model_dump_json()


@pytest.mark.parametrize("role", ["guest", "", " ", "ADMIN"])
def test_unknown_role_cannot_execute_parking_action(monkeypatch, role):
    _assert_gateway_denial(monkeypatch, _identity(role), "ROLE_NOT_AUTHORIZED")


@pytest.mark.parametrize("identity", MALFORMED_IDENTITIES)
def test_malformed_resolved_identity_cannot_execute_or_break_audit(monkeypatch, identity):
    expected_reason = "UNAUTHENTICATED_ACTOR" if identity is None else "IDENTITY_RESOLUTION_FAILED"
    _assert_gateway_denial(monkeypatch, identity, expected_reason)


@pytest.mark.parametrize("identity, operation, reason", [
    (_identity("guest"), "read", "ROLE_NOT_AUTHORIZED"),
    (_identity(""), "reserve_spot", "ROLE_NOT_AUTHORIZED"),
    (_identity("viewer"), "reserve_spot", "ROLE_NOT_AUTHORIZED"),
    (_identity("admin"), "delete_lot", "ROLE_NOT_AUTHORIZED"),
    (_identity("admin"), "dispatch_truck", "ROLE_NOT_AUTHORIZED"),
    (replace(_identity("admin"), is_authenticated="false"), "read", "UNAUTHENTICATED_ACTOR"),
    (replace(_identity("admin"), role=[]), "reserve_spot", "UNAUTHENTICATED_ACTOR"),
])
def test_parking_service_uses_shared_identity_and_role_checks(identity, operation, reason):
    parking = MockParkingService()
    before = deepcopy(parking.records)
    result = parking.execute(
        operation=operation, resource_id="park_south_1", authorized_identity=identity
    )
    assert result["success"] is False
    assert result["reason_code"] == reason
    assert "record" not in result
    assert parking.call_count == 1  # Direct defensive check, not a gateway dispatch.
    assert parking.records == before


@pytest.mark.parametrize("role", ["operator", "viewer"])
def test_known_role_permissions_and_approval_rules_are_preserved(role):
    engine = DevMockPolicyEngine()
    approval_operations = {
        "reroute_power", "isolate_substation", "emergency_stop",
        "open_valve", "broadcast_alert", "close_zone",
    }
    for domain, operations in engine.VALID_DOMAINS.items():
        for operation in operations:
            action = _action(operation, domain).model_copy(update={"resource_district_id": "district_north"})
            result = engine.evaluate(_identity(role), action)
            if role == "viewer" and operation not in ("read", "status"):
                assert result.decision == Decision.DENY, (domain, operation)
                assert result.reason_code == "ROLE_NOT_AUTHORIZED"
            elif operation in approval_operations:
                assert result.decision == Decision.APPROVAL_REQUIRED, (domain, operation)
                assert result.reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"
            else:
                assert result.decision == Decision.ALLOW, (domain, operation)
                assert result.reason_code == "POLICY_ALLOW"


@pytest.mark.parametrize("token, reason", [
    ("token_viewer", "ROLE_NOT_AUTHORIZED"),
    ("token_operator_north", "DISTRICT_MISMATCH"),
])
def test_authenticated_token_role_cannot_be_overridden_by_actor(token, reason):
    parking = MockParkingService()
    before = deepcopy(parking.records)
    gateway = GatewayService(parking_service=parking)
    request = EvaluationRequest(
        request_id="req-actor-role-spoof",
        actor=ActorContext(user_id="user_admin", role="admin", district_id="district_south"),
        action=_action().model_copy(update={"resource_district_id": "district_north"}),
    )
    response = gateway.evaluate(request, auth_token=token)
    assert response.decision == Decision.DENY
    assert response.reason_code == reason
    assert response.executed is False
    assert response.result is None
    assert parking.call_count == 0
    assert parking.records == before
    event = gateway.audit_service.get_by_audit_id(response.audit_id)
    assert event is not None
    assert event.decision == Decision.DENY
    assert event.reason_code == reason
    assert event.execution_status == "not_attempted"
    assert event.executed is False
    assert event.user_id != "user_admin"


def test_admin_cross_district_execution_and_approval_remain_unchanged():
    parking = MockParkingService()
    before = deepcopy(parking.records)
    gateway = GatewayService(parking_service=parking)
    for operation in ("read", "reserve_spot", "release_spot", "close_zone"):
        previous_calls = parking.call_count
        response = gateway.evaluate(
            EvaluationRequest(request_id="req-admin-check", action=_action(operation)),
            auth_token="token_admin",
        )
        event = gateway.audit_service.get_by_audit_id(response.audit_id)
        assert event is not None
        assert event.decision == response.decision
        assert event.executed is response.executed
        if operation == "close_zone":
            assert response.decision == Decision.APPROVAL_REQUIRED
            assert response.reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"
            assert response.executed is False
            assert response.result is None
            assert parking.call_count == previous_calls
            assert event.execution_status == "not_attempted"
        else:
            assert response.decision == Decision.ALLOW
            assert response.reason_code == "POLICY_ALLOW"
            assert response.executed is True
            assert response.result is not None
            assert response.result["success"] is True
            assert parking.call_count == previous_calls + 1
            assert event.execution_status == "success"
    assert parking.records == before  # Reservation and release balance each other.


def test_unsupported_gateway_operation_keeps_error_contract_and_state(monkeypatch):
    parking = MockParkingService()
    before = deepcopy(parking.records)
    gateway = GatewayService(parking_service=parking)
    monkeypatch.setitem(app.dependency_overrides, get_gateway_service, lambda: gateway)
    request = EvaluationRequest(request_id="req-unsupported-op", action=_action("delete_lot"))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/requests/evaluate", json=request.model_dump(),
            headers={"Authorization": "Bearer token_admin"},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "UNKNOWN_OPERATION"
    assert response.json()["request_id"] == request.request_id
    assert parking.call_count == 0
    assert parking.records == before
