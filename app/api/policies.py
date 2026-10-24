from fastapi import APIRouter, Depends
from app.services.policy_factory import get_policy_engine
from app.services.policy_testing import PolicyTestSuiteReport, PolicyTester

router = APIRouter(prefix="/api/v1/policies", tags=["Policies"])

_default_tester = PolicyTester(policy_engine=get_policy_engine())


def get_policy_tester() -> PolicyTester:
    """Dependency provider for PolicyTester, enabling clean dependency overrides in tests."""
    return _default_tester


@router.post(
    "/test",
    response_model=PolicyTestSuiteReport,
    summary="Run pre-deployment policy evaluation tests",
    description=(
        "Evaluates synthetic policy test cases against the policy engine adapter. "
        "Does NOT execute domain services, mutate state, or write runtime audit events. "
        "SECURITY NOTICE: This endpoint is intentionally unauthenticated in this development "
        "prototype for pre-deployment smoke testing and CI/CD validation. In a production environment, "
        "access must be restricted to internal networks or authorized administrative roles."
    ),
)
async def run_policy_tests(
    tester: PolicyTester = Depends(get_policy_tester),
) -> PolicyTestSuiteReport:
    """Run synthetic pre-deployment policy tests and return a structured report."""
    return tester.run_suite()
