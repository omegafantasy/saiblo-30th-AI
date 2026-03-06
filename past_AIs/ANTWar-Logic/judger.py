
import subprocess
import os, json
import sys
import threading

def send(msg: str):
    s = msg
    s = int.to_bytes(len(s), 4, 'big').decode('UTF-8') + s
    return s 

def read_stderr(stderr):
    with open("stderr.txt", "w") as f:
        while True:
            line = stderr.readline()
            if line:
                print(line, file=f)
            else:
                break

if __name__=='__main__':

    logic_path = sys.argv[1]
    ai_path = sys.argv[2]

    flag = True
    p_output = subprocess.Popen(logic_path,shell=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    p = []
    for i in range(2):
        # AI位置
        if ai_path[-2:] == "py":
            p.append(subprocess.Popen("python3 " + ai_path,shell=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE))
        else:
            p.append(subprocess.Popen(ai_path,shell=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE))
    # p[0].stdin.write('0 10086'.encode('UTF-8'))
    # 1. judger 在启动游戏逻辑后，向游戏逻辑发送初始化信息。
    with open(os.path.join('judger_src', 'init.json')) as f:
        msg = send(f.read()).encode("UTF-8")
        print("发送字节数:{}".format(p_output.stdin.write(msg)))
        p_output.stdin.flush()

    t = threading.Thread(target=read_stderr, args=(p[1].stderr,))

    print("AI初始化信息")
    n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
    print('from logic: {}'.format(n))
    output=p_output.stdout.read(4 + n)
    # print(output[4: ])
    output = json.loads(output[4: ])
    if 'end_info' in output.keys():
        flag = False
    print(output)
    # _ =input('pause')

    f = open("stderr.txt", "w")

    for i, msg in zip(output['player'], output['content']):
        print(msg.encode("UTF-8"))
        p[i].stdin.write(msg.encode("UTF-8"))
        p[i].stdin.flush()

    while flag:
        print("round start")
        # 检测到action时即可退出
        # 4 + 4 + n

        # # 一开始应该由逻辑发送正常回合信息，并监听player0信息
        # n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
        # print(n)
        # # if n > 2000:
        # #     output=p_output.stdout.read(4 + 50)
        # #     print(output)            
        # output=p_output.stdout.read(4 + n)
        # output: dict = json.loads(output[4: ])
        # print(output)
        # # 检测回合结束
        # if 'end_info' in output.keys():
        #     break
        # for i, msg in zip(output['player'], output['content']):
        #     p[i].stdin.write(msg.encode("UTF-8"))
        #     p[i].stdin.flush()

        # _ =input('从player0 接收信息')

        # 
        print("AI 限制信息")
        n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
        print('from logic: {}'.format(n))
        output=p_output.stdout.read(4 + n)
        # print(output[4: ])
        output = json.loads(output[4: ])
        if 'end_info' in output.keys():
            flag = False
        print(output)
        # _ =input('pause')

        # 从player0 接收信息
        print("从player0 接收信息")
        n = int.from_bytes(p[0].stdout.read(4), byteorder='big')
        print(n)

        # if (n > 500):
        #     print(p[0].stdout.read(11))
        package=p[0].stdout.read(n).decode("UTF-8")
        print(package)

        if n == 0:
            for line in p[0].stderr:
                print(line)

        # _ =input('将player0 信息(即操作)发给 逻辑')
        # 将player0 信息(即操作)发给 逻辑
        with open(os.path.join('judger_src', 'to_logic.json')) as f:
            msg = json.loads(f.read())
            msg['player'] = 0
            msg['content'] = package
            print(send(json.dumps(msg)).encode("UTF-8"))
            try:
                print("发送字节数:{}".format(p_output.stdin.write(send(json.dumps(msg)).encode("UTF-8"))))
                p_output.stdin.flush()
            except Exception as e:
                pass

        # 切换listen
        print('切换listen ')
        n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
        output = p_output.stdout.read(4 + n)
        tplayer = int.from_bytes(output[:4], byteorder='big', signed=True)
        output = output[4: ]
        print(output)
        # 检测回合结束
        if tplayer == -1:
            end_output = json.loads(output)
            if 'end_info' in end_output.keys():
                break


        # 逻辑接收 将信息转发给 player1 (逻辑请求 judger 直接将消息转发给指定 AI)
        # _ =input('将信息转发给 player1')
        n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
        output = p_output.stdout.read(4 + n)
        tplayer = int.from_bytes(output[:4], byteorder='big', signed=True)
        output = output[4: ]
        print(output)
        # 检测回合结束
        if tplayer == -1:
            end_output = json.loads(output)
            if 'end_info' in end_output.keys():
                break
        try:
            p[1].stdin.write(output)
            p[1].stdin.flush()
        except:
            for line in p[1].stderr.readlines():
                print(line)
        
        # 
        print("AI 限制信息")
        n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
        print('from logic: {}'.format(n))
        output=p_output.stdout.read(4 + n)
        # print(output[4: ])
        output = json.loads(output[4: ])
        if 'end_info' in output.keys():
            flag = False
        print(output)
        # _ =input('pause')

        # _ =input('从player1 接收信息')
        # 从player1 接收信息
        n = int.from_bytes(p[1].stdout.read(4), byteorder='big')
        print(n)
        package=p[1].stdout.read(n).decode("UTF-8")
        print(package)

        # _ =input('将player1 信息发给 逻辑')
        # 将player1 信息发给 逻辑
        with open(os.path.join('judger_src', 'to_logic.json')) as f:
            msg = json.loads(f.read())
            msg['player'] = 1
            msg['content'] = package

            try:
                print("发送字节数:{}".format(p_output.stdin.write(send(json.dumps(msg)).encode("UTF-8"))))
                p_output.stdin.flush()
            except Exception as e:
                pass

        # 切换listen
        print('切换listen ')
        n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
        output = p_output.stdout.read(4 + n)
        tplayer = int.from_bytes(output[:4], byteorder='big', signed=True)
        output = output[4: ]
        print(output)
        # 检测回合结束
        if tplayer == -1:
            end_output = json.loads(output)
            if 'end_info' in end_output.keys():
                break

        # _ =input('逻辑接收 将信息转发给 player0')   
        # 逻辑接收 将信息转发给 player0
        n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
        print(n)
        output = p_output.stdout.read(4 + n)
        tplayer = int.from_bytes(output[:4], byteorder='big', signed=True)
        output = output[4: ]
        print(output)
        
        # 检测回合结束
        if tplayer == -1:
            end_output = json.loads(output)
            if 'end_info' in end_output.keys():
                break
        p[0].stdin.write(output)
        p[0].stdin.flush()

        # _ =input('回合结束') 
        # next_turn(), 回合结束
        # 一开始应该由逻辑发送正常回合信息，并监听player0信息
        n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
        print(n)
        # if n > 2000:
        #     output=p_output.stdout.read(4 + 50)
        #     print(output)            
        output=p_output.stdout.read(4 + n)
        output: dict = json.loads(output[4: ])
        print(output)
        # 检测回合结束
        if 'end_info' in output.keys():
            break
        for i, msg in zip(output['player'], output['content']):
            p[i].stdin.write(msg.encode("UTF-8"))
            p[i].stdin.flush()

    # end_state
    print('end_state')
    t.join()
    # end_info = {
    #     "end_state": "[\"OK\"]",
    # }
    # msg = send(json.dumps(end_info)).encode("UTF-8")
    # print("发送字节数:{}".format(p_output.stdin.write(msg)))
    # p_output.stdin.flush()

    # # receive_end
    # n = int.from_bytes(p_output.stdout.read(4), byteorder='big')
    # print('from logic: {}'.format(n))
    # output=p_output.stdout.read(4 + n)
    # output = json.loads(output[4: ])
    # print(output)

