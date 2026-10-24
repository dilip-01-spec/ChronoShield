from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas import ActionRequest, Decision
from app.services.identity import TrustedIdentity
from app.services.policy import PolicyEngineAdapter
from app.services.policy_factory import get_policy_engine


class PolicyTestCase(BaseModel):
    """Pre-deployment policy test scenario defining inputs and expected evaluation decision."""
    name: str
    identity: TrustedIdentity
    action: ActionRequest
    expected_decision: Decision
    expected_reason_code: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PolicyTestResult(BaseModel):
    """Outcome of evaluating a single policy test case."""
    test_name: str
    expected_decision: Decision
    actual_decision: Decision
    passed: bool
    reason: str
    actual_reason_code: str
    message: str


class PolicyTestSuiteReport(BaseModel):
    """Aggregated pre-deployment policy evaluation test report."""
    total: int
    passed: int
    failed: int
    all_passed: bool
    results: List[PolicyTestResult]


class PolicyTester:
    """Pre-deployment policy testing runner evaluating policy rules without invoking domain services."""

    def __init__(self, policy_engine: Optional[PolicyEngineAdapter] = None):
        self.policy_engine = policy_engine if policy_engine is not None else get_policy_engine()

    @staticmethod
    def get_default_cases() -> List[PolicyTestCase]:
        """Synthetic test cases covering core policy boundaries."""
        return [
            # 1. Authorized access within the same district
            PolicyTestCase(
                name="authorized_same_district_access",
                identity=TrustedIdentity(user_id="user_operator_north", role="operator", district_id="district_north"),
                action=ActionRequest(
                    request_id="test-req-01",
                    domain="parking",
                    operation="read",
                    resource_id="park_north_1",
                    resource_district_id="district_north",
                ),
                expected_decision=Decision.ALLOW,
                expected_reason_code="POLICY_ALLOW",
                description="Operator accessing a resource inside their own assigned district",
            ),
            # 2. Cross-district access (blocked)
            PolicyTestCase(
                name="cross_district_access_denied",
                identity=TrustedIdentity(user_id="user_operator_north", role="operator", district_id="district_north"),
                action=ActionRequest(
                    request_id="test-req-02",
                    domain="parking",
                    operation="read",
                    resource_id="park_south_1",
                    resource_district_id="district_south",
                ),
                expected_decision=Decision.DENY,
                expected_reason_code="DISTRICT_MISMATCH",
                description="Operator attempting to access a resource in another district",
            ),
            # 3. Role attempting unauthorized operation
            PolicyTestCase(
                name="unauthorized_role_operation_denied",
                identity=TrustedIdentity(user_id="user_viewer", role="viewer", district_id="district_central"),
                action=ActionRequest(
                    request_id="test-req-03",
                    domain="parking",
                    operation="reserve_spot",
                    resource_id="park_central_1",
                    resource_district_id="district_central",
                ),
                expected_decision=Decision.DENY,
                expected_reason_code="ROLE_NOT_AUTHORIZED",
                description="Viewer attempting a mutation operation reserved for operators/admins",
            ),
            # 4. Operation requiring approval
            PolicyTestCase(
                name="high_impact_operation_requires_approval",
                identity=TrustedIdentity(user_id="user_operator_north", role="operator", district_id="district_north"),
                action=ActionRequest(
                    request_id="test-req-04",
                    domain="parking",
                    operation="close_zone",
                    resource_id="park_north_1",
                    resource_district_id="district_north",
                ),
                expected_decision=Decision.APPROVAL_REQUIRED,
                expected_reason_code="HIGH_IMPACT_APPROVAL_REQUIRED",
                description="High-impact operation requiring supervisor/temporal approval",
            ),
            # 5a. Unknown domain
            PolicyTestCase(
                name="unknown_domain_denied",
                identity=TrustedIdentity(user_id="user_admin", role="admin", district_id="district_central"),
                action=ActionRequest(
                    request_id="test-req-05",
                    domain="quantum_hyperspace",
                    operation="status",
                    resource_id="node_01",
                    resource_district_id="district_central",
                ),
                expected_decision=Decision.DENY,
                expected_reason_code="UNKNOWN_DOMAIN",
                description="Action targeting an unregistered domain",
            ),
            # 5b. Unknown operation within known domain
            PolicyTestCase(
                name="unknown_operation_denied",
                identity=TrustedIdentity(user_id="user_admin", role="admin", district_id="district_central"),
                action=ActionRequest(
                    request_id="test-req-06",
                    domain="parking",
                    operation="teleport_cars",
                    resource_id="park_north_1",
                    resource_district_id="district_north",
                ),
                expected_decision=Decision.DENY,
                expected_reason_code="UNKNOWN_OPERATION",
                description="Unregistered operation requested on valid domain",
            ),
        ]

    def run_case(self, case: PolicyTestCase) -> PolicyTestResult:
        """Evaluate a single test case against the policy adapter."""
        eval_result = self.policy_engine.evaluate(case.identity, case.action)

        decision_matches = eval_result.decision == case.expected_decision
        reason_matches = (
            case.expected_reason_code is None
            or eval_result.reason_code == case.expected_reason_code
        )
        passed = decision_matches and reason_matches

        if passed:
            reason = f"Decision matched expected '{case.expected_decision.value}'"
        elif not decision_matches:
            reason = (
                f"Decision mismatch: expected '{case.expected_decision.value}', "
                f"got '{eval_result.decision.value}' ({eval_result.reason_code})"
            )
        else:
            reason = (
                f"Reason code mismatch: expected '{case.expected_reason_code}', "
                f"got '{eval_result.reason_code}'"
            )

        return PolicyTestResult(
            test_name=case.name,
            expected_decision=case.expected_decision,
            actual_decision=eval_result.decision,
            passed=passed,
            reason=reason,
            actual_reason_code=eval_result.reason_code,
            message=eval_result.message,
        )

    def run_suite(self, cases: Optional[List[PolicyTestCase]] = None) -> PolicyTestSuiteReport:
        """Run a test suite and return structured results report."""
        test_cases = cases if cases is not None else self.get_default_cases()
        results = [self.run_case(case) for case in test_cases]
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count

        return PolicyTestSuiteReport(
            total=len(results),
            passed=passed_count,
            failed=failed_count,
            all_passed=failed_count == 0,
            results=results,
        )
