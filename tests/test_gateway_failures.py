from copy import deepcopy
from types import SimpleNamespace
from typing import Optional
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.gateway import get_gateway_service
from app.main import app
from app.schemas import ActionRequest, Decision, EvaluationRequest
from app.services.audit import AuditService
from app.services.gateway import GatewayService
from app.services.identity import IdentityResolver, TrustedIdentity
from app.services.parking import MockParkingService
from app.services.policy import PolicyEngineAdapter, PolicyEvaluationResult


# Deliberately sensitive-looking test data: never surface exception text.
INTERNAL_ERROR = "private-backend-detail Bearer test-secret-do-not-expose"


@pytest.fixture
def failure_case(monkeypatch, caplog):
    policy = Mock(spec=PolicyEngineAdapter)
    policy.is_valid_domain.return_value = True
    policy.is_valid_operation.return_value = True
    policy.evaluate.return_value = PolicyEvaluationResult(
        decision=Decision.ALLOW, reason_code="POLICY_ALLOW", message="Allowed"
    )
    identity = Mock(spec=IdentityResolver)
    identity.resolve.return_value = TrustedIdentity(
        user_id="user_operator_north", role="operator", district_id="district_north"
    )
    parking = MockParkingService()
    parking.execute = Mock(wraps=parking.execute)
    parking.get_resource = Mock(wraps=parking.get_resource)
    audit = AuditService()
    audit.record = Mock(wraps=audit.record)
    gateway = GatewayService(
        policy_engine=policy,
        identity_resolver=identity,
        parking_service=parking,
        audit_service=audit,
    )
    monkeypatch.setitem(app.dependency_overrides, get_gateway_service, lambda: gateway)
    request = EvaluationRequest(
        request_id="req-failure-check",
        action=ActionRequest(
            request_id="req-failure-check",
            domain="parking",
            operation="reserve_spot",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    with TestClient(app) as client:
        yield SimpleNamespace(
            policy=policy, identity=identity, parking=parking, audit=audit,
            request=request, client=client, caplog=caplog,
            initial_records=deepcopy(parking.records),
        )


def _evaluate(case):
    response = case.client.post(
        "/api/v1/requests/evaluate",
        json=case.request.model_dump(),
        headers={"Authorization": "Bearer test-secret-do-not-expose"},
    )
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "request_id", "decision", "reason_code", "message", "executed", "audit_id", "result"
    }
    assert data["request_id"] == case.request.request_id
    assert data["audit_id"].startswith("aud_")
    for private_text in (INTERNAL_ERROR, "test-secret-do-not-expose", "Traceback"):
        assert private_text not in response.text
        assert private_text not in case.caplog.text
        assert all(private_text not in e.model_dump_json() for e in case.audit.get_events())
    return data


def _assert_audit(case, data, *, decision, status, error=None, user_id: Optional[str] = "user_operator_north"):
    case.audit.record.assert_called_once()
    events = case.audit.get_by_request_id(case.request.request_id)
    assert len(events) == 1
    event = events[0]
    assert event.audit_id == data["audit_id"]
    assert event.request_id == data["request_id"]
    assert event.decision == data["decision"] == decision
    assert event.reason_code == data["reason_code"]
    assert event.executed is data["executed"]
    assert event.execution_status == status
    assert event.error == error
    assert event.user_id == user_id


def test_policy_engine_exception_does_not_execute_service(failure_case):
    case = failure_case
    case.policy.evaluate.side_effect = RuntimeError(INTERNAL_ERROR)

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "POLICY_ENGINE_FAILED"
    assert data["executed"] is False
    assert data["result"] is None
    case.parking.execute.assert_not_called()
    assert case.parking.records == case.initial_records
    _assert_audit(case, data, decision="deny", status="not_attempted", error="POLICY_ENGINE_FAILED")


def test_policy_engine_exception_produces_controlled_failure(failure_case):
    case = failure_case
    case.policy.evaluate.side_effect = TimeoutError(INTERNAL_ERROR)

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "POLICY_ENGINE_FAILED"
    assert data["executed"] is False
    assert data["result"] is None
    assert data["message"] == "Policy evaluation could not be completed safely"
    case.policy.evaluate.assert_called_once()
    case.parking.execute.assert_not_called()
    _assert_audit(case, data, decision="deny", status="not_attempted", error="POLICY_ENGINE_FAILED")


def test_service_exception_returns_execution_failure(failure_case):
    case = failure_case
    case.parking.execute.side_effect = RuntimeError(INTERNAL_ERROR)

    data = _evaluate(case)

    assert data["decision"] == "allow"
    assert data["reason_code"] == "POLICY_ALLOW"
    assert data["executed"] is False
    assert data["result"]["success"] is False
    assert data["result"]["reason_code"] == "SERVICE_EXECUTION_FAILED"
    assert "could not be confirmed" in data["message"]
    case.parking.execute.assert_called_once()
    assert case.parking.records == case.initial_records
    _assert_audit(case, data, decision="allow", status="failed", error="SERVICE_EXECUTION_FAILED")


def test_service_exception_is_audited(failure_case):
    case = failure_case
    case.parking.execute.side_effect = TimeoutError(INTERNAL_ERROR)

    data = _evaluate(case)

    assert data["executed"] is False
    case.parking.execute.assert_called_once()
    _assert_audit(case, data, decision="allow", status="failed", error="SERVICE_EXECUTION_FAILED")


def test_identity_resolution_failure_does_not_execute_service(failure_case):
    case = failure_case
    case.identity.resolve.side_effect = RuntimeError(INTERNAL_ERROR)

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "IDENTITY_RESOLUTION_FAILED"
    assert data["executed"] is False
    assert data["result"] is None
    case.policy.evaluate.assert_not_called()
    case.parking.get_resource.assert_not_called()
    case.parking.execute.assert_not_called()
    assert case.parking.records == case.initial_records
    _assert_audit(
        case, data, decision="deny", status="not_attempted",
        error="IDENTITY_RESOLUTION_FAILED", user_id=None,
    )


def test_resource_lookup_failure_fails_closed(failure_case):
    case = failure_case
    case.request.action.resource_id = "park_south_1"  # Still falsely claims north.
    case.parking.get_resource.side_effect = RuntimeError(INTERNAL_ERROR)

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "RESOURCE_LOOKUP_FAILED"
    assert data["executed"] is False
    assert data["result"] is None
    case.parking.get_resource.assert_called_once_with("park_south_1")
    case.policy.evaluate.assert_not_called()
    case.parking.execute.assert_not_called()
    assert case.parking.records == case.initial_records
    _assert_audit(case, data, decision="deny", status="not_attempted", error="RESOURCE_LOOKUP_FAILED")


@pytest.mark.parametrize("method", ["is_valid_domain", "is_valid_operation"])
def test_policy_validation_exception_fails_closed(failure_case, method):
    case = failure_case
    getattr(case.policy, method).side_effect = RuntimeError(INTERNAL_ERROR)

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "POLICY_ENGINE_FAILED"
    assert data["executed"] is False
    assert data["result"] is None
    case.identity.resolve.assert_not_called()
    case.policy.evaluate.assert_not_called()
    case.parking.execute.assert_not_called()
    assert case.parking.records == case.initial_records
    _assert_audit(
        case, data, decision="deny", status="not_attempted",
        error="POLICY_ENGINE_FAILED", user_id=None,
    )


@pytest.mark.parametrize("result", [None, object(), {"decision": "allow"}])
def test_malformed_policy_result_fails_closed(failure_case, result):
    case = failure_case
    case.policy.evaluate.return_value = result

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "POLICY_ENGINE_FAILED"
    assert data["executed"] is False
    assert data["result"] is None
    case.parking.execute.assert_not_called()
    _assert_audit(case, data, decision="deny", status="not_attempted", error="POLICY_ENGINE_FAILED")


@pytest.mark.parametrize("result", [None, {}, {"success": "false"}, {"success": False, "error": []}])
def test_malformed_service_result_cannot_claim_success(failure_case, result):
    case = failure_case
    case.parking.execute.return_value = result

    data = _evaluate(case)

    assert data["decision"] == "allow"
    assert data["reason_code"] == "POLICY_ALLOW"
    assert data["executed"] is False
    assert data["result"]["success"] is False
    case.parking.execute.assert_called_once()
    _assert_audit(case, data, decision="allow", status="failed", error="SERVICE_EXECUTION_FAILED")


def test_malformed_identity_result_cannot_reach_protected_service(failure_case):
    case = failure_case
    case.identity.resolve.return_value = {"user_id": "user_operator_north"}

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "IDENTITY_RESOLUTION_FAILED"
    assert data["executed"] is False
    assert data["result"] is None
    case.policy.evaluate.assert_not_called()
    case.parking.get_resource.assert_not_called()
    case.parking.execute.assert_not_called()
    _assert_audit(
        case, data, decision="deny", status="not_attempted",
        error="IDENTITY_RESOLUTION_FAILED", user_id=None,
    )


@pytest.mark.parametrize("resource", [[], "bad-record", {
    "resource_id": "park_south_1", "district_id": "district_north"
}])
def test_malformed_resource_lookup_fails_closed(failure_case, resource):
    case = failure_case
    case.parking.get_resource.return_value = resource

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "RESOURCE_LOOKUP_FAILED"
    assert data["executed"] is False
    assert data["result"] is None
    case.policy.evaluate.assert_not_called()
    case.parking.execute.assert_not_called()
    assert case.parking.records == case.initial_records
    _assert_audit(case, data, decision="deny", status="not_attempted", error="RESOURCE_LOOKUP_FAILED")


@pytest.mark.parametrize("district", [None, "", "   ", 123, []])
def test_invalid_authoritative_district_cannot_reach_policy(failure_case, district):
    case = failure_case
    case.parking.records["park_north_1"]["district_id"] = district
    before = deepcopy(case.parking.records)

    data = _evaluate(case)

    assert data["decision"] == "deny"
    assert data["reason_code"] == "INVALID_RESOURCE_DISTRICT"
    assert data["executed"] is False
    assert data["result"] is None
    case.policy.evaluate.assert_not_called()
    case.parking.execute.assert_not_called()
    assert case.parking.records == before
    _assert_audit(case, data, decision="deny", status="not_attempted")


@pytest.mark.parametrize("write_before_raising", [False, True])
@pytest.mark.parametrize("scenario, decision, reason, status, calls, error", [
    ("allow", "allow", "POLICY_ALLOW", "success", 1, None),
    ("deny", "deny", "DISTRICT_MISMATCH", "not_attempted", 0, None),
    ("approval", "approval_required", "HIGH_IMPACT_APPROVAL_REQUIRED", "not_attempted", 0, None),
    ("policy_failure", "deny", "POLICY_ENGINE_FAILED", "not_attempted", 0, "POLICY_ENGINE_FAILED"),
    ("identity_failure", "deny", "IDENTITY_RESOLUTION_FAILED", "not_attempted", 0, "IDENTITY_RESOLUTION_FAILED"),
    ("resource_failure", "deny", "RESOURCE_LOOKUP_FAILED", "not_attempted", 0, "RESOURCE_LOOKUP_FAILED"),
    ("service_failure", "allow", "POLICY_ALLOW", "failed", 1, "SERVICE_EXECUTION_FAILED"),
    ("unauthenticated", "deny", "UNAUTHENTICATED_ACTOR", "not_attempted", 0, None),
])
def test_audit_failure_preserves_outcome_without_retries(
    failure_case, write_before_raising, scenario, decision, reason, status, calls, error
):
    case = failure_case
    if scenario in ("deny", "approval"):
        case.policy.evaluate.return_value = PolicyEvaluationResult(
            decision=Decision(decision), reason_code=reason, message="Operation blocked"
        )
        case.parking.execute.side_effect = RuntimeError(INTERNAL_ERROR)
    elif scenario == "policy_failure":
        case.policy.evaluate.side_effect = RuntimeError(INTERNAL_ERROR)
    elif scenario == "identity_failure":
        case.identity.resolve.side_effect = RuntimeError(INTERNAL_ERROR)
    elif scenario == "resource_failure":
        case.parking.get_resource.side_effect = RuntimeError(INTERNAL_ERROR)
    elif scenario == "service_failure":
        case.parking.execute.side_effect = RuntimeError(INTERNAL_ERROR)
    elif scenario == "unauthenticated":
        case.identity.resolve.return_value = None

    def record_then_raise(event):
        if write_before_raising:
            AuditService.record(case.audit, event)
        raise RuntimeError(INTERNAL_ERROR)

    case.audit.record.side_effect = record_then_raise
    data = _evaluate(case)

    assert data["decision"] == decision
    assert data["reason_code"] == reason
    assert data["executed"] is (status == "success")
    assert "Audit recording could not be confirmed" in data["message"]
    assert "Do not automatically retry" in data["message"]
    assert "not persisted" not in data["message"]
    assert case.parking.execute.call_count == calls
    case.audit.record.assert_called_once()
    event = case.audit.record.call_args.args[0]
    assert event.audit_id == data["audit_id"]
    assert event.request_id == data["request_id"]
    assert event.decision == decision
    assert event.reason_code == reason
    assert event.executed is data["executed"]
    assert event.execution_status == status
    assert event.error == error
    assert event.user_id == (
        None if scenario in ("identity_failure", "unauthenticated") else "user_operator_north"
    )
    assert case.audit.get_events() == ([event] if write_before_raising else [])
    assert len(case.caplog.records) == 1
    assert case.caplog.records[0].exc_info is None
    assert case.caplog.records[0].getMessage() == f"AUDIT_RECORDING_FAILED audit_id={data['audit_id']}"

    expected_records = deepcopy(case.initial_records)
    if status == "success":
        expected_records["park_north_1"]["available_spots"] -= 1
        assert data["result"]["success"] is True
    elif calls == 0:
        assert data["result"] is None
    else:
        assert data["result"]["success"] is False
    assert case.parking.records == expected_records


def test_service_exception_after_mutation_is_not_retried_or_claimed_rolled_back(failure_case):
    case = failure_case

    def mutate_then_raise(**kwargs):
        MockParkingService.execute(case.parking, **kwargs)
        raise RuntimeError(INTERNAL_ERROR)

    case.parking.execute.side_effect = mutate_then_raise
    data = _evaluate(case)

    assert data["decision"] == "allow"
    assert data["executed"] is False
    assert data["result"]["success"] is False
    assert "side effects may have occurred" in data["message"]
    assert "Do not automatically retry" in data["message"]
    case.parking.execute.assert_called_once()
    expected_records = deepcopy(case.initial_records)
    expected_records["park_north_1"]["available_spots"] -= 1
    assert case.parking.records == expected_records
    _assert_audit(case, data, decision="allow", status="failed", error="SERVICE_EXECUTION_FAILED")
