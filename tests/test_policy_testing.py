from app.schemas import ActionRequest, Decision
from app.services.identity import TrustedIdentity
from app.services.parking import MockParkingService
from app.services.policy import PolicyEvaluationResult
from app.services.policy_testing import (
    PolicyTestCase,
    PolicyTester,
)


def test_default_policy_test_cases_all_pass():
    tester = PolicyTester()
    report = tester.run_suite()

    assert report.all_passed is True
    assert report.failed == 0
    assert report.total == 6

    # Verify all expected categories are present and passing
    names = [r.test_name for r in report.results]
    assert "authorized_same_district_access" in names
    assert "cross_district_access_denied" in names
    assert "unauthorized_role_operation_denied" in names
    assert "high_impact_operation_requires_approval" in names
    assert "unknown_domain_denied" in names
    assert "unknown_operation_denied" in names

    for r in report.results:
        assert r.passed is True
        assert r.expected_decision == r.actual_decision
        assert "matched expected" in r.reason.lower()


def test_policy_testing_does_not_invoke_or_alter_domain_services():
    mock_parking = MockParkingService()
    initial_call_count = mock_parking.call_count
    # Snapshot all records
    initial_records = {k: dict(v) for k, v in mock_parking.records.items()}

    # Run policy tests
    tester = PolicyTester()
    report = tester.run_suite()
    assert report.all_passed is True

    # Invariant: policy testing must NEVER call domain services or alter state
    assert mock_parking.call_count == initial_call_count == 0
    assert mock_parking.records == initial_records


def test_mismatch_reports_useful_reason_and_failure():
    tester = PolicyTester()

    # Intentionally misconfigured expectation: expecting ALLOW for cross-district request
    flawed_case = PolicyTestCase(
        name="deliberate_flawed_cross_district_test",
        identity=TrustedIdentity(user_id="user_operator_north", role="operator", district_id="district_north"),
        action=ActionRequest(
            request_id="test-flaw-01",
            domain="parking",
            operation="read",
            resource_id="park_south_1",
            resource_district_id="district_south",
        ),
        expected_decision=Decision.ALLOW,  # Intentionally wrong
    )

    result = tester.run_case(flawed_case)
    assert result.passed is False
    assert result.expected_decision == Decision.ALLOW
    assert result.actual_decision == Decision.DENY
    assert result.actual_reason_code == "DISTRICT_MISMATCH"
    assert "Decision mismatch: expected 'allow', got 'deny'" in result.reason
    assert "DISTRICT_MISMATCH" in result.reason


def test_each_required_synthetic_policy_case():
    tester = PolicyTester()
    cases = tester.get_default_cases()

    # 1. Authorized access within the same district
    same_dist = next(c for c in cases if c.name == "authorized_same_district_access")
    res1 = tester.run_case(same_dist)
    assert res1.passed is True
    assert res1.actual_decision == Decision.ALLOW

    # 2. Cross-district access
    cross_dist = next(c for c in cases if c.name == "cross_district_access_denied")
    res2 = tester.run_case(cross_dist)
    assert res2.passed is True
    assert res2.actual_decision == Decision.DENY
    assert res2.actual_reason_code == "DISTRICT_MISMATCH"

    # 3. Role attempting an operation it is not allowed to perform
    role_op = next(c for c in cases if c.name == "unauthorized_role_operation_denied")
    res3 = tester.run_case(role_op)
    assert res3.passed is True
    assert res3.actual_decision == Decision.DENY
    assert res3.actual_reason_code == "ROLE_NOT_AUTHORIZED"

    # 4. An operation requiring approval
    appr_op = next(c for c in cases if c.name == "high_impact_operation_requires_approval")
    res4 = tester.run_case(appr_op)
    assert res4.passed is True
    assert res4.actual_decision == Decision.APPROVAL_REQUIRED
    assert res4.actual_reason_code == "HIGH_IMPACT_APPROVAL_REQUIRED"

    # 5. Unknown domain and unknown operation
    unk_dom = next(c for c in cases if c.name == "unknown_domain_denied")
    res5 = tester.run_case(unk_dom)
    assert res5.passed is True
    assert res5.actual_decision == Decision.DENY
    assert res5.actual_reason_code == "UNKNOWN_DOMAIN"

    unk_op = next(c for c in cases if c.name == "unknown_operation_denied")
    res6 = tester.run_case(unk_op)
    assert res6.passed is True
    assert res6.actual_decision == Decision.DENY
    assert res6.actual_reason_code == "UNKNOWN_OPERATION"


def test_policy_tester_pluggable_with_custom_policy_adapter():
    # Simulates Person 2's future policy engine adapter
    class MockCustomEngine:
        def is_valid_domain(self, domain: str) -> bool:
            return domain == "grid"

        def is_valid_operation(self, domain: str, operation: str) -> bool:
            return operation == "status"

        def evaluate(self, identity: TrustedIdentity, action: ActionRequest) -> PolicyEvaluationResult:
            return PolicyEvaluationResult(
                decision=Decision.ALLOW,
                reason_code="CUSTOM_ALLOW",
                message="Allowed by Person 2's engine",
            )

    custom_tester = PolicyTester(policy_engine=MockCustomEngine())
    custom_case = PolicyTestCase(
        name="custom_engine_test",
        identity=TrustedIdentity(user_id="usr_01", role="admin", district_id="dist_1"),
        action=ActionRequest(
            request_id="r1",
            domain="grid",
            operation="status",
            resource_id="res_1",
            resource_district_id="dist_1",
        ),
        expected_decision=Decision.ALLOW,
        expected_reason_code="CUSTOM_ALLOW",
    )
    result = custom_tester.run_case(custom_case)
    assert result.passed is True
    assert result.actual_reason_code == "CUSTOM_ALLOW"


def test_reason_code_mismatch_fails_even_when_decision_matches():
    tester = PolicyTester()
    case = tester.get_default_cases()[0].model_copy(
        update={"expected_reason_code": "WRONG_REASON_CODE"}
    )

    result = tester.run_case(case)

    assert result.passed is False
    assert result.expected_decision == Decision.ALLOW
    assert result.actual_decision == Decision.ALLOW
    assert result.actual_reason_code == "POLICY_ALLOW"
    assert "Reason code mismatch" in result.reason
    assert "WRONG_REASON_CODE" in result.reason
    assert "POLICY_ALLOW" in result.reason
