#pragma once

#include <array>
#include <chrono>
#include <cstdlib>
#include <initializer_list>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "antgame_ai/lure_strategy_v4_params.hpp"
#include "antgame_ai/lure_strategy_v4_session.hpp"

namespace antgame::sdk::lure_strategy_detail {

namespace rs = ::antgame::sdk::random_search_detail;

enum class DebugMode : int {
    None = 0,
    Summary = 1,
    Plans = 2,
};

inline DebugMode debug_mode() {
    static const DebugMode mode = []() {
        const char *value = std::getenv("ANTGAME_CPP_BASELINE_DEBUG");
        if (value == nullptr || *value == '\0') {
            return DebugMode::None;
        }
        const std::string text(value);
        if (text == "0" || text == "off" || text == "false") {
            return DebugMode::None;
        }
        if (text == "1" || text == "summary") {
            return DebugMode::Summary;
        }
        return DebugMode::Plans;
    }();
    return mode;
}

inline std::uint64_t mix_seed(std::uint64_t seed, std::uint64_t value) {
    std::uint64_t mixed = seed + 0x9e3779b97f4a7c15ULL + (value << 1U);
    mixed = (mixed ^ (mixed >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    mixed = (mixed ^ (mixed >> 27U)) * 0x94d049bb133111ebULL;
    return mixed ^ (mixed >> 31U);
}

inline std::uint64_t plan_rollout_seed(
    std::uint64_t state_seed,
    std::uint64_t serial,
    std::size_t root_index,
    int rollout,
    int horizon) {
    return mix_seed(
        state_seed,
        mix_seed(
            serial,
            static_cast<std::uint64_t>((static_cast<int>(root_index) + 1) * 131 + rollout * 977 + horizon * 17)));
}

inline std::uint64_t plan_rollout_assignment_seed(
    std::uint64_t state_seed,
    std::uint64_t serial,
    std::size_t root_index,
    int horizon,
    int rollout_count) {
    return mix_seed(
        state_seed,
        mix_seed(
            serial,
            static_cast<std::uint64_t>(0x5f3759dfU + (static_cast<int>(root_index) + 1) * 719 + horizon * 43 +
                                       rollout_count * 97)));
}

inline std::string debug_json_escape(const std::string &text) {
    std::ostringstream oss;
    for (char ch : text) {
        switch (ch) {
        case '\\':
            oss << "\\\\";
            break;
        case '"':
            oss << "\\\"";
            break;
        case '\n':
            oss << "\\n";
            break;
        case '\r':
            oss << "\\r";
            break;
        case '\t':
            oss << "\\t";
            break;
        default:
            oss << ch;
            break;
        }
    }
    return oss.str();
}

inline std::string op_key(const Operation &operation) {
    std::ostringstream oss;
    oss << static_cast<int>(operation.op_type) << ':' << operation.arg0 << ':' << operation.arg1;
    return oss.str();
}

inline std::string op_text(const Operation &operation) {
    std::ostringstream oss;
    oss << static_cast<int>(operation.op_type);
    if (operation.op_type == OperationType::BuildTower || is_weapon_operation(operation.op_type) ||
        operation.op_type == OperationType::UpgradeTower) {
        oss << ' ' << operation.arg0 << ' ' << operation.arg1;
    } else if (operation.op_type == OperationType::DowngradeTower) {
        oss << ' ' << operation.arg0;
    }
    return oss.str();
}

inline std::string ops_text(const std::vector<Operation> &operations) {
    if (operations.empty()) {
        return "";
    }
    std::ostringstream oss;
    for (std::size_t index = 0; index < operations.size(); ++index) {
        if (index) {
            oss << ';';
        }
        oss << op_text(operations[index]);
    }
    return oss.str();
}

inline std::string enemy_ant_state_text(const PublicState &state, int player) {
    std::ostringstream oss;
    bool first = true;
    for (const auto &ant : state.ants) {
        if (ant.player == player || !ant.is_alive()) {
            continue;
        }
        if (!first) {
            oss << ';';
        }
        first = false;
        oss << ant.ant_id << ':' << ant.x << ',' << ant.y << ':' << ant.hp << ':' << static_cast<int>(ant.kind) << ':'
            << ant.last_move << ':' << ant.age << ':' << static_cast<int>(ant.behavior);
    }
    return oss.str();
}

inline std::string own_tower_state_text(const PublicState &state, int player) {
    std::ostringstream oss;
    bool first = true;
    for (const auto &tower : state.towers) {
        if (tower.player != player) {
            continue;
        }
        if (!first) {
            oss << ';';
        }
        first = false;
        oss << tower.tower_id << ':' << tower.x << ',' << tower.y << ':' << static_cast<int>(tower.tower_type) << ':'
            << tower.hp << ':' << tower.cooldown;
    }
    return oss.str();
}

inline std::string sim_enemy_ant_state_text(const rs::DefenseSimulator &simulator) {
    std::ostringstream oss;
    const auto [base_x, base_y] = kPlayerBases[simulator.player];
    bool first = true;
    for (const auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || (ant.x == base_x && ant.y == base_y)) {
            continue;
        }
        if (!first) {
            oss << ';';
        }
        first = false;
        oss << ant.ant_id << ':' << ant.x << ',' << ant.y << ':' << ant.hp << ':' << static_cast<int>(ant.kind) << ':'
            << ant.last_move << ':' << ant.age << ':' << static_cast<int>(ant.behavior);
    }
    return oss.str();
}

inline const Tower *find_tower_by_id(const PublicState &state, int tower_id) {
    for (const auto &tower : state.towers) {
        if (tower.tower_id == tower_id) {
            return &tower;
        }
    }
    return nullptr;
}

inline const rs::SearchTower *find_tower_by_id(const rs::DefenseSimulator &simulator, int tower_id) {
    return simulator.tower_by_id(tower_id);
}

inline std::string slot_label_or_coord(int player, int x, int y) {
    const int code = old_ai_position_code_at(player, x, y);
    if (code >= 0) {
        return position_code_name(code);
    }
    std::ostringstream oss;
    oss << "P(" << x << ',' << y << ')';
    return oss.str();
}

inline int action_number(const Operation &operation) {
    switch (operation.op_type) {
    case OperationType::BuildTower:
        return 1;
    case OperationType::UpgradeTower:
        switch (static_cast<TowerType>(operation.arg1)) {
        case TowerType::Heavy:
            return 2;
        case TowerType::Quick:
            return 3;
        case TowerType::Sniper:
            return 4;
        case TowerType::Pulse:
            return 7;
        case TowerType::Mortar:
        case TowerType::MortarPlus:
            return 8;
        case TowerType::Bewitch:
            return 9;
        default:
            return 10;
        }
    case OperationType::DowngradeTower:
        return 5;
    case OperationType::UseLightningStorm:
        return 6;
    default:
        return 99;
    }
}

inline std::string pretty_op_text(const PublicState &state, int player, const Operation &operation) {
    if (operation.op_type == OperationType::BuildTower || operation.op_type == OperationType::UseLightningStorm) {
        std::ostringstream oss;
        oss << slot_label_or_coord(player, operation.arg0, operation.arg1) << '-' << action_number(operation);
        return oss.str();
    }
    if (operation.op_type == OperationType::UpgradeTower || operation.op_type == OperationType::DowngradeTower) {
        const Tower *tower = find_tower_by_id(state, operation.arg0);
        std::ostringstream oss;
        if (tower != nullptr) {
            oss << slot_label_or_coord(player, tower->x, tower->y);
        } else {
            oss << "T#" << operation.arg0;
        }
        oss << '-' << action_number(operation);
        return oss.str();
    }
    return op_text(operation);
}

inline std::string pretty_ops_text(const PublicState &state, int player, const std::vector<Operation> &operations) {
    if (operations.empty()) {
        return "HOLD-0";
    }
    std::ostringstream oss;
    std::unordered_map<int, std::pair<int, int>> built_towers;
    int next_tower_id = state.next_tower_id;
    for (std::size_t index = 0; index < operations.size(); ++index) {
        if (index) {
            oss << ';';
        }
        const Operation &operation = operations[index];
        if (operation.op_type == OperationType::UpgradeTower || operation.op_type == OperationType::DowngradeTower) {
            const Tower *tower = find_tower_by_id(state, operation.arg0);
            const auto built_it = built_towers.find(operation.arg0);
            if (tower == nullptr && built_it != built_towers.end()) {
                oss << slot_label_or_coord(player, built_it->second.first, built_it->second.second) << '-'
                    << action_number(operation);
            } else {
                oss << pretty_op_text(state, player, operation);
            }
        } else {
            oss << pretty_op_text(state, player, operation);
        }
        if (operation.op_type == OperationType::BuildTower) {
            built_towers.emplace(next_tower_id++, std::pair<int, int>{operation.arg0, operation.arg1});
        }
    }
    return oss.str();
}

inline const char *action_legend_text() {
    return "0=hold,1=build,2=heavy,3=quick,4=sniper,5=sell,6=lightning,7=pulse,8=mortar,9=bewitch,10=other_upgrade";
}

inline std::string tower_type_name(TowerType type) {
    switch (type) {
    case TowerType::Basic:
        return "Basic";
    case TowerType::Heavy:
        return "Heavy";
    case TowerType::Quick:
        return "Quick";
    case TowerType::Mortar:
        return "Mortar";
    case TowerType::Producer:
        return "Producer";
    case TowerType::HeavyPlus:
        return "HeavyPlus";
    case TowerType::Ice:
        return "Ice";
    case TowerType::Bewitch:
        return "Bewitch";
    case TowerType::QuickPlus:
        return "QuickPlus";
    case TowerType::Double:
        return "Double";
    case TowerType::Sniper:
        return "Sniper";
    case TowerType::MortarPlus:
        return "MortarPlus";
    case TowerType::Pulse:
        return "Pulse";
    case TowerType::Missile:
        return "Missile";
    case TowerType::ProducerFast:
        return "ProducerFast";
    case TowerType::ProducerSiege:
        return "ProducerSiege";
    case TowerType::ProducerMedic:
        return "ProducerMedic";
    }
    return "Tower";
}

inline const Tower *tower_at_code(const PublicState &state, int player, int code) {
    const auto [x, y] = old_ai_position(player, code);
    return state.tower_at(x, y);
}

inline const rs::SearchTower *tower_at_code(const rs::DefenseSimulator &sim, int player, int code) {
    const auto [x, y] = old_ai_position(player, code);
    return sim.tower_at(x, y);
}

inline int code_at(const Tower &tower, int player) {
    return old_ai_position_code_at(player, tower.x, tower.y);
}

inline int code_at(const rs::SearchTower &tower, int player) {
    return old_ai_position_code_at(player, tower.x, tower.y);
}

inline bool is_base_slot_code(int code) {
    switch (code) {
    case C1:
    case C2:
    case C3:
    case L1:
    case L2:
    case L3:
    case R1:
    case R2:
    case R3:
    case LL1:
    case LL2:
    case LL3:
    case RR1:
    case RR2:
    case RR3:
        return true;
    default:
        return false;
    }
}

inline bool is_lure_slot_code(int code) {
    switch (code) {
    case M2:
    case M3:
    case ML1:
    case ML2:
    case M1:
    case M4:
    case MR2:
    case MR1:
    case FL1:
    case FL2:
    case FR2:
    case FR1:
    case FL3:
    case F2:
    case F3:
    case FR3:
    case F1:
    case F4:
        return true;
    default:
        return false;
    }
}

inline std::array<int, 15> base_codes() {
    return {C1, C2, C3, L1, L2, L3, R1, R2, R3, LL1, LL2, LL3, RR1, RR2, RR3};
}

inline std::array<int, 18> lure_codes() {
    return {M2,  M3,  ML1, ML2, M1,  M4,  MR2, MR1, FL1,
            FL2, FR2, FR1, FL3, F2,  F3,  FR3, F1,  F4};
}

inline Operation build_at_code(int player, int code) {
    const auto [x, y] = old_ai_position(player, code);
    return Operation(OperationType::BuildTower, x, y);
}

} // namespace antgame::sdk::lure_strategy_detail
