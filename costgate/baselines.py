from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from costgate.jsonutil import dumps_json


class BaselineFamilyMismatchError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash_yaml(path: Path) -> str:
    """
    Stable hash for YAML content: parse then re-dump with sorted keys.
    """
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    canon = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(canon)


def canonical_hash_json_obj(obj: Any) -> str:
    canon = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(canon)


def safe_model_for_path(model: str) -> str:
    return model.replace("/", "_").replace(":", "_").replace(" ", "_")


def build_baseline_key(
    suite_hash: str,
    provider: str,
    resolved_model: str,
    params_hash: str,
    rate_card_hash: str,
    artifact_schema: str | None = None,
    tokenizer: str | None = None,
) -> str:
    # Keep it deterministic and readable, but still unique.
    parts = [
        suite_hash,
        provider,
        safe_model_for_path(resolved_model),
        params_hash,
        rate_card_hash,
    ]
    if tokenizer:
        parts.append(safe_model_for_path(tokenizer))
    if artifact_schema:
        parts.append(safe_model_for_path(artifact_schema))
    return "__".join(parts)


def baseline_path_for_key(baselines_root: Path, baseline_key: str) -> Path:
    return baselines_root / baseline_key / "baseline.json"


def save_baseline(
    results: Dict[str, Any], baselines_root: Path = Path(".costgate/baselines")
) -> Path:
    baseline_key = results["meta"]["baseline_key"]
    path = baseline_path_for_key(baselines_root, baseline_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_json(results, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_baseline_json(baselines_root: Path) -> Optional[Path]:
    if not baselines_root.exists():
        return None
    best: Optional[Path] = None
    best_mtime = -1.0
    for p in baselines_root.glob("*/baseline.json"):
        try:
            m = p.stat().st_mtime
        except Exception:
            continue
        if m > best_mtime:
            best_mtime = m
            best = p
    return best


def assert_same_family(baseline: Dict[str, Any], pr: Dict[str, Any]) -> None:
    b = baseline.get("meta", {})
    p = pr.get("meta", {})
    keys = ["suite_hash", "provider", "resolved_model", "params_hash", "rate_card_hash"]
    if b.get("schema_version") or p.get("schema_version"):
        keys.append("schema_version")
    if b.get("tokenizer") or p.get("tokenizer"):
        keys.append("tokenizer")
    mismatches = []
    for k in keys:
        if b.get(k) != p.get(k):
            mismatches.append((k, b.get(k), p.get(k)))
    if mismatches:
        lines = ["Baseline family mismatch:"]
        for k, bv, pv in mismatches:
            lines.append(f"- {k}: baseline={bv} pr={pv}")
        lines.append("Refusing compare unless --allow-family-mismatch is set.")
        raise BaselineFamilyMismatchError("\n".join(lines))
