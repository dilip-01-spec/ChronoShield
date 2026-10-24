from copy import deepcopy
from dataclasses import dataclass
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.gateway import get_gateway_service
from app.api.policies import get_policy_tester
from app.main import app
from app.schemas import ActionRequest, ActorContext, Decision, EvaluationRequest
from app.security.engine import FormalPolicyEngine
from app.services.policy import FormalPolicyEngineAdapter, PolicyEvaluationResult
from app.services.gateway import GatewayService
from app.services.identity import IdentityResolver, TrustedIdentity
from app.services.parking import MockParkingService
from app.services.policy_factory import (
    PolicyEngineConfigurationError,
    create_policy_engine,
    get_policy_engine,
)
from app.services.policy_testing import PolicyTester


# =====================================================================
# Fixtures and Helpers
# =====================================================================

def _identity(role="operator", district_id="district_north", user_id="user_test"):
    return TrustedIdentity(user_id=user_id, role=role, district_id=district_id)


def _action(operation="reserve_spot", domain="parking", resource_district_id="district_north", resource_id="park_north_1"):
    return ActionRequest(
        request_id="req-formal-test",
        domain=domain,
        operation=operation,
        resource_id=resource_id,
        resource_district_id=resource_district_id,
    )


# =====================================================================
# 1. Adapter Decision, Reason-Code, and Fallback Normalization
# =====================================================================

def test_adapter_implements_protocol_and_delegates_queries():
    adapter = FormalPolicyEngineAdapter()
    assert adapter.is_valid_domain("parking") is True
    assert adapter.is_valid_domain("grid") is True
    assert adapter.is_valid_domain("unknown_domain") is False
    assert adapter.is_valid_operation("parking", "read") is True
    assert adapter.is_valid_operation("grid", "reroute_power") is True
    assert adapter.is_valid_operation("parking", "reroute_power") is False


def test_adapter_handles_exceptions_in_validation_safely():
    faulty_engine = Mock(spec=FormalPolicyEngine)
    faulty_engine.is_valid_domain.side_effect = RuntimeError("Domain check exploded")
    faulty_engine.is_valid_operation.side_effect = RuntimeError("Op check exploded")
    adapter = FormalPolicyEngineAdapter(engine=faulty_engine)

    assert adapter.is_valid_domain("parking") is False
    assert adapter.is_valid_operation("parking", "read") is False


@pytest.mark.parametrize("decision_val, expected_decision", [
    (Decision.ALLOW, Decision.ALLOW),
    (Decision.DENY, Decision.DENY),
    (Decision.APPROVAL_REQUIRED, Decision.APPROVAL_REQUIRED),
    ("allow", Decision.ALLOW),
    ("ALLOW", Decision.ALLOW),
    ("deny", Decision.DENY),
    ("DENY", Decision.DENY),
    ("approval_required", Decision.APPROVAL_REQUIRED),
    ("requires_approval", Decision.APPROVAL_REQUIRED),
    ("REQUIRES_APPROVAL", Decision.APPROVAL_REQUIRED),
])
def test_adapter_normalizes_valid_decision_variants(decision_val, expected_decision):
    engine = Mock(spec=FormalPolicyEngine)
    engine.evaluate.return_value = PolicyEvaluationResult(
        decision=decision_val,
        reason_code="CUSTOM_CODE",
        message="Custom message",
    )
    adapter = FormalPolicyEngineAdapter(engine=engine)
    result = adapter.evaluate(_identity(), _action())

    assert result.decision == expected_decision
    assert result.reason_code == "CUSTOM_CODE"
    assert result.message == "Custom message"


@pytest.mark.parametrize("invalid_result", [
    None,
    PolicyEvaluationResult(decision="unrecognized_str", reason_code="OK", message="msg"),
    PolicyEvaluationResult(decision=123, reason_code="OK", message="msg"),
    PolicyEvaluationResult(decision=Decision.ALLOW, reason_code="", message="msg"),
    PolicyEvaluationResult(decision=Decision.ALLOW, reason_code=None, message="msg"),
    PolicyEvaluationResult(decision=Decision.ALLOW, reason_code="   ", message="msg"),
])
def test_adapter_fails_closed_on_malformed_engine_result(invalid_result):
    engine = Mock(spec=FormalPolicyEngine)
    engine.evaluate.return_value = invalid_result
    adapter = FormalPolicyEngineAdapter(engine=engine)
    result = adapter.evaluate(_identity(), _action())

    assert result.decision == Decision.DENY
    assert result.reason_code == "POLICY_ENGINE_FAILED"


