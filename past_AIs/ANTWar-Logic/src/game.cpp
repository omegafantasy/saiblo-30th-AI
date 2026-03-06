#include "game.hpp"
#include <algorithm>
#include <iostream>
#include <tuple>
using json = nlohmann::json;

// type of tower behaviors
#define TOWER_DESTROY_TYPE -1
#define TOWER_BUILD_TYPE 0
#define TOWER_UPGRADE_TYPE 1
#define TOWER_ATTACK_TYPE 2
// max coordinates of map
#define INIT_CAMP_HP 50
// max level of defensive tower
#define TOWER_MAX_LEVEL 2
// type of barrack behaviors
#define BARRACK_DESTROY_TYPE -1
#define BARRACK_BUILD_TYPE 0
// #define MAX_TIME 10
void Game::init()
{

    round = 0;
    is_end = false;
    winner = -1;
    std::ofstream fout(mini_replay);
    fout.close();
    player0.ant_target_x = PLAYER_1_BASE_CAMP_X;
    player0.ant_target_y = PLAYER_1_BASE_CAMP_Y;
    player1.ant_target_x = PLAYER_0_BASE_CAMP_X;
    player1.ant_target_y = PLAYER_0_BASE_CAMP_Y;

    // read initial info from judger
    from_judger_init judger_init;
    read_from_judger<from_judger_init>(judger_init);
    record_file = judger_init.get_replay();

    json config = judger_init.get_config();
    if (config.contains("random_seed"))
    {
        random_seed = config["random_seed"];
    }
    else
    {
        std::random_device rd;
        random_seed = rd();
    }
    map.init_pheromon(random_seed);
    // send config json to judger
    // default config

    if (judger_init.get_player_num() != 2)
    {
        std::cerr << "player_num is not equal to 2\n";
        exit(0);
    }
    // if both players run error, player 1 loses
    for (int i = 0; i < 2; i++)
    {
        if (judger_init.get_AI_state(i) == 1)
        {
            state[i] = AI_state::OK;
            output_to_judger.init_player_state(i, true);
        }
        else if (judger_init.get_AI_state(i) == 2)
        {
            state[i] = AI_state::HUMAN_PLAYER;
            output_to_judger.init_player_state(i, false);
        }
        else
        {
            state[i] = AI_state::INITIAL_ERROR;
            is_end = true;
            winner = (i == 0) ? (1) : (0);
        }
    }
    for (int i = 0; i < 2; i++)
    {
        for (int j = 0; j < ItemType::Count; j++)
        {
            item[i].push_back(Item(0, 0, 0, 0));
        }
    }
    output_to_judger.init_to_player(random_seed, map.get_pheromone());
    base_camp0 = {PLAYER_0_BASE_CAMP_X, PLAYER_0_BASE_CAMP_Y, 0, 0, 0,
                  INIT_CAMP_HP /*initial hp*/},
    base_camp1 = {PLAYER_1_BASE_CAMP_X, PLAYER_1_BASE_CAMP_Y, 1, 0, 0,
                  INIT_CAMP_HP /*initial hp*/};
    map.map[PLAYER_0_BASE_CAMP_X][PLAYER_0_BASE_CAMP_Y].base_camp = &base_camp0;
    map.map[PLAYER_1_BASE_CAMP_X][PLAYER_1_BASE_CAMP_Y].base_camp = &base_camp1;
}
void Game::update_items()
{

    for (int i = 0; i < 2; i++)
        for (auto &it : item[i])
        {
            if (it.duration != 0)
                it.duration -= 1;
            if (it.cd != 0)
                it.cd -= 1;
        }
}
bool Game::is_ended() { return is_end; }

