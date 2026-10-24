# pyrefly: ignore[missing-import]
import json
# pyrefly: ignore[missing-import]
from fastapi import FastAPI, Request
# pyrefly: ignore[missing-import]
from fastapi.exceptions import RequestValidationError
# pyrefly: ignore[missing-import]
from fastapi.responses import JSONResponse
from app.api import gateway_router, policies_router
from app.schemas import ApiError
from app.services import GatewayError

app = FastAPI(
    title="ChronoShield API",
    version="1.0.0",
)

app.include_router(gateway_router)
app.include_router(policies_router)


@app.exception_handler(GatewayError)
async def gateway_error_handler(request: Request, exc: GatewayError):
    error = ApiError(
        code=exc.code,
        message=exc.message,
        request_id=exc.request_id,
    )
    return JSONResponse(status_code=400, content=error.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    request_id = "unknown"
    try:
        body = await request.body()
        if body:
            parsed = json.loads(body)
            if isinstance(parsed, dict) and "request_id" in parsed:
                request_id = str(parsed["request_id"])
    except Exception:
        pass

    details = "; ".join(
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
        for err in exc.errors()
    )
    error = ApiError(
        code="MALFORMED_INPUT",
        message=f"Request validation failed: {details}",
        request_id=request_id,
    )
    return JSONResponse(status_code=400, content=error.model_dump())


@app.get("/")
async def root():
    return {
        "message": "Welcome to ChronoShield API",
        "docs": "/docs",
    }


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok",
        "service": "chronoshield-api",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    # pyrefly: ignore[missing-import]
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
