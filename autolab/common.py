from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from config_runtime import get_cfg

ROOT_DIR = Path(__file__).resolve().parents[1]
AUTO_DIR = ROOT_DIR / "autolab"
RUNTIME_DIR = AUTO_DIR / "runtime"
VERSIONS_DIR = AUTO_DIR / "versions"
REGISTRY_FILE = AUTO_DIR / "registry.json"
_DEFAULT_ANT_GAME_DIR = (ROOT_DIR / "Game1" / "Ant-Game").resolve()
_CFG_ANT_GAME_DIR = Path(str(get_cfg("paths.ant_game_dir", str(_DEFAULT_ANT_GAME_DIR)))).resolve()
ANT_GAME_DIR = _CFG_ANT_GAME_DIR if _CFG_ANT_GAME_DIR.is_dir() else _DEFAULT_ANT_GAME_DIR
RULESET_TRUTH_FILES = (
    "README.md",
    "SDK/utils/constants.py",
    "SDK/backend/engine.py",
    "tests/test_engine.py",
)


def ensure_dirs() -> None:
    AUTO_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def read_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.is_file():
        return {} if default is None else default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {} if default is None else default


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def current_ruleset_id() -> str:
    sha1 = hashlib.sha1()
    for rel in RULESET_TRUTH_FILES:
        path = ANT_GAME_DIR / rel
        sha1.update(rel.encode("utf-8"))
        sha1.update(b"\0")
        try:
            sha1.update(path.read_bytes())
        except OSError:
            sha1.update(b"<missing>")
        sha1.update(b"\0")
    return sha1.hexdigest()[:12]
