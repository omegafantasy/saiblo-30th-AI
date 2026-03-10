from __future__ import annotations

import json
import os
import select
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict


TIMEOUT_SECONDS = 20.0


def ensure_game_bin(ant_game_dir: Path) -> Path:
    game_dir = ant_game_dir / "game"
    game_bin = game_dir / "output" / "main"
    if not game_bin.is_file():
        subprocess.run(["make"], cwd=game_dir, check=True)
    return game_bin


def _copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst)
    for cache_dir in dst.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)
    for pyc in dst.rglob("*.pyc"):
        try:
            pyc.unlink()
        except OSError:
            pass


def _copy_sdk_layout(ant_game_dir: Path, output_dir: Path) -> None:
    ai_dir = ant_game_dir / "AI"
    shutil.copy2(ai_dir / "main.py", output_dir / "main.py")
    shutil.copy2(ai_dir / "common.py", output_dir / "common.py")
    shutil.copy2(ai_dir / "protocol.py", output_dir / "protocol.py")
    _copy_tree(ant_game_dir / "SDK", output_dir / "SDK")
    _copy_tree(ant_game_dir / "tools", output_dir / "tools")


def stage_version(ant_game_dir: Path, version: Dict[str, Any], output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    kind = str(version.get("kind", "")).strip()
    if kind == "antgame_py":
        target = str(version.get("name", "")).strip()
        if not target:
            raise RuntimeError(f"invalid antgame_py version: {version}")
        subprocess.run(
            [str(ant_game_dir / "AI" / "package_ai.sh"), target, str(output_dir)],
            cwd=ant_game_dir,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return output_dir

    if kind == "cpp_exe":
        exe = Path(str(version.get("exe", ""))).resolve()
        if not exe.is_file():
            raise RuntimeError(f"cpp exe not found: {exe}")
        _copy_sdk_layout(ant_game_dir, output_dir)
        shutil.copy2(ant_game_dir / "AI" / "ai_cpp_v1.py", output_dir / "ai.py")
        cpp_dir = output_dir / "cpp_ai"
        cpp_dir.mkdir(parents=True, exist_ok=True)
        target = cpp_dir / "ai_v1"
        shutil.copy2(exe, target)
        target.chmod(0o755)
        return output_dir

    raise RuntimeError(f"unsupported version kind for staging: {kind}")


def _packet(payload: object) -> bytes:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body


def _read_exact(stream, size: int, proc: subprocess.Popen[bytes], label: str, timeout: float = TIMEOUT_SECONDS) -> bytes:
    fd = stream.fileno()
    data = bytearray()
    deadline = time.monotonic() + timeout
    while len(data) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"timed out while reading {label}")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            continue
        chunk = os.read(fd, size - len(data))
        if not chunk:
            code = proc.poll()
            if code is None:
                raise EOFError(f"unexpected EOF while reading {label}")
            raise EOFError(f"{label} closed with exit code {code}")
        data.extend(chunk)
    return bytes(data)


def _read_game_packet(game: subprocess.Popen[bytes]) -> tuple[int, bytes]:
    size = struct.unpack(">I", _read_exact(game.stdout, 4, game, "game packet length"))[0]
    obj = struct.unpack(">i", _read_exact(game.stdout, 4, game, "game packet object"))[0]
    payload = _read_exact(game.stdout, size, game, "game packet payload")
    return obj, payload


def _read_ai_packet(ai: subprocess.Popen[bytes], label: str) -> bytes:
    size = struct.unpack(">I", _read_exact(ai.stdout, 4, ai, f"{label} packet length"))[0]
    payload = _read_exact(ai.stdout, size, ai, f"{label} packet payload")
    return struct.pack(">I", size) + payload


def _write_all(stream, payload: bytes) -> None:
    stream.write(payload)
    stream.flush()


def _launch_ai(ai_dir: Path, stderr_path: Path) -> subprocess.Popen[bytes]:
    stderr_handle = stderr_path.open("wb")
    return subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=ai_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_handle,
    )


