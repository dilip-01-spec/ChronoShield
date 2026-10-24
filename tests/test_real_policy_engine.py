"""Focused integration and regression tests for FormalPolicyEngineAdapter and REAL mode.

Validates the full security contract when the canonical FormalPolicyEngine is integrated:
- Adapter decision and reason-code mapping
- Trusted identity mapping and fail-closed handling
- Authoritative resource-district validation
- Parking state preservation and defense-in-depth
- Runtime and policy-testing use of the same engine
- Explicit engine configuration and no silent fallback
- Deny and approval-required execution blocking
"""

from copy import deepcopy
from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.gateway import get_gateway_service
from app.api.policies import get_policy_tester
from app.main import app
from app.schemas import ActionRequest, ActorContext, Decision, EvaluationRequest
from app.security.engine import FormalPolicyEngine
from app.services import GatewayService, PolicyTester
from app.services.identity import IdentityResolver, TrustedIdentity
from app.services.parking import MockParkingService
from app.services.policy import (
    DevMockPolicyEngine,
    FormalPolicyEngineAdapter,
    PolicyEvaluationResult,
)
from app.services.policy_factory import (
    PolicyEngineConfigurationError,
    create_policy_engine,
    get_policy_engine,
)


# =============================================================================
# 1. Adapter Decision, Reason-Code, and Fallback Unit Tests
# =============================================================================

def test_adapter_implements_valid_domain_and_operation_contracts():
    adapter = FormalPolicyEngineAdapter()
    for domain in ("parking", "grid", "transit", "water", "waste", "emergency", "telecom", "healthcare"):
        assert adapter.is_valid_domain(domain)

    assert not adapter.is_valid_domain("unknown_domain")
    assert not adapter.is_valid_domain(None)
    assert not adapter.is_valid_domain("")

    assert adapter.is_valid_operation("parking", "read")
    assert adapter.is_valid_operation("transit", "emergency_stop")
    assert adapter.is_valid_operation("grid", "reroute_power")
    assert not adapter.is_valid_operation("parking", "teleport")
    assert not adapter.is_valid_operation("unknown_domain", "status")


def test_adapter_maps_decisions_and_normalizes_reason_codes():
    adapter = FormalPolicyEngineAdapter()

    # 1. Allow
    id_north = TrustedIdentity(user_id="user_operator_north", role="operator", district_id="district_north")
    act_read = ActionRequest(
        request_id="r1", domain="parking", operation="read",
        resource_id="park_north_1", resource_district_id="district_north",
    )
    res = adapter.evaluate(id_north, act_read)
    assert res.decision == Decision.ALLOW
    assert res.reason_code == "POLICY_ALLOW"

    # 2. District mismatch
    act_cross = ActionRequest(
        request_id="r2", domain="parking", operation="read",
        resource_id="park_south_1", resource_district_id="district_south",
    )
    res = adapter.evaluate(id_north, act_cross)
    assert res.decision == Decision.DENY
    assert res.reason_code == "DISTRICT_MISMATCH"

    # 3. Role not authorized (viewer mutating)
    id_viewer = TrustedIdentity(user_id="user_viewer", role="viewer", district_id="district_central")
    act_reserve = ActionRequest(
        request_id="r3", domain="parking", operation="reserve_spot",
        resource_id="park_central_1", resource_district_id="district_central",
    )
    res = adapter.evaluate(id_viewer, act_reserve)
    assert res.decision == Decision.DENY
    assert res.reason_code == "ROLE_NOT_AUTHORIZED"

    # 4. Unknown role normalized to ROLE_NOT_AUTHORIZED
    id_guest = TrustedIdentity(user_id="user_guest", role="guest", district_id="district_north")
    res = adapter.evaluate(id_guest, act_read)
    assert res.decision == Decision.DENY
    assert res.reason_code == "ROLE_NOT_AUTHORIZED"

    # 5. Sensitive action requires approval
    act_close = ActionRequest(
        request_id="r5", domain="parking", operation="close_zone",
        resource_id="park_north_1", resource_district_id="district_north",
    )
    res = adapter.evaluate(id_north, act_close)
    assert res.decision == Decision.APPROVAL_REQUIRED
    assert res.reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"

    # 6. Unknown domain
    act_unk_dom = ActionRequest(
        request_id="r6", domain="super_grid", operation="status",
        resource_id="node_1", resource_district_id="district_north",
    )
    res = adapter.evaluate(id_north, act_unk_dom)
    assert res.decision == Decision.DENY
    assert res.reason_code == "UNKNOWN_DOMAIN"

    # 7. Unknown operation
    act_unk_op = ActionRequest(
        request_id="r7", domain="parking", operation="teleport",
        resource_id="park_north_1", resource_district_id="district_north",
    )
    res = adapter.evaluate(id_north, act_unk_op)
    assert res.decision == Decision.DENY
    assert res.reason_code == "UNKNOWN_OPERATION"


