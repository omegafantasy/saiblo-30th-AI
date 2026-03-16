#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autolab.registry import (
    ensure_registry,
    list_versions,
    load_registry,
    set_champion,
    snapshot_cpp_version,
    upsert_version,
)


def cmd_init(_: argparse.Namespace) -> int:
    reg = ensure_registry()
    print(json.dumps(reg, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    reg = load_registry()
    versions = list_versions(enabled_only=args.enabled_only)
    out = {"champion": reg.get("champion", ""), "count": len(versions), "versions": versions}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_set_champion(args: argparse.Namespace) -> int:
    set_champion(args.version_id)
    reg = load_registry()
    print(json.dumps({"champion": reg.get("champion", "")}, ensure_ascii=False, indent=2))
    return 0


def cmd_register_cpp(args: argparse.Namespace) -> int:
    entry = {
        "id": args.version_id,
        "kind": "cpp_exe",
        "exe": str(Path(args.exe).resolve()),
        "src": str(Path(args.src).resolve()) if args.src else "",
        "enabled": not args.disabled,
        "anchor": bool(args.anchor),
        "notes": args.notes,
    }
    upsert_version(entry)
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0


def cmd_register_ant(args: argparse.Namespace) -> int:
    entry = {
        "id": args.version_id,
        "kind": "antgame_py",
        "name": args.name,
        "enabled": not args.disabled,
        "anchor": bool(args.anchor),
        "notes": args.notes,
    }
    upsert_version(entry)
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0


def cmd_snapshot_cpp(args: argparse.Namespace) -> int:
    entry = snapshot_cpp_version(
        version_id=args.version_id,
        src_file=Path(args.src).resolve(),
        exe_file=Path(args.exe).resolve(),
        notes=args.notes,
        enabled=not args.disabled,
        anchor=bool(args.anchor),
    )
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Autolab version management")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="create default registry if missing")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("list", help="list versions")
    sp.add_argument("--enabled-only", action="store_true")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("set-champion", help="set champion version id")
    sp.add_argument("--version-id", required=True)
    sp.set_defaults(func=cmd_set_champion)

    sp = sub.add_parser("register-cpp", help="register a C++ executable version")
    sp.add_argument("--version-id", required=True)
    sp.add_argument("--exe", required=True)
    sp.add_argument("--src", default="")
    sp.add_argument("--notes", default="")
    sp.add_argument("--anchor", action="store_true")
    sp.add_argument("--disabled", action="store_true")
    sp.set_defaults(func=cmd_register_cpp)

    sp = sub.add_parser("register-ant", help="register Ant-Game python AI version")
    sp.add_argument("--version-id", required=True)
    sp.add_argument("--name", required=True, help="AI module suffix (AI/ai_{name}.py)")
    sp.add_argument("--notes", default="")
    sp.add_argument("--anchor", action="store_true")
    sp.add_argument("--disabled", action="store_true")
    sp.set_defaults(func=cmd_register_ant)

    sp = sub.add_parser("snapshot-cpp", help="snapshot src+exe into autolab/versions and register")
    sp.add_argument("--version-id", required=True)
    sp.add_argument("--src", required=True)
    sp.add_argument("--exe", required=True)
    sp.add_argument("--notes", default="")
    sp.add_argument("--anchor", action="store_true")
    sp.add_argument("--disabled", action="store_true")
    sp.set_defaults(func=cmd_snapshot_cpp)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

