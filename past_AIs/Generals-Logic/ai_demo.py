import json
import os
import sys
from typing import Callable

import logic.constant as constant
from logic.execute import execute_single_command
from logic.constant import col, row
from logic.gamedata import (
    CellType,
    Direction,
    Farmer,
    MainGenerals,
    SkillType,
    SubGenerals,
    WeaponType,
)
from logic.gamestate import GameState, update_round

Fake_ID = 0  # 测试用，指定读取json中哪个玩家的操作


def move_army_op(position: list[int, int], direction: Direction, num: int):
    return [1, position[0], position[1], int(direction) + 1, num]


def move_general_op(id: int, new_pos: list[int, int]):
    return [2, id, new_pos[0], new_pos[1]]


def update_general_production_level_op(id: int):
    return [3, id, 1]


def update_defence_level_op(id: int):
    return [3, id, 2]


def update_general_mobility_level_op(id: int):
    return [3, id, 3]


def release_general_skill_op(
    id: int, skill: SkillType, destination: list[int, int] = [-1, -1]
):
    if skill == SkillType.SURPRISE_ATTACK or skill == SkillType.ROUT:
        return [4, id, int(skill) + 1, destination[0], destination[1]]
    return [4, id, int(skill) + 1]


def update_army_mobility_op():
    return [5, 1]


def unlock_montaineering_op():
    return [5, 2]


def unlock_swap_immunity_op():
    return [5, 3]


def unlock_superwapon_op():
    return [5, 4]


def use_superweapon_op(
    superweapon_type: WeaponType, position: list[int, int], starting_pos: list[int, int]
):
    if superweapon_type == WeaponType.TRANSMISSION:
        return [6, 3, position[0], position[1], starting_pos[0], starting_pos[1]]
    return [6, int(superweapon_type) + 1, position[0], position[1]]


def call_subgeneral_op(position: list[int, int]):
    return [7, position[0], position[1]]


def load_map() -> tuple[int, GameState]:
    gamestate = GameState()
    dict_str = sys.stdin.buffer.readline().decode("utf-8")
    # print(dict_str, file=sys.stderr)
    dict = json.loads(dict_str)
    my_seat = dict["Player"]
    map = dict["Cells"]
    types = dict["Cell_type"]
    generals = dict["Generals"]
    for i in range(len(map)):
        gamestate.board[int(i / row)][i % col].type = CellType(int(types[i]))
        gamestate.board[int(i / row)][i % col].player = map[i][1]
        gamestate.board[int(i / row)][i % col].army = map[i][2]
    for i in range(len(generals)):
        id, player = generals[i]["Id"], generals[i]["Player"]
        position = generals[i]["Position"]
        if generals[i]["Type"] == 1:
            general = MainGenerals(id, player, position)
        elif generals[i]["Type"] == 2:
            general = SubGenerals(id, player, position)
        else:
            general = Farmer(id, player, position)
        gamestate.generals.append(general)
        gamestate.board[position[0]][position[1]].generals = general
    gamestate.coin = dict["Coins"]
    return my_seat, gamestate


def read_enemy_operations() -> list[list[int]]:
    operations: list[list[int]] = []
    while True:
        op = input()
        operations.append([int(i) for i in op.split()])
        if op == "8":
            break
        else:
            print("read operations ", op, file=sys.stderr)
    return operations


def write_to_judger(msg: str) -> None:
    """
    按照4+N协议将消息输出给评测机

    :param msg: 需要输出的消息
    :type msg: str
    """
    sys.stdout.buffer.write(
        int.to_bytes(len(msg), length=4, byteorder="big", signed=False)
    )
    sys.stdout.buffer.write(msg.encode())
    sys.stdout.buffer.flush()


