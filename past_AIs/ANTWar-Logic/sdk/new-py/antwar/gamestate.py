# pylint: disable=invalid-name, missing-module-docstring, missing-class-docstring, too-few-public-methods, no-member
from dataclasses import dataclass, field
from random import random
from typing import Optional, TypeVar
from .coord import Coord, is_player_highland, distance, neighbor, headquarter_coord
from .gamedata import (
    AntState,
    Ant,
    TowerType,
    Tower,
    SuperWeaponType,
    SuperWeapon,
    can_tower_upgrade_to,
    init_coin,
    init_hp,
)
from .pheromone import Pheromone, generate_init_pheromone
from .protocol import Operation, OperationType

T = TypeVar("T")


def _find_idx_by_id(lst: list[T], id: int) -> int:
    for i, ele in enumerate(lst):
        if ele.id == id:
            return i
    return -1


def _find_by_id(lst: list[T], id: int) -> Optional[T]:
    for ele in lst:
        if ele.id == id:
            return ele
    return None


def _find_by_coord(lst: list[T], coord: Coord) -> list[T]:
    return list(filter(lambda ele: ele.coord == coord, lst))


@dataclass
class GameState:
    round: int = 0
    ants: list[Ant] = field(default_factory=list)
    towers: list[Tower] = field(default_factory=list)
    coin: list[int] = field(default_factory=lambda: [init_coin() for p in range(2)])
    hp: list[int] = field(default_factory=lambda: [init_hp() for p in range(2)])
    active_super_weapon: list[SuperWeapon] = field(default_factory=list)
    super_weapon_cd: list[list[int]] = field(default_factory=lambda: [[0, 0, 0, 0], [0, 0, 0, 0]])
    phero: list[Pheromone] = field(default_factory=lambda: [Pheromone(), Pheromone()])
    gen_speed_lv: list[int] = field(default_factory=lambda: [0, 0])
    ant_maxhp_lv: list[int] = field(default_factory=lambda: [0, 0])

    next_ant_id: int = 0
    next_tower_id: int = 0

    __mini_replay_name: str = f"mini-replay-{int(random() * 10000)}.txt"

    def init_with_seed(self, seed: int) -> None:
        p0, p1 = generate_init_pheromone(seed)
        self.phero = [p0, p1]

    def ant_idx_of_id(self, id: int) -> int:
        return _find_idx_by_id(self.ants, id)

    def ant_of_id(self, id: int) -> Optional[Ant]:
        return _find_by_id(self.ants, id)

    def ant_at(self, coord: Coord) -> list[Ant]:
        return _find_by_coord(self.ants, coord)

    def tower_idx_of_id(self, id: int) -> int:
        return _find_idx_by_id(self.towers, id)

    def tower_of_id(self, id: int) -> Optional[Tower]:
        return _find_by_id(self.towers, id)

    def tower_at(self, coord: Coord) -> Optional[Tower]:
        lst = _find_by_coord(self.towers, coord)
        if len(lst) > 0:
            return lst[0]
        return None

    def build_tower(self, player: int, coord: Coord) -> Optional[Tower]:
        if not is_player_highland(coord, player):
            return None
        t = Tower(self.next_tower_id, player, coord, TowerType.BASIC, 0)
        t.reset_cd()
        self.towers.append(t)
        self.next_tower_id += 1
        return t

    def upgrade_tower(self, id: int, ttype: TowerType) -> Optional[Tower]:
        t = self.tower_of_id(id)
        if t is None:
            return None
        if not can_tower_upgrade_to(t.type, ttype):
            return None
        t.type = ttype
        t.reset_cd()
        return t

    def downgrade_tower(self, id: int) -> Optional[Tower]:
        t = self.tower_of_id(id)
        if t is None:
            return None
        if t.type == TowerType.BASIC:
            self.towers.pop(self.tower_idx_of_id(id))
        else:
            t.type = TowerType(t.type // 10)
            t.reset_cd()
        return t

    def build_tower_cost(self, player: int) -> int:
        exist_tower_count = len(list(filter(lambda t: t.player == player, self.towers)))
        return 15 * (2 ** exist_tower_count)

    def upgrade_tower_cost(self, ttype: TowerType) -> int:
        if ttype.value > 10:
            return 200
        if ttype.value > 0:
            return 60
        return -1

    def downgrade_tower_income(self, id: int) -> int:
        t = self.tower_of_id(id)
        if t is None:
            return -1
        if t.type.value > 10:
            return 160
        if t.type.value > 0:
            return 48
        if t.type.value == 0:
            return int(self.build_tower_cost(t.player) * 0.4)

    def upgrade_generate_speed(self, player: int) -> bool:
        if self.gen_speed_lv[player] >= 2:
            return False
        self.gen_speed_lv[player] += 1
        return True

    def upgrade_ant_maxhp(self, player: int) -> bool:
        if self.ant_maxhp_lv[player] >= 2:
            return False
        self.ant_maxhp_lv[player] += 1
        return True

    def deploy_super_weapon(
            self, player: int, coord: Coord, swtype: SuperWeaponType
    ) -> bool:
        sw = SuperWeapon(player, swtype, coord)
        sw.init_duration()
        if swtype == SuperWeaponType.EMERGENCY_EVASION:
            for ant in filter(
                    lambda ant: ant.player == player
                                and distance(ant.coord, coord) <= sw.range(),
                    self.ants,
            ):
                ant.evasion_count += sw.duration
        else:
            self.active_super_weapon.append(sw)
        return True

    def check_in_emp_range(self, player: int, coord: Coord) -> bool:
        for sw in self.active_super_weapon:
            if (
                    sw.player != player
                    and sw.type == SuperWeaponType.EMP_BLASTER
                    and distance(coord, sw.coord) <= sw.range()
            ):
                return True
        return False

    def set_coin(self, player: int, new_coin: int) -> None:
        self.coin[player] = new_coin

    def update_coin(self, player: int, delta: int) -> None:
        self.coin[player] += delta

    def set_hp(self, player: int, new_hp: int) -> None:
        self.hp[player] = new_hp

    def update_hp(self, player: int, delta: int) -> None:
        self.hp[player] += delta

    def pheromone_decay(self) -> None:
        for p in self.phero:
            p.decay()

    def is_operation_valid(self, player: int, op: Operation) -> bool:
        return self.apply_operation(player, op, True)

    def apply_operation(
            self, player: int, op: Operation, dry_run: bool = False
    ) -> bool:
        c = Coord(op.arg0, op.arg1)
        if op.type == OperationType.BUILD_TOWER:
            cost = self.build_tower_cost(player)
            valid = (
                    self.coin[player] >= cost
                    and is_player_highland(c, player)
                    and self.tower_at(c) is None
                    and not self.check_in_emp_range(player, c)
            )
            if valid and not dry_run:
                self.build_tower(player, c)
                self.coin[player] -= cost
            return valid
        if op.type == OperationType.UPGRADE_TOWER:
            t = self.tower_of_id(op.arg0)
            newtype = TowerType(op.arg1)
            cost = self.upgrade_tower_cost(newtype)
            valid = (
                    t is not None
                    and t.player == player
                    and self.coin[player] >= cost
                    and not self.check_in_emp_range(player, c)
                    and can_tower_upgrade_to(t.type, newtype)
            )
            if valid and not dry_run:
                self.upgrade_tower(op.arg0, TowerType(op.arg1))
                self.coin[player] -= cost
            return valid
        if op.type == OperationType.DOWNGRADE_TOWER:
            t = self.tower_of_id(op.arg0)
            valid = (
                    t is not None
                    and t.player == player
                    and not self.check_in_emp_range(player, c)
            )
            if valid and not dry_run:
                self.downgrade_tower(op.arg0)
                self.coin[player] += self.downgrade_tower_income(op.arg0)
            return valid

        def check_and_deploy(player: int, swtype: SuperWeaponType) -> bool:
            cost = SuperWeapon.config_of_type(swtype).cost
            if (
                    self.coin[player] >= cost
                    and self.super_weapon_cd[player][swtype.value - 1] == 0
            ):
                if not dry_run:
                    self.deploy_super_weapon(player, c, swtype)
                    self.coin[player] -= cost
                    self.super_weapon_cd[player][
                        swtype.value - 1
                        ] = SuperWeapon.config_of_type(swtype).cd
                return True
            return False

        if op.type == OperationType.DEPLOY_LIGHTNING_STORM:
            return check_and_deploy(player, SuperWeaponType.LIGHTNING_STORM)
        if op.type == OperationType.DEPLOY_EMP_BLASTER:
            return check_and_deploy(player, SuperWeaponType.EMP_BLASTER)
        if op.type == OperationType.DEPLOY_DEFLECTORS:
            return check_and_deploy(player, SuperWeaponType.DEFLECTORS)
        if op.type == OperationType.DEPLOY_EMERGENCY_EVASION:
            return check_and_deploy(player, SuperWeaponType.EMERGENCY_EVASION)

        def check_and_upgrade_hq(player: int, level_array: list[int]) -> bool:
            cost = Ant.upgrade_cost(level_array[player])
            if self.coin[player] >= cost:
                if not dry_run:
                    level_array[player] += 1
                    self.coin[player] -= cost
                return True
            return False

        if op.type == OperationType.UPGRADE_GENERATE_SPEED:
            return check_and_upgrade_hq(player, self.gen_speed_lv)
        if op.type == OperationType.UPGRADE_ANT_MAXHP:
            return check_and_upgrade_hq(player, self.ant_maxhp_lv)

        return False

    def search_attack_target(
            self, player: int, coord: Coord, trange: int, skip: int = -1
    ) -> Optional[Ant]:
        target: Optional[Ant] = None
        min_dist = 0
        for ant in self.ants:
            dist = distance(coord, ant.coord)
            if (
                    ant.player != player
                    and dist <= trange
                    and ant.id != skip
                    and ant.hp > 0
            ):
                if (
                        target is None
                        or dist < min_dist
                        or (dist == min_dist and ant.id < target.id)
                ):
                    target = ant
                    min_dist = dist
        return target

    def try_attack_ant(self, ant: Ant, damage: int):
        if ant.evasion_count > 0:
            ant.evasion_count -= 1
        else:
            if damage < ant.maxhp / 2 and any(
                    map(
                        lambda sw: sw.type == SuperWeaponType.DEFLECTORS
                                   and sw.player == ant.player
                                   and distance(sw.coord, ant.coord) <= sw.range(),
                        self.active_super_weapon,
                    )
            ):
                damage = 0
            ant.hp -= damage
            if ant.hp <= 0:
                ant.state = AntState.FAIL
                self.coin[1 - ant.player] += Ant.coin_of_level(ant.level)

    def aoe_attack_ant(self, player: int, center: Coord, radius: int, damage: int):
        for ant in filter(
                lambda ant: ant.player != player
                            and ant.hp > 0
                            and distance(ant.coord, center) <= radius,
                self.ants,
        ):
            self.try_attack_ant(ant, damage)

    def simulate_next_round(self) -> None:
        # 1. lightning storm
        for lightning in filter(
                lambda sw: sw.type == SuperWeaponType.LIGHTNING_STORM,
                self.active_super_weapon,
        ):
            for ant in filter(
                    lambda ant: ant.hp > 0 and ant.player != lightning.player
                                and distance(ant.coord, lightning.coord) <= lightning.range(),
                    self.ants,
            ):
                ant.hp -= 100
                self.coin[1 - ant.player] += Ant.coin_of_level(ant.level)

        # 2. tower attack
        for tower in self.towers:
            if self.check_in_emp_range(tower.player, tower.coord):
                continue
            if tower.cd > 0:
                tower.cd -= 1
            if tower.cd > 0:
                continue
            target = self.search_attack_target(tower.player, tower.coord, tower.range())
            if target is None:
                continue
            tower.reset_cd()
            # QUICK_PLUS
            if tower.type == TowerType.QUICK_PLUS:
                self.try_attack_ant(target, tower.damage())
                target = self.search_attack_target(
                    tower.player, tower.coord, tower.range()
                )
                if target is not None:
                    self.try_attack_ant(target, tower.damage())
            # DOUBLE
            elif tower.type == TowerType.DOUBLE:
                self.try_attack_ant(target, tower.damage())
                target = self.search_attack_target(
                    tower.player, tower.coord, tower.range(), target.id
                )
                if target is not None:
                    self.try_attack_ant(target, tower.damage())
            # PULSE
            elif tower.type == TowerType.PULSE:
                self.aoe_attack_ant(
                    tower.player, tower.coord, tower.range(), tower.damage()
                )
            # NORMAL
            elif tower.aoe() == 0:
                # ICE
                if tower.type == TowerType.ICE:
                    target.state = AntState.FROZEN
                self.try_attack_ant(target, tower.damage())
            # AOE
            else:
                self.aoe_attack_ant(
                    tower.player, target.coord, tower.aoe(), tower.damage()
                )

        # 3. filter too-old
        for too_old_ant in filter(
                lambda ant: ant.hp > 0 and ant.age > Ant.max_age(), self.ants
        ):
            too_old_ant.state = AntState.TOO_OLD

        # 4. ant move
        for ant in filter(lambda ant: ant.state == AntState.ALIVE, self.ants):
            direction = self.phero[ant.player].next_move_direction(ant)
            new_coord = neighbor(ant.coord, direction)
            ant.coord = new_coord
            ant.path.append(new_coord)
            if new_coord == headquarter_coord(1 - ant.player):
                ant.state = AntState.SUCCESS
                self.hp[1 - ant.player] -= 1

        # 5. pheromone update
        for p in self.phero:
            p.decay()
        for ant in self.ants:
            if ant.state == AntState.FAIL:
                self.phero[ant.player].modify_by_failed_ant(ant)
            if ant.state == AntState.TOO_OLD:
                self.phero[ant.player].modify_by_too_old_ant(ant)
            if ant.state == AntState.SUCCESS:
                self.phero[ant.player].modify_by_success_ant(ant)

        # 6. generate new ant
        for player in range(2):
            if self.round % Ant.gen_speed_of_level(self.gen_speed_lv[player]) == 0:
                self.ants.append(
                    Ant(
                        self.next_ant_id,
                        player,
                        Ant.maxhp_of_level(self.ant_maxhp_lv[player]),
                        Ant.maxhp_of_level(self.ant_maxhp_lv[player]),
                        headquarter_coord(player),
                        self.ant_maxhp_lv[player],
                        0,
                        0,
                        AntState.ALIVE,
                        [headquarter_coord(player)],
                    )
                )
                self.next_ant_id += 1

        # 7. final update
        self.round += 1
        self.coin[0] += 1
        self.coin[1] += 1
        self.dump_mini_replay()

        for ant in filter(lambda ant: ant.state == AntState.FROZEN, self.ants):
            ant.state = AntState.ALIVE
        self.ants = list(filter(lambda ant: ant.state == AntState.ALIVE, self.ants))
        for ant in self.ants:
            ant.age += 1

        for sw in self.active_super_weapon:
            sw.duration -= 1
        self.active_super_weapon = list(
            filter(lambda sw: sw.duration > 0, self.active_super_weapon)
        )

    def dump_mini_replay(self) -> None:
        with open(self.__mini_replay_name, "a", encoding="utf-8") as f:
            def fprint(*args, **kwargs):
                print(*args, file=f, **kwargs)

            fprint(self.round)
            fprint(len(self.towers))
            for tower in self.towers:
                fprint(
                    f"{tower.id} {tower.player} {tower.coord.x} {tower.coord.y} {tower.type.value} {tower.cd}"
                )
            fprint(len(self.ants))
            for ant in self.ants:
                fprint(
                    f"{ant.id} {ant.player} {ant.coord.x} {ant.coord.y} {ant.hp} {ant.level} {ant.age} {ant.state}"
                )
            fprint(f"{self.coin[0]} {self.coin[1]}")
            fprint(f"{self.hp[0]} {self.hp[1]}")
            for p in self.phero:
                for row in p.value:
                    fprint(" ".join(map(lambda value: f"{value:.4f}", row)))
