#pragma once

#include "antgame_ai/lure_strategy_v3_lure_plans.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline double enemy_tower_lightning_damage_score(const PublicState &state, int player, int x, int y) {
    constexpr int kLightningTowerDamage = 3;
    const int enemy = 1 - player;
    const int strikes = lightning_tower_strikes_within_horizon(v3_lure_config().lightning_horizon);
    if (strikes <= 0) {
        return 0.0;
    }

    int enemy_tower_count = 0;
    for (const auto &tower : state.towers) {
        if (tower.player == enemy && tower.hp > 0) {
            ++enemy_tower_count;
        }
    }
    if (enemy_tower_count <= 0) {
        return 0.0;
    }

    const int total_damage = strikes * kLightningTowerDamage;
    double score = 0.0;
    for (const auto &tower : state.towers) {
        if (tower.player != enemy || tower.hp <= 0) {
            continue;
        }
        if (hex_distance(x, y, tower.x, tower.y) > weapon_stats(SuperWeaponType::LightningStorm).attack_range) {
            continue;
        }
        const double before = tower_salvage_value(state, tower, enemy_tower_count);
        Tower damaged = tower;
        damaged.hp = std::max(0, tower.hp - total_damage);
        const double after = tower_salvage_value(state, damaged, enemy_tower_count);
        score += (before - after) * v3_lure_config().tower_value_weight * v3_lure_config().lightning_tower_value_ratio;
    }
    return score;
}

inline std::vector<SinglePlan> generate_lightning_center_candidates(
    const PublicState &state,
    const rs::DefenseSimulator *simulator,
    int player) {
    std::vector<SinglePlan> plans;
    static_cast<void>(simulator);
    if (state.weapon_cooldowns[player][static_cast<int>(SuperWeaponType::LightningStorm)] > 0) {
        return plans;
    }

    for (int x = 0; x < kMapSize; ++x) {
        for (int y = 0; y < kMapSize; ++y) {
            if (!is_lightning_center_candidate(x, y)) {
                continue;
            }
            const Operation operation(OperationType::UseLightningStorm, x, y);
            if (legalize_operations(state, player, {operation}).empty()) {
                continue;
            }
            plans.push_back(SinglePlan{
                "lightning_" + std::to_string(x) + "_" + std::to_string(y),
                {operation},
                0.0,
            });
        }
    }
    return plans;
}

inline std::vector<SinglePlan> generate_lightning_prep_candidates(const PublicState &state, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"lightning_hold", {}, 0.0});
    static_cast<void>(state);
    static_cast<void>(player);
    return plans;
}

} // namespace antgame::sdk::lure_strategy_detail
