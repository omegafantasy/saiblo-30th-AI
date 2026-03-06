# 本文件定义了游戏状态类，以及负责初始化将军，更新回合的函数
import math
import random
from dataclasses import dataclass, field

from logic.constant import *
from logic.gamedata import (
    Cell,
    CellType,
    Farmer,
    Generals,
    MainGenerals,
    SubGenerals,
    SuperWeapon,
    WeaponType,
    init_coin,
)
from logic.generate_round_replay import get_single_round_replay
from logic.super_weapons import *
from logic.upgrade import *


@dataclass
class GameState:
    replay_file: str = "default_replay.json"
    round: int = 1  # 当前游戏回合数
    generals: list[Generals] = field(default_factory=list)  # 游戏中的将军列表，用于通信
    coin: list[int] = field(
        default_factory=lambda: [init_coin() for p in range(2)]
    )  # 每个玩家的金币数量列表，分别对应玩家1，玩家2
    active_super_weapon: list[SuperWeapon] = field(default_factory=list)
    super_weapon_unlocked: list[bool] = field(
        default_factory=lambda: [False, False]
    )  # 超级武器是否解锁的列表，解锁了是true，分别对应玩家1，玩家2

    super_weapon_cd: list[int] = field(
        default_factory=lambda: [-1, -1]
    )  # 超级武器的冷却回合数列表，分别对应玩家1，玩家2

    tech_level: list[list[int]] = field(
        default_factory=lambda: [[2, 0, 0, 0], [2, 0, 0, 0]]
    )
    # 科技等级列表，第一层对应玩家一，玩家二，第二层分别对应行动力，攀岩，免疫沼泽，超级武器

    rest_move_step: list[int, int] = field(default_factory=lambda: [2, 2])

    board: list[list[Cell]] = field(
        default_factory=lambda: [
            [Cell(position=[i, j]) for j in range(col)] for i in range(row)
        ]
    )  # 游戏棋盘的二维列表，每个元素是一个Cell对象

    changed_cells: list[list[int, int]] = field(default_factory=lambda: [])
    next_generals_id: int = 0
    winner: int = -1

    def find_general_position_by_id(self, general_id: int):
        for gen in self.generals:
            if gen.id == general_id:
                return gen.position
        return None

    def trans_state_to_init_json(self, player):
        result = get_single_round_replay(
            self,
            [[int(i / row), i % row] for i in range(row * col)],
            player,
            [8],
            set([gen.id for gen in self.generals]),
        )
        cell_type = ""
        for i in range(row * col):
            cell_type += str(int(self.board[int(i / row)][i % row].type))
        result["Cell_type"] = cell_type
        return result


def generate_general_points():
    x1 = random.randint(0, 14)
    y1 = random.randint(0, 14)
    x2 = random.randint(0, 14)
    y2 = random.randint(0, 14)
    return (x1, y1), (x2, y2)


def manhattan_distance(point1, point2):
    x1, y1 = point1
    x2, y2 = point2
    return abs(x1 - x2) + abs(y1 - y2)


import random


def connect_points(board, start, end):
    x1, y1 = start
    x2, y2 = end

    # 随机选择横向或纵向移动
    while x1 != x2 or y1 != y2:
        if x1 != x2 and y1 != y2:
            # 随机选择横向或纵向移动
            direction = random.choice(["x", "y"])
        elif x1 != x2:
            direction = "x"
        else:
            direction = "y"

        if direction == "x":
            x_step = 1 if x1 < x2 else -1
            x1 += x_step
            board[x1][y1].type = CellType(0)
        else:
            y_step = 1 if y1 < y2 else -1
            y1 += y_step
            board[x1][y1].type = CellType(0)

    # 将目标位置设为 0
    board[x2][y2].type = CellType(0)


def init_generals(gamestate: GameState):
    # init random position
    while True:
        point1, point2 = generate_general_points()
        distance = manhattan_distance(point1, point2)
        if distance > 18:
            break
    mainpos = [point1, point2]
    # generate main generals
    for player in range(2):
        gen = MainGenerals(player=player, id=gamestate.next_generals_id)
        gamestate.next_generals_id += 1
        x = mainpos[player][0]
        y = mainpos[player][1]
        gen.position[0] = x
        gen.position[1] = y
        gamestate.generals.append(gen)
        gamestate.board[x][y].generals = gen
        gamestate.board[x][y].type = CellType(0)
        gamestate.board[x][y].player = player
    if not is_connected(gamestate.board, point1, point2):
        connect_points(gamestate.board, point1, point2)
        connect_points(gamestate.board, point1, point2)
    positions = []
    positions_mountain = []
    for i in range(row):
        for j in range(col):
            if (
                gamestate.board[i][j].type == CellType(0)
                and not gamestate.board[i][j].generals
            ):
                positions.append([i, j])
            if gamestate.board[i][j].type == CellType(2):
                positions_mountain.append([i, j])
    random.shuffle(positions)
    random.shuffle(positions_mountain)
    # generate sub generals
    for player in range(subgen_num):
        gen = SubGenerals(player=-1, id=gamestate.next_generals_id)
        gamestate.next_generals_id += 1
        pos = positions.pop()
        gen.position[0] = pos[0]
        gen.position[1] = pos[1]
        gamestate.generals.append(gen)
        gamestate.board[pos[0]][pos[1]].generals = gen
        gamestate.board[pos[0]][pos[1]].army = random.randint(10, 20)

    # generate farmer
    for i in range(farmer_num - 3):
        gen = Farmer(player=-1, produce_level=1, id=gamestate.next_generals_id)
        gamestate.next_generals_id += 1
        pos = positions.pop()
        gen.position[0] = pos[0]
        gen.position[1] = pos[1]
        gamestate.generals.append(gen)
        gamestate.board[pos[0]][pos[1]].generals = gen
        gamestate.board[pos[0]][pos[1]].army = random.randint(3, 5)

    for i in range(3):
        gen = Farmer(player=-1, produce_level=1, id=gamestate.next_generals_id)
        gamestate.next_generals_id += 1
        pos = positions_mountain.pop()
        gen.position[0] = pos[0]
        gen.position[1] = pos[1]
        gamestate.generals.append(gen)
        gamestate.board[pos[0]][pos[1]].generals = gen
        gamestate.board[pos[0]][pos[1]].army = random.randint(3, 5)


