from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from aivanta_core import analytics as A
from aivanta_core import reporting
from aivanta_core.domain import Dataset

from ..deps import org_dataset, request_filters
from ..errors import ApiError

router = APIRouter(prefix="/reports", tags=["reports"])


def _csv(body: str, filename: str) -> Response:
    # BOM so Excel opens UTF-8 (accents in Spanish labels) correctly.
    return Response("﻿" + body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/roi.csv")
def roi_csv(locale: Literal["en", "es"] = Query("en"), ds: Dataset = Depends(org_dataset),
            f: A.Filters = Depends(request_filters)):
    body = reporting.roi_summary_csv(ds, f, locale, datetime.now(timezone.utc))
    name = "aivanta_roi_resumen.csv" if locale == "es" else "aivanta_roi_summary.csv"
    return _csv(body, name)


@router.get("/usage.csv")
def usage_csv(dimension: str = Query("department"), locale: Literal["en", "es"] = Query("en"),
              ds: Dataset = Depends(org_dataset), f: A.Filters = Depends(request_filters)):
    if dimension not in A.DIMENSIONS:
        raise ApiError(404, "unknown_dimension", {"dimension": dimension})
    body = reporting.usage_breakdown_csv(ds, f, dimension, locale, datetime.now(timezone.utc))
    name = f"aivanta_{'uso' if locale == 'es' else 'usage'}_{dimension}.csv"
    return _csv(body, name)
