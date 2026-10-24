from typing import List, Optional
from app.schemas import AuditEvent


class AuditService:
    """In-memory audit logging service recording policy evaluations and execution outcomes.

    SECURITY RULE: Never store authentication tokens, secrets, or raw bearer credentials.
    Actor identity is logged only when authenticated via trusted server resolution.
    """

    def __init__(self):
        self._events: List[AuditEvent] = []

    def record(self, event: AuditEvent) -> AuditEvent:
        """Record an audit event to the in-memory log."""
        self._events.append(event)
        return event

    def get_events(self) -> List[AuditEvent]:
        """Return a copy of all recorded audit events."""
        return list(self._events)

    def get_by_audit_id(self, audit_id: str) -> Optional[AuditEvent]:
        """Lookup an audit event by its unique audit_id."""
        for event in self._events:
            if event.audit_id == audit_id:
                return event
        return None

    def get_by_request_id(self, request_id: str) -> List[AuditEvent]:
        """Lookup all audit events associated with a request_id."""
        return [e for e in self._events if e.request_id == request_id]

    def clear(self) -> None:
        """Clear all in-memory audit events (useful for test resets)."""
        self._events.clear()
