#include "include/template.hpp"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>
#define TIME1 0.15f
#define TIME2 0.2f
#define MAX_NODE_COUNT 20000

int positions[2][35][2] = {{{2, 9},  {4, 9}, {5, 9},  {5, 7},  {6, 9},  {5, 11}, {5, 6},  {6, 7}, {6, 11},
                            {5, 12}, {4, 3}, {5, 3},  {7, 8},  {7, 10}, {4, 15}, {5, 15}, {4, 2}, {6, 4},
                            {7, 5},  {8, 7}, {8, 11}, {7, 13}, {6, 14}, {4, 16}, {6, 1},  {6, 2}, {6, 16},
                            {6, 17}, {7, 1}, {8, 4},  {8, 14}, {7, 17}, {8, 2},  {8, 16}, {3, 9}},
                           {{16, 9},  {14, 9}, {13, 9},  {13, 7},  {12, 9},  {13, 11}, {12, 6},  {12, 7}, {12, 11},
                            {12, 12}, {14, 3}, {13, 3},  {10, 8},  {10, 10}, {14, 15}, {13, 15}, {13, 2}, {11, 4},
                            {11, 5},  {10, 7}, {10, 11}, {11, 13}, {11, 14}, {13, 16}, {12, 1},  {11, 2}, {11, 16},
                            {12, 17}, {11, 1}, {9, 4},   {9, 14},  {11, 17}, {9, 2},   {9, 16},  {15, 9}}};
bool emp_flag[34];
const int BASE = 0, C1 = 1, C2 = 2, C3 = 4, L1 = 3, L2 = 6, L3 = 7, R1 = 5, R2 = 9, R3 = 8, LL1 = 10, LL2 = 16,
          LL3 = 11, RR1 = 14, RR2 = 23, RR3 = 15, M1 = 19, M2 = 12, M3 = 13, M4 = 20, ML1 = 17, ML2 = 18, MR1 = 22,
          MR2 = 21, STORM = 34, FL1 = 24, FL2 = 25, FL3 = 28, FR1 = 27, FR2 = 26, FR3 = 31, F1 = 32, F2 = 29, F3 = 30,
          F4 = 33;

long total_eva_time = 0;
int SIDE = 0;
int current_round;
int global_state = 0;
int now_hp;
int base_old_count;
int base_die_count;
bool attack_flag = false;
SuperWeaponType last_superweapon_type;
int last_superweapon_round = -1;
short reserved = 0;

int GROUP[4];
int GROUP_COUNT;
inline void get_group(int code) {
    switch (code) {
    case C1:
    case C2:
    case C3:
        GROUP[0] = C1;
        GROUP[1] = C2;
        GROUP[2] = C3;
        GROUP_COUNT = 3;
        break;
    case L1:
    case L2:
    case L3:
        GROUP[0] = L1;
        GROUP[1] = L2;
        GROUP[2] = L3;
        GROUP_COUNT = 3;
        break;
    case R1:
    case R2:
    case R3:
        GROUP[0] = R1;
        GROUP[1] = R2;
        GROUP[2] = R3;
        GROUP_COUNT = 3;
        break;
    case LL1:
    case LL2:
    case LL3:
        GROUP[0] = LL1;
        GROUP[1] = LL2;
        GROUP[2] = LL3;
        GROUP_COUNT = 3;
        break;
    case RR1:
    case RR2:
    case RR3:
        GROUP[0] = RR1;
        GROUP[1] = RR2;
        GROUP[2] = RR3;
        GROUP_COUNT = 3;
        break;
    case M1:
    case M2:
    case M3:
    case M4:
        GROUP[0] = M1;
        GROUP[1] = M2;
        GROUP[2] = M3;
        GROUP[3] = M4;
        GROUP_COUNT = 4;
        break;
    case ML1:
    case ML2:
        GROUP[0] = ML1;
        GROUP[1] = ML2;
        GROUP_COUNT = 2;
        break;
    case MR1:
    case MR2:
        GROUP[0] = MR1;
        GROUP[1] = MR2;
        GROUP_COUNT = 2;
        break;
    case FL1:
    case FL2:
    case FL3:
        GROUP[0] = FL1;
        GROUP[1] = FL2;
        GROUP[2] = FL3;
        GROUP_COUNT = 3;
        break;
    case FR1:
    case FR2:
    case FR3:
        GROUP[0] = FR1;
        GROUP[1] = FR2;
        GROUP[2] = FR3;
        GROUP_COUNT = 3;
        break;
    case F1:
    case F2:
        GROUP[0] = F1;
        GROUP[1] = F2;
        GROUP_COUNT = 2;
        break;
    case F3:
    case F4:
        GROUP[0] = F3;
        GROUP[1] = F4;
        GROUP_COUNT = 2;
        break;
    }
}

inline Tower get_tower(int x, int y, const GameInfo &game_info) {
    for (auto &tower : game_info.towers) {
        if (tower.x == x && tower.y == y) {
            return tower;
        }
    }
    return Tower(-1, -1, -1, -1);
}

inline Tower get_tower(int id, const GameInfo &game_info) {
    for (auto &tower : game_info.towers) {
        if (tower.id == id) {
            return tower;
        }
    }
    return Tower(-1, -1, -1, -1);
}

inline int nearest_to_base_dis(const GameInfo &game_info) {
    int dis = 100;
    for (auto &ant : game_info.ants) {
        if (ant.player == SIDE) {
            dis = std::min(distance(ant.x, ant.y, positions[!SIDE][BASE][0], positions[!SIDE][BASE][1]), dis);
        }
    }
    return dis;
}

inline short safe_coin(const GameInfo &info) {
    int res = 0;
    if (info.super_weapon_cd[!SIDE][SuperWeaponType::EmpBlaster] >= 90)
        return 0;
    else if (info.super_weapon_cd[!SIDE][SuperWeaponType::EmpBlaster] > 0)
        return std::max((int)(std::min(info.coins[!SIDE], (short)(149)) -
                              info.super_weapon_cd[!SIDE][SuperWeaponType::EmpBlaster] * 1.66),
                        0);
    else
        return std::min(info.coins[!SIDE], (short)(149));
}

inline short get_safe_val(const GameInfo &info) { return std::min(0, info.coins[SIDE] - safe_coin(info)); }

inline char nearest_ant_dis(const GameInfo &info) {
    char res = 32, dis;
    for (int i = 0; i < info.ants.size(); i++) {
        if (info.ants[i].player == !SIDE) {
            dis = distance(info.ants[i].x, info.ants[i].y, positions[SIDE][BASE][0], positions[SIDE][BASE][1]);
            if (dis < res)
                res = dis;
        }
    }
    return res;
}

bool action_r1;
OperationType action_r2;
int action_r3, action_r4;

