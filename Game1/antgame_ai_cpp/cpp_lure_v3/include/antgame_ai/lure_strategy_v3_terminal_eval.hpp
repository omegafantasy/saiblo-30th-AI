#pragma once

#include <algorithm>

#include "antgame_ai/lure_strategy_v3_rollout_sampling.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline bool apply_operations(rs::DefenseSimulator &simulator, const std::vector<Operation> &operations) {
    for (const auto &operation : sort_operations(simulator, operations)) {
        if (!simulator.apply_operation(operation)) {
            return false;
        }
    }
    return true;
}

inline double c1_state_bonus(TowerType tower_type, bool transition_phase) {
    switch (tower_type) {
    case TowerType::Heavy:
    case TowerType::HeavyPlus:
    case TowerType::Ice:
    case TowerType::Bewitch:
        return transition_phase ? v3_lure_config().c1_heavy_side_trans_bonus : v3_lure_config().c1_heavy_bonus;
    case TowerType::Quick:
    case TowerType::QuickPlus:
    case TowerType::Double:
        return transition_phase ? v3_lure_config().c1_quick_trans_bonus : 0.0;
    case TowerType::Sniper:
        return transition_phase ? v3_lure_config().c1_sniper_trans_bonus : 0.0;
    default:
        return 0.0;
    }
}

inline double own_equivalent_total_coins(const rs::DefenseSimulator &simulator) {
    return simulator.coins + tower_full_salvage_value(simulator);
}

inline bool c1_transition_phase_from_action_start(const rs::DefenseSimulator &action_start) {
    return own_equivalent_total_coins(action_start) >=
           static_cast<double>(v3_lure_config().c1_quick_transition_coin_threshold);
}

inline double c1_root_bonus(const rs::DefenseSimulator &post_root, int player, bool transition_phase) {
    const rs::SearchTower *c1 = tower_at_code(post_root, player, C1);
    if (c1 == nullptr || !c1->alive()) {
        return 0.0;
    }
    return c1_state_bonus(c1->tower_type, transition_phase);
}

inline double c1_root_bonus_for_plan(
    const rs::DefenseSimulator &post_root,
    int player,
    const FollowupAction &followup,
    bool transition_phase) {
    if (followup.empty()) {
        return c1_root_bonus(post_root, player, transition_phase);
    }
    rs::DefenseSimulator projected = post_root.clone();
    for (int turn = 1; turn <= 2; ++turn) {
        apply_operations(projected, resolve_followup_operations(projected, player, followup, turn));
    }
    return c1_root_bonus(projected, player, transition_phase);
}

inline double c1_terminal_bonus(const rs::DefenseSimulator &, int) {
    return 0.0;
}

inline double own_equivalent_money_score(double equivalent_money) {
    const double threshold = v3_lure_config().money_decay_threshold;
    const double below = std::min(equivalent_money, threshold);
    const double above = std::max(0.0, equivalent_money - threshold);
    return below * v3_lure_config().money_weight +
           above * v3_lure_config().money_weight_above_threshold;
}

inline EvalBreakdown evaluate_terminal(const rs::DefenseSimulator &simulator, int player) {
    EvalBreakdown out;
    out.base_hp_raw = static_cast<double>(simulator.base_hp);
    out.base_hp_score = out.base_hp_raw * v3_lure_config().base_hp_weight;
    out.tower_value_raw = tower_full_salvage_value(simulator);
    out.money_raw = simulator.coins;
    const double equivalent_money = own_equivalent_total_coins(simulator);
    const double equivalent_money_score = own_equivalent_money_score(equivalent_money);
    if (equivalent_money > 0.0) {
        out.tower_value_score = equivalent_money_score * out.tower_value_raw / equivalent_money;
        out.money_score = equivalent_money_score * out.money_raw / equivalent_money;
    }
    out.c1_bonus_raw = c1_terminal_bonus(simulator, player);
    out.c1_bonus_score = out.c1_bonus_raw;
    out.worker_threat_raw = worker_threat_score(simulator, player);
    out.worker_threat_score = -out.worker_threat_raw;
    out.combat_threat_raw = combat_threat_score(simulator, player);
    out.combat_threat_score = -out.combat_threat_raw;
    out.total_score = out.base_hp_score + out.tower_value_score + out.money_score + out.c1_bonus_score +
                      out.worker_threat_score + out.combat_threat_score;
    return out;
}

inline EvalBreakdown combine_eval_breakdowns(
    const EvalBreakdown &mid,
    const EvalBreakdown &terminal,
    double mid_weight) {
    const double weight = std::max(0.0, std::min(1.0, mid_weight));
    EvalBreakdown out = mid.scaled(weight);
    out += terminal.scaled(1.0 - weight);
    return out;
}

} // namespace antgame::sdk::lure_strategy_detail