void Game::attack_ants()
{
    // super_weapon
    for (int i = 0; i < 2; i++)
    {
        int player = i;
        Item &it = item[player][ItemType::LightingStorm];
        if (it.duration)
        {
            for (auto &ant : ants)
            {
                if (ant.get_player() == !player &&
                    distance(Pos(it.x, it.y), Pos(ant.get_x(), ant.get_y())) <=
                        3)
                {
                    ant.set_hp_true(-100);
                }
            }
        }
    }
    for (auto &ant : ants)
    {
        ant.defend = 0;
        Item it = item[ant.get_player()][ItemType::Deflectors];
        if (it.duration &&
            distance(Pos(ant.get_x(), ant.get_y()), Pos(it.x, it.y)) <= 3)
        {
            ant.defend = 1;
        }
        ant.is_frozen = false;
    }
    for (auto &tower : defensive_towers)
    {
        if (tower.destroy())
            continue;
        // EMP
        Item it = item[!tower.get_player()][ItemType::EMPBlaster];
        if (it.duration &&
            distance(Pos(tower.get_x(), tower.get_y()), Pos(it.x, it.y)) <= 3)
        {
            continue;
        }

        Ant *target = tower.find_attack_target(ants);

        tower.round++;
        if (tower.round >= tower.get_spd() && target != nullptr)
        {
            auto type = tower.get_type();
            tower.set_changed_this_round();
            if (type == TowerType::Mortar || type == TowerType::MortarPlus ||
                type == TowerType::Missile)
            { // AOE
                tower.add_attacked_ants(target->get_id());
                tower.round_damage(ants, target->get_x(), target->get_y(),
                                   type == TowerType::Missile ? 2 : 1);
            }
            else if (type == TowerType::Pulse)
            {
                tower.round_damage(ants, tower.get_x(), tower.get_y(), 2);
            }
            else if (type == TowerType::Double)
            {
                tower.add_attacked_ants(target->get_id());
                target->set_hp(-tower.get_damage());
                target = tower.find_attack_target(ants);
                if (target != nullptr)
                {
                    target->set_hp(-tower.get_damage());
                    tower.add_attacked_ants(target->get_id());
                }
            }
            else if (type == TowerType::QuickPlus)
            {
                tower.add_attacked_ants(target->get_id());
                target->set_hp(-tower.get_damage());
                target = tower.find_attack_target(ants);
                if (target != nullptr)
                {
                    tower.add_attacked_ants(target->get_id());
                    target->set_hp(-tower.get_damage());
                }
            }
            else
            { // Single
                tower.add_attacked_ants(target->get_id());
                target->set_hp(-tower.get_damage());
                if (type == TowerType::Ice)
                {
                    target->is_frozen = true;
                }
            }

            tower.round = 0;
        }
        // output.add_tower(tower, TOWER_ATTACK_TYPE, attacked_ant->get_id());
    }
}

void Game::move_ants()
{
    for (auto &ant : ants)
    {
        int move = -1;

        if (ant.get_status() == Ant::Status::Alive) {
            int ant_target_x, ant_target_y;
            if (ant.get_player())
            {
                ant_target_x = PLAYER_0_BASE_CAMP_X;
                ant_target_y = PLAYER_0_BASE_CAMP_Y;
            }
            else
            {
                ant_target_x = PLAYER_1_BASE_CAMP_X;
                ant_target_y = PLAYER_1_BASE_CAMP_Y;
            }
            move = map.get_move(&ant, Pos(ant_target_x, ant_target_y));
        }
        ant.path.push_back(move);
        ant.move(move);
    }
}

void Game::generate_ants()
{

    if (base_camp0.create_new_ant(round))
    {

        ants.push_back(Ant(base_camp0.get_player(), ant_id, base_camp0.get_x(),
                           base_camp0.get_y(), base_camp0.get_ant_level()));
        output.add_ant(ants.back());
        ant_id++;
    }
    if (base_camp1.create_new_ant(round))
    {

        ants.push_back(Ant(base_camp1.get_player(), ant_id, base_camp1.get_x(),
                           base_camp1.get_y(), base_camp1.get_ant_level()));
        output.add_ant(ants.back());
        ant_id++;
    }
}

// if after one ant moves, base_camp of a player < 0, then return true
bool Game::manage_ants()
{

    /* save output, remove fail ant */
    for (auto ant_it = ants.begin(); ant_it != ants.end();)
    {
        output.add_ant(*ant_it);

        if (ant_it->get_status() == Ant::Status::Success)
        {
            if (ant_it->get_player())
            {
                base_camp0.set_hp(-1);
            }
            else
            {
                base_camp1.set_hp(-1);
            }
            ant_it = ants.erase(ant_it);
            if (judge_base_camp())
            {
                return false;
            }
        }
        else if (ant_it->get_status() == Ant::Status::Fail)
        {
            if (ant_it->get_player() == 1)
            {
                player0.coin.income_ant_kill(*ant_it);
                player0.opponent_killed_ant++;
            }
            else
            {
                player1.coin.income_ant_kill(*ant_it);
                player1.opponent_killed_ant++;
            }
            ant_it = ants.erase(ant_it);
        }
        else
        {
            ++ant_it;
        }
    }
    /* remove old*/
    for (auto ant_it = ants.begin(); ant_it != ants.end();) {
        if (ant_it->get_status() == Ant::Status::TooOld) {
            ant_it = ants.erase(ant_it);
        }
        else
        {
            ant_it++;
        }
    }
    return true;
}

