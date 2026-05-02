#pragma once

#include "antgame_ai/lure_strategy_v4_lightning_plans.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline bool root_ops_respect_non_lure_limit(
    const PublicState &state,
    int player,
    const std::vector<Operation> &operations) {
    const int initial_count = non_lure_tower_count(state, player);
    int post_count = initial_count;
    bool builds_base_tower = false;
    for (const Operation &operation : operations) {
        if (operation.op_type == OperationType::BuildTower) {
            if (is_base_slot_code(old_ai_position_code_at(player, operation.arg0, operation.arg1))) {
                builds_base_tower = true;
                ++post_count;
            }
            continue;
        }
        if (operation.op_type != OperationType::DowngradeTower) {
            continue;
        }
        const Tower *tower = state.tower_by_id(operation.arg0);
        if (tower == nullptr || !is_base_slot_code(code_at(*tower, player))) {
            continue;
        }
        if (tower->tower_type == TowerType::Basic) {
            --post_count;
        }
    }
    if (!builds_base_tower || post_count <= initial_count) {
        return true;
    }
    return post_count <= non_lure_tower_build_limit(state, player);
}

inline bool push_followup_checked(FollowupAction &followup, FollowupStep step) {
    if (step.empty() || followup.count >= FollowupAction::kMaxSteps) {
        return false;
    }
    followup.push(step);
    return true;
}

inline bool append_delayed_operation_followup(
    const PublicState &state,
    int player,
    const Operation &operation,
    int turn,
    FollowupAction &followup) {
    if (operation.op_type == OperationType::BuildTower) {
        const int code = old_ai_position_code_at(player, operation.arg0, operation.arg1);
        if (code < 0) {
            return false;
        }
        return push_followup_checked(followup, build_step(code, turn));
    }

    const Tower *tower = state.tower_by_id(operation.arg0);
    if (tower == nullptr || tower->player != player) {
        return false;
    }
    const int code = code_at(*tower, player);
    if (operation.op_type == OperationType::UpgradeTower) {
        return push_followup_checked(
            followup,
            upgrade_step(code, static_cast<TowerType>(operation.arg1), turn));
    }
    if (operation.op_type == OperationType::DowngradeTower) {
        return push_followup_checked(followup, downgrade_step(code, turn));
    }
    return false;
}

inline bool delayed_followup_from_plan(
    const PublicState &state,
    int player,
    const SinglePlan &plan,
    int delay_turn,
    FollowupAction &out) {
    if (plan.ops.empty() || delay_turn <= 0) {
        return false;
    }
    FollowupAction followup;
    for (const Operation &operation : plan.ops) {
        if (!append_delayed_operation_followup(state, player, operation, delay_turn, followup)) {
            return false;
        }
    }
    for (int index = 0; index < plan.followup.count; ++index) {
        FollowupStep step = plan.followup.steps[static_cast<std::size_t>(index)];
        if (step.empty()) {
            continue;
        }
        step.turn += delay_turn;
        if (!push_followup_checked(followup, step)) {
            return false;
        }
    }
    out = followup;
    return !out.empty();
}

inline bool append_followup_steps(FollowupAction &target, const FollowupAction &source) {
    for (int index = 0; index < source.count; ++index) {
        if (!push_followup_checked(target, source.steps[static_cast<std::size_t>(index)])) {
            return false;
        }
    }
    return true;
}

