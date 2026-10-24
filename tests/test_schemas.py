import pytest
from pydantic import ValidationError
from app.schemas import (
    ActionRequest,
    ActorContext,
    ApiError,
    AuditEvent,
    Decision,
    EvaluationRequest,
    EvaluationResponse,
)


def test_actor_context():
    actor = ActorContext(user_id="usr_01", role="operator", district_id="dist_north")
    assert actor.user_id == "usr_01"
    assert actor.role == "operator"
    assert actor.district_id == "dist_north"


def test_action_request():
    action = ActionRequest(
        request_id="req_01",
        domain="grid",
        operation="reroute_power",
        resource_id="substation_4",
        resource_district_id="dist_north",
    )
    assert action.operation == "reroute_power"


def test_evaluation_request():
    action = ActionRequest(
        request_id="req_01",
        domain="grid",
        operation="reroute_power",
        resource_id="substation_4",
        resource_district_id="dist_north",
    )
    actor = ActorContext(user_id="usr_01", role="operator", district_id="dist_north")
    req = EvaluationRequest(request_id="req_01", action=action, actor=actor)
    assert req.action.resource_id == "substation_4"
    assert req.actor.user_id == "usr_01"


def test_evaluation_response_valid_decisions():
    for dec in (Decision.ALLOW, Decision.DENY, Decision.APPROVAL_REQUIRED):
        resp = EvaluationResponse(
            request_id="req_01",
            decision=dec,
            reason_code="POLICY_OK",
            message="Evaluation successful",
            executed=True,
            audit_id="aud_01",
        )
        assert resp.decision == dec


def test_evaluation_response_invalid_decision_rejected():
    with pytest.raises(ValidationError):
        EvaluationResponse(
            request_id="req_01",
            decision="unauthorized_decision",  # invalid enum value
            reason_code="ERR",
            message="Error",
            executed=False,
            audit_id="aud_01",
        )


def test_api_error():
    err = ApiError(code="INVALID_PAYLOAD", message="Field missing", request_id="req_01")
    assert err.code == "INVALID_PAYLOAD"
    assert err.model_dump() == {
        "code": "INVALID_PAYLOAD",
        "message": "Field missing",
        "request_id": "req_01",
    }


def test_audit_event_valid_and_invalid_decision():
    event = AuditEvent(
        audit_id="aud_01",
        request_id="req_01",
        domain="grid",
        decision=Decision.ALLOW,
        executed=True,
        reason_code="ALLOWED_BY_RULE",
    )
    assert event.decision == "allow"

    with pytest.raises(ValidationError):
        AuditEvent(
            audit_id="aud_01",
            request_id="req_01",
            domain="grid",
            decision="unknown_state",
            executed=False,
            reason_code="INVALID",
        )
