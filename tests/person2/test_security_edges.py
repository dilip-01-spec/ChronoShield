
import pytest

from app.security.engine import evaluate_request
from app.security.schemas import ActionRequest


def make_request():
    return ActionRequest(
        domain="parking",
        action="read",
        resource_id="parking_101",
        parameters={},
        reason="Security edge-case test",
    )


def make_resource():
    return {
        "id": "parking_101",
        "domain": "parking",
        "scope_id": "district_A",
    }


def make_identity():
    return {
        "id": "agent_101",
        "role": "parking_agent",
        "scope_id": "district_A",
    }


def test_none_identity_is_denied():
    result = evaluate_request(None, make_request(), make_resource())
    assert result.decision == "DENY"
    assert result.reason_code == "INVALID_IDENTITY"


def test_empty_identity_id_is_denied():
    identity = make_identity()
    identity["id"] = ""

    result = evaluate_request(identity, make_request(), make_resource())
    assert result.decision == "DENY"
    assert result.reason_code == "INVALID_IDENTITY"


def test_missing_role_is_denied():
    identity = make_identity()
    identity.pop("role")

    result = evaluate_request(identity, make_request(), make_resource())
    assert result.decision == "DENY"
    assert result.reason_code == "UNKNOWN_ROLE"


def test_empty_identity_scope_is_denied():
    identity = make_identity()
    identity["scope_id"] = ""

    result = evaluate_request(identity, make_request(), make_resource())
    assert result.decision == "DENY"
    assert result.reason_code == "MISSING_RESOURCE_SCOPE"


def test_missing_resource_scope_is_denied():
    resource = make_resource()
    resource.pop("scope_id")

    result = evaluate_request(identity=make_identity(),
                              request=make_request(),
                              resource=resource)
    assert result.decision == "DENY"
    assert result.reason_code == "MISSING_RESOURCE_SCOPE"


def test_wrong_district_is_denied():
    resource = make_resource()
    resource["scope_id"] = "district_B"

    result = evaluate_request(make_identity(), make_request(), resource)
    assert result.decision == "DENY"
    assert result.reason_code == "RESOURCE_SCOPE_VIOLATION"

def test_identity_as_string_is_denied():
    result = evaluate_request(
        "fake_identity",
        make_request(),
        make_resource(),
    )
    assert result.decision == "DENY"


def test_identity_as_list_is_denied():
    result = evaluate_request(
        ["agent_101"],
        make_request(),
        make_resource(),
    )
    assert result.decision == "DENY"


def test_resource_as_list_is_denied():
    result = evaluate_request(
        make_identity(),
        make_request(),
        [],
    )
    assert result.decision == "DENY"


def test_resource_as_string_is_denied():
    result = evaluate_request(
        make_identity(),
        make_request(),
        "fake_resource",
    )
    assert result.decision == "DENY"
