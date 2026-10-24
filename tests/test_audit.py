from app.schemas import AuditEvent, ActionRequest, ActorContext, Decision, EvaluationRequest
from app.services.audit import AuditService
from app.services.gateway import GatewayService
from app.services.parking import MockParkingService


def test_audit_event_recorded_on_allow_success():
    audit_service = AuditService()
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking, audit_service=audit_service)

    req = EvaluationRequest(
        request_id="req-audit-allow-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-audit-allow-01",
            domain="parking",
            operation="read",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    resp = gateway.evaluate(req, auth_token="token_operator_north")

    events = audit_service.get_by_request_id("req-audit-allow-01")
    assert len(events) == 1
    event = events[0]

    assert event.audit_id == resp.audit_id
    assert event.request_id == "req-audit-allow-01"
    assert event.domain == "parking"
    assert event.decision == Decision.ALLOW
    assert event.executed is True
    assert event.reason_code == "POLICY_ALLOW"
    assert event.user_id == "user_operator_north"  # Resolved by trusted identity
    assert event.execution_status == "success"
    assert event.error is None


def test_audit_event_recorded_on_deny():
    audit_service = AuditService()
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking, audit_service=audit_service)

    req = EvaluationRequest(
        request_id="req-audit-deny-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-audit-deny-01",
            domain="parking",
            operation="read",
            resource_id="park_south_1",
            resource_district_id="district_south",  # Cross-district
        ),
    )
    resp = gateway.evaluate(req, auth_token="token_operator_north")

    events = audit_service.get_by_request_id("req-audit-deny-01")
    assert len(events) == 1
    event = events[0]

    assert event.audit_id == resp.audit_id
    assert event.decision == Decision.DENY
    assert event.executed is False
    assert event.reason_code == "DISTRICT_MISMATCH"
    assert event.user_id == "user_operator_north"
    assert event.execution_status == "not_attempted"


def test_audit_event_recorded_on_approval_required():
    audit_service = AuditService()
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking, audit_service=audit_service)

    req = EvaluationRequest(
        request_id="req-audit-appr-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-audit-appr-01",
            domain="parking",
            operation="close_zone",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    resp = gateway.evaluate(req, auth_token="token_operator_north")

    events = audit_service.get_by_request_id("req-audit-appr-01")
    assert len(events) == 1
    event = events[0]

    assert event.audit_id == resp.audit_id
    assert event.decision == Decision.APPROVAL_REQUIRED
    assert event.executed is False
    assert event.reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"
    assert event.user_id == "user_operator_north"
    assert event.execution_status == "not_attempted"


def test_audit_event_recorded_on_execution_failure():
    audit_service = AuditService()
    mock_parking = MockParkingService()
    # Fill lot to trigger domain execution failure
    mock_parking.records["park_north_1"]["available_spots"] = 0
    gateway = GatewayService(parking_service=mock_parking, audit_service=audit_service)

    req = EvaluationRequest(
        request_id="req-audit-fail-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-audit-fail-01",
            domain="parking",
            operation="reserve_spot",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    resp = gateway.evaluate(req, auth_token="token_operator_north")

    events = audit_service.get_by_request_id("req-audit-fail-01")
    assert len(events) == 1
    event = events[0]

    # Clearly distinguishes execution failure from authorization denial:
    # Decision is ALLOW, but executed is False and execution_status is 'failed'
    assert event.audit_id == resp.audit_id
    assert event.decision == Decision.ALLOW
    assert event.executed is False
    assert event.execution_status == "failed"
    assert event.error == "No spots available"
    assert event.user_id == "user_operator_north"


def test_audit_event_on_unauthenticated_request_excludes_actor_identity():
    audit_service = AuditService()
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking, audit_service=audit_service)

    # Client passes unverified actor metadata with an invalid auth token
    req = EvaluationRequest(
        request_id="req-audit-unauth-01",
        actor=ActorContext(user_id="unverified_impersonator", role="admin", district_id="district_central"),
        action=ActionRequest(
            request_id="req-audit-unauth-01",
            domain="parking",
            operation="read",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    gateway.evaluate(req, auth_token="invalid_token_xyz")

    events = audit_service.get_by_request_id("req-audit-unauth-01")
    assert len(events) == 1
    event = events[0]

    assert event.decision == Decision.DENY
    assert event.executed is False
    assert event.reason_code == "UNAUTHENTICATED_ACTOR"
    # Invariant: actor identity must NOT be logged if not resolved by trusted identity mechanism
    assert event.user_id is None


def test_audit_event_never_logs_tokens_or_secrets():
    audit_service = AuditService()
    gateway = GatewayService(audit_service=audit_service)

    secret_token = "token_operator_north"
    req = EvaluationRequest(
        request_id="req-audit-sec-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-audit-sec-01",
            domain="parking",
            operation="read",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    gateway.evaluate(req, auth_token=f"Bearer {secret_token}")

    events = audit_service.get_by_request_id("req-audit-sec-01")
    assert len(events) == 1
    event_dump = events[0].model_dump_json()

    # Invariant: raw token / bearer secret must NEVER be serialized in the audit event
    assert secret_token not in event_dump
    assert "Bearer" not in event_dump


def test_known_username_without_token_is_not_logged_as_authenticated():
    audit_service = AuditService()
    parking = MockParkingService()
    gateway = GatewayService(
        parking_service=parking,
        audit_service=audit_service,
    )
    initial_records = {key: dict(value) for key, value in parking.records.items()}

    request = EvaluationRequest(
        request_id="req-audit-known-user-no-token-01",
        actor=ActorContext(
            user_id="user_operator_north",
            role="operator",
            district_id="district_north",
        ),
        action=ActionRequest(
            request_id="req-audit-known-user-no-token-01",
            domain="parking",
            operation="read",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )

    response = gateway.evaluate(request)

    events = audit_service.get_by_request_id(request.request_id)
    assert len(events) == 1
    event = events[0]
    assert response.decision == Decision.ALLOW
    assert response.executed is False
    assert response.result is None
    assert event.user_id is None
    assert event.executed is False
    assert event.execution_status == "not_attempted"
    assert parking.call_count == 0
    assert parking.records == initial_records


def test_audit_logs_token_identity_not_client_claimed_identity():
    audit_service = AuditService()
    parking = MockParkingService()
    gateway = GatewayService(
        parking_service=parking,
        audit_service=audit_service,
    )
    request = EvaluationRequest(
        request_id="req-audit-token-identity-01",
        actor=ActorContext(
            user_id="user_admin",
            role="admin",
            district_id="district_central",
        ),
        action=ActionRequest(
            request_id="req-audit-token-identity-01",
            domain="parking",
            operation="read",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )

    response = gateway.evaluate(
        request,
        auth_token="Bearer token_operator_north",
    )

    events = audit_service.get_by_request_id(request.request_id)
    assert len(events) == 1
    event = events[0]
    assert response.decision == Decision.ALLOW
    assert response.executed is True
    assert event.user_id == "user_operator_north"
    assert event.user_id != "user_admin"
    event_dump = event.model_dump_json()
    assert "token_operator_north" not in event_dump
    assert "Bearer" not in event_dump


def test_audit_lookup_returns_copy_and_clear_removes_events():
    audit_service = AuditService()
    event = AuditEvent(
        audit_id="audit-management-01",
        request_id="req-management-01",
        domain="parking",
        decision=Decision.ALLOW,
        executed=True,
        reason_code="POLICY_ALLOW",
        user_id="user_operator_north",
        execution_status="success",
    )

    try:
        audit_service.record(event)

        assert audit_service.get_by_audit_id(event.audit_id) == event
        assert audit_service.get_by_audit_id("missing-audit-id") is None

        returned_events = audit_service.get_events()
        returned_events.clear()
        assert len(audit_service.get_events()) == 1

        request_events = audit_service.get_by_request_id(event.request_id)
        request_events.clear()
        assert len(audit_service.get_by_request_id(event.request_id)) == 1

        audit_service.clear()
        assert audit_service.get_events() == []
        assert audit_service.get_by_request_id(event.request_id) == []
        assert audit_service.get_by_audit_id(event.audit_id) is None
    finally:
        audit_service.clear()
