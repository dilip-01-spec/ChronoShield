from typing import Optional
from fastapi import APIRouter, Depends, Header
from app.schemas import ApiError, EvaluationRequest, EvaluationResponse
from app.services import GatewayService
from app.services.policy_factory import get_policy_engine

router = APIRouter(prefix="/api/v1/requests", tags=["Gateway"])

_default_gateway = GatewayService(policy_engine=get_policy_engine())


def get_gateway_service() -> GatewayService:
    return _default_gateway


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    responses={
        400: {
            "model": ApiError,
            "description": "Validation error or unknown domain/operation",
        },
    },
)
async def evaluate_request(
    request: EvaluationRequest,
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None),
    gateway: GatewayService = Depends(get_gateway_service),
) -> EvaluationResponse:
    """Evaluate an infrastructure action request against security policies and dispatch if authorized."""
    auth_token = x_auth_token or authorization
    return gateway.evaluate(request, auth_token=auth_token)
