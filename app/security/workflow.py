
from app.security.approval import ApprovalManager
from app.security.engine import evaluate_request


class SecurityWorkflow:
    """Connect policy evaluation with the human-approval manager."""

    def __init__(self, approval_manager=None):
        self.approvals = (
            approval_manager
            if approval_manager is not None
            else ApprovalManager()
        )

    def evaluate_and_submit(self, identity, request, resource):
        """Evaluate a request and store it if approval is required."""

        decision = evaluate_request(identity, request, resource)

        if decision.decision == "REQUIRES_APPROVAL":
            record = self.approvals.submit(
                identity=identity,
                request=request,
                security_decision=decision,
            )
            return decision, record

        return decision, None

    def pending_approvals(self):
        return self.approvals.list_pending()

    def get_approval(self, request_id):
        return self.approvals.get(request_id)

    def decide_approval(
        self,
        request_id,
        approver,
        approve,
        reason="",
    ):
        return self.approvals.decide(
            request_id=request_id,
            approver=approver,
            approve=approve,
            reason=reason,
        )

    def audit_history(self, request_id=None):
        return self.approvals.audit_history(request_id)