void Game::increase_ant_age() {
    for (auto &ant : ants) {
        ant.increase_age();
    }
}

// when game ends, return true
bool Game::judge_base_camp()
{
    if (base_camp0.get_hp() <= 0 && base_camp1.get_hp() <= 0)
    {
        // player 0 wins
        is_end = 1;
        winner = 0;
        return true;
    }
    else if (base_camp1.get_hp() <= 0)
    {
        is_end = 1;
        winner = 0;
        return true;
    }
    else if (base_camp0.get_hp() <= 0)
    {
        is_end = 1;
        winner = 1;
        return true;
    }
    else
    {
        return false;
    }
}

void Game::judge_winner()
{
    // judge base_camp
    if (base_camp0.get_hp() < base_camp1.get_hp())
    {
        winner = 1;
        return;
    }
    else if (base_camp0.get_hp() > base_camp1.get_hp())
    {
        winner = 0;
        return;
    }
    else
    {
        // judge kiiled ants
        if (player0.opponent_killed_ant > player1.opponent_killed_ant)
        {
            winner = 0;
            return;
        }
        else if (player1.opponent_killed_ant > player0.opponent_killed_ant)
        {
            winner = 1;
            return;
        }
        else
        {
            // judge super weapons usage
            if (player0.super_weapons_usage < player1.super_weapons_usage)
            {
                winner = 0;
                return;
            }
            else if (player0.super_weapons_usage >
                     player1.super_weapons_usage)
            {
                winner = 1;
                return;
            }
            else
            {
                // judge AI_total_time
                if (player0.AI_total_time < player1.AI_total_time)
                {
                    winner = 0;
                    return;
                }
                else if (player0.AI_total_time > player1.AI_total_time)
                {
                    winner = 1;
                    return;
                }
                else
                {
                    // player 0 wins
                    winner = 0;
                    return;
                }
            }
        }
    }
}

void Game::update_coin()
{
    std::tuple<bool, int> coin0 = player0.coin.basic_income_and_penalty();
    std::tuple<bool, int> coin1 = player1.coin.basic_income_and_penalty();
    if (std::get<0>(coin0))
        player0.coin.set_coin(std::get<1>(coin0));
    else
        base_camp0.set_hp(std::get<1>(coin0));
    if (std::get<0>(coin1))
        player1.coin.set_coin(std::get<1>(coin1));
    else
        base_camp1.set_hp(std::get<1>(coin1));
}

// when game ends, return false
bool Game::next_round()
{

    // std::ofstream fout;
    // out.open("test_2.out");

    attack_ants();
    // fout << "atk "<< std::endl;
    move_ants();
    // fout << "mov "<< std::endl;
    update_pheromone();
    // fout << "upp "<< std::endl;
    manage_ants();
    // fout << "mng "<< std::endl;
    generate_ants();
    increase_ant_age();
    // fout << "gen "<< std::endl;
    update_coin();
    update_items();
    round++;
    if (round == MAX_ROUND)
    {
        is_end = 1;
        judge_winner();
        return false;
    }

    if (judge_base_camp())
    {
        return false;
    }
    return true;
}
void Game::update_pheromone()
{
    map.next_round();

    /* update pheromone*/
    for (auto ant = ants.begin(); ant != ants.end(); ant++)
    {
        map.update_pheromone(&*ant);
    }
}

