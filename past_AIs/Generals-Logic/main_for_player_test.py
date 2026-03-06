import json
import random

from logic.execute import execute_single_command
from logic.constant import *
from logic.gamedata import *
from logic.gamestate import GameState, init_generals, update_round
from logic.generate_round_replay import get_single_round_replay


def show_map(state: GameState):
    print(state.round)
    print(state.coin)
    print(state.active_super_weapon)
    print(state.tech_level)
    for row in state.board:
        for element in row:
            print(element.type, end=" ")
            print(element.player, end=" ")
            print(element.army)
    for element in state.generals:
        if type(element).__name__ == "MainGenerals":
            typenow = 0
        elif type(element).__name__ == "SubGenerals":
            typenow = 1
        else:
            typenow = 2
        print(element.id, end=" ")
        print(typenow, end=" ")
        print(element.player, end=" ")
        print(element.position[0], end=" ")
        print(element.position[1])


def show_map_to_file(state: GameState, file_name: str):
    # open the file for writing
    f = open(file_name, "a")
    # write the state information to the file
    f.write(str(state.round) + "\n")
    f.write(str(state.coin) + "\n")
    f.write(str(state.tech_level) + "\n")
    for row in state.board:
        for element in row:
            f.write(str(element.type) + " ")
            f.write(str(element.player) + " ")
            f.write(str(element.army) + " ")
        f.write("\n")
    for element in state.generals:
        if type(element).__name__ == "MainGenerals":
            typenow = 0
        elif type(element).__name__ == "SubGenerals":
            typenow = 1
        else:
            typenow = 2
        f.write(str(element.id) + " ")
        f.write(str(typenow) + " ")
        f.write(str(element.player) + " ")
        f.write(str(element.position[0]) + " ")
        f.write(str(element.position[1]) + "\n")
    # close the file
    f.close()


def show_replay(state):  # 显示replay文件的最后一行
    with open(state.replay_file, "r") as file:
        lines = file.readlines()
    if lines:
        last_line = lines[-1].strip()
        print(last_line)
    else:
        return None