inline void action(int code, int type, const GameInfo &game_info, int &coins, int &towers, int up = 0,
                   int ignorecode = -1) {
    auto pos = positions[SIDE][code];
    if (type == 1) { // build
        if (coins < game_info.build_tower_cost(towers)) {
            action_r1 = false;
            return;
        }
        get_group(code);
        for (int i = 0; i < GROUP_COUNT; i++) {
            if (GROUP[i] == ignorecode)
                continue;
            if (game_info.building_tag[positions[SIDE][GROUP[i]][0]][positions[SIDE][GROUP[i]][1]] !=
                BuildingType::Empty) {
                action_r1 = false;
                return;
            }
        }
        coins -= game_info.build_tower_cost(towers);
        towers++;
        action_r1 = true;
        action_r2 = OperationType::BuildTower;
        action_r3 = pos[0];
        action_r4 = pos[1];
        return;
    } else if (type == 2) { // upgrade
        if (game_info.building_tag[pos[0]][pos[1]] == BuildingType::Empty) {
            action_r1 = false;
            return;
        }
        Tower tower = get_tower(pos[0], pos[1], game_info);
        TowerType target_type;
        // if (code == C1) {
        //     if (tower.type == TowerType::Basic) {
        //         target_type = TowerType::Mortar;
        //     } else if (tower.type == TowerType::Mortar) {
        //         target_type = TowerType::MortarPlus;
        //     } else {
        //         action_r1 = false;
        //         return;
        //     }
        // } else {
        if (tower.type / 10 > 0) {
            action_r1 = false;
            return;
        }
        if (tower.type == TowerType::Basic) {
            switch (up) {
            case 0:
                target_type = TowerType::Heavy;
                break;
            case 1:
                target_type = TowerType::Mortar;
                break;
            case 2:
                target_type = TowerType::Quick;
                break;
            }
        }
        if (tower.type == TowerType::Heavy) {
            switch (up) {
            case 0:
                target_type = TowerType::HeavyPlus;
                break;
            case 1:
                target_type = TowerType::Cannon;
                break;
            case 2:
                target_type = TowerType::Ice;
                break;
            }
        }
        if (tower.type == TowerType::Mortar) {
            switch (up) {
            case 0:
                target_type = TowerType::MortarPlus;
                break;
            case 1:
                target_type = TowerType::Missile;
                break;
            case 2:
                target_type = TowerType::Pulse;
                break;
            }
        }
        if (tower.type == TowerType::Quick) {
            switch (up) {
            case 0:
                target_type = TowerType::QuickPlus;
                break;
            case 1:
                target_type = TowerType::Double;
                break;
            case 2:
                target_type = TowerType::Sniper;
                break;
            }
        }
        // }

        if (coins < game_info.upgrade_tower_cost(target_type)) {
            action_r1 = false;
            return;
        } else {
            coins -= game_info.upgrade_tower_cost(target_type);
            action_r1 = true;
            action_r2 = OperationType::UpgradeTower;
            action_r3 = tower.id;
            action_r4 = target_type;
            return;
        }
    } else if (type == 3) { // destroy
        if (game_info.building_tag[pos[0]][pos[1]] == BuildingType::Empty) {
            action_r1 = false;
            return;
        }
        Tower tower = get_tower(pos[0], pos[1], game_info);
        if (tower.type != TowerType::Basic) {
            action_r1 = false;
            return;
        }
        coins += game_info.destroy_tower_income(towers);
        towers--;
        action_r1 = true;
        action_r2 = OperationType::DowngradeTower;
        action_r3 = tower.id;
        action_r4 = -1;
        return;
    } else if (type == 4) { // downgrade
        if (game_info.building_tag[pos[0]][pos[1]] == BuildingType::Empty) {
            action_r1 = false;
            return;
        }
        Tower tower = get_tower(pos[0], pos[1], game_info);
        if (tower.type == TowerType::Basic) {
            action_r1 = false;
            return;
        }
        coins += game_info.downgrade_tower_income(tower.type);
        action_r1 = true;
        action_r2 = OperationType::DowngradeTower;
        action_r3 = tower.id;
        action_r4 = -1;
        return;
    }
    action_r1 = false;
    return;
}

