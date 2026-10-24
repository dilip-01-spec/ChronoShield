import logging
import uuid
from typing import Optional
from app.schemas import AuditEvent, Decision, EvaluationRequest, EvaluationResponse
from app.services.audit import AuditService
from app.services.identity import IdentityResolver, TrustedIdentity, is_well_formed_identity
from app.services.parking import MockParkingService
from app.services.policy import PolicyEngineAdapter, PolicyEvaluationResult
from app.services.policy_factory import get_policy_engine

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    """Exception carrying structured error details conforming to ApiError."""

    def __init__(self, code: str, message: str, request_id: str):
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(message)


class GatewayService:
    """Security Gateway evaluating requests, recording audit events, and routing authorized operations."""

    def __init__(
        self,
        policy_engine: Optional[PolicyEngineAdapter] = None,
        identity_resolver: Optional[IdentityResolver] = None,
        parking_service: Optional[MockParkingService] = None,
        audit_service: Optional[AuditService] = None,
    ):
        self.policy_engine = policy_engine if policy_engine is not None else get_policy_engine()
        self.identity_resolver = identity_resolver or IdentityResolver()
        self.parking_service = parking_service or MockParkingService()
        self.audit_service = audit_service or AuditService()

    @staticmethod
    def _with_audit_status(message: str, recorded: bool) -> str:
        """Make an unavailable audit record visible without exposing internals."""
        if recorded:
            return message
        return (
            f"{message} Audit recording could not be confirmed. "
            "Do not automatically retry this request."
        )

    def _record_audit_safely(self, event: AuditEvent) -> bool:
        """Attempt one write; an exception can occur before or after storage.

        The audit ID remains a correlation ID, not proof that a record exists.
        Do not retry a write or a protected action on an ambiguous failure.
        """
        try:
            self.audit_service.record(event)
            return True
        except Exception:
            # Log only a server-generated ID, never raw exception text or payloads.
            logger.error(
                "AUDIT_RECORDING_FAILED audit_id=%s",
                event.audit_id,
            )
            return False

    def _deny(
        self,
        request: EvaluationRequest,
        audit_id: str,
        reason_code: str,
        message: str,
        trusted_identity: Optional[TrustedIdentity] = None,
        audit_error: Optional[str] = None,
    ) -> EvaluationResponse:
        """Record a blocked request and return the standard denial response."""
        user_id = (
            trusted_identity.user_id
            if trusted_identity and trusted_identity.is_authenticated
            else None
        )
        audit_recorded = self._record_audit_safely(
            AuditEvent(
                audit_id=audit_id,
                request_id=request.request_id,
                domain=request.action.domain,
                decision=Decision.DENY,
                executed=False,
                reason_code=reason_code,
                user_id=user_id,
                execution_status="not_attempted",
                error=audit_error,
            )
        )
        return EvaluationResponse(
            request_id=request.request_id,
            decision=Decision.DENY,
            reason_code=reason_code,
            message=self._with_audit_status(message, audit_recorded),
            executed=False,
            audit_id=audit_id,
            result=None,
        )

    def evaluate(
        self,
        request: EvaluationRequest,
        auth_token: Optional[str] = None,
    ) -> EvaluationResponse:
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"

        # 1. Adapter validation is also a policy-engine failure boundary.
        try:
            valid_domain = self.policy_engine.is_valid_domain(request.action.domain)
            valid_operation = valid_domain and self.policy_engine.is_valid_operation(
                request.action.domain, request.action.operation
            )
        except Exception:
            return self._deny(
                request=request,
                audit_id=audit_id,
                reason_code="POLICY_ENGINE_FAILED",
                message="Policy evaluation could not be completed safely",
                audit_error="POLICY_ENGINE_FAILED",
            )

        if not valid_domain:
            raise GatewayError(
                code="UNKNOWN_DOMAIN",
                message=f"Domain '{request.action.domain}' is not recognized",
                request_id=request.request_id,
            )

        # 2. Validate operation existence for the domain
        if not valid_operation:
            raise GatewayError(
                code="UNKNOWN_OPERATION",
                message=(
                    f"Operation '{request.action.operation}' is not supported "
                    f"for domain '{request.action.domain}'"
                ),
                request_id=request.request_id,
            )

        # 3. Resolve identity (separating authenticated credentials from client-supplied actor metadata)
        actor_user_id = request.actor.user_id if request.actor else None
        try:
            trusted_identity = self.identity_resolver.resolve(
                auth_token=auth_token,
                actor_user_id=actor_user_id,
            )
            if trusted_identity is not None and not is_well_formed_identity(trusted_identity):
                raise ValueError("Invalid identity result")
        except Exception:
            return self._deny(
                request=request,
                audit_id=audit_id,
                reason_code="IDENTITY_RESOLUTION_FAILED",
                message="Identity resolution could not be completed safely",
                audit_error="IDENTITY_RESOLUTION_FAILED",
            )

        if not trusted_identity:
            return self._deny(
                request=request,
                audit_id=audit_id,
                reason_code="UNAUTHENTICATED_ACTOR",
                message="Actor identity could not be verified against trusted identity source",
            )

        # 4. Resolve authoritative resource metadata before policy evaluation.
        # The request's resource_district_id is only a client claim and is
        # never used as the authorization source for parking resources.
        authoritative_action = request.action
        if request.action.domain == "parking":
            try:
                resource = self.parking_service.get_resource(request.action.resource_id)
                if resource is not None and (
                    not isinstance(resource, dict)
                    or resource.get("resource_id") != request.action.resource_id
                ):
                    raise ValueError("Invalid resource lookup result")
                authoritative_district_id = (
                    resource.get("district_id") if resource is not None else None
                )
            except Exception:
                return self._deny(
                    request=request,
                    audit_id=audit_id,
                    reason_code="RESOURCE_LOOKUP_FAILED",
                    message="The requested parking resource could not be resolved safely",
                    trusted_identity=trusted_identity,
                    audit_error="RESOURCE_LOOKUP_FAILED",
                )

            if resource is None:
                return self._deny(
                    request=request,
                    audit_id=audit_id,
                    reason_code="RESOURCE_NOT_FOUND",
                    message=f"Parking resource '{request.action.resource_id}' was not found",
                    trusted_identity=trusted_identity,
                )

            if (
                not isinstance(authoritative_district_id, str)
                or not authoritative_district_id.strip()
            ):
                return self._deny(
                    request=request,
                    audit_id=audit_id,
                    reason_code="INVALID_RESOURCE_DISTRICT",
                    message=(
                        f"Parking resource '{request.action.resource_id}' has invalid "
                        "district metadata"
                    ),
                    trusted_identity=trusted_identity,
                )

            authoritative_action = request.action.model_copy(
                update={"resource_district_id": authoritative_district_id}
            )

        # 5. Authorize via policy engine adapter BEFORE any protected domain service can be called.
        try:
            eval_result = self.policy_engine.evaluate(
                trusted_identity, authoritative_action
            )
            # Reject malformed adapter output before a potentially mutating action.
            if (
                not isinstance(eval_result, PolicyEvaluationResult)
                or not isinstance(eval_result.decision, Decision)
                or not isinstance(eval_result.reason_code, str)
                or not eval_result.reason_code
                or not isinstance(eval_result.message, str)
            ):
                raise ValueError("Invalid policy result")
        except Exception:
            return self._deny(
                request=request,
                audit_id=audit_id,
                reason_code="POLICY_ENGINE_FAILED",
                message="Policy evaluation could not be completed safely",
                trusted_identity=trusted_identity,
                audit_error="POLICY_ENGINE_FAILED",
            )

        # 6. Dispatch to protected domain service ONLY when decision is ALLOW and identity is authenticated
        executed = False
        result_payload = None
        response_message = eval_result.message
        execution_status = "not_attempted"
        execution_error = None

        if eval_result.decision == Decision.ALLOW:
            if request.action.domain == "parking":
                # Ensure client-supplied actor metadata in unauthenticated requests cannot execute operations
                if trusted_identity.is_authenticated:
                    try:
                        result_payload = self.parking_service.execute(
                            operation=request.action.operation,
                            resource_id=request.action.resource_id,
                            authorized_identity=trusted_identity,
                        )
                        if (
                            not isinstance(result_payload, dict)
                            or not isinstance(result_payload.get("success"), bool)
                            or (
                                not result_payload["success"]
                                and not isinstance(result_payload.get("error", "Execution failed"), str)
                            )
                        ):
                            raise ValueError("Invalid service result")
                    except Exception:
                        # A service may mutate state before raising; never retry or claim rollback.
                        result_payload = {
                            "success": False,
                            "reason_code": "SERVICE_EXECUTION_FAILED",
                            "error": (
                                "Protected service execution could not be confirmed; "
                                "side effects may have occurred. Do not automatically retry this request."
                            ),
                        }
                        execution_error = "SERVICE_EXECUTION_FAILED"
                    success = result_payload["success"]
                    executed = success
                    if success:
                        execution_status = "success"
                        response_message = (
                            f"Operation '{request.action.operation}' executed on {request.action.resource_id}"
                        )
                    else:
                        execution_status = "failed"
                        failure_message = result_payload.get("error", "Execution failed")
                        execution_error = execution_error or failure_message
                        response_message = (
                            f"Operation '{request.action.operation}' failed: {failure_message}"
                        )
                else:
                    # Unauthenticated request: policy permits, but execution requires authenticated proof
                    executed = False
                    execution_status = "not_attempted"
                    execution_error = "Unauthenticated request cannot execute protected operation"
                    response_message = (
                        "Policy allows operation, but protected execution requires authenticated credentials"
                    )

        # For DENY and APPROVAL_REQUIRED, protected domain service is strictly NOT called (executed=False, execution_status="not_attempted")

        # 7. Record audit event for evaluated request
        trusted_user_id = (
            trusted_identity.user_id
            if trusted_identity.is_authenticated
            else None
        )

        audit_recorded = self._record_audit_safely(
            AuditEvent(
                audit_id=audit_id,
                request_id=request.request_id,
                domain=request.action.domain,
                decision=eval_result.decision,
                executed=executed,
                reason_code=eval_result.reason_code,
                user_id=trusted_user_id,
                execution_status=execution_status,
                error=execution_error,
            )
        )

        return EvaluationResponse(
            request_id=request.request_id,
            decision=eval_result.decision,
            reason_code=eval_result.reason_code,
            message=self._with_audit_status(response_message, audit_recorded),
            executed=executed,
            audit_id=audit_id,
            result=result_payload,
        )
