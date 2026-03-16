import sys
import requests
import time

base_api = "https://api.dev.saiblo.net/api/"


def login(username, password):
    r = requests.post(
        base_api + "token/",
        json={"method": "password", "username": username, "password": password},
        timeout=5,
    )
    return r.json()["access"]


def upload_logic(token, game_id, logic):
    r = requests.post(
        base_api + "entities/" + str(game_id) + "/codes/",
        headers={"authorization": "Bearer " + token},
        files={"file": open(logic, "rb")},
        timeout=5,
    )
    return r.json()["id"]


def check_compile_status(token, game_id, id):
    r = requests.get(
        base_api + "entities/" + str(game_id) + "/codes/",
        headers={"authorization": "Bearer " + token},
        timeout=5,
    )
    logic_list = r.json()
    for logic in logic_list:
        if logic["id"] == id:
            if logic["compile_status"] == "编译成功":
                return True
            if logic["compile_status"] == "编译中":
                return False
            print(logic["compile_message"])
            sys.exit(-1)
    print("Logic not found")
    sys.exit(-1)


def set_logic_active(token, game_id, id):
    r = requests.put(
        base_api + "entities/" + str(game_id) + "/codes/" + str(id) + "/",
        headers={"authorization": "Bearer " + token},
        json={"activate": True},
        timeout=5,
    )
    return r.json()["err_msg"] == "设置成功"


def main():
    if len(sys.argv) != 4:
        print("Usage: python saiblo.py <game_id> <logic_file> <admin_password>")
        sys.exit(-1)

    game_id = int(sys.argv[1])
    logic = sys.argv[2]
    print("Uploading " + logic + " to game " + str(game_id) + "...")
    password = sys.argv[3]

    token = login("admin", password)
    logic_id = upload_logic(token, game_id, logic)
    print("Uploaded Logic ID: " + str(logic_id))

    time.sleep(5)
    while not check_compile_status(token, game_id, logic_id):
        print("Waiting for compile...")
        time.sleep(5)
    print("Compile success")

    if set_logic_active(token, game_id, logic_id):
        print("Logic activated")
    else:
        print("Logic activation failed")
        sys.exit(-1)


if __name__ == "__main__":
    main()
