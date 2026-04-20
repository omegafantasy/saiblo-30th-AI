#pragma once

#include "antgame_sdk/position_slots.hpp"

namespace antgame::sdk {

struct RandomSearchTuning {
    int defense_rollouts = 100;
    int defense_plan_initial_rollouts = 20;
    int defense_plan_rollout_step = 20;
    int defense_horizon = 8;
    int important_ant_limit = 3;
    int move_option_limit = 3;
    int lightning_center_limit = 10;
    int lightning_rollouts_per_center = 20;
    int lightning_horizon = 10;
    int offense_rollouts = 0;
    int offense_horizon = 8;
    double defense_plan_keep_fraction = 0.5;
    bool ignore_periodic_random_move = true;

    double hold_bias = 50.0;
    double downgrade_penalty = 20.0;
    double downgrade_refund_penalty_scale = 0.1;
    double lightning_penalty = 0.0;
    double enemy_superweapon_window_lightning_bonus = 200.0;

    double base_hp_weight = 200.0;
    double tower_value_weight = 10.0;
    double ant_threat_weight = 1.0;
    double money_weight = 10.0;
    double heavy_tower_bonus = 30.0;
    double bewitch_tower_bonus = 100.0;

    double base_ant_threat_cap = 200.0;
    double combat_tower_threat_coin_ratio = 0.3;
    double randomized_threat_scale = 0.6;
    double bewitched_threat_scale = 0.25;
    double control_free_threat_scale = 1.0;

    double c1_bonus = 50.0;
    double c2_bonus = 50.0;
    double c3_bonus = 30.0;
    double l1_bonus = 30.0;
    double l2_bonus = 20.0;
    double l3_bonus = 15.0;
    double r1_bonus = 30.0;
    double r2_bonus = 20.0;
    double r3_bonus = 15.0;
};

inline constexpr RandomSearchTuning kRandomSearchTuning{};

inline constexpr const RandomSearchTuning &config() {
    return kRandomSearchTuning;
}

inline constexpr double random_search_position_bonus(int code) {
    switch (code) {
    case C1:
        return kRandomSearchTuning.c1_bonus;
    case C2:
        return kRandomSearchTuning.c2_bonus;
    case C3:
        return kRandomSearchTuning.c3_bonus;
    case L1:
        return kRandomSearchTuning.l1_bonus;
    case L2:
        return kRandomSearchTuning.l2_bonus;
    case L3:
        return kRandomSearchTuning.l3_bonus;
    case R1:
        return kRandomSearchTuning.r1_bonus;
    case R2:
        return kRandomSearchTuning.r2_bonus;
    case R3:
        return kRandomSearchTuning.r3_bonus;
    default:
        return 0.0;
    }
}

} // namespace antgame::sdk
