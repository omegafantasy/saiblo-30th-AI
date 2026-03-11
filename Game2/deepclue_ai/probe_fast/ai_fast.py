#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import sys
from typing import Any


class SDK:
    def __init__(self) -> None:
        self._stdin = sys.stdin.buffer
        self._stdout = sys.stdout.buffer

    def _send(self, data: dict[str, Any]) -> None:
        msg = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self._stdout.write(struct.pack('>I', len(msg)) + msg)
        self._stdout.flush()

    def _receive(self) -> dict[str, Any]:
        self._stdin.read(4)
        line = self._stdin.readline()
        if not line:
            raise EOFError('stdin closed')
        msg = line.decode('utf-8', errors='replace').strip()
        return json.loads(msg) if msg else {}

    def request(self, action: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        self._send({'action': action, **kwargs})
        return self._receive()


def main() -> int:
    sdk = SDK()
    sdk._receive()
    for _ in range(4):
        try:
            npcs = sdk.request('npcs')
        except EOFError:
            break
        if not isinstance(npcs, list):
            break
        murderer = str(npcs[0]) if npcs else ''
        try:
            sdk.request('answer', murderer=murderer, motivation='未知', method='未知')
        except EOFError:
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