def update_round(gamestate: GameState):
    changed = set()
    for i in range(row):
        for j in range(col):
            # 将军
            if gamestate.board[i][j].generals != None:
                gamestate.board[i][j].generals.rest_move = gamestate.board[i][
                    j
                ].generals.mobility_level
            if isinstance(gamestate.board[i][j].generals, MainGenerals):
                gamestate.board[i][j].army += gamestate.board[i][
                    j
                ].generals.produce_level
                changed.add(i * row + j)
            elif isinstance(gamestate.board[i][j].generals, SubGenerals):
                if gamestate.board[i][j].generals.player != -1:
                    gamestate.board[i][j].army += gamestate.board[i][
                        j
                    ].generals.produce_level
                    changed.add(i * row + j)
            elif isinstance(gamestate.board[i][j].generals, Farmer):
                if gamestate.board[i][j].generals.player != -1:
                    gamestate.coin[
                        gamestate.board[i][j].generals.player
                    ] += gamestate.board[i][j].generals.produce_level
            # 每25回合增兵
            if gamestate.round % 10 == 0:
                if gamestate.board[i][j].player != -1:
                    gamestate.board[i][j].army += 1
                    changed.add(i * row + j)
            # 沼泽减兵
            if (
                gamestate.board[i][j].type == CellType(1)
                and gamestate.board[i][j].player != -1
                and gamestate.board[i][j].army > 0
            ):
                if gamestate.tech_level[gamestate.board[i][j].player][2] == 0:
                    gamestate.board[i][j].army -= 1
                    if (
                        gamestate.board[i][j].army == 0
                        and gamestate.board[i][j].generals == None
                    ):
                        gamestate.board[i][j].player = -1
                    changed.add(i * row + j)

    # 超级武器判定
    for weapon in gamestate.active_super_weapon:
        if weapon.type == WeaponType(0):
            for _i in range(
                max(0, weapon.position[0] - 1), min(row, weapon.position[0] + 2)
            ):
                for _j in range(
                    max(0, weapon.position[1] - 1), min(col, weapon.position[1] + 2)
                ):
                    if gamestate.board[_i][_j].army > 0:
                        gamestate.board[_i][_j].army = max(
                            0, gamestate.board[_i][_j].army - 3
                        )
                        gamestate.board[_i][_j].player = (
                            -1
                            if (
                                gamestate.board[_i][_j].army == 0
                                and gamestate.board[_i][_j].generals == None
                            )
                            else gamestate.board[_i][_j].player
                        )
                        changed.add(_i * row + _j)

    # 更新超级武器信息
    gamestate.super_weapon_cd = [
        i - 1 if i > 0 else i for i in gamestate.super_weapon_cd
    ]
    for weapon in gamestate.active_super_weapon:
        weapon.rest -= 1
    # cd和duration 减少
    for gen in gamestate.generals:
        gen.skills_cd = [i - 1 if i > 0 else i for i in gen.skills_cd]
        gen.skill_duration = [i - 1 if i > 0 else i for i in gen.skill_duration]
    # 移动步数恢复
    gamestate.rest_move_step = [gamestate.tech_level[0][0], gamestate.tech_level[1][0]]

    # 生成回放
    replay = get_single_round_replay(
        gamestate, [[int(i / row), i % row] for i in changed], -1, [8]
    )
    with open(gamestate.replay_file, "a") as f:
        f.write(str(replay).replace("'", '"') + "\n")
    f.close()

    gamestate.active_super_weapon = list(
        filter(lambda x: (x.rest > 0), gamestate.active_super_weapon)
    )

    gamestate.round += 1


# 定义四个方向的移动
dx = [-1, 0, 1, 0]
dy = [0, 1, 0, -1]


def is_valid(board, x, y):
    m = len(board)
    n = len(board[0])
    return 0 <= x < m and 0 <= y < n and board[x][y].type == CellType(0)


# 定义一个函数，使用 DFS 来遍历棋盘上的连通区域
def dfs(board, x, y, visited):
    # 将当前位置标记为已访问
    visited[x][y] = True
    # 遍历四个方向
    for i in range(4):
        # 计算下一个位置的坐标
        nx = x + dx[i]
        ny = y + dy[i]
        # 如果下一个位置是有效的，且没有被访问过，继续 DFS
        if is_valid(board, nx, ny) and not visited[nx][ny]:
            dfs(board, nx, ny, visited)


# 定义一个函数，判断两个位置是否联通
def is_connected(board, p1, p2):
    # 获取棋盘的行数和列数
    m = len(board)
    n = len(board[0])
    # 获取两个位置的坐标
    x1, y1 = p1
    x2, y2 = p2
    # 判断两个位置是否有效
    if not is_valid(board, x1, y1) or not is_valid(board, x2, y2):
        return False
    # 创建一个二维数组，记录每个位置是否被访问过
    visited = [[False] * n for _ in range(m)]
    # 从第一个位置开始 DFS
    dfs(board, x1, y1, visited)
    # 返回第二个位置是否被访问过
    return visited[x2][y2]