bool Game::apply_operation(const std::vector<Operation> &op_list, int player,
                           std::string &err_msg)
{
    op[player] = op_list;
    bool camp_upgraded_flag = false;
    std::vector<int> used_tower;
    for (auto &op : op_list)
    {
        int x = op.get_pos_x();
        int y = op.get_pos_y();
        switch (op.get_operation_type())
        {
        case Operation::Type::TowerBuild:
        {
            /*if (!map.is_empty(x, y, player)) { // position judge
                err_msg = "TowerBuild: position is not empty";
                return false;
            }*/
            if (x > MAP_SIZE || y > MAP_SIZE || x < 0 || y < 0)
            {
                char msg[100];
                sprintf(msg, "TowerBuild: position out of range (at %d, %d)", x, y);
                err_msg = msg;
                return false;
            }
            if (map.map[x][y].base_camp != nullptr)
            {
                char msg[100];
                ;
                sprintf(msg, "TowerBuild: attempt to build a tower (at %d, %d), in which there is already a camp. (player id = %d)",
                        x, y, map.map[x][y].player);
                err_msg = msg;
                return false;
            }
            if (map.map[x][y].tower != nullptr)
            {
                char msg[100];
                ;
                sprintf(msg, "TowerBuild: attempt to build a tower (at %d, %d), in which there is already a tower. (player id = %d)",
                        x, y, map.map[x][y].player);
                err_msg = msg;
                return false;
            }
            if (map.map[x][y].player != player)
            {
                char msg[100];
                ;
                sprintf(msg, "TowerBuild: Build a tower at position (%d, %d), its player is %d, request player = %d", x, y, map.map[x][y].player, player);
                err_msg = msg;
                return false;
            }
            if (player == 1 &&
                !player1.coin.isEnough_tower_build())
            { // not enough money
                err_msg = "TowerBuild: P1 not enough money";
                return false;
            }
            if (player == 0 && !player0.coin.isEnough_tower_build())
            {
                err_msg = "TowerBuild: P0 not enough money";
                return false;
            }
            Item it = item[!player][ItemType::EMPBlaster];
            if (it.duration && distance(Pos(x, y), Pos(it.x, it.y)) <= 3)
            {
                err_msg = "TowerBuild: EMPBlaster is active";
                return false;
            }

            if (player == 1)
                player1.coin.cost_tower_build();
            else
                player0.coin.cost_tower_build();

            used_tower.push_back(tower_id);
            defensive_towers.push_back(DefenseTower{x, y, player, tower_id, 0});
            DefenseTower &new_tower = defensive_towers.back();
            map.build(&new_tower);
            new_tower.set_changed_this_round();
            // output.add_tower(new_tower, TOWER_BUILD_TYPE);
            tower_id++;
            break;
        }
        case Operation::Type::TowerUpgrade:
        {
            int id = op.get_id();
            if (id < 0 || id >= (int)defensive_towers.size() ||
                defensive_towers[id].destroy()|| defensive_towers[id].get_player() != player)
            {
                err_msg = "TowerUpgrade: Invalid Tower id";
                return false;
            }
            if (std::find(used_tower.begin(), used_tower.end(), id) !=
                used_tower.end())
            {
                err_msg = "TowerUpgrade: Tower has been used";
                return false;
            }
            Item it = item[!player][ItemType::EMPBlaster];
            if (it.duration && distance(Pos(x, y), Pos(it.x, it.y)) <= 3)
            {
                err_msg = "TowerUpgrade: EMPBlaster is active";
                return false;
            }

            DefenseTower &tower = defensive_towers[id];
            if (tower.get_level() ==
                TOWER_MAX_LEVEL)
            { // have reached max level
                err_msg = "TowerUpgrade: Tower has reached max level";
                return false;
            }
            if (player == 1 && !player1.coin.isEnough_tower_upgrade(
                                   tower))
            { // not enough money
                err_msg = "TowerUpgrade: P1 not enough money";
                return false;
            }
            if (player == 0 && !player0.coin.isEnough_tower_upgrade(tower))
            {
                err_msg = "TowerUpgrade: P0 not enough money";
                return false;
            }
            if (!tower.upgrade_type_check(op.get_args()))
            {
                err_msg = "TowerUpgrade: Invalid upgrade type";
                return false;
            }

            used_tower.push_back(id);
            if (player == 1) // must cost coin first!!
                player1.coin.cost_tower_upgrade(tower);
            else
                player0.coin.cost_tower_upgrade(tower);

            tower.upgrade(TowerType(op.get_args()));
            tower.set_changed_this_round();
            // output.add_tower(tower, op.get_args());
            break;
        }
        case Operation::Type::TowerDestroy:
        {
            int id = op.get_id();
            if (id < 0 || id >= (int)defensive_towers.size() ||
                defensive_towers[id].destroy() || defensive_towers[id].get_player() != player)
            {
                err_msg = "TowerDestroy: Invalid Tower id";
                return false;
            }
            if (std::find(used_tower.begin(), used_tower.end(), id) !=
                used_tower.end())
            {
                err_msg = "TowerDestroy: Tower has been used";
                return false;
            }
            Item it = item[!player][ItemType::EMPBlaster];
            if (it.duration && distance(Pos(x, y), Pos(it.x, it.y)) <= 3)
            {
                err_msg = "TowerDestroy: EMPBlaster is active";
                return false;
            }
            DefenseTower *defensive_tower = &defensive_towers[id];
            if (player == 1)
                player1.coin.income_tower_destroy(defensive_tower->get_level());
            else
                player0.coin.income_tower_destroy(defensive_tower->get_level());

            if (defensive_tower->get_type() == TowerType::Basic)
            {
                map.destroy(defensive_tower->get_x(), defensive_tower->get_y());
                output.add_tower(*defensive_tower, TOWER_DESTROY_TYPE,
                                 defensive_tower->get_attack());
                defensive_tower->set_destroy();
            }
            else
            {
                TowerType new_type = defensive_tower->tower_downgrade_type();
                defensive_tower->downgrade(new_type);
                defensive_tower->set_changed_this_round();
                // output.add_tower(*defensive_tower, new_type);
            }
            used_tower.push_back(id);
            break;
        }
        case Operation::Type::LightingStorm:
        {
            if (x < 0 || x >= MAP_SIZE || y < 0 ||
                y >= MAP_SIZE)
            { // position judge
                err_msg = "LightingStorm: invaid position";
                return false;
            }
            ItemType it = ItemType::LightingStorm;
            if (item[player][it].cd)
            {
                err_msg = "LightingStorm: in CD";
                return false;
            }
            if (player == 1 &&
                !player1.coin.isEnough_item_applied(it))
            { // not enough money
                err_msg = "LightingStorm: P1 not enough money";
                return false;
            }
            if (player == 0 && !player0.coin.isEnough_item_applied(it))
            {
                err_msg = "LightingStorm: P0 not enough money";
                return false;
            }

            if (player == 1)
                player1.coin.cost_item(it);
            else
                player0.coin.cost_item(it);

            if (player == 0)
                player0.super_weapons_usage++;
            else
                player1.super_weapons_usage++;
            item[player][it] = Item(it, x, y);

            break;
        }
        case Operation::Type::EMPBlaster:
        {
            if (x < 0 || x >= MAP_SIZE || y < 0 ||
                y >= MAP_SIZE)
            { // position judge
                err_msg = "EMPBlaster: invaid position";
                return false;
            }
            ItemType it = ItemType::EMPBlaster;
            if (item[player][it].cd)
            {
                err_msg = "EMPBlaster: in CD";
                return false;
            }
            if (player == 1 &&
                !player1.coin.isEnough_item_applied(it))
            { // not enough money
                err_msg = "EMPBlaster: P1 not enough money";
                return false;
            }
            if (player == 0 && !player0.coin.isEnough_item_applied(it))
            {
                err_msg = "EMPBlaster: P0 not enough money";
                return false;
            }
            if (player == 1)
                player1.coin.cost_item(it);
            else
                player0.coin.cost_item(it);

            if (player == 0)
                player0.super_weapons_usage++;
            else
                player1.super_weapons_usage++;
            item[player][it] = Item(it, x, y);
            break;
        }
        case Operation::Type::Deflectors:
        {
            if (x < 0 || x >= MAP_SIZE || y < 0 ||
                y >= MAP_SIZE)
            { // position judge
                err_msg = "Deflectors: invaid position";
                return false;
            }
            ItemType it = ItemType::Deflectors;
            if (item[player][it].cd)
            {
                err_msg = "Deflectors: in CD";
                return false;
            }
            if (player == 1 &&
                !player1.coin.isEnough_item_applied(it))
            { // not enough money
                err_msg = "Deflectors: P1 not enough money";
                return false;
            }
            if (player == 0 && !player0.coin.isEnough_item_applied(it))
            {
                err_msg = "Deflectors: P0 not enough money";
                return false;
            }
            if (player == 1)
                player1.coin.cost_item(it);
            else
                player0.coin.cost_item(it);

            item[player][it] = Item(it, x, y);

            if (player == 0)
                player0.super_weapons_usage++;
            else
                player1.super_weapons_usage++;

            break;
        }
        case Operation::Type::EmergencyEvasion:
        {
            if (x < 0 || x >= MAP_SIZE || y < 0 ||
                y >= MAP_SIZE)
            { // position judge
                err_msg = "EmergencyEvasion: invaid position";
                return false;
            }
            ItemType it = ItemType::EmergencyEvasion;
            if (item[player][it].cd)
            {
                err_msg = "EmergencyEvasion: in CD";
                return false;
            }
            if (player == 1 &&
                !player1.coin.isEnough_item_applied(it))
            { // not enough money
                err_msg = "EmergencyEvasion: P1 not enough money";
                return false;
            }
            if (player == 0 && !player0.coin.isEnough_item_applied(it))
            {
                err_msg = "EmergencyEvasion: P0 not enough money";
                return false;
            }
            if (player == 1)
                player1.coin.cost_item(it);
            else
                player0.coin.cost_item(it);

            if (player == 0)
                player0.super_weapons_usage++;
            else
                player1.super_weapons_usage++;
            for (auto &ant : ants)
            {
                if (ant.get_player() == player &&
                    distance(Pos(x, y), Pos(ant.get_x(), ant.get_y())) <= 3)
                {
                    ant.shield = 2;
                }
            }
            item[player][it] = Item(it, x, y);

            break;
        }

        case Operation::Type::BarrackUpgrade:
        {
            Headquarter &base_camp = player ? base_camp1 : base_camp0;
            if (camp_upgraded_flag)
            {
                err_msg = "BarrackUpgrade: already upgraded this tern";
                return false;
            }
            int level = base_camp.get_cd_level();
            if (level == 2)
            {
                err_msg = "BarrackUpgrade: already max level";
                return false;
            }
            if (player == 1 && !player1.coin.isEnough_base_camp_upgrade(
                                   level))
            { // not enough money
                err_msg = "BarrackUpgrade: P1 not enough money";
                return false;
            }
            if (player == 0 &&
                !player0.coin.isEnough_base_camp_upgrade(level))
            {
                err_msg = "BarrackUpgrade: P0 not enough money";
                return false;
            }
            camp_upgraded_flag = true;
            if (player == 1)
                player1.coin.cost_base_camp_upgrade(level);
            else
                player0.coin.cost_base_camp_upgrade(level);
            base_camp.barrack_upgrade();
            break;
        }
        case Operation::Type::AntUpgrade:
        {
            Headquarter &base_camp = player ? base_camp1 : base_camp0;
            if (camp_upgraded_flag)
            {
                err_msg = "BarrackUpgrade: already upgraded this tern";
                return false;
            }
            int level = base_camp.get_ant_level();
            if (level == 2)
            {
                err_msg = "AntUpgrade: already max level";
                return false;
            }
            if (player == 1 && !player1.coin.isEnough_base_camp_upgrade(
                                   level))
            { // not enough money
                err_msg = "AntUpgrade: P1 not enough money";
                return false;
            }
            if (player == 0 &&
                !player0.coin.isEnough_base_camp_upgrade(level))
            {
                err_msg = "AntUpgrade: P0 not enough money";
                return false;
            }
            camp_upgraded_flag = true;
            if (player == 1)
                player1.coin.cost_base_camp_upgrade(level);
            else
                player0.coin.cost_base_camp_upgrade(level);

            base_camp.ant_upgrade();
            break;
        }

        // case Operation::Type::PutAnt:
        // {
        //     if (!map.is_valid(x, y)) // position judge
        //         return false;

        //     ants.push_back(Ant(player, ant_id, x, y, 5));
        //     ant_id++;
        //     break;
        // }
        // case Operation::Type::DeleteAnt:
        // {
        //     int id = op.get_id();
        //     auto ant =
        //         std::find_if(ants.begin(), ants.end(), [id](const Ant &ant)
        //                      { return id == ant.get_id(); });
        //     if (ant == ants.end())
        //     {
        //         return false;
        //     }

        //     ants.erase(ant);
        //     break;
        // }
        // case Operation::Type::MaxCoin:
        //     if (player == 1)
        //         player1.coin.set_coin(100000);
        //     else
        //         player0.coin.set_coin(100000);
        //     break;
        default:
            return false;
        }
    }
    return true;
}

