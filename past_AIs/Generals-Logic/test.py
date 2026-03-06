import json
import os
import unittest

import logic.constant as constant
from logic.execute import execute_single_command
from logic.gamedata import Farmer, MainGenerals, SubGenerals, SuperWeapon, WeaponType
from logic.gamestate import GameState, init_generals, update_round
from logic.generate_round_replay import get_single_round_replay
from load import *
from old_main import show_state


def load_move():
    # 读取JSON文件
    with open("test_config/map_move.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_move.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data)
    gamestate.replay_file = "replay/replay_move.json"
    # print(op_data)
    commands = op_data["operation"]
    return gamestate, commands


def load_attack_and_defence():
    with open("test_config/map_atdf.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_atdf.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data)
    gamestate.replay_file = "replay/replay_attack_and_defence.json"
    # print(op_data)
    commands = op_data["operation"]
    return gamestate, commands


def load_update_tech():
    with open("test_config/map_update_tech.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_update_tech.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data, 3, 3)
    gamestate.replay_file = "replay/replay_update_tech.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    return gamestate, commands


def load_update_generals():
    with open("test_config/map_update_generals.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_update_generals.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data, 3, 3)
    gamestate.replay_file = "replay/replay_update_generals.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    return gamestate, commands


def load_computation_skills():
    with open("test_config/map_computation_skills.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_computation_skills.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data)
    gamestate.replay_file = "replay/replay_computation_skills.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    return gamestate, commands


def load_computation_superweapon():
    with open("test_config/map_computation_superweapon.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_computation_superweapon.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data, 3, 3)
    gamestate.replay_file = "replay/replay_computation_superweapon.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    gamestate.tech_level = [[2, 0, 0, 1], [2, 0, 0, 1]]
    gamestate.super_weapon_cd = [0, 0]
    gamestate.super_weapon_unlocked = [True, True]
    return gamestate, commands


def load_not_enough_money():
    with open("test_config/map_update_generals.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_update_generals.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data, 3, 3)
    # print(op_data)
    commands = op_data["operation"]
    return gamestate, commands


def load_complex_movement():
    with open("test_config/map_complex_movement.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_complex_movement.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data)
    gamestate.replay_file = "replay/replay_complex_movement.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    gamestate.super_weapon_unlocked = [True, True]
    gamestate.super_weapon_cd = [0, 0]
    gamestate.generals[1].mobility_level = 2
    gamestate.board[1][1].generals.mobility_level = 2
    return gamestate, commands


def load_generals_movement():
    with open("test_config/map_generals_movement.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_generals_movement.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data)
    gamestate.replay_file = "replay/replay_general_movement.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    return gamestate, commands


def load_general_skills():
    with open("test_config/map_general_skills.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_general_skills.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data)
    gamestate.replay_file = "replay/replay_general_skills.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    return gamestate, commands


def load_call_generals():
    with open("test_config/map_call_generals.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_call_generals.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data, 3, 3)
    gamestate.replay_file = "replay/replay_call_generals.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    return gamestate, commands


def load_super_weapon():
    with open("test_config/map_super_weapon.json", "r") as f:
        json_data = f.read()
    with open("test_config/operation_super_weapon.json", "r") as f:
        op_data = json.load(f)
    gamestate = load_map_from_json(json_data)
    gamestate.replay_file = "replay/replay_super_weapon.json"
    # print(op_data)
    commands = op_data["operation"]
    gamestate.coin = [10000, 10000]
    return gamestate, commands


def check_super_weapon(state: GameState) -> bool:
    if state.board[0][0].army != 2:
        return False
    if state.board[1][1].army != 0:
        return False
    if state.board[19][9].army != 140:
        return False
    if state.board[19][10].army != 220:
        return False
    return True


def check_not_enough_money(state: GameState) -> bool:
    if state.coin != [0, 1]:
        return False
    if state.board[2][0].army != 4:
        return False
    if state.board[0][0].army != 2:
        return False
    return True


def check_test_move(state: GameState) -> bool:
    if state.round != 15:
        return False
    if state.board[0][0].army != 9:
        return False
    if state.board[0][1].army != 2:
        return False
    return True


def check_atdf(state: GameState) -> bool:
    if state.coin != [48, 74]:
        return False
    if state.board[0][0].army != 81:
        return False
    return True


def check_update_tech(state: GameState) -> bool:
    if state.coin != [9050, 10000]:
        return False
    if state.tech_level != [[5, 1, 1, 1], [2, 0, 0, 0]]:
        return False
    return True


def check_test_computation_skills(state: GameState) -> bool:
    if state.board[0][1].army != 36:
        return False
    if state.board[4][5].army != 45:
        return False
    if state.board[8][9].army != 51:
        return False
    if state.board[12][13].army != 51:
        return False
    if state.board[19][19].army != 51:
        return False
    if state.board[19][10].army != 51:
        return False
    if state.board[19][13].army != 51:
        return False
    if state.coin != [9800, 9700]:
        return False
    return True


def check_test_computation_superweapon(state: GameState) -> bool:
    if state.coin != [10000, 10000]:
        return False
    if state.board[0][1].army != 21:
        return False
    if state.board[1][0].army != 38:
        return False
    if state.board[0][0].army != 41:
        return False
    if state.board[1][1].army != 11:
        return False
    return True


def check_update_generals(state: GameState) -> bool:
    if state.coin != [9400, 9801]:
        return False
    if state.board[0][0].army != 5:
        return False
    if state.board[2][0].army != 8:
        return False
    return True


def check_test_complex_movement(state: GameState) -> bool:
    if state.board[1][0].player != 1:
        return False
    if state.board[1][0].army != 3:
        return False
    if len(state.active_super_weapon) != 1:
        return False
    if state.board[2][2].generals == None:
        return False
    return True


def check_generals_movement(state: GameState) -> bool:
    if state.generals[0].position != [0, 0]:
        return False
    if state.generals[1].position != [5, 5]:
        return False
    return True


def check_general_skills(state: GameState) -> bool:
    if state.board[1][0].army != 20:
        return False
    if state.board[0][1].army != 11:
        return False
    if state.board[4][3].army != 40:
        return False
    if state.board[8][7].army != 50 or state.board[8][7].player != 1:
        return False
    if state.coin != [9930, 10000]:
        return False
    return True


def check_call_generals(state: GameState) -> bool:
    if state.board[1][0].generals == None:
        return False
    elif (
        not isinstance(state.board[1][0].generals, SubGenerals)
        or state.board[1][0].generals.player != 0
    ):
        return False
    if state.board[1][1].generals == None:
        return False
    elif (
        not isinstance(state.board[1][1].generals, SubGenerals)
        or state.board[1][1].generals.player != 1
    ):
        return False
    if state.coin != [9950, 9950]:
        return False
    return True


def execute_commands(state, command) -> GameState:
    index = 0
    state.round = 0
    res = state.trans_state_to_init_json(0)

    with open(state.replay_file, "w") as f:
        f.write(str(res).replace("'", '"') + "\n")
    f.close()
    replay = get_single_round_replay(
        state,
        [],
        -1,
        [8],
    )
    with open(state.replay_file, "a") as f:
        f.write(str(replay).replace("'", '"') + "\n")
    state.round = 1
    try:
        while 1:
            FLAG = False
            while 1:
                # show_state(state)
                tmp = [int(num) for num in command[index]]
                index += 1
                if tmp != []:
                    print(
                        "success:",
                        execute_single_command(tmp[0], state, tmp[1], tmp[2:]),
                    )
                    if index == len(command):
                        show_state(state)
                        FLAG = True
                        break
                else:
                    if index == len(command):
                        show_state(state)
                        FLAG = True
                        break
                    break
            update_round(state)
            if FLAG == True:
                break

            for gen in state.generals:
                print(
                    "generals id: ", gen.id, "position: ", gen.position, end="   |   "
                )
            if index == len(command):
                show_state(state)
                break

    except Exception as e:
        print(e)
        return None
    return state


class TestGame(unittest.TestCase):
    def setUp(self):
        # Load initial game state and commands for each test case
        self.gamestates_and_commands = {
            "test_move": load_move(),
            "test_attack_and_defence": load_attack_and_defence(),
            "test_update_tech": load_update_tech(),
            "test_update_generals": load_update_generals(),
            "test_computation_skills": load_computation_skills(),
            "test_computation_superweapon": load_computation_superweapon(),
            "test_not_enough_money": load_not_enough_money(),
            "test_complex_movement": load_complex_movement(),
            "test_generals_movement": load_generals_movement(),
            "test_general_skills": load_general_skills(),
            "test_call_generals": load_call_generals(),
            "test_super_weapon": load_super_weapon(),
        }

    def test_test_move(self):
        gamestate, commands = self.gamestates_and_commands["test_move"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_test_move(gamestate))

    def test_attack_and_defence(self):
        gamestate, commands = self.gamestates_and_commands["test_attack_and_defence"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_atdf(gamestate))

    def test_update_tech(self):
        gamestate, commands = self.gamestates_and_commands["test_update_tech"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_update_tech(gamestate))

    def test_update_generals(self):
        gamestate, commands = self.gamestates_and_commands["test_update_generals"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_update_generals(gamestate))

    def test_computation_skills(self):
        gamestate, commands = self.gamestates_and_commands["test_computation_skills"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_test_computation_skills(gamestate))

    def test_computation_superweapon(self):
        gamestate, commands = self.gamestates_and_commands[
            "test_computation_superweapon"
        ]
        execute_commands(gamestate, commands)
        self.assertTrue(check_test_computation_superweapon(gamestate))

    def test_not_enough_money(self):
        gamestate, commands = self.gamestates_and_commands["test_not_enough_money"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_not_enough_money(gamestate))

    def test_complex_movement(self):
        gamestate, commands = self.gamestates_and_commands["test_complex_movement"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_test_complex_movement(gamestate))

    def test_generals_movement(self):
        gamestate, commands = self.gamestates_and_commands["test_generals_movement"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_generals_movement(gamestate))

    def test_general_skills(self):
        gamestate, commands = self.gamestates_and_commands["test_general_skills"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_general_skills(gamestate))

    def test_call_generals(self):
        gamestate, commands = self.gamestates_and_commands["test_call_generals"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_call_generals(gamestate))

    def test_super_weapon(self):
        gamestate, commands = self.gamestates_and_commands["test_super_weapon"]
        execute_commands(gamestate, commands)
        self.assertTrue(check_super_weapon(gamestate))


# a = TestGame()
# a.setUp()
# a.test_general_skills()
if not os.path.exists("replay"):
    os.mkdir("replay")
unittest.main()
