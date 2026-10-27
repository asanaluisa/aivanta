from fastapi import APIRouter

from . import admin, analytics, auth, reports

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(analytics.router)
api_router.include_router(admin.router)
api_router.include_router(reports.router)
