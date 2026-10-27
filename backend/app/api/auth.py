from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as M
from ..config import Settings, get_settings
from ..db import get_db
from ..deps import current_principal
from ..errors import ApiError
from ..security import ROLE_PERMISSIONS, Principal, issue_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class MeOut(BaseModel):
    email: str | None
    display_name: str | None
    role: str
    permissions: list[str]
    preferred_locale: str
    organization: str
    organization_name: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeOut


class MePatch(BaseModel):
    preferred_locale: Literal["en", "es"]


def _me(db: Session, user: M.User) -> MeOut:
    org = db.get(M.Organization, user.organization_id)
    return MeOut(email=user.email, display_name=user.display_name, role=user.role,
                 permissions=sorted(ROLE_PERMISSIONS.get(user.role, [])),
                 preferred_locale=user.preferred_locale, organization=org.key, organization_name=org.name)


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = db.scalar(select(M.User).where(func.lower(M.User.email) == body.email.strip().lower()))
    if user is None or not user.is_active or user.role == "member" \
            or not verify_password(body.password, user.password_hash):
        raise ApiError(401, "invalid_credentials")
    token = issue_token(Principal(user.id, user.organization_id, user.role), settings.jwt_secret,
                        algorithm=settings.jwt_algorithm, minutes=settings.jwt_expiry_minutes)
    return LoginOut(access_token=token, user=_me(db, user))


@router.get("/me", response_model=MeOut)
def me(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user = db.get(M.User, p.user_id)
    if user is None or user.organization_id != p.organization_id:
        raise ApiError(401, "invalid_token")
    return _me(db, user)


@router.patch("/me", response_model=MeOut)
def update_me(body: MePatch, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user = db.get(M.User, p.user_id)
    if user is None or user.organization_id != p.organization_id:
        raise ApiError(401, "invalid_token")
    user.preferred_locale = body.preferred_locale
    db.commit()
    return _me(db, user)