def test_adapter_fails_closed_when_engine_raises_exception():
    engine = Mock(spec=FormalPolicyEngine)
    engine.evaluate.side_effect = RuntimeError("Database down / internal error")
    adapter = FormalPolicyEngineAdapter(engine=engine)
    result = adapter.evaluate(_identity(), _action())

    assert result.decision == Decision.DENY
    assert result.reason_code == "POLICY_ENGINE_FAILED"


# =====================================================================
# 2. Trusted Identity Mapping & Malformed Identity Protection
# =====================================================================

@pytest.mark.parametrize("malformed_identity", [
    None,
    {},
    {"user_id": "u1", "role": "admin", "district_id": "district_north"},
    _identity(role=None),
    _identity(role=[]),
    _identity(role=123),
    _identity(user_id=""),
    _identity(user_id="  "),
    _identity(district_id=""),
    _identity(district_id="  "),
])
def test_adapter_rejects_malformed_identity_without_calling_engine(malformed_identity):
    engine = Mock(spec=FormalPolicyEngine)
    adapter = FormalPolicyEngineAdapter(engine=engine)
    result = adapter.evaluate(malformed_identity, _action())

    assert result.decision == Decision.DENY
    assert result.reason_code == "UNAUTHENTICATED_ACTOR"
    engine.evaluate.assert_not_called()


# =====================================================================
# 3. Authoritative Resource Security & Defense in Depth
# =====================================================================

