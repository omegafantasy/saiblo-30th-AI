from common import *
from protocol import *
import sys
def my_operations() -> list[Operation]:
    global game, player
    if game.round == 1 and player == 0:
        my_game = game.copy()
        
        for _ in range(512):
            my_game.show()
            ops = copy_my_operations(my_game, player)
            my_game.apply_operations(player, ops)
            ops = copy_my_operations(my_game, 1 - player)
            my_game.apply_operations(1 - player, ops)
            
            my_game.next_round()

    op_list = []
    coin = game.coin(player)
    if game.round == 1:
        # op_list.append(Operation(OperationType.unlimit_coins))
        if not player:
            op_list.append(Operation(OperationType.build_tower, 5, 6))
        else:
            op_list.append(Operation(OperationType.build_tower, 12, 6))
    if game.round == 2:
        if not player:
            op_list.append(Operation(OperationType.build_tower, 5, 12))
        else:
            op_list.append(Operation(OperationType.build_tower, 12, 12))
    if coin >= 100 and game.get_base_hp_level(player) == 0:
        op_list.append(Operation(OperationType.upgrade_ant_hp))
        coin -= 100
    if coin >= 150 and player == 1 and game.get_lightning_cd(player) == 0:
        # print("use lightning!", coin,game.round, file=sys.stderr)
        op_list.append(Operation(OperationType.use_item_1, 2, 9))
        coin -= 150
    # if coin >= 150 and player == 0 and game.get_emp_cd(player) == 0:
    #     op_list.append(Operation(OperationType.use_item_2, 12, 6))
    #     print("use emp!", coin,game.round, file=sys.stderr)
        # coin -= 150
    ant_player_0 = [0,0]
    ant_player_1 = [0,0]
    for ant in game.ants():
        if ant.player == 0:
            if ant.y < 4:
                ant_player_0[0] += 1
            elif ant.y > 13:
                ant_player_0[1] += 1
        else:
            if ant.y < 4:
                ant_player_1[0] += 1
            elif ant.y > 13:
                ant_player_1[1] += 1
    if (ant_player_0[0] >= 2) and player and coin >= game.towercost[player] and game.tower_at(13, 3) is None:
        op_list.append(Operation(OperationType.build_tower, 13, 3))
        coin -= game.towercost[player]
    if (ant_player_0[1] >= 2) and player and coin >= game.towercost[player] and game.tower_at(13, 15) is None:
        op_list.append(Operation(OperationType.build_tower, 13, 15))
        coin -= game.towercost[player]
    if (ant_player_1[0] >= 2) and not player and coin >= game.towercost[player] and game.tower_at(5, 3) is None:
        op_list.append(Operation(OperationType.build_tower, 5, 3))
        coin -= game.towercost[player]
    if (ant_player_1[1] >= 2) and not player and coin >= game.towercost[player] and game.tower_at(5, 15) is None:
        op_list.append(Operation(OperationType.build_tower, 5, 15))
        coin -= game.towercost[player]
        
    
    if coin >= 60:
        if not player and game.tower_of_id(0).level == 0 and game.tower_of_id(0).player == 0:
            op_list.append(Operation(OperationType.upgrade_tower, 0, 3))
            coin -= 60
        elif player and game.tower_of_id(1).level == 0:
            op_list.append(Operation(OperationType.upgrade_tower, 1, 1))
            coin -= 60
    if coin >= 150:
        if not player and game.tower_of_id(0).level == 3:
            op_list.append(Operation(OperationType.upgrade_tower, 0, 31))
            coin -= 100
        elif player and game.tower_of_id(1).level == 1:
            op_list.append(Operation(OperationType.upgrade_tower, 1, 12))
            coin -= 100
        
    return op_list


def copy_my_operations(game: AntGame, player: int) -> list[Operation]:
    # global game, player
    op_list = []
    coin = game.coin(player)
    if game.round == 1:
        # op_list.append(Operation(OperationType.unlimit_coins))
        if not player:
            op_list.append(Operation(OperationType.build_tower, 5, 6))
        else:
            op_list.append(Operation(OperationType.build_tower, 12, 6))
    if game.round == 2:
        if not player:
            op_list.append(Operation(OperationType.build_tower, 5, 12))
        else:
            op_list.append(Operation(OperationType.build_tower, 12, 12))
    if coin >= 100 and game.get_base_hp_level(player) == 0:
        op_list.append(Operation(OperationType.upgrade_ant_hp))
        coin -= 100
    if coin >= 150 and player == 1 and game.get_lightning_cd(player) == 0:
        # print("use lightning!", coin,game.round, file=sys.stderr)
        op_list.append(Operation(OperationType.use_item_1, 2, 9))
        coin -= 150
    # if coin >= 150 and player == 0 and game.get_emp_cd(player) == 0:
    #     op_list.append(Operation(OperationType.use_item_2, 12, 6))
    #     print("use emp!", coin,game.round, file=sys.stderr)
        # coin -= 150
    ant_player_0 = [0,0]
    ant_player_1 = [0,0]
    for ant in game.ants():
        if ant.player == 0:
            if ant.y < 4:
                ant_player_0[0] += 1
            elif ant.y > 13:
                ant_player_0[1] += 1
        else:
            if ant.y < 4:
                ant_player_1[0] += 1
            elif ant.y > 13:
                ant_player_1[1] += 1
    if (ant_player_0[0] >= 2) and player and coin >= game.towercost[player] and game.tower_at(13, 3) is None:
        op_list.append(Operation(OperationType.build_tower, 13, 3))
        coin -= game.towercost[player]
    if (ant_player_0[1] >= 2) and player and coin >= game.towercost[player] and game.tower_at(13, 15) is None:
        op_list.append(Operation(OperationType.build_tower, 13, 15))
        coin -= game.towercost[player]
    if (ant_player_1[0] >= 2) and not player and coin >= game.towercost[player] and game.tower_at(5, 3) is None:
        op_list.append(Operation(OperationType.build_tower, 5, 3))
        coin -= game.towercost[player]
    if (ant_player_1[1] >= 2) and not player and coin >= game.towercost[player] and game.tower_at(5, 15) is None:
        op_list.append(Operation(OperationType.build_tower, 5, 15))
        coin -= game.towercost[player]
        
    
    if coin >= 60:
        if not player and game.tower_of_id(0).level == 0 and game.tower_of_id(0).player == 0:
            op_list.append(Operation(OperationType.upgrade_tower, 0, 3))
            coin -= 60
        elif player and game.tower_of_id(1).level == 0:
            op_list.append(Operation(OperationType.upgrade_tower, 1, 1))
            coin -= 60
    if coin >= 150:
        if not player and game.tower_of_id(0).level == 3:
            op_list.append(Operation(OperationType.upgrade_tower, 0, 31))
            coin -= 100
        elif player and game.tower_of_id(1).level == 1:
            op_list.append(Operation(OperationType.upgrade_tower, 1, 12))
            coin -= 100

    return op_list

# with open("test-python.txt", 'w') as f:
#     f.write(str(111))
player, seed = protocol.read_init_info()

game = AntGame(seed)

while 1:
       
    
    ops = []
    if player == 0:
        
        ops = my_operations()
        game.apply_operations(0, ops)
        
       
        protocol.send_operations(ops)
        opponent = protocol.read_opponent_operations()
        
        game.apply_operations(1, opponent)
    else:
        opponent = protocol.read_opponent_operations()
        game.apply_operations(0, opponent)
        ops = my_operations()
        game.apply_operations(1, ops)
        protocol.send_operations(ops)
    round_info = protocol.read_round_info()
    game.update_round_info(round_info)