std::vector<std::vector<Operation>> series_action(int tac, const GameInfo &game_info) {
    std::vector<std::vector<Operation>> ops;
    bool valid, new_valid;
    OperationType type, new_type;
    int arg0, arg1, new_arg0, new_arg1;
    if (tac == 0) { // build 1
        int valid_codes[] = {C1, C2, C3, LL1, LL2, LL3, RR1, RR2, RR3, ML1, ML2, MR1, MR2, L1, L2,
                             L3, R1, R2, R3,  M1,  M2,  M3,  M4,  FL1, FL2, FL3, FR1, FR2, FR3};
        for (auto &valid_code : valid_codes) {
            if (emp_flag[valid_code])
                continue;
            int coins = game_info.coins[SIDE], towers = game_info.tower_num_of_player(SIDE);
            std::vector<Operation> op;
            action(valid_code, 1, game_info, coins, towers);
            valid = action_r1;
            type = action_r2;
            arg0 = action_r3;
            arg1 = action_r4;
            if (valid) {
                op.emplace_back(type, arg0, arg1);
                ops.emplace_back(op);
            }
        }
    } else if (tac == 1) { // upgrade 1;
        int valid_codes[] = {C1, C2, C3, LL1, LL2, LL3, RR1, RR2, RR3, ML1, ML2, MR1, MR2, L1, L2,
                             L3, R1, R2, R3,  M1,  M2,  M3,  M4,  FL1, FL2, FL3, FR1, FR2, FR3};
        for (auto &valid_code : valid_codes) {
            if (emp_flag[valid_code])
                continue;
            for (int j = 0; j < 3; j++) {
                // if (valid_code == C1 && j > 0)
                //     continue;
                int coins = game_info.coins[SIDE], towers = game_info.tower_num_of_player(SIDE);
                std::vector<Operation> op;
                action(valid_code, 2, game_info, coins, towers, j);
                valid = action_r1;
                type = action_r2;
                arg0 = action_r3;
                arg1 = action_r4;
                if (valid) {
                    op.emplace_back(type, arg0, arg1);
                    ops.emplace_back(op);
                }
            }
        }
    } else if (tac == 2) { // downgrade 1 and build 1
        int valid_codes[] = {C1, C2, C3, LL1, LL2, LL3, RR1, RR2, RR3, ML1, ML2, MR1, MR2, L1, L2,
                             L3, R1, R2, R3,  M1,  M2,  M3,  M4,  FL1, FL2, FL3, FR1, FR2, FR3};
        for (auto &valid_code : valid_codes) {
            if (emp_flag[valid_code])
                continue;
            int coins = game_info.coins[SIDE], towers = game_info.tower_num_of_player(SIDE);
            action(valid_code, 4, game_info, coins, towers);
            valid = action_r1;
            type = action_r2;
            arg0 = action_r3;
            arg1 = action_r4;
            if (valid) {
                for (auto &code2 : valid_codes) {
                    if (emp_flag[code2])
                        continue;
                    if (code2 == valid_code)
                        continue;
                    std::vector<Operation> op;
                    int new_coins = coins, new_towers = towers;
                    action(code2, 1, game_info, new_coins, new_towers);
                    new_valid = action_r1;
                    new_type = action_r2;
                    new_arg0 = action_r3;
                    new_arg1 = action_r4;
                    if (new_valid) {
                        op.emplace_back(type, arg0, arg1);
                        op.emplace_back(new_type, new_arg0, new_arg1);
                        ops.emplace_back(op);
                    }
                }
            }
        }
    } else if (tac == 3) { // destroy 1
        int valid_codes[] = {C1, C2, C3, LL1, LL2, LL3, RR1, RR2, RR3, ML1, ML2, MR1, MR2, L1, L2,
                             L3, R1, R2, R3,  M1,  M2,  M3,  M4,  FL1, FL2, FL3, FR1, FR2, FR3};
        for (auto &valid_code : valid_codes) {
            if (emp_flag[valid_code])
                continue;
            std::vector<Operation> op;
            int coins = game_info.coins[SIDE], towers = game_info.tower_num_of_player(SIDE);
            action(valid_code, 3, game_info, coins, towers);
            valid = action_r1;
            type = action_r2;
            arg0 = action_r3;
            arg1 = action_r4;
            if (valid) {
                op.emplace_back(type, arg0, arg1);
                ops.emplace_back(op);
            }
        }
    } else if (tac == 4) { // destroy 1 and upgrade 1
        int valid_codes[] = {C1, C2, C3, LL1, LL2, LL3, RR1, RR2, RR3, ML1, ML2, MR1, MR2, L1, L2,
                             L3, R1, R2, R3,  M1,  M2,  M3,  M4,  FL1, FL2, FL3, FR1, FR2, FR3};
        for (auto &valid_code : valid_codes) {
            if (emp_flag[valid_code])
                continue;
            int coins = game_info.coins[SIDE], towers = game_info.tower_num_of_player(SIDE);
            action(valid_code, 3, game_info, coins, towers);
            valid = action_r1;
            type = action_r2;
            arg0 = action_r3;
            arg1 = action_r4;
            if (valid) {
                for (auto &code2 : valid_codes) {
                    if (emp_flag[code2])
                        continue;
                    if (code2 == valid_code)
                        continue;
                    for (int j = 0; j < 3; j++) {
                        std::vector<Operation> op;
                        int new_coins = coins, new_towers = towers;
                        action(code2, 2, game_info, new_coins, new_towers, j);
                        new_valid = action_r1;
                        new_type = action_r2;
                        new_arg0 = action_r3;
                        new_arg1 = action_r4;
                        if (new_valid) {
                            op.emplace_back(type, arg0, arg1);
                            op.emplace_back(new_type, new_arg0, new_arg1);
                            ops.emplace_back(op);
                        }
                    }
                }
            }
        }
    } else if (tac == 5) { // downgrade 1
        int valid_codes[] = {C1, C2, C3, LL1, LL2, LL3, RR1, RR2, RR3, ML1, ML2, MR1, MR2, L1, L2,
                             L3, R1, R2, R3,  M1,  M2,  M3,  M4,  FL1, FL2, FL3, FR1, FR2, FR3};
        for (auto &valid_code : valid_codes) {
            if (emp_flag[valid_code])
                continue;
            int coins = game_info.coins[SIDE], towers = game_info.tower_num_of_player(SIDE);
            std::vector<Operation> op;
            action(valid_code, 4, game_info, coins, towers);
            valid = action_r1;
            type = action_r2;
            arg0 = action_r3;
            arg1 = action_r4;
            if (valid) {
                op.emplace_back(type, arg0, arg1);
                ops.emplace_back(op);
            }
        }
    } else if (tac == 6) { // destroy 1 and build 1
        int valid_codes[] = {C1, C2, C3, LL1, LL2, LL3, RR1, RR2, RR3, ML1, ML2, MR1, MR2, L1, L2,
                             L3, R1, R2, R3,  M1,  M2,  M3,  M4,  FL1, FL2, FL3, FR1, FR2, FR3};
        for (auto &valid_code : valid_codes) {
            if (emp_flag[valid_code])
                continue;
            int coins = game_info.coins[SIDE], towers = game_info.tower_num_of_player(SIDE);
            action(valid_code, 3, game_info, coins, towers);
            valid = action_r1;
            type = action_r2;
            arg0 = action_r3;
            arg1 = action_r4;
            if (valid) {
                for (auto &code2 : valid_codes) {
                    if (emp_flag[code2])
                        continue;
                    if (code2 == valid_code)
                        continue;
                    std::vector<Operation> op;
                    int new_coins = coins, new_towers = towers;
                    action(code2, 1, game_info, new_coins, new_towers, 0, valid_code);
                    new_valid = action_r1;
                    new_type = action_r2;
                    new_arg0 = action_r3;
                    new_arg1 = action_r4;
                    if (new_valid) {
                        op.emplace_back(type, arg0, arg1);
                        op.emplace_back(new_type, new_arg0, new_arg1);
                        ops.emplace_back(op);
                    }
                }
            }
        }
    } else if (tac == 7) { // downgrade 1 and upgrade 1
        int valid_codes[] = {C1, C2, C3, LL1, LL2, LL3, RR1, RR2, RR3, ML1, ML2, MR1, MR2, L1, L2,
                             L3, R1, R2, R3,  M1,  M2,  M3,  M4,  FL1, FL2, FL3, FR1, FR2, FR3};
        for (auto &valid_code : valid_codes) {
            if (emp_flag[valid_code])
                continue;
            int coins = game_info.coins[SIDE], towers = game_info.tower_num_of_player(SIDE);
            action(valid_code, 4, game_info, coins, towers);
            valid = action_r1;
            type = action_r2;
            arg0 = action_r3;
            arg1 = action_r4;
            if (valid) {
                for (auto &code2 : valid_codes) {
                    if (emp_flag[code2])
                        continue;
                    if (code2 == valid_code)
                        continue;
                    for (int j = 0; j < 3; j++) {
                        std::vector<Operation> op;
                        int new_coins = coins, new_towers = towers;
                        action(code2, 2, game_info, new_coins, new_towers, j);
                        new_valid = action_r1;
                        new_type = action_r2;
                        new_arg0 = action_r3;
                        new_arg1 = action_r4;
                        if (new_valid) {
                            op.emplace_back(type, arg0, arg1);
                            op.emplace_back(new_type, new_arg0, new_arg1);
                            ops.emplace_back(op);
                        }
                    }
                }
            }
        }
    }

    return ops;
}

int node_count = 0;
struct Node {
    Simulator s;
    int id;
    int parent;
    std::vector<int> children;
    Operation actions[3];
    float node_val;
    float max_val;
    short round;
    short loss;
    short max_expand;
    short expand_count;
    short fail_round;
    bool danger;
    bool safe;
    char action_num;
    char dis_vals[60];

    Node() {}

    Node(const Simulator &sim) : s(sim) {
        round = s.info.round;
        children.clear();
        loss = 0;
        action_num = 0;
        expand_count = 0;
        max_expand = 0;
        danger = false;
        fail_round = 0;
        safe = true;
    }
    float evaluate();
    void expand(bool is_root = false);
};
Node *nodes[MAX_NODE_COUNT];

inline void del() {
    for (int i = 0; i < node_count; i++) {
        delete nodes[i];
    }
}

