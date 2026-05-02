#pragma once

#include <vector>

#include "antgame_ai/lure_strategy_v4_base_swap.hpp"
#include "antgame_ai/lure_strategy_v4_reactive_targets.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline std::vector<SinglePlan> generate_base_candidates(const PublicState &state, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"base_hold", {}, 0.0});

    const int base_tower_count = non_lure_tower_count(state, player);
    const bool can_build_more = base_tower_count < non_lure_tower_build_limit(state, player);
    const bool c1_sniper_ready = c1_has_sniper(state, player);
    const bool producer_medic_enabled = producer_medic_branch_enabled(state, player);

    if (base_tower_count == 0 && tower_at_code(state, player, C1) == nullptr) {
        for (int code : base_codes()) {
            if (code == C1 || !base_build_enabled(code) || tower_at_code(state, player, code) != nullptr) {
                continue;
            }
            std::vector<Operation> ops{build_at_code(player, C1), build_at_code(player, code)};
            if (!legalize_operations(state, player, ops).empty()) {
                plans.push_back(SinglePlan{
                    "base_double_build_C1_" + code_name(code),
                    ops,
                    c1_build_heuristic(C1) + c1_build_heuristic(code),
                });
            }
        }
    }

    for (int code : base_codes()) {
        const Tower *tower = tower_at_code(state, player, code);
        if (tower == nullptr) {
            if (can_build_more && base_build_enabled(code)) {
                const Operation build = build_at_code(player, code);
                if (!legalize_operations(state, player, {build}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_build_" + code_name(code),
                        {build},
                        c1_build_heuristic(code),
                    });
                    for (TowerType target_type : base_build_upgrade_targets(code, c1_sniper_ready, producer_medic_enabled)) {
                        const FollowupAction followup = upgrade_followup(code, target_type);
                        plans.push_back(SinglePlan{
                            "base_build_" + code_name(code) + "_then_" + tower_type_name(target_type),
                            {build},
                            c1_build_heuristic(code) + followup_upgrade_heuristic(followup),
                            followup,
                        });
                        if (target_type == TowerType::Producer) {
                            const FollowupAction medic_followup = producer_medic_followup(code);
                            plans.push_back(SinglePlan{
                                "base_build_" + code_name(code) + "_then_Producer_then_ProducerMedic",
                                {build},
                                c1_build_heuristic(code) + followup_upgrade_heuristic(medic_followup),
                                medic_followup,
                            });
                        }
                    }
                    if (can_build_quick_sniper_chain(code, c1_sniper_ready)) {
                        plans.push_back(SinglePlan{
                            "base_build_" + code_name(code) + "_then_Quick_then_Sniper",
                            {build},
                            c1_build_heuristic(code),
                            quick_sniper_followup(code),
                        });
                    }
                }
            }
            if (can_build_more && !base_build_enabled(code) && can_build_quick_sniper_chain(code, c1_sniper_ready)) {
                const Operation build = build_at_code(player, code);
                if (!legalize_operations(state, player, {build}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_build_" + code_name(code) + "_then_Quick_then_Sniper",
                        {build},
                        c1_build_heuristic(code),
                        quick_sniper_followup(code),
                    });
                }
            }
            continue;
        }
        if (tower->player != player) {
            continue;
        }

        append_downgrade_candidate(state, player, tower, "base_" + code_name(code) + "_downgrade", plans);
        append_base_swap_candidates(state, player, *tower, code, plans);
        if (tower->tower_type != TowerType::Basic) {
            const Operation down(OperationType::DowngradeTower, tower->tower_id);
            if (!legalize_operations(state, player, {down}).empty()) {
                plans.push_back(SinglePlan{
                    "base_" + code_name(code) + "_downgrade_then_downgrade",
                    {down},
                    0.0,
                    downgrade_followup(code),
                });
            }
            if (tower->tower_type == TowerType::Heavy && c1_quick_route_enabled(code) &&
                can_build_quick_sniper_chain(code, c1_sniper_ready)) {
                plans.push_back(SinglePlan{
                    "base_" + code_name(code) + "_downgrade_then_Quick_then_Sniper",
                    {down},
                    0.0,
                    quick_sniper_followup(code),
                });
            }
            if (tower->tower_type == TowerType::Sniper && sniper_route_allowed(code, c1_sniper_ready)) {
                plans.push_back(SinglePlan{
                    "base_" + code_name(code) + "_refresh_Sniper",
                    {down},
                    0.0,
                    upgrade_followup(code, TowerType::Sniper),
                });
            }
        }

        if (tower->tower_type == TowerType::Basic) {
            for (TowerType target_type : base_existing_upgrade_targets(code, c1_sniper_ready, producer_medic_enabled)) {
                const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(target_type));
                if (!legalize_operations(state, player, {upgrade}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_" + code_name(code) + "_to_" + tower_type_name(target_type),
                        {upgrade},
                        producer_medic_upgrade_heuristic(target_type),
                    });
                    if (target_type == TowerType::Producer) {
                        const FollowupAction medic_followup = upgrade_followup(code, TowerType::ProducerMedic);
                        plans.push_back(SinglePlan{
                            "base_" + code_name(code) + "_to_Producer_then_ProducerMedic",
                            {upgrade},
                            producer_medic_upgrade_heuristic(target_type) + followup_upgrade_heuristic(medic_followup),
                            medic_followup,
                        });
                    }
                    if (target_type == TowerType::Quick && sniper_route_allowed(code, c1_sniper_ready)) {
                        plans.push_back(SinglePlan{
                            "base_" + code_name(code) + "_to_Quick_then_Sniper",
                            {upgrade},
                            0.0,
                            upgrade_followup(code, TowerType::Sniper),
                        });
                    }
                }
            }
            if (can_build_quick_sniper_chain(code, c1_sniper_ready)) {
                const Operation quick(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Quick));
                if (!legalize_operations(state, player, {quick}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_" + code_name(code) + "_to_Quick_then_Sniper",
                        {quick},
                        0.0,
                        upgrade_followup(code, TowerType::Sniper),
                    });
                }
            }
        } else if (tower->tower_type == TowerType::Quick) {
            const Operation sniper(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Sniper));
            if (sniper_route_allowed(code, c1_sniper_ready) && !legalize_operations(state, player, {sniper}).empty()) {
                plans.push_back(SinglePlan{"base_" + code_name(code) + "_to_Sniper", {sniper}, 0.0});
            }
        } else if (tower->tower_type == TowerType::Producer && producer_medic_enabled) {
            const Operation medic(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::ProducerMedic));
            if (!legalize_operations(state, player, {medic}).empty()) {
                plans.push_back(SinglePlan{
                    "base_" + code_name(code) + "_to_ProducerMedic",
                    {medic},
                    producer_medic_upgrade_heuristic(TowerType::ProducerMedic),
                });
            }
        }
    }

    return plans;
}

