import json
import random
import struct
import sys

import logic.constant as constant
from logic.execute import execute_single_command
from logic.gamedata import Farmer, MainGenerals, SubGenerals, SuperWeapon, WeaponType
from logic.gamestate import GameState, init_generals, update_round
from logic.generate_round_replay import get_single_round_replay
from load import *

# 分别代表两个玩家，0是第一个玩家，1是第二个玩家，与gamestate里的相对应


# 发送数据包给 Judger
def send_to_judger(data, target=-1):
    length = len(data)
    header = struct.pack(">Ii", length, target)
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(data)
    sys.stdout.flush()


# 接收judger发来的数据包
def receive_from_judger():
    header = sys.stdin.buffer.read(4)
    length = struct.unpack(">I", header)[0]
    data = sys.stdin.buffer.read(length)
    sys.stdin.buffer.flush()
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
def send_round_config(time: int, length: int):
    round_config = {"state": 0, "time": time, "length": length}
    round_config_str = json.dumps(round_config)
    round_config_bytes = round_config_str.encode("utf-8")
    send_to_judger(round_config_bytes)


# 逻辑向judger发生地图信息
def send_map_info(state: int, content: list[str]):
    round_info = {"state": state, "listen": [], "player": [0, 1], "content": content}
    round_info_bytes = json.dumps(round_info).encode("utf-8")
    send_to_judger(round_info_bytes)


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


# judger 向逻辑发送 AI 正常或异常消息
def receive_ai_info():
    ai_info_bytes = receive_from_judger()
    ai_info_str = ai_info_bytes.decode("utf-8")
    ai_info = json.loads(ai_info_str)
    return ai_info


# 逻辑表示对局已结束，向 judger 请求 AI 结束状态
def request_ai_end_state():
    request_end = {"action": "request_end_state"}
    request_end_bytes = json.dumps(request_end).encode("utf-8")
    send_to_judger(request_end_bytes)


# judger 向逻辑回复 AI 结束状态
def receive_ai_end_state():
    ai_end_state_bytes = receive_from_judger()
    ai_end_state_str = ai_end_state_bytes.decode("utf-8")
    ai_end_state = json.loads(ai_end_state_str)
    return ai_end_state


# 逻辑向judger发送游戏结束信息
def send_game_end_info(end_info: str, end_state: str):
    game_end_info = {"state": -1, "end_info": end_info, "end_state": end_state}
    game_end_info_bytes = json.dumps(game_end_info).encode("utf-8")
    send_to_judger(game_end_info_bytes)


# 判断游戏是否结束
def is_game_over(gamestate: GameState) -> int:
    is_general0_alive, is_general1_alive = 0, 0
    for general in gamestate.generals:
        if isinstance(general, MainGenerals):
            if general.player == 0:
                is_general0_alive = 1
            elif general.player == 1:
                is_general1_alive = 1
    if is_general1_alive == 0:
        return 0
    elif is_general0_alive == 0:
        return 1
    else:
        if gamestate.round <= 500:
            return -1
    if gamestate.round > 500:
        army0_num, army1_num = 0, 0
        cell0_num, cell1_num = 0, 0
        for i in range(20):
            for j in range(20):
                if gamestate.board[i][j].player == 0:
                    army0_num += gamestate.board[i][j].army
                    cell0_num += 1
                elif gamestate.board[i][j].player == 1:
                    army1_num += gamestate.board[i][j].army
                    cell1_num += 1
        if army0_num > army1_num:
            return 0
        elif army1_num > army0_num:
            return 1
        else:
            if cell0_num > cell1_num:
                return 0
            elif cell1_num > cell0_num:
                return 1
            else:
                if gamestate.coin[0] > gamestate.coin[1]:
                    return 0
                elif gamestate.coin[1] > gamestate.coin[0]:
                    return 1
        return 0


def convert_command_list_str(command_list_str: str):
    res: list[list[int]] = []
    with open("command_list_str.txt", "w") as f:
        f.write(command_list_str)
    for command_str in command_list_str.split("\n"):
        command = command_str.split()
        command = [int(num) for num in command]
        res.append(command)
    return res