int tower_positions[4][2];
int tower_position_count;
float Node::evaluate() {
    auto new_s = s;
    auto &info = new_s.info;
    if (info.round - current_round < 60)
        dis_vals[info.round - current_round] = nearest_ant_dis(info);
    int safe_val;
    if (current_round > 60) {
        safe_val = get_safe_val(info);
        safe = safe_val == 0;
    }
    short ruin_round = current_round + 60;
    bool fail_flag = false;
    if (info.bases[SIDE].hp <= now_hp - 1) {
        fail_flag = true;
        ruin_round = fail_round;
    }
    if (!fail_flag) {
        fail_round = current_round + 60;
        for (int i = info.round; i < current_round + 60; i++) {
            if (!new_s.fast_next_round(SIDE)) {
                break;
            }
            dis_vals[i - current_round] = nearest_ant_dis(info);
            // if (id == 1) {
            //     info.cerrdump();
            // }
            if (info.bases[SIDE].hp <= now_hp - 1) {
                fail_round = info.round;
                if (info.bases[SIDE].hp <= now_hp - 2)
                    ruin_round = fail_round;
                break;
            }
        }
    }
    if (info.bases[SIDE].hp > now_hp - 2) {
        for (int i = info.round; i < current_round + 60; i++) {
            if (!new_s.fast_next_round(SIDE)) {
                break;
            }
            dis_vals[i - current_round] = nearest_ant_dis(info);
            if (info.bases[SIDE].hp <= now_hp - 2) {
                ruin_round = info.round;
                break;
            }
        }
    }
    float ant_ratio = 0;
    switch (info.bases[!SIDE].ant_level) {
    case 0:
        ant_ratio = 3.0;
        break;
    case 1:
        ant_ratio = 5.0;
        break;
    case 2:
        ant_ratio = 7.0;
        break;
    }
    node_val = (info.bases[SIDE].hp - now_hp) + (fail_round - current_round) * 0.8 + (ruin_round - fail_round) * 0.1 -
               loss * 1.5 + 20;
    if (global_state == 0) {
        node_val += -(info.old_count[!SIDE] - base_old_count) * ant_ratio * 2 +
                    (info.die_count[!SIDE] - base_die_count) * ant_ratio * 1.5;
    }
    if (fail_round - current_round <= 16) {
        danger = true;
        node_val -= 500;
        if (ruin_round - fail_round <= 8) {
            node_val -= 300;
        }
    }
    if (!safe && !danger && global_state >= 0) {
        node_val += (-40 + safe_val / 5) * std::min((current_round - 60) / 30, 1);
    }

    int corrected_tower_num = info.tower_num_of_player(SIDE);
    node_val -= (std::pow(2, corrected_tower_num) - 1) * 15 * 0.2 * 0.75;
    tower_position_count = 0;
    bool distanced = false;
    for (int i = 0; i < info.towers.size(); i++) {
        auto &tower = info.towers[i];
        // if (tower.player == SIDE && !(tower.x == positions[SIDE][C1][0] && tower.y == positions[SIDE][C1][1])) {
        if (tower.player == SIDE) {
            if (tower.type > 0 && tower.type / 10 == 0) {
                node_val -= 60 * 0.2 * 0.75;
            } else if (tower.type / 10 > 0) {
                node_val -= 260 * 0.2 * 0.75;
            }
            tower_positions[tower_position_count][0] = tower.x;
            tower_positions[tower_position_count][1] = tower.y;
            tower_position_count++;
        }
    }
    for (int i = 0; i < tower_position_count - 1; i++) {
        for (int j = i + 1; j < tower_position_count; j++) {
            int dis =
                distance(tower_positions[i][0], tower_positions[i][1], tower_positions[j][0], tower_positions[j][1]);
            if (dis <= 3) {
                node_val -= 5;
            } else if (dis <= 6) {
                node_val -= 2;
            } else {
                distanced = true;
            }
        }
    }
    if (corrected_tower_num >= 3 && !distanced) {
        node_val -= 20;
    }
    for (int i = 0; i < tower_position_count; i++) {
        int base_dis = distance(tower_positions[i][0], tower_positions[i][1], info.bases[SIDE].x, info.bases[SIDE].y);
        node_val += base_dis * 0.4;
    }

    if (global_state >= 0) {
        bool close_flag = false;
        for (int i = 0; i < std::min(60, info.round - current_round - 4); i++) {
            if (dis_vals[i] <= 3) {
                close_flag = true;
            }
            switch (dis_vals[i]) {
            case 5:
                node_val -= 0.2;
                break;
            case 4:
                node_val -= 0.5;
            case 3:
            case 2:
            case 1:
                node_val -= 2;
                break;
            default:
                break;
            }
        }
        if (close_flag) {
            node_val -= 20;
        }
        int ant_count = 0;
        float mis_val = 0;
        for (auto &ant : info.ants) {
            if (ant.player == !SIDE) {
                mis_val += 32 - ant.age - distance(ant.x, ant.y, info.bases[SIDE].x, info.bases[SIDE].y) * 1.5;
                ant_count++;
            }
        }
        if (ant_count > 0 && current_round >= 20)
            node_val += mis_val / ant_count * 0.5;
    }

    max_val = node_val;
    return node_val;
}

void Node::expand(bool is_root) {
    if (s.info.round >= MAX_ROUND || s.info.bases[SIDE].hp <= 0 || s.info.bases[!SIDE].hp <= 0) {
        return;
    }
    if (!is_root) {
        if (s.info.round - current_round < 60)
            dis_vals[s.info.round - current_round] = nearest_ant_dis(s.info);
        if (!s.fast_next_round(SIDE)) {
            return;
        }
    }
    std::vector<std::vector<Operation>> ops;
    memset(emp_flag, 0, sizeof(emp_flag));
    for (auto &sw : s.info.super_weapons) {
        if (sw.player == !SIDE && sw.type == SuperWeaponType::EmpBlaster) {
            for (int i = 0; i < 34; i++) {
                if (distance(sw.x, sw.y, positions[SIDE][i][0], positions[SIDE][i][1]) <= 3)
                    emp_flag[i] = 1;
            }
            break;
        }
    }
    // std::cerr << "start find actions" << std::endl;

    for (int i = 0; i < 8; i++) {
        // if (action_num > 0 && expand_count < 5 && (i == 3 || i == 4))
        //     continue;
        if (action_num > 0 && (i == 3 || i == 5))
            continue;
        if (action_num == 1 && actions[0].type == OperationType::BuildTower && expand_count < 2 &&
            (i == 3 || i == 4 || i == 6))
            continue;
        if (action_num == 1 && actions[0].type == OperationType::UpgradeTower && expand_count < 2 && i == 2)
            continue;
        if (action_num == 2 && actions[1].type == OperationType::BuildTower && expand_count < 2 &&
            (i == 3 || i == 4 || i == 6))
            continue;
        if (s.info.tower_num_of_player(SIDE) >= 4 && (i == 0 || i == 2))
            continue;
        auto res = series_action(i, s.info);
        ops.insert(ops.end(), res.begin(), res.end());
    }
    if (is_root) {
        Node *empty = new Node(s);
        empty->id = node_count;
        empty->parent = id;
        empty->evaluate();
        nodes[node_count++] = empty;
        children.emplace_back(empty->id);
    }
    for (auto &op : ops) {
        if (node_count >= MAX_NODE_COUNT - 10)
            break;
        Node *child = new Node(s);
        auto &new_s = child->s;
        child->id = node_count;
        child->parent = id;
        child->loss = loss;
        child->action_num = op.size();
        child->fail_round = fail_round;
        child->node_val = child->max_val = -1e9;
        if (s.info.round > current_round) {
            memcpy(child->dis_vals, dis_vals, std::min(60, s.info.round - current_round));
        }
        auto &info = new_s.info;
        new_s.operations[0].clear();
        new_s.operations[1].clear();
        for (int i = 0; i < op.size(); i++) {
            // if (current_round > 170)
            //     std::cerr << op[i].type << " " << op[i].arg0 << " " << op[i].arg1 << " ";
            child->actions[i] = op[i];
            if (op[i].type == OperationType::DowngradeTower) {
                auto tower = get_tower(op[i].arg0, info);
                if (tower.type == TowerType::Basic) {
                    child->loss += info.build_tower_cost(info.tower_num_of_player(SIDE)) * 0.2;
                } else {
                    child->loss += info.upgrade_tower_cost(tower.type) * 0.2;
                }
            }
            new_s.add_operation_of_player(SIDE, op[i]);
        }
        new_s.apply_operations_of_player(SIDE);
        // auto start_time = clock();
        int child_val = child->evaluate();
        // total_eva_time += clock() - start_time;
        if (child_val > max_val) {
            max_val = child_val;
            max_expand = expand_count + 1;
        }
        nodes[node_count++] = child;
        children.emplace_back(child->id);
    }

    if (is_root)
        if (!s.fast_next_round(SIDE)) {
            return;
        }
    expand_count++;
}

