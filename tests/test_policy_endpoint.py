from fastapi.testclient import TestClient
from app.api.gateway import get_gateway_service
from app.api.policies import get_policy_tester
from app.main import app
from app.schemas import ActionRequest, Decision
from app.services.identity import TrustedIdentity
from app.services.policy import PolicyEvaluationResult
from app.services.policy_testing import PolicyTester

client = TestClient(app)


def test_post_policies_test_endpoint_passing_suite():
    response = client.post("/api/v1/policies/test")
    assert response.status_code == 200
    data = response.json()

    assert data["all_passed"] is True
    assert data["total"] == 6
    assert data["passed"] == 6
    assert data["failed"] == 0
    assert len(data["results"]) == 6

    # Verify per-case structured fields
    for result in data["results"]:
        assert "test_name" in result
        assert "expected_decision" in result
        assert "actual_decision" in result
        assert result["passed"] is True
        assert "reason" in result
        assert "actual_reason_code" in result
        assert result["expected_decision"] == result["actual_decision"]


def test_post_policies_test_endpoint_with_injected_failing_policy_engine():
    # Flawed engine that denies all requests
    class FailingPolicyEngine:
        def is_valid_domain(self, domain: str) -> bool:
            return True

        def is_valid_operation(self, domain: str, operation: str) -> bool:
            return True

        def evaluate(self, identity: TrustedIdentity, action: ActionRequest) -> PolicyEvaluationResult:
            return PolicyEvaluationResult(
                decision=Decision.DENY,
                reason_code="TOTAL_LOCKDOWN",
                message="All requests blocked by test engine",
            )

    # Cleanly inject flawed engine into the endpoint via FastAPI dependency_overrides
    app.dependency_overrides[get_policy_tester] = lambda: PolicyTester(policy_engine=FailingPolicyEngine())

    try:
        response = client.post("/api/v1/policies/test")
        assert response.status_code == 200
        data = response.json()

        assert data["all_passed"] is False
        assert data["failed"] > 0
        assert data["passed"] < data["total"]

        # Find the case expecting ALLOW (e.g. authorized_same_district_access)
        failed_case = next(r for r in data["results"] if r["test_name"] == "authorized_same_district_access")
        assert failed_case["passed"] is False
        assert failed_case["expected_decision"] == Decision.ALLOW
        assert failed_case["actual_decision"] == Decision.DENY
        assert failed_case["actual_reason_code"] == "TOTAL_LOCKDOWN"
        assert "Decision mismatch" in failed_case["reason"]
        assert "TOTAL_LOCKDOWN" in failed_case["reason"]
    finally:
        app.dependency_overrides.clear()


def test_post_policies_test_endpoint_does_not_execute_domain_services_or_audit():
    gateway = get_gateway_service()
    initial_parking_calls = gateway.parking_service.call_count
    initial_audit_count = len(gateway.audit_service.get_events())
    initial_parking_records = {k: dict(v) for k, v in gateway.parking_service.records.items()}

    response = client.post("/api/v1/policies/test")
    assert response.status_code == 200

    # Invariants: No domain service invocation, no parking record mutation, no runtime audit writes
    assert gateway.parking_service.call_count == initial_parking_calls
    assert gateway.parking_service.records == initial_parking_records
    assert len(gateway.audit_service.get_events()) == initial_audit_count
