from dataclasses import dataclass
from typing import Optional, Protocol, Set
from app.schemas import ActionRequest, Decision
from app.services.identity import TrustedIdentity, is_well_formed_identity


# Registration alone must not grant permission to a new domain or operation.
_OPERATOR_ADMIN_PERMISSIONS = frozenset({
    ("grid", "status"), ("grid", "reroute_power"), ("grid", "isolate_substation"),
    ("transit", "status"), ("transit", "adjust_signals"), ("transit", "emergency_stop"),
    ("water", "status"), ("water", "adjust_flow"), ("water", "open_valve"),
    ("waste", "status"), ("waste", "schedule_pickup"), ("waste", "dispatch_truck"),
    ("emergency", "status"), ("emergency", "dispatch_unit"), ("emergency", "broadcast_alert"),
    ("telecom", "status"), ("telecom", "boost_cell"), ("telecom", "reboot_node"),
    ("healthcare", "status"), ("healthcare", "triage_alert"), ("healthcare", "allocate_beds"),
    ("parking", "read"), ("parking", "status"), ("parking", "reserve_spot"),
    ("parking", "release_spot"), ("parking", "close_zone"),
})
ROLE_PERMISSIONS = {
    "admin": _OPERATOR_ADMIN_PERMISSIONS,
    "operator": _OPERATOR_ADMIN_PERMISSIONS,
    "viewer": frozenset({
        ("grid", "status"), ("transit", "status"), ("water", "status"),
        ("waste", "status"), ("emergency", "status"), ("telecom", "status"),
        ("healthcare", "status"), ("parking", "status"), ("parking", "read"),
    }),
}


def role_allows_action(role: object, domain: str, operation: str) -> bool:
    """Only explicitly listed role/domain/operation combinations grant access."""
    return (
        isinstance(role, str)
        and (domain, operation) in ROLE_PERMISSIONS.get(role, frozenset())
    )


@dataclass(frozen=True)
class PolicyEvaluationResult:
    decision: Decision
    reason_code: str
    message: str


class PolicyEngineAdapter(Protocol):
    """Interface to be implemented by Person 2's formal policy engine."""

    def is_valid_domain(self, domain: str) -> bool:
        ...

    def is_valid_operation(self, domain: str, operation: str) -> bool:
        ...

    def evaluate(
        self, identity: TrustedIdentity, action: ActionRequest
    ) -> PolicyEvaluationResult:
        ...


def district_scope_for_identity(identity: TrustedIdentity) -> Optional[str]:
    """Return the district scope enforced by the current policy model.

    Called after identity and role checks. Operators are district-scoped;
    administrators and viewers retain their existing global district scope.
    """
    if identity.role == "operator":
        return identity.district_id
    return None


class DevMockPolicyEngine:
    """DEVELOPMENT ONLY: Temporary policy adapter until Person 2 integrates the formal engine."""

    # 8 domains: 7 future smart-city domains + synthetic parking domain
    VALID_DOMAINS = {
        "grid": {"status", "reroute_power", "isolate_substation"},
        "transit": {"status", "adjust_signals", "emergency_stop"},
        "water": {"status", "adjust_flow", "open_valve"},
        "waste": {"status", "schedule_pickup", "dispatch_truck"},
        "emergency": {"status", "dispatch_unit", "broadcast_alert"},
        "telecom": {"status", "boost_cell", "reboot_node"},
        "healthcare": {"status", "triage_alert", "allocate_beds"},
        "parking": {"read", "status", "reserve_spot", "release_spot", "close_zone"},
    }

    # High-impact operations requiring temporal/supervisor approval
    APPROVAL_REQUIRED_OPERATIONS: Set[str] = {
        "reroute_power",
        "isolate_substation",
        "emergency_stop",
        "open_valve",
        "broadcast_alert",
        "close_zone",
    }

    def is_valid_domain(self, domain: str) -> bool:
        return domain in self.VALID_DOMAINS

    def is_valid_operation(self, domain: str, operation: str) -> bool:
        return (
            self.is_valid_domain(domain)
            and operation in self.VALID_DOMAINS[domain]
        )

    def evaluate(
        self, identity: TrustedIdentity, action: ActionRequest
    ) -> PolicyEvaluationResult:
        # 1. Unknown domain or operation
        if not self.is_valid_domain(action.domain):
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="UNKNOWN_DOMAIN",
                message=f"Domain '{action.domain}' is not recognized",
            )

        if not self.is_valid_operation(action.domain, action.operation):
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="UNKNOWN_OPERATION",
                message=f"Operation '{action.operation}' is not supported for domain '{action.domain}'",
            )

        # 2. Dataclass annotations do not validate incoming resolver results.
        if not is_well_formed_identity(identity):
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="UNAUTHENTICATED_ACTOR",
                message="Actor identity is malformed",
            )

        if not role_allows_action(identity.role, action.domain, action.operation):
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="ROLE_NOT_AUTHORIZED",
                message="Role is not authorized for the requested operation",
            )

        # 3. District boundaries: district-scoped identities cannot access
        # resources outside their authoritative district.
        district_scope = district_scope_for_identity(identity)
        if district_scope is not None and action.resource_district_id != district_scope:
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="DISTRICT_MISMATCH",
                message=(
                    f"Identity district '{district_scope}' does not match "
                    f"resource district '{action.resource_district_id}'"
                ),
            )

        # 4. Critical/high-impact operations require supervisor approval
        if action.operation in self.APPROVAL_REQUIRED_OPERATIONS:
            return PolicyEvaluationResult(
                decision=Decision.APPROVAL_REQUIRED,
                reason_code="HIGH_IMPACT_APPROVAL_REQUIRED",
                message=f"Operation '{action.operation}' requires temporal approval (pending)",
            )

        # 5. Explicit role permission, district, and approval checks all passed.
        return PolicyEvaluationResult(
            decision=Decision.ALLOW,
            reason_code="POLICY_ALLOW",
            message=f"Operation '{action.operation}' permitted for {identity.user_id}",
        )