class GameController:
    """游戏控制器。可以帮助选手处理通讯与数据维护有关的繁琐操作。"""

    my_seat: int = 0  #: 您的位置。0代表您是先手，1代表您是后手。
    game_state: GameState = GameState()  #: 游戏状态，一个 :class:`.gamestate.GameState` 对象
    my_operation_list: list[list[int]] = []  #: 我方未发送的操作列表

    def init(self) -> None:
        """初始化游戏"""
        self.my_seat, self.game_state = load_map()

    def read_enemy_ops(self) -> list[list[int]]:
        """读取敌方操作列表"""
        return read_enemy_operations()

    def apply_enemy_ops(self, ops: list[list[int]]) -> bool:
        """应用敌方操作。如果返回``False``说明敌方操作不合法。"""
        for op in ops:
            if not execute_single_command(
                1 - self.my_seat, self.game_state, op[0], op[1:]
            ):
                return False
        return True

    def read_and_apply_enemy_ops(self) -> bool:
        """读取并应用敌方操作。如果返回``False``说明敌方操作不合法。"""
        return self.apply_enemy_ops(self.read_enemy_ops())

    def try_apply_our_op(self, op: list[int]) -> bool:
        """尝试执行我方操作。如果返回``False``说明我方操作不合法。"""
        if execute_single_command(self.my_seat, self.game_state, op[0], op[1:]):
            self.my_operation_list.append(op)
            return True
        return False

    def try_apply_our_ops(self, ops: list[list[int]]) -> bool:
        """尝试执行我方若干操作。如果返回``False``说明我方操作不合法，并停止执行后面的操作。"""
        for op in ops:
            if not self.try_apply_our_op(op):
                return False
        return True

    def finish_and_send_our_ops(self) -> None:
        """结束我方操作回合，将操作列表打包发送并清空。"""
        msg = ""
        for op in self.my_operation_list:
            msg = msg + " ".join(str(param) for param in op) + "\n"
        msg += "8\n"
        write_to_judger(msg)
        self.my_operation_list = []


def run_ai(ai_func: Callable[[int, GameState], list[list[int]]]) -> None:
    """
    执行AI。将你的决策过程封装在一个函数中，我们帮你处理各类通讯相关的繁琐事项。
    如果你不喜欢这么做，也可以直接把下面的代码复制到你的主函数中重复利用。

    :param ai_func: 你的决策函数，第一个参数为``my_seat``，第二个参数为当前的 :class:`.gamestate.GameState` 对象。
    """
    game = GameController()
    game.init()
    round = 1
    while True:
        if game.my_seat == 0:
            ops = ai_func(round, 0, game.game_state)
            # print("round", game.game_state.round, ",", ops, file=sys.stderr)
            game.try_apply_our_ops(ops)
            game.finish_and_send_our_ops()
            game.read_and_apply_enemy_ops()
            update_round(game.game_state)
        else:
            game.read_and_apply_enemy_ops()
            ops = ai_func(round, 1, game.game_state)
            # print("round", game.game_state.round, ",", ops, file=sys.stderr)
            game.try_apply_our_ops(ops)
            game.finish_and_send_our_ops()
            update_round(game.game_state)
        round += 1


# def load_operation_from_json() -> list[list[list[int]]]:
#     """测试用，从json中读取操作"""
#     with open(os.getcwd() + "/test_config/operation1.json", "r") as f:
#         op_data = json.load(f)
#     all_commands = op_data["operation"]
#     round = 1
#     my_commands = [[], []]
#     for command in all_commands:
#         if command == []:
#             round += 1
#             my_commands.append([])
#             continue
#         if command[0] == Fake_ID:
#             my_commands[-1].append(command)
#     return my_commands


# def make_move_from_json(round: int, my_seat: int, state: GameState) -> list[list[int]]:
#     """测试用，使用json中的操作"""
#     return my_commands[round]

import random


def example_ai(round: int, my_seat: int, state: GameState) -> list[list[int]]:
    """一个AI示例"""
    return [
        move_army_op(
            state.generals[my_seat].position, Direction(random.randint(0, 3)), 1
        )
    ]


# my_commands = load_operation_from_json()
# run_ai(make_move_from_json)
run_ai(example_ai)
