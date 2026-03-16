from dataclasses import dataclass, field
from enum import IntEnum

from .coord import Coord


def init_hp() -> int:
    return 50


def init_coin() -> int:
    return 50


class AntState(IntEnum):
    ALIVE = 0
    SUCCESS = 1
    FAIL = 2
    TOO_OLD = 3
    FROZEN = 4


@dataclass
class Ant:
    id: int
    player: int
    hp: int
    maxhp: int
    coord: Coord
    level: int
    age: int
    evasion_count: int
    state: AntState
    path: list[Coord] = field(default_factory=list)

    @staticmethod
    def upgrade_cost(level: int) -> int:
        return [200, 250][level]

    @staticmethod
    def maxhp_of_level(level: int) -> int:
        return [10, 25, 50][level]

    @staticmethod
    def coin_of_level(level: int) -> int:
        return [3, 5, 7][level]

    @staticmethod
    def gen_speed_of_level(level: int) -> int:
        return [4, 2, 1][level]

    @staticmethod
    def max_age() -> int:
        return 32


class TowerType(IntEnum):
    BASIC = 0
    HEAVY = 1
    HEAVY_PLUS = 11
    ICE = 12
    CANNON = 13
    QUICK = 2
    QUICK_PLUS = 21
    DOUBLE = 22
    SNIPER = 23
    MORTAR = 3
    MORTAR_PLUS = 31
    PULSE = 32
    MISSILE = 33


def can_tower_upgrade_to(t0: TowerType, t1: TowerType) -> bool:
    return t1 != TowerType.BASIC and t0.value == t1.value // 10


@dataclass
class TowerConfig:
    damage: int
    interval: int
    range: int
    aoe: int


@dataclass
class Tower:
    id: int
    player: int
    coord: Coord
    type: TowerType
    cd: int

    def damage(self) -> int:
        return Tower.config_of_type(self.type).damage

    def interval(self) -> int:
        return Tower.config_of_type(self.type).interval

    def reset_cd(self) -> None:
        self.cd = self.interval()

    def range(self) -> int:
        return Tower.config_of_type(self.type).range

    def aoe(self) -> int:
        return Tower.config_of_type(self.type).aoe

    @staticmethod
    def config_of_type(ttype: TowerType) -> TowerConfig:
        config_map = {
            TowerType.BASIC: TowerConfig(5, 2, 2, 0),
            TowerType.HEAVY: TowerConfig(15, 2, 2, 0),
            TowerType.HEAVY_PLUS: TowerConfig(35, 2, 2, 0),
            TowerType.ICE: TowerConfig(15, 2, 2, 0),
            TowerType.CANNON: TowerConfig(50, 4, 3, 0),
            TowerType.QUICK: TowerConfig(6, 1, 3, 0),
            TowerType.QUICK_PLUS: TowerConfig(8, 1, 3, 0),
            TowerType.DOUBLE: TowerConfig(10, 1, 4, 0),
            TowerType.SNIPER: TowerConfig(13, 2, 6, 0),
            TowerType.MORTAR: TowerConfig(16, 4, 3, 1),
            TowerType.MORTAR_PLUS: TowerConfig(35, 4, 4, 1),
            TowerType.PULSE: TowerConfig(30, 3, 2, 2),
            TowerType.MISSILE: TowerConfig(45, 6, 5, 2),
        }
        return config_map[ttype]


class SuperWeaponType(IntEnum):
    LIGHTNING_STORM = 1
    EMP_BLASTER = 2
    DEFLECTORS = 3
    EMERGENCY_EVASION = 4


@dataclass
class SuperWeaponConfig:
    cost: int
    cd: int
    duration: int
    range: int


@dataclass
class SuperWeapon:
    player: int
    type: SuperWeaponType
    coord: Coord
    duration: int = 0

    def init_duration(self):
        self.duration = SuperWeapon.config_of_type(self.type).duration

    def cost(self) -> int:
        return SuperWeapon.config_of_type(self.type).cost

    def cd(self) -> int:
        return SuperWeapon.config_of_type(self.type).cd

    def range(self) -> int:
        return SuperWeapon.config_of_type(self.type).range

    @staticmethod
    def config_of_type(swtype: SuperWeaponType) -> SuperWeaponConfig:
        config_map = {
            SuperWeaponType.LIGHTNING_STORM: SuperWeaponConfig(150, 100, 20, 3),
            SuperWeaponType.EMP_BLASTER: SuperWeaponConfig(150, 100, 20, 3),
            SuperWeaponType.DEFLECTORS: SuperWeaponConfig(100, 50, 10, 3),
            SuperWeaponType.EMERGENCY_EVASION: SuperWeaponConfig(100, 50, 2, 3),
        }
        return config_map[swtype]
