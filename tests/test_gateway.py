from fastapi.testclient import TestClient
from app.api.gateway import get_gateway_service
from app.main import app
from app.schemas import Decision

client = TestClient(app)


def test_decision_allow():
    payload = {
        "request_id": "req-allow-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "ignored_client_role",
            "district_id": "ignored_client_district",
        },
        "action": {
            "request_id": "req-allow-01",
            "domain": "grid",
            "operation": "status",
            "resource_id": "substation_north_1",
            "resource_district_id": "district_north",
        },
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req-allow-01"
    assert data["decision"] == Decision.ALLOW
    assert data["executed"] is False
    assert data["reason_code"] == "POLICY_ALLOW"
    assert "audit_id" in data


def test_decision_deny_unauthorized_role():
    payload = {
        "request_id": "req-deny-role-01",
        "actor": {
            "user_id": "user_viewer",
            "role": "viewer",
            "district_id": "district_central",
        },
        "action": {
            "request_id": "req-deny-role-01",
            "domain": "water",
            "operation": "adjust_flow",
            "resource_id": "pump_01",
            "resource_district_id": "district_central",
        },
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == "ROLE_NOT_AUTHORIZED"
    assert data["executed"] is False


def test_decision_deny_district_mismatch():
    payload = {
        "request_id": "req-deny-dist-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "operator",
            "district_id": "district_north",
        },
        "action": {
            "request_id": "req-deny-dist-01",
            "domain": "grid",
            "operation": "status",
            "resource_id": "substation_south_1",
            "resource_district_id": "district_south",
        },
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == "DISTRICT_MISMATCH"
    assert data["executed"] is False


def test_untrusted_client_role_cannot_elevate_privileges():
    # Client attempts to claim "admin" role, but server resolves real role as operator
    payload = {
        "request_id": "req-spoof-role-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "admin",  # Untrusted client spoofing
            "district_id": "district_central",
        },
        "action": {
            "request_id": "req-spoof-role-01",
            "domain": "grid",
            "operation": "status",
            "resource_id": "substation_south_1",
            "resource_district_id": "district_south",  # Operator north cannot touch south
        },
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Spoofed role was ignored; operator was denied access to south district
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == "DISTRICT_MISMATCH"
    assert data["executed"] is False


def test_decision_deny_unauthenticated_user():
    payload = {
        "request_id": "req-unauth-01",
        "actor": {
            "user_id": "unregistered_intruder",
            "role": "admin",
            "district_id": "district_central",
        },
        "action": {
            "request_id": "req-unauth-01",
            "domain": "grid",
            "operation": "status",
            "resource_id": "substation_1",
            "resource_district_id": "district_central",
        },
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == "UNAUTHENTICATED_ACTOR"
    assert data["executed"] is False


def test_decision_approval_required():
    payload = {
        "request_id": "req-approval-01",
        "actor": {
            "user_id": "user_operator_north",
            "role": "operator",
            "district_id": "district_north",
        },
        "action": {
            "request_id": "req-approval-01",
            "domain": "grid",
            "operation": "reroute_power",  # High-impact operation
            "resource_id": "substation_north_1",
            "resource_district_id": "district_north",
        },
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.APPROVAL_REQUIRED
    assert data["reason_code"] == "HIGH_IMPACT_APPROVAL_REQUIRED"
    assert data["executed"] is False
    assert "pending" in data["message"].lower()


def test_rule_no_operation_executes_in_stage_3():
    # Ensure executed is False across allow, deny, and approval_required decisions
    scenarios = [
        # Allow case
        {
            "request_id": "req-check-exec-1",
            "actor": {"user_id": "user_operator_north", "role": "", "district_id": ""},
            "action": {
                "request_id": "req-check-exec-1",
                "domain": "grid",
                "operation": "status",
                "resource_id": "sub_1",
                "resource_district_id": "district_north",
            },
        },
        # Deny case
        {
            "request_id": "req-check-exec-2",
            "actor": {"user_id": "user_viewer", "role": "", "district_id": ""},
            "action": {
                "request_id": "req-check-exec-2",
                "domain": "grid",
                "operation": "reroute_power",
                "resource_id": "sub_1",
                "resource_district_id": "district_north",
            },
        },
        # Approval required case
        {
            "request_id": "req-check-exec-3",
            "actor": {"user_id": "user_operator_north", "role": "", "district_id": ""},
            "action": {
                "request_id": "req-check-exec-3",
                "domain": "grid",
                "operation": "reroute_power",
                "resource_id": "sub_1",
                "resource_district_id": "district_north",
            },
        },
    ]

    for scenario in scenarios:
        res = client.post("/api/v1/requests/evaluate", json=scenario)
        assert res.status_code == 200
        assert res.json()["executed"] is False


def test_unknown_domain_returns_api_error():
    payload = {
        "request_id": "req-err-domain-01",
        "actor": {"user_id": "user_admin", "role": "admin", "district_id": "district_central"},
        "action": {
            "request_id": "req-err-domain-01",
            "domain": "hyperspace_relay",  # Unknown domain
            "operation": "status",
            "resource_id": "relay_1",
            "resource_district_id": "district_central",
        },
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "UNKNOWN_DOMAIN"
    assert data["request_id"] == "req-err-domain-01"
    assert "hyperspace_relay" in data["message"]


def test_unknown_operation_returns_api_error():
    payload = {
        "request_id": "req-err-op-01",
        "actor": {"user_id": "user_admin", "role": "admin", "district_id": "district_central"},
        "action": {
            "request_id": "req-err-op-01",
            "domain": "grid",
            "operation": "overcharge_quantum_core",  # Unknown operation for grid
            "resource_id": "core_1",
            "resource_district_id": "district_central",
        },
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "UNKNOWN_OPERATION"
    assert data["request_id"] == "req-err-op-01"
    assert "overcharge_quantum_core" in data["message"]


def test_malformed_input_returns_structured_api_error():
    # Missing required 'action' block entirely
    payload = {
        "request_id": "req-malformed-01",
    }
    response = client.post("/api/v1/requests/evaluate", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "MALFORMED_INPUT"
    assert data["request_id"] == "req-malformed-01"
    assert "action" in data["message"]


def test_health_and_root_endpoints_preserved():
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert root_resp.json()["docs"] == "/docs"


def test_authenticated_viewer_cannot_spoof_admin_role():
    gateway = get_gateway_service()
    initial_call_count = gateway.parking_service.call_count
    initial_records = {key: dict(value) for key, value in gateway.parking_service.records.items()}
    payload = {
        "request_id": "req-role-spoof-01",
        "actor": {
            "user_id": "user_viewer",
            "role": "admin",
            "district_id": "district_central",
        },
        "action": {
            "request_id": "req-role-spoof-01",
            "domain": "parking",
            "operation": "reserve_spot",
            "resource_id": "park_north_1",
            "resource_district_id": "district_north",
        },
    }

    response = client.post(
        "/api/v1/requests/evaluate",
        json=payload,
        headers={"X-Auth-Token": "token_viewer"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == Decision.DENY
    assert data["reason_code"] == "ROLE_NOT_AUTHORIZED"
    assert data["executed"] is False
    assert data["result"] is None
    assert gateway.parking_service.call_count == initial_call_count
    assert gateway.parking_service.records == initial_records