inline std::vector<SinglePlan> generate_base_candidates(const rs::DefenseSimulator &simulator, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"base_hold", {}, 0.0});

    const int base_tower_count = non_lure_tower_count(simulator, player);
    const bool can_build_more = base_tower_count < non_lure_tower_build_limit(simulator);
    const bool c1_sniper_ready = c1_has_sniper(simulator, player);
    const bool producer_medic_enabled = producer_medic_branch_enabled(simulator, player);

    if (base_tower_count == 0 && tower_at_code(simulator, player, C1) == nullptr) {
        for (int code : base_codes()) {
            if (code == C1 || !base_build_enabled(code) || tower_at_code(simulator, player, code) != nullptr) {
                continue;
            }
            std::vector<Operation> ops{build_at_code(player, C1), build_at_code(player, code)};
            if (!legalize_operations(simulator, ops).empty()) {
                plans.push_back(SinglePlan{
                    "base_double_build_C1_" + code_name(code),
                    ops,
                    c1_build_heuristic(C1) + c1_build_heuristic(code),
                });
            }
        }
    }

    for (int code : base_codes()) {
        const rs::SearchTower *tower = tower_at_code(simulator, player, code);
        if (tower == nullptr) {
            if (can_build_more && base_build_enabled(code)) {
                const Operation build = build_at_code(player, code);
                if (!legalize_operations(simulator, {build}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_build_" + code_name(code),
                        {build},
                        c1_build_heuristic(code),
                    });
                    for (TowerType target_type : base_build_upgrade_targets(code, c1_sniper_ready, producer_medic_enabled)) {
                        const FollowupAction followup = upgrade_followup(code, target_type);
                        plans.push_back(SinglePlan{
                            "base_build_" + code_name(code) + "_then_" + tower_type_name(target_type),
                            {build},
                            c1_build_heuristic(code) + followup_upgrade_heuristic(followup),
                            followup,
                        });
                        if (target_type == TowerType::Producer) {
                            const FollowupAction medic_followup = producer_medic_followup(code);
                            plans.push_back(SinglePlan{
                                "base_build_" + code_name(code) + "_then_Producer_then_ProducerMedic",
                                {build},
                                c1_build_heuristic(code) + followup_upgrade_heuristic(medic_followup),
                                medic_followup,
                            });
                        }
                    }
                    if (can_build_quick_sniper_chain(code, c1_sniper_ready)) {
                        plans.push_back(SinglePlan{
                            "base_build_" + code_name(code) + "_then_Quick_then_Sniper",
                            {build},
                            c1_build_heuristic(code),
                            quick_sniper_followup(code),
                        });
                    }
                }
            }
            if (can_build_more && !base_build_enabled(code) && can_build_quick_sniper_chain(code, c1_sniper_ready)) {
                const Operation build = build_at_code(player, code);
                if (!legalize_operations(simulator, {build}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_build_" + code_name(code) + "_then_Quick_then_Sniper",
                        {build},
                        c1_build_heuristic(code),
                        quick_sniper_followup(code),
                    });
                }
            }
            continue;
        }

        append_downgrade_candidate(simulator, player, tower, "base_" + code_name(code) + "_downgrade", plans);
        append_base_swap_candidates(simulator, player, *tower, code, plans);
        if (tower->tower_type != TowerType::Basic) {
            const Operation down(OperationType::DowngradeTower, tower->tower_id);
            if (!legalize_operations(simulator, {down}).empty()) {
                plans.push_back(SinglePlan{
                    "base_" + code_name(code) + "_downgrade_then_downgrade",
                    {down},
                    0.0,
                    downgrade_followup(code),
                });
            }
            if (tower->tower_type == TowerType::Heavy && c1_quick_route_enabled(code) &&
                can_build_quick_sniper_chain(code, c1_sniper_ready)) {
                plans.push_back(SinglePlan{
                    "base_" + code_name(code) + "_downgrade_then_Quick_then_Sniper",
                    {down},
                    0.0,
                    quick_sniper_followup(code),
                });
            }
            if (tower->tower_type == TowerType::Sniper && sniper_route_allowed(code, c1_sniper_ready)) {
                plans.push_back(SinglePlan{
                    "base_" + code_name(code) + "_refresh_Sniper",
                    {down},
                    0.0,
                    upgrade_followup(code, TowerType::Sniper),
                });
            }
        }

        if (tower->tower_type == TowerType::Basic) {
            for (TowerType target_type : base_existing_upgrade_targets(code, c1_sniper_ready, producer_medic_enabled)) {
                const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(target_type));
                if (!legalize_operations(simulator, {upgrade}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_" + code_name(code) + "_to_" + tower_type_name(target_type),
                        {upgrade},
                        producer_medic_upgrade_heuristic(target_type),
                    });
                    if (target_type == TowerType::Producer) {
                        const FollowupAction medic_followup = upgrade_followup(code, TowerType::ProducerMedic);
                        plans.push_back(SinglePlan{
                            "base_" + code_name(code) + "_to_Producer_then_ProducerMedic",
                            {upgrade},
                            producer_medic_upgrade_heuristic(target_type) + followup_upgrade_heuristic(medic_followup),
                            medic_followup,
                        });
                    }
                    if (target_type == TowerType::Quick && sniper_route_allowed(code, c1_sniper_ready)) {
                        plans.push_back(SinglePlan{
                            "base_" + code_name(code) + "_to_Quick_then_Sniper",
                            {upgrade},
                            0.0,
                            upgrade_followup(code, TowerType::Sniper),
                        });
                    }
                }
            }
            if (can_build_quick_sniper_chain(code, c1_sniper_ready)) {
                const Operation quick(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Quick));
                if (!legalize_operations(simulator, {quick}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_" + code_name(code) + "_to_Quick_then_Sniper",
                        {quick},
                        0.0,
                        upgrade_followup(code, TowerType::Sniper),
                    });
                }
            }
        } else if (tower->tower_type == TowerType::Quick) {
            const Operation sniper(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Sniper));
            if (sniper_route_allowed(code, c1_sniper_ready) && !legalize_operations(simulator, {sniper}).empty()) {
                plans.push_back(SinglePlan{"base_" + code_name(code) + "_to_Sniper", {sniper}, 0.0});
            }
        } else if (tower->tower_type == TowerType::Producer && producer_medic_enabled) {
            const Operation medic(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::ProducerMedic));
            if (!legalize_operations(simulator, {medic}).empty()) {
                plans.push_back(SinglePlan{
                    "base_" + code_name(code) + "_to_ProducerMedic",
                    {medic},
                    producer_medic_upgrade_heuristic(TowerType::ProducerMedic),
                });
            }
        }
    }

    return plans;
}

} // namespace antgame::sdk::lure_strategy_detail