// void Game::dump_mini_replay(const std::string &filename) {
//     std::ofstream fout(filename, std::ios_base::app);
//     fout << round <<std::endl;
//     fout << player0.coin.get_coin() << " " << player1.coin.get_coin() <<
//     std::endl; fout << base_camp0.get_hp() << " " << base_camp1.get_hp() <<
//     std::endl; fout << barracks.size() << std::endl; for(auto barrack :
//     barracks) {
//         if(barrack.destroy()) continue;
//         fout << barrack.get_id() << " " << barrack.get_x() << " " <<
//         barrack.get_y() << " " << barrack.get_player() << std::endl;
//     }
//     fout << ants.size() << std::endl;
//     for(auto ant : ants) {
//         fout << ant.get_id() << " " << ant.get_x() << " " << ant.get_y() << "
//         " <<
//             ant.get_player() << " " << ant.get_hp() << " " <<
//             ant.get_status() << std::endl;
//     }
//     fout << defensive_towers.size() << std::endl;
//     for(auto tower : defensive_towers) {
//         if(tower.destroy()) continue;
//         fout << tower.get_id() << " " << tower.get_x() << " " <<
//         tower.get_y() << " " <<
//             tower.get_player() << " " << tower.get_type() << std::endl;
//     }
//     // items
//     std::vector<Item> exist_items;
//     for(auto item : items) {
//         if(item.get_state(round) != ItemState::Exist) continue;
//         exist_items.push_back(item);
//     }
//     fout << exist_items.size() << std::endl;
//     for(auto item : exist_items) {
//         fout << item.get_id() << " " << item.get_pos().x << " " <<
//         item.get_pos().y << " " << item.get_type() << std::endl;
//     }
//     // applied items
//     fout << buff_list.size() << std::endl;
//     for(auto buff : buff_list) {
//         fout << std::get<3>(buff) << " " << std::get<1>(buff) << " " <<
//         std::get<0>(buff) << std::endl;
//     }
//     fout.close();
// }

