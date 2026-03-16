#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / 'static'
REPO_ROOT = Path('/www').resolve()
ALLOWED_ROOTS = [REPO_ROOT, Path('/tmp').resolve()]
DEFAULT_LIST_ROOTS = [
    REPO_ROOT / 'autolab/runtime/scopes/game1_v4_eval_core_tight/replays',
    REPO_ROOT / 'autolab/runtime/scopes/game1_v4_eval_core/replays',
    REPO_ROOT / 'autolab/runtime/scopes/game1_v4_eval_fast/replays',
    REPO_ROOT / 'autolab/runtime/scopes/game1_v4_eval/replays',
    REPO_ROOT / 'replays/saiblo_api',
]

sys.path.insert(0, str((REPO_ROOT / 'Game1/Ant-Game').resolve()))
from SDK.utils.constants import (  # type: ignore
    ANT_AGE_LIMIT,
    ANT_GENERATION_CYCLE,
    ANT_KILL_REWARD,
    ANT_MAX_HP,
    BASE_UPGRADE_COST,
    HIGHLAND_CELLS,
    MAP_PROPERTY,
    MAP_SIZE,
    PATH_CELLS,
    PLAYER_BASES,
    SUPER_WEAPON_STATS,
    TOWER_STATS,
    TOWER_UPGRADE_TREE,
    AntBehavior,
    AntStatus,
    SuperWeaponType,
    Terrain,
    TowerType,
)


TERRAIN_BY_CELL: dict[tuple[int, int], str] = {}
for x, y in PATH_CELLS:
    TERRAIN_BY_CELL[(x, y)] = 'path'
for x, y in HIGHLAND_CELLS[0]:
    TERRAIN_BY_CELL[(x, y)] = 'p0_highland'
for x, y in HIGHLAND_CELLS[1]:
    TERRAIN_BY_CELL[(x, y)] = 'p1_highland'
for index, (x, y) in enumerate(PLAYER_BASES):
    TERRAIN_BY_CELL[(x, y)] = f'base{index}'


TOWER_LABELS = {
    TowerType.BASIC: 'B',
    TowerType.HEAVY: 'H',
    TowerType.QUICK: 'Q',
    TowerType.MORTAR: 'M',
    TowerType.HEAVY_PLUS: 'H+',
    TowerType.ICE: 'Ice',
    TowerType.CANNON: 'Can',
    TowerType.QUICK_PLUS: 'Q+',
    TowerType.DOUBLE: '2x',
    TowerType.SNIPER: 'Snp',
    TowerType.MORTAR_PLUS: 'M+',
    TowerType.PULSE: 'Pls',
    TowerType.MISSILE: 'Mis',
}


def _json_response(handler: SimpleHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)


def _normalize_path(raw: str) -> Path:
    if not raw:
        raise ValueError('missing path')
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if not any(str(candidate).startswith(str(root)) for root in ALLOWED_ROOTS):
        raise ValueError(f'path outside allowed roots: {candidate}')
    return candidate


def _load_replay(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding='utf-8', errors='ignore').lstrip()
    if not raw:
        raise ValueError('empty replay file')
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'invalid json: {exc}') from exc
    if not isinstance(obj, list):
        raise ValueError('unsupported replay root type; expected JSON array replay')
    return obj


def _build_map_payload() -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for x in range(MAP_SIZE):
        for y in range(MAP_SIZE):
            value = MAP_PROPERTY[x][y]
            if value == Terrain.VOID:
                continue
            terrain = TERRAIN_BY_CELL.get((x, y))
            if not terrain:
                terrain = 'barrier' if value == Terrain.BARRIER else 'unknown'
            cells.append({'x': x, 'y': y, 'terrain': terrain})
    return {
        'mapSize': MAP_SIZE,
        'bases': [
            {'player': idx, 'x': x, 'y': y}
            for idx, (x, y) in enumerate(PLAYER_BASES)
        ],
        'cells': cells,
    }


