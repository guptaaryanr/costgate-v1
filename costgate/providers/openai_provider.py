from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import OpenAI
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    RateLimitError,
)

from costgate.providers.base import (
    Provider,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
)
from costgate.token_count import estimate_chat_tokens


@dataclass(frozen=True)
class OpenAIProviderConfig:
    max_retries: int = 6
    backoff_base_s: float = 0.5
    backoff_max_s: float = 8.0


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(
        self,
        cfg: Optional[OpenAIProviderConfig] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        if config:
            cfg = OpenAIProviderConfig(
                max_retries=int(config.get("max_retries", OpenAIProviderConfig.max_retries)),
                backoff_base_s=float(
                    config.get("backoff_base_s", OpenAIProviderConfig.backoff_base_s)
                ),
                backoff_max_s=float(
                    config.get("backoff_max_s", OpenAIProviderConfig.backoff_max_s)
                ),
            )
        self.cfg = cfg or OpenAIProviderConfig()
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set.")
        self.client = OpenAI(api_key=api_key)

    def _sleep_backoff(self, attempt: int) -> None:
        # deterministic "jitter": 0.9, 1.0, 1.1 repeating
        jitter = 1.0 + 0.1 * ((attempt % 3) - 1)
        delay = (
            min(self.cfg.backoff_max_s, self.cfg.backoff_base_s * (2**attempt)) * jitter
        )
        time.sleep(delay)

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        retry_count = 0
        start = time.perf_counter()
        last_err: Optional[str] = None

        for attempt in range(self.cfg.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=request.model,
                    messages=request.messages,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    max_tokens=request.max_output_tokens,
                    timeout=request.timeout_s,
                )

                latency_ms = (time.perf_counter() - start) * 1000.0

                text = ""
                if (
                    resp.choices
                    and resp.choices[0].message
                    and resp.choices[0].message.content
                ):
                    text = resp.choices[0].message.content

                resolved_model = getattr(resp, "model", None) or request.model

                usage = getattr(resp, "usage", None)
                if usage and getattr(usage, "prompt_tokens", None) is not None:
                    input_tokens = int(usage.prompt_tokens)
                    output_tokens = int(getattr(usage, "completion_tokens", 0))
                    total_tokens = int(
                        getattr(usage, "total_tokens", input_tokens + output_tokens)
                    )
                    token_source = "api"
                else:
                    # Estimate tokens locally and mark source.
                    input_tokens = estimate_chat_tokens(request.model, request.messages)
                    output_tokens = estimate_chat_tokens(
                        request.model, [{"role": "assistant", "content": text}]
                    )
                    total_tokens = (input_tokens or 0) + (output_tokens or 0)
                    token_source = "estimated"

                return ProviderResponse(
                    text=text,
                    resolved_model=resolved_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    token_source=token_source,
                    latency_ms=latency_ms,
                    retry_count=retry_count,
                    success=True,
                    error=None,
                )

            except (RateLimitError, APITimeoutError, APIConnectionError, APIError) as e:
                last_err = f"{type(e).__name__}: {e}"
                if attempt >= self.cfg.max_retries:
                    break
                retry_count += 1
                self._sleep_backoff(attempt)
                continue
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                break

        latency_ms = (time.perf_counter() - start) * 1000.0
        return ProviderResponse(
            text="",
            resolved_model=request.model,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            token_source="api",
            latency_ms=latency_ms,
            retry_count=retry_count,
            success=False,
            error=last_err or "Unknown error",
        )
