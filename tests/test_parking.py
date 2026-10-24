from fastapi.testclient import TestClient
from app.api.gateway import get_gateway_service
from app.main import app
from app.schemas import ActionRequest, ActorContext, Decision, EvaluationRequest
from app.services.audit import AuditService
from app.services.gateway import GatewayService
from app.services.identity import TrustedIdentity
from app.services.parking import MockParkingService

client = TestClient(app)


def test_synthetic_parking_records_in_at_least_two_districts():
    service = MockParkingService()
    north_records = [r for r in service.records.values() if r["district_id"] == "district_north"]
    south_records = [r for r in service.records.values() if r["district_id"] == "district_south"]

    assert len(north_records) >= 2
    assert len(south_records) >= 2
    assert any(r["resource_id"] == "park_north_1" for r in north_records)
    assert any(r["resource_id"] == "park_south_1" for r in south_records)


def test_all_synthetic_parking_records_have_valid_data():
    service = MockParkingService()
    required_fields = {
        "resource_id",
        "district_id",
        "name",
        "total_spots",
        "available_spots",
        "status",
    }

    assert service.records, "Synthetic parking dataset must not be empty"

    for resource_id, record in service.records.items():
        assert isinstance(record, dict)
        assert required_fields <= record.keys()
        assert isinstance(resource_id, str) and resource_id.strip()
        assert record["resource_id"] == resource_id
        assert isinstance(record["district_id"], str)
        assert record["district_id"].strip()
        assert isinstance(record["name"], str) and record["name"].strip()
        assert type(record["total_spots"]) is int
        assert record["total_spots"] > 0
        assert type(record["available_spots"]) is int
        assert 0 <= record["available_spots"] <= record["total_spots"]
        assert record["status"] in {"open", "closed"}