def _terminate(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def _close_stdin(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.stdin is None:
        return
    try:
        proc.stdin.close()
    except OSError:
        pass


def _safe_read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _infer_score_from_failure(a_on_seat0: bool, ai0: subprocess.Popen[bytes] | None, ai1: subprocess.Popen[bytes] | None) -> tuple[float, int]:
    rc0 = ai0.poll() if ai0 is not None else None
    rc1 = ai1.poll() if ai1 is not None else None
    if rc0 not in (None, 0) and rc1 in (None, 0):
        winner = 1
        score_a = 0.0 if a_on_seat0 else 1.0
        return score_a, winner
    if rc1 not in (None, 0) and rc0 in (None, 0):
        winner = 0
        score_a = 1.0 if a_on_seat0 else 0.0
        return score_a, winner
    return 0.5, -1


def run_match_task(task: Dict[str, Any]) -> Dict[str, Any]:
    a = str(task["a"])
    b = str(task["b"])
    seed = int(task["seed"])
    a_on_seat0 = bool(task["a_on_seat0"])
    ai0_dir = Path(str(task["ai0_dir"])).resolve()
    ai1_dir = Path(str(task["ai1_dir"])).resolve()
    game_bin = Path(str(task["game_bin"])).resolve()
    work_dir = Path(str(task["work_dir"])).resolve()
    replay_file = Path(str(task["replay_file"])).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    replay_file.parent.mkdir(parents=True, exist_ok=True)

    ai0_stderr_path = work_dir / "ai0.stderr.log"
    ai1_stderr_path = work_dir / "ai1.stderr.log"
    game_stderr_path = work_dir / "game.stderr.log"
    game_dir = game_bin.parent.parent

    result: Dict[str, Any] = {
        "a": a,
        "b": b,
        "seed": seed,
        "a_seat": 0 if a_on_seat0 else 1,
        "replay_file": str(replay_file),
    }

    game_stderr_handle = game_stderr_path.open("wb")
    game = None
    ai0 = None
    ai1 = None
    try:
        ai0 = _launch_ai(ai0_dir, ai0_stderr_path)
        ai1 = _launch_ai(ai1_dir, ai1_stderr_path)
        ais = {0: ai0, 1: ai1}

        game = subprocess.Popen(
            [str(game_bin)],
            cwd=game_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=game_stderr_handle,
        )

        init = {
            "player_list": [1, 1],
            "player_num": 2,
            "config": {"random_seed": seed},
            "replay": str(replay_file),
        }
        _write_all(game.stdin, _packet(init))

        while True:
            obj, payload = _read_game_packet(game)
            if obj in (0, 1):
                _write_all(ais[obj].stdin, payload)
                continue

            message = json.loads(payload.decode("utf-8"))
            if isinstance(message, dict) and "player" in message and "content" in message:
                for player, content in zip(message["player"], message["content"]):
                    _write_all(ais[int(player)].stdin, content.encode("utf-8"))
            if isinstance(message, dict) and message.get("listen"):
                for player in message["listen"]:
                    ai_packet = _read_ai_packet(ais[int(player)], f"ai{player}")
                    reply = {
                        "player": int(player),
                        "content": ai_packet.decode("latin1"),
                        "time": 0,
                    }
                    _write_all(game.stdin, _packet(reply))
            if isinstance(message, dict) and "end_state" in message:
                result["end_state"] = message["end_state"]
                result["end_info"] = message.get("end_info")
                break

        game.wait(timeout=3)
        _close_stdin(ai0)
        _close_stdin(ai1)
        for ai in (ai0, ai1):
            try:
                ai.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _terminate(ai)

        replay_obj = _safe_read_json(replay_file)
        winner = -1
        rounds = 0
        if isinstance(replay_obj, list) and replay_obj:
            rounds = len(replay_obj)
            last_state = replay_obj[-1].get("round_state", {}) if isinstance(replay_obj[-1], dict) else {}
            if isinstance(last_state, dict):
                winner = int(last_state.get("winner", -1))
        score_a = 1.0 if winner == (0 if a_on_seat0 else 1) else 0.0 if winner in (0, 1) else 0.5
        result.update(
            {
                "score_a": score_a,
                "winner_seat": winner,
                "rounds_played": rounds,
                "game_returncode": game.returncode,
                "ai0_returncode": ai0.returncode,
                "ai1_returncode": ai1.returncode,
            }
        )
        return result
    except Exception as exc:
        score_a, winner = _infer_score_from_failure(a_on_seat0, ai0, ai1)
        result.update(
            {
                "score_a": score_a,
                "winner_seat": winner,
                "error": f"{type(exc).__name__}: {exc}",
                "game_returncode": game.poll() if game is not None else None,
                "ai0_returncode": ai0.poll() if ai0 is not None else None,
                "ai1_returncode": ai1.poll() if ai1 is not None else None,
            }
        )
        return result
    finally:
        _close_stdin(ai0)
        _close_stdin(ai1)
        _terminate(ai0)
        _terminate(ai1)
        _terminate(game)
        try:
            game_stderr_handle.close()
        except Exception:
            pass
