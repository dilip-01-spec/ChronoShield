
"""Person 2's canonical ChronoShield policy engine.

This module evaluates security policies only. It does not execute operations
or modify Person 1's backend.

The legacy evaluate_request function remains for backward compatibility
with Person 2's existing tests. FormalPolicyEngine is the canonical
eight-domain policy engine.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.security.policies import (
    ROLE_PERMISSIONS,
    SENSITIVE_ACTIONS,
    VALID_DOMAINS,
    VALID_ACTIONS,
)
from app.security.schemas import ActionRequest, SecurityDecision


# ---------------------------------------------------------------------
# Legacy evaluator: retained to keep existing tests and workflow working
# ---------------------------------------------------------------------

def evaluate_request(identity, request, resource):
    """Evaluate a legacy ActionRequest against the original policy rules.

    Identity and resource data must come from trusted backend code.
    This function evaluates policy only; it does not execute operations.
    """

    if not isinstance(identity, dict):
        return SecurityDecision(
            decision="DENY",
            reason_code="INVALID_IDENTITY",
            message="Caller identity must be a valid dictionary",
        )

    if not identity.get("id"):
        return SecurityDecision(
            decision="DENY",
            reason_code="INVALID_IDENTITY",
            message="Caller identity could not be verified",
        )

    role = identity.get("role")
    if role not in ROLE_PERMISSIONS:
        return SecurityDecision(
            decision="DENY",
            reason_code="UNKNOWN_ROLE",
            message="Caller role is not recognized",
        )

    if not isinstance(request, ActionRequest):
        return SecurityDecision(
            decision="DENY",
            reason_code="INVALID_REQUEST",
            message="Request must be a valid ActionRequest",
        )

    if request.domain not in VALID_DOMAINS:
        return SecurityDecision(
            decision="DENY",
            reason_code="UNKNOWN_DOMAIN",
            message="Domain is not supported",
        )

    if request.action not in VALID_ACTIONS:
        return SecurityDecision(
            decision="DENY",
            reason_code="UNKNOWN_ACTION",
            message="Action is not recognized",
        )

    if resource is None:
        return SecurityDecision(
            decision="DENY",
            reason_code="RESOURCE_NOT_FOUND",
            message="Requested resource was not found",
        )

    if not isinstance(resource, dict):
        return SecurityDecision(
            decision="DENY",
            reason_code="INVALID_RESOURCE",
            message="Resource must be a valid dictionary",
        )

    if resource.get("domain") != request.domain:
        return SecurityDecision(
            decision="DENY",
            reason_code="RESOURCE_DOMAIN_MISMATCH",
            message="Resource does not belong to the requested domain",
        )

    permissions = ROLE_PERMISSIONS.get(role, {})
    allowed_actions = permissions.get(request.domain, set())

    if request.action not in allowed_actions:
        return SecurityDecision(
            decision="DENY",
            reason_code="INSUFFICIENT_PERMISSION",
            message="Role cannot perform this action in this domain",
        )

    identity_scope = identity.get("scope_id")
    resource_scope = resource.get("scope_id")

    if not identity_scope or not resource_scope:
        return SecurityDecision(
            decision="DENY",
            reason_code="MISSING_RESOURCE_SCOPE",
            message="Resource access scope could not be verified",
        )

    if identity_scope != resource_scope:
        return SecurityDecision(
            decision="DENY",
            reason_code="RESOURCE_SCOPE_VIOLATION",
            message="Resource is outside the caller's permitted scope",
        )

    if (request.domain, request.action) in SENSITIVE_ACTIONS:
        return SecurityDecision(
            decision="REQUIRES_APPROVAL",
            reason_code="SENSITIVE_ACTION",
            message="Verified human approval is required",
        )

    return SecurityDecision(
        decision="ALLOW",
        reason_code="POLICY_MATCH",
        message="Request is authorized",
    )


# ---------------------------------------------------------------------
# Canonical policy engine: eight ChronoShield domains
# ---------------------------------------------------------------------

# Prefer Person 1's types when they are available in the integrated project.
# In Person 2's standalone project, use these local fallback types.
try:
    from app.schemas import Decision
    from app.services.policy import PolicyEvaluationResult
except ImportError:
    class Decision(str, Enum):
        ALLOW = "allow"
        DENY = "deny"
        APPROVAL_REQUIRED = "approval_required"

    @dataclass(frozen=True)
    class PolicyEvaluationResult:
        decision: Decision
        reason_code: str
        message: str


class FormalPolicyEngine:
    """Check roles, domains, operations, districts, and approval requirements."""


    VALID_DOMAINS = {
        "parking": {
            "read", "status", "reserve_spot",



            "release_spot", "close_zone",
        },
        "grid": {
            "status", "reroute_power", "isolate_substation",
        },
        "transit": {



            "status", "adjust_signals", "emergency_stop",
        },
        "water": {
            "status", "adjust_flow", "open_valve",
        },
        "waste": {



            "status", "schedule_pickup", "dispatch_truck",
        },
        "emergency": {
            "status", "dispatch_unit", "broadcast_alert",
        },
        "telecom": {



            "status", "boost_cell", "reboot_node",
        },
        "healthcare": {
            "status", "triage_alert", "allocate_beds",
        },
    }

    APPROVAL_REQUIRED_OPERATIONS = {
        "reroute_power",
        "isolate_substation",
        "emergency_stop",
        "open_valve",
        "broadcast_alert",
        "close_zone",
    }

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

    READ_OPERATIONS = {"read", "status"}
    VALID_ROLES = {"admin", "operator", "viewer"}

    def role_allows_action(self, role: object, domain: str, operation: str) -> bool:
        """Only explicitly listed role/domain/operation combinations grant access."""
        return (
            isinstance(role, str)
            and (domain, operation) in self.ROLE_PERMISSIONS.get(role, frozenset())
        )

    def is_valid_domain(self, domain: str) -> bool:
        """Return whether a domain is registered."""
        return isinstance(domain, str) and domain in self.VALID_DOMAINS

    def is_valid_operation(self, domain: str, operation: str) -> bool:
        """Return whether an operation belongs to its domain."""
        return (
            self.is_valid_domain(domain)
            and isinstance(operation, str)
            and operation in self.VALID_DOMAINS[domain]
        )

    def evaluate(
        self,
        identity: Any,
        action: Any,
    ) -> PolicyEvaluationResult:
        """Evaluate an identity and an ActionRequest-like object.

        Identity must come from trusted backend code. This method makes
        policy decisions only; it never executes requested operations.
        """

        domain = getattr(action, "domain", None)
        if not self.is_valid_domain(domain):
            return self._result(
                Decision.DENY,
                "UNKNOWN_DOMAIN",
                f"Domain '{domain}' is not recognized",
            )

        operation = getattr(action, "operation", None)
        if not self.is_valid_operation(domain, operation):
            return self._result(
                Decision.DENY,
                "UNKNOWN_OPERATION",
                f"Operation '{operation}' is not supported for domain '{domain}'",
            )

        if identity is None:
            return self._result(
                Decision.DENY,
                "INVALID_IDENTITY",
                "Trusted identity is required",
            )

        user_id = getattr(identity, "user_id", None)
        role = getattr(identity, "role", None)
        district_id = getattr(identity, "district_id", None)

        if (
            not isinstance(user_id, str) or not user_id.strip()
            or not isinstance(district_id, str) or not district_id.strip()
            or not isinstance(role, str)
        ):
            return self._result(
                Decision.DENY,
                "INVALID_IDENTITY",
                "Trusted identity is incomplete",
            )

        if role not in self.VALID_ROLES:
            return self._result(
                Decision.DENY,
                "UNKNOWN_ROLE",
                "Caller role is not recognized",
            )

        if not self.role_allows_action(role, domain, operation):
            return self._result(
                Decision.DENY,
                "ROLE_NOT_AUTHORIZED",
                f"Role '{role}' is not authorized for '{operation}'",
            )

        # Operators may only access resources in their own district.
        # Admins are not restricted by this district check.
        if role == "operator":
            resource_district_id = getattr(
                action,
                "resource_district_id",
                None,
            )

            if (
                not resource_district_id
                or resource_district_id != district_id
            ):
                return self._result(
                    Decision.DENY,
                    "DISTRICT_MISMATCH",
                    f"Operator district '{district_id}' does not "
                    f"match resource district '{resource_district_id}'",
                )

        if operation in self.APPROVAL_REQUIRED_OPERATIONS:
            return self._result(
                Decision.APPROVAL_REQUIRED,
                "HIGH_IMPACT_APPROVAL_REQUIRED",
                f"Operation '{operation}' requires human approval (pending)",
            )

        return self._result(
            Decision.ALLOW,
            "POLICY_ALLOW",
            f"Operation '{operation}' permitted for {user_id}",
        )

    @staticmethod
    def _result(
        decision: Decision,
        reason_code: str,
        message: str,
    ) -> PolicyEvaluationResult:
        """Build a consistent policy result."""
        return PolicyEvaluationResult(
            decision=decision,
            reason_code=reason_code,
            message=message,
        )