inline bool base_lure_recycle_plan(
    const PublicState &state,
    int player,
    const Tower &source,
    const SinglePlan &lure_plan,
    std::vector<Operation> &ops,
    FollowupAction &followup) {
    const int source_code = code_at(source, player);
    if (source.player != player || !is_base_slot_code(source_code) || lure_plan.ops.empty()) {
        return false;
    }

    const Operation first_downgrade(OperationType::DowngradeTower, source.tower_id);
    if (legalize_operations(state, player, {first_downgrade}).empty()) {
        return false;
    }

    const int source_level = tower_level(source.tower_type);
    if (source_level <= 0) {
        ops = {first_downgrade};
        ops.insert(ops.end(), lure_plan.ops.begin(), lure_plan.ops.end());
        followup = lure_plan.followup;
        return true;
    }

    ops = {first_downgrade};
    FollowupAction combined;
    for (int turn = 1; turn <= source_level; ++turn) {
        if (!push_followup_checked(combined, downgrade_step(source_code, turn))) {
            return false;
        }
    }

    FollowupAction delayed_lure;
    if (!delayed_followup_from_plan(state, player, lure_plan, source_level, delayed_lure)) {
        return false;
    }
    if (!append_followup_steps(combined, delayed_lure)) {
        return false;
    }
    followup = combined;
    return true;
}

inline bool is_lure_sell_only_plan(const PublicState &state, int player, const SinglePlan &plan) {
    if (!plan.followup.empty() || plan.ops.size() != 1) {
        return false;
    }
    const Operation &operation = plan.ops.front();
    if (operation.op_type != OperationType::DowngradeTower) {
        return false;
    }
    const Tower *tower = state.tower_by_id(operation.arg0);
    return tower != nullptr && tower->player == player && is_lure_slot_code(code_at(*tower, player));
}

inline bool is_single_turn_base_plan(const SinglePlan &plan) {
    return !plan.ops.empty() && plan.followup.empty();
}

