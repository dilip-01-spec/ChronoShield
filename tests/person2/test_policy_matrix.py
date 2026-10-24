
import pytest

from app.security.engine import evaluate_request
from app.security.schemas import ActionRequest


# One standard identity and resource for each test.
def make_identity(role):
    return {
        "id": "agent_101",
        "role": role,
        "scope_id": "district_A",
    }


def make_request(domain, action):
    return ActionRequest(
        domain=domain,
        action=action,
        resource_id="resource_101",
        parameters={},
        reason="Policy matrix test",
    )


def make_resource(domain):
    return {
        "id": "resource_101",
        "domain": domain,
        "scope_id": "district_A",
    }


# Each domain's normal read action should be allowed.
@pytest.mark.parametrize(
    "domain,role",
    [
        ("parking", "parking_agent"),
        ("traffic", "traffic_agent"),
        ("water", "water_agent"),
        ("ev_chargers", "ev_charger_agent"),
        ("energy_grid", "energy_grid_agent"),
    ],
)
def test_domain_read_is_allowed(domain, role):
    result = evaluate_request(
        make_identity(role),
        make_request(domain, "read"),
        make_resource(domain),
    )

    assert result.decision == "ALLOW"
    assert result.reason_code == "POLICY_MATCH"


# Sensitive operations should require approval.
@pytest.mark.parametrize(
    "domain,role,action",
    [
        ("parking", "parking_agent", "update"),
        ("traffic", "traffic_agent", "change_signal"),
        ("water", "water_agent", "update"),
        ("ev_chargers", "ev_charger_agent", "update"),
        (
            "energy_grid",
            "energy_grid_agent",
            "change_grid_settings",
        ),
    ],
)
def test_sensitive_action_requires_approval(domain, role, action):
    result = evaluate_request(
        make_identity(role),
        make_request(domain, action),
        make_resource(domain),
    )

    assert result.decision == "REQUIRES_APPROVAL"
    assert result.reason_code == "SENSITIVE_ACTION"


# An agent must not access another domain.
@pytest.mark.parametrize(
    "role,domain",
    [
        ("parking_agent", "traffic"),
        ("traffic_agent", "water"),
        ("water_agent", "ev_chargers"),
        ("ev_charger_agent", "energy_grid"),
        ("energy_grid_agent", "parking"),
    ],
)
def test_cross_domain_access_is_denied(role, domain):
    result = evaluate_request(
        make_identity(role),
        make_request(domain, "read"),
        make_resource(domain),
    )

    assert result.decision == "DENY"
    assert result.reason_code == "INSUFFICIENT_PERMISSION"
