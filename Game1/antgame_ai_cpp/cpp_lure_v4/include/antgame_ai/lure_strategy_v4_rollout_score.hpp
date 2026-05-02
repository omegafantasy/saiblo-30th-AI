#pragma once

#include <limits>
#include <vector>

#include "antgame_ai/lure_strategy_v4_terminal_eval.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline std::vector<Operation> strip_lightning_operations(const std::vector<Operation> &operations) {
    std::vector<Operation> out;
    out.reserve(operations.size());
    for (const auto &operation : operations) {
        if (operation.op_type != OperationType::UseLightningStorm) {
            out.push_back(operation);
        }
    }
    return out;
}

inline double lightning_counterfactual_bonus(
    const rs::DefenseSimulator &with_lightning,
    const rs::DefenseSimulator &without_lightning) {
    double bonus = 0.0;
    for (const auto &ant : without_lightning.ants) {
        if (ant.kind != AntKind::Combat || !ant.alive()) {
            continue;
        }
        const int without_shield = ant.shield;
        int with_shield = 0;
        int with_hp = 0;
        const rs::SearchAnt *with_ant = nullptr;
        for (const auto &candidate : with_lightning.ants) {
            if (candidate.ant_id == ant.ant_id && candidate.kind == AntKind::Combat && candidate.alive()) {
                with_ant = &candidate;
                break;
            }
        }
        if (with_ant != nullptr) {
            with_shield = with_ant->shield;
            with_hp = with_ant->hp;
        }

        if (without_shield > 0 && with_shield < without_shield) {
            bonus += v4_lure_config().lightning_shield_break_bonus;
        }
        const int damage = std::max(0, ant.hp - with_hp);
        bonus += static_cast<double>(damage) * v4_lure_config().lightning_damage_bonus_per_hp;
    }
    return bonus;
}

inline RolloutEvaluation rollout_plan_score_from_applied_root(
    const rs::DefenseSimulator &pre_plan_root,
    const rs::DefenseSimulator &post_plan_root,
    int player,
    const CombinedPlan &plan,
    std::uint64_t rollout_seed,
    const rs::FixedList<rs::ForcedMove, rs::kMaxImportantAnts> *first_round_forced_moves = nullptr);

inline RolloutEvaluation rollout_plan_score(
    const rs::DefenseSimulator &root,
    int player,
    const CombinedPlan &plan,
    std::uint64_t rollout_seed,
    const rs::FixedList<rs::ForcedMove, rs::kMaxImportantAnts> *first_round_forced_moves = nullptr) {
    rs::DefenseSimulator simulator = root.clone();
    if (!plan.ops.empty()) {
        if (!apply_operations(simulator, plan.ops)) {
            RolloutEvaluation failed;
            failed.total_score = -std::numeric_limits<double>::infinity();
            return failed;
        }
    }
    return rollout_plan_score_from_applied_root(root, simulator, player, plan, rollout_seed, first_round_forced_moves);
}

inline RolloutEvaluation rollout_plan_score_from_applied_root(
    const rs::DefenseSimulator &pre_plan_root,
    const rs::DefenseSimulator &post_plan_root,
    int player,
    const CombinedPlan &plan,
    std::uint64_t rollout_seed,
    const rs::FixedList<rs::ForcedMove, rs::kMaxImportantAnts> *first_round_forced_moves) {
    rs::DefenseSimulator simulator = post_plan_root.clone();
    rs::FastRng rng(rollout_seed);
    if (first_round_forced_moves != nullptr) {
        simulator.simulate_round(rng, *first_round_forced_moves);
    } else {
        simulator.simulate_round(rng);
    }
    RolloutEvaluation out;
    if (plan.has_lightning) {
        rs::DefenseSimulator control = pre_plan_root.clone();
        if (!plan.ops.empty()) {
            apply_operations(control, strip_lightning_operations(plan.ops));
        }
        rs::FastRng control_rng(rollout_seed);
        if (first_round_forced_moves != nullptr) {
            control.simulate_round(control_rng, *first_round_forced_moves);
        } else {
            control.simulate_round(control_rng);
        }
        out.lightning_bonus_raw = lightning_counterfactual_bonus(simulator, control) + plan.lightning_static_bonus;
        out.lightning_bonus_score = out.lightning_bonus_raw;
    }
    EvalBreakdown mid_eval;
    bool has_mid_eval = false;
    double reactive_penalty = 0.0;
    double mid_reactive_penalty = 0.0;
    const int mid_horizon = std::max(0, std::min(plan.horizon, v4_lure_config().mid_eval_horizon));
    int step = 1;
    auto capture_mid_eval = [&]() {
        if (!has_mid_eval && step >= mid_horizon) {
            mid_eval = evaluate_terminal(simulator, player, v4_lure_config().future_threat_apply_to_mid_eval);
            mid_reactive_penalty = reactive_penalty;
            has_mid_eval = true;
        }
    };

    capture_mid_eval();
    while (step < plan.horizon && !simulator.terminal) {
        if (followup_has_turn(plan.followup, step)) {
            const auto followup_ops = resolve_followup_operations(simulator, player, plan.followup, step);
            apply_operations(simulator, followup_ops);
        } else {
            reactive_penalty += apply_reactive_turn_operations_with_penalty(simulator, player);
        }
        simulator.simulate_round(rng);
        ++step;
        capture_mid_eval();
    }
    const EvalBreakdown terminal_eval = evaluate_terminal(simulator, player, true);
    if (!has_mid_eval) {
        mid_eval = terminal_eval;
        mid_reactive_penalty = reactive_penalty;
    }
    out.terminal = combine_eval_breakdowns(mid_eval, terminal_eval, v4_lure_config().mid_eval_weight);
    const double mid_weight = std::max(0.0, std::min(1.0, v4_lure_config().mid_eval_weight));
    out.reactive_operation_penalty = mid_weight * mid_reactive_penalty + (1.0 - mid_weight) * reactive_penalty;
    out.total_score = out.terminal.total_score + out.lightning_bonus_score - out.reactive_operation_penalty;
    return out;
}

} // namespace antgame::sdk::lure_strategy_detail