inline RootPlanSet generate_root_plans(
    const PublicState &state,
    const rs::DefenseSimulator *simulator,
    int player) {
    const auto base = generate_base_candidates(state, player);
    const auto lure = generate_lure_candidates(state, simulator, player);
    const auto lightning_prep = generate_lightning_prep_candidates(state, player);
    const auto lightning_center = generate_lightning_center_candidates(state, simulator, player);

    RootPlanSet out;
    out.base_candidates = base;
    out.lure_candidates = lure;
    out.lightning_prep_candidates = lightning_prep;
    out.lightning_center_candidates = lightning_center;
    out.base_count = static_cast<int>(base.size());
    out.lure_count = static_cast<int>(lure.size());
    out.lightning_count = static_cast<int>(lightning_center.size());
    out.raw_combo_count = out.base_count + out.lure_count;
    out.raw_plan_count = out.raw_combo_count + out.lightning_count;
    int base_lure_combo_count = 0;
    int lure_sell_base_combo_count = 0;
    int lightning_recycle_combo_count = 0;

    std::vector<CombinedPlan> &plans = out.plans;
    std::unordered_map<std::string, std::size_t> seen;
    const SinglePlan no_lightning{"no_lightning", {}, 0.0};

    auto add_plan = [&](const std::string &name,
                        const std::string &base_name,
                        const std::string &lure_name,
                        const std::string &lightning_name,
                        const std::vector<Operation> &raw_ops,
                        double base_heuristic,
                        double lure_heuristic,
                        double lightning_heuristic,
                        bool has_lightning,
                        int horizon,
                        FollowupAction followup) {
        std::vector<Operation> combined = legalize_operations(state, player, raw_ops);
        if (!raw_ops.empty() && combined.empty()) {
            return;
        }
        if (!root_ops_respect_non_lure_limit(state, player, combined)) {
            return;
        }
        const std::string key = plan_key(combined, followup);
        const double operation_penalty = downgrade_penalty_for_ops(state, player, combined);
        const double followup_penalty = followup.empty() ? 0.0 : v4_lure_config().followup_plan_penalty;
        const double heuristic =
            base_heuristic + lure_heuristic + lightning_heuristic - operation_penalty - followup_penalty;
        double lightning_static_bonus = 0.0;
        if (has_lightning && !combined.empty()) {
            lightning_static_bonus += enemy_super_effect_active(state, player)
                                          ? v4_lure_config().lightning_enemy_super_bonus
                                          : v4_lure_config().lightning_no_enemy_super_penalty;
        }
        if (has_lightning) {
            for (const auto &operation : combined) {
                if (operation.op_type == OperationType::UseLightningStorm) {
                    lightning_static_bonus +=
                        enemy_tower_lightning_damage_score(state, player, operation.arg0, operation.arg1);
                }
            }
        }
        auto it = seen.find(key);
        if (it == seen.end()) {
            CombinedPlan item;
            item.key = key;
            item.name = name;
            item.base_name = base_name;
            item.lure_name = lure_name;
            item.lightning_name = lightning_name;
            item.ops = std::move(combined);
            item.heuristic = heuristic;
            item.base_heuristic = base_heuristic;
            item.lure_heuristic = lure_heuristic;
            item.lightning_heuristic = lightning_heuristic;
            item.operation_penalty = operation_penalty;
            item.followup_penalty = followup_penalty;
            item.lightning_static_bonus = lightning_static_bonus;
            item.has_lightning = has_lightning;
            item.horizon = horizon;
            item.followup = followup;
            seen.emplace(key, plans.size());
            plans.push_back(std::move(item));
            return;
        }
        if (heuristic > plans[it->second].heuristic) {
            plans[it->second].name = name;
            plans[it->second].base_name = base_name;
            plans[it->second].lure_name = lure_name;
            plans[it->second].lightning_name = lightning_name;
            plans[it->second].heuristic = heuristic;
            plans[it->second].base_heuristic = base_heuristic;
            plans[it->second].lure_heuristic = lure_heuristic;
            plans[it->second].lightning_heuristic = lightning_heuristic;
            plans[it->second].operation_penalty = operation_penalty;
            plans[it->second].followup_penalty = followup_penalty;
            plans[it->second].lightning_static_bonus = lightning_static_bonus;
            plans[it->second].has_lightning = has_lightning;
            plans[it->second].horizon = horizon;
            plans[it->second].followup = followup;
        }
    };

    const auto is_hold = [](const SinglePlan &plan) {
        return plan.ops.empty() && plan.followup.empty();
    };
    bool has_base_hold = false;
    bool has_lure_hold = false;
    for (const auto &base_plan : base) {
        if (is_hold(base_plan)) {
            has_base_hold = true;
        }
    }
    for (const auto &lure_plan : lure) {
        if (is_hold(lure_plan)) {
            has_lure_hold = true;
        }
    }
    if (has_base_hold || has_lure_hold) {
        add_plan(
            "base_hold+lure_hold",
            has_base_hold ? "base_hold" : "none",
            has_lure_hold ? "lure_hold" : "none",
            no_lightning.name,
            {},
            v4_lure_config().hold_bonus,
            0.0,
            0.0,
            false,
            v4_lure_config().long_eval_horizon,
            FollowupAction{});
    }

    if (v4_lure_config().hold_followup_enabled && v4_lure_config().hold_followup_delay_turn > 0) {
        const int delay_turn = std::max(1, v4_lure_config().hold_followup_delay_turn);
        const double scale = std::max(0.0, v4_lure_config().hold_followup_heuristic_scale);
        for (const auto &lure_plan : lure) {
            if (is_hold(lure_plan)) {
                continue;
            }
            FollowupAction delayed;
            if (!delayed_followup_from_plan(state, player, lure_plan, delay_turn, delayed)) {
                continue;
            }
            add_plan(
                "hold_then_" + lure_plan.name,
                "base_hold",
                "hold_then_" + lure_plan.name,
                no_lightning.name,
                {},
                v4_lure_config().hold_bonus,
                lure_plan.heuristic * scale,
                0.0,
                false,
                v4_lure_config().long_eval_horizon,
                delayed);
        }
    }

    for (const auto &base_plan : base) {
        if (is_hold(base_plan)) {
            continue;
        }
        add_plan(
            base_plan.name,
            base_plan.name,
            "none",
            no_lightning.name,
            base_plan.ops,
            base_plan.heuristic,
            0.0,
            0.0,
            false,
            v4_lure_config().long_eval_horizon,
            base_plan.followup);
    }

    for (const auto &lure_plan : lure) {
        if (is_hold(lure_plan)) {
            continue;
        }
        add_plan(
            lure_plan.name,
            "none",
            lure_plan.name,
            no_lightning.name,
            lure_plan.ops,
            0.0,
            lure_plan.heuristic,
            0.0,
            false,
            v4_lure_config().long_eval_horizon,
            lure_plan.followup);
    }

    for (const auto &lure_plan : lure) {
        if (!is_lure_sell_only_plan(state, player, lure_plan)) {
            continue;
        }
        for (const auto &base_plan : base) {
            if (!is_single_turn_base_plan(base_plan)) {
                continue;
            }
            std::vector<Operation> ops;
            ops.reserve(lure_plan.ops.size() + base_plan.ops.size());
            ops.insert(ops.end(), lure_plan.ops.begin(), lure_plan.ops.end());
            ops.insert(ops.end(), base_plan.ops.begin(), base_plan.ops.end());
            ++lure_sell_base_combo_count;
            add_plan(
                lure_plan.name + "+" + base_plan.name,
                base_plan.name,
                lure_plan.name,
                no_lightning.name,
                ops,
                base_plan.heuristic,
                lure_plan.heuristic,
                0.0,
                false,
                v4_lure_config().long_eval_horizon,
                FollowupAction{});
        }
    }

    for (const auto &source : state.towers) {
        if (source.player != player || !is_base_slot_code(code_at(source, player))) {
            continue;
        }
        for (const auto &lure_plan : lure) {
            if (is_hold(lure_plan)) {
                continue;
            }
            std::vector<Operation> ops;
            FollowupAction followup;
            if (!base_lure_recycle_plan(state, player, source, lure_plan, ops, followup)) {
                continue;
            }
            ++base_lure_combo_count;
            const std::string base_name = std::string("base_recycle_") + code_name(code_at(source, player));
            add_plan(
                base_name + "+" + lure_plan.name,
                base_name,
                lure_plan.name,
                no_lightning.name,
                ops,
                0.0,
                lure_plan.heuristic,
                0.0,
                false,
                v4_lure_config().long_eval_horizon,
                followup);
        }
    }

    for (const auto &center_plan : lightning_center) {
        add_plan(
            center_plan.name,
            "none",
            "none",
            center_plan.name,
            center_plan.ops,
            0.0,
            0.0,
            center_plan.heuristic,
            true,
            v4_lure_config().lightning_horizon,
            FollowupAction{});
    }

    for (const Tower *target : combat_adjacent_tower_targets(state, player)) {
        const Operation recycle(OperationType::DowngradeTower, target->tower_id);
        for (const auto &center_plan : lightning_center) {
            std::vector<Operation> ops;
            ops.reserve(1 + center_plan.ops.size());
            ops.push_back(recycle);
            ops.insert(ops.end(), center_plan.ops.begin(), center_plan.ops.end());
            add_plan(
                std::string("combat_adjacent_recycle_") + tower_slot_name(*target, player) + "+" + center_plan.name,
                std::string("combat_adjacent_recycle_") + tower_slot_name(*target, player),
                "none",
                center_plan.name,
                ops,
                0.0,
                0.0,
                center_plan.heuristic,
                true,
                v4_lure_config().lightning_horizon,
                FollowupAction{});
            ++lightning_recycle_combo_count;
        }
    }

    out.raw_combo_count = out.base_count + out.lure_count + base_lure_combo_count + lure_sell_base_combo_count;
    out.raw_plan_count = out.raw_combo_count + out.lightning_count + lightning_recycle_combo_count;

    std::sort(plans.begin(), plans.end(), [](const CombinedPlan &lhs, const CombinedPlan &rhs) {
        if (lhs.heuristic != rhs.heuristic) {
            return lhs.heuristic > rhs.heuristic;
        }
        return lhs.key < rhs.key;
    });
    return out;
}

} // namespace antgame::sdk::lure_strategy_detail
