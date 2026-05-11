from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from costgate.providers.base import Provider, ProviderRequest, ProviderResponse


class ReplayProvider(Provider):
    name = "replay"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.records = self._load_records(self.config)
        self.by_key: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.by_task: Dict[str, List[Dict[str, Any]]] = {}
        for record in self.records:
            task_id = str(record.get("task_id") or record.get("test_id") or "")
            repeat = int(record.get("repeat", record.get("repeat_index", 0)) or 0)
            if task_id:
                self.by_key[(task_id, repeat)] = record
                self.by_task.setdefault(task_id, []).append(record)

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        extra = request.extra or {}
        task_id = str(extra.get("task_id") or "")
        repeat_index = int(extra.get("repeat_index") or 0)
        record = self.by_key.get((task_id, repeat_index))
        if record is None:
            task_records = self.by_task.get(task_id, [])
            if task_records:
                record = task_records[repeat_index % len(task_records)]
        if record is None:
            return ProviderResponse(
                text="",
                resolved_model=request.model,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                token_source="replay",
                latency_ms=0.0,
                retry_count=0,
                success=False,
                error=f"No replay fixture for task_id={task_id!r} repeat={repeat_index}",
            )

        success = bool(record.get("api_success", record.get("success", True)))
        error = record.get("error")
        if error:
            success = False
        text = str(record.get("output_text", record.get("text", "")))
        input_tokens = _optional_int(record.get("input_tokens"))
        output_tokens = _optional_int(record.get("output_tokens"))
        total_tokens = _optional_int(record.get("total_tokens"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        return ProviderResponse(
            text=text if success else "",
            resolved_model=str(record.get("resolved_model", record.get("model", request.model))),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            token_source=str(record.get("token_source", "replay")),
            latency_ms=float(record.get("latency_ms", 0.0) or 0.0),
            retry_count=int(record.get("retry_count", 0) or 0),
            success=success,
            error=str(error) if error else None,
        )

    @staticmethod
    def _load_records(config: Dict[str, Any]) -> List[Dict[str, Any]]:
        obj: Any = config
        path = (
            config.get("fixture_path")
            or config.get("artifact_path")
            or config.get("path")
        )
        if path:
            p = Path(str(path))
            text = p.read_text(encoding="utf-8")
            if p.suffix.lower() in {".yaml", ".yml"}:
                obj = yaml.safe_load(text)
            else:
                obj = json.loads(text)

        if isinstance(obj, dict):
            for key in ("responses", "calls", "per_call_runs", "tasks"):
                value = obj.get(key)
                if isinstance(value, list):
                    return [r for r in value if isinstance(r, dict)]
        if isinstance(obj, list):
            return [r for r in obj if isinstance(r, dict)]
        return []


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