class FormalPolicyEngineAdapter:
    """Production PolicyEngineAdapter wrapping Person 2's FormalPolicyEngine.

    Conforms to the PolicyEngineAdapter protocol and bridges ChronoShield's
    trusted identity and action models with FormalPolicyEngine.
    """

    def __init__(self, engine: Optional[object] = None):
        if engine is not None:
            self.engine = engine
        else:
            from app.security.engine import FormalPolicyEngine
            self.engine = FormalPolicyEngine()

    def is_valid_domain(self, domain: str) -> bool:
        """Return whether a domain is recognized by the formal engine."""
        try:
            checker = getattr(self.engine, "is_valid_domain", None)
            if callable(checker):
                return bool(checker(domain))
            domains = getattr(self.engine, "VALID_DOMAINS", {})
            return isinstance(domain, str) and domain in domains
        except Exception:
            return False

    def is_valid_operation(self, domain: str, operation: str) -> bool:
        """Return whether an operation belongs to a recognized domain."""
        try:
            checker = getattr(self.engine, "is_valid_operation", None)
            if callable(checker):
                return bool(checker(domain, operation))
            domains = getattr(self.engine, "VALID_DOMAINS", {})
            return (
                isinstance(domain, str)
                and domain in domains
                and isinstance(operation, str)
                and operation in domains[domain]
            )
        except Exception:
            return False

    def evaluate(
        self, identity: TrustedIdentity, action: ActionRequest
    ) -> PolicyEvaluationResult:
        """Evaluate an identity and action using the canonical FormalPolicyEngine.

        Maps decisions and reason codes into ChronoShield's authoritative contract.
        Fails safely on any engine error or malformed input.
        """
        # 1. Reject unregistered domain or operation before deeper evaluation.
        try:
            domain = getattr(action, "domain", None)
            operation = getattr(action, "operation", None)
            if not self.is_valid_domain(domain):
                return PolicyEvaluationResult(
                    decision=Decision.DENY,
                    reason_code="UNKNOWN_DOMAIN",
                    message=f"Domain '{domain}' is not recognized",
                )
            if not self.is_valid_operation(domain, operation):
                return PolicyEvaluationResult(
                    decision=Decision.DENY,
                    reason_code="UNKNOWN_OPERATION",
                    message=f"Operation '{operation}' is not supported for domain '{domain}'",
                )
        except Exception:
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="POLICY_ENGINE_FAILED",
                message="Policy evaluation could not be completed safely",
            )

        # 2. Trusted identity must be well-formed; unauthenticated/malformed fail closed.
        if not is_well_formed_identity(identity):
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="UNAUTHENTICATED_ACTOR",
                message="Actor identity is malformed",
            )

        # 3. Delegate evaluation to FormalPolicyEngine.
        try:
            raw_result = self.engine.evaluate(identity, action)
        except Exception:
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="POLICY_ENGINE_FAILED",
                message="Policy evaluation could not be completed safely",
            )

        # 4. Handle malformed engine result.
        if raw_result is None:
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="POLICY_ENGINE_FAILED",
                message="Policy evaluation could not be completed safely",
            )

        raw_decision = getattr(raw_result, "decision", None)
        raw_reason_code = getattr(raw_result, "reason_code", None)
        raw_message = getattr(raw_result, "message", None)

        if (
            not isinstance(raw_reason_code, str)
            or not raw_reason_code.strip()
            or not isinstance(raw_message, str)
            or not raw_message.strip()
        ):
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="POLICY_ENGINE_FAILED",
                message="Policy evaluation could not be completed safely",
            )

        # 5. Translate decision explicitly into Decision enum.
        if isinstance(raw_decision, Decision):
            decision = raw_decision
        elif isinstance(raw_decision, str):
            normalized = raw_decision.lower()
            if normalized == "allow":
                decision = Decision.ALLOW
            elif normalized == "deny":
                decision = Decision.DENY
            elif normalized in ("approval_required", "requires_approval"):
                decision = Decision.APPROVAL_REQUIRED
            else:
                return PolicyEvaluationResult(
                    decision=Decision.DENY,
                    reason_code="POLICY_ENGINE_FAILED",
                    message="Policy evaluation could not be completed safely",
                )
        else:
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="POLICY_ENGINE_FAILED",
                message="Policy evaluation could not be completed safely",
            )

        # 6. Normalize reason codes to preserve ChronoShield's authoritative contract.
        reason_code = raw_reason_code
        if reason_code == "UNKNOWN_ROLE":
            reason_code = "ROLE_NOT_AUTHORIZED"
        elif reason_code == "INVALID_IDENTITY":
            reason_code = "UNAUTHENTICATED_ACTOR"

        return PolicyEvaluationResult(
            decision=decision,
            reason_code=reason_code,
            message=raw_message,
        )
