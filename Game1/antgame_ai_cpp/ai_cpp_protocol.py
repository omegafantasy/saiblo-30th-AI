from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path

try:
    from common import MatchSession
except ModuleNotFoundError as exc:
    if exc.name != "common":
        raise
    ant_game_ai_dir = Path(__file__).resolve().parents[1] / "Ant-Game" / "AI"
    sys.path.insert(0, str(ant_game_ai_dir))
    from common import MatchSession


class CppProtocolSession(MatchSession):
    def __init__(self, exe_path: Path | None = None) -> None:
        self.stdin = sys.stdin.buffer
        self.stdout = sys.stdout.buffer
        self.stderr = sys.stderr
        self.exe_path = exe_path or (Path(__file__).resolve().parent / "cpp_ai" / "ai")
        self.debug_path = os.environ.get("ANTGAME_CPP_PROTOCOL_DEBUG_PATH", "").strip()

        init_line = self.stdin.readline()
        if not init_line:
            raise RuntimeError("missing init line")
        try:
            player_token = init_line.decode("utf-8", errors="replace").split()[0]
            self._player = int(player_token)
        except Exception as exc:
            raise RuntimeError("invalid init line") from exc
        self._debug(f"init player={self._player} line={init_line!r}")

        self.proc = subprocess.Popen(
            [str(self.exe_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
        )
        self._write_child(init_line)

    @property
    def player(self) -> int:
        return self._player

    def _write_child(self, payload: bytes) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("cpp child stdin unavailable")
        self.proc.stdin.write(payload)
        self.proc.stdin.flush()

    def _read_exact_child(self, size: int) -> bytes:
        if self.proc.stdout is None:
            raise RuntimeError("cpp child stdout unavailable")
        data = bytearray()
        while len(data) < size:
            chunk = self.proc.stdout.read(size - len(data))
            if not chunk:
                raise EOFError("unexpected EOF from cpp child")
            data.extend(chunk)
        return bytes(data)

    def _forward_line_block(self, line_count: int) -> bool:
        for _ in range(line_count):
            line = self.stdin.readline()
            if not line:
                self._terminate_child()
                return False
            self._write_child(line)
        return True

    def _forward_counted_block(self, label: str) -> bool:
        count_line = self.stdin.readline()
        if not count_line:
            self._terminate_child()
            return False
        self._write_child(count_line)
        try:
            count = int(count_line.decode("utf-8", errors="replace").strip() or "0")
        except ValueError as exc:
            raise RuntimeError(f"invalid {label} count") from exc
        self._debug(f"{label}_count={count}")
        return self._forward_line_block(count)

    def _terminate_child(self) -> None:
        if self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=1.0)

    def _debug(self, message: str) -> None:
        if not self.debug_path:
            return
        with open(self.debug_path, "a", encoding="utf-8") as handle:
            handle.write(f"[cpp_protocol] {message}\n")

    def perform_self_turn(self) -> None:
        self._debug("perform_self_turn: waiting child packet")
        packet_len = struct.unpack(">I", self._read_exact_child(4))[0]
        payload = self._read_exact_child(packet_len)
        self._debug(f"perform_self_turn: child packet_len={packet_len}")
        self.stdout.write(struct.pack(">I", packet_len))
        self.stdout.write(payload)
        self.stdout.flush()

    def receive_opponent_turn(self) -> bool:
        count_line = self.stdin.readline()
        if not count_line:
            self._terminate_child()
            return False
        self._write_child(count_line)
        try:
            count = int(count_line.decode("utf-8", errors="replace").strip() or "0")
        except ValueError as exc:
            raise RuntimeError("invalid opponent operation count") from exc
        self._debug(f"receive_opponent_turn: count={count}")
        return self._forward_line_block(count)

    def sync_round(self) -> bool:
        round_line = self.stdin.readline()
        if not round_line:
            self._terminate_child()
            return False
        self._write_child(round_line)
        self._debug(f"sync_round: round={round_line.decode('utf-8', errors='replace').strip()}")

        tower_count_line = self.stdin.readline()
        if not tower_count_line:
            self._terminate_child()
            return False
        self._write_child(tower_count_line)
        try:
            tower_count = int(tower_count_line.decode("utf-8", errors="replace").strip() or "0")
        except ValueError as exc:
            raise RuntimeError("invalid tower count") from exc
        self._debug(f"sync_round: tower_count={tower_count}")
        if not self._forward_line_block(tower_count):
            return False

        ant_count_line = self.stdin.readline()
        if not ant_count_line:
            self._terminate_child()
            return False
        self._write_child(ant_count_line)
        try:
            ant_count = int(ant_count_line.decode("utf-8", errors="replace").strip() or "0")
        except ValueError as exc:
            raise RuntimeError("invalid ant count") from exc
        self._debug(f"sync_round: ant_count={ant_count}")
        if not self._forward_line_block(ant_count):
            return False

        if not self._forward_line_block(2):
            return False
        if not self._forward_counted_block("weapon cooldown row"):
            return False
        return self._forward_counted_block("active effect")


class AI:
    def create_session(self) -> MatchSession:
        return CppProtocolSession()
