import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.gateway import get_gateway_service
from app.api.policies import get_policy_tester
from app.main import app
from app.schemas import Decision, EvaluationRequest
from app.services.gateway import GatewayService
from app.services import policy_factory
from app.services.policy import DevMockPolicyEngine, FormalPolicyEngineAdapter, PolicyEvaluationResult
from app.services.policy_factory import PolicyEngineConfigurationError, create_policy_engine, get_policy_engine
from app.services.policy_testing import PolicyTester


class FalseyDenyEngine:
    """Test adapter whose truthiness must not trigger a mock fallback."""

    def __init__(self):
        self.evaluations = []

    def __bool__(self):
        return False

    def is_valid_domain(self, domain):
        return domain == "parking"

    def is_valid_operation(self, domain, operation):
        return domain == "parking" and operation == "read"

    def evaluate(self, identity, action):
        self.evaluations.append((identity, action))
        return PolicyEvaluationResult(Decision.DENY, "INJECTED_DENY", "Blocked by test adapter")


@pytest.mark.parametrize("service_type", [GatewayService, PolicyTester])
def test_explicit_falsey_adapter_is_preserved(monkeypatch, service_type):
    provider = Mock(side_effect=AssertionError("An explicit adapter must not resolve a default"))
    monkeypatch.setattr(f"{service_type.__module__}.get_policy_engine", provider)
    engine = FalseyDenyEngine()
    assert service_type(policy_engine=engine).policy_engine is engine
    provider.assert_not_called()


def test_default_services_share_one_selected_adapter():
    engine = get_gateway_service().policy_engine
    assert engine is get_policy_engine()
    assert get_policy_tester().policy_engine is engine
    assert GatewayService().policy_engine is engine
    assert PolicyTester().policy_engine is engine


def test_custom_adapter_can_be_shared_through_existing_fastapi_overrides(monkeypatch):
    engine = FalseyDenyEngine()
    gateway = GatewayService(policy_engine=engine)
    tester = PolicyTester(policy_engine=engine)
    before = deepcopy(gateway.parking_service.records)
    monkeypatch.setitem(app.dependency_overrides, get_gateway_service, lambda: gateway)
    monkeypatch.setitem(app.dependency_overrides, get_policy_tester, lambda: tester)
    case = PolicyTester.get_default_cases()[0]
    request = EvaluationRequest(request_id="req-shared-adapter", action=case.action)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/requests/evaluate", json=request.model_dump(),
            headers={"Authorization": "Bearer token_operator_north"},
        )
        assert response.status_code == 200
        assert response.json()["reason_code"] == "INJECTED_DENY"
        assert response.json()["decision"] == "deny"
        assert response.json()["executed"] is False
        audit_count = len(gateway.audit_service.get_events())
        report = client.post("/api/v1/policies/test")

    assert report.status_code == 200
    data = report.json()
    assert data["all_passed"] is False
    assert all(result["actual_reason_code"] == "INJECTED_DENY" for result in data["results"])
    assert len(engine.evaluations) == 1 + data["total"]
    assert gateway.parking_service.call_count == 0
    assert gateway.parking_service.records == before
    assert len(gateway.audit_service.get_events()) == audit_count == 1


def test_dev_mock_can_be_selected_explicitly(monkeypatch):
    monkeypatch.setenv("CHRONOSHIELD_POLICY_ENGINE", "REAL")
    assert isinstance(create_policy_engine("DEV_MOCK"), DevMockPolicyEngine)


def test_real_can_be_selected_explicitly(monkeypatch):
    monkeypatch.setenv("CHRONOSHIELD_POLICY_ENGINE", "DEV_MOCK")
    mock_constructor = Mock(side_effect=AssertionError("Mock fallback must not happen"))
    monkeypatch.setattr(policy_factory, "DevMockPolicyEngine", mock_constructor)
    engine = create_policy_engine("REAL")
    assert isinstance(engine, FormalPolicyEngineAdapter)
    mock_constructor.assert_not_called()


@pytest.mark.parametrize("mode", [None, "DEV_MOCK"])
def test_environment_selection_and_development_default(monkeypatch, mode):
    if mode is None:
        monkeypatch.delenv("CHRONOSHIELD_POLICY_ENGINE", raising=False)
    else:
        monkeypatch.setenv("CHRONOSHIELD_POLICY_ENGINE", mode)
    assert isinstance(create_policy_engine(), DevMockPolicyEngine)


def test_environment_selection_real(monkeypatch):
    monkeypatch.setenv("CHRONOSHIELD_POLICY_ENGINE", "REAL")
    assert isinstance(create_policy_engine(), FormalPolicyEngineAdapter)


@pytest.mark.parametrize("mode", ["UNKNOWN", "", "dev_mock", " DEV_MOCK", "DEV_MOCK ", "real", " REAL", "REAL ", " \t"])
def test_invalid_or_unavailable_mode_never_constructs_mock(monkeypatch, mode):
    mock_constructor = Mock(side_effect=AssertionError("Mock fallback must not happen"))
    real_constructor = Mock(side_effect=AssertionError("Real fallback must not happen"))
    monkeypatch.setattr(policy_factory, "DevMockPolicyEngine", mock_constructor)
    monkeypatch.setattr(policy_factory, "FormalPolicyEngineAdapter", real_constructor)
    message = "Invalid CHRONOSHIELD_POLICY_ENGINE"
    with pytest.raises(PolicyEngineConfigurationError, match=message):
        create_policy_engine(mode)
    monkeypatch.setenv("CHRONOSHIELD_POLICY_ENGINE", mode)
    with pytest.raises(PolicyEngineConfigurationError, match=message):
        create_policy_engine()
    mock_constructor.assert_not_called()
    real_constructor.assert_not_called()


