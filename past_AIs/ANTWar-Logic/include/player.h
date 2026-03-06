#ifndef __PLAYER_H__
#define __PLAYER_H__
#include "ant.h"
#include "coin.h"
class Player {
  public:
    Player() : opponent_killed_ant(0), super_weapons_usage(0), AI_total_time(0){};
    ~Player(){};
    int ant_target_x, ant_target_y; // 蚂蚁目标点
    int opponent_killed_ant;
    int super_weapons_usage;
    int AI_total_time;
    Coin coin;
    Ant *first_attack_ant = nullptr;
};

#endif