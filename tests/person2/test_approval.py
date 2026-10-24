
import pytest

from app.security.approval import ApprovalManager
from app.security.schemas import ActionRequest, SecurityDecision


@pytest.fixture
def setup_approval():
    manager = ApprovalManager()

    requester = {
        "id": "agent_101",
        "role": "water_agent",
    }

    approver = {
        "id": "admin_001",
        "role": "admin",
    }

    request = ActionRequest(
        domain="water",
        action="update",
        resource_id="water_101",
        parameters={"valve_setting": "restricted"},
        reason="Water system update",
    )

    decision = SecurityDecision(
        decision="REQUIRES_APPROVAL",
        reason_code="SENSITIVE_ACTION",
        message="Human approval is required",
    )

    record = manager.submit(requester, request, decision)

    return manager, requester, approver, request, decision, record


def test_submit_creates_pending_request(setup_approval):
    manager, _, _, _, _, record = setup_approval

    assert record.status == "PENDING"
    assert record.domain == "water"
    assert record.requested_by == "agent_101"
    assert manager.get(record.request_id) is not None


def test_only_approval_required_requests_can_be_submitted(setup_approval):
    manager, requester, request, _, _, _ = (
        setup_approval[0],
        setup_approval[1],
        setup_approval[3],
        setup_approval[3],
        setup_approval[4],
        setup_approval[5],
    )

    allow_decision = SecurityDecision(
        decision="ALLOW",
        reason_code="POLICY_MATCH",
        message="Request is authorized",
    )

    with pytest.raises(ValueError):
        manager.submit(requester, request, allow_decision)


def test_admin_can_approve_request(setup_approval):
    manager, _, approver, _, _, record = setup_approval

    result = manager.decide(
        record.request_id, approver, True, "Verified by admin"
    )

    assert result.status == "APPROVED"
    assert result.decided_by == "admin_001"
    assert result.decision_reason == "Verified by admin"


def test_admin_can_reject_request(setup_approval):
    manager, _, approver, _, _, record = setup_approval

    result = manager.decide(
        record.request_id, approver, False, "Unsafe operation"
    )

    assert result.status == "REJECTED"
    assert result.decision_reason == "Unsafe operation"


def test_non_admin_cannot_decide_request(setup_approval):
    manager, _, _, _, _, record = setup_approval

    traffic_agent = {
        "id": "agent_traffic",
        "role": "traffic_agent",
    }

    with pytest.raises(PermissionError):
        manager.decide(record.request_id, traffic_agent, True)


def test_requester_cannot_approve_own_request(setup_approval):
    manager, requester, _, _, _, record = setup_approval

    requester["role"] = "admin"

    with pytest.raises(PermissionError):
        manager.decide(record.request_id, requester, True)


def test_already_decided_request_cannot_be_decided_again(setup_approval):
    manager, _, approver, _, _, record = setup_approval

    manager.decide(record.request_id, approver, True)

    with pytest.raises(ValueError):
        manager.decide(record.request_id, approver, False)


def test_unknown_request_id_is_rejected(setup_approval):
    manager, _, approver, _, _, _ = setup_approval

    with pytest.raises(KeyError):
        manager.decide("unknown-request-id", approver, True)


def test_pending_list_excludes_decided_requests(setup_approval):
    manager, _, approver, _, _, record = setup_approval

    assert len(manager.list_pending()) == 1

    manager.decide(record.request_id, approver, True)

    assert manager.list_pending() == []


def test_returned_record_cannot_mutate_stored_record(setup_approval):
    manager, _, _, _, _, record = setup_approval

    record.status = "APPROVED"

    stored_record = manager.get(record.request_id)
    assert stored_record.status == "PENDING"