inline bool select_expand() {
    auto &root = nodes[0];
    int target_id = -1;
    float val = -1e9;
    if (root->children.size() == 0)
        return false;
    for (auto &child_id : root->children) {
        auto &child = nodes[child_id];
        float value = -child->expand_count;
        if (child_id == 0) {
            value += reserved;
        }
        if (child->children.size() == 0)
            value += 1000;
        if (child->danger) {
            value += 20;
        }
        if (!child->safe) {
            value -= 20;
        }
        if (value > val) {
            val = value;
            target_id = child_id;
        }
    }
    // std::cerr << "expand " << target_id << std::endl;
    nodes[target_id]->expand();
    return true;
}

void supp_expand(int bias) {
    auto &root = nodes[0];
    if (root->children.size() == 0)
        return;
    for (auto &child_id : root->children) {
        auto &child = nodes[child_id];
        int fail_round = child->fail_round;
        if (fail_round - current_round <= 24) {
            int now_round = child->s.info.round;
            int target_round = std::min(MAX_ROUND - 1, fail_round - bias);
            if (now_round >= target_round) {
                continue;
            }
            for (int i = now_round; i < target_round - 1; i++) {
                if (!child->s.fast_next_round(SIDE)) {
                    break;
                }
            }
            child->expand();
        }
    }
    // std::cerr << "expand " << target_id << std::endl;
    // nodes[target_id]->expand();
}

std::vector<Operation> try_sell_all(int &coins, int &towers, int coin_need, const GameInfo &info) {
    std::vector<Operation> ops;
    int max_coins = coins;
    int valid_tower_num = 0;

    for (int i = 0; i < info.towers.size(); i++) {
        auto &tower = info.towers[i];
        if (tower.player == SIDE && !info.is_shielded_by_emp(tower)) {
            if (tower.type == TowerType::Basic) {
                coins += info.destroy_tower_income(towers);
                towers--;
            } else {
                coins += info.downgrade_tower_income(tower.type);
                if (tower.type / 10 == 0) {
                    max_coins += 48;
                } else {
                    max_coins += 48 + 160;
                }
            }
            ops.emplace_back(OperationType::DowngradeTower, tower.id, -1);
            valid_tower_num++;
        }
        if (coins >= coin_need) {
            return ops;
        }
    }
    max_coins +=
        (std::pow(2, info.tower_num_of_player(SIDE)) - std::pow(2, info.tower_num_of_player(SIDE) - valid_tower_num)) *
        12;
    if (max_coins >= coin_need) {
        return ops;
    }
    return {};
}

std::vector<Operation> try_sell(int &coins, int &towers, int coin_need, const GameInfo &info) {
    std::vector<int> tower_ids;
    for (int i = 0; i < info.towers.size(); i++) {
        auto &tower = info.towers[i];
        if (tower.player == SIDE && !info.is_shielded_by_emp(tower)) {
            tower_ids.emplace_back(tower.id);
        }
    }
    int valid_count = tower_ids.size();
    if (valid_count > 0) {
        Simulator s(info);
        int f_round = 48;
        for (int i = 1; i <= 48; i++) {
            if (!s.fast_next_round(SIDE)) {
                break;
            }
            if (s.info.bases[SIDE].hp < info.bases[SIDE].hp) {
                f_round = i;
                break;
            }
        }

        int *idx = new int[valid_count];
        for (int i = 0; i < valid_count; i++) {
            idx[i] = i;
        }
        int max_round = -1, max_coins;
        std::vector<Operation> best_ops;
        while (true) {
            std::vector<Operation> ops;
            Simulator new_s(info);
            auto &new_info = new_s.info;
            int new_coin = coins, new_towers = towers;
            bool valid = false;
            for (int i = 0; i < valid_count; i++) {
                int id = tower_ids[idx[i]];
                auto tower = get_tower(id, new_info);
                if (tower.type == TowerType::Basic) {
                    new_coin += new_info.destroy_tower_income(new_towers);
                    new_towers--;
                } else {
                    new_coin += new_info.downgrade_tower_income(tower.type);
                }
                ops.emplace_back(OperationType::DowngradeTower, id, -1);
                if (new_coin >= coin_need) {
                    valid = true;
                    break;
                }
            }
            if (valid) {
                for (auto &op : ops) {
                    new_s.add_operation_of_player(SIDE, op);
                }
                new_s.apply_operations_of_player(SIDE);
                int val = 48, base_hp = new_info.bases[SIDE].hp;
                for (int i = 1; i <= 48; i++) {
                    if (!new_s.fast_next_round(SIDE)) {
                        break;
                    }
                    if (new_info.bases[SIDE].hp < base_hp) {
                        val = i;
                        break;
                    }
                }
                if (val > max_round) {
                    max_round = val;
                    max_coins = new_coin;
                    best_ops = ops;
                }
            }
            if (!std::next_permutation(idx, idx + valid_count)) {
                break;
            }
        }
        delete[] idx;
        if (max_round < std::min(24, f_round)) {
            return {};
        }
        coins = max_coins;
        return best_ops;
    }

    return {};
}

inline std::vector<Operation> try_use_storm(const GameInfo &info, bool all_in) {
    std::vector<Operation> res;
    bool use = false;
    if (info.super_weapon_cd[SIDE][SuperWeaponType::LightningStorm] > 0)
        return {};
    if (info.coins[SIDE] >= info.use_super_weapon_cost(SuperWeaponType::LightningStorm)) {
        use = true;
    }
    int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
    if (!use) {
        if (all_in)
            res = try_sell_all(coins, towers, info.use_super_weapon_cost(SuperWeaponType::LightningStorm), info);
        else
            res = try_sell(coins, towers, info.use_super_weapon_cost(SuperWeaponType::LightningStorm), info);
        if (res.size() > 0 && coins >= info.use_super_weapon_cost(SuperWeaponType::LightningStorm))
            use = true;
    }
    if (!use)
        return {};
    int max_x, max_y, max_val = -1;
    for (int i = 0; i <= 18; i++) {
        for (int j = 0; j <= 18; j++) {
            if (!is_valid_pos(i, j))
                continue;
            Simulator new_s(info);
            for (int k = 0; k < res.size(); k++)
                new_s.add_operation_of_player(SIDE, res[k]);
            new_s.add_operation_of_player(SIDE, Operation(OperationType::UseLightningStorm, i, j));
            new_s.apply_operations_of_player(SIDE);
            int fround = 32;
            for (int k = 0; k < 32; k++) {
                if (!new_s.fast_next_round(SIDE))
                    break;
                if (new_s.info.bases[SIDE].hp < info.bases[SIDE].hp) {
                    fround = k;
                    break;
                }
            }
            if (fround < 24) {
                continue;
            }
            int value = new_s.info.die_count[!SIDE] + fround;
            if (value > max_val) {
                max_val = value;
                max_x = i;
                max_y = j;
            }
        }
    }
    if (max_val == -1)
        return {};
    res.emplace_back(OperationType::UseLightningStorm, max_x, max_y);

    return res;
}

inline std::vector<Operation> try_end_storm(const GameInfo &info) {
    std::vector<Operation> res;
    bool use = false;
    if (info.super_weapon_cd[SIDE][SuperWeaponType::LightningStorm] > 0)
        return {};
    if (info.coins[SIDE] >= info.use_super_weapon_cost(SuperWeaponType::LightningStorm)) {
        use = true;
    }
    int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
    if (!use) {
        res = try_sell_all(coins, towers, info.use_super_weapon_cost(SuperWeaponType::LightningStorm), info);
        if (res.size() > 0 && coins >= info.use_super_weapon_cost(SuperWeaponType::LightningStorm))
            use = true;
    }
    if (!use)
        return {};
    res.emplace_back(OperationType::UseLightningStorm, positions[SIDE][STORM][0], positions[SIDE][STORM][1]);
    return res;
}

