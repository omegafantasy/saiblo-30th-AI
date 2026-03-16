from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Tuple, TypeVar

from .rawio import write_to_judger, debug

from .gamedata import Ant, Tower, TowerType, SuperWeaponType

from .coord import Coord


def _read_line_of_int() -> list[int]:
    return [int(s) for s in input().split(' ')]


T = TypeVar("T")


def _read_list(read_func: Callable[[], T]) -> list[T]:
    n = int(input())
    return [read_func() for i in range(n)]


@dataclass
class InitInfo:
    my_seat: int
    seed: int


def read_init_info() -> InitInfo:
    """
    读取游戏初始化信息。
    :return: 游戏初始化信息，包括当前玩家的位置/先后手和信息素初始化种子。
    """
    part = _read_line_of_int()
    debug(f"{part}")
    return InitInfo(part[0], part[1])


class OperationType(IntEnum):
    BUILD_TOWER = 11
    UPGRADE_TOWER = 12
    DOWNGRADE_TOWER = 13
    DEPLOY_LIGHTNING_STORM = 21
    DEPLOY_EMP_BLASTER = 22
    DEPLOY_DEFLECTORS = 23
    DEPLOY_EMERGENCY_EVASION = 24
    UPGRADE_GENERATE_SPEED = 31
    UPGRADE_ANT_MAXHP = 32


@dataclass
class Operation:
    type: OperationType
    arg0: int = -1
    arg1: int = -1

    def dump(self) -> str:
        res = str(self.type.value)
        if self.arg0 >= 0:
            res += " " + str(self.arg0)
        if self.arg1 >= 0:
            res += " " + str(self.arg1)
        return res


def build_tower_op(coord: Coord) -> Operation:
    """
    创建新建防御塔操作
    :param coord: 指定的建造位置
    :return: 创建的操作对象
    """
    return Operation(OperationType.BUILD_TOWER, coord.x, coord.y)


def upgrade_tower_op(id: int, type: TowerType) -> Operation:
    """
    创建升级防御塔操作
    :param id: 需要升级的防御塔的ID编号
    :param type: 要升级到的防御塔类型
    :return: 创建的操作对象
    """
    return Operation(OperationType.UPGRADE_TOWER, id, type.value)


def downgrade_tower_op(id: int) -> Operation:
    """
    创建降级防御塔操作。对BASIC防御塔进行降级即为拆除。
    :param id: 要降级/拆除对防御塔ID编号
    :return: 创建的操作对象
    """
    return Operation(OperationType.DOWNGRADE_TOWER, id)


def deploy_super_weapon_op(type: SuperWeaponType, coord: Coord) -> Operation:
    """
    创建部署超级武器的操作。
    :param type: 部署的超级武器类型
    :param coord: 部署的坐标
    :return: 创建的操作对象
    """
    type_to_op = [
        OperationType.DEPLOY_LIGHTNING_STORM,
        OperationType.DEPLOY_EMP_BLASTER,
        OperationType.DEPLOY_DEFLECTORS,
        OperationType.DEPLOY_EMERGENCY_EVASION,
    ]
    return Operation(type_to_op[type.value - 1], coord.x, coord.y)


def upgrade_generate_speed_op() -> Operation:
    """
    创建升级蚂蚁生成速度的操作
    :return: 创建的操作对象
    """
    return Operation(OperationType.UPGRADE_GENERATE_SPEED)


def upgrade_ant_maxhp_op() -> Operation:
    """
    创建升级蚂蚁最大生命值的操作
    :return: 创建的操作对象
    """
    return Operation(OperationType.UPGRADE_ANT_MAXHP)


def read_enemy_operations() -> list[Operation]:
    """
    读取对手的操作列表
    :return: 对手的操作列表
    """
    def read_operation() -> Operation:
        parts = _read_line_of_int()
        op_type = OperationType(parts[0])
        if (
                op_type == OperationType.UPGRADE_GENERATE_SPEED
                or op_type == OperationType.UPGRADE_ANT_MAXHP
        ):
            return Operation(op_type)
        if op_type == OperationType.DOWNGRADE_TOWER:
            return Operation(op_type, parts[1])
        return Operation(op_type, parts[1], parts[2])

    return _read_list(read_operation)


def write_our_operation(ops: list[Operation]) -> None:
    """
    向评测机输出我方的操作列表
    :param ops: 我方的操作列表
    """
    msg = str(len(ops)) + "\n"
    for op in ops:
        msg += op.dump() + "\n"
    write_to_judger(msg)


@dataclass
class RoundInfo:
    round: int
    towers: list[Tower]
    ants: list[Ant]
    coin: Tuple[int, int]
    hp: Tuple[int, int]


def read_round_info() -> RoundInfo:
    def read_one_int() -> int:
        return int(input())

    def read_two_ints() -> Tuple[int, int]:
        parts = _read_line_of_int()
        return parts[0], parts[1]

    def read_tower() -> Tower:
        parts = _read_line_of_int()
        return Tower(parts[0], parts[1], Coord(parts[2], parts[3]), parts[4], parts[5])

    def read_ant() -> Ant:
        parts = _read_line_of_int()
        return Ant(
            parts[0],
            parts[1],
            parts[4],
            Ant.maxhp_of_level(parts[5]),
            Coord(parts[2], parts[3]),
            parts[5],
            parts[6],
            0,
            parts[7],
        )

    return RoundInfo(
        read_one_int(),
        _read_list(read_tower),
        _read_list(read_ant),
        read_two_ints(),
        read_two_ints(),
    )
