from protocol import *
from init import Item
from map import *
from aco import *
from ant import *
import copy
import sys
# test_player = 0
class RoundInfo():
    def __init__(self) -> None:
        self.round = 0
        self.ant_list = []
        self.tower_list = []
        self.coins = []
        self.camp_hps = []


class protocol():
    def read_init_info() -> int:
        info = input().split(' ')
        player = int(info[0])
        lcg_seed = int(info[1])
        global test_player
        test_player = player
        return player, lcg_seed

    def read_round_info() -> RoundInfo:
        round_infomation = RoundInfo()
        round_infomation.round = int(input())
        n1 = int(input())
        for _ in range(n1):
            tower_info = input().split(' ')
            round_infomation.tower_list.append([int(x) for x in tower_info])
        n2 = int(input())
        for _ in range(n2):
            ant_info = input().split(' ')
            round_infomation.ant_list.append([int(x) for x in ant_info])
        coins = (input()).split(' ')
        round_infomation.coins.append(int(coins[0]))
        round_infomation.coins.append(int(coins[1]))
        camp_hps = (input()).split(' ')
        round_infomation.camp_hps.append(int(camp_hps[0]))
        round_infomation.camp_hps.append(int(camp_hps[1]))
        return round_infomation

    def send_operations(ops: list[Operation]) -> None:
        s = str(len(ops)) + '\n'
        for op in ops:
            s += op.dumps()
        # 4 bite -> 4 * 16 / 16 = 2
        s = int.to_bytes(len(s), 4, 'big').decode('UTF-8') + s
        print(s, end='')

    def read_opponent_operations() -> list[Operation]:
        op_list = []
        operations_num = int(input())
        for i in range(operations_num):
            info = input()
            info = info.split(' ')
            if int(info[0]) == 11:
                op_list.append(
                    Operation(OperationType.build_tower, int(info[1]), int(info[2])))
            elif int(info[0]) == 12:
                op_list.append(
                    Operation(OperationType.upgrade_tower, int(info[1]), int(info[2])))
            elif int(info[0]) == 13:
                op_list.append(
                    Operation(OperationType.destory_tower, int(info[1])))
            elif int(info[0]) == 21:
                op_list.append(
                    Operation(OperationType.use_item_1, int(info[1]), int(info[2])))
            elif int(info[0]) == 22:
                op_list.append(
                    Operation(OperationType.use_item_2, int(info[1]), int(info[2])))
            elif int(info[0]) == 23:
                op_list.append(
                    Operation(OperationType.use_item_3, int(info[1]), int(info[2])))
            elif int(info[0]) == 24:
                op_list.append(
                    Operation(OperationType.use_item_4, int(info[1]), int(info[2])))
            elif int(info[0]) == 31:
                op_list.append(
                    Operation(OperationType.upgrade_base_speed))
            elif int(info[0]) == 32:
                op_list.append(
                    Operation(OperationType.upgrade_ant_hp))
        return op_list

    def send_string(s: str) -> None:
        send_s = ""
        send_s = int.to_bytes(len(s), 4, 'big').decode('UTF-8') + s
        print(send_s)


MAP_SIZE = 19