std::vector<Operation> try_use_superweapon(const GameInfo &info) {
    // if (current_round - last_superweapon_round < 15 && (last_superweapon_type == SuperWeaponType::EmpBlaster))
    //     return {};
    // else if (current_round - last_superweapon_round < 10)
    //     return {};
    // else if (nearest_to_base_dis(info) > 6)
    //     return {};
    std::vector<Operation> ops;
    int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
    bool can_emp = false, can_deflect = false, can_eva = false, enemy_storm = false;
    if (info.super_weapon_cd[SIDE][SuperWeaponType::EmpBlaster] == 0 &&
        coins >= info.use_super_weapon_cost(SuperWeaponType::EmpBlaster))
        can_emp = true;
    if (info.super_weapon_cd[SIDE][SuperWeaponType::Deflector] == 0 &&
        coins >= info.use_super_weapon_cost(SuperWeaponType::Deflector))
        can_deflect = true;
    if (info.super_weapon_cd[SIDE][SuperWeaponType::EmergencyEvasion] == 0 &&
        coins >= info.use_super_weapon_cost(SuperWeaponType::EmergencyEvasion))
        can_eva = true;
    if (info.super_weapon_cd[!SIDE][SuperWeaponType::LightningStorm] == 0 &&
        info.coins[!SIDE] >= info.use_super_weapon_cost(SuperWeaponType::LightningStorm))
        enemy_storm = true;
    if (!can_emp && info.super_weapon_cd[SIDE][SuperWeaponType::EmpBlaster] == 0) {
        ops = try_sell(coins, towers, 150, info);
    }
    if (ops.size() == 0 && ((info.super_weapon_cd[SIDE][SuperWeaponType::Deflector] == 0 && !can_deflect) ||
                            (info.super_weapon_cd[SIDE][SuperWeaponType::EmergencyEvasion] == 0 && !can_eva))) {
        ops = try_sell(coins, towers, 100, info);
    }
    if (info.super_weapon_cd[SIDE][SuperWeaponType::EmpBlaster] == 0 &&
        coins >= info.use_super_weapon_cost(SuperWeaponType::EmpBlaster))
        can_emp = true;
    if (info.super_weapon_cd[SIDE][SuperWeaponType::Deflector] == 0 &&
        coins >= info.use_super_weapon_cost(SuperWeaponType::Deflector))
        can_deflect = true;
    if (info.super_weapon_cd[SIDE][SuperWeaponType::EmergencyEvasion] == 0 &&
        coins >= info.use_super_weapon_cost(SuperWeaponType::EmergencyEvasion))
        can_eva = true;

    Simulator s(info);
    for (int i = 0; i < 24; i++) {
        if (!s.fast_next_round(!SIDE))
            break;
    }
    int base_enemy_hp = s.info.bases[!SIDE].hp;
    int base_die_count = s.info.die_count[SIDE];
    std::vector<std::tuple<int, int, float>> storm_results;
    if (can_emp) {
        std::vector<std::tuple<int, int, float>> results;
        for (int i = 0; i <= 18; i++) {
            for (int j = 0; j <= 18; j++) {
                if (!is_valid_pos(i, j))
                    continue;
                float value = 0;
                for (auto &tower : info.towers) {
                    if (tower.player == !SIDE && distance(tower.x, tower.y, i, j) <= 3) {
                        if (tower.type == TowerType::Basic) {
                            value += 50;
                        } else if (tower.type / 10 < 0) {
                            value += 60;
                        } else {
                            value += 80;
                        }
                    }
                }
                if (value < 100)
                    continue;
                Simulator new_s(info);
                for (int k = 0; k < ops.size(); k++)
                    new_s.add_operation_of_player(SIDE, ops[k]);
                new_s.add_operation_of_player(SIDE, Operation(OperationType::UseEmpBlaster, i, j));
                new_s.apply_operations_of_player(SIDE);
                for (int k = 0; k < 24; k++) {
                    if (!new_s.fast_next_round(!SIDE))
                        break;
                }
                if (current_round > 495) {
                    if (new_s.info.bases[!SIDE].hp >= base_enemy_hp)
                        continue;
                } else if (current_round > 460) {
                    if (new_s.info.bases[!SIDE].hp >= base_enemy_hp - 2)
                        continue;
                } else if (new_s.info.bases[!SIDE].hp >= base_enemy_hp - 4)
                    continue;
                value += 100 * (base_enemy_hp - new_s.info.bases[!SIDE].hp);
                for (int k = 1; k < 34; k++) {
                    if (distance(positions[!SIDE][k][0], positions[!SIDE][k][1], i, j) <= 3) {
                        value += 3 - distance(positions[!SIDE][k][0], positions[!SIDE][k][1], positions[!SIDE][BASE][0],
                                              positions[!SIDE][BASE][1]) *
                                         0.01;
                    }
                }
                results.emplace_back(i, j, value);
            }
        }
        if (results.size() > 0 && !enemy_storm) {
            float max_val = -1e9;
            int max_x = -1, max_y = -1;
            for (int i = 0; i < results.size(); i++) {
                if (std::get<2>(results[i]) > max_val) {
                    max_val = std::get<2>(results[i]);
                    max_x = std::get<0>(results[i]);
                    max_y = std::get<1>(results[i]);
                }
            }
            ops.emplace_back(OperationType::UseEmpBlaster, max_x, max_y);
            last_superweapon_round = current_round;
            last_superweapon_type = SuperWeaponType::EmpBlaster;
            return ops;
        } else {
            storm_results = results;
        }
    }
    if (can_deflect || can_eva) {
        std::vector<std::tuple<int, int, float, bool>> results;
        if (can_eva) {
            for (int i = 0; i <= 18; i++) {
                for (int j = 0; j <= 18; j++) {
                    if (!is_valid_pos(i, j))
                        continue;
                    float value = 0;
                    int eva_num = 0;
                    int min_dis = 100;
                    for (auto &ant : info.ants) {
                        if (ant.player == SIDE && distance(ant.x, ant.y, i, j) <= 3 && ant.is_alive()) {
                            value += ant.level + 1;
                            eva_num++;
                            int dis = distance(ant.x, ant.y, positions[!SIDE][BASE][0], positions[!SIDE][BASE][1]);
                            if (dis < min_dis)
                                min_dis = dis;
                        }
                    }
                    if (current_round <= 506 && min_dis > 5)
                        continue;
                    if (eva_num < 3 || (current_round > 460 && eva_num < 2))
                        continue;
                    Simulator new_s(info);
                    for (int k = 0; k < ops.size(); k++)
                        new_s.add_operation_of_player(SIDE, ops[k]);
                    new_s.add_operation_of_player(SIDE, Operation(OperationType::UseEmergencyEvasion, i, j));
                    new_s.apply_operations_of_player(SIDE);
                    for (int k = 0; k < 24; k++) {
                        if (!new_s.fast_next_round(!SIDE))
                            break;
                    }
                    if (current_round > 506) {
                        if (new_s.info.bases[!SIDE].hp >= base_enemy_hp &&
                            new_s.info.die_count[SIDE] >= base_die_count - 2)
                            continue;
                    } else if (current_round > 460) {
                        if (new_s.info.bases[!SIDE].hp >= base_enemy_hp - 2)
                            continue;
                    } else if (new_s.info.bases[!SIDE].hp >= base_enemy_hp - 3)
                        continue;
                    value += 100 * (base_enemy_hp - new_s.info.bases[!SIDE].hp);
                    results.emplace_back(i, j, value, 1);
                }
            }
        }
        if (can_deflect && results.size() == 0) {
            for (int i = 0; i <= 18; i++) {
                for (int j = 0; j <= 18; j++) {
                    if (!is_valid_pos(i, j))
                        continue;
                    if (distance(i, j, positions[!SIDE][BASE][0], positions[!SIDE][BASE][1]) > 4)
                        continue;
                    float value = 0;
                    Simulator new_s(info);
                    for (int k = 0; k < ops.size(); k++)
                        new_s.add_operation_of_player(SIDE, ops[k]);
                    new_s.add_operation_of_player(SIDE, Operation(OperationType::UseDeflector, i, j));
                    new_s.apply_operations_of_player(SIDE);
                    for (int k = 0; k < 24; k++) {
                        if (!new_s.fast_next_round(!SIDE))
                            break;
                    }
                    if ((current_round > 460 && new_s.info.bases[!SIDE].hp >= base_enemy_hp - 2) ||
                        new_s.info.bases[!SIDE].hp >= base_enemy_hp - 3)
                        continue;
                    value += 100 * (base_enemy_hp - new_s.info.bases[!SIDE].hp);
                    value -= distance(i, j, positions[!SIDE][STORM][0], positions[!SIDE][STORM][1]);
                    results.emplace_back(i, j, value, 0);
                }
            }
        }
        if (results.size() > 0) {
            float max_val = -1e9;
            int max_x = -1, max_y = -1;
            bool max_type = 0;
            for (int i = 0; i < results.size(); i++) {
                if (std::get<2>(results[i]) > max_val) {
                    max_val = std::get<2>(results[i]);
                    max_x = std::get<0>(results[i]);
                    max_y = std::get<1>(results[i]);
                    max_type = std::get<3>(results[i]);
                }
            }
            if (max_type) {
                ops.emplace_back(OperationType::UseEmergencyEvasion, max_x, max_y);
                last_superweapon_round = current_round;
                last_superweapon_type = SuperWeaponType::EmergencyEvasion;
            } else {
                ops.emplace_back(OperationType::UseDeflector, max_x, max_y);
                last_superweapon_round = current_round;
                last_superweapon_type = SuperWeaponType::Deflector;
            }
            return ops;
        }
    }
    if (can_emp && storm_results.size() > 0) {
        float max_val = -1e9;
        int max_x = -1, max_y = -1;
        for (int i = 0; i < storm_results.size(); i++) {
            if (std::get<2>(storm_results[i]) > max_val) {
                max_val = std::get<2>(storm_results[i]);
                max_x = std::get<0>(storm_results[i]);
                max_y = std::get<1>(storm_results[i]);
            }
        }
        ops.emplace_back(OperationType::UseEmpBlaster, max_x, max_y);
        last_superweapon_round = current_round;
        last_superweapon_type = SuperWeaponType::EmpBlaster;
        return ops;
    }
    return {};
}

