#pragma once

#include <algorithm>
#include <cmath>
#include <vector>

#include "antgame_ai/lure_strategy_v4_core_ops.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline double tower_salvage_value(const PublicState &state, const Tower &tower, int tower_count_hint) {
    if (tower.tower_type == TowerType::Basic) {
        return static_cast<double>(state.destroy_tower_income(tower_count_hint, &tower));
    }
    return static_cast<double>(state.downgrade_tower_income(tower.tower_type, &tower));
}

inline double tower_salvage_value(const rs::SearchTower &tower, int tower_count_hint) {
    return rs::tower_estimated_salvage_value(tower, tower_count_hint);
}

inline double downgrade_operation_refund(const PublicState &state, int player, const Operation &operation) {
    if (operation.op_type != OperationType::DowngradeTower) {
        return 0.0;
    }
    const int refund = state.operation_income(player, operation);
    return refund > 0 ? static_cast<double>(refund) : 0.0;
}

inline double downgrade_operation_refund(const rs::DefenseSimulator &simulator, const Operation &operation) {
    if (operation.op_type != OperationType::DowngradeTower) {
        return 0.0;
    }
    const rs::SearchTower *tower = simulator.tower_by_id(operation.arg0);
    if (tower == nullptr || !tower->alive()) {
        return 0.0;
    }
    return tower_salvage_value(*tower, static_cast<int>(simulator.towers.size()));
}

inline double downgrade_refund_penalty(double refund) {
    return refund * v4_lure_config().downgrade_refund_penalty_scale;
}

inline bool non_lure_tower_has_adjacent_combat(
    const PublicState &state,
    int player,
    const Tower &tower) {
    if (tower.player != player || is_lure_slot_code(code_at(tower, player))) {
        return false;
    }
    for (const auto &ant : state.ants) {
        if (ant.player == player || ant.kind != AntKind::Combat || !ant.is_alive()) {
            continue;
        }
        if (hex_distance(tower.x, tower.y, ant.x, ant.y) <= 1) {
            return true;
        }
    }
    return false;
}

inline bool non_lure_tower_has_adjacent_combat(
    const rs::DefenseSimulator &simulator,
    int player,
    const rs::SearchTower &tower) {
    if (!tower.alive() || is_lure_slot_code(code_at(tower, player))) {
        return false;
    }
    for (const auto &ant : simulator.ants) {
        if (ant.kind != AntKind::Combat || !ant.alive()) {
            continue;
        }
        if (hex_distance(tower.x, tower.y, ant.x, ant.y) <= 1) {
            return true;
        }
    }
    return false;
}

inline double downgrade_operation_penalty(const PublicState &state, int player, const Operation &operation) {
    if (operation.op_type != OperationType::DowngradeTower) {
        return 0.0;
    }
    const Tower *tower = state.tower_by_id(operation.arg0);
    double penalty = downgrade_refund_penalty(downgrade_operation_refund(state, player, operation));
    if (tower != nullptr && tower->tower_type == TowerType::Sniper) {
        penalty += v4_lure_config().sniper_downgrade_penalty;
    }
    if (tower != nullptr && non_lure_tower_has_adjacent_combat(state, player, *tower)) {
        penalty -= v4_lure_config().non_lure_adjacent_combat_downgrade_bonus;
    }
    return penalty;
}

inline double downgrade_operation_penalty(const rs::DefenseSimulator &simulator, int player, const Operation &operation) {
    if (operation.op_type != OperationType::DowngradeTower) {
        return 0.0;
    }
    const rs::SearchTower *tower = simulator.tower_by_id(operation.arg0);
    double penalty = downgrade_refund_penalty(downgrade_operation_refund(simulator, operation));
    if (tower != nullptr && tower->alive() && tower->tower_type == TowerType::Sniper) {
        penalty += v4_lure_config().sniper_downgrade_penalty;
    }
    if (tower != nullptr && non_lure_tower_has_adjacent_combat(simulator, player, *tower)) {
        penalty -= v4_lure_config().non_lure_adjacent_combat_downgrade_bonus;
    }
    return penalty;
}

inline double downgrade_penalty_for_ops(
    const PublicState &state,
    int player,
    const std::vector<Operation> &operations) {
    double penalty = 0.0;
    PublicState scratch = state.clone();
    std::vector<int> used_towers;
    bool base_upgraded = false;
    for (const auto &operation : sort_operations(state, operations)) {
        const int built_tower_id = scratch.next_tower_id;
        if (!scratch.can_apply_operation_sequential(player, operation, used_towers, base_upgraded)) {
            return penalty;
        }
        penalty += downgrade_operation_penalty(scratch, player, operation);
        scratch.apply_operation(player, operation);
        scratch.record_operation_turn_usage(operation, built_tower_id, used_towers, base_upgraded);
    }
    return penalty;
}

inline double downgrade_penalty_for_ops(
    const rs::DefenseSimulator &simulator,
    int player,
    const std::vector<Operation> &operations) {
    double penalty = 0.0;
    rs::DefenseSimulator scratch = simulator.clone();
    for (const auto &operation : sort_operations(simulator, operations)) {
        if (!scratch.can_apply_operation(operation)) {
            return penalty;
        }
        penalty += downgrade_operation_penalty(scratch, player, operation);
        scratch.apply_operation(operation);
    }
    return penalty;
}

inline double tower_full_salvage_value(const PublicState &state, int player) {
    struct BasicRefund {
        int hp = 0;
    };

    std::vector<Tower> owned;
    owned.reserve(state.towers.size());
    for (const auto &tower : state.towers) {
        if (tower.player == player) {
            owned.push_back(tower);
        }
    }
    double total = 0.0;
    std::vector<BasicRefund> basics;
    basics.reserve(owned.size());
    for (const auto &tower : owned) {
        Tower current = tower;
        while (current.tower_type != TowerType::Basic) {
            total += static_cast<double>(state.downgrade_tower_income(current.tower_type, &current));
            const int prev_max_hp = current.max_hp();
            current.tower_type = static_cast<TowerType>(static_cast<int>(current.tower_type) / 10);
            const int next_max_hp = current.max_hp();
            current.hp = prev_max_hp > 0 ? std::max(1, (next_max_hp * std::max(current.hp, 0) + prev_max_hp - 1) / prev_max_hp)
                                         : next_max_hp;
        }
        basics.push_back(BasicRefund{std::max(current.hp, 0)});
    }

    std::sort(basics.begin(), basics.end(), [](const BasicRefund &lhs, const BasicRefund &rhs) { return lhs.hp > rhs.hp; });
    int tower_count = static_cast<int>(basics.size());
    for (const auto &basic : basics) {
        Tower basic_tower;
        basic_tower.tower_type = TowerType::Basic;
        basic_tower.hp = basic.hp;
        total += static_cast<double>(state.destroy_tower_income(tower_count, &basic_tower));
        --tower_count;
    }
    return total;
}

inline double tower_full_salvage_value(const rs::DefenseSimulator &simulator) {
    return rs::tower_full_salvage_value(simulator.towers);
}

inline int alive_tower_count(const rs::DefenseSimulator &simulator) {
    int count = 0;
    for (const auto &tower : simulator.towers) {
        if (tower.alive()) {
            ++count;
        }
    }
    return count;
}

inline double behavior_threat_scale(AntBehavior behavior) {
    if (behavior == AntBehavior::Random) {
        return v4_lure_config().randomized_threat_scale;
    }
    if (behavior == AntBehavior::Bewitched) {
        return v4_lure_config().bewitched_threat_scale;
    }
    return 1.0;
}

} // namespace antgame::sdk::lure_strategy_detail
