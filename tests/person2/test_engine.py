from dataclasses import dataclass
from app.security.engine import evaluate_request
from app.security.schemas import ActionRequest
from app.security.engine import (
    Decision,
    FormalPolicyEngine,
)



def make_request(domain, action):
    return ActionRequest(
        domain=domain,
        action=action,
        resource_id="resource_101",
    )


def make_identity(role, scope_id="district_A"):
    return {
        "id": "agent_101",
        "role": role,
        "scope_id": scope_id,
    }


def make_resource(domain, scope_id="district_A"):
    return {
        "id": "resource_101",
        "domain": domain,
        "scope_id": scope_id,
    }


def test_parking_read_allowed():
    result = evaluate_request(
        make_identity("parking_agent"),
        make_request("parking", "read"),
        make_resource("parking"),
    )

    assert result.decision == "ALLOW"


def test_cross_scope_access_denied():
    result = evaluate_request(
        make_identity("parking_agent", "district_A"),
        make_request("parking", "read"),
        make_resource("parking", "district_B"),
    )

    assert result.decision == "DENY"
    assert result.reason_code == "RESOURCE_SCOPE_VIOLATION"


def test_water_update_requires_approval():
    result = evaluate_request(
        make_identity("water_agent"),
        make_request("water", "update"),
        make_resource("water"),
    )

    assert result.decision == "REQUIRES_APPROVAL"


def test_unknown_role_denied():
    result = evaluate_request(
        make_identity("unknown_agent"),
        make_request("parking", "read"),
        make_resource("parking"),
    )

    assert result.decision == "DENY"
    assert result.reason_code == "UNKNOWN_ROLE"


def test_missing_resource_denied():
    result = evaluate_request(
        make_identity("parking_agent"),
        make_request("parking", "read"),
        None,
    )

    assert result.decision == "DENY"
    assert result.reason_code == "RESOURCE_NOT_FOUND"


def test_resource_domain_mismatch_denied():
    result = evaluate_request(
        make_identity("parking_agent"),
        make_request("parking", "read"),
        make_resource("traffic"),
    )

    assert result.decision == "DENY"
    assert result.reason_code == "RESOURCE_DOMAIN_MISMATCH"


def test_unknown_action_denied():
    result = evaluate_request(
        make_identity("parking_agent"),
        make_request("parking", "delete_everything"),
        make_resource("parking"),
    )

    assert result.decision == "DENY"
    assert result.reason_code == "UNKNOWN_ACTION"

def test_traffic_signal_change_requires_approval():
    result = evaluate_request(
        make_identity("traffic_agent"),
        make_request("traffic", "change_signal"),
        make_resource("traffic"),
    )

    assert result.decision == "REQUIRES_APPROVAL"


def test_energy_grid_change_requires_approval():
    result = evaluate_request(
        make_identity("energy_grid_agent"),
        make_request("energy_grid", "change_grid_settings"),
        make_resource("energy_grid"),
    )

    assert result.decision == "REQUIRES_APPROVAL"


def test_ev_charger_update_requires_approval():
    result = evaluate_request(
        make_identity("ev_charger_agent"),
        make_request("ev_chargers", "update"),
        make_resource("ev_chargers"),
    )

    assert result.decision == "REQUIRES_APPROVAL"


def test_agent_cannot_access_different_domain():
    result = evaluate_request(
        make_identity("parking_agent"),
        make_request("traffic", "read"),
        make_resource("traffic"),
    )

    assert result.decision == "DENY"
    assert result.reason_code == "INSUFFICIENT_PERMISSION"


def test_unknown_domain_is_rejected():
    request = ActionRequest.model_construct(
        domain="healthcare",
        action="read",
        resource_id="resource_101",
        parameters={},
        reason="Test invalid domain",
    )

    result = evaluate_request(
        make_identity("parking_agent"),
        request,
        make_resource("healthcare"),
    )

    assert result.decision == "DENY"
    assert result.reason_code == "UNKNOWN_DOMAIN"

def test_missing_identity_is_denied():
    result = evaluate_request(
        {},
        make_request("parking", "read"),
        make_resource("parking"),
    )
    assert result.decision == "DENY"
    assert result.reason_code == "INVALID_IDENTITY"


def test_missing_identity_scope_is_denied():
    identity = {
        "id": "agent_101",
        "role": "parking_agent",
    }

    result = evaluate_request(
        identity,
        make_request("parking", "read"),
        make_resource("parking"),
    )

    assert result.decision == "DENY"
    assert result.reason_code == "MISSING_RESOURCE_SCOPE"


def test_resource_scope_mismatch_is_denied():
    identity = {
        "id": "agent_101",
        "role": "parking_agent",
        "scope_id": "district_A",
    }
    resource = {
        "domain": "parking",
        "scope_id": "district_B",
    }

    result = evaluate_request(
        identity,
        make_request("parking", "read"),
        resource,
    )

    assert result.decision == "DENY"
    assert result.reason_code == "RESOURCE_SCOPE_VIOLATION"


@dataclass
class Identity:
    user_id: str = "user_operator_north"
    role: str = "operator"
    district_id: str = "north"
    is_authenticated: bool = True


@dataclass
class Action:
    domain: str = "parking"
    operation: str = "status"
    resource_id: str = "p-1"
    resource_district_id: str = "north"


def test_all_eight_domains_and_operations_are_registered():
    engine = FormalPolicyEngine()

    assert set(engine.VALID_DOMAINS) == {
        "parking",
        "grid",
        "transit",
        "water",
        "waste",
        "emergency",
        "telecom",
        "healthcare",
    }

    assert engine.is_valid_operation("transit", "adjust_signals")
    assert engine.is_valid_operation("grid", "reroute_power")

    assert not engine.is_valid_domain("ev_chargers")
    assert not engine.is_valid_domain("traffic")


def test_operator_can_read_in_own_district():
    result = FormalPolicyEngine().evaluate(
        Identity(),
        Action(),
    )

    assert result.decision == Decision.ALLOW


def test_operator_cannot_access_another_district():
    result = FormalPolicyEngine().evaluate(
        Identity(),
        Action(resource_district_id="south"),
    )

    assert result.decision == Decision.DENY
    assert result.reason_code == "DISTRICT_MISMATCH"


def test_viewer_cannot_change_signals():
    result = FormalPolicyEngine().evaluate(
        Identity(role="viewer"),
        Action(
            domain="transit",
            operation="adjust_signals",
        ),
    )

    assert result.decision == Decision.DENY
    assert result.reason_code == "ROLE_NOT_AUTHORIZED"


def test_sensitive_grid_operation_requires_approval():
    result = FormalPolicyEngine().evaluate(
        Identity(role="admin"),
        Action(
            domain="grid",
            operation="reroute_power",
        ),
    )

    assert result.decision == Decision.APPROVAL_REQUIRED


def test_sensitive_transit_emergency_stop_requires_approval():
    result = FormalPolicyEngine().evaluate(
        Identity(role="admin"),
        Action(
            domain="transit",
            operation="emergency_stop",
        ),
    )

    assert result.decision == Decision.APPROVAL_REQUIRED


def test_unknown_operation_is_denied():
    result = FormalPolicyEngine().evaluate(
        Identity(role="admin"),
        Action(operation="delete_everything"),
    )

    assert result.decision == Decision.DENY
    assert result.reason_code == "UNKNOWN_OPERATION"


def test_missing_identity_is_denied():
    result = FormalPolicyEngine().evaluate(
        None,
        Action(),
    )

    assert result.decision == Decision.DENY
    assert result.reason_code == "INVALID_IDENTITY"