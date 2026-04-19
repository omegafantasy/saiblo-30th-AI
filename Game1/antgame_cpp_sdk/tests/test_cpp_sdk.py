from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

import pytest

GAME1_DIR = Path(__file__).resolve().parents[2]
ANTGAME_DIR = GAME1_DIR / "Ant-Game"
sys.path.insert(0, str(ANTGAME_DIR))

from SDK.backend.engine import GameState, MOVEMENT_POLICY_ENHANCED, MOVEMENT_POLICY_LEGACY, PublicRoundState
from SDK.backend.model import Ant, Operation, Tower
from SDK.utils.constants import (
    AntBehavior,
    AntKind,
    OperationType,
    PLAYER_BASES,
    STRATEGIC_BUILD_ORDER,
    SUPER_WEAPON_STATS,
    SuperWeaponType,
    TOWER_UPGRADE_TREE,
    TowerType,
)
from SDK.utils.geometry import hex_distance


GAME_DIR = ANTGAME_DIR / "game"
GAME_BIN = GAME_DIR / "output" / "main"
CPP_SDK_DIR = GAME1_DIR / "antgame_cpp_sdk"
CPP_SDK_RUNNER = CPP_SDK_DIR / "build" / "sdk_json_runner"


@lru_cache(maxsize=1)
def _ensure_game_binary() -> None:
    subprocess.run(["make"], cwd=GAME_DIR, check=True, capture_output=True, text=True)


@lru_cache(maxsize=1)
def _ensure_cpp_sdk_runner() -> None:
    subprocess.run(
        ["make", "-j2", "build/sdk_json_runner"],
        cwd=CPP_SDK_DIR,
        check=True,
        capture_output=True,
        text=True,
    )


def _operation_tokens(operation: Operation) -> list[int]:
    return list(operation.to_protocol_tokens())


def _packet(message: object) -> bytes:
    payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def _prefixed_text_packet(text: str) -> str:
    payload = text.encode("utf-8")
    return (struct.pack(">I", len(payload)) + payload).decode("latin1")


def _operations_text(operations: list[Operation]) -> str:
    if not operations:
        return "0\n"
    lines = [str(len(operations))]
    for operation in operations:
        lines.append(" ".join(str(token) for token in operation.to_protocol_tokens()))
    return "\n".join(lines) + "\n"