void Game::dump_round_state(/* const std::string &filename */)
{
    // state info
    for (auto &tower : defensive_towers)
    {
        if (tower.is_changed() && !tower.destroy())
        {
            output.add_tower(tower, tower.get_type(), tower.get_attack());
            tower.set_unchanged_before_another_round();
        }
    }
    output.add_camps(base_camp0, base_camp1);
    output.add_coins(player0.coin, player1.coin);
    output.add_pheromone(map.get_pheromone());
    output.add_winner(winner, "");
    if (!err_msg.empty())
        output.add_error(err_msg);

    // replay info
    output.add_operation(op);
    if (round == 1) {
        output.save_seed(random_seed);
    }
    output.save_data();
    // output.dump_cur(filename);
    output_to_judger.set_json_to_web_player(output.get_cur());
    output.update_cur(defensive_towers);

    // mini replay info
    // dump_mini_replay(mini_replay);

    // change cur to another new json so that it can send needed message to ai
    output_to_judger.send_info_to_judger(output.get_cur(), round);
    output.next_round();
}

void Game::dump_last_round(
    /* const std::string &filename */ const std::string &msg)
{
    for (auto tower : defensive_towers)
    {
        if (tower.is_changed())
        {
            output.add_tower(tower, tower.get_type(), tower.get_attack());
        }
    }
    output.add_camps(base_camp0, base_camp1);
    output.add_coins(player0.coin, player1.coin);
    output.add_pheromone(map.get_pheromone());

    output.add_winner(winner, msg);
    output.add_operation(op);
    output.add_error(err_msg);
    output.save_data();
    // output.dump_cur(filename);
    output_to_judger.set_json_to_web_player(output.get_cur());

    output.update_cur(defensive_towers);
    // dump_mini_replay(mini_replay);
    output_to_judger.send_info_to_judger(output.get_cur(), round);
}