if __name__ == "__main__":
    state = GameState()  # 每局游戏唯一的游戏状态类，所有的修改应该在此对象中进行
    # init_generals(gamestate)
    # gamestate.coin = [40, 40]

    init_json = """{"Round": 0, "Player": -1, "Action": [8], "Cells": [[[0, 0], -1, 0], [[0, 1], -1, 0], [[0, 2], -1, 0], [[0, 3], -1, 0], [[0, 4], -1, 0], [[0, 5], -1, 0], [[0, 6], -1, 0], [[0, 7], -1, 0], [[0, 8], -1, 0], [[0, 9], -1, 0], [[0, 10], -1, 0], [[0, 11], -1, 0], [[0, 12], -1, 0], [[0, 13], -1, 0], [[0, 14], -1, 0], [[1, 0], -1, 0], [[1, 1], -1, 0], [[1, 2], -1, 5], [[1, 3], -1, 0], [[1, 4], -1, 0], [[1, 5], -1, 0], [[1, 6], -1, 0], [[1, 7], -1, 0], [[1, 8], -1, 0], [[1, 9], -1, 0], [[1, 10], -1, 0], [[1, 11], -1, 0], [[1, 12], -1, 0], [[1, 13], -1, 0], [[1, 14], -1, 0], [[2, 0], -1, 0], [[2, 1], -1, 0], [[2, 2], -1, 0], [[2, 3], -1, 0], [[2, 4], -1, 0], [[2, 5], -1, 0], [[2, 6], -1, 0], [[2, 7], -1, 0], [[2, 8], -1, 0], [[2, 9], -1, 0], [[2, 10], -1, 0], [[2, 11], -1, 0], [[2, 12], -1, 0], [[2, 13], -1, 0], [[2, 14], -1, 0], [[3, 0], -1, 0], [[3, 1], -1, 0], [[3, 2], -1, 0], [[3, 3], -1, 0], [[3, 4], -1, 0], [[3, 5], -1, 0], [[3, 6], -1, 0], [[3, 7], -1, 0], [[3, 8], -1, 14], [[3, 9], -1, 0], [[3, 10], -1, 0], [[3, 11], -1, 0], [[3, 12], -1, 0], [[3, 13], -1, 0], [[3, 14], -1, 0], [[4, 0], -1, 0], [[4, 1], -1, 0], [[4, 2], -1, 0], [[4, 3], -1, 0], [[4, 4], -1, 0], [[4, 5], -1, 0], [[4, 6], -1, 0], [[4, 7], -1, 0], [[4, 8], -1, 0], [[4, 9], -1, 0], [[4, 10], -1, 0], [[4, 11], -1, 0], [[4, 12], -1, 0], [[4, 13], -1, 0], [[4, 14], -1, 0], [[5, 0], -1, 0], [[5, 1], -1, 0], [[5, 2], -1, 0], [[5, 3], -1, 0], [[5, 4], -1, 0], [[5, 5], -1, 5], [[5, 6], -1, 0], [[5, 7], -1, 0], [[5, 8], -1, 0], [[5, 9], -1, 0], [[5, 10], -1, 0], [[5, 11], -1, 3], [[5, 12], -1, 0], [[5, 13], -1, 0], [[5, 14], -1, 0], [[6, 0], -1, 0], [[6, 1], -1, 0], [[6, 2], -1, 0], [[6, 3], -1, 0], [[6, 4], -1, 3], [[6, 5], -1, 0], [[6, 6], -1, 0], [[6, 7], -1, 0], [[6, 8], -1, 0], [[6, 9], -1, 0], [[6, 10], -1, 5], [[6, 11], -1, 19], [[6, 12], -1, 0], [[6, 13], -1, 0], [[6, 14], -1, 0], [[7, 0], -1, 0], [[7, 1], -1, 0], [[7, 2], -1, 0], [[7, 3], -1, 0], [[7, 4], -1, 0], [[7, 5], -1, 0], [[7, 6], -1, 0], [[7, 7], -1, 0], [[7, 8], -1, 0], [[7, 9], -1, 0], [[7, 10], -1, 0], [[7, 11], 0, 0], [[7, 12], -1, 0], [[7, 13], -1, 0], [[7, 14], -1, 0], [[8, 0], -1, 0], [[8, 1], -1, 0], [[8, 2], -1, 0], [[8, 3], -1, 0], [[8, 4], -1, 0], [[8, 5], -1, 3], [[8, 6], -1, 0], [[8, 7], -1, 5], [[8, 8], -1, 0], [[8, 9], -1, 0], [[8, 10], -1, 0], [[8, 11], -1, 0], [[8, 12], -1, 0], [[8, 13], -1, 0], [[8, 14], -1, 0], [[9, 0], -1, 0], [[9, 1], -1, 0], [[9, 2], -1, 0], [[9, 3], -1, 0], [[9, 4], -1, 0], [[9, 5], -1, 0], [[9, 6], 1, 0], [[9, 7], -1, 0], [[9, 8], -1, 0], [[9, 9], -1, 0], [[9, 10], -1, 0], [[9, 11], -1, 0], [[9, 12], -1, 0], [[9, 13], -1, 0], [[9, 14], -1, 0], [[10, 0], -1, 0], [[10, 1], -1, 0], [[10, 2], -1, 0], [[10, 3], -1, 0], [[10, 4], -1, 0], [[10, 5], -1, 0], [[10, 6], -1, 0], [[10, 7], -1, 0], [[10, 8], -1, 13], [[10, 9], -1, 0], [[10, 10], -1, 0], [[10, 11], -1, 0], [[10, 12], -1, 0], [[10, 13], -1, 0], [[10, 14], -1, 0], [[11, 0], -1, 16], [[11, 1], -1, 0], [[11, 2], -1, 0], [[11, 3], -1, 0], [[11, 4], -1, 0], [[11, 5], -1, 0], [[11, 6], -1, 0], [[11, 7], -1, 0], [[11, 8], -1, 0], [[11, 9], -1, 0], [[11, 10], -1, 0], [[11, 11], -1, 0], [[11, 12], -1, 0], [[11, 13], -1, 0], [[11, 14], -1, 0], [[12, 0], -1, 0], [[12, 1], -1, 0], [[12, 2], -1, 0], [[12, 3], -1, 0], [[12, 4], -1, 0], [[12, 5], -1, 0], [[12, 6], -1, 0], [[12, 7], -1, 0], [[12, 8], -1, 0], [[12, 9], -1, 0], [[12, 10], -1, 0], [[12, 11], -1, 0], [[12, 12], -1, 0], [[12, 13], -1, 0], [[12, 14], -1, 0], [[13, 0], -1, 0], [[13, 1], -1, 0], [[13, 2], -1, 0], [[13, 3], -1, 0], [[13, 4], -1, 0], [[13, 5], -1, 0], [[13, 6], -1, 0], [[13, 7], -1, 0], [[13, 8], -1, 0], [[13, 9], -1, 0], [[13, 10], -1, 0], [[13, 11], -1, 0], [[13, 12], -1, 0], [[13, 13], -1, 0], [[13, 14], -1, 0], [[14, 0], -1, 0], [[14, 1], -1, 0], [[14, 2], -1, 0], [[14, 3], -1, 0], [[14, 4], -1, 3], [[14, 5], -1, 0], [[14, 6], -1, 0], [[14, 7], -1, 0], [[14, 8], -1, 0], [[14, 9], -1, 0], [[14, 10], -1, 0], [[14, 11], -1, 0], [[14, 12], -1, 0], [[14, 13], -1, 0], [[14, 14], -1, 0]], "Generals": [{"Id": 0, "Player": 0, "Type": 1, "Position": [7, 11], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 1, "Player": 1, "Type": 1, "Position": [9, 6], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 2, "Player": -1, "Type": 2, "Position": [6, 11], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 3, "Player": -1, "Type": 2, "Position": [10, 8], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 4, "Player": -1, "Type": 2, "Position": [3, 8], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 5, "Player": -1, "Type": 2, "Position": [11, 0], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 6, "Player": -1, "Type": 3, "Position": [14, 4], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 7, "Player": -1, "Type": 3, "Position": [6, 10], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 8, "Player": -1, "Type": 3, "Position": [8, 7], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 9, "Player": -1, "Type": 3, "Position": [5, 11], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 10, "Player": -1, "Type": 3, "Position": [1, 2], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 11, "Player": -1, "Type": 3, "Position": [8, 5], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 12, "Player": -1, "Type": 3, "Position": [5, 5], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}, {"Id": 13, "Player": -1, "Type": 3, "Position": [6, 4], "Level": [1, 1, 1], "Skill_cd": [0, 0, 0, 0, 0], "Skill_rest": [0, 0, 0], "Alive": 1}], "Weapons": [], "Weapon_cds": [-1, -1], "Tech_level": [[1, 0, 0, 0], [1, 0, 0, 0]], "Coins": [400000, 400000], "Cell_type": "000202000002100000000020200001000001000000000002000100101022000100000000120100000010020001000000000000000001000000000010000000000000100012000000002000022000000001000000000000000000000000101000000000000100100000000000200000000"}"""
    dict = json.loads(init_json)
    map = dict["Cells"]
    types = dict["Cell_type"]
    generals = dict["Generals"]
    for i in range(len(map)):
        state.board[int(i / row)][i % col].type = CellType(int(types[i]))
        state.board[int(i / row)][i % col].player = map[i][1]
        state.board[int(i / row)][i % col].army = map[i][2]
    for i in range(len(generals)):
        id, player = generals[i]["Id"], generals[i]["Player"]
        position = generals[i]["Position"]
        if generals[i]["Type"] == 1:
            general = MainGenerals(id, player, position)
        elif generals[i]["Type"] == 2:
            general = SubGenerals(id, player, position)
        else:
            general = Farmer(id, player, position)
        state.generals.append(general)
        state.board[position[0]][position[1]].generals = general
    state.coin = dict["Coins"]
    state.next_generals_id = len(generals)
    player0: int = 0
    player1: int = 1
    state.coin = [114514, 114514]
    show_map_to_file(state, "res.txt")
    # show_map(state)
    while 1:
        while 1:
            
            tmp = [int(i) for i in input().split()]
            try:
                print(0, tmp)
                if tmp != []:
                    if tmp[0] != 8:
                        issuccess = execute_single_command(0, state, tmp[0], tmp[1:])
                        if issuccess:
                            show_replay(state)
                        else:
                            print("False")
                    else:
                        print(
                            str(get_single_round_replay(state, [], 0, [8])).replace(
                                "'", '"'
                            )
                        )
                        break
                else:
                    break
            except KeyboardInterrupt:
                break
            else:
                continue
        while 1:
            tmp = [int(i) for i in input().split()]
            try:
                print(1, tmp)
                if tmp != []:
                    if tmp[0] != 8:
                        issuccess = execute_single_command(1, state, tmp[0], tmp[1:])
                        if issuccess:
                            show_replay(state)
                        else:
                            print("False")
                    else:
                        print(
                            str(get_single_round_replay(state, [], 1, [8])).replace(
                                "'", '"'
                            )
                        )
                        break
                else:
                    break
            except KeyboardInterrupt:
                break
            else:
                continue
        update_round(state)
        show_replay(state)
