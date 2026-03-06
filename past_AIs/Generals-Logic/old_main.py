import json
import random
import struct
import sys

import logic.constant as constant
from logic.execute import execute_single_command
from logic.gamedata import Farmer, MainGenerals, SubGenerals, SuperWeapon, WeaponType
from logic.gamestate import GameState, init_generals, update_round

# 分别代表两个玩家，0是第一个玩家，1是第二个玩家，与gamestate里的相对应


def count_surroundings(map, i, j, landtype):
    count = 0
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            ni = i + dx
            nj = j + dy
            if ni >= 0 and ni < constant.row and nj >= 0 and nj < constant.col:
                if map[ni][nj].type in landtype:
                    count += 1
    return count


def update_map(gamestate: GameState):
    for row in gamestate.board:
        for cell in row:
            if cell.type == 2:
                sur_num = count_surroundings(
                    gamestate.board, cell.position[0], cell.position[1], [2]
                )
                if sur_num < 3:
                    cell.type = 0

    for row in gamestate.board:
        for cell in row:
            if cell.type in [0, 1]:
                sur_num = count_surroundings(
                    gamestate.board, cell.position[0], cell.position[1], [0, 1]
                )
                if sur_num < 4:
                    cell.type = 2


# 发送数据包给 Judger
def send_to_judger(data, target=-1):
    length = len(data)
    header = struct.pack(">II", length, target)
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(data)
    sys.stdout.flush()


# 接收逻辑发来的数据包
def receive_from_judger():
    header = sys.stdin.buffer.read(4)
    length = struct.unpack(">I", header)[0]
    data = sys.stdin.buffer.read(length)
    return data


# judger 向逻辑发送初始化信息
def receive_init_info():
    # 接收来自 Judger 的字节流数据
    init_info_bytes = receive_from_judger()
    # 将字节流解码成字符串
    init_info_str = init_info_bytes.decode("utf-8")
    # 将JSON格式的字符串解析为 python 数据类型
    init_info = json.loads(init_info_str)
    return init_info


# 逻辑向judger发送回合配置信息
def send_round_config(state: int, time: int, length: int):
    round_config = {"state": state, "time": time, "length": length}
    round_config_str = json.dumps(round_config)
    round_config_bytes = round_config_str.encodes("utf-8")
    send_to_judger(round_config_bytes)


# 逻辑向 judger 发送正常回合消息
def send_round_info(
    state: int, listen: list[int], player: list[int], content: list[str]
):
    round_info = {
        "state": state,
        "listen": listen,
        "player": player,
        "content": content,
    }
    round_info_bytes = json.dumps(round_info).encode("utf-8")
    send_to_judger(round_info_bytes)


# 逻辑向 judger 发送观战消息
def send_watch_info(watch: str):
    watch_info = {"watch": watch}
    watch_info_bytes = json.dumps(watch_info).encode("utf-8")
    send_to_judger(watch_info_bytes)


# judger 向逻辑发送 AI 正常消息
def receive_ai_normal_info():
    ai_normal_info_bytes = receive_from_judger()
    ai_normal_info_str = ai_normal_info_bytes.decode("utf-8")
    ai_normal_info = json.loads(ai_normal_info_str)
    return ai_normal_info


# judger 向逻辑发送 AI 异常消息
def receive_ai_abnormal_info():
    ai_abnormal_info_bytes = receive_from_judger()
    ai_abnormal_info_str = ai_abnormal_info_bytes.decode("utf-8")
    ai_abnormal_info = json.loads(ai_abnormal_info_str)
    return ai_abnormal_info


# 逻辑表示对局已结束，向 judger 请求 AI 结束状态
def send_game_end(action: str):
    game_end = {"action": action}
    game_end_bytes = json.dumps(game_end).encode("utf-8")
    send_to_judger(game_end_bytes)


# judger 向逻辑回复 AI 结束状态
def receive_ai_end_state():
    ai_end_state_bytes = receive_from_judger()
    ai_end_state_str = ai_end_state_bytes.decode("utf-8")
    ai_end_state = json.loads(ai_end_state_str)
    return ai_end_state


def show_state(state: GameState):
    def print_color(color, end, message, background="0"):
        print("\033[" + color + ";" + background + "m" + message + "\033[0m", end=end)

    print("   ", end="")
    for i in range(15):
        print(str(format(i, "03d")), end="")
    print("")
    for i in range(constant.row):
        print(str(format(i, "03d")), end="")
        for j in range(constant.col):
            if state.board[i][j].player != -1:
                if state.board[i][j].player == 0:
                    print_color(
                        "0", "", str(format(state.board[i][j].army, "03d")), "41"
                    )

                elif state.board[i][j].player == 1:
                    print_color(
                        "0", "", str(format(state.board[i][j].army, "03d")), "44"
                    )
                else:
                    print("xxx", end="")
            else:
                if int(state.board[i][j].type) == 0:
                    print_color(
                        "0", "", str(format(state.board[i][j].army, "03d")), "47"
                    )
                elif int(state.board[i][j].type) == 1:
                    print_color(
                        "0", "", str(format(state.board[i][j].army, "03d")), "42"
                    )
                elif int(state.board[i][j].type) == 2:
                    print_color(
                        "0", "", str(format(state.board[i][j].army, "03d")), "43"
                    )
                else:
                    print(int(state.board[i][j].type), end=" ")
        print("")
    print("round:", state.round)
    print("coins:", state.coin)
    print("super weapons:", state.active_super_weapon)
    print("super weapon cds:", state.super_weapon_cd)
    print("tech level:", state.tech_level)
    for gen in state.generals:
        print(
            "|generals id: ",
            gen.id,
            "\t|type: ",
            type(gen).__name__,
            "\t|position: ",
            gen.position,
            "\tplayer:",
            gen.player,
        )
    # print("generals:")
    # for i in state.generals:
    #     print(i)


if __name__ == "__main__":
    state = GameState()  # 每局游戏唯一的游戏状态类，所有的修改应该在此对象中进行
    update_map(state)
    init_generals(state)

    show_state(state)
    print(state.trans_state_to_init_json(-1))
    player0: int = 0
    player1: int = 1
    state.coin = [114514, 114514]

    # 接收judger的初始化信息
    # init_info = receive_init_info()
    # state.replay_file = init_info["replay"]
    # 向 Judger发送回合配置信息
    # state = 0
    while 1:
        while 1:
            try:
                tmp = [
                    int(num)
                    for num in input(
                        "now player 0 play, please input your command: "
                    ).split()
                ]
                if tmp != []:
                    if tmp[0] != 8:
                        print(
                            "success:",
                            execute_single_command(0, state, tmp[0], tmp[1:]),
                        )
                        show_state(state)
                else:
                    show_state(state)
                    break
            except KeyboardInterrupt:
                break
            else:
                continue
        while 1:
            try:
                tmp = [
                    int(num)
                    for num in input(
                        "now player 1 play, please input your command: "
                    ).split()
                ]
                if tmp != []:
                    if tmp[0] != 8:
                        print(
                            "success:",
                            execute_single_command(1, state, tmp[0], tmp[1:]),
                        )
                        show_state(state)
                else:
                    show_state(state)
                    break
            except KeyboardInterrupt:
                break
            else:
                continue
        update_round(state)