def _run_game_replay(
    *,
    replay_path: Path,
    seed: int,
    movement_policy: str,
    rounds0: list[list[Operation]],
    rounds1: list[list[Operation]],
    cold_handle_rule_illegal: bool,
) -> list[dict]:
    _ensure_game_binary()
    packets = [
        _packet(
            {
                "player_list": [1, 1],
                "player_num": 2,
                "config": {
                    "random_seed": seed,
                    "movement_policy": movement_policy,
                    "max_rounds": max(len(rounds0), len(rounds1)),
                    "cold_handle_rule_illegal": cold_handle_rule_illegal,
                },
                "replay": str(replay_path),
            }
        )
    ]
    round_count = max(len(rounds0), len(rounds1))
    for round_index in range(round_count):
        packets.append(
            _packet(
                {
                    "player": 0,
                    "content": _prefixed_text_packet(
                        _operations_text(rounds0[round_index] if round_index < len(rounds0) else [])
                    ),
                    "time": 0,
                }
            )
        )
        packets.append(
            _packet(
                {
                    "player": 1,
                    "content": _prefixed_text_packet(
                        _operations_text(rounds1[round_index] if round_index < len(rounds1) else [])
                    ),
                    "time": 0,
                }
            )
        )
    packets.append(
        _packet(
            {
                "player": -1,
                "content": json.dumps({"player": 0, "error": 0}),
                "time": 0,
            }
        )
    )
    completed = subprocess.run(
        [str(GAME_BIN)],
        cwd=GAME_DIR,
        input=b"".join(packets),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    return json.loads(replay_path.read_text())


def _run_cpp_sdk_runner(payload: dict) -> dict:
    _ensure_cpp_sdk_runner()
    completed = subprocess.run(
        [str(CPP_SDK_RUNNER)],
        cwd=CPP_SDK_DIR,
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    response = json.loads(completed.stdout.decode("utf-8"))
    assert "error" not in response, response
    return response


def _candidate_operations(state: GameState, player: int) -> list[Operation]:
    candidates: list[Operation] = []
    for x, y in STRATEGIC_BUILD_ORDER[player][:10]:
        candidates.append(Operation(OperationType.BUILD_TOWER, x, y))

    for tower in state.towers_of(player):
        for target in TOWER_UPGRADE_TREE.get(tower.tower_type, ()):
            candidates.append(Operation(OperationType.UPGRADE_TOWER, tower.tower_id, int(target)))
        candidates.append(Operation(OperationType.DOWNGRADE_TOWER, tower.tower_id))

    candidates.append(Operation(OperationType.UPGRADE_GENERATION_SPEED))
    candidates.append(Operation(OperationType.UPGRADE_GENERATED_ANT))

    positions: list[tuple[int, int]] = [PLAYER_BASES[player], PLAYER_BASES[1 - player]]
    positions.extend((tower.x, tower.y) for tower in state.towers)
    positions.extend((ant.x, ant.y) for ant in state.ants)
    seen: set[tuple[int, int]] = set()
    unique_positions: list[tuple[int, int]] = []
    for position in positions:
        if position in seen:
            continue
        seen.add(position)
        unique_positions.append(position)
    for x, y in unique_positions[:8]:
        for op_type in (
            OperationType.USE_LIGHTNING_STORM,
            OperationType.USE_EMP_BLASTER,
            OperationType.USE_DEFLECTOR,
            OperationType.USE_EMERGENCY_EVASION,
        ):
            candidates.append(Operation(op_type, x, y))
    return candidates


def _sample_turn_operations(state: GameState, player: int, rng: random.Random) -> list[Operation]:
    candidates = _candidate_operations(state, player)
    rng.shuffle(candidates)
    accepted: list[Operation] = []
    target_count = rng.randint(0, 2)
    for candidate in candidates:
        if len(accepted) >= target_count:
            break
        if state.can_apply_operation(player, candidate, accepted):
            accepted.append(candidate)
    return accepted


def _generate_legal_turn_script(
    *,
    seed: int,
    movement_policy: str,
    cold_handle_rule_illegal: bool,
    rounds: int,
    script_seed: int,
) -> list[tuple[list[Operation], list[Operation]]]:
    rng = random.Random(script_seed)
    state = GameState.initial(
        seed=seed,
        movement_policy=movement_policy,
        cold_handle_rule_illegal=cold_handle_rule_illegal,
    )
    turns: list[tuple[list[Operation], list[Operation]]] = []
    for _ in range(rounds):
        ops0 = _sample_turn_operations(state, 0, rng)
        ops1 = _sample_turn_operations(state, 1, rng)
        turns.append((ops0, ops1))
        state.resolve_turn(ops0, ops1)
        if state.terminal:
            break
    return turns


def _trace_request(
    *,
    seed: int,
    movement_policy: str,
    cold_handle_rule_illegal: bool,
    turns: list[tuple[list[Operation], list[Operation]]],
) -> dict:
    return {
        "seed": seed,
        "movement_policy": movement_policy,
        "cold_handle_rule_illegal": cold_handle_rule_illegal,
        "turns": [
            {"ops0": [_operation_tokens(op) for op in ops0], "ops1": [_operation_tokens(op) for op in ops1]}
            for ops0, ops1 in turns
        ],
    }


def _public_round_state_to_payload(round_state: PublicRoundState) -> dict:
    return {
        "round_index": int(round_state.round_index),
        "towers": [list(row) for row in round_state.towers],
        "ants": [list(row) for row in round_state.ants],
        "coins": list(round_state.coins),
        "camps_hp": list(round_state.camps_hp),
        "speed_lv": list(round_state.speed_lv or (0, 0)),
        "anthp_lv": list(round_state.anthp_lv or (0, 0)),
        "weapon_cooldowns": [
            [0, *list(row)]
            for row in (round_state.weapon_cooldowns or ((0, 0, 0, 0), (0, 0, 0, 0)))
        ],
        "active_effects": [list(row) for row in (round_state.active_effects or [])],
    }


def _normalize_python_public_round_state(round_state: PublicRoundState) -> dict:
    return {
        "round_index": int(round_state.round_index),
        "towers": sorted(tuple(row) for row in round_state.towers),
        "ants": sorted(tuple(row) for row in round_state.ants),
        "coins": tuple(round_state.coins),
        "camps_hp": tuple(round_state.camps_hp),
        "speed_lv": tuple(round_state.speed_lv or (0, 0)),
        "anthp_lv": tuple(round_state.anthp_lv or (0, 0)),
        "weapon_cooldowns": tuple(tuple(row) for row in (round_state.weapon_cooldowns or ((0, 0, 0, 0), (0, 0, 0, 0)))),
        "active_effects": sorted(tuple(row) for row in (round_state.active_effects or [])),
    }


def _normalize_cpp_public_round_state(state: dict) -> dict:
    return {
        "round_index": int(state["round_index"]),
        "towers": sorted(tuple(row) for row in state["towers"]),
        "ants": sorted(tuple(row) for row in state["ants"]),
        "coins": tuple(state["coins"]),
        "camps_hp": tuple(state["camps_hp"]),
        "speed_lv": tuple(state["speed_lv"]),
        "anthp_lv": tuple(state["anthp_lv"]),
        "weapon_cooldowns": tuple(tuple(row[1:5]) for row in state["weapon_cooldowns"]),
        "active_effects": sorted(tuple(row) for row in state["active_effects"]),
    }


def _query_operations_for_public_state(state: GameState, player: int) -> list[Operation]:
    candidates = _candidate_operations(state, player)
    extra_invalid = Operation(OperationType.BUILD_TOWER, *PLAYER_BASES[1 - player])
    tokens_seen: set[tuple[int, ...]] = set()
    ordered: list[Operation] = []
    for operation in [*candidates[:14], extra_invalid]:
        tokens = tuple(_operation_tokens(operation))
        if tokens in tokens_seen:
            continue
        tokens_seen.add(tokens)
        ordered.append(operation)
    return ordered


def _apply_operations_for_public_state(state: GameState, player: int) -> list[Operation]:
    owned_towers = state.towers_of(player)
    if owned_towers:
        tower = owned_towers[0]
        upgrades = TOWER_UPGRADE_TREE.get(tower.tower_type, ())
        if upgrades:
            return [
                Operation(OperationType.UPGRADE_TOWER, tower.tower_id, int(upgrades[0])),
                Operation(OperationType.DOWNGRADE_TOWER, tower.tower_id),
            ]
        return [
            Operation(OperationType.DOWNGRADE_TOWER, tower.tower_id),
            Operation(OperationType.DOWNGRADE_TOWER, tower.tower_id),
        ]

    for x, y in STRATEGIC_BUILD_ORDER[player]:
        build = Operation(OperationType.BUILD_TOWER, x, y)
        if state.can_apply_operation(player, build):
            return [build, build]

    return [
        Operation(OperationType.UPGRADE_GENERATION_SPEED),
        Operation(OperationType.UPGRADE_GENERATED_ANT),
    ]


@pytest.mark.parametrize("movement_policy", [MOVEMENT_POLICY_ENHANCED, MOVEMENT_POLICY_LEGACY])
@pytest.mark.parametrize("cold_handle_rule_illegal", [False, True])
def test_cpp_sdk_native_simulator_matches_authoritative_cpp_game(
    movement_policy: str,
    cold_handle_rule_illegal: bool,
) -> None:
    seed_base = 104729 if movement_policy == MOVEMENT_POLICY_ENHANCED else 104759
    cold_mask = 0x314159 if cold_handle_rule_illegal else 0x271828

    for batch_index in range(4):
        seed = seed_base + batch_index * 97 + (1 if cold_handle_rule_illegal else 0)
        turns = _generate_legal_turn_script(
            seed=seed,
            movement_policy=movement_policy,
            cold_handle_rule_illegal=cold_handle_rule_illegal,
            rounds=14,
            script_seed=seed ^ cold_mask ^ (batch_index * 0x9E3779B1),
        )
        payload = _trace_request(
            seed=seed,
            movement_policy=movement_policy,
            cold_handle_rule_illegal=cold_handle_rule_illegal,
            turns=turns,
        )

        native_trace = _run_cpp_sdk_runner({"mode": "native_trace", **payload})["trace"]
        game_trace = _run_cpp_sdk_runner({"mode": "game_trace", **payload})["trace"]

        assert len(native_trace) == len(game_trace), (movement_policy, cold_handle_rule_illegal, batch_index)
        for native_row, game_row in zip(native_trace, game_trace):
            assert native_row["illegal0"] == game_row["illegal0"]
            assert native_row["illegal1"] == game_row["illegal1"]
            assert native_row["terminal"] == game_row["terminal"]
            assert native_row["winner"] == game_row["winner"]
            assert _normalize_cpp_public_round_state(native_row["state"]) == _normalize_cpp_public_round_state(
                game_row["state"]
            )


@pytest.mark.parametrize("movement_policy", [MOVEMENT_POLICY_ENHANCED, MOVEMENT_POLICY_LEGACY])
@pytest.mark.parametrize("cold_handle_rule_illegal", [False, True])
def test_cpp_sdk_public_state_matches_python_public_queries(
    movement_policy: str,
    cold_handle_rule_illegal: bool,
) -> None:
    seed = 65537 if movement_policy == MOVEMENT_POLICY_ENHANCED else 65539
    turns = _generate_legal_turn_script(
        seed=seed,
        movement_policy=movement_policy,
        cold_handle_rule_illegal=cold_handle_rule_illegal,
        rounds=8,
        script_seed=seed ^ (0x1234 if cold_handle_rule_illegal else 0x5678),
    )
    python_state = GameState.initial(
        seed=seed,
        movement_policy=movement_policy,
        cold_handle_rule_illegal=cold_handle_rule_illegal,
    )
    snapshots: list[PublicRoundState] = []
    for ops0, ops1 in turns:
        python_state.resolve_turn(ops0, ops1)
        snapshots.append(python_state.to_public_round_state())
        if python_state.terminal:
            break

    selected_indices = list(range(min(4, len(snapshots))))
    if snapshots and selected_indices[-1] != len(snapshots) - 1:
        selected_indices.append(len(snapshots) - 1)

    for snapshot_index in selected_indices:
        snapshot = snapshots[snapshot_index]
        for player in (0, 1):
            query_state = GameState.initial(
                seed=seed,
                movement_policy=movement_policy,
                cold_handle_rule_illegal=cold_handle_rule_illegal,
            )
            query_state.sync_public_round_state(snapshot)
            query_operations = _query_operations_for_public_state(query_state, player)
            apply_operations = _apply_operations_for_public_state(query_state, player)
            slot_points = [list(point) for point in STRATEGIC_BUILD_ORDER[player][:6]]

            cpp_out = _run_cpp_sdk_runner(
                {
                    "mode": "public_eval",
                    "seed": seed,
                    "movement_policy": movement_policy,
                    "cold_handle_rule_illegal": cold_handle_rule_illegal,
                    "player": player,
                    "public_state": _public_round_state_to_payload(snapshot),
                    "query_operations": [_operation_tokens(operation) for operation in query_operations],
                    "apply_operations": [_operation_tokens(operation) for operation in apply_operations],
                    "slot_points": slot_points,
                }
            )

            expected_can_apply = [query_state.can_apply_operation(player, operation) for operation in query_operations]
            expected_income = [query_state.operation_income(player, operation) for operation in query_operations]

            after_state = GameState.initial(
                seed=seed,
                movement_policy=movement_policy,
                cold_handle_rule_illegal=cold_handle_rule_illegal,
            )
            after_state.sync_public_round_state(snapshot)
            illegal = after_state.apply_operation_list(player, apply_operations)

            assert cpp_out["can_apply"] == expected_can_apply
            assert cpp_out["operation_income"] == expected_income
            assert cpp_out["illegal"] == [_operation_tokens(operation) for operation in illegal]
            assert cpp_out["terminal"] == after_state.terminal
            assert cpp_out["winner"] == (-1 if after_state.winner is None else after_state.winner)
            assert cpp_out["metrics"]["tower_count"] == query_state.tower_count(player)
            assert cpp_out["metrics"]["nearest_ant_distance"] == query_state.nearest_ant_distance(player)
            assert cpp_out["metrics"]["frontline_distance"] == query_state.frontline_distance(player)
            assert cpp_out["metrics"]["safe_coin_threshold"] == query_state.safe_coin_threshold(player)
            assert cpp_out["metrics"]["tower_spread_score"] == pytest.approx(query_state.tower_spread_score(player))
            expected_slot_priorities = [
                query_state.slot_priority(player, x, y)
                for x, y in STRATEGIC_BUILD_ORDER[player][:6]
            ]
            assert cpp_out["metrics"]["slot_priorities"] == pytest.approx(expected_slot_priorities)
            assert _normalize_cpp_public_round_state(cpp_out["state"]) == _normalize_python_public_round_state(
                after_state.to_public_round_state()
            )


def test_cpp_sdk_lightning_storm_matches_python_evasion_blocking() -> None:
    seed = 2
    storm = Operation(OperationType.USE_LIGHTNING_STORM, 6, 12)
    turns = [([], []) for _ in range(21)]
    turns.append(([storm], []))

    python_state = GameState.initial(
        seed=seed,
        movement_policy=MOVEMENT_POLICY_ENHANCED,
        cold_handle_rule_illegal=True,
    )
    for _ in range(21):
        python_state.resolve_turn([], [])

    storm_range = SUPER_WEAPON_STATS[SuperWeaponType.LIGHTNING_STORM].attack_range
    target_before = {
        ant.ant_id: (ant.hp, ant.shield)
        for ant in python_state.ants
        if ant.player == 1
        and ant.kind == AntKind.COMBAT
        and ant.shield > 0
        and hex_distance(ant.x, ant.y, storm.arg0, storm.arg1) <= storm_range
    }
    assert target_before

    python_state.resolve_turn([storm], [])
    target_after = {ant.ant_id: (ant.hp, ant.shield) for ant in python_state.ants}
    assert any(
        ant_id in target_after
        and target_after[ant_id][0] == before_hp
        and target_after[ant_id][1] == before_shield - 1
        for ant_id, (before_hp, before_shield) in target_before.items()
    )

    payload = _trace_request(
        seed=seed,
        movement_policy=MOVEMENT_POLICY_ENHANCED,
        cold_handle_rule_illegal=True,
        turns=turns,
    )
    native_trace = _run_cpp_sdk_runner({"mode": "native_trace", **payload})["trace"]
    game_trace = _run_cpp_sdk_runner({"mode": "game_trace", **payload})["trace"]
    expected_state = _normalize_python_public_round_state(python_state.to_public_round_state())
    expected_without_effects = {key: value for key, value in expected_state.items() if key != "active_effects"}

    native_state = _normalize_cpp_public_round_state(native_trace[-1]["state"])
    game_state = _normalize_cpp_public_round_state(game_trace[-1]["state"])

    assert {key: value for key, value in native_state.items() if key != "active_effects"} == expected_without_effects
    assert {key: value for key, value in game_state.items() if key != "active_effects"} == expected_without_effects


def test_cpp_sdk_public_state_same_turn_emp_blocks_later_player_tower_op() -> None:
    seed = 0
    build_x, build_y = STRATEGIC_BUILD_ORDER[1][0]
    emp = Operation(OperationType.USE_EMP_BLASTER, build_x, build_y)
    build = Operation(OperationType.BUILD_TOWER, build_x, build_y)

    python_state = GameState.initial(seed=seed, movement_policy=MOVEMENT_POLICY_ENHANCED)
    python_state.coins[0] = 200
    snapshot = python_state.to_public_round_state()

    first_eval = _run_cpp_sdk_runner(
        {
            "mode": "public_eval",
            "seed": seed,
            "movement_policy": MOVEMENT_POLICY_ENHANCED,
            "cold_handle_rule_illegal": False,
            "player": 0,
            "public_state": _public_round_state_to_payload(snapshot),
            "query_operations": [_operation_tokens(emp)],
            "apply_operations": [_operation_tokens(emp)],
            "slot_points": [],
        }
    )
    state_after_emp = first_eval["state"]

    python_after_emp = GameState.initial(seed=seed, movement_policy=MOVEMENT_POLICY_ENHANCED)
    python_after_emp.sync_public_round_state(snapshot)
    python_after_emp.apply_operation_list(0, [emp])
    assert python_after_emp.can_apply_operation(1, build) is False

    second_eval = _run_cpp_sdk_runner(
        {
            "mode": "public_eval",
            "seed": seed,
            "movement_policy": MOVEMENT_POLICY_ENHANCED,
            "cold_handle_rule_illegal": False,
            "player": 1,
            "public_state": state_after_emp,
            "query_operations": [_operation_tokens(build)],
            "apply_operations": [],
            "slot_points": [],
        }
    )

    assert second_eval["can_apply"] == [False]


def test_cpp_sdk_public_advance_keeps_basic_range_one() -> None:
    seed = 0
    baseline_state = GameState.initial(seed=seed, movement_policy=MOVEMENT_POLICY_ENHANCED)
    baseline_state.towers = [Tower(0, 0, 6, 9, TowerType.BASIC, cooldown_clock=0.0, hp=10)]
    baseline_state.ants = [
        Ant(
            0,
            1,
            7,
            7,
            hp=20,
            level=0,
            kind=AntKind.WORKER,
            behavior=AntBehavior.DEFAULT,
        )
    ]
    public_state = baseline_state.to_public_round_state()

    python_state = GameState.initial(seed=seed, movement_policy=MOVEMENT_POLICY_ENHANCED)
    python_state.sync_public_round_state(public_state)
    python_state.advance_round()
    tracked_ant = next(ant for ant in python_state.ants if ant.ant_id == 0)
    assert tracked_ant.hp == 20

    cpp_out = _run_cpp_sdk_runner(
        {
            "mode": "public_advance",
            "seed": seed,
            "movement_policy": MOVEMENT_POLICY_ENHANCED,
            "cold_handle_rule_illegal": False,
            "public_state": _public_round_state_to_payload(public_state),
            "steps": 1,
        }
    )

    assert _normalize_cpp_public_round_state(cpp_out["state"]) == _normalize_python_public_round_state(
        python_state.to_public_round_state()
    )
