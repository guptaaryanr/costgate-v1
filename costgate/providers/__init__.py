from __future__ import annotations

import importlib
from typing import Any, Dict, Type

from costgate.providers.base import Provider, ProviderError

_PROVIDER_ENTRYPOINTS = {
    "mock": "costgate.providers.mock_provider:MockProvider",
    "openai": "costgate.providers.openai_provider:OpenAIProvider",
    "replay": "costgate.providers.replay_provider:ReplayProvider",
}


def available_providers() -> list[str]:
    return sorted(_PROVIDER_ENTRYPOINTS)


def register_provider(name: str, entrypoint: str) -> None:
    if ":" not in entrypoint:
        raise ProviderError("Provider entrypoint must be 'module:ClassName'.")
    _PROVIDER_ENTRYPOINTS[name] = entrypoint


def get_provider(name: str, config: Dict[str, Any] | None = None) -> Provider:
    entrypoint = _PROVIDER_ENTRYPOINTS.get(name)
    if entrypoint is None:
        supported = ", ".join(available_providers())
        raise ProviderError(f"Unknown provider: {name}. Supported: {supported}")

    module_name, class_name = entrypoint.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        cls: Type[Provider] = getattr(module, class_name)
    except Exception as e:
        raise ProviderError(f"Failed to load provider '{name}': {e}") from e

    try:
        return cls(config=config or {})
    except TypeError:
        return cls()
