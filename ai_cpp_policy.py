from __future__ import annotations

import atexit
import json
import os
import struct
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parent
ANT_GAME_DIR = ROOT_DIR / "Ant-Game"
if str(ANT_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(ANT_GAME_DIR))

from logic.gamestate import GameState


def _default_exe() -> str:
    return str(ROOT_DIR / "ai_cpp_v1" / "ai_v1")


def _parse_ops(text: str) -> list[list[int]]:
    ops: list[list[int]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            op = [int(x) for x in line.split()]
        except Exception:
            continue
        if not op:
            continue
        ops.append(op)
        if op[0] == 8:
            break
    if not ops or ops[-1][0] != 8:
        ops.append([8])
    return ops


class _CppWorker:
    def __init__(self, seat: int, seed: int = 0):
        self.seat = int(seat)
        self.seed = int(seed)
        self.exe = os.environ.get("CPP_AI_EXE", _default_exe())
        if not os.path.isfile(self.exe):
            raise FileNotFoundError(f"C++ AI executable not found: {self.exe}")
        self.proc = subprocess.Popen(
            [self.exe],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._send_line(f"{self.seat} {self.seed}")

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=0.5)
            except Exception:
                self.proc.kill()

    def _send_line(self, line: str) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("cpp worker stdin unavailable")
        data = (line if line.endswith("\n") else line + "\n").encode("utf-8")
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def _read_exact(self, n: int) -> bytes:
        if self.proc.stdout is None:
            return b""
        buf = bytearray()
        while len(buf) < n:
            chunk = self.proc.stdout.read(n - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def query(self, state: GameState) -> list[list[int]]:
        if self.proc.poll() is not None:
            return [[8]]

        rep = state.trans_state_to_init_json(self.seat)
        rep["Player"] = self.seat
        rep["Turn"] = self.seat
        payload = json.dumps(rep, ensure_ascii=False, separators=(",", ":"))

        try:
            self._send_line(payload)
            hdr = self._read_exact(4)
            if len(hdr) < 4:
                return [[8]]
            length = struct.unpack(">I", hdr)[0]
            if length <= 0 or length > 1_000_000:
                return [[8]]
            body = self._read_exact(length)
            if len(body) < length:
                return [[8]]
            text = body.decode("utf-8", errors="replace")
            return _parse_ops(text)
        except Exception:
            return [[8]]


_lock = threading.Lock()
_workers: Dict[int, _CppWorker] = {}


def _cleanup() -> None:
    with _lock:
        for w in _workers.values():
            w.close()
        _workers.clear()


atexit.register(_cleanup)


def _worker_for(seat: int) -> _CppWorker:
    with _lock:
        if seat in _workers:
            return _workers[seat]
        seed = int(os.environ.get("CPP_AI_SEED", "0"))
        w = _CppWorker(seat=seat, seed=seed)
        _workers[seat] = w
        return w


def policy(round_idx: int, my_seat: int, state: GameState) -> list[list[int]]:
    try:
        worker = _worker_for(my_seat)
        return worker.query(state)
    except Exception:
        return [[8]]


def ai_func(state: GameState) -> List[List[int]]:
    return policy(getattr(state, "round", 1), 0, state)