def test_mock_initialization_error_is_sanitized_without_retry(monkeypatch):
    constructor = Mock(side_effect=RuntimeError("synthetic-private-initialization-detail"))
    monkeypatch.setattr(policy_factory, "DevMockPolicyEngine", constructor)
    with pytest.raises(PolicyEngineConfigurationError, match="initialization failed") as error:
        create_policy_engine("DEV_MOCK")
    constructor.assert_called_once_with()
    assert "synthetic-private-initialization-detail" not in str(error.value)
    assert error.value.__suppress_context__ is True


def test_real_initialization_error_is_sanitized_without_fallback(monkeypatch):
    real_constructor = Mock(side_effect=RuntimeError("synthetic-real-engine-failure"))
    mock_constructor = Mock(side_effect=AssertionError("Mock fallback must not happen"))
    monkeypatch.setattr(policy_factory, "FormalPolicyEngineAdapter", real_constructor)
    monkeypatch.setattr(policy_factory, "DevMockPolicyEngine", mock_constructor)
    with pytest.raises(PolicyEngineConfigurationError, match="REAL policy engine initialization failed") as error:
        create_policy_engine("REAL")
    real_constructor.assert_called_once_with()
    mock_constructor.assert_not_called()
    assert "synthetic-real-engine-failure" not in str(error.value)
    assert error.value.__suppress_context__ is True


@pytest.mark.parametrize("service_type", [GatewayService, PolicyTester])
def test_service_initialization_does_not_hide_configuration_failure(monkeypatch, service_type):
    provider = Mock(side_effect=PolicyEngineConfigurationError("Selected adapter is unavailable"))
    monkeypatch.setattr(f"{service_type.__module__}.get_policy_engine", provider)
    with pytest.raises(PolicyEngineConfigurationError, match="Selected adapter is unavailable"):
        service_type()
    provider.assert_called_once_with()


def test_runtime_and_policy_testing_use_the_selected_adapter(monkeypatch):
    engine = get_policy_engine()
    evaluate = Mock(wraps=engine.evaluate)
    monkeypatch.setattr(engine, "evaluate", evaluate)
    gateway = get_gateway_service()
    before = deepcopy(gateway.parking_service.records)
    calls_before = gateway.parking_service.call_count
    audits_before = len(gateway.audit_service.get_events())
    case = PolicyTester.get_default_cases()[0]
    action = case.action.model_copy(update={"resource_district_id": "district_south"})
    request = EvaluationRequest(request_id="req-selected-adapter", action=action)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/requests/evaluate", json=request.model_dump(),
            headers={"Authorization": "Bearer token_operator_north"},
        )
        assert response.status_code == 200
        assert response.json()["decision"] == "allow"
        assert response.json()["executed"] is True
        assert evaluate.call_count == 1
        assert evaluate.call_args.args[1].resource_district_id == "district_north"
        report = client.post("/api/v1/policies/test")

    assert report.status_code == 200
    assert report.json()["all_passed"] is True
    assert evaluate.call_count == 1 + report.json()["total"]
    assert gateway.parking_service.call_count == calls_before + 1
    assert len(gateway.audit_service.get_events()) == audits_before + 1
    assert gateway.parking_service.records == before


def _run_fresh_process(code, mode):
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "CHRONOSHIELD_POLICY_ENGINE": mode},
        capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize("mode", ["DEV_MOCK", "REAL", "UNKNOWN", ""])
def test_application_initialization_respects_mode_and_constructs_one_adapter(mode):
    result = _run_fresh_process("""
from unittest.mock import Mock
from app.services import policy_factory
import os
mode = os.environ.get("CHRONOSHIELD_POLICY_ENGINE")
from app.main import app
from app.api.gateway import get_gateway_service
from app.api.policies import get_policy_tester
from app.services import GatewayService, PolicyTester, DevMockPolicyEngine, FormalPolicyEngineAdapter
engine = policy_factory.get_policy_engine()
if mode == "REAL":
    assert isinstance(engine, FormalPolicyEngineAdapter)
else:
    assert isinstance(engine, DevMockPolicyEngine)
assert get_gateway_service().policy_engine is engine
assert get_policy_tester().policy_engine is engine
assert GatewayService().policy_engine is engine
assert PolicyTester().policy_engine is engine
print(f"one shared {mode} adapter")
""", mode)
    if mode in ("DEV_MOCK", "REAL"):
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == f"one shared {mode} adapter"
    else:
        assert result.returncode != 0
        assert result.stdout == ""
        assert "PolicyEngineConfigurationError" in result.stderr
        assert "Invalid CHRONOSHIELD_POLICY_ENGINE" in result.stderr



def test_application_initialization_failure_aborts_without_leaking_details():
    result = _run_fresh_process("""
from app.services import policy_factory
def fail_initialization():
    raise RuntimeError("synthetic-private-initialization-detail")
policy_factory.DevMockPolicyEngine = fail_initialization
from app.main import app
print("unexpected application startup")
""", "DEV_MOCK")
    assert result.returncode != 0
    assert result.stdout == ""
    assert "PolicyEngineConfigurationError" in result.stderr
    assert "initialization failed" in result.stderr
    assert "synthetic-private-initialization-detail" not in result.stderr
