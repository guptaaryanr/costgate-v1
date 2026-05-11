from __future__ import annotations

import json
import math
from typing import Any


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, float):
        if math.isnan(obj):
            return "nan"
        if math.isinf(obj):
            return "inf" if obj > 0 else "-inf"
        return obj
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, tuple):
        return [to_jsonable(v) for v in obj]
    return obj


def dumps_json(obj: Any, **kwargs: Any) -> str:
    return json.dumps(to_jsonable(obj), allow_nan=False, **kwargs)


def coerce_float(value: Any) -> float:
    if value is None:
        return float("nan")
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "nan":
            return float("nan")
        if lowered in {"inf", "+inf", "infinity", "+infinity"}:
            return float("inf")
        if lowered in {"-inf", "-infinity"}:
            return float("-inf")
    try:
        return float(value)
    except Exception:
        return float("nan")
