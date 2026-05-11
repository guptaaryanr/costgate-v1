from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProviderRequest:
    model: str
    messages: List[Dict[str, str]]  # [{"role": "...", "content": "..."}]
    temperature: float = 0.0
    top_p: float = 1.0
    max_output_tokens: int = 96
    timeout_s: float = 60.0
    extra: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    resolved_model: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    token_source: str  # "api" or "estimated"
    latency_ms: float
    retry_count: int
    success: bool
    error: Optional[str] = None


class ProviderError(RuntimeError):
    pass


class Provider:
    name: str

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError
