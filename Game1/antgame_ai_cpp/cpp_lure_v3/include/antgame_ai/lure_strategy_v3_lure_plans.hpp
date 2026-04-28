#pragma once

#include "antgame_ai/lure_strategy_v3_base_plans.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline std::vector<SinglePlan> generate_lure_candidates(const PublicState &state, const rs::DefenseSimulator *simulator, int player) {
    const Tower *forced = forced_lure_sell_target(state, player);
    if (forced != nullptr) {
        std::vector<SinglePlan> plans;
        const int from_code = code_at(*forced, player);
        const Operation sell(OperationType::DowngradeTower, forced->tower_id);
        const auto sell_ops = legalize_operations(state, player, {sell});
        if (!sell_ops.empty()) {
            plans.push_back(SinglePlan{
                "lure_forced_sell_" + code_name(from_code),
                sell_ops,
                0.0,
            });
        }
        for (int code : lure_codes()) {
            if (code == from_code) {
                continue;
            }
            const Operation build = build_at_code(player, code);
            const auto ops = legalize_operations(state, player, {sell, build});
            if (ops.size() != 2) {
                continue;
            }
            plans.push_back(SinglePlan{
                "lure_forced_relocate_" + code_name(from_code) + "_to_" + code_name(code),
                ops,
                0.0,
            });
        }
        return plans;
    }

    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"lure_hold", {}, 0.0});

    std::vector<const Tower *> lure_towers;
    static_cast<void>(simulator);
    for (const auto &tower : state.towers) {
        if (tower.player == player && is_lure_slot_code(code_at(tower, player))) {
            lure_towers.push_back(&tower);
            plans.push_back(SinglePlan{
                "lure_sell_" + code_name(code_at(tower, player)),
                {Operation(OperationType::DowngradeTower, tower.tower_id)},
                0.0,
            });
        }
    }

    if (lure_towers.empty()) {
        for (int code : lure_codes()) {
            const Operation build = build_at_code(player, code);
            if (!legalize_operations(state, player, {build}).empty()) {
                plans.push_back(SinglePlan{"lure_build_" + code_name(code), {build}, 0.0});
            }
        }
    }

    for (const auto *tower : lure_towers) {
        const int from_code = code_at(*tower, player);
        for (int code : lure_codes()) {
            if (code == from_code) {
                continue;
            }
            const Operation build = build_at_code(player, code);
            std::vector<Operation> ops = {
                Operation(OperationType::DowngradeTower, tower->tower_id),
                build,
            };
            ops = legalize_operations(state, player, ops);
            if (ops.size() != 2) {
                continue;
            }
            plans.push_back(SinglePlan{
                "lure_relocate_" + code_name(from_code) + "_to_" + code_name(code),
                ops,
                0.0,
            });
        }
    }

    return plans;
}

inline std::vector<SinglePlan> generate_lure_candidates(const rs::DefenseSimulator &simulator, int player) {
    const rs::SearchTower *forced = forced_lure_sell_target(simulator, player);
    if (forced != nullptr) {
        std::vector<SinglePlan> plans;
        const int from_code = code_at(*forced, player);
        const Operation sell(OperationType::DowngradeTower, forced->tower_id);
        const auto sell_ops = legalize_operations(simulator, {sell});
        if (!sell_ops.empty()) {
            plans.push_back(SinglePlan{
                "lure_forced_sell_" + code_name(from_code),
                sell_ops,
                0.0,
            });
        }
        for (int code : lure_codes()) {
            if (code == from_code) {
                continue;
            }
            const Operation build = build_at_code(player, code);
            const auto ops = legalize_operations(simulator, {sell, build});
            if (ops.size() != 2) {
                continue;
            }
            plans.push_back(SinglePlan{
                "lure_forced_relocate_" + code_name(from_code) + "_to_" + code_name(code),
                ops,
                0.0,
            });
        }
        return plans;
    }

    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"lure_hold", {}, 0.0});

    std::vector<const rs::SearchTower *> lure_towers;

    for (const auto &tower : simulator.towers) {
        if (!tower.alive() || !is_lure_slot_code(code_at(tower, player))) {
            continue;
        }
        lure_towers.push_back(&tower);
        plans.push_back(SinglePlan{
            "lure_sell_" + code_name(code_at(tower, player)),
            {Operation(OperationType::DowngradeTower, tower.tower_id)},
            0.0,
        });
    }

    if (lure_towers.empty()) {
        for (int code : lure_codes()) {
            const Operation build = build_at_code(player, code);
            if (!legalize_operations(simulator, {build}).empty()) {
                plans.push_back(SinglePlan{"lure_build_" + code_name(code), {build}, 0.0});
            }
        }
    }

    for (const auto *tower : lure_towers) {
        const int from_code = code_at(*tower, player);
        for (int code : lure_codes()) {
            if (code == from_code) {
                continue;
            }
            const Operation build = build_at_code(player, code);
            std::vector<Operation> ops = {
                Operation(OperationType::DowngradeTower, tower->tower_id),
                build,
            };
            ops = legalize_operations(simulator, ops);
            if (ops.size() != 2) {
                continue;
            }
            plans.push_back(SinglePlan{
                "lure_relocate_" + code_name(from_code) + "_to_" + code_name(code),
                ops,
                0.0,
            });
        }
    }

    return plans;
}

} // namespace antgame::sdk::lure_strategy_detail