def quit_running(er):
    with open(gamestate.replay_file, "a") as f:
        f.write(er + "\n")
    f.close()
    end_state = json.dumps(["IA", "IA"])
    end_info = {"0": 0, "1": 0}
    send_game_end_info(json.dumps(end_info), end_state)


def write_debug_into_replay(gamestate, message):
    with open(gamestate.replay_file, "a") as f:
        f.write(message + "\n")
    f.close()


def read_human_information_and_apply(gamestate: GameState, player, enemy_human):
    command_list_str = ""
    while 1:
        # 持续收消息
        ai_info = receive_ai_info()
        write_debug_into_replay(
            gamestate,
            "receive human info from player " + str(player) + ": " + str(ai_info),
        )
        # 出现错误，退出游戏
        if ai_info["player"] == -1:
            gamestate.winner = 1 - player
            # request_ai_end_state()
            # end_state = receive_ai_end_state().get("end_state")
            with open(gamestate.replay_file, "a") as f:
                f.write(
                    str(
                        {
                            "Round": gamestate.round,
                            "Player": gamestate.winner,
                            "Action": [9],
                        }
                    ).replace("'", '"')
                    + "\n"
                )
            f.close()
            end_state = json.dumps(["IA", "OK"])
            end_info = {"0": player, "1": 0 if player == 1 else 0}
            send_game_end_info(json.dumps(end_info), end_state)
            return False, ""

        if ai_info["content"] == "8\n":
            # 操作结束，停止接收消息
            command_list_str += "8\n"
            break
        else:
            # 执行操作
            command = ai_info["content"][:-1].split()
            command = [int(i) for i in command]
            success = execute_single_command(player, gamestate, command[0], command[1:])
            if success:
                # 操作成功，返回操作结果
                send_to_judger(
                    (
                        open(gamestate.replay_file, "r").readlines()[-1].strip() + "\n"
                    ).encode("utf-8"),
                    player,
                )
                if enemy_human:
                    # 如果对方是播放器，同时向对方转发结果
                    send_to_judger(
                        (
                            open(gamestate.replay_file, "r").readlines()[-1].strip()
                            + "\n"
                        ).encode("utf-8"),
                        1 - player,
                    )
                # 检查游戏是否结束，如果结束则停止操作
                gamestate.winner = is_game_over(gamestate)
                if gamestate.winner != -1:
                    break
            else:
                # 操作不成功，通知播放器
                send_to_judger(
                    str(get_single_round_replay(gamestate, [], player, [-1])).encode(
                        "utf-8"
                    ),
                    player,
                )

    # 玩家操作结束后，判断游戏是否结束
    if gamestate.winner != -1:
        with open(gamestate.replay_file, "a") as f:
            f.write(
                str(
                    {
                        "Round": gamestate.round,
                        "Player": gamestate.winner,
                        "Action": [9],
                    }
                ).replace("'", '"')
                + "\n"
            )
        f.close()
        end_state = json.dumps(["OK", "OK"])
        end_info = {"0": 1 - gamestate.winner, "1": gamestate.winner}
        send_game_end_info(json.dumps(end_info), end_state)
        return False, ""

    if player == 0:
        send_to_judger(
            (
                str(get_single_round_replay(gamestate, [], player, [8])).replace(
                    "'", '"'
                )
                + "\n"
            ).encode("utf-8"),
            player,
        )
        if enemy_human:
            # 如果对方是播放器，同时向对方转发结果
            send_to_judger(
                (
                    str(get_single_round_replay(gamestate, [], player, [8])).replace(
                        "'", '"'
                    )
                    + "\n"
                ).encode("utf-8"),
                1 - player,
            )
    else:
        # 如果是后手，更新回合
        update_round(gamestate)
        # 向播放器发送回合更新信息
        update_info = json.loads(
            open(gamestate.replay_file, "r").readlines()[-1].strip()
        )
        update_info["Player"] = player
        send_to_judger(
            (str(update_info).replace("'", '"') + "\n").encode("utf-8"),
            player,
        )
        if enemy_human:
            # 如果对方是播放器，同时向对方转发结果
            send_to_judger(
                (str(update_info).replace("'", '"') + "\n").encode("utf-8"),
                1 - player,
            )

        # 判断游戏是否结束
        gamestate.winner = is_game_over(gamestate)
        if gamestate.winner != -1:
            # request_ai_end_state()
            # end_state = receive_ai_end_state().get("end_state")
            with open(gamestate.replay_file, "a") as f:
                f.write(
                    str(
                        {
                            "Round": gamestate.round,
                            "Player": gamestate.winner,
                            "Action": [9],
                        }
                    ).replace("'", '"')
                    + "\n"
                )
            f.close()
            end_state = json.dumps(["OK", "OK"])
            end_info = {"0": 1 - gamestate.winner, "1": gamestate.winner}
            send_game_end_info(json.dumps(end_info), end_state)
            return False, ""

    return True, command_list_str


