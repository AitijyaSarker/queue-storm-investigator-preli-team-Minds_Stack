"""FastAPI entrypoint."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.middleware import error_handler
from app.schemas.request import AnalyzeRequest
from app.services.investigator import investigate

log = get_logger("app")

app = FastAPI(
    title="QueueStorm Investigator",
    version="1.0.0",
    description="AI/API SupportOps copilot for digital finance complaint tickets.",
)
error_handler.register(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze-ticket")
async def analyze_ticket(req: Request) -> JSONResponse:
    # Defensive JSON parsing — keep 400 semantics even if client sends invalid JSON.
    try:
        raw = await req.body()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read request body.",
        )

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is empty.",
        )

    try:
        import json as _json
        payload = _json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON in request body.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be a JSON object.",
        )

    try:
        body = AnalyzeRequest.model_validate(payload)
    except RequestValidationError:
        # Let the global handler format this consistently.
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "invalid_request", "message": str(exc)[:300]},
        )

    if not body.complaint.strip():
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "unprocessable_entity",
                "message": "complaint must not be empty or whitespace.",
            },
        )

    result = investigate(body)
    return JSONResponse(status_code=status.HTTP_200_OK, content=result.model_dump(mode="json"))


@app.on_event("startup")
async def _startup() -> None:
    log.info("queue_storm_investigator_ready port=%s", settings.port)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, log_level=settings.log_level.lower())
