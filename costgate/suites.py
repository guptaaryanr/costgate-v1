from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from costgate.validation import ValidationError


@dataclass(frozen=True)
class SuiteTest:
    id: str
    task_type: str
    system: str
    user: str
    expected: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class Suite:
    tests: List[SuiteTest]
    provider_config: Optional[Dict[str, Any]] = None


def load_and_validate_suite(path: Path) -> Suite:
    try:
        obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValidationError(f"Failed to parse suite YAML: {path}: {e}") from e

    if not isinstance(obj, dict) or "tests" not in obj:
        raise ValidationError("Suite must be a mapping with a top-level 'tests' list.")
    tests = obj.get("tests")
    if not isinstance(tests, list) or not tests:
        raise ValidationError("'tests' must be a non-empty list.")

    provider_config = obj.get("provider_config")
    if provider_config is not None and not isinstance(provider_config, dict):
        raise ValidationError("provider_config must be a mapping when supplied.")

    from costgate.validators import validate_expected_config

    seen = set()
    parsed: List[SuiteTest] = []
    for i, t in enumerate(tests):
        if not isinstance(t, dict):
            raise ValidationError(f"Test #{i} must be a mapping.")
        tid = t.get("id")
        if not isinstance(tid, str) or not tid.strip():
            raise ValidationError(f"Test #{i} missing non-empty 'id'.")
        if tid in seen:
            raise ValidationError(f"Duplicate test id: {tid}")
        seen.add(tid)

        task_type = t.get("task_type")
        if not isinstance(task_type, str) or not task_type.strip():
            raise ValidationError(f"Test {tid} missing non-empty 'task_type'.")

        system = t.get("system")
        user = t.get("user")
        if not isinstance(system, str):
            raise ValidationError(f"Test {tid} missing string 'system'.")
        if not isinstance(user, str):
            raise ValidationError(f"Test {tid} missing string 'user'.")

        expected = t.get("expected")
        validate_expected_config(expected, tid)

        meta = {
            k: v
            for k, v in t.items()
            if k not in {"id", "task_type", "system", "user", "expected"}
        }
        parsed.append(
            SuiteTest(
                id=tid,
                task_type=task_type,
                system=system,
                user=user,
                expected=expected,
                meta=meta or None,
            )
        )

    return Suite(tests=parsed, provider_config=provider_config)