void Game::dump_result(const std::string &filename)
{
    output.dump_all(filename);
}

Game::Game() {}

Game::~Game()
{
    // TO DO (important?)
}

bool Game::round_read_from_judger(int player)
{
    // player 0 & player 1

    read_from_judger<from_judger_round>(judger_round_info);

    std::string content = judger_round_info.get_content();

    if (judger_round_info.get_player() == -1)
    {
        json error;
        try
        {
            error = json::parse(content);
            int AI_ID = error["player"].get<int>();
            switch (error["error"].get<int>())
            {
            case 0:
            {
                state[AI_ID] = AI_state::RUN_ERROR;
                break;
            }
            case 1:
            {
                state[AI_ID] = AI_state::TIMEOUT_ERROR;
                break;
            }
            case 2:
            {
                state[AI_ID] = AI_state::OUTPUT_LIMIT;
                break;
            }
            default:
            {
                break;
            }
            }
            is_end = true;
            winner = (AI_ID == 0) ? (1) : (0);
            return false;
        }
        catch (const std::exception &e)
        {
            std::cerr << "Information of ai's error is not json\n";
            std::cerr << content << '\n';
            winner = -1;
            return false;
        }
    }
    else
    {
        judger_round_info.transfer_op(output_to_judger.if_ai(player));

        if (judger_round_info.get_player() != player)
        {
            is_end = true;
            winner = player;
            return false;
        }

        int another_player = 1 - player;

        std::vector<Operation> op_list = judger_round_info.get_op_list();
        if (!apply_operation(op_list, player, err_msg))
        {
            set_AI_state_IO(player);
            return false;
        }

        judger_round_info.send_operation(
            output_to_judger.if_ai(another_player));

        // update AI_total_time
        if (player == 0)
        {
            player0.AI_total_time += judger_round_info.get_time();
        }
        else
        {
            player1.AI_total_time += judger_round_info.get_time();
        }

        return true;
    }
}

