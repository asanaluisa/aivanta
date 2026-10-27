"""ASGI entry point: ``uvicorn app.main:app``."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from aivanta_core import __version__

from . import errors
from .api import api_router
from .config import get_settings
from .db import get_engine


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Aivanta API",
        version=__version__,
        description="AI business value and ROI intelligence. Identifiers and enum values are "
                    "language-neutral; the web client localizes them (EN/ES).",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )
    errors.install(app)
    app.include_router(api_router)

    @app.get("/api/health", tags=["health"])
    def health():
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
