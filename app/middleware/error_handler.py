"""Centralized error handling — never leak stack traces or secrets."""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger("error")


def register(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        log.info("validation_error: %s", str(exc)[:200])
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "invalid_request",
                "message": "Request body failed schema validation. Please check required fields and types.",
                "details": [
                    {"loc": list(e.get("loc", [])), "msg": str(e.get("msg", ""))}
                    for e in exc.errors()[:5]
                ],
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.error("internal_error: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "message": "An internal error occurred while analyzing the ticket."},
        )
