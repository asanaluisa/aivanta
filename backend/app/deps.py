"""FastAPI dependencies: authentication, permissions, dataset and filters."""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from aivanta_core import analytics as A
from aivanta_core.domain import Dataset
from aivanta_core.serialize import clamp_filters, parse_filters

from .config import Settings, get_settings
from .db import get_db
from .errors import ApiError
from .repository import load_dataset
from .security import InvalidToken, Principal, decode_token

_bearer = HTTPBearer(auto_error=False)


def current_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise ApiError(401, "not_authenticated")
    try:
        return decode_token(creds.credentials, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    except InvalidToken:
        raise ApiError(401, "invalid_token") from None


def require(permission: str) -> Callable[[Principal], Principal]:
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.can(permission):
            raise ApiError(403, "forbidden", {"permission": permission})
        return principal

    return dependency


def org_dataset(principal: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> Dataset:
    """The caller's organization dataset — the only data any read endpoint can see."""
    return load_dataset(db, principal.organization_id)


def request_filters(request: Request, ds: Dataset = Depends(org_dataset)) -> A.Filters:
    q = request.query_params
    try:
        f = parse_filters({k: q.get(k) for k in ("start", "end", "departments", "providers", "models",
                                                  "use_cases")})
    except ValueError as exc:
        raise ApiError(422, "invalid_filters", {"detail": str(exc)}) from None
    return clamp_filters(ds, f)
