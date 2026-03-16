#include "map.h"
#include <cmath>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <stdlib.h>
#include <time.h>
#include <vector>

// move
const double Q0 = 0;
// arrive
const double Q1 = 10;
// hp < 0 
const double Q2 = -5;
// too old
const double Q3 = -3;

// y 为奇偶时方向不同
const int d[2][6][2] = {{{0, 1}, {-1, 0}, {0, -1}, {1, -1}, {1, 0}, {1, 1}},
                        {{-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, 0}, {0, 1}}};

double eta(int _x, int _y, int x, int y, Pos des) {
    if (distance(Pos(_x, _y), des) < distance(Pos(x, y), des)) {
        return 1.25;
    } else if (distance(Pos(_x, _y), des) == distance(Pos(x, y), des)) {
        return 1.0;
    } else {
        return 0.75;
    }
}

// void Map::update_move_pheromone(Ant *ant) {
//     int L_k = std::max(ant->get_path_len(), 1);
//     int mov = -1;
//     if ((!ant->path.empty()) && (ant->get_status() != Ant::Status::Frozen))
//         mov = *(ant->path.end() - 1);
//     int player = ant->get_player();
//     int x = ant->get_x();
//     int y = ant->get_y();
//     // 移动信息素变化
//     if (mov != -1) {
//         map[x][y].pheromone[player][mov] += (double)Q0 / L_k;
//         x = x + d[y % 2][mov][0];
//         y = y + d[y % 2][mov][1];
//         map[x][y].pheromone[player][(mov + 3) % 6] += (double)Q0 / L_k;
//     }
//     ant->move(mov);
// }

// update pheromone
void Map::update_pheromone(Ant *ant) {
    int player = ant->get_player();
    int x = ant->get_x();
    int y = ant->get_y();
    // 如果到达大本营, 更新全局信息素
    // 如果hp <= 0 或已经走了很长距离, 判定死亡,更新全局信息素并返回
    double Q = 0.0;
    if (ant->get_status() == Ant::Status::Success) {
            Q = Q1;
    } else if (ant->get_status() == Ant::Status::Fail) {
            Q = Q2;
    } else if (ant->get_status() == Ant::Status::TooOld){
            Q = Q3;
    } else {
        return;
    }


    auto iter = ant->path.end() - 1;
    // if (ant->get_status() == Ant::Status::TooOld) {
    //     int mov = *iter;
    //     if (mov != -1) {
    //         x += d[y % 2][(mov + 3) % 6][0];
    //         y += d[y % 2][(mov + 3) % 6][1];
    //     }
    //     iter--;
    // }

    std::vector<std::pair<int, int>> visited_p = {std::make_pair(x, y)};
    map[x][y].pheromone[player] = std::max(0.0, map[x][y].pheromone[player] + (double)Q);
    for (; iter >= ant->path.begin();
            iter--) {
        int mov = *iter;
        if (mov == -1)
            continue;
        x += d[y % 2][(mov + 3) % 6][0];
        y += d[y % 2][(mov + 3) % 6][1];
        if (std::find(visited_p.begin(), visited_p.end(), std::make_pair(x, y)) != visited_p.end())
            continue;
        map[x][y].pheromone[player] = std::max(0.0, map[x][y].pheromone[player] + (double)Q);
        visited_p.push_back(std::make_pair(x, y));        
    }
}

// get the next step of ant
int Map::get_move(Ant *ant, Pos des) {
    // 保证蚂蚁健康，可以移动
    int x = ant->get_x();
    int y = ant->get_y();
    int player = ant->get_player();

    double p[6];
    for (int i = 0; i < 6; i++) {
        int _x = x + d[y % 2][i][0];
        int _y = y + d[y % 2][i][1];
        if (!ant->path.empty() && ant->path.back() == ((i + 3) % 6)) {
            p[i] = -1.0; // 不能走回头路,设为-1
        } else if (!is_valid(_x, _y)) {
            p[i] = -1.0; // 判断此边是否可走
        } else {
            p[i] = map[_x][_y].pheromone[player];
        }
        double m = eta(_x, _y, x, y, des);
        p[i] *= m;
    }
    int mov = -1;
    double max_p = - 0.1;
    for (int i = 0; i < 6; i++) {
        if (p[i] > max_p) {
            max_p = p[i];
            mov = i;
        }
    }
    return mov;
}


// global reduction
void Map::next_round() {
    for (int i = 0; i < MAP_SIZE; i++)
        for (int j = 0; j < MAP_SIZE; j++)
            for (int k = 0; k < 2; k++) {
                    map[i][j].pheromone[k] = LAMBDA * map[i][j].pheromone[k] + (1.0 - LAMBDA) * TAU_BASE;
                }

}