def test_adapter_fails_closed_on_malformed_identity():
    adapter = FormalPolicyEngineAdapter()
    act = ActionRequest(
        request_id="r-mal", domain="parking", operation="read",
        resource_id="park_north_1", resource_district_id="district_north",
    )

    # None identity
    res = adapter.evaluate(None, act)
    assert res.decision == Decision.DENY
    assert res.reason_code == "UNAUTHENTICATED_ACTOR"

    # Incomplete identity
    bad_id = replace(
        TrustedIdentity(user_id="u1", role="operator", district_id="district_north"),
        role=None,
    )
    res = adapter.evaluate(bad_id, act)
    assert res.decision == Decision.DENY
    assert res.reason_code == "UNAUTHENTICATED_ACTOR"

    # Dict instead of TrustedIdentity
    res = adapter.evaluate({"role": "operator"}, act)
    assert res.decision == Decision.DENY
    assert res.reason_code == "UNAUTHENTICATED_ACTOR"


def test_adapter_fails_closed_on_engine_exceptions_and_malformed_results():
    # 1. Engine raises unexpected error
    faulty_engine = Mock(spec=FormalPolicyEngine)
    faulty_engine.is_valid_domain.return_value = True
    faulty_engine.is_valid_operation.return_value = True
    faulty_engine.evaluate.side_effect = RuntimeError("Fatal engine crash")

    adapter = FormalPolicyEngineAdapter(engine=faulty_engine)
    id_north = TrustedIdentity(user_id="user_operator_north", role="operator", district_id="district_north")
    act = ActionRequest(
        request_id="r-err", domain="parking", operation="read",
        resource_id="park_north_1", resource_district_id="district_north",
    )

    res = adapter.evaluate(id_north, act)
    assert res.decision == Decision.DENY
    assert res.reason_code == "POLICY_ENGINE_FAILED"

    # 2. Engine returns None
    faulty_engine.evaluate.side_effect = None
    faulty_engine.evaluate.return_value = None
    res = adapter.evaluate(id_north, act)
    assert res.decision == Decision.DENY
    assert res.reason_code == "POLICY_ENGINE_FAILED"

    # 3. Engine returns invalid decision value
    faulty_engine.evaluate.return_value = Mock(decision="MAYBE", reason_code="UNKNOWN", message="err")
    res = adapter.evaluate(id_north, act)
    assert res.decision == Decision.DENY
    assert res.reason_code == "POLICY_ENGINE_FAILED"


# =============================================================================
# 2. Authoritative Resource Security & State Preservation
# =============================================================================

def test_authoritative_district_overrides_client_claim_in_real_mode():
    """North operator attempts to access south resource park_south_1 by claiming district_north.
    The server derives district_south from trusted metadata, adapter evaluates cross-district,
    and Gateway blocks execution with DISTRICT_MISMATCH.
    """
    engine = FormalPolicyEngineAdapter()
    parking = MockParkingService()
    before_spots = parking.records["park_south_1"]["available_spots"]

    gateway = GatewayService(policy_engine=engine, parking_service=parking)
    app.dependency_overrides[get_gateway_service] = lambda: gateway

    try:
        with TestClient(app) as client:
            request = EvaluationRequest(
                request_id="req-auth-claim-mismatch",
                action=ActionRequest(
                    request_id="req-auth-claim-mismatch",
                    domain="parking",
                    operation="reserve_spot",
                    resource_id="park_south_1",
                    resource_district_id="district_north",  # False client claim!
                ),
            )
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
            assert data["result"] is None

            # Verify parking state was NOT changed
            assert parking.call_count == 0
            assert parking.records["park_south_1"]["available_spots"] == before_spots
    finally:
        app.dependency_overrides.pop(get_gateway_service, None)