class AntGame:
    def __init__(self, lcg_seed) -> None:
        self.tower_id_max = -1
        self.ant_id_max = -1
        self.tower_list = []
        self.ant_list = []
        self.coins = [int(25) for _ in range(2)]
        self.base_camps_hp = [int(10) for _ in range(2)]
        self.base_hp_level = [int(0) for _ in range(2)]
        self.base_speed_level = [int(0) for _ in range(2)]
        # self.base_cd = [int(0) for _ in range(2)]
        self.item_cd = [[0 for i in range(
            4)] for i in range(2)]
        self.EMP_pos = [Pos(0, 0), Pos(0, 0)]
        self.Shield_pos = [Pos(0, 0), Pos(0, 0)]
        self.Lightning_pos = [Pos(0, 0), Pos(0, 0)]
        self.Lightning_time = [0, 0]
        self.EMP_time = [0, 0]
        self.Shield_time = [0, 0]
        self.pheromon = [[[phe_init for i in range(
            MAP_SIZE)] for i in range(MAP_SIZE)] for i in range(2)]
        self.round = 0
        self.towercost = [15, 15]
        self.ant_protection = [0, 0]
        self.ant_frozen = [0, 0]
        self.tower_power = [0, 0]
        self.winner = -1
        self.lcg_seed = lcg_seed
        self.init_pheromon(lcg_seed)
        self.applied_item_list = []
        self.ant_level_hp_table = {
            0: 10,
            1: 25,
            2: 50
        }
        self.unmovable_place = [  # ants can't move to
            (6, 1), (7, 1), (9, 1), (11, 1), (12, 1),
            (4, 2), (6, 2), (8, 2), (9, 2), (11, 2),
            (13, 2), (4, 3), (5, 3), (13, 3), (14, 3),
            (6, 4), (8, 4), (9, 4), (11, 4), (3, 5),
            (4, 5), (7, 5), (9, 5), (11, 5), (14, 5),
            (15, 5), (3, 6), (5, 6), (12, 6), (14, 6),
            (2, 7), (5, 7), (6, 7), (8, 7), (9, 7),
            (10, 7), (12, 7), (13, 7), (16, 7), (1, 8),
            (2, 8), (7, 8), (10, 8), (15, 8), (16, 8),
            (0, 9), (4, 9), (5, 9), (6, 9), (9, 9),
            (12, 9), (13, 9), (14, 9), (18, 9), (1, 10),
            (2, 10), (7, 10), (10, 10), (15, 10), (16, 10),
            (2, 11), (5, 11), (6, 11), (8, 11), (9, 11),
            (10, 11), (12, 11), (13, 11), (16, 11), (3, 12),
            (5, 12), (12, 12), (14, 12), (3, 13), (4, 13),
            (7, 13), (9, 13), (11, 13), (14, 13), (15, 13),
            (6, 14), (8, 14), (9, 14), (11, 14), (4, 15),
            (5, 15), (13, 15), (14, 15), (4, 16), (6, 16),
            (8, 16), (9, 16), (11, 16), (13, 16), (6, 17),
            (7, 17), (9, 17), (11, 17), (12, 17),
        ]
        self.buildable_place = [
            [   # player0 buildable
                (6, 1), (7, 1), (4, 2), (6, 2), (8, 2),
                (4, 3), (5, 3), (6, 4), (8, 4), (7, 5),
                (5, 6), (5, 7), (6, 7), (8, 7), (7, 8),
                (4, 9), (5, 9), (6, 9), (7, 10), (5, 11),
                (6, 11), (8, 11), (5, 12), (7, 13), (6, 14),
                (8, 14), (4, 15), (5, 15), (4, 16), (6, 16),
                (8, 16), (6, 17), (7, 17),
            ],
            [   # player1 buildable
                (11, 1), (12, 1), (9, 2), (11, 2), (13, 2),
                (13, 3), (14, 3), (9, 4), (11, 4), (11, 5),
                (12, 6), (10, 7), (12, 7), (13, 7), (10, 8),
                (12, 9), (13, 9), (14, 9), (10, 10), (10, 11),
                (12, 11), (13, 11), (12, 12), (11, 13), (9, 14),
                (11, 14), (13, 15), (14, 15), (9, 16), (11, 16),
                (13, 16), (11, 17), (12, 17),
            ]
        ]

    def lcg(self):
        # lcg_seed = self.lcg_seed
        self.lcg_seed = (25214903917 * self.lcg_seed) & ((1 << 48) - 1)
        return self.lcg_seed

    def init_pheromon(self, M):
        for i in [0, 1]:
            for j in range(0, MAP_SIZE):
                for k in range(0, MAP_SIZE):
                    self.pheromon[i][j][k] = self.lcg() * pow(2, -46) + 8
                    # self.pheromon[i][j][k] = 10

    def update_round_info(self, round_infomation: RoundInfo) -> None:

        self.clear()
        self.round = round_infomation.round
        self.tower_list.clear()
        n1 = len(round_infomation.tower_list)
        for i in range(n1):
            tower_info = round_infomation.tower_list[i]
            new_tower = Tower()
            new_tower.player = int(tower_info[1])
            new_tower.id = int(tower_info[0])
            new_tower.x = int(tower_info[2])
            new_tower.y = int(tower_info[3])
            new_tower.level = int(tower_info[4])
            new_tower.cd = int(tower_info[5])
            self.tower_list.append(copy.copy(new_tower))
        n2 = len(round_infomation.ant_list)
        new_ant_list = []
        for i in range(n2):
            ant_info = round_infomation.ant_list[i]
            new_ant = None
            cur_list_num = 0
            for i in self.ant_list:
                if i.id == int(ant_info[0]):
                    new_ant = copy.deepcopy(i)
                    new_ant.x = int(ant_info[2])
                    new_ant.y = int(ant_info[3])
                    del self.ant_list[cur_list_num]
                    break
                cur_list_num += 1
            if new_ant is None:
                new_ant = Ant(int(ant_info[2]), int(ant_info[3]))
                new_ant.player = int(ant_info[1])
                new_ant.id = int(ant_info[0])
            new_ant.path.append((new_ant.x, new_ant.y))
            new_ant.hp = int(ant_info[4])
            new_ant.max_hp = self.ant_level_hp_table[int(ant_info[5])]
            new_ant.age = int(ant_info[6])
            new_ant.state = (int(ant_info[7]))
            new_ant_list.append(copy.copy(new_ant))
            if new_ant.id > self.ant_id_max:
                self.ant_id_max = new_ant.id
        self.ant_list = copy.deepcopy(new_ant_list)
        # 更新蚂蚁列表蚂蚁信息

        # self.ant_list = new_ant_list.copy()
        self.coins.clear()
        for i in round_infomation.coins:
            self.coins.append(int(i))
        self.base_camps_hp.clear()
        for i in round_infomation.camp_hps:
            self.base_camps_hp.append(int(i))

        self.update_pheromone_all()
        self.update_weapon()

    def apply_operations(self, is_first: int, ops: list[Operation]) -> bool:
        operations_num = len(ops)
        for i in range(operations_num):
            self.apply_operation(is_first, ops[i])
        return True

    def check_valid(self, x: int, y: int, is_first: int):
        if (x, y) in self.buildable_place[is_first] and self.tower_at(x, y) is None:
            return True
        return False

    def apply_operation(self, is_first: int, info: Operation) -> bool:
        if info.operation_type == OperationType.build_tower:
            # check coins enough
            if self.coins[is_first] < self.towercost[is_first]:
                return False
            if not self.check_valid(int(info.args_1), int(info.args_2), is_first):
                return False
            if self.EMP_time[1-is_first] > 0 and distance(self.EMP_pos[1-is_first], Pos(int(info.args_1), int(info.args_2))) <= 3:
                return False
            new_tower = Tower()
            new_tower.id = self.tower_id_max + 1
            self.tower_id_max += 1
            new_tower.x = int(info.args_1)
            new_tower.y = int(info.args_2)
            new_tower.level = 0
            new_tower.player = is_first
            new_tower.cd = new_tower.get_cd() - 1
            new_tower.cost = self.towercost[new_tower.player]
            self.coins[new_tower.player] -= self.towercost[new_tower.player]
            self.towercost[new_tower.player] *= 2
            self.tower_list.append(copy.copy(new_tower))

        elif info.operation_type == OperationType.upgrade_tower:
            
            cur_num = 0
            for i in self.tower_list:
                if i.id == int(info.args_1):
                    break
                cur_num += 1
            # print(self.coins[is_first] < (60 if int(info.args_2) // 10 == 0 else 100),self.tower_list[cur_num].level != int(info.args_2) // 10)
            if self.coins[is_first] < (60 if int(info.args_2) // 10 == 0 else 100):
                return False
            if self.tower_list[cur_num].level != int(info.args_2) // 10:
                return False
            if self.EMP_time[1-is_first] > 0 and distance(self.EMP_pos[1-is_first], Pos(self.tower_list[cur_num].x, self.tower_list[cur_num].x)) <= 3:
                return False
            self.tower_list[cur_num].level = int(info.args_2)
            self.tower_list[cur_num].cd = self.tower_list[cur_num].get_cd() - 1
            if (int(info.args_2) // 10 != 0):
                self.coins[self.tower_list[cur_num].player] -= 100
            else:
                self.coins[self.tower_list[cur_num].player] -= 60
        elif info.operation_type == OperationType.destory_tower:
            cur_num = 0
            for i in self.tower_list:
                if i.id == int(info.args_1):
                    break
                cur_num += 1
            if self.EMP_time[1-is_first] > 0 and distance(self.EMP_pos[1-is_first], Pos(self.tower_list[cur_num].x, self.tower_list[cur_num].x)) <= 3:
                return False
            if (self.tower_list[cur_num].level == 0):
                self.towercost[is_first] /= 2
                self.coins[self.tower_list[cur_num].player] += int(
                    self.towercost[is_first] * 0.8)
                del self.tower_list[cur_num]
            elif (self.tower_list[cur_num].level // 10 == 0):
                self.coins[self.tower_list[cur_num].player] += 48
                self.tower_list[cur_num].level = 0
                self.tower_list[cur_num].cd = self.tower_list[cur_num].get_cd() - 1
            else:
                self.coins[self.tower_list[cur_num].player] += 80
                self.tower_list[cur_num].level = self.tower_list[cur_num].level // 10
                self.tower_list[cur_num].cd = self.tower_list[cur_num].get_cd() - 1

        elif info.operation_type == OperationType.use_item_1:
            if self.coins[is_first] < 150:
                return False
            if self.item_cd[is_first][0] > 0:
                return False
            x = int(info.args_1)
            y = int(info.args_2)
            self.coins[is_first] -= 150
            self.item_cd[is_first][0] = 100
            self.Lightning_pos[is_first] = Pos(x, y)
            self.Lightning_time[is_first] = 10

        elif info.operation_type == OperationType.use_item_2:
            if self.coins[is_first] < 150:
                return False
            if self.item_cd[is_first][1] > 0:
                return False
            x = int(info.args_1)
            y = int(info.args_2)
            self.coins[is_first] -= 150
            self.item_cd[is_first][1] = 75
            self.EMP_pos[is_first] = Pos(x, y)
            self.EMP_time[is_first] = 10

        elif info.operation_type == OperationType.use_item_3:
            if self.coins[is_first] < 100:
                return False
            if self.item_cd[is_first][2] > 0:
                return False
            x = int(info.args_1)
            y = int(info.args_2)
            self.coins[is_first] -= 100
            self.item_cd[is_first][1] = 55
            self.Shield_pos[is_first] = Pos(x, y)
            self.Shield_time[is_first] = 10

        elif info.operation_type == OperationType.use_item_4:
            if self.coins[is_first] < 100:
                return False
            if self.item_cd[is_first][3] > 0:
                return False
            x = int(info.args_1)
            y = int(info.args_2)
            self.coins[is_first] -= 100
            self.item_cd[is_first][3] = 35
            for i in range(len(self.ant_list)):
                ant = self.ant_list[i]
                if ant.player != is_first:
                    continue
                if distance(Pos(ant.x, ant.y), Pos(x, y)) <= 3:
                    self.ant_list[i].protection += 2

        elif info.operation_type == OperationType.upgrade_base_speed:
            if self.base_speed_level[is_first] >= 2:
                return False
            if self.base_speed_level[is_first] == 1:
                if self.coins[is_first] < 200:
                    return False
                self.coins[is_first] -= 200
                self.base_speed_level[is_first] += 1
                self.base_cd = 0
            elif self.base_speed_level[is_first] == 0:
                if self.coins[is_first] < 100:
                    return False
                self.coins[is_first] -= 100
                self.base_speed_level[is_first] += 1
                self.base_cd = 0
            return False

        elif info.operation_type == OperationType.upgrade_ant_hp:
            if self.base_hp_level[is_first] >= 2:
                return False
            if self.base_hp_level[is_first] == 1:
                if self.coins[is_first] < 200:
                    return False
                self.coins[is_first] -= 200
                self.base_hp_level[is_first] += 1
                self.base_cd = 0
            elif self.base_hp_level[is_first] == 0:
                if self.coins[is_first] < 100:
                    return False
                self.coins[is_first] -= 100
                self.base_hp_level[is_first] += 1
                self.base_cd = 0
            return False

        return True

    def clear(self) -> None:
        pass

    def update_pheromon(self, ant) -> None:
        x = ant.x
        y = ant.y
        L_k = max(len(ant.path), 1)
        player = ant.player
        # 依据状态确定信息素更新
        if ant.path == []:
            return
        path = list(set(ant.path))
        if ant.state == State.Success.value:
            for point in reversed(path):
                self.pheromon[player][point[0]][point[1]] += Q1
                    # path_map[point[0]][point[1]] = 1
                # self.pheromon[x][y][player][(mov + 3) % 6] += Q1 / L_k
                # x += d[y % 2][(mov + 3) % 6][0]
                # y += d[y % 2][(mov + 3) % 6][1]
                # self.pheromon[x][y][player][mov] += Q1 / L_k

        elif ant.state == State.Fail.value or ant.state == State.TooOld.value:  # Fail or TooOld
            Q = Q2 if ant.state == State.Fail.value else Q3
            for point in reversed(path):
                self.pheromon[player][point[0]][point[1]] += Q
                if self.pheromon[player][point[0]][point[1]] < 0:
                    self.pheromon[player][point[0]][point[1]] = 0

    def move_probability(self, ant, side: int, x: int, y: int, des: Pos) -> list[float]:
        player = side
        p = [float(0) for _ in range(6)]
        # 计算蚂蚁路径,更新局部信息素
        nor = 0.0
        for i in range(6):
            _x = x + d[y % 2][i][0]
            _y = y + d[y % 2][i][1]
            # 如果该方向不可移动，跳过
            if (_x, _y) in self.unmovable_place or not is_valid(Pos(_x, _y)) or (len(ant.path) >= 2 and (_x, _y) == ant.path[-2]):
                p[i] = -1
                continue
            # 计算该方向上的信息素强度
            n = 1
            if distance(Pos(_x, _y), des) < distance(Pos(x, y), des):
                n = 1.25
            elif distance(Pos(_x, _y), des) > distance(Pos(x, y), des):
                n = 0.75
            p[i] = self.pheromon[player][_x][_y] * n
        return p.copy()

    def ants(self) -> list[Ant]:
        return self.ant_list

    def ant_at(self, x: int, y: int) -> list[Ant]:
        ant_list = []
        for ant in self.ant_list:
            if ant.x == x and ant.y == y:
                ant_list.append(ant)
        return ant_list

    def ant_of_id(self, id: int) -> Ant:
        for i in self.ant_list:
            if i.id == id:
                return i
        return None

    def towers(self) -> list[Tower]:
        return self.tower_list

    def tower_at(self, x: int, y: int) -> Tower:
        for tower in self.tower_list:
            if tower.x == x and tower.y == y:
                return tower
        return None

    def tower_of_id(self, id: int) -> Tower:
        for i in self.tower_list:
            if i.id == id:
                return i
        return None

    def pheromone(self, side: int) -> list[list[list[int]]]:
        return self.pheromon[side][:][:]

    def pheromone_at(self, side: int, x: int, y: int) -> list[int]:
        return self.pheromon[side][x][y]

    def coin(self, side) -> int:
        return self.coins[side]

    def base_hp(self, side) -> int:
        return self.base_camps_hp[side]

    def ended(self) -> bool:
        return self.round > 511

    def copy(self):
        new_game = copy.deepcopy(self)
        return new_game

    def tower_attack_target(self, id: int) -> list[int]:
        tower = None
        for i in self.tower_list:
            if i.id == id:
                tower = i
        if tower is None:
            return None
        if self.EMP_time[1-tower.player] > 0 and distance(self.EMP_pos[1-tower.player], Pos(tower.x, tower.y)) <= 3:
            return None
        if tower.cd:
            tower.cd -= 1
            return None
        if tower.level != 22 and tower.level != 32 and tower.level != 3 and tower.level != 31 and tower.level != 33:
            nearest_ant = None
            min_dis = tower.get_range()
            for ant in self.ant_list:
                if (distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) <= min_dis or (nearest_ant and distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) == distance(Pos(tower.x, tower.y), Pos(nearest_ant.x, nearest_ant.y)) and nearest_ant.id > ant.id)) and ant.hp > 0 and ant.player != tower.player:
                    min_dis = distance(
                        Pos(tower.x, tower.y), Pos(ant.x, ant.y))
                    nearest_ant = ant
            if nearest_ant is None:
                return []
            tower.cd = tower.get_cd() - 1
            return [nearest_ant.id]
        elif tower.level == 22:
            target_ant_list = []
            nearest_ant = None
            min_dis = tower.get_range()
            for ant in self.ant_list:
                if (distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) <= min_dis or (nearest_ant and distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) == distance(Pos(tower.x, tower.y), Pos(nearest_ant.x, nearest_ant.y)) and nearest_ant.id > ant.id)) and ant.hp > 0 and ant.player != tower.player:
                    min_dis = distance(
                        Pos(tower.x, tower.y), Pos(ant.x, ant.y))
                    nearest_ant = ant
            if nearest_ant is not None:
                tower.cd = tower.get_cd() - 1
                target_ant_list.append(nearest_ant.id)

                nearest_ant_second = None
                min_dis = tower.get_range()
                for ant in self.ant_list:
                    if (distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) <= min_dis or (nearest_ant_second and distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) == distance(Pos(tower.x, tower.y), Pos(nearest_ant_second.x, nearest_ant_second.y)) and nearest_ant_second.id > ant.id)) and ant.id != nearest_ant.id and ant.hp > 0 and ant.player != tower.player:
                        min_dis = distance(
                            Pos(tower.x, tower.y), Pos(ant.x, ant.y))
                        nearest_ant_second = ant
                if nearest_ant_second is not None:
                    target_ant_list.append(
                        nearest_ant_second.id)
            return target_ant_list
        elif tower.level == 32:
            target_ant_list = []
            min_dis = tower.get_range()
            for ant in self.ant_list:
                if distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) <= tower.get_range():
                    target_ant_list.append(ant.id)
            if target_ant_list != []:
                tower.cd = tower.get_cd() - 1
            return target_ant_list
        elif tower.level == 3 or tower.level == 31 or tower.level == 33:
            nearest_ant = None
            min_dis = tower.get_range()
            for ant in self.ant_list:
                if (distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) <= min_dis or (nearest_ant and distance(Pos(tower.x, tower.y), Pos(ant.x, ant.y)) == distance(Pos(tower.x, tower.y), Pos(nearest_ant.x, nearest_ant.y)) and nearest_ant.id > ant.id)) and ant.hp > 0 and ant.player != tower.player:
                    min_dis = distance(
                        Pos(tower.x, tower.y), Pos(ant.x, ant.y))
                    nearest_ant = ant
            if nearest_ant is None:
                return []
            target_ant_list = []
            min_dis = 1
            if tower.level == 33:
                min_dis = 2
            for ant in self.ant_list:
                if distance(Pos(nearest_ant.x, nearest_ant.y), Pos(ant.x, ant.y)) <= min_dis and ant.hp > 0 and ant.player != tower.player:
                    target_ant_list.append(ant.id)
            if target_ant_list != []:
                tower.cd = tower.get_cd() - 1
                # print(tower.id, tower.level, target_ant_list)
            return target_ant_list

    def attack_ant(self, ant_id: int, damage: int) -> None:
        ant_coin_table = {
            0: 3,
            1: 5,
            2: 7
        }
        # 紧急回避
        ant = self.ant_list[ant_id]
        if ant.protection > 0:
            self.ant_list[ant_id].protection -= 1
            return
        # 引力护盾
        elif self.Shield_time[ant.player] > 0 and damage < int(0.5 * ant.max_hp):
            if distance(self.Shield_pos[ant.player], Pos(ant.x, ant.y)) <= 3:
                return
        # print(ant.id, ant.hp,damage)
        self.ant_list[ant_id].hp -= damage
        self.ant_list[ant_id].hp = (int)(self.ant_list[ant_id].hp)
        # print(ant.id, ant.hp,damage)
        if ant.hp <= 0:
            self.ant_list[ant_id].state = State.Fail.value
            for level in self.ant_level_hp_table:
                if self.ant_list[ant_id].max_hp == self.ant_level_hp_table[level]:
                    self.coins[1-self.ant_list[ant_id].player] += ant_coin_table[level]

    # 模拟所有塔的攻击（双方，按id顺序进行）
    def tower_attack(self) -> None:

        for tower in self.tower_list:
            targets = self.tower_attack_target(tower.id)
            
            if targets is None or targets == []:
                continue
            # print("tower",targets, tower.id, tower.level, tower.get_damage())
            for target in targets:
                for i in range(len(self.ant_list)):
                    ant = self.ant_list[i]
                    if ant.id == target and ant.player != tower.player:
                        if (tower.level == 12):
                            ant.state = State.Frozen.value
                        # if self.ant_protection[ant.player] != 0:
                        #     # print("protect")
                        #     self.ant_protection[ant.player]
                        # elif self.tower_power[tower.player] != 0:
                        #     self.tower_power[tower.player] -= 1
                        #     self.ant_list[i].hp -= 2 * tower.get_damage()
                        #     self.ant_list[i].hp = (int)(self.ant_list[i].hp)
                        # else:
                        
                        self.attack_ant(i, tower.get_damage())
            if tower.level == 21:
                tower.cd = 0
                targets = self.tower_attack_target(tower.id)
                if targets is None or targets == []:
                    return None
                for target in targets:
                    for i in range(len(self.ant_list)):
                        ant = self.ant_list[i]
                        if ant.id == target and ant.player != tower.player:
                            if (tower.level == 12):
                                ant.state = State.Frozen.value
                            # if self.ant_protection[ant.player] != 0:
                            #     self.ant_protection[ant.player]
                            # elif self.tower_power[tower.player] != 0:
                            #     self.tower_power[tower.player] -= 1
                            #     self.ant_list[i].hp -= 2 * tower.get_damage()
                            #     self.ant_list[i].hp = (int)(
                            #         self.ant_list[i].hp)
                            # else:
                            self.attack_ant(i, tower.get_damage())
                tower.cd = tower.get_cd() - 1

    def judge_winner(self) -> None:
        if self.base_camps_hp[0] <= 0:
            self.winner = 1
        elif self.base_camps_hp[1] <= 0:
            self.winner = 0

    # 模拟所有蚂蚁的移动（双方，按id顺序进行）
    def ant_move(self) -> None:
        for i in range(len(self.ant_list)):
            ant = self.ant_list[i]
            if ant.state == State.Frozen.value:
                self.ant_list[i].state = State.Alive.value
            if ant.state != State.Alive.value:
                continue
            if self.ant_frozen[ant.player] != 0:
                self.ant_frozen[ant.player] -= 1
                self.ant_list[i].age += 1
                if ant.age >= age_limit:
                    self.ant_list[i].state = State.TooOld.value
                continue
            move_prob = self.move_probability(
                ant, ant.player, ant.x, ant.y, camp_pos[1-ant.player])
            # if ant.id == 20:
            #     print(move_prob, ant.x, ant.y)
            max_p = -1
            move_direction = 0
            for j in range(6):
                if move_prob[j] > max_p:
                    move_direction = j
                    max_p = move_prob[j]
                if move_prob[j] == max_p:
                    _x1 = ant.x + d[ant.y % 2][j][0]
                    _y1 = ant.y + d[ant.y % 2][j][1]
                    _x2 = ant.x + d[ant.y % 2][move_direction][0]
                    _y2 = ant.y + d[ant.y % 2][move_direction][1]
                    if is_valid(Pos(_x1, _y1)) and is_valid(Pos(_x2, _y2)) and self.pheromon[ant.player][_x1][_y1] > self.pheromon[ant.player][_x2][_y2]:
                        move_direction = j
            if max_p > -1:
                # print("i",i, move_direction)
                self.ant_list[i].x += d[ant.y % 2][move_direction][0]
                self.ant_list[i].y += d[ant.y % 2][move_direction][1]
                self.ant_list[i].path.append(
                    (self.ant_list[i].x, self.ant_list[i].y))
            self.ant_list[i].age += 1
            if ant.age >= age_limit:
                self.ant_list[i].state = State.TooOld.value
            if ant.x == camp_pos[1-ant.player].x and ant.y == camp_pos[1-ant.player].y:
                self.ant_list[i].state = State.Success.value
                self.base_camps_hp[1-ant.player] -= 1
                self.judge_winner()

    # 模拟指定玩家兵营生成
    def ant_born(self) -> None:
        # for barrack in self.barrack_list:
        #     if (self.round - barrack.buildtime) % 4 != 0:
        #         continue
        #     new_ant = Ant(barrack.x, barrack.y)
        #     new_ant.player = barrack.player
        #     new_ant.hp = (int)(10 * 1.005 ** self.round)
        #     new_ant.max_hp = (int)(10 * 1.005 ** self.round)
        #     self.ant_id_max += 1
        #     new_ant.id = self.ant_id_max
        #     self.ant_list.append(new_ant)
        for i in range(2):
            speed_list = [4, 2, 1]
            hp_list = [10, 25, 50]
            if self.round % speed_list[self.base_speed_level[i]] == 0:
                new_ant = Ant(camp_pos[i].x, camp_pos[i].y)
                new_ant.player = i
                new_ant.hp = hp_list[self.base_hp_level[i]]
                new_ant.max_hp = hp_list[self.base_hp_level[i]]
                self.ant_id_max += 1
                new_ant.id = self.ant_id_max
                new_ant.path.append((camp_pos[i].x, camp_pos[i].y))
                self.ant_list.append(new_ant)

    def update_pheromone_all(self) -> None:
        R = 0.97
        for i1 in range(2):
            for i2 in range(MAP_SIZE):
                for i3 in range(MAP_SIZE):
                    self.pheromon[i1][i2][i3] *= R
                    self.pheromon[i1][i2][i3] += (1-R)*10
        for ant in self.ant_list:
            self.update_pheromon(ant)

    def clear_ants(self) -> None:
        self.ant_list = list(filter(lambda x:not (x.state == State.Success.value or x.state == State.Fail.value or x.state == State.TooOld.value), self.ant_list))
        # for ant in self.ant_list:
        #     if ant.state == State.Success.value or ant.state == State.Fail.value or ant.state == State.TooOld.value:
        #         self.ant_list.remove(ant)

    # def update_items(self) -> None:
    #     for item in self.item_list:
    #         if item.time + item.duration <= self.round:
    #             item.state = State.TimeOut.value
    #         elif item.time <= self.round:
    #             item.state = State.Available.value
    #         else:
    #             item.state = State.NotGenerated.value

    def get_items(self) -> None:
        for item in self.item_list:
            for ant in self.ant_list:
                if item.state == State.Available.value and item.x == ant.x and item.y == ant.y:
                    item.state = State.GotByPlayer0.value if ant.player == 0 else State.GotByPlayer1.value
                    break
            if item.state == State.Available.value:
                for ant in self.ant_list:
                    if item.state == State.Available.value and abs(item.x - ant.x) <= 1 and abs(item.y - ant.y) <= 1:
                        item.state = State.GotByPlayer0.value if ant.player == 0 else State.GotByPlayer1.value
                    break

    def get_base_hp_level(self, player):
        return self.base_hp_level[player]

    def get_base_speed_level(self, player):
        return self.base_speed_level[player]
    # def apply_items(self) -> None:
    #     for item in self.item_list:
    #         if item.state == State.GotByPlayer0.value:
    #             if item.type == 1:
    #                 for i in range(len(self.ant_list)):
    #                     ant = self.ant_list[i]
    #                     if ant.player == 0:
    #                         self.ant_list[i].hp = (int)(
    #                             1.5*self.ant_list[i].hp)
    #                         if ant.hp > ant.max_hp:
    #                             self.ant_list[i].hp = ant.max_hp
    #             elif item.type == 2:
    #                 for barrack in self.barrack_list:
    #                     if barrack.player == 1:
    #                         continue
    #                     new_ant = Ant(barrack.x, barrack.y)
    #                     new_ant.player = barrack.player
    #                     new_ant.hp = (int)(10 * 1.005 ** self.round)
    #                     new_ant.max_hp = (int)(10 * 1.005 ** self.round)
    #                     self.ant_id_max += 1
    #                     new_ant.id = self.ant_id_max
    #                     self.ant_list.append(new_ant)
    #             elif item.type == 3:
    #                 self.ant_protection[0] = 4
    #             elif item.type == 4:
    #                 self.tower_power[0] = 8
    #             else:
    #                 self.ant_frozen[1] = 2

    #         elif item.state == State.GotByPlayer1.value:
    #             if item.type == 1:
    #                 for i in range(len(self.ant_list)):
    #                     ant = self.ant_list[i]
    #                     if ant.player == 1:
    #                         self.ant_list[i].hp = (int)(
    #                             1.5*self.ant_list[i].hp)
    #                         if ant.hp > ant.max_hp:
    #                             self.ant_list[i].hp = ant.max_hp
    #             elif item.type == 2:
    #                 for barrack in self.barrack_list:
    #                     if barrack.player == 0:
    #                         continue
    #                     new_ant = Ant(barrack.x, barrack.y)
    #                     new_ant.player = barrack.player
    #                     new_ant.hp = (int)(10 * 1.005 ** self.round)
    #                     new_ant.max_hp = (int)(10 * 1.005 ** self.round)
    #                     self.ant_id_max += 1
    #                     new_ant.id = self.ant_id_max
    #                     self.ant_list.append(new_ant)
    #             elif item.type == 3:
    #                 self.ant_protection[1] = 4
    #             elif item.type == 4:
    #                 self.tower_power[1] = 8
    #             else:
    #                 self.ant_frozen[0] = 2

    # def clear_items(self) -> None:
    #     for item in self.item_list:
    #         if item.state == State.TimeOut.value or item.state == State.GotByPlayer0.value or item.state == State.GotByPlayer1.value:
    #             self.item_list.remove(item)

    def get_income(self) -> None:
        income = 1
        # panalty0 = 0
        # panalty1 = 0
        # for barrack in self.barrack_list:
        #     if barrack.player == 0:
        #         panalty0 += 1
        #     else:
        #         panalty1 += 1
        # panalty0 = max(0, panalty0 - 1)
        # if self.coins[0] <= 0 and income - panalty0 <= 0:
        #     self.base_camps_hp[0] += income - panalty0
        # else:
        #     self.coins[0] += income - panalty0

        # panalty1 = max(0, panalty1 - 1)
        # if self.coins[1] <= 0 and income - panalty1 <= 0:
        #     self.base_camps_hp[1] += income - panalty1
        # else:
        #     self.coins[1] += income - panalty1
        self.coins[0] += income
        self.coins[1] += income

    def update_weapon(self) -> None:
        for player_item_cd in self.item_cd:
            for item_cd in player_item_cd:
                if item_cd:
                    item_cd -= 1
        for player in range(2):
            if self.EMP_time[player] > 0:
                self.EMP_time[player] -= 1
            if self.Shield_time[player] > 0:
                self.Shield_time[player] -= 1

    def apply_weapon(self) -> None:
        for player in range(2):
            if self.Lightning_time[player] > 0:
                self.Lightning_time[player] -= 1
                ant_coin_table = {
                    0: 3,
                    1: 5,
                    2: 7
                }
                for i in range(len(self.ant_list)):
                    ant = self.ant_list[i]
                    if ant.player == player:
                        continue
                    if distance(self.Lightning_pos[player], Pos(ant.x, ant.y)) <= 3:
                        self.ant_list[i].hp -= 100
                        self.ant_list[i].hp = (int)(self.ant_list[i].hp)
                        if ant.hp <= 0:
                            self.ant_list[i].state = State.Fail.value
                            for level in self.ant_level_hp_table:
                                if self.ant_list[i].max_hp == self.ant_level_hp_table[level]:
                                    self.coins[1-self.ant_list[i].player] += ant_coin_table[level]

    def show(self) -> None:
        max_hp_to_level = {
            10: 0,
            25: 1,
            50: 2
        }
        fp = open("mini-replay-python.out", 'a')
        # fp = sys.stderr
        print(self.round, file=fp)  # round
        print(len(self.tower_list), file=fp)  # tower_number
        for tower in self.tower_list:
            print(tower.id, tower.player, tower.x, tower.y,
                  tower.level, tower.cd, file=fp)
        print(len(self.ant_list), file=fp)  # ant_number
        for ant in self.ant_list:
            print(ant.id, ant.player, ant.x, ant.y,
                  ant.hp, max_hp_to_level[ant.max_hp], ant.age, ant.state, file=fp)
        print(self.coins[0], self.coins[1], file=fp)  # Coin_0, Coin_1
        print(self.base_camps_hp[0],
              self.base_camps_hp[1], file=fp)  # HQ_0, HQ_1
        # print(len(self.barrack_list), file=fp)  # barrack_number
        for player in self.pheromon:
            for i in player:
                for j in i:
                    print("%.4f" % j, file=fp, end=' ')
                print('\n', file=fp, end='')
        fp.close()

    # simulation
    def next_round(self) -> None:
        self.get_income()

        self.apply_weapon()
        self.tower_attack()
        self.ant_move()
        self.update_pheromone_all()
        self.clear_ants()

        self.ant_born()

        # self.update_items()
        # self.get_items()
        # self.apply_items()
        # self.clear_items()
        self.update_weapon()
        # self.show()
        self.round += 1

    def get_lightning_cd(self, player):
        return self.item_cd[player][0]

    def get_emp_cd(self, player):
        return self.item_cd[player][1]

    def get_shield_cd(self, player):
        return self.item_cd[player][2]

    def get_protection_cd(self, player):
        return self.item_cd[player][3]