def read_ai_information_and_apply(gamestate: GameState, player, enemy_human):
    ai_info = receive_ai_info()
    write_debug_into_replay(
        gamestate, "receive ai info from player " + str(player) + ": " + str(ai_info)
    )

    if ai_info["player"] == -1:
        # 如果信息异常，胜负已分，游戏结束
        gamestate.winner = 0 if player == 1 else 0

        with open(gamestate.replay_file, "a") as f:
            f.write(
                str(
                    {
                        "Round": gamestate.round,
                        "Player": gamestate.winner,
                        "Action": [9],
                    }
                ).replace("'", '"')
                + "\n"
            )
        f.close()
        end_state = json.dumps(["IA", "OK"])
        end_info = {"0": player, "1": 0 if player == 1 else 0}
        send_game_end_info(json.dumps(end_info), end_state)
        return False, ""

    # 进行操作
    command_list_str = ai_info["content"]

    # 检查操作字符串合法性
    if command_list_str[-2:] != "8\n":
        command_list_str = ai_info["content"]
        gamestate.winner = 0 if player == 1 else 0
        # request_ai_end_state()
        # end_state = receive_ai_end_state().get("end_state")
        with open(gamestate.replay_file, "a") as f:
            f.write(
                str(
                    {
                        "Round": gamestate.round,
                        "Player": gamestate.winner,
                        "Action": [9],
                    }
                ).replace("'", '"')
                + "\n"
            )
        f.close()
        end_state = json.dumps(["IA", "OK"])
        end_info = {"0": player, "1": 0 if player == 1 else 0}
        send_game_end_info(json.dumps(end_info), end_state)
        return False, ""

    command_list = convert_command_list_str(command_list_str)

    for command in command_list:
        if command[0] == 8:
            break
        if command[0] != 8:
            success = execute_single_command(player, gamestate, command[0], command[1:])
            # 如果操作失败，胜负已分
            if not success:
                gamestate.winner = 1
                break
            # 如果对方是播放器，向对方发送操作结果
            if enemy_human:
                send_to_judger(
                    (
                        open(gamestate.replay_file, "r").readlines()[-1].strip() + "\n"
                    ).encode("utf-8"),
                    1 - player,
                )
            # 如果满足条件，胜负已分
            gamestate.winner = is_game_over(gamestate)  # isgameover返回-1代表没结束
            if gamestate.winner != -1:
                break

    # 玩家0的操作回合结束后，判断游戏是否结束
    if gamestate.winner != -1:
        with open(gamestate.replay_file, "a") as f:
            f.write(
                str(
                    {
                        "Round": gamestate.round,
                        "Player": gamestate.winner,
                        "Action": [9],
                    }
                ).replace("'", '"')
                + "\n"
            )
        f.close()
        end_state = json.dumps(["OK", "OK"])
        end_info = {"0": 1 - gamestate.winner, "1": gamestate.winner}
        send_game_end_info(json.dumps(end_info), end_state)
        return False, ""

    # 发送正常回合消息
    # quit_running("before send round info")
    if player == 0:
        if enemy_human:
            # 如果对方是播放器，同时向对方转发结果
            send_to_judger(
                (
                    str(get_single_round_replay(gamestate, [], player, [8])).replace(
                        "'", '"'
                    )
                    + "\n"
                ).encode("utf-8"),
                1 - player,
            )
    elif player == 1:
        update_round(gamestate)
        update_info = json.loads(
            open(gamestate.replay_file, "r").readlines()[-1].strip()
        )
        update_info["Player"] = player
        if enemy_human:
            # 如果对方是播放器，同时向对方转发结果
            send_to_judger(
                (str(update_info).replace("'", '"') + "\n").encode("utf-8"),
                1 - player,
            )
        # 判断游戏是否结束
        gamestate.winner = is_game_over(gamestate)
        if gamestate.winner != -1:
            # request_ai_end_state()
            # end_state = receive_ai_end_state().get("end_state")
            with open(gamestate.replay_file, "a") as f:
                f.write(
                    str(
                        {
                            "Round": gamestate.round,
                            "Player": gamestate.winner,
                            "Action": [9],
                        }
                    ).replace("'", '"')
                    + "\n"
                )
            f.close()
            end_state = json.dumps(["OK", "OK"])
            end_info = {"0": 1 - gamestate.winner, "1": gamestate.winner}
            send_game_end_info(json.dumps(end_info), end_state)
            return False, ""

    return True, command_list_str