std::vector<Operation> try_emp(const GameInfo &info) {
    if (nearest_to_base_dis(info) > 5)
        return {};
    int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
    if (info.super_weapon_cd[SIDE][SuperWeaponType::EmpBlaster] > 0)
        return {};
    int enemy_coins = info.coins[!SIDE], enemy_towers = info.tower_num_of_player(!SIDE);
    // if (enemy_coins >= info.use_super_weapon_cost(SuperWeaponType::LightningStorm) &&
    //     info.super_weapon_cd[!SIDE][SuperWeaponType::LightningStorm] == 0)
    //     return {};
    std::vector<Operation> ops;
    if (coins - enemy_coins < 100 || coins < 150) {
        ops = try_sell(coins, towers, std::max(enemy_coins + 100, 150), info);
        if (ops.size() == 0) {
            return {};
        }
    }
    Simulator my_s(info);
    for (int i = 0; i < 24; i++) {
        if (!my_s.fast_next_round(SIDE))
            break;
        if (my_s.info.bases[SIDE].hp < info.bases[SIDE].hp)
            return {};
    }

    Simulator s(info);
    for (int i = 0; i < 24; i++) {
        if (!s.fast_next_round(!SIDE))
            break;
    }
    int base_enemy_hp = s.info.bases[!SIDE].hp;

    std::vector<std::tuple<int, int, float>> results;
    for (int i = 0; i <= 18; i++) {
        for (int j = 0; j <= 18; j++) {
            if (MAP_PROPERTY[i][j] < 0)
                continue;
            float value = 0;
            for (auto &tower : info.towers) {
                if (tower.player == !SIDE && distance(tower.x, tower.y, i, j) <= 3) {
                    if (tower.type == TowerType::Basic) {
                        value += 50;
                    } else if (tower.type / 10 < 0) {
                        value += 60;
                    } else {
                        value += 80;
                    }
                }
            }
            if (value < 100)
                continue;
            Simulator new_s(info);
            for (int k = 0; k < ops.size(); k++)
                new_s.add_operation_of_player(SIDE, ops[k]);
            new_s.add_operation_of_player(SIDE, Operation(OperationType::UseEmpBlaster, i, j));
            new_s.apply_operations_of_player(SIDE);
            for (int k = 0; k < 24; k++) {
                if (!new_s.fast_next_round(!SIDE))
                    break;
            }
            if (new_s.info.bases[!SIDE].hp >= base_enemy_hp - 4)
                continue;
            value += 100 * (base_enemy_hp - new_s.info.bases[!SIDE].hp);
            for (int k = 1; k < 34; k++) {
                if (distance(positions[!SIDE][k][0], positions[!SIDE][k][1], i, j) <= 3) {
                    value += 3 - distance(positions[!SIDE][k][0], positions[!SIDE][k][1], positions[!SIDE][BASE][0],
                                          positions[!SIDE][BASE][1]) *
                                     0.01;
                }
            }

            results.emplace_back(i, j, value);
        }
    }
    if (results.size() > 0) {
        float max_val = -1e9;
        int max_x = -1, max_y = -1;
        for (int i = 0; i < results.size(); i++) {
            if (std::get<2>(results[i]) > max_val) {
                max_val = std::get<2>(results[i]);
                max_x = std::get<0>(results[i]);
                max_y = std::get<1>(results[i]);
            }
        }
        ops.emplace_back(OperationType::UseEmpBlaster, max_x, max_y);
        last_superweapon_round = current_round;
        last_superweapon_type = SuperWeaponType::EmpBlaster;
        return ops;
    }
    return {};
}

