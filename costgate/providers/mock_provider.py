from __future__ import annotations

from typing import Any, Dict, Optional

from costgate.providers.base import Provider, ProviderRequest, ProviderResponse


class MockProvider(Provider):
    name = "mock"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.default = {
            "output_text": "OK",
            "input_tokens": 10,
            "output_tokens": 5,
            "latency_ms": 25.0,
            "retry_count": 0,
            "token_source": "mock",
            "success": True,
        }
        self.default.update(self.config.get("default", {}) or {})
        self.tasks = self.config.get("tasks", {}) or {}
        self.call_index = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        extra = request.extra or {}
        task_id = str(extra.get("task_id") or "")
        repeat_index = int(extra.get("repeat_index") or 0)
        task_cfg = self._task_config(task_id, repeat_index)

        text = str(task_cfg.get("output_text", task_cfg.get("text", "")))
        success = bool(task_cfg.get("success", True))
        error = task_cfg.get("error")
        if error:
            success = False

        input_tokens = _optional_int(task_cfg.get("input_tokens"))
        output_tokens = _optional_int(task_cfg.get("output_tokens"))
        if input_tokens is None:
            input_tokens = self._estimate_input_tokens(request)
        if output_tokens is None:
            output_tokens = self._estimate_output_tokens(text)
        total_tokens = _optional_int(task_cfg.get("total_tokens"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        self.call_index += 1
        return ProviderResponse(
            text=text if success else "",
            resolved_model=str(task_cfg.get("resolved_model", request.model)),
            input_tokens=input_tokens if success else task_cfg.get("input_tokens"),
            output_tokens=output_tokens if success else task_cfg.get("output_tokens"),
            total_tokens=total_tokens if success else task_cfg.get("total_tokens"),
            token_source=str(task_cfg.get("token_source", "mock")),
            latency_ms=float(task_cfg.get("latency_ms", 25.0)),
            retry_count=int(task_cfg.get("retry_count", 0)),
            success=success,
            error=str(error) if error else None,
        )

    def _task_config(self, task_id: str, repeat_index: int) -> Dict[str, Any]:
        cfg = dict(self.default)
        raw = self.tasks.get(task_id, {}) if isinstance(self.tasks, dict) else {}
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            return cfg

        base = {k: v for k, v in raw.items() if k not in {"repeats", "by_repeat"}}
        cfg.update(base)

        repeats = raw.get("repeats")
        if isinstance(repeats, list) and repeats:
            chosen = repeats[repeat_index % len(repeats)]
            if isinstance(chosen, dict):
                cfg.update(chosen)

        by_repeat = raw.get("by_repeat")
        if isinstance(by_repeat, dict):
            chosen = by_repeat.get(str(repeat_index), by_repeat.get(repeat_index))
            if isinstance(chosen, dict):
                cfg.update(chosen)
        return cfg

    @staticmethod
    def _estimate_input_tokens(request: ProviderRequest) -> int:
        total = 0
        for message in request.messages:
            total += len(str(message.get("content", "")).split())
        return max(total, 1)

    @staticmethod
    def _estimate_output_tokens(text: str) -> int:
        return max(len((text or "").split()), 1)


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
