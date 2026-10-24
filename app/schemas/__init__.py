from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class ActorContext(BaseModel):
    """Client-supplied actor context for prototype request routing only (not trusted identity proof)."""
    user_id: str
    role: str
    district_id: str


class ActionRequest(BaseModel):
    """Details of the requested operation to evaluate.

    ``resource_district_id`` is a client-supplied claim only. Runtime
    authorization must resolve the authoritative district from the resource ID.
    """
    request_id: str
    domain: str
    operation: str
    resource_id: str
    resource_district_id: str


class EvaluationRequest(BaseModel):
    """Payload to evaluate an action against policy."""
    request_id: str
    action: ActionRequest
    actor: Optional[ActorContext] = None


class EvaluationResponse(BaseModel):
    """Authorization and execution are separate outcomes.

    ``executed=False`` means successful execution was not confirmed, not that
    partial side effects were rolled back. Audit-write failures are disclosed
    in ``message``; ``audit_id`` then remains a correlation ID, not a receipt.
    """
    request_id: str
    decision: Decision
    reason_code: str
    message: str
    executed: bool
    audit_id: str
    result: Optional[dict] = None


class ApiError(BaseModel):
    """Standardized API error contract."""
    code: str
    message: str
    request_id: str


class AuditEvent(BaseModel):
    """Audit log entry capturing authorization and execution separately.

    Pre-execution failures use ``not_attempted``. Execution exceptions retain
    the allow decision with ``failed`` and a safe error code, not exception text.
    """
    audit_id: str
    request_id: str
    domain: str
    decision: Decision
    executed: bool
    reason_code: str
    user_id: Optional[str] = None  # Populated only when resolved by trusted identity
    execution_status: Optional[str] = None  # "success", "failed", or "not_attempted"
    error: Optional[str] = None


__all__ = [
    "Decision",
    "ActorContext",
    "ActionRequest",
    "EvaluationRequest",
    "EvaluationResponse",
    "ApiError",
    "AuditEvent",
]