std::vector<Operation> try_attack(const GameInfo &info) {
    std::cerr << "try att" << std::endl;
    std::vector<Operation> ops;
    if (global_state == 0) {
        // if (current_round <= 450 && info.bases[SIDE].ant_level == 0) {
        //     int coin_need = 200;
        //     int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
        //     if (coins >= coin_need) {
        //         ops.emplace_back(OperationType::UpgradeGeneratedAnt, -1, -1);
        //         return ops;
        //     }
        // } else {
        //     if (current_round <= 440 && info.bases[SIDE].ant_level == 1) {
        //         int coin_need = 250;
        //         int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
        //         if (coins >= coin_need) {
        //             ops.emplace_back(OperationType::UpgradeGeneratedAnt, -1, -1);
        //             return ops;
        //         }
        //     }
        return try_use_superweapon(info);
        // }
    } else {
        if (current_round <= 460) {
            if (info.bases[SIDE].ant_level == 0) {
                int coin_need = 200;
                int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
                if (coins >= coin_need) {
                    ops.emplace_back(OperationType::UpgradeGeneratedAnt, -1, -1);
                    return ops;
                }
            } else if (info.bases[SIDE].ant_level == 1) {
                int coin_need = 250;
                int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
                if (coins >= coin_need) {
                    ops.emplace_back(OperationType::UpgradeGeneratedAnt, -1, -1);
                    return ops;
                }
                ops = try_sell(coins, towers, coin_need, info);
                if (ops.size() > 0) {
                    ops.emplace_back(OperationType::UpgradeGeneratedAnt, -1, -1);
                    return ops;
                }
            } else if (info.bases[SIDE].gen_speed_level == 0) {
                int coin_need = 200;
                int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
                if (coins >= coin_need) {
                    ops.emplace_back(OperationType::UpgradeGenerationSpeed, -1, -1);
                    return ops;
                }
                ops = try_sell_all(coins, towers, coin_need, info);
                if (ops.size() > 0) {
                    ops.emplace_back(OperationType::UpgradeGenerationSpeed, -1, -1);
                    return ops;
                }
            }
            return try_use_superweapon(info);
        } else {
            if (current_round <= 470 && info.bases[SIDE].ant_level == 0) {
                int coin_need = 200;
                int coins = info.coins[SIDE], towers = info.tower_num_of_player(SIDE);
                if (coins >= coin_need) {
                    ops.emplace_back(OperationType::UpgradeGeneratedAnt, -1, -1);
                    return ops;
                }
            } else {
                return try_use_superweapon(info);
            }
        }
    }

    return {};
}

std::vector<Operation> advanced_ai(int player_id, const GameInfo &game_info) {
    // for (auto &ant : game_info.ants) {
    //     if (ant.evasion > 0) {
    //         std::cerr << "eva:" << ant.id << " " << (int)(ant.evasion) << std::endl;
    //     }
    // }
    current_round = game_info.round;
    total_eva_time = 0;
    base_old_count = game_info.old_count[!SIDE];
    base_die_count = game_info.die_count[!SIDE];
    std::cerr << "round:" << current_round << " " << game_info.bases[0].hp << ":" << game_info.bases[1].hp << " "
              << game_info.die_count[0] << ":" << game_info.die_count[1] << " " << game_info.coins[0] << ":"
              << game_info.coins[1] << std::endl;
    std::vector<Operation> ops;
    if (current_round == 0) {
        SIDE = player_id;
        // ops.emplace_back(OperationType::BuildTower, positions[SIDE][C1][0], positions[SIDE][C1][1]);
        // return ops;
    }
    now_hp = game_info.bases[SIDE].hp;

    global_state = 0;
    if (game_info.bases[SIDE].hp > game_info.bases[!SIDE].hp) {
        global_state = 1;
        attack_flag = false;
    } else if (game_info.bases[SIDE].hp < game_info.bases[!SIDE].hp) {
        global_state = -1;
    }

    bool attack = global_state == -1;
    float kill1 = game_info.die_count[!SIDE], kill2 = game_info.die_count[SIDE];
    for (auto &ant : game_info.ants) {
        if (ant.player == !SIDE && ant.is_alive())
            kill1 += 1 * std::min(1.0, (512 - current_round) / 20.0);
        else if (ant.player == SIDE && ant.is_alive())
            kill2 += 1 * std::min(1.0, (512 - current_round) / 20.0);
    }
    if (!attack && global_state == 0) {
        if (kill1 - kill2 >= 4) {
            attack_flag = false;
        } else if (kill1 - kill2 <= -3 - std::max((450 - current_round) / 50, 0)) {
            attack = true;
        } else if (attack_flag) {
            attack = true;
        } else if (current_round >= 450 && kill1 - kill2 <= 1) {
            attack = true;
        }
    }
    int enemy_emp = -1;
    for (auto &sw : game_info.super_weapons) {
        if (sw.player == !SIDE && sw.type == SuperWeaponType::EmpBlaster) {
            enemy_emp = sw.left_time;
            break;
        }
    }

    if (global_state <= 0 && !reserved) {
        ops = try_emp(game_info);
        if (ops.size() > 0)
            return ops;
    }
    if (attack && !reserved) {
        attack_flag = true;
        ops = try_attack(game_info);
        if (ops.size() > 0)
            return ops;
    }

    if (global_state == 1 && current_round >= 488) {
        ops = try_end_storm(game_info);
        if (ops.size() > 0)
            return ops;
    }
    if (global_state == 0 && current_round >= 510) {
        ops = try_use_storm(game_info, true);
        if (ops.size() > 0)
            return ops;
    }

    clock_t start_t = clock();
    auto modified_info = game_info;
    modified_info.bases[!SIDE].hp = 1000;

    Simulator s(modified_info);
    node_count = 0;
    Node *root = new Node(s);
    root->id = 0;
    root->parent = -1;
    // std::cerr << "start evaluate" << std::endl;
    root->evaluate();
    nodes[node_count++] = root;
    // std::cerr << "start expand" << std::endl;
    nodes[0]->expand(true);
    while (true) {
        if (clock() - start_t >= TIME1 * CLOCKS_PER_SEC || node_count >= MAX_NODE_COUNT - 10) {
            break;
        }
        if (!select_expand()) {
            break;
        }
    }
    // for (int i = 8; i > 1; i--) {
    //     if (clock() - start_t >= TIME2 * CLOCKS_PER_SEC || node_count >= MAX_NODE_COUNT - 10) {
    //         break;
    //     }
    //     supp_expand(i);
    // }
    // std::cerr << "total_eva_time:" << total_eva_time << std::endl;
    std::cerr << " node_count: " << node_count << std::endl;
    int max_id = -1;
    float max_val = -1e9;
    for (auto &child_id : root->children) {
        auto &child = nodes[child_id];
        std::cerr << child_id << " v:" << child->max_val << " " << child->max_expand << " " << child->fail_round
                  << std::endl;
        if (child->max_val > max_val) {
            max_val = child->max_val;
            max_id = child_id;
        }
    }

    if (node_count > 1 && max_id > 1 && max_val - nodes[1]->max_val < 2) {
        max_id = 1;
        max_val = nodes[1]->max_val;
    }
    std::cerr << "max_id: " << max_id << " max_val: " << max_val << std::endl;
    if (global_state >= 0 &&
            ((enemy_emp > 0 && nodes[max_id]->fail_round - current_round < std::min(8, enemy_emp) && max_val < -400) ||
             (max_val < -700 && nodes[max_id]->fail_round - current_round <= 2)) ||
        (global_state == 0 && game_info.die_count[!SIDE] - game_info.die_count[SIDE] >= 8 &&
         nodes[max_id]->fail_round - current_round <= 1)) {
        if (current_round < 480)
            ops = try_use_storm(game_info, false);
        else
            ops = try_use_storm(game_info, true);
        std::cerr << "emergency use storm" << std::endl;
        if (ops.size() > 0) {
            del();
            return ops;
        }
    }
    if (max_id > 0) {
        for (int i = 0; i < nodes[max_id]->action_num; i++) {
            ops.emplace_back(nodes[max_id]->actions[i]);
            std::cerr << "action: " << nodes[max_id]->actions[i].type << " " << (int)(nodes[max_id]->actions[i].arg0)
                      << " " << (int)(nodes[max_id]->actions[i].arg1) << std::endl;
        }
        reserved = nodes[max_id]->max_expand;
    }
    del();
    return ops;
}

int main() {
    // Run the game with the simple AI
    std::ios::sync_with_stdio(false);
    run_with_ai(advanced_ai);

    // Run the game with the advanced AI
    // run_with_ai(advanced_ai);

    return 0;
}