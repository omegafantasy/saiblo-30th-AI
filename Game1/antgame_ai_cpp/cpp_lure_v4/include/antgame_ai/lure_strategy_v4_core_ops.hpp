#pragma once

#include <algorithm>
#include <sstream>
#include <string>
#include <vector>

#include "antgame_ai/lure_strategy_v4_core_format.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline int op_priority(OperationType type) {
    switch (type) {
    case OperationType::DowngradeTower:
        return 0;
    case OperationType::UseLightningStorm:
    case OperationType::UseEmpBlaster:
    case OperationType::UseDeflector:
    case OperationType::UseEmergencyEvasion:
        return 1;
    case OperationType::BuildTower:
        return 2;
    case OperationType::UpgradeTower:
        return 3;
    case OperationType::UpgradeGenerationSpeed:
    case OperationType::UpgradeGeneratedAnt:
        return 4;
    }
    return 5;
}

inline int downgrade_hp(const PublicState &state, const Operation &operation) {
    if (operation.op_type != OperationType::DowngradeTower) {
        return -1;
    }
    const Tower *tower = find_tower_by_id(state, operation.arg0);
    return tower != nullptr ? tower->hp : -1;
}

inline int downgrade_hp(const rs::DefenseSimulator &simulator, const Operation &operation) {
    if (operation.op_type != OperationType::DowngradeTower) {
        return -1;
    }
    const rs::SearchTower *tower = find_tower_by_id(simulator, operation.arg0);
    return tower != nullptr ? tower->hp : -1;
}

inline std::vector<Operation> sort_operations(const PublicState &state, std::vector<Operation> operations) {
    std::stable_sort(operations.begin(), operations.end(), [&state](const Operation &lhs, const Operation &rhs) {
        const int lp = op_priority(lhs.op_type);
        const int rp = op_priority(rhs.op_type);
        if (lp != rp) {
            return lp < rp;
        }
        if (lhs.op_type == OperationType::DowngradeTower && rhs.op_type == OperationType::DowngradeTower) {
            const int lhp = downgrade_hp(state, lhs);
            const int rhp = downgrade_hp(state, rhs);
            if (lhp != rhp) {
                return lhp > rhp;
            }
        }
        if (lhs.arg0 != rhs.arg0) {
            return lhs.arg0 < rhs.arg0;
        }
        return lhs.arg1 < rhs.arg1;
    });
    return operations;
}

inline std::vector<Operation> sort_operations(const rs::DefenseSimulator &simulator, std::vector<Operation> operations) {
    std::stable_sort(operations.begin(), operations.end(), [&simulator](const Operation &lhs, const Operation &rhs) {
        const int lp = op_priority(lhs.op_type);
        const int rp = op_priority(rhs.op_type);
        if (lp != rp) {
            return lp < rp;
        }
        if (lhs.op_type == OperationType::DowngradeTower && rhs.op_type == OperationType::DowngradeTower) {
            const int lhp = downgrade_hp(simulator, lhs);
            const int rhp = downgrade_hp(simulator, rhs);
            if (lhp != rhp) {
                return lhp > rhp;
            }
        }
        if (lhs.arg0 != rhs.arg0) {
            return lhs.arg0 < rhs.arg0;
        }
        return lhs.arg1 < rhs.arg1;
    });
    return operations;
}

inline std::string join_plan_key(const std::vector<Operation> &operations) {
    if (operations.empty()) {
        return "hold";
    }
    std::ostringstream oss;
    for (std::size_t index = 0; index < operations.size(); ++index) {
        if (index) {
            oss << '|';
        }
        oss << op_key(operations[index]);
    }
    return oss.str();
}

inline std::vector<Operation> legalize_operations(const PublicState &state, int player, const std::vector<Operation> &operations) {
    PublicState scratch = state.clone();
    const std::vector<Operation> ordered = sort_operations(state, operations);
    std::vector<int> used_towers;
    bool base_upgraded = false;
    for (const auto &operation : ordered) {
        const int built_tower_id = scratch.next_tower_id;
        if (!scratch.can_apply_operation_sequential(player, operation, used_towers, base_upgraded)) {
            return {};
        }
        scratch.apply_operation(player, operation);
        scratch.record_operation_turn_usage(operation, built_tower_id, used_towers, base_upgraded);
    }
    return ordered;
}

inline std::vector<Operation> legalize_operations(const rs::DefenseSimulator &simulator, const std::vector<Operation> &operations) {
    rs::DefenseSimulator scratch = simulator.clone();
    const std::vector<Operation> ordered = sort_operations(simulator, operations);
    for (const auto &operation : ordered) {
        if (!scratch.apply_operation(operation)) {
            return {};
        }
    }
    return ordered;
}

} // namespace antgame::sdk::lure_strategy_detail
