#pragma once

#include <algorithm>
#include <string>
#include <vector>

#include "antgame_ai/lure_strategy_v4_common.hpp"

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

inline bool base_code_enabled(int code) {
    return is_base_slot_code(code) && code != C2;
}

inline bool base_build_enabled(int code) {
    return base_code_enabled(code);
}

inline bool base_upgrade_enabled(int code) {
    return base_code_enabled(code);
}

inline bool c1_quick_route_enabled(int code) {
    return code == C1;
}

inline bool quick_sniper_route_enabled(int code) {
    return base_upgrade_enabled(code) &&
           (code == C1 || code == C3 || code == L1 || code == L2 || code == L3 || code == R1 ||
            code == R2 || code == R3);
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

inline bool producer_medic_branch_enabled(const PublicState &state, int player) {
    return v4_lure_config().enable_producer_medic_branch &&
           c1_has_sniper(state, player) &&
           equivalent_money_excluding_c1_sniper(state, player) > v4_lure_config().producer_medic_equivalent_money_threshold;
}

inline bool producer_medic_branch_enabled(const rs::DefenseSimulator &simulator, int player) {
    return v4_lure_config().enable_producer_medic_branch &&
           c1_has_sniper(simulator, player) &&
           equivalent_money_excluding_c1_sniper(simulator, player) >
               v4_lure_config().producer_medic_equivalent_money_threshold;
}

inline double base_limit_equivalent_money(const PublicState &state, int player) {
    return static_cast<double>(state.coins[player]) + tower_full_salvage_value(state, player);
}

inline double base_limit_equivalent_money(const rs::DefenseSimulator &simulator) {
    return static_cast<double>(simulator.coins) + tower_full_salvage_value(simulator);
}

inline int non_lure_tower_build_limit(double equivalent_money) {
    if (equivalent_money >= v4_lure_config().money_decay_threshold) {
        return std::max(v4_lure_config().max_non_lure_towers, v4_lure_config().rich_max_non_lure_towers);
    }
    return v4_lure_config().max_non_lure_towers;
}

inline int non_lure_tower_build_limit(const PublicState &state, int player) {
    return non_lure_tower_build_limit(base_limit_equivalent_money(state, player));
}

inline int non_lure_tower_build_limit(const rs::DefenseSimulator &simulator) {
    return non_lure_tower_build_limit(base_limit_equivalent_money(simulator));
}

inline double producer_medic_upgrade_heuristic(TowerType target_type) {
    if (target_type == TowerType::Producer) {
        return v4_lure_config().producer_upgrade_bonus;
    }
    if (target_type == TowerType::ProducerMedic) {
        return v4_lure_config().medic_upgrade_bonus;
    }
    return 0.0;
}

inline double followup_upgrade_heuristic(const FollowupAction &followup) {
    double bonus = 0.0;
    for (int index = 0; index < followup.count; ++index) {
        const FollowupStep &step = followup.steps[static_cast<std::size_t>(index)];
        if (step.type == FollowupType::UpgradeAtCode) {
            bonus += producer_medic_upgrade_heuristic(step.target);
        }
    }
    return bonus;
}

inline FollowupAction producer_medic_followup(int code) {
    return followup_sequence({
        upgrade_step(code, TowerType::Producer, 1),
        upgrade_step(code, TowerType::ProducerMedic, 2),
    });
}

inline std::vector<TowerType> base_build_upgrade_targets(int code, bool c1_sniper_ready, bool producer_medic_enabled) {
    if (!base_upgrade_enabled(code)) {
        return {};
    }
    if (code == C1) {
        return {TowerType::Heavy};
    }
    std::vector<TowerType> out;
    if (c1_sniper_ready) {
        out = {TowerType::Heavy, TowerType::Quick, TowerType::Mortar};
    } else {
        out = {TowerType::Heavy, TowerType::Mortar};
    }
    if (producer_medic_enabled) {
        out.push_back(TowerType::Producer);
    }
    return out;
}

inline bool can_build_quick_sniper_chain(int code, bool c1_sniper_ready) {
    return sniper_route_allowed(code, c1_sniper_ready);
}

inline FollowupAction quick_sniper_followup(int code) {
    return followup_sequence({upgrade_step(code, TowerType::Quick, 1), upgrade_step(code, TowerType::Sniper, 2)});
}

inline std::vector<TowerType> base_existing_upgrade_targets(int code, bool c1_sniper_ready, bool producer_medic_enabled) {
    if (!base_upgrade_enabled(code)) {
        return {};
    }
    if (code == C1) {
        return {TowerType::Heavy};
    }
    std::vector<TowerType> out;
    if (c1_sniper_ready) {
        out = {TowerType::Heavy, TowerType::Quick, TowerType::Mortar};
    } else {
        out = {TowerType::Heavy, TowerType::Mortar};
    }
    if (producer_medic_enabled) {
        out.push_back(TowerType::Producer);
    }
    return out;
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
    return code == C1 ? v4_lure_config().c1_build_bonus : 0.0;
}

} // namespace antgame::sdk::lure_strategy_detail
