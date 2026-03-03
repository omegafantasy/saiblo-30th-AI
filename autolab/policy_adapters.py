from __future__ import annotations

import importlib
import json
import os
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict

from .common import ANT_GAME_DIR

if str(ANT_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(ANT_GAME_DIR))


class _CppWorker:
    def __init__(self, exe: str, seat: int, seed: int):
        self.exe = exe
        self.seat = int(seat)
        self.seed = int(seed)
        self.proc = subprocess.Popen(
            [self.exe],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._send_line(f"{self.seat} {self.seed}")

    def _send_line(self, line: str) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("cpp stdin unavailable")
        data = (line if line.endswith("\n") else line + "\n").encode("utf-8")
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def _read_exact(self, n: int) -> bytes:
        if self.proc.stdout is None:
            return b""
        out = bytearray()
        while len(out) < n:
            chunk = self.proc.stdout.read(n - len(out))
            if not chunk:
                break
            out.extend(chunk)
        return bytes(out)

    def query(self, state: Any, seat: int) -> list[list[int]]:
        if self.proc.poll() is not None:
            return [[8]]
        rep = state.trans_state_to_init_json(seat)
        rep["Player"] = seat
        rep["Turn"] = seat
        payload = json.dumps(rep, ensure_ascii=False, separators=(",", ":"))
        try:
            self._send_line(payload)
            hdr = self._read_exact(4)
            if len(hdr) < 4:
                return [[8]]
            n = struct.unpack(">I", hdr)[0]
            if n <= 0 or n > 1_000_000:
                return [[8]]
            body = self._read_exact(n)
            if len(body) < n:
                return [[8]]
            return _parse_ops(body.decode("utf-8", errors="replace"))
        except Exception:
            return [[8]]

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=0.5)
            except Exception:
                self.proc.kill()


def _parse_ops(text: str) -> list[list[int]]:
    ops: list[list[int]] = []
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        try:
            op = [int(x) for x in ln.split()]
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


class CppPolicyAdapter:
    def __init__(self, exe: str, base_seed: int):
        if not os.path.isfile(exe):
            raise FileNotFoundError(f"cpp exe not found: {exe}")
        self.exe = exe
        self.base_seed = int(base_seed)
        self.workers: Dict[int, _CppWorker] = {}

    def __call__(self, round_idx: int, my_seat: int, state: Any) -> list[list[int]]:
        del round_idx
        seat = int(my_seat)
        if seat not in self.workers:
            self.workers[seat] = _CppWorker(self.exe, seat=seat, seed=self.base_seed + seat)
        return self.workers[seat].query(state, seat)

    def close(self) -> None:
        for w in self.workers.values():
            w.close()
        self.workers.clear()


def _load_antgame_policy(name: str) -> Callable[[int, int, Any], list[list[int]]]:
    mod = importlib.import_module(f"AI.ai_{name}")
    fn = getattr(mod, "policy", None)
    if not callable(fn):
        raise RuntimeError(f"policy not found in AI.ai_{name}")
    return fn


def _load_module_callable(spec: str) -> Callable[[int, int, Any], list[list[int]]]:
    mod_name, fn_name = spec.split(":", 1)
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name)
    if not callable(fn):
        raise RuntimeError(f"callable not found: {spec}")
    return fn


def make_policy(version: Dict[str, Any], base_seed: int) -> Callable[[int, int, Any], list[list[int]]]:
    kind = str(version.get("kind", "")).strip()
    if kind == "cpp_exe":
        return CppPolicyAdapter(str(version.get("exe", "")), base_seed=base_seed)
    if kind == "antgame_py":
        return _load_antgame_policy(str(version.get("name", "")))
    if kind == "python_module":
        return _load_module_callable(str(version.get("callable", "")))
    raise RuntimeError(f"unsupported version kind: {kind}")


def close_policy(policy: Any) -> None:
    close = getattr(policy, "close", None)
    if callable(close):
        close()

