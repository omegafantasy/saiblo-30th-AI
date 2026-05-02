#pragma once

#include <string>
#include <vector>

#include "antgame_ai/lure_strategy_v4_base_rules.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline bool can_sell_to_bottom_for_swap(TowerType type) {
    const int raw = static_cast<int>(type);
    return type == TowerType::Basic || (raw > 0 && raw < 10);
}

inline std::string swap_plan_name(int from_code, int to_code, TowerType upgrade_target) {
    return std::string("base_swap_") + code_name(from_code) + "_to_" + code_name(to_code) +
           "_" + tower_type_name(upgrade_target);
}

inline bool swap_needs_second_turn_sell(TowerType source_type) {
    return source_type != TowerType::Basic;
}

inline FollowupAction swap_followup(TowerType source_type, int source_code, int target_code, TowerType upgrade_target) {
    FollowupAction followup;
    if (swap_needs_second_turn_sell(source_type)) {
        followup.push(downgrade_step(source_code));
        followup.push(build_step(target_code));
        if (upgrade_target != TowerType::Basic) {
            followup.push(upgrade_step(target_code, upgrade_target, 2));
        }
        return followup;
    }
    if (upgrade_target != TowerType::Basic) {
        followup.push(upgrade_step(target_code, upgrade_target));
    }
    return followup;
}

inline FollowupAction swap_producer_medic_followup(TowerType source_type, int source_code, int target_code) {
    FollowupAction followup;
    if (swap_needs_second_turn_sell(source_type)) {
        followup.push(downgrade_step(source_code, 1));
        followup.push(build_step(target_code, 1));
        followup.push(upgrade_step(target_code, TowerType::Producer, 2));
        followup.push(upgrade_step(target_code, TowerType::ProducerMedic, 3));
        return followup;
    }
    followup.push(upgrade_step(target_code, TowerType::Producer, 1));
    followup.push(upgrade_step(target_code, TowerType::ProducerMedic, 2));
    return followup;
}

inline std::vector<Operation> swap_root_operations(
    int player,
    int source_tower_id,
    TowerType source_type,
    int target_code) {
    std::vector<Operation> ops;
    ops.reserve(2);
    ops.push_back(Operation(OperationType::DowngradeTower, source_tower_id));
    if (!swap_needs_second_turn_sell(source_type)) {
        ops.push_back(build_at_code(player, target_code));
    }
    return ops;
}

inline void append_base_swap_candidates(
    const PublicState &state,
    int player,
    const Tower &source,
    int source_code,
    std::vector<SinglePlan> &plans) {
    if (!can_sell_to_bottom_for_swap(source.tower_type)) {
        return;
    }
    const Operation down(OperationType::DowngradeTower, source.tower_id);
    if (legalize_operations(state, player, {down}).empty()) {
        return;
    }
    const bool c1_sniper_ready = c1_has_sniper(state, player);
    const bool producer_medic_enabled = producer_medic_branch_enabled(state, player);
    for (int target_code : base_codes()) {
        if (target_code == source_code || !base_build_enabled(target_code) ||
            tower_at_code(state, player, target_code) != nullptr) {
            continue;
        }
        const auto basic_ops = swap_root_operations(
            player,
            source.tower_id,
            source.tower_type,
            target_code);
        if (!legalize_operations(state, player, basic_ops).empty()) {
            plans.push_back(SinglePlan{
                swap_plan_name(source_code, target_code, TowerType::Basic),
                basic_ops,
                0.0,
                swap_followup(source.tower_type, source_code, target_code, TowerType::Basic),
            });
        }
        for (TowerType target_type : base_build_upgrade_targets(target_code, c1_sniper_ready, producer_medic_enabled)) {
            const auto ops = swap_root_operations(
                player,
                source.tower_id,
                source.tower_type,
                target_code);
            if (!legalize_operations(state, player, ops).empty()) {
                const FollowupAction followup = swap_followup(source.tower_type, source_code, target_code, target_type);
                plans.push_back(SinglePlan{
                    swap_plan_name(source_code, target_code, target_type),
                    ops,
                    followup_upgrade_heuristic(followup),
                    followup,
                });
                if (target_type == TowerType::Producer) {
                    const FollowupAction medic_followup =
                        swap_producer_medic_followup(source.tower_type, source_code, target_code);
                    plans.push_back(SinglePlan{
                        swap_plan_name(source_code, target_code, TowerType::ProducerMedic),
                        ops,
                        followup_upgrade_heuristic(medic_followup),
                        medic_followup,
                    });
                }
            }
        }
    }
}

inline void append_base_swap_candidates(
    const rs::DefenseSimulator &simulator,
    int player,
    const rs::SearchTower &source,
    int source_code,
    std::vector<SinglePlan> &plans) {
    if (!can_sell_to_bottom_for_swap(source.tower_type)) {
        return;
    }
    const Operation down(OperationType::DowngradeTower, source.tower_id);
    if (legalize_operations(simulator, {down}).empty()) {
        return;
    }
    const bool c1_sniper_ready = c1_has_sniper(simulator, player);
    const bool producer_medic_enabled = producer_medic_branch_enabled(simulator, player);
    for (int target_code : base_codes()) {
        if (target_code == source_code || !base_build_enabled(target_code) ||
            tower_at_code(simulator, player, target_code) != nullptr) {
            continue;
        }
        const auto basic_ops = swap_root_operations(
            player,
            source.tower_id,
            source.tower_type,
            target_code);
        if (!legalize_operations(simulator, basic_ops).empty()) {
            plans.push_back(SinglePlan{
                swap_plan_name(source_code, target_code, TowerType::Basic),
                basic_ops,
                0.0,
                swap_followup(source.tower_type, source_code, target_code, TowerType::Basic),
            });
        }
        for (TowerType target_type : base_build_upgrade_targets(target_code, c1_sniper_ready, producer_medic_enabled)) {
            const auto ops = swap_root_operations(
                player,
                source.tower_id,
                source.tower_type,
                target_code);
            if (!legalize_operations(simulator, ops).empty()) {
                const FollowupAction followup = swap_followup(source.tower_type, source_code, target_code, target_type);
                plans.push_back(SinglePlan{
                    swap_plan_name(source_code, target_code, target_type),
                    ops,
                    followup_upgrade_heuristic(followup),
                    followup,
                });
                if (target_type == TowerType::Producer) {
                    const FollowupAction medic_followup =
                        swap_producer_medic_followup(source.tower_type, source_code, target_code);
                    plans.push_back(SinglePlan{
                        swap_plan_name(source_code, target_code, TowerType::ProducerMedic),
                        ops,
                        followup_upgrade_heuristic(medic_followup),
                        medic_followup,
                    });
                }
            }
        }
    }
}

} // namespace antgame::sdk::lure_strategy_detail
