from __future__ import annotations

from typing import Dict, List, Optional

import tiktoken


def _encoding_for_model(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def estimate_text_tokens(model: str, text: str) -> int:
    enc = _encoding_for_model(model)
    return len(enc.encode(text or ""))


def estimate_chat_tokens(model: str, messages: List[Dict[str, str]]) -> Optional[int]:
    """
    Best-effort chat token estimation.
    This is intentionally conservative and marks token_source="estimated".
    """
    enc = _encoding_for_model(model)

    # Common cookbook-ish defaults; unknown models get a reasonable fallback.
    tokens_per_message = 3
    tokens_per_name = 1

    total = 0
    for m in messages:
        total += tokens_per_message
        total += len(enc.encode(m.get("role", "")))
        total += len(enc.encode(m.get("content", "")))
        if m.get("name"):
            total += tokens_per_name
            total += len(enc.encode(m.get("name", "")))

    total += 3  # assistant priming
    return total