def test_operator_cannot_access_south_resource_by_claiming_north_district(monkeypatch):
    """Client claims resource_district_id is north, but server resolves south."""
    adapter = FormalPolicyEngineAdapter()
    parking = MockParkingService()
    before = deepcopy(parking.records)
    gateway = GatewayService(policy_engine=adapter, parking_service=parking)
    monkeypatch.setitem(app.dependency_overrides, get_gateway_service, lambda: gateway)

    # South resource park_south_1
    request = EvaluationRequest(
        request_id="req-spoof-district",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-spoof-district",
            domain="parking",
            operation="reserve_spot",
            resource_id="park_south_1",
            resource_district_id="district_north",  # Spoofed claim!
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/requests/evaluate",
            json=request.model_dump(),
            headers={"Authorization": "Bearer token_operator_north"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "deny"
    assert data["reason_code"] == "DISTRICT_MISMATCH"
    assert data["executed"] is False
    assert parking.call_count == 0
    assert parking.records == before


def test_cross_district_reservation_does_not_mutate_parking_state(monkeypatch):
    adapter = FormalPolicyEngineAdapter()
    parking = MockParkingService()
    before = deepcopy(parking.records)
    gateway = GatewayService(policy_engine=adapter, parking_service=parking)

    request = EvaluationRequest(
        request_id="req-cross-district",
        action=ActionRequest(
            request_id="req-cross-district",
            domain="parking",
            operation="reserve_spot",
            resource_id="park_south_1",
            resource_district_id="district_south",
        ),
    )

    response = gateway.evaluate(request, auth_token="token_operator_north")
    assert response.decision == Decision.DENY
    assert response.reason_code == "DISTRICT_MISMATCH"
    assert response.executed is False
    assert parking.call_count == 0
    assert parking.records == before


def test_parking_service_defense_in_depth_check_remains_active():
    parking = MockParkingService()
    before = deepcopy(parking.records)

    # Operator North attempting South resource directly on MockParkingService
    identity_north = _identity(role="operator", district_id="district_north")
    result = parking.execute("reserve_spot", "park_south_1", authorized_identity=identity_north)

    assert result["success"] is False
    assert result["reason_code"] == "DISTRICT_MISMATCH"
    assert parking.call_count == 1
    assert parking.records == before


def test_engine_exceptions_do_not_execute_protected_actions(monkeypatch):
    faulty_adapter = FormalPolicyEngineAdapter()
    faulty_adapter.evaluate = Mock(side_effect=RuntimeError("Engine exploded"))

    parking = MockParkingService()
    before = deepcopy(parking.records)
    gateway = GatewayService(policy_engine=faulty_adapter, parking_service=parking)

    request = EvaluationRequest(
        request_id="req-fail-safe",
        action=_action("reserve_spot", resource_id="park_north_1", resource_district_id="district_north"),
    )

    response = gateway.evaluate(request, auth_token="token_operator_north")
    assert response.decision == Decision.DENY
    assert response.reason_code == "POLICY_ENGINE_FAILED"
    assert response.executed is False
    assert parking.call_count == 0
    assert parking.records == before


# =====================================================================
# 4. Role and Operation Permissions (8 Domains)
# =====================================================================

@pytest.mark.parametrize("role", ["guest", "auditor", "ADMIN", " admin", "UNKNOWN"])
def test_unknown_role_is_denied(role):
    adapter = FormalPolicyEngineAdapter()
    result = adapter.evaluate(_identity(role=role), _action("read"))
    assert result.decision == Decision.DENY
    assert result.reason_code == "ROLE_NOT_AUTHORIZED"


def test_viewer_cannot_execute_mutations():
    adapter = FormalPolicyEngineAdapter()
    for op in ("reserve_spot", "release_spot", "close_zone"):
        result = adapter.evaluate(_identity(role="viewer"), _action(op))
        assert result.decision == Decision.DENY
        assert result.reason_code == "ROLE_NOT_AUTHORIZED"


def test_viewer_can_read_and_status():
    adapter = FormalPolicyEngineAdapter()
    for op in ("read", "status"):
        result = adapter.evaluate(_identity(role="viewer"), _action(op))
        assert result.decision == Decision.ALLOW
        assert result.reason_code == "POLICY_ALLOW"


def test_admin_has_unrestricted_district_access():
    adapter = FormalPolicyEngineAdapter()
    # Admin from central accessing south resource
    result = adapter.evaluate(
        _identity(role="admin", district_id="district_central"),
        _action("reserve_spot", resource_id="park_south_1", resource_district_id="district_south"),
    )
    assert result.decision == Decision.ALLOW
    assert result.reason_code == "POLICY_ALLOW"


@pytest.mark.parametrize("domain, op", [
    ("grid", "reroute_power"),
    ("grid", "isolate_substation"),
    ("transit", "emergency_stop"),
    ("water", "open_valve"),
    ("emergency", "broadcast_alert"),
    ("parking", "close_zone"),
])
def test_high_impact_operations_require_approval(domain, op):
    adapter = FormalPolicyEngineAdapter()
    result = adapter.evaluate(
        _identity(role="admin", district_id="district_north"),
        _action(op, domain=domain, resource_district_id="district_north"),
    )
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"


def test_unregistered_operation_denied():
    adapter = FormalPolicyEngineAdapter()
    result = adapter.evaluate(_identity(role="admin"), _action("teleport_cars", domain="parking"))
    assert result.decision == Decision.DENY
    assert result.reason_code == "UNKNOWN_OPERATION"


def test_unregistered_domain_denied():
    adapter = FormalPolicyEngineAdapter()
    result = adapter.evaluate(_identity(role="admin"), _action("status", domain="space_exploration"))
    assert result.decision == Decision.DENY
    assert result.reason_code == "UNKNOWN_DOMAIN"


def test_registered_operation_without_role_permission_is_denied(monkeypatch):
    """Adding an operation to VALID_DOMAINS without ROLE_PERMISSIONS must fail closed."""
    adapter = FormalPolicyEngineAdapter()
    engine = getattr(adapter, "engine", getattr(adapter, "_engine", None))
    domains = {k: set(v) for k, v in getattr(engine, "VALID_DOMAINS", {}).items()}
    domains["parking"].add("delete_lot")
    monkeypatch.setattr(engine, "VALID_DOMAINS", domains)

    for role in ("admin", "operator", "viewer"):
        result = adapter.evaluate(_identity(role=role), _action("delete_lot"))
        assert result.decision == Decision.DENY
        assert result.reason_code == "ROLE_NOT_AUTHORIZED"


# =====================================================================
# 5. Policy Testing and Runtime Endpoints in REAL mode
# =====================================================================

def test_policy_testing_endpoint_all_six_scenarios_pass_in_real_mode():
    adapter = FormalPolicyEngineAdapter()
    tester = PolicyTester(policy_engine=adapter)
    report = tester.run_suite()

    assert report.all_passed is True
    assert report.total == 6
    assert report.failed == 0

    results_by_name = {r.test_name: r for r in report.results}

    # 1. Authorized same-district access
    r1 = results_by_name["authorized_same_district_access"]
    assert r1.passed is True
    assert r1.actual_decision == Decision.ALLOW
    assert r1.actual_reason_code == "POLICY_ALLOW"

    # 2. Cross-district access
    r2 = results_by_name["cross_district_access_denied"]
    assert r2.passed is True
    assert r2.actual_decision == Decision.DENY
    assert r2.actual_reason_code == "DISTRICT_MISMATCH"

    # 3. Unauthorized role operation
    r3 = results_by_name["unauthorized_role_operation_denied"]
    assert r3.passed is True
    assert r3.actual_decision == Decision.DENY
    assert r3.actual_reason_code == "ROLE_NOT_AUTHORIZED"

    # 4. High-impact operation requires approval
    r4 = results_by_name["high_impact_operation_requires_approval"]
    assert r4.passed is True
    assert r4.actual_decision == Decision.APPROVAL_REQUIRED
    assert r4.actual_reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"

    # 5. Unknown domain
    r5 = results_by_name["unknown_domain_denied"]
    assert r5.passed is True
    assert r5.actual_decision == Decision.DENY
    assert r5.actual_reason_code == "UNKNOWN_DOMAIN"

    # 6. Unknown operation
    r6 = results_by_name["unknown_operation_denied"]
    assert r6.passed is True
    assert r6.actual_decision == Decision.DENY
    assert r6.actual_reason_code == "UNKNOWN_OPERATION"


def test_shared_real_engine_across_runtime_and_policy_testing(monkeypatch):
    adapter = FormalPolicyEngineAdapter()
    gateway = GatewayService(policy_engine=adapter)
    tester = PolicyTester(policy_engine=adapter)

    monkeypatch.setitem(app.dependency_overrides, get_gateway_service, lambda: gateway)
    monkeypatch.setitem(app.dependency_overrides, get_policy_tester, lambda: tester)

    with TestClient(app) as client:
        # Runtime evaluation
        request = EvaluationRequest(
            request_id="req-runtime-real",
            action=_action("read", resource_id="park_north_1", resource_district_id="district_north"),
        )
        runtime_resp = client.post(
            "/api/v1/requests/evaluate",
            json=request.model_dump(),
            headers={"Authorization": "Bearer token_operator_north"},
        )
        assert runtime_resp.status_code == 200
        assert runtime_resp.json()["decision"] == "allow"
        assert runtime_resp.json()["executed"] is True

        # Policy testing
        test_resp = client.post("/api/v1/policies/test")
        assert test_resp.status_code == 200
        assert test_resp.json()["all_passed"] is True
        assert test_resp.json()["total"] == 6


def test_approval_required_blocks_execution_in_real_mode(monkeypatch):
    adapter = FormalPolicyEngineAdapter()
    parking = MockParkingService()
    before = deepcopy(parking.records)
    gateway = GatewayService(policy_engine=adapter, parking_service=parking)
    monkeypatch.setitem(app.dependency_overrides, get_gateway_service, lambda: gateway)

    request = EvaluationRequest(
        request_id="req-close-zone-real",
        action=_action("close_zone", resource_id="park_north_1", resource_district_id="district_north"),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/requests/evaluate",
            json=request.model_dump(),
            headers={"Authorization": "Bearer token_operator_north"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "approval_required"
    assert data["reason_code"] == "HIGH_IMPACT_APPROVAL_REQUIRED"
    assert data["executed"] is False
    assert data["result"] is None
    assert parking.call_count == 0
    assert parking.records == before
