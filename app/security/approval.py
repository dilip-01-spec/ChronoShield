from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

from app.security.schemas import ActionRequest, SecurityDecision


def utc_now():
    return datetime.now(timezone.utc)


@dataclass
class ApprovalRecord:
    request_id: str
    domain: str
    action: str
    resource_id: str
    requested_by: str
    reason: str
    status: str = "PENDING"
    created_at: str = field(
        default_factory=lambda: utc_now().isoformat()
    )
    expires_at: str = ""
    decided_by: str | None = None
    decision_reason: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    event: str
    actor_id: str
    timestamp: str
    details: str = ""


class ApprovalManager:
    """
    Standalone in-memory approval manager.

    This module records decisions; it never executes actions.
    Identity dictionaries must come from trusted backend code.
    """

    def __init__(self, ttl_seconds=1800, clock=None):
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or ttl_seconds <= 0
        ):
            raise ValueError("ttl_seconds must be a positive number")

        self._ttl = ttl_seconds
        self._clock = clock or utc_now
        self._records = {}
        self._expiry_times = {}
        self._audit_events = []
        self._lock = RLock()

    def _now(self):
        now = self._clock()

        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Clock must return a timezone-aware datetime")

        return now.astimezone(timezone.utc)

    def _audit(self, request_id, event, actor_id, details=""):
        self._audit_events.append(
            AuditEvent(
                request_id=request_id,
                event=event,
                actor_id=str(actor_id),
                timestamp=self._now().isoformat(),
                details=details,
            )
        )

    def _expire_if_needed(self, record):
        if record.status != "PENDING":
            return

        if self._now() >= self._expiry_times[record.request_id]:
            record.status = "EXPIRED"
            record.decision_reason = "Approval request expired"

            self._audit(
                record.request_id,
                "EXPIRED",
                "system",
                "Approval deadline passed",
            )

    def submit(self, identity, request, security_decision):
        """Create an approval request only when approval is required."""

        if not isinstance(identity, dict) or not identity.get("id"):
            raise ValueError("A valid requester identity is required")

        if not isinstance(request, ActionRequest):
            raise ValueError("A valid ActionRequest is required")

        if not isinstance(security_decision, SecurityDecision):
            raise ValueError("A valid security decision is required")

        if security_decision.decision != "REQUIRES_APPROVAL":
            raise ValueError(
                "Only requests requiring approval can be submitted"
            )

        with self._lock:
            now = self._now()
            expires = now + timedelta(seconds=self._ttl)

            record = ApprovalRecord(
                request_id=str(uuid4()),
                domain=request.domain,
                action=request.action,
                resource_id=request.resource_id,
                requested_by=str(identity["id"]),
                reason=request.reason,
                created_at=now.isoformat(),
                expires_at=expires.isoformat(),
            )

            self._records[record.request_id] = record
            self._expiry_times[record.request_id] = expires

            self._audit(
                record.request_id,
                "SUBMITTED",
                record.requested_by,
                "Approval request created",
            )

            return deepcopy(record)

    def decide(self, request_id, approver, approve, reason=""):
        """Approve or reject a pending request."""

        if not isinstance(approver, dict) or not approver.get("id"):
            raise ValueError("A valid approver identity is required")

        if approver.get("role") != "admin":
            raise PermissionError("Only an admin can decide requests")

        if not isinstance(approve, bool):
            raise ValueError("approve must be True or False")

        with self._lock:
            record = self._records.get(request_id)

            if record is None:
                raise KeyError("Approval request was not found")

            self._expire_if_needed(record)

            if record.status == "EXPIRED":
                raise ValueError("This approval request has expired")

            if record.status != "PENDING":
                raise ValueError("This request has already been decided")

            approver_id = str(approver["id"])

            if approver_id == record.requested_by:
                raise PermissionError(
                    "The requester cannot approve their own request"
                )

            record.status = "APPROVED" if approve else "REJECTED"
            record.decided_by = approver_id
            record.decision_reason = reason.strip() or (
                "Approved" if approve else "Rejected"
            )

            self._audit(
                record.request_id,
                record.status,
                approver_id,
                record.decision_reason,
            )

            return deepcopy(record)

    def get(self, request_id):
        """Return a copy of a request, or None if not found."""

        with self._lock:
            record = self._records.get(request_id)

            if record is None:
                return None

            self._expire_if_needed(record)
            return deepcopy(record)

    def list_pending(self):
        """Return copies of requests still awaiting a decision."""

        with self._lock:
            pending = []

            for record in self._records.values():
                self._expire_if_needed(record)

                if record.status == "PENDING":
                    pending.append(deepcopy(record))

            return pending

    def audit_history(self, request_id=None):
        """
        Return audit events in chronological order.
        Optionally filter to one approval request.
        """

        with self._lock:
            if request_id is None:
                return deepcopy(self._audit_events)

            return deepcopy([
                event
                for event in self._audit_events
                if event.request_id == request_id
            ])
