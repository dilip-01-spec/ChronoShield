
from app.security.workflow import SecurityWorkflow
from app.security.approval import ApprovalManager
from app.security.schemas import ActionRequest


def test_workflow_creates_pending_approval():
    workflow = SecurityWorkflow(ApprovalManager())

    identity = {
        "id": "water_agent_1",
        "role": "water_agent",
        "scope_id": "district_A",
    }

    request = ActionRequest(
        domain="water",
        action="update",
        resource_id="water_101",
        reason="Test water control update",
    )

    resource = {
        "id": "water_101",
        "domain": "water",
        "scope_id": "district_A",
    }

    decision, record = workflow.evaluate_and_submit(
        identity,
        request,
        resource,
    )

    assert decision.decision == "REQUIRES_APPROVAL"
    assert record is not None
    assert record.status == "PENDING"
    assert record.domain == "water"
    assert record.requested_by == "water_agent_1"

    pending = workflow.pending_approvals()
    assert len(pending) == 1
    assert pending[0].request_id == record.request_id

    events = workflow.audit_history(record.request_id)
    assert any(event.event == "SUBMITTED" for event in events)


def test_workflow_lists_pending_approvals():
    workflow = SecurityWorkflow(ApprovalManager())
    assert workflow.pending_approvals() == []


def test_workflow_exposes_audit_history():
    workflow = SecurityWorkflow(ApprovalManager())
    assert workflow.audit_history() == []
