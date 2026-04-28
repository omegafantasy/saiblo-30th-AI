#pragma once

#include <string>
#include <vector>

#include "antgame_ai/lure_strategy_v3_common.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline void append_downgrade_candidate(
    const PublicState &state,
    int player,
    const Tower *tower,
    const std::string &name,
    std::vector<SinglePlan> &plans) {
    if (tower == nullptr || tower->player != player) {
        return;
    }
    const Operation downgrade(OperationType::DowngradeTower, tower->tower_id);
    if (!legalize_operations(state, player, {downgrade}).empty()) {
        plans.push_back(SinglePlan{name, {downgrade}, 0.0});
    }
}

inline void append_downgrade_candidate(
    const rs::DefenseSimulator &simulator,
    int /*player*/,
    const rs::SearchTower *tower,
    const std::string &name,
    std::vector<SinglePlan> &plans) {
    if (tower == nullptr || !tower->alive()) {
        return;
    }
    const Operation downgrade(OperationType::DowngradeTower, tower->tower_id);
    if (!legalize_operations(simulator, {downgrade}).empty()) {
        plans.push_back(SinglePlan{name, {downgrade}, 0.0});
    }
}

inline bool base_build_enabled(int code) {
    return code != C2 && code != C3;
}

inline bool c1_quick_route_enabled(int code) {
    return code == C1;
}

inline bool quick_sniper_route_enabled(int code) {
    return code == C1 || code == C2 || code == C3 || code == L1 || code == L2 || code == L3 || code == R1 ||
           code == R2 || code == R3;
}

inline bool sniper_route_allowed(int code, bool c1_sniper_ready) {
    return quick_sniper_route_enabled(code) && (c1_sniper_ready || code == C1);
}

inline bool c1_has_sniper(const PublicState &state, int player) {
    const Tower *tower = tower_at_code(state, player, C1);
    return tower != nullptr && tower->player == player && tower->tower_type == TowerType::Sniper;
}

inline bool c1_has_sniper(const rs::DefenseSimulator &simulator, int player) {
    const rs::SearchTower *tower = tower_at_code(simulator, player, C1);
    return tower != nullptr && tower->alive() && tower->tower_type == TowerType::Sniper;
}

inline std::vector<TowerType> base_build_upgrade_targets(int code, bool c1_sniper_ready) {
    if (code == C1) {
        return {TowerType::Heavy};
    }
    if (c1_sniper_ready) {
        return {TowerType::Heavy, TowerType::Quick, TowerType::Mortar};
    }
    return {TowerType::Heavy, TowerType::Mortar};
}

inline bool can_build_quick_sniper_chain(int code, bool c1_sniper_ready) {
    return sniper_route_allowed(code, c1_sniper_ready);
}

inline FollowupAction quick_sniper_followup(int code) {
    return followup_sequence({upgrade_step(code, TowerType::Quick, 1), upgrade_step(code, TowerType::Sniper, 2)});
}

inline std::vector<TowerType> base_existing_upgrade_targets(int code, bool c1_sniper_ready) {
    if (code == C1) {
        return {TowerType::Heavy};
    }
    if (c1_sniper_ready) {
        return {TowerType::Heavy, TowerType::Quick, TowerType::Mortar};
    }
    return {TowerType::Heavy, TowerType::Mortar};
}

inline int non_lure_tower_count(const PublicState &state, int player) {
    int count = 0;
    for (const auto &tower : state.towers) {
        if (tower.player == player && !is_lure_slot_code(code_at(tower, player))) {
            ++count;
        }
    }
    return count;
}

inline int non_lure_tower_count(const rs::DefenseSimulator &simulator, int player) {
    int count = 0;
    for (const auto &tower : simulator.towers) {
        if (tower.alive() && !is_lure_slot_code(code_at(tower, player))) {
            ++count;
        }
    }
    return count;
}

inline double c1_build_heuristic(int code) {
    return code == C1 ? v3_lure_config().c1_build_bonus : 0.0;
}

} // namespace antgame::sdk::lure_strategy_detail
