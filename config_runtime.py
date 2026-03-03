from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_json_file(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@lru_cache(maxsize=1)
def load_config() -> Dict[str, Any]:
    """
    Load merged runtime config.
    Priority: config.json < config.local.json < CONFIG_FILE (if set).
    """
    cfg: Dict[str, Any] = {}
    cfg = _deep_merge(cfg, _load_json_file(ROOT_DIR / "config.json"))
    cfg = _deep_merge(cfg, _load_json_file(ROOT_DIR / "config.local.json"))

    custom = os.environ.get("CONFIG_FILE", "").strip()
    if custom:
        cfg = _deep_merge(cfg, _load_json_file(Path(custom)))
    return cfg


def get_cfg(path: str, default: Any = None) -> Any:
    cur: Any = load_config()
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

