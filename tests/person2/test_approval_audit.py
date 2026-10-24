
from datetime import datetime, timedelta, timezone

import pytest

from app.security.approval import ApprovalManager
from app.security.schemas import ActionRequest, SecurityDecision


class FakeClock:
    def __init__(self):
        self.current = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def approval_setup():
    clock = FakeClock()
    manager = ApprovalManager(ttl_seconds=60, clock=clock)

    requester = {"id": "agent_101", "role": "water_agent"}
    approver = {"id": "admin_001", "role": "admin"}

    request = ActionRequest(
        domain="water",
        action="update",
        resource_id="water_101",
        parameters={},
        reason="Water system update",
    )

    decision = SecurityDecision(
        decision="REQUIRES_APPROVAL",
        reason_code="SENSITIVE_ACTION",
        message="Human approval is required",
    )

    record = manager.submit(requester, request, decision)

    return clock, manager, requester, approver, record


def test_submission_records_expiry_time(approval_setup):
    _, _, _, _, record = approval_setup

    created = datetime.fromisoformat(record.created_at)
    expires = datetime.fromisoformat(record.expires_at)

    assert expires - created == timedelta(seconds=60)


def test_pending_request_expires_after_deadline(approval_setup):
    clock, manager, _, _, record = approval_setup

    clock.advance(61)

    result = manager.get(record.request_id)

    assert result.status == "EXPIRED"
    assert manager.list_pending() == []


def test_request_cannot_be_approved_after_expiry(approval_setup):
    clock, manager, _, approver, record = approval_setup

    clock.advance(61)

    with pytest.raises(ValueError, match="expired"):
        manager.decide(record.request_id, approver, True)

    assert manager.get(record.request_id).status == "EXPIRED"


def test_request_can_be_approved_before_expiry(approval_setup):
    clock, manager, _, approver, record = approval_setup

    clock.advance(30)

    result = manager.decide(record.request_id, approver, True)

    assert result.status == "APPROVED"


def test_submission_creates_audit_event(approval_setup):
    _, manager, _, _, record = approval_setup

    events = manager.audit_history(record.request_id)

    assert len(events) == 1
    assert events[0].event == "SUBMITTED"
    assert events[0].actor_id == "agent_101"


def test_approval_is_recorded_in_audit_history(approval_setup):
    _, manager, _, approver, record = approval_setup

    manager.decide(record.request_id, approver, True, "Reviewed")

    events = manager.audit_history(record.request_id)

    assert [event.event for event in events] == [
        "SUBMITTED",
        "APPROVED",
    ]
    assert events[-1].actor_id == "admin_001"
    assert events[-1].details == "Reviewed"


def test_rejection_is_recorded_in_audit_history(approval_setup):
    _, manager, _, approver, record = approval_setup

    manager.decide(record.request_id, approver, False, "Unsafe")

    events = manager.audit_history(record.request_id)

    assert events[-1].event == "REJECTED"
    assert events[-1].details == "Unsafe"


def test_expiry_is_recorded_in_audit_history(approval_setup):
    clock, manager, _, _, record = approval_setup

    clock.advance(61)
    manager.get(record.request_id)

    events = manager.audit_history(record.request_id)

    assert [event.event for event in events] == [
        "SUBMITTED",
        "EXPIRED",
    ]
    assert events[-1].actor_id == "system"


def test_audit_history_can_be_filtered_by_request(approval_setup):
    _, manager, requester, _, record = approval_setup

    second_request = ActionRequest(
        domain="water",
        action="update",
        resource_id="water_202",
        parameters={},
        reason="Second request",
    )

    decision = SecurityDecision(
        decision="REQUIRES_APPROVAL",
        reason_code="SENSITIVE_ACTION",
        message="Approval required",
    )

    second_record = manager.submit(requester, second_request, decision)

    assert len(manager.audit_history()) == 2
    assert len(manager.audit_history(record.request_id)) == 1
    assert len(manager.audit_history(second_record.request_id)) == 1


def test_expiry_time_is_recorded_in_utc(approval_setup):
    _, _, _, _, record = approval_setup

    expires = datetime.fromisoformat(record.expires_at)

    assert expires.tzinfo is not None
    assert expires.utcoffset() == timedelta(0)


def test_invalid_expiry_duration_is_rejected():
    with pytest.raises(ValueError):
        ApprovalManager(ttl_seconds=0)

    with pytest.raises(ValueError):
        ApprovalManager(ttl_seconds=-10)