void Game::request_end_state()
{
    json end_request = {{"action", "request_end_state"}};
    output_info(-1, end_request);
}

void Game::receive_end_state()
{
    end_from_judger end_state;
    read_from_judger<end_from_judger>(end_state);

    // use this to judge scores
    // TO DO
}

void Game::send_end_info()
{
    // scores of players, TO DO
    int score[2];
    if (winner == 0)
    {
        score[0] = 1;
        score[1] = 0;
    }
    else
    {
        score[0] = 0;
        score[1] = 1;
    }
    json end_info_json = {
        {"0", score[0]},
        {"1", score[1]},
    };
    std::string end_info = end_info_json.dump();
    std::string end_state = "[";
    // state of player 0 & player 1
    std::string AI_state_info[2] = {"OK", "OK"};
    for (int i = 0; i <= 1; i++)
    {
        switch (state[i])
        {
        case AI_state::OK:
        {
            AI_state_info[i] = "OK";
            break;
        }
        case AI_state::INITIAL_ERROR:
        {
            // AI_state_info[i] = "INITIAL_ERROR";
            AI_state_info[i] = "RE";
            break;
        }
        case AI_state::RUN_ERROR:
        {
            // AI_state_info[i] = "RUN_ERROR";
            AI_state_info[i] = "RE";
            break;
        }
        case AI_state::TIMEOUT_ERROR:
        {
            // AI_state_info[i] = "TIMEOUT_ERROR";
            AI_state_info[i] = "TLE";
            break;
        }
        case AI_state::OUTPUT_LIMIT:
        {
            // AI_state_info[i] = "OUTPUT_LIMIT";
            AI_state_info[i] = "OLE";
            break;
        }
        case AI_state::ILLEGAL_OPERATION:
        {
            // AI_state_info[i] = "ILLEGAL_OPERATION";
            AI_state_info[i] = "IA";
            break;
        }
        case AI_state::HUMAN_PLAYER:
        {
            // AI_state_info[i] = "HUMAN_PLAYER";
            AI_state_info[i] = "OK";
            break;
        }

        default:
        {
            break;
        }
        }
    }
    end_state =
        end_state + "\"" + AI_state_info[0] /*end state of player 0*/ + "\", ";
    end_state =
        end_state + "\"" + AI_state_info[1] /*end state of player 1*/ + "\"]";
    json end_message = {
        {"state", -1}, {"end_info", end_info}, {"end_state", end_state}};

    dump_last_round(/* "output.json" */ end_state);

    dump_result(get_record_file());
    output_info(-1, end_message);
}

std::string Game::get_record_file() { return record_file; }

void Game::set_AI_state_IO(int player)
{
    state[player] = AI_state::ILLEGAL_OPERATION;
    is_end = true;
    winner = (player == 0) ? (1) : (0);
}

template <typename T>
void Game::read_from_judger(T &des)
{
    int length = 0;
    for (int i = 1; i <= 4; i++)
        length = (length << 8) + getchar();
    std::string in;
    for (int i = 1; i <= length; i++)
    {
        char c = getchar();
        in = in + c;
    }
    json judger_json;

    try
    {
        judger_json = json::parse(in);
        des = judger_json;
    }
    catch (const std::exception &e)
    {
        std::cerr << "read from judger error\n";
        std::cerr << in << '\n';
        exit(0);
    }
}

void Game::listen(int player) { output_to_judger.listen_player(player); }