if __name__ == "__main__":
    import traceback

    try:
        constant.mountain_persent = random.uniform(0.05, 0.1)
        constant.bog_percent = random.uniform(0.05, 0.25)
        gamestate = GameState()  # 每局游戏唯一的游戏状态类，所有的修改应该在此对象中进行
        init_generals(gamestate)
        gamestate.coin = [4000000, 4000000]
        # state=load_map_from_json("name")#加载已有地图
        # 接收judger的初始化信息
        # send_round_config(0, 1, 1024)

        init_info = receive_init_info()
        gamestate.replay_file = init_info["replay"]
        player_type = init_info["player_list"]
        state = 0

        # 写入初始化json
        init_json = gamestate.trans_state_to_init_json(-1)
        init_json["Round"] = 0
        with open(gamestate.replay_file, "w") as f:
            f.write(str(init_json).replace("'", '"') + "\n")
        f.close()

        state += 1

        if player_type[0] == 1:
            send_round_config(1, 1024)
        else:
            send_round_config(100, 1024)
        # 向双方AI发送初始化信息
        json0 = gamestate.trans_state_to_init_json(0)
        json0["Round"] = 0
        json1 = gamestate.trans_state_to_init_json(1)
        json1["Round"] = 0
        send_round_info(
            state,
            [0],
            [0, 1],
            [
                str(json0).replace("'", '"') + "\n",
                str(json1).replace("'", '"') + "\n",
            ],
        )
        # state += 1

        player = 0
        game_continue = True
        while game_continue:
            # send_round_config(state, 1, 1024)
            if player_type[player] == 1:
                send_round_config(1, 1024)
                game_continue, operation_string = read_ai_information_and_apply(
                    gamestate, player, player_type[1 - player] == 2
                )
            elif player_type[player] == 2:
                send_round_config(300, 1024)
                game_continue, operation_string = read_human_information_and_apply(
                    gamestate, player, player_type[1 - player] == 2
                )

            if not game_continue:
                break
            player = 1 - player
            state += 1
            if player_type[player] == 1:
                send_round_info(
                    state,
                    [player],
                    [player],
                    [operation_string],
                )
            elif player_type[player] == 2:
                send_round_info(
                    state,
                    [player],
                    [],
                    [],
                )
    except Exception as e:
        errorFile = open(gamestate.replay_file, "a")
        errorFile.write(traceback.format_exc())
        errorFile.close()
        quit_running("")
