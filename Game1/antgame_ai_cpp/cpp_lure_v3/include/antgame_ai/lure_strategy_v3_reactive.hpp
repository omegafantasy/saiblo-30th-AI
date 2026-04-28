#pragma once

#include "antgame_ai/lure_strategy_v3_root_plans.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline std::vector<Operation> choose_reactive_turn_operations(const rs::DefenseSimulator &simulator, int player) {
    if (const rs::SearchTower *forced = forced_reactive_sell_target(simulator, player); forced != nullptr) {
        return {Operation(OperationType::DowngradeTower, forced->tower_id)};
    }
    const auto base = generate_base_candidates(simulator, player);
    const auto lure = generate_lure_candidates(simulator, player);

    double best_heuristic = -std::numeric_limits<double>::infinity();
    std::vector<Operation> best_ops;

    auto consider = [&](const SinglePlan &plan) {
        std::vector<Operation> combined = legalize_operations(simulator, plan.ops);
        if (!plan.ops.empty() && combined.empty()) {
            return;
        }
        const double heuristic = plan.heuristic - downgrade_penalty_for_ops(simulator, combined);
        if (heuristic > best_heuristic) {
            best_heuristic = heuristic;
            best_ops = std::move(combined);
        }
    };
    for (const auto &base_plan : base) {
        consider(base_plan);
    }
    for (const auto &lure_plan : lure) {
        consider(lure_plan);
    }
    return best_ops;
}

inline double apply_reactive_turn_operations_with_penalty(rs::DefenseSimulator &simulator, int player) {
    if (const rs::SearchTower *forced = forced_reactive_sell_target(simulator, player); forced != nullptr) {
        const Operation downgrade(OperationType::DowngradeTower, forced->tower_id);
        const double penalty = downgrade_operation_penalty(simulator, downgrade);
        if (simulator.apply_operation(downgrade)) {
            return penalty;
        }
    }
    return 0.0;
}

inline std::vector<Operation> resolve_followup_step_operations(
    const rs::DefenseSimulator &simulator,
    int player,
    const FollowupStep &step) {
    if (step.empty()) {
        return {};
    }
    if (step.type == FollowupType::BuildAtCode) {
        return legalize_operations(simulator, {build_at_code(player, step.code)});
    }

    const rs::SearchTower *tower = tower_at_code(simulator, player, step.code);
    if (tower == nullptr || !tower->alive()) {
        return {};
    }
    switch (step.type) {
    case FollowupType::UpgradeAtCode: {
        const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(step.target));
        return legalize_operations(simulator, {upgrade});
    }
    case FollowupType::DowngradeAtCode: {
        const Operation downgrade(OperationType::DowngradeTower, tower->tower_id);
        return legalize_operations(simulator, {downgrade});
    }
    case FollowupType::BuildAtCode:
    case FollowupType::None:
    default:
        return {};
    }
}

inline std::vector<Operation> resolve_followup_operations(
    const rs::DefenseSimulator &simulator,
    int player,
    const FollowupAction &followup,
    int turn = 1) {
    if (followup.empty()) {
        return {};
    }
    std::vector<Operation> raw_ops;
    raw_ops.reserve(static_cast<std::size_t>(followup.count));

    struct PendingBuild {
        int code = -1;
        int tower_id = -1;
    };
    std::array<PendingBuild, FollowupAction::kMaxSteps> pending_builds{};
    int pending_build_count = 0;
    int predicted_tower_id = simulator.next_tower_id;

    auto pending_tower_id_at = [&](int code) {
        for (int index = pending_build_count - 1; index >= 0; --index) {
            if (pending_builds[static_cast<std::size_t>(index)].code == code) {
                return pending_builds[static_cast<std::size_t>(index)].tower_id;
            }
        }
        return -1;
    };

    for (int index = 0; index < followup.count; ++index) {
        const FollowupStep &step = followup.steps[static_cast<std::size_t>(index)];
        if (step.empty() || step.turn != turn) {
            continue;
        }
        if (step.type == FollowupType::BuildAtCode) {
            raw_ops.push_back(build_at_code(player, step.code));
            if (pending_build_count < FollowupAction::kMaxSteps) {
                pending_builds[static_cast<std::size_t>(pending_build_count++)] =
                    PendingBuild{step.code, predicted_tower_id++};
            }
            continue;
        }

        const rs::SearchTower *tower = tower_at_code(simulator, player, step.code);
        int tower_id = tower != nullptr && tower->alive() ? tower->tower_id : -1;
        if (tower_id < 0 && step.type == FollowupType::UpgradeAtCode) {
            tower_id = pending_tower_id_at(step.code);
        }
        if (tower_id < 0) {
            continue;
        }

        if (step.type == FollowupType::UpgradeAtCode) {
            raw_ops.emplace_back(OperationType::UpgradeTower, tower_id, static_cast<int>(step.target));
        } else if (step.type == FollowupType::DowngradeAtCode) {
            raw_ops.emplace_back(OperationType::DowngradeTower, tower_id);
        }
    }

    rs::DefenseSimulator scratch = simulator.clone();
    std::vector<Operation> accepted;
    accepted.reserve(raw_ops.size());
    bool required_recycle_failed = false;
    for (const Operation &operation : sort_operations(simulator, raw_ops)) {
        if (required_recycle_failed && operation.op_type == OperationType::UpgradeTower) {
            continue;
        }
        if (scratch.can_apply_operation(operation)) {
            scratch.apply_operation(operation);
            accepted.push_back(operation);
            continue;
        }
        if (operation.op_type == OperationType::DowngradeTower) {
            required_recycle_failed = true;
        }
    }
    return accepted;
}

} // namespace antgame::sdk::lure_strategy_detail
