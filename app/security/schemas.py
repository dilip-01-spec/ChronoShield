
from typing import Any, Literal
from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    domain: Literal[
    "parking",
    "traffic",
    "water",
    "ev_chargers",
    "energy_grid",
]
    action: str
    resource_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class SecurityDecision(BaseModel):
    decision: Literal[
        "ALLOW",
        "DENY",
        "REQUIRES_APPROVAL",
    ]
    reason_code: str
    message: str