def _build_meta_payload() -> dict[str, Any]:
    towers: dict[str, Any] = {}
    for tower_type, stats in TOWER_STATS.items():
        towers[str(int(tower_type))] = {
            'name': tower_type.name,
            'label': TOWER_LABELS[tower_type],
            'damage': stats.damage,
            'speed': stats.speed,
            'range': stats.attack_range,
            'upgrades': [int(x) for x in TOWER_UPGRADE_TREE.get(tower_type, ())],
        }
    weapons: dict[str, Any] = {}
    for weapon_type, stats in SUPER_WEAPON_STATS.items():
        weapons[str(int(weapon_type))] = {
            'name': weapon_type.name,
            'duration': stats.duration,
            'range': stats.attack_range,
            'cooldown': stats.cooldown,
            'cost': stats.cost,
        }
    return {
        'towerTypes': towers,
        'weaponTypes': weapons,
        'behaviors': {str(int(x)): x.name for x in AntBehavior},
        'statuses': {str(int(x)): x.name for x in AntStatus},
        'antMaxHp': list(ANT_MAX_HP),
        'antGenerationCycle': list(ANT_GENERATION_CYCLE),
        'antKillReward': list(ANT_KILL_REWARD),
        'baseUpgradeCost': list(BASE_UPGRADE_COST),
        'antAgeLimit': ANT_AGE_LIMIT,
    }


MAP_PAYLOAD = _build_map_payload()
META_PAYLOAD = _build_meta_payload()


def _list_replays(root: Path, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not root.exists():
        return out
    candidates: list[Path] = []
    if root.is_file():
        candidates = [root]
    else:
        for path in root.rglob('*.json'):
            candidates.append(path)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates[:limit]:
        try:
            size = path.stat().st_size
            mtime = int(path.stat().st_mtime)
        except OSError:
            continue
        out.append({
            'path': str(path),
            'name': path.name,
            'size': size,
            'mtime': mtime,
        })
    return out


class ReplayPlayerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == '/api/map':
            _json_response(self, MAP_PAYLOAD)
            return
        if parsed.path == '/api/meta':
            _json_response(self, META_PAYLOAD)
            return
        if parsed.path == '/api/replay':
            params = parse_qs(parsed.query)
            try:
                replay_path = _normalize_path(params.get('path', [''])[0])
                frames = _load_replay(replay_path)
            except Exception as exc:
                _json_response(self, {'ok': False, 'error': str(exc)}, status=400)
                return
            _json_response(self, {
                'ok': True,
                'path': str(replay_path),
                'frames': frames,
                'count': len(frames),
            })
            return
        if parsed.path == '/api/list':
            params = parse_qs(parsed.query)
            limit = int(params.get('limit', ['200'])[0] or 200)
            limit = max(1, min(limit, 1000))
            raw_root = params.get('root', [''])[0]
            if raw_root:
                try:
                    root = _normalize_path(raw_root)
                except Exception as exc:
                    _json_response(self, {'ok': False, 'error': str(exc)}, status=400)
                    return
                roots = [root]
            else:
                roots = [path for path in DEFAULT_LIST_ROOTS if path.exists()]
            payload = []
            for root in roots:
                payload.append({
                    'root': str(root),
                    'files': _list_replays(root, limit),
                })
            _json_response(self, {'ok': True, 'roots': payload})
            return
        if parsed.path in ('/', '/index.html'):
            self.path = '/index.html'
        return super().do_GET()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write('[replay-player] ' + fmt % args + '\n')


def main() -> int:
    parser = argparse.ArgumentParser(description='Game1 replay player server')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8010)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ReplayPlayerHandler)
    print(json.dumps({
        'ok': True,
        'host': args.host,
        'port': args.port,
        'url': f'http://{args.host}:{args.port}/',
        'static_dir': str(STATIC_DIR),
    }, ensure_ascii=False))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
