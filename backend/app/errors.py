"""Error responses with language-neutral codes.

The API never returns user-facing prose: it returns ``{"error": {"code": ...}}``
and the frontend shows the translation for ``error.<code>``.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, details: Optional[dict[str, Any]] = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.details = details or {}


def _body(code: str, details: Optional[dict] = None) -> dict:
    return {"error": {"code": code, "details": details or {}}}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(_body(exc.code, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e.get("loc", [])) for e in exc.errors()]
        return JSONResponse(_body("validation_error", {"fields": fields}), status_code=422)

    @app.exception_handler(LookupError)
    async def _not_found(_: Request, exc: LookupError):
        return JSONResponse(_body("not_found"), status_code=404)
