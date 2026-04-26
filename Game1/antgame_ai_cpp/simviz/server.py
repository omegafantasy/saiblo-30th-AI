#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import mimetypes
import re
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
GAME1_DIR = REPO_ROOT / "Game1"
ANTGAME_AI_CPP_DIR = GAME1_DIR / "antgame_ai_cpp"
CPP_SDK_DIR = GAME1_DIR / "antgame_cpp_sdk"
INSPECTOR_BIN = CPP_SDK_DIR / "build" / "sdk_lure_inspector"
STATIC_DIR = HERE / "static"
OLD_AI_MAIN = REPO_ROOT / "past_AIs" / "ANTWar-AI" / "main.cpp"
CONSTANTS_PY = GAME1_DIR / "Ant-Game" / "SDK" / "utils" / "constants.py"


def parse_code_map(text: str) -> dict[str, int]:
    match = re.search(r"const int\s+([^;]+);", text, re.S)
    if not match:
        raise ValueError("failed to parse old AI code map")
    mapping: dict[str, int] = {}
    for chunk in match.group(1).replace("\n", " ").split(","):
        item = chunk.strip()
        if not item:
            continue
        name, value = [part.strip() for part in item.split("=")]
        mapping[name] = int(value)
    return mapping


def parse_positions(text: str) -> list[list[tuple[int, int]]]:
    match = re.search(
        r"int positions\[2\]\[35\]\[2\]\s*=\s*(.*?)\s*;\s*bool emp_flag",
        text,
        re.S,
    )
    if not match:
        raise ValueError("failed to parse old AI positions")
    pairs = re.findall(r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*\}", match.group(1))
    coords = [(int(x), int(y)) for x, y in pairs]
    if len(coords) != 70:
        raise ValueError(f"unexpected old AI position count: {len(coords)}")
    return [coords[:35], coords[35:]]


def parse_map_property(text: str) -> tuple[tuple[tuple[int, ...], ...], int]:
    match = re.search(r"MAP_PROPERTY\s*=\s*(\(.+?\))\s*\n\nPATH_CELLS", text, re.S)
    if not match:
        raise ValueError("failed to parse MAP_PROPERTY")
    map_property = ast.literal_eval(match.group(1))
    return map_property, len(map_property)


def build_map_metadata() -> dict[str, object]:
    code_map = parse_code_map(OLD_AI_MAIN.read_text(encoding="utf-8"))
    name_by_index = {index: name for name, index in code_map.items()}
    positions = parse_positions(OLD_AI_MAIN.read_text(encoding="utf-8"))
    map_property, map_size = parse_map_property(CONSTANTS_PY.read_text(encoding="utf-8"))

    cells: list[dict[str, int]] = []
    for x in range(map_size):
        for y in range(map_size):
            terrain = int(map_property[x][y])
            if terrain < 0:
                continue
            cells.append({"x": x, "y": y, "terrain": terrain})

    slots: list[dict[str, object]] = []
    for player in (0, 1):
        for code, (x, y) in enumerate(positions[player]):
            slots.append(
                {
                    "player": player,
                    "code": code,
                    "name": name_by_index.get(code, f"S{code}"),
                    "x": x,
                    "y": y,
                }
            )

    return {
        "map_size": map_size,
        "cells": cells,
        "slots": slots,
        "bases": [
            {"player": 0, "x": 2, "y": 9},
            {"player": 1, "x": map_size - 3, "y": 9},
        ],
        "terrain_names": {
            "0": "Path",
            "1": "Barrier",
            "2": "P0 Highland",
            "3": "P1 Highland",
        },
    }


MAP_METADATA = build_map_metadata()


@dataclass
class ReplayCacheEntry:
    path: Path
    mtime_ns: int
    payload: list[dict]
    reconstructed_rounds: list[dict]


REPLAY_CACHE: dict[Path, ReplayCacheEntry] = {}


def clone_tower_record(tower: dict) -> dict:
    pos = tower.get("pos") or {}
    cloned = {
        "id": tower.get("id", -1),
        "player": tower.get("player", -1),
        "pos": {"x": pos.get("x", tower.get("x", -1)), "y": pos.get("y", tower.get("y", -1))},
        "type": tower.get("type", -1),
    }
    if "hp" in tower:
        cloned["hp"] = tower["hp"]
    if "cd" in tower:
        cloned["cd"] = tower["cd"]
    return cloned


def snapshot_towers(towers_by_id: dict[int, dict]) -> list[dict]:
    return [deepcopy(tower) for _, tower in sorted(towers_by_id.items(), key=lambda item: (item[1].get("player", -1), item[0]))]


def advance_reconstructed_tower_cooldowns(towers_by_id: dict[int, dict]) -> None:
    for tower in towers_by_id.values():
        cd = tower.get("cd")
        if isinstance(cd, int) and cd > 0:
            tower["cd"] = cd - 1


