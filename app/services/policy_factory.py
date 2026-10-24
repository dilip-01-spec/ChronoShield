import os
from functools import lru_cache
from typing import Optional

from app.services.policy import (
    DevMockPolicyEngine,
    FormalPolicyEngineAdapter,
    PolicyEngineAdapter,
)


class PolicyEngineConfigurationError(RuntimeError):
    """Policy selection or initialization failed; the application must not start."""


def create_policy_engine(mode: Optional[str] = None) -> PolicyEngineAdapter:
    """Construct an adapter without falling back from an invalid selection."""
    selected_mode = mode if mode is not None else os.getenv("CHRONOSHIELD_POLICY_ENGINE", "DEV_MOCK")
    if selected_mode == "REAL":
        try:
            return FormalPolicyEngineAdapter()
        except Exception:
            # Initialization errors may contain credentials; never expose their details.
            raise PolicyEngineConfigurationError(
                "REAL policy engine initialization failed; application startup aborted."
            ) from None
    if selected_mode == "DEV_MOCK":
        try:
            return DevMockPolicyEngine()
        except Exception:
            # Initialization errors may contain credentials; never expose their details.
            raise PolicyEngineConfigurationError(
                "DEV_MOCK policy engine initialization failed; application startup aborted."
            ) from None
    raise PolicyEngineConfigurationError(
        "Invalid CHRONOSHIELD_POLICY_ENGINE mode; expected DEV_MOCK or REAL (case-sensitive)."
    )


@lru_cache(maxsize=1)
def get_policy_engine() -> PolicyEngineAdapter:
    """One configured adapter per process; restart to change its configuration."""
    return create_policy_engine()
