from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as jsonschema_validate

from costgate.validation import ValidationError


@dataclass(frozen=True)
class ValidatorResult:
    validator_type: str
    passed: bool
    details: Dict[str, Any]
    warning: Optional[str] = None


SUPPORTED_VALIDATORS = {
    "exact",
    "contains",
    "regex",
    "json_schema",
    "numeric_tolerance",
}


def validate_expected_config(expected: Optional[Dict[str, Any]], test_id: str) -> None:
    if expected is None:
        return
    if not isinstance(expected, dict):
        raise ValidationError(f"Test {test_id} expected must be a mapping.")
    validator_type = expected.get("type")
    if validator_type not in SUPPORTED_VALIDATORS:
        raise ValidationError(
            f"Test {test_id} expected.type must be one of {sorted(SUPPORTED_VALIDATORS)}."
        )

    if validator_type in {"exact", "contains"} and "value" not in expected:
        raise ValidationError(f"Test {test_id} expected.{validator_type} requires value.")
    if validator_type == "regex" and "pattern" not in expected:
        raise ValidationError(f"Test {test_id} expected.regex requires pattern.")
    if validator_type == "json_schema" and "schema" not in expected:
        raise ValidationError(f"Test {test_id} expected.json_schema requires schema.")
    if validator_type == "numeric_tolerance" and not (
        "value" in expected or "target" in expected
    ):
        raise ValidationError(
            f"Test {test_id} expected.numeric_tolerance requires value or target."
        )


def validate_output(
    output: str,
    expected: Optional[Dict[str, Any]],
    api_success: bool,
) -> ValidatorResult:
    if not api_success:
        return ValidatorResult(
            validator_type=(str(expected.get("type")) if isinstance(expected, dict) else "none"),
            passed=False,
            details={"reason": "api_error"},
        )

    if expected is None:
        return ValidatorResult(
            validator_type="none",
            passed=True,
            details={"reason": "no_expected_validator"},
            warning=(
                "No expected validator supplied; task_success defaults to api_success. "
                "Success-normalized metrics are weaker for this task."
            ),
        )

    validate_expected_config(expected, test_id="<inline>")
    validator_type = str(expected["type"])

    if validator_type == "exact":
        expected_value = str(expected.get("value", ""))
        actual = output.strip()
        passed = actual == expected_value.strip()
        return ValidatorResult(
            validator_type=validator_type,
            passed=passed,
            details={"expected": expected_value, "actual": actual},
        )

    if validator_type == "contains":
        expected_value = str(expected.get("value", ""))
        case_sensitive = bool(expected.get("case_sensitive", True))
        haystack = output if case_sensitive else output.lower()
        needle = expected_value if case_sensitive else expected_value.lower()
        return ValidatorResult(
            validator_type=validator_type,
            passed=needle in haystack,
            details={"expected_contains": expected_value, "case_sensitive": case_sensitive},
        )

    if validator_type == "regex":
        flags = re.IGNORECASE if bool(expected.get("ignore_case", False)) else 0
        pattern = str(expected.get("pattern", ""))
        try:
            matched = re.search(pattern, output, flags=flags) is not None
        except re.error as e:
            return ValidatorResult(
                validator_type=validator_type,
                passed=False,
                details={"pattern": pattern, "error": str(e)},
            )
        return ValidatorResult(
            validator_type=validator_type,
            passed=matched,
            details={"pattern": pattern, "ignore_case": bool(expected.get("ignore_case", False))},
        )

    if validator_type == "json_schema":
        schema = expected.get("schema")
        try:
            parsed = json.loads(output)
            jsonschema_validate(instance=parsed, schema=schema)
        except json.JSONDecodeError as e:
            return ValidatorResult(
                validator_type=validator_type,
                passed=False,
                details={"reason": "invalid_json", "error": str(e)},
            )
        except JsonSchemaValidationError as e:
            return ValidatorResult(
                validator_type=validator_type,
                passed=False,
                details={"reason": "schema_validation_failed", "error": e.message},
            )
        return ValidatorResult(
            validator_type=validator_type,
            passed=True,
            details={"reason": "schema_validation_passed"},
        )

    if validator_type == "numeric_tolerance":
        target = float(expected.get("value", expected.get("target")))
        actual = _extract_numeric(output, expected.get("path"))
        absolute_tolerance = float(
            expected.get("absolute_tolerance", expected.get("tolerance", 0.0))
        )
        relative_tolerance = float(expected.get("relative_tolerance", 0.0))
        allowed = max(absolute_tolerance, abs(target) * relative_tolerance)
        delta = abs(actual - target) if math.isfinite(actual) else float("inf")
        return ValidatorResult(
            validator_type=validator_type,
            passed=bool(math.isfinite(actual) and delta <= allowed),
            details={
                "target": target,
                "actual": actual,
                "absolute_delta": delta,
                "allowed_delta": allowed,
            },
        )

    return ValidatorResult(
        validator_type=validator_type,
        passed=False,
        details={"reason": "unsupported_validator"},
    )


def _extract_numeric(output: str, path: Any = None) -> float:
    if path:
        try:
            obj = json.loads(output)
            cur: Any = obj
            parts = str(path).split(".")
            for part in parts:
                if isinstance(cur, list):
                    cur = cur[int(part)]
                elif isinstance(cur, dict):
                    cur = cur[part]
                else:
                    return float("nan")
            return float(cur)
        except Exception:
            return float("nan")

    stripped = output.strip()
    try:
        return float(stripped)
    except Exception:
        pass

    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", output)
    if not match:
        return float("nan")
    try:
        return float(match.group(0))
    except Exception:
        return float("nan")