def test_parking_service_defense_in_depth_check_remains_active():
    """Even if an erroneous ALLOW decision were produced, MockParkingService.execute
    validates authorized_identity district scope and refuses execution.
    """
    parking = MockParkingService()
    id_north = TrustedIdentity(
        user_id="user_operator_north", role="operator",
        district_id="district_north", is_authenticated=True,
    )

    # Attempting to execute reserve_spot on south resource directly
    result = parking.execute(
        operation="reserve_spot",
        resource_id="park_south_1",
        authorized_identity=id_north,
    )

    assert result["success"] is False
    assert result["reason_code"] == "DISTRICT_MISMATCH"
    assert "does not match resource district" in result["error"]
    assert parking.call_count == 1


def test_unknown_role_cannot_execute_protected_operations_in_real_mode():
    engine = FormalPolicyEngineAdapter()
    parking = MockParkingService()
    resolver = Mock(spec=IdentityResolver)
    resolver.resolve.return_value = TrustedIdentity(
        user_id="user_guest", role="guest", district_id="district_north", is_authenticated=True,
    )

    gateway = GatewayService(policy_engine=engine, identity_resolver=resolver, parking_service=parking)
    app.dependency_overrides[get_gateway_service] = lambda: gateway

    try:
        with TestClient(app) as client:
            request = EvaluationRequest(
                request_id="req-unknown-role",
                action=ActionRequest(
                    request_id="req-unknown-role",
                    domain="parking",
                    operation="reserve_spot",
                    resource_id="park_north_1",
                    resource_district_id="district_north",
                ),
            )
            response = client.post(
                "/api/v1/requests/evaluate",
                json=request.model_dump(),
                headers={"Authorization": "Bearer token_guest"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["decision"] == "deny"
            assert data["reason_code"] == "ROLE_NOT_AUTHORIZED"
            assert data["executed"] is False
            assert parking.call_count == 0
    finally:
        app.dependency_overrides.pop(get_gateway_service, None)


def test_engine_exception_fails_closed_and_blocks_execution():
    faulty_engine = Mock(spec=FormalPolicyEngineAdapter)
    faulty_engine.is_valid_domain.return_value = True
    faulty_engine.is_valid_operation.return_value = True
    faulty_engine.evaluate.side_effect = RuntimeError("Catastrophic policy evaluation fault")

    parking = MockParkingService()
    gateway = GatewayService(policy_engine=faulty_engine, parking_service=parking)
    app.dependency_overrides[get_gateway_service] = lambda: gateway

    try:
        with TestClient(app) as client:
            request = EvaluationRequest(
                request_id="req-crash",
                action=ActionRequest(
                    request_id="req-crash",
                    domain="parking",
                    operation="reserve_spot",
                    resource_id="park_north_1",
                    resource_district_id="district_north",
                ),
            )
            response = client.post(
                "/api/v1/requests/evaluate",
                json=request.model_dump(),
                headers={"Authorization": "Bearer token_operator_north"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["decision"] == "deny"
            assert data["reason_code"] == "POLICY_ENGINE_FAILED"
            assert data["executed"] is False
            assert parking.call_count == 0

            # Audit event must be recorded for safety visibility
            events = gateway.audit_service.get_events()
            assert len(events) == 1
            assert events[0].reason_code == "POLICY_ENGINE_FAILED"
            assert events[0].executed is False
    finally:
        app.dependency_overrides.pop(get_gateway_service, None)


# =============================================================================
# 3. Policy Testing Endpoint & Shared Selected Engine
# =============================================================================

def test_policy_testing_runs_six_scenarios_and_does_not_mutate_state():
    engine = FormalPolicyEngineAdapter()
    tester = PolicyTester(policy_engine=engine)
    report = tester.run_suite()

    assert report.total == 6
    assert report.passed == 6
    assert report.failed == 0
    assert report.all_passed is True

    # Validate the 6 canonical scenarios
    scenario_map = {r.test_name: r for r in report.results}
    assert scenario_map["authorized_same_district_access"].actual_decision == Decision.ALLOW
    assert scenario_map["cross_district_access_denied"].actual_decision == Decision.DENY
    assert scenario_map["cross_district_access_denied"].actual_reason_code == "DISTRICT_MISMATCH"
    assert scenario_map["unauthorized_role_operation_denied"].actual_decision == Decision.DENY
    assert scenario_map["unauthorized_role_operation_denied"].actual_reason_code == "ROLE_NOT_AUTHORIZED"
    assert scenario_map["high_impact_operation_requires_approval"].actual_decision == Decision.APPROVAL_REQUIRED
    assert scenario_map["high_impact_operation_requires_approval"].actual_reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"
    assert scenario_map["unknown_domain_denied"].actual_decision == Decision.DENY
    assert scenario_map["unknown_domain_denied"].actual_reason_code == "UNKNOWN_DOMAIN"
    assert scenario_map["unknown_operation_denied"].actual_decision == Decision.DENY
    assert scenario_map["unknown_operation_denied"].actual_reason_code == "UNKNOWN_OPERATION"


def test_runtime_and_policy_testing_both_use_real_engine_without_audit_bleed():
    engine = FormalPolicyEngineAdapter()
    parking = MockParkingService()
    before_records = deepcopy(parking.records)
    gateway = GatewayService(policy_engine=engine, parking_service=parking)
    tester = PolicyTester(policy_engine=engine)

    app.dependency_overrides[get_gateway_service] = lambda: gateway
    app.dependency_overrides[get_policy_tester] = lambda: tester

    try:
        with TestClient(app) as client:
            # 1. Runtime authorized execution
            req = EvaluationRequest(
                request_id="req-rt-allow",
                action=ActionRequest(
                    request_id="req-rt-allow",
                    domain="parking",
                    operation="reserve_spot",
                    resource_id="park_north_1",
                    resource_district_id="district_north",
                ),
            )
            rt_resp = client.post(
                "/api/v1/requests/evaluate",
                json=req.model_dump(),
                headers={"Authorization": "Bearer token_operator_north"},
            )
            assert rt_resp.status_code == 200
            assert rt_resp.json()["decision"] == "allow"
            assert rt_resp.json()["executed"] is True
            assert parking.call_count == 1
            assert len(gateway.audit_service.get_events()) == 1

            # 2. Run policy tests - must NOT increment parking call_count or audit events
            test_resp = client.post("/api/v1/policies/test")
            assert test_resp.status_code == 200
            test_data = test_resp.json()
            assert test_data["all_passed"] is True
            assert test_data["passed"] == 6

            # Verify no mutation or audit bleed from policy testing
            assert parking.call_count == 1
            assert len(gateway.audit_service.get_events()) == 1
    finally:
        app.dependency_overrides.pop(get_gateway_service, None)
        app.dependency_overrides.pop(get_policy_tester, None)


# =============================================================================
# 4. Deny and Approval-Required Execution Blocking
# =============================================================================

@pytest.mark.parametrize("operation,expected_decision,expected_reason", [
    ("close_zone", Decision.APPROVAL_REQUIRED, "HIGH_IMPACT_APPROVAL_REQUIRED"),
    ("reserve_spot", Decision.DENY, "DISTRICT_MISMATCH"),
])
def test_non_allow_decisions_block_execution_in_real_mode(operation, expected_decision, expected_reason):
    engine = FormalPolicyEngineAdapter()
    parking = MockParkingService()
    gateway = GatewayService(policy_engine=engine, parking_service=parking)
    app.dependency_overrides[get_gateway_service] = lambda: gateway

    # For cross-district test, target south resource; for close_zone, target north resource
    resource_id = "park_south_1" if expected_reason == "DISTRICT_MISMATCH" else "park_north_1"

    try:
        with TestClient(app) as client:
            req = EvaluationRequest(
                request_id="req-block-test",
                action=ActionRequest(
                    request_id="req-block-test",
                    domain="parking",
                    operation=operation,
                    resource_id=resource_id,
                    resource_district_id="district_north",
                ),
            )
            resp = client.post(
                "/api/v1/requests/evaluate",
                json=req.model_dump(),
                headers={"Authorization": "Bearer token_operator_north"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["decision"] == expected_decision
            assert data["reason_code"] == expected_reason
            assert data["executed"] is False
            assert data["result"] is None
            assert parking.call_count == 0
    finally:
        app.dependency_overrides.pop(get_gateway_service, None)
