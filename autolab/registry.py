from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from .common import REGISTRY_FILE, ROOT_DIR, VERSIONS_DIR, ensure_dirs, read_json, write_json


def _default_registry() -> Dict[str, Any]:
    return {
        "champion": "cpp_v3_unified_online",
        "versions": [
            {
                "id": "cpp_v3_unified_online",
                "kind": "cpp_protocol_exe",
                "exe": str(ROOT_DIR / "Game1" / "antgame_ai_cpp" / "v3" / "ai_v3"),
                "src": str(ROOT_DIR / "Game1" / "antgame_ai_cpp" / "v3" / "ai_v3.cpp"),
                "enabled": True,
                "anchor": False,
                "notes": "Unified pure C++ protocol AI; current local evaluation mainline",
            },
            {
                "id": "greedy",
                "kind": "antgame_py",
                "name": "greedy",
                "enabled": True,
                "anchor": True,
                "notes": "Ant-Game built-in greedy baseline",
            },
            {
                "id": "random",
                "kind": "antgame_py",
                "name": "random",
                "enabled": True,
                "anchor": True,
                "notes": "Ant-Game built-in random baseline",
            },
            {
                "id": "example",
                "kind": "antgame_py",
                "name": "example",
                "enabled": True,
                "anchor": False,
                "notes": "Ant-Game example baseline",
            },
        ],
    }


def ensure_registry() -> Dict[str, Any]:
    ensure_dirs()
    if not REGISTRY_FILE.is_file():
        data = _default_registry()
        write_json(REGISTRY_FILE, data)
        return data
    data = read_json(REGISTRY_FILE, default=_default_registry())
    if "versions" not in data or not isinstance(data["versions"], list):
        data = _default_registry()
        write_json(REGISTRY_FILE, data)
    return data


def load_registry() -> Dict[str, Any]:
    return ensure_registry()


def save_registry(reg: Dict[str, Any]) -> None:
    write_json(REGISTRY_FILE, reg)


def list_versions(enabled_only: bool = False) -> List[Dict[str, Any]]:
    reg = load_registry()
    versions = reg.get("versions", [])
    if not isinstance(versions, list):
        return []
    out = [v for v in versions if isinstance(v, dict)]
    if enabled_only:
        out = [v for v in out if bool(v.get("enabled", True))]
    return out


def get_version(version_id: str) -> Dict[str, Any] | None:
    for v in list_versions(enabled_only=False):
        if str(v.get("id", "")) == version_id:
            return v
    return None


def upsert_version(entry: Dict[str, Any]) -> None:
    reg = load_registry()
    versions = reg.get("versions", [])
    if not isinstance(versions, list):
        versions = []
    vid = str(entry.get("id", "")).strip()
    if not vid:
        raise ValueError("version id is required")
    replaced = False
    for i, v in enumerate(versions):
        if isinstance(v, dict) and str(v.get("id", "")) == vid:
            versions[i] = entry
            replaced = True
            break
    if not replaced:
        versions.append(entry)
    reg["versions"] = versions
    save_registry(reg)


def set_champion(version_id: str) -> None:
    if get_version(version_id) is None:
        raise ValueError(f"version not found: {version_id}")
    reg = load_registry()
    reg["champion"] = version_id
    save_registry(reg)


def snapshot_cpp_version(
    version_id: str,
    src_file: Path,
    exe_file: Path,
    notes: str = "",
    enabled: bool = True,
    anchor: bool = False,
) -> Dict[str, Any]:
    if not src_file.is_file():
        raise FileNotFoundError(f"source file not found: {src_file}")
    if not exe_file.is_file():
        raise FileNotFoundError(f"exe file not found: {exe_file}")

    dst_root = VERSIONS_DIR / version_id
    src_dir = dst_root / "src"
    bin_dir = dst_root / "bin"
    src_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    dst_src = src_dir / src_file.name
    dst_exe = bin_dir / exe_file.name
    shutil.copy2(src_file, dst_src)
    shutil.copy2(exe_file, dst_exe)
    dst_exe.chmod(0o755)

    entry = {
        "id": version_id,
        "kind": "cpp_exe",
        "exe": str(dst_exe),
        "src": str(dst_src),
        "enabled": bool(enabled),
        "anchor": bool(anchor),
        "notes": notes,
    }
    upsert_version(entry)
    return entry