def test_permitted_parking_read_executes():
    payload = {
        "request_id": "req-park-read-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "ignored_client_role",
            "district_id": "district_north",
        },
        "action": {
            "request_id": "req-park-read-01",
            "domain": "parking",
            "operation": "read",
            "resource_id": "park_north_1",
            "resource_district_id": "district_north",
        },
    }
    # Authenticated request using valid demo token
    headers = {"X-Auth-Token": "token_operator_north"}
    response = client.post("/api/v1/requests/evaluate", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.ALLOW
    assert data["executed"] is True
    assert data["result"] is not None
    assert data["result"]["success"] is True
    assert data["result"]["record"]["resource_id"] == "park_north_1"
    assert data["result"]["record"]["district_id"] == "district_north"
    assert data["result"]["record"]["total_spots"] == 120
    assert data["result"]["record"]["available_spots"] == 45


def test_cross_district_parking_read_blocked():
    payload = {
        "request_id": "req-park-cross-dist-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "operator",
            "district_id": "district_north",
        },
        "action": {
            "request_id": "req-park-cross-dist-01",
            "domain": "parking",
            "operation": "read",
            "resource_id": "park_south_1",
            "resource_district_id": "district_south",  # Mismatch with North operator
        },
    }
    headers = {"X-Auth-Token": "token_operator_north"}
    response = client.post("/api/v1/requests/evaluate", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == "DISTRICT_MISMATCH"
    assert data["executed"] is False
    assert data["result"] is None


def test_protected_service_never_called_for_denied_or_approval_required():
    # Direct unit test on GatewayService with a fresh mock to verify call_count invariant
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking)

    # 1. Denied request: Cross-district operation
    denied_req = EvaluationRequest(
        request_id="req-unit-deny-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-unit-deny-01",
            domain="parking",
            operation="read",
            resource_id="park_south_1",
            resource_district_id="district_south",
        ),
    )
    denied_resp = gateway.evaluate(denied_req, auth_token="token_operator_north")
    assert denied_resp.decision == Decision.DENY
    assert denied_resp.executed is False
    # Verified invariant: protected service was NOT called
    assert mock_parking.call_count == 0

    # 2. Approval-required request: high-impact operation 'close_zone'
    approval_req = EvaluationRequest(
        request_id="req-unit-approval-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-unit-approval-01",
            domain="parking",
            operation="close_zone",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    approval_resp = gateway.evaluate(approval_req, auth_token="token_operator_north")
    assert approval_resp.decision == Decision.APPROVAL_REQUIRED
    assert approval_resp.executed is False
    # Verified invariant: protected service was NOT called for pending approval
    assert mock_parking.call_count == 0


def test_unauthenticated_request_cannot_execute_protected_parking_service():
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking)

    # Request has user_id="user_operator_north" in ActorContext, but NO auth_token
    unauth_req = EvaluationRequest(
        request_id="req-unauth-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-unauth-01",
            domain="parking",
            operation="read",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    resp = gateway.evaluate(unauth_req, auth_token=None)

    # Execution is blocked because actor metadata alone is not proof of identity
    assert resp.executed is False
    assert mock_parking.call_count == 0
    assert "authenticated" in resp.message.lower()


def test_permitted_parking_reserve_spot_execution():
    payload = {
        "request_id": "req-park-reserve-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "operator",
            "district_id": "district_north",
        },
        "action": {
            "request_id": "req-park-reserve-01",
            "domain": "parking",
            "operation": "reserve_spot",
            "resource_id": "park_north_2",
            "resource_district_id": "district_north",
        },
    }
    headers = {"X-Auth-Token": "token_operator_north"}
    response = client.post("/api/v1/requests/evaluate", json=payload, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.ALLOW
    assert data["executed"] is True
    assert data["result"]["status"] == "reserved"
    assert data["result"]["available_spots"] == 109  # 110 - 1


def test_invalid_token_denied_with_unauthenticated_actor():
    payload = {
        "request_id": "req-invalid-tok-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "operator",
            "district_id": "district_north",
        },
        "action": {
            "request_id": "req-invalid-tok-01",
            "domain": "parking",
            "operation": "read",
            "resource_id": "park_north_1",
            "resource_district_id": "district_north",
        },
    }
    response = client.post(
        "/api/v1/requests/evaluate",
        json=payload,
        headers={"X-Auth-Token": "completely_invalid_secret_token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == "UNAUTHENTICATED_ACTOR"
    assert data["executed"] is False
    assert data["result"] is None


def test_valid_token_via_authorization_bearer_header():
    payload = {
        "request_id": "req-bearer-tok-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "operator",
            "district_id": "district_north",
        },
        "action": {
            "request_id": "req-bearer-tok-01",
            "domain": "parking",
            "operation": "read",
            "resource_id": "park_north_1",
            "resource_district_id": "district_north",
        },
    }
    response = client.post(
        "/api/v1/requests/evaluate",
        json=payload,
        headers={"Authorization": "Bearer token_operator_north"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.ALLOW
    assert data["executed"] is True
    assert data["result"]["record"]["resource_id"] == "park_north_1"


def test_cross_district_reserve_spot_denied_without_changing_spots():
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking)

    initial_spots = mock_parking.records["park_south_1"]["available_spots"]

    req = EvaluationRequest(
        request_id="req-cross-reserve-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-cross-reserve-01",
            domain="parking",
            operation="reserve_spot",
            resource_id="park_south_1",
            resource_district_id="district_south",
        ),
    )
    resp = gateway.evaluate(req, auth_token="token_operator_north")

    assert resp.decision == Decision.DENY
    assert resp.reason_code == "DISTRICT_MISMATCH"
    assert resp.executed is False
    # Verify spots were NOT modified and service was never executed
    assert mock_parking.records["park_south_1"]["available_spots"] == initial_spots
    assert mock_parking.call_count == 0


def test_unauthenticated_reserve_spot_does_not_execute_or_change_spots():
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking)

    initial_spots = mock_parking.records["park_north_1"]["available_spots"]

    req = EvaluationRequest(
        request_id="req-unauth-reserve-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-unauth-reserve-01",
            domain="parking",
            operation="reserve_spot",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    resp = gateway.evaluate(req, auth_token=None)

    assert resp.executed is False
    # Verify spots were NOT modified and service was never executed
    assert mock_parking.records["park_north_1"]["available_spots"] == initial_spots
    assert mock_parking.call_count == 0


def test_full_parking_facility_returns_failure_with_executed_false():
    mock_parking = MockParkingService()
    # Simulate a completely full lot
    mock_parking.records["park_north_1"]["available_spots"] = 0
    gateway = GatewayService(parking_service=mock_parking)

    req = EvaluationRequest(
        request_id="req-full-reserve-01",
        actor=ActorContext(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="req-full-reserve-01",
            domain="parking",
            operation="reserve_spot",
            resource_id="park_north_1",
            resource_district_id="district_north",
        ),
    )
    resp = gateway.evaluate(req, auth_token="token_operator_north")

    # Policy authorized the request, but domain execution reported failure
    assert resp.decision == Decision.ALLOW
    assert resp.executed is False
    assert resp.result is not None
    assert resp.result["success"] is False
    assert resp.result["error"] == "No spots available"
    assert "failed" in resp.message.lower()
    assert mock_parking.records["park_north_1"]["available_spots"] == 0
    assert mock_parking.call_count == 1


def test_claimed_resource_district_cannot_override_authoritative_resource():
    mock_parking = MockParkingService()
    audit_service = AuditService()
    gateway = GatewayService(
        parking_service=mock_parking,
        audit_service=audit_service,
    )

    req = EvaluationRequest(
        request_id="req-spoofed-resource-district-01",
        actor=ActorContext(
            user_id="user_operator_north",
            role="operator",
            district_id="district_north",
        ),
        action=ActionRequest(
            request_id="req-spoofed-resource-district-01",
            domain="parking",
            operation="read",
            resource_id="park_south_1",
            resource_district_id="district_north",  # False client claim
        ),
    )

    response = gateway.evaluate(req, auth_token="token_operator_north")

    assert response.decision == Decision.DENY
    assert response.reason_code == "DISTRICT_MISMATCH"
    assert response.executed is False
    assert response.result is None
    assert mock_parking.call_count == 0

    events = audit_service.get_by_request_id(
        "req-spoofed-resource-district-01"
    )
    assert len(events) == 1
    assert events[0].decision == Decision.DENY
    assert events[0].executed is False
    assert events[0].execution_status == "not_attempted"
    assert events[0].user_id == "user_operator_north"


def test_cross_district_read_denied_when_claimed_district_is_local():
    gateway = get_gateway_service()
    initial_call_count = gateway.parking_service.call_count
    payload = {
        "request_id": "req-api-spoofed-resource-district-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "operator",
            "district_id": "district_north",
        },
        "action": {
            "request_id": "req-api-spoofed-resource-district-01",
            "domain": "parking",
            "operation": "read",
            "resource_id": "park_south_1",
            "resource_district_id": "district_north",  # False client claim
        },
    }

    response = client.post(
        "/api/v1/requests/evaluate",
        json=payload,
        headers={"X-Auth-Token": "token_operator_north"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == "DISTRICT_MISMATCH"
    assert data["executed"] is False
    assert data["result"] is None
    assert gateway.parking_service.call_count == initial_call_count


def test_cross_district_reserve_with_spoofed_district_does_not_mutate():
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking)
    initial_spots = mock_parking.records["park_south_1"]["available_spots"]

    req = EvaluationRequest(
        request_id="req-spoofed-reserve-01",
        actor=ActorContext(
            user_id="user_operator_north",
            role="operator",
            district_id="district_north",
        ),
        action=ActionRequest(
            request_id="req-spoofed-reserve-01",
            domain="parking",
            operation="reserve_spot",
            resource_id="park_south_1",
            resource_district_id="district_north",  # False client claim
        ),
    )

    response = gateway.evaluate(req, auth_token="token_operator_north")

    assert response.decision == Decision.DENY
    assert response.reason_code == "DISTRICT_MISMATCH"
    assert response.executed is False
    assert response.result is None
    assert mock_parking.call_count == 0
    assert mock_parking.records["park_south_1"]["available_spots"] == initial_spots


def test_parking_service_rechecks_authoritative_resource_district():
    mock_parking = MockParkingService()
    north_identity = TrustedIdentity(
        user_id="user_operator_north",
        role="operator",
        district_id="district_north",
        is_authenticated=True,
    )
    initial_spots = mock_parking.records["park_south_1"]["available_spots"]

    read_result = mock_parking.execute(
        operation="read",
        resource_id="park_south_1",
        authorized_identity=north_identity,
    )
    reserve_result = mock_parking.execute(
        operation="reserve_spot",
        resource_id="park_south_1",
        authorized_identity=north_identity,
    )

    assert read_result["success"] is False
    assert read_result["reason_code"] == "DISTRICT_MISMATCH"
    assert reserve_result["success"] is False
    assert reserve_result["reason_code"] == "DISTRICT_MISMATCH"
    assert mock_parking.call_count == 2
    assert mock_parking.records["park_south_1"]["available_spots"] == initial_spots


def test_missing_or_invalid_resource_metadata_is_denied_safely():
    missing_resource_service = MockParkingService()
    missing_gateway = GatewayService(parking_service=missing_resource_service)
    missing_req = EvaluationRequest(
        request_id="req-missing-resource-01",
        actor=ActorContext(
            user_id="user_operator_north",
            role="operator",
            district_id="district_north",
        ),
        action=ActionRequest(
            request_id="req-missing-resource-01",
            domain="parking",
            operation="read",
            resource_id="park_missing",
            resource_district_id="district_north",
        ),
    )

    missing_response = missing_gateway.evaluate(
        missing_req, auth_token="token_operator_north"
    )

    assert missing_response.decision == Decision.DENY
    assert missing_response.reason_code == "RESOURCE_NOT_FOUND"
    assert missing_response.executed is False
    assert missing_response.result is None
    assert missing_resource_service.call_count == 0

    invalid_metadata_service = MockParkingService()
    invalid_metadata_service.records["park_north_1"].pop("district_id")
    invalid_gateway = GatewayService(parking_service=invalid_metadata_service)
    invalid_req = missing_req.model_copy(
        update={
            "request_id": "req-invalid-resource-metadata-01",
            "action": missing_req.action.model_copy(
                update={
                    "request_id": "req-invalid-resource-metadata-01",
                    "resource_id": "park_north_1",
                }
            ),
        }
    )

    invalid_response = invalid_gateway.evaluate(
        invalid_req, auth_token="token_operator_north"
    )

    assert invalid_response.decision == Decision.DENY
    assert invalid_response.reason_code == "INVALID_RESOURCE_DISTRICT"
    assert invalid_response.executed is False
    assert invalid_response.result is None
    assert invalid_metadata_service.call_count == 0


def test_permitted_parking_release_spot_execution():
    mock_parking = MockParkingService()
    gateway = GatewayService(parking_service=mock_parking)
    initial_spots = mock_parking.records["park_north_2"]["available_spots"]

    req = EvaluationRequest(
        request_id="req-park-release-01",
        actor=ActorContext(
            user_id="user_operator_north",
            role="operator",
            district_id="district_north",
        ),
        action=ActionRequest(
            request_id="req-park-release-01",
            domain="parking",
            operation="release_spot",
            resource_id="park_north_2",
            resource_district_id="district_north",
        ),
    )

    response = gateway.evaluate(req, auth_token="token_operator_north")

    assert response.decision == Decision.ALLOW
    assert response.executed is True
    assert response.result["status"] == "released"
    assert response.result["available_spots"] == initial_spots + 1
    assert mock_parking.records["park_north_2"]["available_spots"] == initial_spots + 1
