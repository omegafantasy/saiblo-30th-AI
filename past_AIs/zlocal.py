import json
import random
import time
import os
import argparse
import importlib.util

from core.GymEnvironment import PacmanEnv
from core.gamedata import *

ERROR_MAP = ["RE", "TLE", "OLE"]
replay_file = None


class Player:
    def __init__(
        self,
        id,
        type,
    ):
        self.id = id
        self.action = []
        self.type = type
        self.role = Role.PACMAN.value


def load_ai_func(module_path):
    if not os.path.isfile(module_path):
        raise FileNotFoundError(f"指定的路径不存在: {module_path}")

    module_name = os.path.splitext(os.path.basename(module_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "ai_func"):
        raise AttributeError(f"模块 {module_name} 中未找到 'ai_func' 函数")

    return module.ai_func


import subprocess
import select


def tolist_json_dump(obj):
    # handle numpy array inside iteratively
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return json.dumps({k: tolist_json_dump(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        return [tolist_json_dump(item) for item in obj]
    else:
        return obj


def load_ai_func_new(module_path, playerid, idx):
    if not os.path.isfile(module_path):
        raise FileNotFoundError(f"指定的路径不存在: {module_path}")

    # 判断是否为可执行文件
    if os.access(module_path, os.X_OK):
        # 启动C++子进程
        proc = subprocess.Popen(
            [module_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=open("logs/" + str(idx) + "_out" + str(playerid) + ".txt", "w"),
            bufsize=0,
            text=True,
            universal_newlines=True,
        )

        def cpp_ai_func_pac(env, func_action, pac_action=None, ghosts_action=None):
            # try:
            assert isinstance(env, PacmanEnv)
            if func_action == 0:
                proc.stdin.write("0\n")
                proc.stdin.flush()
                return [0]
            elif func_action == 1:
                dic = {"pacman_action": pac_action, "ghosts_action": ghosts_action}
                proc.stdin.write(json.dumps(dic) + "\n")
                proc.stdin.flush()
                return [0]
            if int(env._round) == 0:
                return_dict = env.get_return_dict()
                proc.stdin.write(tolist_json_dump(return_dict) + "\n")
                proc.stdin.flush()
            # timeout = 2.0
            # rlist, _, _ = select.select([proc.stdout], [], [], timeout)
            # if not rlist:
            #     raise TimeoutError("timeout")
            output_line = proc.stdout.readline().strip()
            if not output_line:
                raise EOFError("pac no output")
            action = int(output_line.split('"')[-2])
            proc.stdin.write("player 1 send info\n")
            proc.stdin.flush()
            return [action]
            # except Exception as e:
            #     stderr = proc.stderr.read()
            #     print(f"error: {e}, stderr: {stderr}")
            #     proc.terminate()
            #     raise e

        def cpp_ai_func_ghost(env, func_action, pac_action=None, ghosts_action=None):
            try:
                assert isinstance(env, PacmanEnv)
                if func_action == 0:
                    proc.stdin.write("1\n")
                    proc.stdin.flush()
                    return [0, 0, 0]
                elif func_action == 1:
                    dic = {"pacman_action": pac_action, "ghosts_action": ghosts_action}
                    proc.stdin.write(json.dumps(dic) + "\n")
                    proc.stdin.flush()
                    return [0, 0, 0]
                if env._round == 0:
                    return_dict = env.get_return_dict()
                    proc.stdin.write(tolist_json_dump(return_dict) + "\n")
                    proc.stdin.flush()
                proc.stdin.write("player 0 send info\n")
                proc.stdin.flush()
                output_line = proc.stdout.readline().strip()
                if not output_line:
                    raise EOFError("pac no output")
                actions = [int(i) for i in output_line.split('"')[-2].split(" ")]
                return actions
            except Exception as e:
                stderr = proc.stderr.read()
                print(f"error: {e}, stderr: {stderr}")
                proc.terminate()
                raise e

        if playerid == 0:
            return cpp_ai_func_pac
        else:
            return cpp_ai_func_ghost
    else:
        print("failed")


def get_ai_info(env: PacmanEnv, func, playerid, func_action, pac_action=None, ghosts_action=None):
    """
    获取ai或播放器用户的操作

    env: 游戏逻辑维护的唯一局面
    玩家0和玩家1的类型: 1 为 AI, 2 为网页播放器。
    """
    try:
        # 获取操作
        action = func(env, func_action, pac_action, ghosts_action)
        role = players[playerid].role

        if role == Role.PACMAN.value:
            # 表明玩家是吃豆人
            if len(action) != 1 or action[0] < 0 or action[0] >= 5:
                raise ValueError("Invalid action for PACMAN.")
        else:
            # 表明玩家是幽灵
            if len(action) != 3:
                raise ValueError("Invalid action count for ghost.")
            else:
                if action[0] < 0 or action[0] >= 5:
                    raise ValueError("Invalid action for ghost at index 0.")
                if action[1] < 0 or action[1] >= 5:
                    raise ValueError("Invalid action for ghost at index 1.")
                if action[2] < 0 or action[2] >= 5:
                    raise ValueError("Invalid action for ghost at index 2.")
        return role, action
    except:
        error = traceback.format_exc()
        return_dict = env.render()
        return_dict["StopReason"] = f"{error}"
        # 回放文件写入结束信息
        replay_file.write(json.dumps(return_dict, ensure_ascii=False) + "\n")

        end_state = ["OK", "OK"]
        end_state[playerid] = "IA"

        pacmanscore = env.get_pacman_score()
        ghostscore = env.get_ghosts_score()
        end_info = {}
        if players[0].role == Role.PACMAN.value:
            end_info = {
                "0": pacmanscore,
                "1": ghostscore,
            }
        else:
            end_info = {
                "0": ghostscore,
                "1": pacmanscore,
            }
        replay_file.close()
        exit(0)


def interact(env: PacmanEnv, pacman: Player, ghosts: Player):
    """
    执行操作，输出要转发给对方的字符串

    env: 游戏逻辑维护的唯一局面
    interact返回五个值: game_continue, info1, info2, level_change, eat_all_beans  info1和info2分别发给吃豆人和幽灵
    """
    # 执行两个玩家的操作
    try:
        get_ai_info(env, ai_func[pacman.id], pacman.id, 1, pacman.action[0], ghosts.action)
        get_ai_info(env, ai_func[ghosts.id], ghosts.id, 1, pacman.action[0], ghosts.action)
        info, pacman_reward, ghosts_reward, level_change, eat_all_beans = env.step(pacman.action[0], ghosts.action)

    except:
        error = traceback.format_exc()
        return_dict = env.render()
        return_dict["StopReason"] = f"Error in executing actions from players, error: {error}"
        replay_file.write(json.dumps(return_dict, ensure_ascii=False) + "\n")

        end_state = ["IA", "IA"]

        pacmanscore = env.get_pacman_score()
        ghostscore = env.get_ghosts_score()
        end_info = {}
        if pacman.id == 0:
            end_info = {
                "0": pacmanscore,
                "1": ghostscore,
            }
        else:
            end_info = {
                "0": ghostscore,
                "1": pacmanscore,
            }
        replay_file.close()
        exit(0)

    # 更新游戏状态
    new_state = env.render()
    replay_file.write(json.dumps(new_state, ensure_ascii=False) + "\n")
    # 返回新的状态信息
    game_continue = True
    info1 = ""  # 返回给吃豆人的信息
    info2 = ""  # 返回给幽灵的信息
    if pacman.type == Type.AI.value:
        info_to_ai = {"pacman_action": pacman.action[0], "ghosts_action": ghosts.action}
        info1 = json.dumps(info_to_ai, ensure_ascii=False)
    elif pacman.type == Type.PLAYER.value:
        info1 = json.dumps(new_state, ensure_ascii=False)
    if ghosts.type == Type.AI.value:
        info_to_ai = {"pacman_action": pacman.action[0], "ghosts_action": ghosts.action}
        info2 = json.dumps(info_to_ai, ensure_ascii=False)
    elif ghosts.type == Type.PLAYER.value:
        info2 = json.dumps(new_state, ensure_ascii=False)
    return game_continue, info1, info2, level_change, eat_all_beans


if __name__ == "__main__":
    import traceback

    if not os.path.exists("logs"):
        os.makedirs("logs")
    parser = argparse.ArgumentParser(description="Pac-Man AI Launcher")
    parser.add_argument("--make", "-m", type=bool, default=False)
    parser.add_argument("--idx", type=int, default=0)
    parser.add_argument("--dir_pacman", type=str, default="pac.exe")
    parser.add_argument("--dir_ghosts", type=str, default="ghost.exe")
    args = parser.parse_args()
    ai_func = []
    if args.make:
        import os

        os.system("make")
    # 从指定路径加载函数
    try:
        pacman_func = load_ai_func_new(args.dir_pacman, 0, args.idx)
        ghosts_func = load_ai_func_new(args.dir_ghosts, 1, args.idx)
        ai_func = [pacman_func, ghosts_func]
    except (FileNotFoundError, AttributeError) as e:
        print(f"加载模块失败: {e}")
        exit(0)
    try:
        # 接收judger的初始化信息
        init_info = {
            "player_list": [1, 1],
            "player_num": 2,
            "config": {"random_seed": 1674552577091},
            "replay": "./replay/replay" + str(args.idx) + ".json",
        }
        replay_path = init_info["replay"]
        replay_dir = os.path.dirname(replay_path)
        if not os.path.exists(replay_dir):
            os.makedirs(replay_dir)
        replay_file = open(replay_path, "w")
        # 设置随机种子
        try:
            seed = init_info["config"]["random_seed"]
        except:
            seed = random.randint(1, 100000000)

        env = PacmanEnv("logic")
        # 每局游戏唯一的游戏状态类，所有的修改应该在此对象中进行

        # playertype 0 表示未正常启动，1 表示本地 AI，2 表示网页播放器
        players = [Player(0, init_info["player_list"][0]), Player(1, init_info["player_list"][1])]

        players[0].role = Role.PACMAN.value
        players[1].role = Role.GHOSTS.value

        if players[0].type == Type.ABNORMAL.value or players[1].type == Type.ABNORMAL.value:
            # 状态异常，未正常启动
            end_dict = env.render()
            end_dict["StopReason"] = "player quit unexpectedly"
            end_json = json.dumps(end_dict, ensure_ascii=False)
            replay_file.write(end_json + "\n")

            end_state = json.dumps(["OK" if players[0].type else "RE", "OK" if players[1].type else "RE"])
            # 若初始化异常则都为0分
            end_info = {
                "0": 0,
                "1": 0,
            }
            replay_file.close()
            exit(0)

        # 第一回合发送座位信息
        state = 1

        game_continue = True
        level_change = False
        eat_all_beans = False
        first_round = False

        reset_info = env.reset().copy()
        reset_info["pacman_skill_status"] = reset_info["pacman_skill_status"].tolist()
        reset_info["board"] = reset_info["board"].tolist()
        reset_info["pacman_coord"] = reset_info["pacman_coord"].tolist()
        reset_info["ghosts_coord"] = [coord.tolist() for coord in reset_info["ghosts_coord"]]
        reset_info["portal_coord"] = reset_info["portal_coord"].tolist()

        init_json = json.dumps(reset_info, ensure_ascii=False)
        replay_file.write(init_json + "\n")
        print("init")
        # 第一次接收ai信息，设定更长的time，为sdk的初始化预留时间
        for i in range(2):
            state += 1

            players[i].role, players[i].action = get_ai_info(env, ai_func[i], players[i].id, 0)

        # 一局中包含三个state 1.接收吃豆人消息 2.接收幽灵消息 3.调用step
        while game_continue:
            print("level", env._level, "round", env._round)
            if first_round != True:
                # 考察是否需要重新渲染，如果level发生改变，重置环境+获取初始化信息
                if level_change == True:
                    if env.get_level() >= MAX_LEVEL:
                        game_continue = False

                    else:
                        reset_info = env.reset().copy()
                        reset_info["pacman_skill_status"] = reset_info["pacman_skill_status"].tolist()
                        reset_info["board"] = reset_info["board"].tolist()
                        reset_info["pacman_coord"] = reset_info["pacman_coord"].tolist()
                        reset_info["ghosts_coord"] = [coord.tolist() for coord in reset_info["ghosts_coord"]]
                        reset_info["portal_coord"] = reset_info["portal_coord"].tolist()

                        init_json = json.dumps(reset_info, ensure_ascii=False)
                        replay_file.write(init_json + "\n")
                        level_change = False

                if not game_continue:
                    break

                # 接受吃豆人的消息和幽灵的消息
                for i in range(2):
                    state += 1

                    role, players[i].action = get_ai_info(env, ai_func[i], players[i].id, 2)
                    if role != players[i].role:
                        # 角色信息错误
                        return_dict = env.render()
                        return_dict["StopReason"] = f"Role error."
                        # 回放文件写入结束信息
                        replay_file.write(json.dumps(return_dict, ensure_ascii=False) + "\n")

                        end_state = ["OK", "OK"]
                        end_state[i] = "IA"

                        pacmanscore = env.get_pacman_score()
                        ghostscore = env.get_ghosts_score()
                        end_info = {}
                        if players[0].role == Role.PACMAN.value:
                            end_info = {
                                "0": pacmanscore,
                                "1": ghostscore,
                            }
                        else:
                            end_info = {
                                "0": ghostscore,
                                "1": pacmanscore,
                            }

                        replay_file.close()
                        exit(0)
            else:
                first_round = False

            # 调用step
            state += 1

            if players[0].role == Role.PACMAN.value:
                # 0号玩家是吃豆人
                game_continue, info1, info2, level_change, eat_all_beans = interact(env, players[0], players[1])
            else:
                # 1号玩家是吃豆人
                game_continue, info1, info2, level_change, eat_all_beans = interact(env, players[1], players[0])

        end_state = json.dumps(["OK", "OK"])
        pacmanscore = env.get_pacman_score()
        ghostscore = env.get_ghosts_score()

        end_json = env.render()
        if eat_all_beans == True:
            end_json["StopReason"] = f"Pacman ate all the beans!!!"
        else:
            end_json["StopReason"] = f"time is up"
        end_info = {}
        if players[0].role == Role.PACMAN.value:
            end_info = {
                "0": pacmanscore,
                "1": ghostscore,
            }
        else:
            end_info = {
                "0": ghostscore,
                "1": pacmanscore,
            }

        replay_file.write(json.dumps(end_json, ensure_ascii=False) + "\n")
        replay_file.close()
        exit(0)

    except Exception as e:
        replay_file.write(traceback.format_exc())
        replay_file.write(str(e))
        replay_file.close()

    replay_file.close()