def build_reconstructed_rounds(payload: list[dict]) -> list[dict]:
    reconstructed: list[dict] = []
    towers_by_id: dict[int, dict] = {}
    for record in payload:
        round_state = record.get("round_state", {})
        round_start_towers = snapshot_towers(towers_by_id)
        advance_reconstructed_tower_cooldowns(towers_by_id)
        for tower in round_state.get("towers", []) or []:
            tower_id = int(tower.get("id", -1))
            if tower.get("type", -1) == -1:
                towers_by_id.pop(tower_id, None)
            else:
                towers_by_id[tower_id] = clone_tower_record(tower)
        full_round_state = deepcopy(round_state)
        full_round_state["towers"] = snapshot_towers(towers_by_id)
        reconstructed.append(
            {
                "round_start_towers": round_start_towers,
                "full_round_state": full_round_state,
            }
        )
    return reconstructed


def load_replay(path_text: str) -> ReplayCacheEntry:
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"replay not found: {path}")
    stat = path.stat()
    cached = REPLAY_CACHE.get(path)
    if cached is not None and cached.mtime_ns == stat.st_mtime_ns:
        return cached
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("replay must be a JSON array")
    entry = ReplayCacheEntry(
        path=path,
        mtime_ns=stat.st_mtime_ns,
        payload=payload,
        reconstructed_rounds=build_reconstructed_rounds(payload),
    )
    REPLAY_CACHE[path] = entry
    return entry


def require_inspector() -> None:
    if INSPECTOR_BIN.is_file():
        return
    raise FileNotFoundError(
        f"missing inspector binary: {INSPECTOR_BIN}. Run `make -C {CPP_SDK_DIR} build/sdk_lure_inspector` first."
    )


def run_inspector(payload: dict[str, object]) -> dict[str, object]:
    require_inspector()
    proc = subprocess.run(
        [str(INSPECTOR_BIN)],
        input=json.dumps(payload).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        cwd=str(CPP_SDK_DIR),
    )
    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    if not stdout:
        raise RuntimeError(f"inspector returned empty output: {stderr}")
    result = json.loads(stdout)
    if proc.returncode != 0:
        message = result.get("error") if isinstance(result, dict) else stdout
        raise RuntimeError(f"inspector failed: {message}\n{stderr}".strip())
    return result


class SimVizHandler(BaseHTTPRequestHandler):
    server_version = "AntGameSimViz/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[simviz] " + fmt % args + "\n")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/map":
            self._send_json(MAP_METADATA)
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if parsed.path == "/api/replay/load":
                self._send_json(self._handle_replay_load(payload))
                return
            if parsed.path == "/api/replay/round":
                self._send_json(self._handle_replay_round(payload))
                return
            if parsed.path == "/api/inspect/actions":
                self._send_json(run_inspector({"mode": "round_summary", **payload}))
                return
            if parsed.path == "/api/inspect/rollouts":
                self._send_json(run_inspector({"mode": "plan_rollouts", **payload}))
                return
            if parsed.path == "/api/inspect/trace":
                self._send_json(run_inspector({"mode": "plan_trace", **payload}))
                return
            self._send_error_json(HTTPStatus.NOT_FOUND, f"unknown endpoint: {parsed.path}")
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_replay_load(self, payload: dict[str, object]) -> dict[str, object]:
        replay_path = str(payload.get("replay_path", ""))
        entry = load_replay(replay_path)
        seed = entry.payload[0].get("seed", 0) if entry.payload else 0
        return {
            "ok": True,
            "replay_path": str(entry.path),
            "round_count": len(entry.payload),
            "seed": seed,
        }

    def _handle_replay_round(self, payload: dict[str, object]) -> dict[str, object]:
        replay_path = str(payload.get("replay_path", ""))
        round_index = int(payload.get("round", 0))
        entry = load_replay(replay_path)
        if round_index < 0 or round_index >= len(entry.payload):
            raise ValueError("round out of range")
        record = entry.payload[round_index]
        reconstructed = entry.reconstructed_rounds[round_index]
        return {
            "ok": True,
            "replay_path": str(entry.path),
            "round": round_index,
            "round_count": len(entry.payload),
            "seed": record.get("seed", entry.payload[0].get("seed", 0) if entry.payload else 0),
            "record": record,
            "round_start_towers": reconstructed["round_start_towers"],
            "full_round_state": reconstructed["full_round_state"],
        }

    def _serve_static(self, path: str) -> None:
        if path in ("", "/"):
            target = STATIC_DIR / "index.html"
        elif path.startswith("/static/"):
            rel = path[len("/static/") :].lstrip("/")
            target = STATIC_DIR / rel
        else:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"unknown path: {path}")
            return

        target = target.resolve()
        if not target.is_file() or STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve() / "index.html":
            self._send_error_json(HTTPStatus.NOT_FOUND, f"file not found: {path}")
            return

        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"ok": False, "error": message}, status=status)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Game1 simulation visualizer server")
    parser.add_argument("--host", default="127.0.0.1", help="bind host, default is localhost only")
    parser.add_argument("--port", type=int, default=8765, help="bind port")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SimVizHandler)
    print(f"simviz listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
