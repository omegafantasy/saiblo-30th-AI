#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <initializer_list>
#include <limits>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "antgame_sdk/lure_strategy_v2_params.hpp"
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/random_search_baseline.hpp"
#include "antgame_sdk/sdk.hpp"

namespace antgame::sdk {

struct LureStrategyDecisionContext {
    const PublicState *state = nullptr;
    const NativeSimulator *simulator = nullptr;
    int player = 0;
    bool opponent_ops_already_applied = false;
};

struct LureStrategySession {
    struct AntPositionMemory {
        int x = -1;
        int y = -1;
    };

    std::array<int, 2> last_round_seen = {-1, -1};
    std::array<std::uint64_t, 2> decision_serial = {0, 0};
    std::array<std::unordered_map<int, AntPositionMemory>, 2> previous_ant_positions{};
    std::array<std::unordered_map<int, int>, 2> inferred_last_moves{};

    static int infer_move_direction(int from_x, int from_y, int to_x, int to_y) {
        if (from_x == to_x && from_y == to_y) {
            return -1;
        }
        for (int direction = 0; direction < 6; ++direction) {
            const int nx = from_x + kOffset[from_y & 1][direction][0];
            const int ny = from_y + kOffset[from_y & 1][direction][1];
            if (nx == to_x && ny == to_y) {
                return direction;
            }
        }
        return -1;
    }

    void observe(const PublicState &state, int player) {
        if (last_round_seen[player] == state.round_index) {
            return;
        }
        last_round_seen[player] = state.round_index;
        ++decision_serial[player];

        std::unordered_map<int, int> current_moves;
        current_moves.reserve(state.ants.size());
        std::unordered_map<int, AntPositionMemory> current_positions;
        current_positions.reserve(state.ants.size());
        const auto &previous = previous_ant_positions[player];
        for (const auto &ant : state.ants) {
            if (!ant.is_alive()) {
                continue;
            }
            int last_move = ant.last_move;
            const auto it = previous.find(ant.ant_id);
            if (it != previous.end()) {
                last_move = infer_move_direction(it->second.x, it->second.y, ant.x, ant.y);
            }
            current_moves[ant.ant_id] = last_move;
            current_positions[ant.ant_id] = AntPositionMemory{ant.x, ant.y};
        }
        inferred_last_moves[player] = std::move(current_moves);
        previous_ant_positions[player] = std::move(current_positions);
    }

    void apply_inferred_last_moves(PublicState &state, int player) const {
        const auto &moves = inferred_last_moves[player];
        for (auto &ant : state.ants) {
            const auto it = moves.find(ant.ant_id);
            if (it != moves.end()) {
                ant.last_move = it->second;
            }
        }
    }
};

namespace lure_strategy_detail {

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
    bool first = true;
    for (const auto &ant : simulator.ants) {
        if (!ant.alive()) {
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

inline PublicState make_state_from_simulator(const NativeSimulator &simulator) {
    PublicState state(simulator.seed(), simulator.movement_policy(), simulator.cold_handle_rule_illegal());
    state.sync_public_round_state(simulator.to_public_round_state());
    state.terminal = simulator.terminal();
    state.winner = simulator.winner();
    state.next_ant_id = simulator.next_ant_id();
    state.next_tower_id = simulator.next_tower_id();
    state.old_count = simulator.old_count();
    state.die_count = simulator.die_count();
    state.super_weapon_usage = simulator.super_weapon_usage();
    state.ai_time = simulator.ai_time();
    return state;
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

inline Operation lightning_at(int x, int y) {
    return Operation(OperationType::UseLightningStorm, x, y);
}

inline std::vector<Operation> legalize_operations(const PublicState &state, int player, const std::vector<Operation> &operations) {
    PublicState scratch = state.clone();
    const std::vector<Operation> ordered = sort_operations(state, operations);
    std::vector<Operation> accepted;
    accepted.reserve(ordered.size());
    for (const auto &operation : ordered) {
        if (!scratch.can_apply_operation(player, operation, accepted)) {
            return {};
        }
        scratch.apply_operation(player, operation);
        accepted.push_back(operation);
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
    return refund * v2_lure_config().downgrade_refund_penalty_scale;
}

inline double downgrade_operation_penalty(const PublicState &state, int player, const Operation &operation) {
    if (operation.op_type != OperationType::DowngradeTower) {
        return 0.0;
    }
    const Tower *tower = state.tower_by_id(operation.arg0);
    double penalty = downgrade_refund_penalty(downgrade_operation_refund(state, player, operation));
    if (tower != nullptr && tower->tower_type == TowerType::Sniper) {
        penalty += v2_lure_config().sniper_downgrade_penalty;
    }
    return penalty;
}

inline double downgrade_operation_penalty(const rs::DefenseSimulator &simulator, const Operation &operation) {
    if (operation.op_type != OperationType::DowngradeTower) {
        return 0.0;
    }
    const rs::SearchTower *tower = simulator.tower_by_id(operation.arg0);
    double penalty = downgrade_refund_penalty(downgrade_operation_refund(simulator, operation));
    if (tower != nullptr && tower->alive() && tower->tower_type == TowerType::Sniper) {
        penalty += v2_lure_config().sniper_downgrade_penalty;
    }
    return penalty;
}

inline double downgrade_penalty_for_ops(
    const PublicState &state,
    int player,
    const std::vector<Operation> &operations) {
    double penalty = 0.0;
    PublicState scratch = state.clone();
    std::vector<Operation> accepted;
    accepted.reserve(operations.size());
    for (const auto &operation : sort_operations(state, operations)) {
        if (!scratch.can_apply_operation(player, operation, accepted)) {
            return penalty;
        }
        penalty += downgrade_operation_penalty(scratch, player, operation);
        scratch.apply_operation(player, operation);
        accepted.push_back(operation);
    }
    return penalty;
}

inline double downgrade_penalty_for_ops(
    const rs::DefenseSimulator &simulator,
    const std::vector<Operation> &operations) {
    double penalty = 0.0;
    rs::DefenseSimulator scratch = simulator.clone();
    for (const auto &operation : sort_operations(simulator, operations)) {
        if (!scratch.can_apply_operation(operation)) {
            return penalty;
        }
        penalty += downgrade_operation_penalty(scratch, operation);
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
        return v2_lure_config().randomized_threat_scale;
    }
    if (behavior == AntBehavior::Bewitched) {
        return v2_lure_config().bewitched_threat_scale;
    }
    return 1.0;
}

enum class FollowupType : int {
    None = 0,
    UpgradeAtCode = 1,
    DowngradeAtCode = 2,
    BuildAtCode = 3,
};

struct FollowupStep {
    FollowupType type = FollowupType::None;
    int code = -1;
    TowerType target = TowerType::Basic;
    int turn = 1;

    bool empty() const {
        return type == FollowupType::None;
    }
};

struct FollowupAction {
    static constexpr int kMaxSteps = 3;

    std::array<FollowupStep, kMaxSteps> steps{};
    int count = 0;

    bool empty() const {
        return count <= 0;
    }

    void push(FollowupStep step) {
        if (step.empty() || count >= kMaxSteps) {
            return;
        }
        steps[static_cast<std::size_t>(count++)] = step;
    }
};

inline FollowupStep upgrade_step(int code, TowerType target, int turn = 1) {
    return FollowupStep{FollowupType::UpgradeAtCode, code, target, turn};
}

inline FollowupStep downgrade_step(int code, int turn = 1) {
    return FollowupStep{FollowupType::DowngradeAtCode, code, TowerType::Basic, turn};
}

inline FollowupStep build_step(int code, int turn = 1) {
    return FollowupStep{FollowupType::BuildAtCode, code, TowerType::Basic, turn};
}

inline FollowupAction followup_sequence(std::initializer_list<FollowupStep> steps) {
    FollowupAction out;
    for (const FollowupStep &step : steps) {
        out.push(step);
    }
    return out;
}

inline FollowupAction upgrade_followup(int code, TowerType target) {
    return followup_sequence({upgrade_step(code, target)});
}

inline FollowupAction downgrade_followup(int code) {
    return followup_sequence({downgrade_step(code)});
}

inline FollowupAction build_followup(int code, bool upgrade_to_heavy) {
    return upgrade_to_heavy ? followup_sequence({build_step(code), upgrade_step(code, TowerType::Heavy)})
                            : followup_sequence({build_step(code)});
}

inline double combat_threat_at(const PublicState &state, int player, const Ant &ant, int x, int y);
inline double combat_threat_at(const rs::DefenseSimulator &simulator, int player, const rs::SearchAnt &ant, int x, int y);

inline bool is_lightning_center_candidate(int x, int y) {
    return is_valid_pos(x, y) &&
           hex_distance(kEdge - 1, kEdge - 1, x, y) <= v2_lure_config().lightning_center_radius;
}

inline int lightning_active_turn(int remaining_duration) {
    return weapon_stats(SuperWeaponType::LightningStorm).duration - remaining_duration + 1;
}

inline bool lightning_tower_strike_turn(int remaining_duration) {
    return lightning_active_turn(remaining_duration) % 5 == 0;
}

inline int lightning_tower_strikes_within_horizon(int horizon) {
    const int duration = weapon_stats(SuperWeaponType::LightningStorm).duration;
    const int capped_horizon = std::max(0, std::min(horizon, duration));
    int strikes = 0;
    for (int step = 0; step < capped_horizon; ++step) {
        if (lightning_tower_strike_turn(duration - step)) {
            ++strikes;
        }
    }
    return strikes;
}

inline bool enemy_super_effect_active(const PublicState &state, int player) {
    const int enemy = 1 - player;
    for (const auto &effect : state.active_effects) {
        if (effect.player != enemy) {
            continue;
        }
        if (effect.weapon_type == SuperWeaponType::EmpBlaster || effect.weapon_type == SuperWeaponType::Deflector ||
            effect.weapon_type == SuperWeaponType::EmergencyEvasion) {
            return true;
        }
    }
    return false;
}

struct SinglePlan {
    SinglePlan() = default;
    SinglePlan(std::string name_, std::vector<Operation> ops_, double heuristic_, FollowupAction followup_ = {})
        : name(std::move(name_)),
          ops(std::move(ops_)),
          heuristic(heuristic_),
          followup(followup_) {}

    std::string name;
    std::vector<Operation> ops;
    double heuristic = 0.0;
    FollowupAction followup;
};

struct CombinedPlan {
    std::string key;
    std::string name;
    std::string base_name;
    std::string lure_name;
    std::string lightning_name;
    std::vector<Operation> ops;
    double heuristic = 0.0;
    double base_heuristic = 0.0;
    double lure_heuristic = 0.0;
    double lightning_heuristic = 0.0;
    double operation_penalty = 0.0;
    double lightning_static_bonus = 0.0;
    bool has_lightning = false;
    int horizon = 0;
    FollowupAction followup;
};

struct RootPlanSet {
    std::vector<CombinedPlan> plans;
    std::vector<SinglePlan> base_candidates;
    std::vector<SinglePlan> lure_candidates;
    std::vector<SinglePlan> lightning_prep_candidates;
    std::vector<SinglePlan> lightning_center_candidates;
    int base_count = 0;
    int lure_count = 0;
    int lightning_count = 0;
    int raw_combo_count = 0;
    int raw_plan_count = 0;
};

struct EvalBreakdown {
    double base_hp_raw = 0.0;
    double base_hp_score = 0.0;
    double tower_value_raw = 0.0;
    double tower_value_score = 0.0;
    double money_raw = 0.0;
    double money_score = 0.0;
    double c1_bonus_raw = 0.0;
    double c1_bonus_score = 0.0;
    double worker_threat_raw = 0.0;
    double worker_threat_score = 0.0;
    double combat_threat_raw = 0.0;
    double combat_threat_score = 0.0;
    double total_score = 0.0;

    EvalBreakdown &operator+=(const EvalBreakdown &other) {
        base_hp_raw += other.base_hp_raw;
        base_hp_score += other.base_hp_score;
        tower_value_raw += other.tower_value_raw;
        tower_value_score += other.tower_value_score;
        money_raw += other.money_raw;
        money_score += other.money_score;
        c1_bonus_raw += other.c1_bonus_raw;
        c1_bonus_score += other.c1_bonus_score;
        worker_threat_raw += other.worker_threat_raw;
        worker_threat_score += other.worker_threat_score;
        combat_threat_raw += other.combat_threat_raw;
        combat_threat_score += other.combat_threat_score;
        total_score += other.total_score;
        return *this;
    }

    EvalBreakdown scaled(double factor) const {
        EvalBreakdown out = *this;
        out.base_hp_raw *= factor;
        out.base_hp_score *= factor;
        out.tower_value_raw *= factor;
        out.tower_value_score *= factor;
        out.money_raw *= factor;
        out.money_score *= factor;
        out.c1_bonus_raw *= factor;
        out.c1_bonus_score *= factor;
        out.worker_threat_raw *= factor;
        out.worker_threat_score *= factor;
        out.combat_threat_raw *= factor;
        out.combat_threat_score *= factor;
        out.total_score *= factor;
        return out;
    }
};

struct RolloutEvaluation {
    EvalBreakdown terminal;
    double lightning_bonus_raw = 0.0;
    double lightning_bonus_score = 0.0;
    double reactive_operation_penalty = 0.0;
    double total_score = 0.0;

    RolloutEvaluation &operator+=(const RolloutEvaluation &other) {
        terminal += other.terminal;
        lightning_bonus_raw += other.lightning_bonus_raw;
        lightning_bonus_score += other.lightning_bonus_score;
        reactive_operation_penalty += other.reactive_operation_penalty;
        total_score += other.total_score;
        return *this;
    }

    RolloutEvaluation scaled(double factor) const {
        RolloutEvaluation out = *this;
        out.terminal = out.terminal.scaled(factor);
        out.lightning_bonus_raw *= factor;
        out.lightning_bonus_score *= factor;
        out.reactive_operation_penalty *= factor;
        out.total_score *= factor;
        return out;
    }
};

struct RolloutForcedSample {
    rs::FixedList<rs::ForcedMove, rs::kMaxImportantAnts> forced_moves;
    double probability = 1.0;
};

struct RolloutForcedPlan {
    std::vector<RolloutForcedSample> samples;
    int selected_ant_count = 0;
};

inline std::string code_name(int code) {
    return position_code_name(code);
}

inline std::string summarize_plan_name(const SinglePlan &base, const SinglePlan &lure, const SinglePlan &lightning) {
    std::ostringstream oss;
    oss << base.name << '+' << lure.name;
    if (!lightning.ops.empty()) {
        oss << '+' << lightning.name;
    }
    return oss.str();
}

inline std::string followup_step_name(const FollowupStep &step) {
    if (step.empty()) {
        return "";
    }
    if (step.type == FollowupType::DowngradeAtCode) {
        return std::string(code_name(step.code)) + "_downgrade_t" + std::to_string(step.turn);
    }
    if (step.type == FollowupType::BuildAtCode) {
        return std::string("build_") + code_name(step.code) + "_t" + std::to_string(step.turn);
    }
    return std::string(code_name(step.code)) + "_to_" + tower_type_name(step.target) + "_t" + std::to_string(step.turn);
}

inline std::string followup_name(const FollowupAction &followup) {
    if (followup.empty()) {
        return "";
    }
    std::ostringstream oss;
    for (int index = 0; index < followup.count; ++index) {
        if (index) {
            oss << "_then_";
        }
        oss << followup_step_name(followup.steps[static_cast<std::size_t>(index)]);
    }
    return oss.str();
}

inline std::string followup_key(const FollowupAction &followup) {
    if (followup.empty()) {
        return "";
    }
    std::ostringstream oss;
    for (int index = 0; index < followup.count; ++index) {
        if (index) {
            oss << '|';
        }
        const FollowupStep &step = followup.steps[static_cast<std::size_t>(index)];
        oss << "F:" << static_cast<int>(step.type) << ':' << step.code << ':' << static_cast<int>(step.target) << ':'
            << step.turn;
    }
    return oss.str();
}

inline int followup_action_number(const FollowupStep &step) {
    if (step.empty()) {
        return 0;
    }
    if (step.type == FollowupType::DowngradeAtCode) {
        return 5;
    }
    if (step.type == FollowupType::BuildAtCode) {
        return 1;
    }
    switch (step.target) {
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
}

inline std::string followup_text(const FollowupAction &followup) {
    if (followup.empty()) {
        return "";
    }
    std::ostringstream oss;
    for (int index = 0; index < followup.count; ++index) {
        if (index) {
            oss << ';';
        }
        const FollowupStep &step = followup.steps[static_cast<std::size_t>(index)];
        oss << 't' << step.turn << ':' << code_name(step.code) << '-' << followup_action_number(step);
    }
    return oss.str();
}

inline bool followup_has_turn(const FollowupAction &followup, int turn) {
    for (int index = 0; index < followup.count; ++index) {
        const FollowupStep &step = followup.steps[static_cast<std::size_t>(index)];
        if (!step.empty() && step.turn == turn) {
            return true;
        }
    }
    return false;
}

inline std::string plan_key(const std::vector<Operation> &operations, const FollowupAction &followup) {
    const std::string base = join_plan_key(operations);
    const std::string suffix = followup_key(followup);
    if (suffix.empty()) {
        return base;
    }
    return base + '|' + suffix;
}

inline std::string tower_slot_name(const Tower &tower, int player) {
    return slot_label_or_coord(player, tower.x, tower.y);
}

inline std::string tower_slot_name(const rs::SearchTower &tower, int player) {
    return slot_label_or_coord(player, tower.x, tower.y);
}

inline void append_downgrade_candidate(
    const PublicState &state,
    int player,
    const Tower *tower,
    const std::string &name,
    std::vector<SinglePlan> &plans) {
    if (tower == nullptr || tower->player != player) {
        return;
    }
    const Operation downgrade(OperationType::DowngradeTower, tower->tower_id);
    if (!legalize_operations(state, player, {downgrade}).empty()) {
        plans.push_back(SinglePlan{name, {downgrade}, 0.0});
    }
}

inline void append_downgrade_candidate(
    const rs::DefenseSimulator &simulator,
    int /*player*/,
    const rs::SearchTower *tower,
    const std::string &name,
    std::vector<SinglePlan> &plans) {
    if (tower == nullptr || !tower->alive()) {
        return;
    }
    const Operation downgrade(OperationType::DowngradeTower, tower->tower_id);
    if (!legalize_operations(simulator, {downgrade}).empty()) {
        plans.push_back(SinglePlan{name, {downgrade}, 0.0});
    }
}

inline bool base_build_enabled(int code) {
    return code != C2 && code != C3;
}

inline bool c1_quick_route_enabled(int code) {
    return code == C1;
}

inline bool quick_sniper_route_enabled(int code) {
    return code == C1 || code == C2 || code == C3 || code == L1 || code == L2 || code == L3 || code == R1 ||
           code == R2 || code == R3;
}

inline bool sniper_route_allowed(int code, bool c1_sniper_ready) {
    return quick_sniper_route_enabled(code) && (c1_sniper_ready || code == C1);
}

inline bool c1_has_sniper(const PublicState &state, int player) {
    const Tower *tower = tower_at_code(state, player, C1);
    return tower != nullptr && tower->player == player && tower->tower_type == TowerType::Sniper;
}

inline bool c1_has_sniper(const rs::DefenseSimulator &simulator, int player) {
    const rs::SearchTower *tower = tower_at_code(simulator, player, C1);
    return tower != nullptr && tower->alive() && tower->tower_type == TowerType::Sniper;
}

inline std::vector<TowerType> base_build_upgrade_targets(int code, bool c1_sniper_ready) {
    if (code == C1) {
        return {TowerType::Heavy};
    }
    if (c1_sniper_ready) {
        return {TowerType::Heavy, TowerType::Quick, TowerType::Mortar};
    }
    return {TowerType::Heavy, TowerType::Mortar};
}

inline bool can_build_quick_sniper_chain(int code, bool c1_sniper_ready) {
    return sniper_route_allowed(code, c1_sniper_ready);
}

inline FollowupAction quick_sniper_followup(int code) {
    return followup_sequence({upgrade_step(code, TowerType::Quick, 1), upgrade_step(code, TowerType::Sniper, 2)});
}

inline std::vector<TowerType> base_existing_upgrade_targets(int code, bool c1_sniper_ready) {
    if (code == C1) {
        return {TowerType::Heavy};
    }
    if (c1_sniper_ready) {
        return {TowerType::Heavy, TowerType::Quick, TowerType::Mortar};
    }
    return {TowerType::Heavy, TowerType::Mortar};
}

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
    if (!swap_needs_second_turn_sell(source_type)) {
        return FollowupAction{};
    }
    FollowupAction followup;
    followup.push(downgrade_step(source_code));
    if (upgrade_target != TowerType::Basic) {
        followup.push(upgrade_step(target_code, upgrade_target));
    }
    return followup;
}

inline std::vector<Operation> swap_root_operations(
    int player,
    int source_tower_id,
    int target_code,
    TowerType upgrade_target,
    int predicted_tower_id,
    TowerType source_type) {
    std::vector<Operation> ops;
    ops.reserve(upgrade_target == TowerType::Basic || source_type != TowerType::Basic ? 2 : 3);
    ops.push_back(Operation(OperationType::DowngradeTower, source_tower_id));
    ops.push_back(build_at_code(player, target_code));
    if (source_type == TowerType::Basic && upgrade_target != TowerType::Basic) {
        ops.push_back(Operation(OperationType::UpgradeTower, predicted_tower_id, static_cast<int>(upgrade_target)));
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
    for (int target_code : base_codes()) {
        if (target_code == source_code || !base_build_enabled(target_code) ||
            tower_at_code(state, player, target_code) != nullptr) {
            continue;
        }
        const auto basic_ops = swap_root_operations(
            player,
            source.tower_id,
            target_code,
            TowerType::Basic,
            state.next_tower_id,
            source.tower_type);
        if (!legalize_operations(state, player, basic_ops).empty()) {
            plans.push_back(SinglePlan{
                swap_plan_name(source_code, target_code, TowerType::Basic),
                basic_ops,
                0.0,
                swap_followup(source.tower_type, source_code, target_code, TowerType::Basic),
            });
        }
        for (TowerType target_type : base_build_upgrade_targets(target_code, c1_sniper_ready)) {
            const auto ops = swap_root_operations(
                player,
                source.tower_id,
                target_code,
                target_type,
                state.next_tower_id,
                source.tower_type);
            if (!legalize_operations(state, player, ops).empty()) {
                plans.push_back(SinglePlan{
                    swap_plan_name(source_code, target_code, target_type),
                    ops,
                    0.0,
                    swap_followup(source.tower_type, source_code, target_code, target_type),
                });
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
    for (int target_code : base_codes()) {
        if (target_code == source_code || !base_build_enabled(target_code) ||
            tower_at_code(simulator, player, target_code) != nullptr) {
            continue;
        }
        const auto basic_ops = swap_root_operations(
            player,
            source.tower_id,
            target_code,
            TowerType::Basic,
            simulator.next_tower_id,
            source.tower_type);
        if (!legalize_operations(simulator, basic_ops).empty()) {
            plans.push_back(SinglePlan{
                swap_plan_name(source_code, target_code, TowerType::Basic),
                basic_ops,
                0.0,
                swap_followup(source.tower_type, source_code, target_code, TowerType::Basic),
            });
        }
        for (TowerType target_type : base_build_upgrade_targets(target_code, c1_sniper_ready)) {
            const auto ops = swap_root_operations(
                player,
                source.tower_id,
                target_code,
                target_type,
                simulator.next_tower_id,
                source.tower_type);
            if (!legalize_operations(simulator, ops).empty()) {
                plans.push_back(SinglePlan{
                    swap_plan_name(source_code, target_code, target_type),
                    ops,
                    0.0,
                    swap_followup(source.tower_type, source_code, target_code, target_type),
                });
            }
        }
    }
}

inline int non_lure_tower_count(const PublicState &state, int player) {
    int count = 0;
    for (const auto &tower : state.towers) {
        if (tower.player == player && !is_lure_slot_code(code_at(tower, player))) {
            ++count;
        }
    }
    return count;
}

inline int non_lure_tower_count(const rs::DefenseSimulator &simulator, int player) {
    int count = 0;
    for (const auto &tower : simulator.towers) {
        if (tower.alive() && !is_lure_slot_code(code_at(tower, player))) {
            ++count;
        }
    }
    return count;
}

inline double c1_build_heuristic(int code) {
    return code == C1 ? v2_lure_config().c1_build_bonus : 0.0;
}

inline const Tower *forced_lure_sell_target(const PublicState &state, int player) {
    const Tower *best = nullptr;
    int best_distance = 32;
    double best_value = -1.0;
    for (const auto &tower : state.towers) {
        if (tower.player != player) {
            continue;
        }
        const int code = code_at(tower, player);
        if (!is_lure_slot_code(code)) {
            continue;
        }
        int nearest = 32;
        for (const auto &ant : state.ants) {
            if (ant.player == player || ant.kind != AntKind::Combat || !ant.is_alive()) {
                continue;
            }
            nearest = std::min(nearest, hex_distance(tower.x, tower.y, ant.x, ant.y));
        }
        if (nearest > v2_lure_config().forced_lure_sell_distance) {
            continue;
        }
        const double value = tower_salvage_value(state, tower, state.tower_count(player));
        if (nearest < best_distance || (nearest == best_distance && value > best_value)) {
            best = &tower;
            best_distance = nearest;
            best_value = value;
        }
    }
    return best;
}

inline const rs::SearchTower *forced_lure_sell_target(const rs::DefenseSimulator &simulator, int player) {
    const rs::SearchTower *best = nullptr;
    int best_distance = 32;
    double best_value = -1.0;
    const int tower_count = alive_tower_count(simulator);
    for (const auto &tower : simulator.towers) {
        if (!tower.alive()) {
            continue;
        }
        const int code = code_at(tower, player);
        if (!is_lure_slot_code(code)) {
            continue;
        }
        int nearest = 32;
        for (const auto &ant : simulator.ants) {
            if (ant.kind != AntKind::Combat || !ant.alive()) {
                continue;
            }
            nearest = std::min(nearest, hex_distance(tower.x, tower.y, ant.x, ant.y));
        }
        if (nearest > v2_lure_config().forced_lure_sell_distance) {
            continue;
        }
        const double value = tower_salvage_value(tower, tower_count);
        if (nearest < best_distance || (nearest == best_distance && value > best_value)) {
            best = &tower;
            best_distance = nearest;
            best_value = value;
        }
    }
    return best;
}

inline const rs::SearchTower *forced_reactive_sell_target(const rs::DefenseSimulator &simulator, int player) {
    const rs::SearchTower *best = nullptr;
    int best_distance = 32;
    double best_value = -1.0;
    const int tower_count = alive_tower_count(simulator);
    for (const auto &tower : simulator.towers) {
        if (!tower.alive()) {
            continue;
        }
        int nearest = 32;
        for (const auto &ant : simulator.ants) {
            if (ant.kind != AntKind::Combat || !ant.alive()) {
                continue;
            }
            nearest = std::min(nearest, hex_distance(tower.x, tower.y, ant.x, ant.y));
        }
        if (nearest > v2_lure_config().forced_lure_sell_distance) {
            continue;
        }
        const double value = tower_salvage_value(tower, tower_count);
        if (nearest < best_distance || (nearest == best_distance && value > best_value)) {
            best = &tower;
            best_distance = nearest;
            best_value = value;
        }
    }
    static_cast<void>(player);
    return best;
}

inline std::vector<const Tower *> combat_adjacent_tower_targets(const PublicState &state, int player) {
    std::vector<const Tower *> out;
    for (const auto &tower : state.towers) {
        if (tower.player != player) {
            continue;
        }
        bool adjacent = false;
        for (const auto &ant : state.ants) {
            if (ant.player == player || ant.kind != AntKind::Combat || !ant.is_alive()) {
                continue;
            }
            if (hex_distance(tower.x, tower.y, ant.x, ant.y) <= 1) {
                adjacent = true;
                break;
            }
        }
        if (!adjacent) {
            continue;
        }
        out.push_back(&tower);
    }
    const int tower_count = state.tower_count(player);
    std::sort(out.begin(), out.end(), [&](const Tower *lhs, const Tower *rhs) {
        const double lv = tower_salvage_value(state, *lhs, tower_count);
        const double rv = tower_salvage_value(state, *rhs, tower_count);
        if (lv != rv) {
            return lv > rv;
        }
        return lhs->tower_id < rhs->tower_id;
    });
    return out;
}

inline std::vector<SinglePlan> generate_base_candidates(const PublicState &state, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"base_hold", {}, 0.0});

    const int base_tower_count = non_lure_tower_count(state, player);
    const bool can_build_more = base_tower_count < v2_lure_config().max_non_lure_towers;
    const bool can_expand_existing = base_tower_count <= v2_lure_config().max_non_lure_towers;
    const bool c1_sniper_ready = c1_has_sniper(state, player);

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
                    for (TowerType target_type : base_build_upgrade_targets(code, c1_sniper_ready)) {
                        plans.push_back(SinglePlan{
                            "base_build_" + code_name(code) + "_then_" + tower_type_name(target_type),
                            {build},
                            c1_build_heuristic(code),
                            upgrade_followup(code, target_type),
                        });
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

        if (!can_expand_existing) {
            continue;
        }
        if (tower->tower_type == TowerType::Basic) {
            for (TowerType target_type : base_existing_upgrade_targets(code, c1_sniper_ready)) {
                const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(target_type));
                if (!legalize_operations(state, player, {upgrade}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_" + code_name(code) + "_to_" + tower_type_name(target_type),
                        {upgrade},
                        0.0,
                    });
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
        }
    }

    return plans;
}

inline std::vector<SinglePlan> generate_base_candidates(const rs::DefenseSimulator &simulator, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"base_hold", {}, 0.0});

    const int base_tower_count = non_lure_tower_count(simulator, player);
    const bool can_build_more = base_tower_count < v2_lure_config().max_non_lure_towers;
    const bool can_expand_existing = base_tower_count <= v2_lure_config().max_non_lure_towers;
    const bool c1_sniper_ready = c1_has_sniper(simulator, player);

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
                    for (TowerType target_type : base_build_upgrade_targets(code, c1_sniper_ready)) {
                        plans.push_back(SinglePlan{
                            "base_build_" + code_name(code) + "_then_" + tower_type_name(target_type),
                            {build},
                            c1_build_heuristic(code),
                            upgrade_followup(code, target_type),
                        });
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

        if (!can_expand_existing) {
            continue;
        }
        if (tower->tower_type == TowerType::Basic) {
            for (TowerType target_type : base_existing_upgrade_targets(code, c1_sniper_ready)) {
                const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(target_type));
                if (!legalize_operations(simulator, {upgrade}).empty()) {
                    plans.push_back(SinglePlan{
                        "base_" + code_name(code) + "_to_" + tower_type_name(target_type),
                        {upgrade},
                        0.0,
                    });
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
        }
    }

    return plans;
}

inline std::vector<SinglePlan> generate_lure_candidates(const PublicState &state, const rs::DefenseSimulator *simulator, int player) {
    const Tower *forced = forced_lure_sell_target(state, player);
    if (forced != nullptr) {
        return {SinglePlan{
            "lure_forced_sell_" + code_name(code_at(*forced, player)),
            {Operation(OperationType::DowngradeTower, forced->tower_id)},
            0.0,
        }};
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
            if (legalize_operations(state, player, {build}).empty()) {
                continue;
            }
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
        return {SinglePlan{
            "lure_forced_sell_" + code_name(code_at(*forced, player)),
            {Operation(OperationType::DowngradeTower, forced->tower_id)},
            0.0,
        }};
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
            if (legalize_operations(simulator, {build}).empty()) {
                continue;
            }
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

inline double enemy_tower_lightning_damage_score(const PublicState &state, int player, int x, int y) {
    constexpr int kLightningTowerDamage = 3;
    const int enemy = 1 - player;
    const int strikes = lightning_tower_strikes_within_horizon(v2_lure_config().lightning_horizon);
    if (strikes <= 0) {
        return 0.0;
    }

    int enemy_tower_count = 0;
    for (const auto &tower : state.towers) {
        if (tower.player == enemy && tower.hp > 0) {
            ++enemy_tower_count;
        }
    }
    if (enemy_tower_count <= 0) {
        return 0.0;
    }

    const int total_damage = strikes * kLightningTowerDamage;
    double score = 0.0;
    for (const auto &tower : state.towers) {
        if (tower.player != enemy || tower.hp <= 0) {
            continue;
        }
        if (hex_distance(x, y, tower.x, tower.y) > weapon_stats(SuperWeaponType::LightningStorm).attack_range) {
            continue;
        }
        const double before = tower_salvage_value(state, tower, enemy_tower_count);
        Tower damaged = tower;
        damaged.hp = std::max(0, tower.hp - total_damage);
        const double after = tower_salvage_value(state, damaged, enemy_tower_count);
        score += (before - after) * v2_lure_config().tower_value_weight * v2_lure_config().lightning_tower_value_ratio;
    }
    return score;
}

inline std::vector<SinglePlan> generate_lightning_center_candidates(
    const PublicState &state,
    const rs::DefenseSimulator *simulator,
    int player) {
    std::vector<SinglePlan> plans;
    static_cast<void>(simulator);
    if (state.weapon_cooldowns[player][static_cast<int>(SuperWeaponType::LightningStorm)] > 0) {
        return plans;
    }

    for (int x = 0; x < kMapSize; ++x) {
        for (int y = 0; y < kMapSize; ++y) {
            if (!is_lightning_center_candidate(x, y)) {
                continue;
            }
            const Operation operation(OperationType::UseLightningStorm, x, y);
            if (legalize_operations(state, player, {operation}).empty()) {
                continue;
            }
            plans.push_back(SinglePlan{
                "lightning_" + std::to_string(x) + "_" + std::to_string(y),
                {operation},
                0.0,
            });
        }
    }
    return plans;
}

inline std::vector<SinglePlan> generate_lightning_prep_candidates(const PublicState &state, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"lightning_hold", {}, 0.0});
    static_cast<void>(state);
    static_cast<void>(player);
    return plans;
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
        const std::string key = plan_key(combined, followup);
        const double operation_penalty = downgrade_penalty_for_ops(state, player, combined);
        const double heuristic = base_heuristic + lure_heuristic + lightning_heuristic - operation_penalty;
        double lightning_static_bonus = 0.0;
        if (has_lightning && !combined.empty()) {
            lightning_static_bonus += enemy_super_effect_active(state, player)
                                          ? v2_lure_config().lightning_enemy_super_bonus
                                          : v2_lure_config().lightning_no_enemy_super_penalty;
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
            plans[it->second].lightning_static_bonus = lightning_static_bonus;
            plans[it->second].has_lightning = has_lightning;
            plans[it->second].horizon = horizon;
            plans[it->second].followup = followup;
        }
    };

    const auto is_hold = [](const SinglePlan &plan) {
        return plan.ops.empty() && plan.followup.empty();
    };
    const auto is_downgrade_only_followup = [](const FollowupAction &followup) {
        for (int index = 0; index < followup.count; ++index) {
            if (followup.steps[static_cast<std::size_t>(index)].type != FollowupType::DowngradeAtCode) {
                return false;
            }
        }
        return true;
    };
    const auto is_recycle_only = [&](const SinglePlan &plan) {
        if (plan.ops.empty() || !is_downgrade_only_followup(plan.followup)) {
            return false;
        }
        int recycle_code = -1;
        const auto note_code = [&](int code) {
            if (code < 0) {
                return false;
            }
            if (recycle_code < 0) {
                recycle_code = code;
                return true;
            }
            return recycle_code == code;
        };
        for (const auto &operation : plan.ops) {
            if (operation.op_type != OperationType::DowngradeTower) {
                return false;
            }
            const Tower *tower = state.tower_by_id(operation.arg0);
            if (tower == nullptr || !note_code(code_at(*tower, player))) {
                return false;
            }
        }
        for (int index = 0; index < plan.followup.count; ++index) {
            if (plan.followup.steps[static_cast<std::size_t>(index)].type == FollowupType::DowngradeAtCode) {
                if (!note_code(plan.followup.steps[static_cast<std::size_t>(index)].code)) {
                    return false;
                }
            }
        }
        return recycle_code >= 0;
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
            v2_lure_config().hold_bonus,
            0.0,
            0.0,
            false,
            v2_lure_config().long_eval_horizon,
            FollowupAction{});
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
            v2_lure_config().long_eval_horizon,
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
            v2_lure_config().long_eval_horizon,
            lure_plan.followup);
    }

    for (const auto &base_plan : base) {
        if (!is_recycle_only(base_plan)) {
            continue;
        }
        for (const auto &lure_plan : lure) {
            if (is_hold(lure_plan)) {
                continue;
            }
            ++base_lure_combo_count;
            std::vector<Operation> ops = base_plan.ops;
            ops.insert(ops.end(), lure_plan.ops.begin(), lure_plan.ops.end());
            add_plan(
                base_plan.name + "+" + lure_plan.name,
                base_plan.name,
                lure_plan.name,
                no_lightning.name,
                ops,
                base_plan.heuristic,
                lure_plan.heuristic,
                0.0,
                false,
                v2_lure_config().long_eval_horizon,
                base_plan.followup);
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
            v2_lure_config().lightning_horizon,
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
                v2_lure_config().lightning_horizon,
                FollowupAction{});
            ++lightning_recycle_combo_count;
        }
    }

    out.raw_combo_count = out.base_count + out.lure_count + base_lure_combo_count;
    out.raw_plan_count = out.raw_combo_count + out.lightning_count + lightning_recycle_combo_count;

    std::sort(plans.begin(), plans.end(), [](const CombinedPlan &lhs, const CombinedPlan &rhs) {
        if (lhs.heuristic != rhs.heuristic) {
            return lhs.heuristic > rhs.heuristic;
        }
        return lhs.key < rhs.key;
    });
    return out;
}

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

inline bool apply_reactive_turn_operations(rs::DefenseSimulator &simulator, int player) {
    // Rollout-time adaptive behavior is intentionally limited to emergency
    // recycling. Proactive base/lure choices are root-plan decisions.
    if (const rs::SearchTower *forced = forced_reactive_sell_target(simulator, player); forced != nullptr) {
        return simulator.apply_operation(Operation(OperationType::DowngradeTower, forced->tower_id));
    }
    return true;
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

inline double worker_threat_score(const PublicState &state, int player) {
    const auto [base_x, base_y] = kPlayerBases[player];
    double threat = 0.0;
    for (const auto &ant : state.ants) {
        if (ant.player == player || ant.kind != AntKind::Worker || !ant.is_alive()) {
            continue;
        }
        const int distance = std::max(1, hex_distance(ant.x, ant.y, base_x, base_y));
        threat += v2_lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
    }
    return threat;
}

inline double combat_anchor_threat_at(const PublicState &state, int player, int x, int y) {
    double threat = 0.0;
    int tower_count = state.tower_count(player);
    for (const auto &tower : state.towers) {
        if (tower.player != player) {
            continue;
        }
        const int code = code_at(tower, player);
        if (!is_core_build_position(code)) {
            continue;
        }
        const int distance = std::max(1, hex_distance(x, y, tower.x, tower.y));
        const double value = tower_salvage_value(state, tower, tower_count);
        double tower_threat = value * v2_lure_config().combat_anchor_threat_coin_ratio / distance;
        if (distance <= v2_lure_config().combat_anchor_ring_distance) {
            tower_threat += value * v2_lure_config().combat_anchor_ring1_bonus_ratio;
        }
        threat = std::max(threat, tower_threat);
    }
    return threat;
}

inline double combat_threat_at(const PublicState &state, int player, const Ant &ant, int x, int y) {
    const auto [base_x, base_y] = kPlayerBases[player];
    const int distance = std::max(1, hex_distance(x, y, base_x, base_y));
    double threat = v2_lure_config().combat_base_threat_unit / distance;
    threat = std::max(threat, combat_anchor_threat_at(state, player, x, y));
    threat *= behavior_threat_scale(ant.behavior);
    return threat;
}

inline double worker_threat_score(const rs::DefenseSimulator &simulator, int player) {
    const auto [base_x, base_y] = kPlayerBases[player];
    double threat = 0.0;
    for (const auto &ant : simulator.ants) {
        if (ant.kind != AntKind::Worker || !ant.alive()) {
            continue;
        }
        const int distance = std::max(1, hex_distance(ant.x, ant.y, base_x, base_y));
        threat += v2_lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
    }
    return threat;
}

inline double combat_anchor_threat_at(const rs::DefenseSimulator &simulator, int player, int x, int y) {
    double threat = 0.0;
    const int tower_count = alive_tower_count(simulator);
    for (const auto &tower : simulator.towers) {
        if (!tower.alive()) {
            continue;
        }
        const int code = code_at(tower, player);
        if (!is_core_build_position(code)) {
            continue;
        }
        const int distance = std::max(1, hex_distance(x, y, tower.x, tower.y));
        const double value = tower_salvage_value(tower, tower_count);
        double tower_threat = value * v2_lure_config().combat_anchor_threat_coin_ratio / distance;
        if (distance <= v2_lure_config().combat_anchor_ring_distance) {
            tower_threat += value * v2_lure_config().combat_anchor_ring1_bonus_ratio;
        }
        threat = std::max(threat, tower_threat);
    }
    return threat;
}

inline double combat_threat_at(const rs::DefenseSimulator &simulator, int player, const rs::SearchAnt &ant, int x, int y) {
    const auto [base_x, base_y] = kPlayerBases[player];
    const int distance = std::max(1, hex_distance(x, y, base_x, base_y));
    double threat = v2_lure_config().combat_base_threat_unit / distance;
    threat = std::max(threat, combat_anchor_threat_at(simulator, player, x, y));
    threat *= behavior_threat_scale(ant.behavior);
    return threat;
}

inline double forced_rollout_ant_priority(const rs::DefenseSimulator &simulator, int player, const rs::SearchAnt &ant) {
    if (!ant.alive() || ant.too_old() || ant.is_frozen) {
        return -std::numeric_limits<double>::infinity();
    }
    if (ant.kind == AntKind::Combat) {
        return combat_threat_at(simulator, player, ant, ant.x, ant.y);
    }
    const auto [base_x, base_y] = kPlayerBases[player];
    const int distance = std::max(1, hex_distance(ant.x, ant.y, base_x, base_y));
    double threat = v2_lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
    if (ant.behavior == AntBehavior::Random) {
        threat *= v2_lure_config().randomized_threat_scale;
    } else if (ant.behavior == AntBehavior::Bewitched) {
        threat *= v2_lure_config().bewitched_threat_scale;
    }
    return threat;
}

inline std::vector<rs::MoveOption> positive_rollout_move_options_for(
    const rs::DefenseSimulator &simulator,
    const rs::SearchAnt &ant) {
    std::vector<rs::MoveOption> options;
    const auto fixed = simulator.move_options_for(ant);
    options.reserve(static_cast<std::size_t>(fixed.size()));
    for (int index = 0; index < fixed.size(); ++index) {
        if (fixed[index].probability > 1e-12) {
            options.push_back(fixed[index]);
        }
    }
    if (options.empty()) {
        options.push_back(rs::MoveOption{rs::kNoMove, ant.x, ant.y, 1.0, 0.0});
    }
    return options;
}

inline std::vector<int> rollout_option_sequence_indices(
    const std::vector<rs::MoveOption> &options,
    int rollout_count,
    rs::FastRng &rng) {
    std::vector<int> sequence;
    if (rollout_count <= 0 || options.empty()) {
        return sequence;
    }

    const int option_count = static_cast<int>(options.size());
    std::vector<int> counts(static_cast<std::size_t>(option_count), 0);
    std::vector<int> order(static_cast<std::size_t>(option_count), 0);
    std::iota(order.begin(), order.end(), 0);
    for (int index = option_count - 1; index > 0; --index) {
        std::swap(order[static_cast<std::size_t>(index)], order[static_cast<std::size_t>(rng.next_int(index + 1))]);
    }

    if (option_count >= rollout_count) {
        std::stable_sort(order.begin(), order.end(), [&](int lhs, int rhs) {
            if (options[static_cast<std::size_t>(lhs)].probability != options[static_cast<std::size_t>(rhs)].probability) {
                return options[static_cast<std::size_t>(lhs)].probability > options[static_cast<std::size_t>(rhs)].probability;
            }
            return lhs < rhs;
        });
        for (int index = 0; index < rollout_count; ++index) {
            counts[static_cast<std::size_t>(order[static_cast<std::size_t>(index)])] = 1;
        }
    } else {
        for (int index = 0; index < option_count; ++index) {
            counts[static_cast<std::size_t>(index)] = 1;
        }
        int remaining = rollout_count - option_count;
        std::vector<double> fractional(static_cast<std::size_t>(option_count), 0.0);
        for (int index = 0; index < option_count; ++index) {
            const double desired_extra =
                std::max(0.0, options[static_cast<std::size_t>(index)].probability * static_cast<double>(rollout_count) - 1.0);
            const int extra = static_cast<int>(std::floor(desired_extra + 1e-9));
            counts[static_cast<std::size_t>(index)] += extra;
            remaining -= extra;
            fractional[static_cast<std::size_t>(index)] = desired_extra - static_cast<double>(extra);
        }
        std::stable_sort(order.begin(), order.end(), [&](int lhs, int rhs) {
            const double lhs_fractional = fractional[static_cast<std::size_t>(lhs)];
            const double rhs_fractional = fractional[static_cast<std::size_t>(rhs)];
            if (lhs_fractional != rhs_fractional) {
                return lhs_fractional > rhs_fractional;
            }
            if (options[static_cast<std::size_t>(lhs)].probability != options[static_cast<std::size_t>(rhs)].probability) {
                return options[static_cast<std::size_t>(lhs)].probability > options[static_cast<std::size_t>(rhs)].probability;
            }
            return lhs < rhs;
        });
        for (int index = 0; index < remaining; ++index) {
            counts[static_cast<std::size_t>(order[static_cast<std::size_t>(index)])] += 1;
        }
    }

    sequence.reserve(static_cast<std::size_t>(rollout_count));
    for (int index = 0; index < option_count; ++index) {
        for (int count = 0; count < counts[static_cast<std::size_t>(index)]; ++count) {
            sequence.push_back(index);
        }
    }
    if (sequence.empty()) {
        sequence.push_back(0);
    }
    while (static_cast<int>(sequence.size()) < rollout_count) {
        sequence.push_back(order.empty() ? 0 : order.front());
    }
    if (static_cast<int>(sequence.size()) > rollout_count) {
        sequence.resize(static_cast<std::size_t>(rollout_count));
    }
    for (int index = rollout_count - 1; index > 0; --index) {
        std::swap(sequence[static_cast<std::size_t>(index)], sequence[static_cast<std::size_t>(rng.next_int(index + 1))]);
    }
    return sequence;
}

inline RolloutForcedPlan build_first_round_rollout_plan(
    const rs::DefenseSimulator &simulator,
    int player,
    int rollout_count,
    std::uint64_t schedule_seed) {
    RolloutForcedPlan out;
    const int effective_rollouts = std::max(1, rollout_count);
    out.samples.resize(static_cast<std::size_t>(effective_rollouts));
    for (auto &sample : out.samples) {
        sample.probability = 1.0;
    }

    std::vector<const rs::SearchAnt *> ranked;
    ranked.reserve(static_cast<std::size_t>(simulator.ants.size()));
    for (const auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || ant.is_frozen) {
            continue;
        }
        ranked.push_back(&ant);
    }
    std::stable_sort(ranked.begin(), ranked.end(), [&](const rs::SearchAnt *lhs, const rs::SearchAnt *rhs) {
        const double lhs_priority = forced_rollout_ant_priority(simulator, player, *lhs);
        const double rhs_priority = forced_rollout_ant_priority(simulator, player, *rhs);
        if (lhs_priority != rhs_priority) {
            return lhs_priority > rhs_priority;
        }
        return lhs->ant_id < rhs->ant_id;
    });

    const int limit = std::min(v2_lure_config().rollout_forced_ant_limit, rs::kMaxImportantAnts);
    if (static_cast<int>(ranked.size()) > limit) {
        ranked.resize(static_cast<std::size_t>(limit));
    }
    out.selected_ant_count = static_cast<int>(ranked.size());

    rs::FastRng rng(schedule_seed);
    for (const rs::SearchAnt *ant : ranked) {
        const auto options = positive_rollout_move_options_for(simulator, *ant);
        const auto sequence = rollout_option_sequence_indices(options, effective_rollouts, rng);
        for (int rollout = 0; rollout < effective_rollouts; ++rollout) {
            const int option_index = sequence[static_cast<std::size_t>(rollout)];
            const auto &option = options[static_cast<std::size_t>(option_index)];
            if (option.direction != rs::kNoMove) {
                out.samples[static_cast<std::size_t>(rollout)].forced_moves.push_back(
                    rs::ForcedMove{ant->ant_id, option.direction});
            }
            out.samples[static_cast<std::size_t>(rollout)].probability *= std::max(option.probability, 1e-12);
        }
    }
    return out;
}

inline bool apply_operations(rs::DefenseSimulator &simulator, const std::vector<Operation> &operations) {
    for (const auto &operation : sort_operations(simulator, operations)) {
        if (!simulator.apply_operation(operation)) {
            return false;
        }
    }
    return true;
}

inline double combat_threat_score(const rs::DefenseSimulator &terminal_simulator, int player) {
    double threat = 0.0;
    for (const auto &ant : terminal_simulator.ants) {
        if (ant.kind != AntKind::Combat || !ant.alive()) {
            continue;
        }
        threat += combat_threat_at(terminal_simulator, player, ant, ant.x, ant.y);
    }
    return threat;
}

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
    const rs::DefenseSimulator &without_lightning,
    int player) {
    double bonus = 0.0;
    for (const auto &ant : without_lightning.ants) {
        if (ant.kind != AntKind::Combat || !ant.alive()) {
            continue;
        }
        const double before_threat = combat_threat_at(without_lightning, player, ant, ant.x, ant.y);
        const int without_shield = ant.shield;
        int with_shield = 0;
        int with_hp = 0;
        double after_threat = 0.0;
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
            after_threat = combat_threat_at(with_lightning, player, *with_ant, with_ant->x, with_ant->y);
        }

        bonus += std::max(0.0, before_threat - after_threat) * v2_lure_config().lightning_combat_threat_ratio;
        if (without_shield > 0 && with_shield < without_shield) {
            bonus += v2_lure_config().lightning_shield_break_bonus;
        }
        const int damage = std::max(0, ant.hp - with_hp);
        bonus += static_cast<double>(damage) * v2_lure_config().lightning_damage_bonus_per_hp;
        if (with_ant == nullptr) {
            bonus += v2_lure_config().lightning_kill_bonus;
        }
    }
    return bonus;
}

inline double c1_state_bonus(TowerType tower_type, bool transition_phase) {
    switch (tower_type) {
    case TowerType::Heavy:
    case TowerType::HeavyPlus:
    case TowerType::Ice:
    case TowerType::Bewitch:
        return transition_phase ? v2_lure_config().c1_heavy_side_trans_bonus : v2_lure_config().c1_heavy_bonus;
    case TowerType::Quick:
    case TowerType::QuickPlus:
    case TowerType::Double:
        return transition_phase ? v2_lure_config().c1_quick_trans_bonus : 0.0;
    case TowerType::Sniper:
        return transition_phase ? v2_lure_config().c1_sniper_trans_bonus : 0.0;
    default:
        return 0.0;
    }
}

inline double c1_root_bonus(const rs::DefenseSimulator &post_root, int player, double root_coins) {
    const rs::SearchTower *c1 = tower_at_code(post_root, player, C1);
    if (c1 == nullptr || !c1->alive()) {
        return 0.0;
    }
    const bool transition_phase =
        root_coins > static_cast<double>(v2_lure_config().c1_quick_transition_coin_threshold);
    return c1_state_bonus(c1->tower_type, transition_phase);
}

inline double c1_root_bonus_for_plan(
    const rs::DefenseSimulator &post_root,
    int player,
    double root_coins,
    const FollowupAction &followup) {
    if (followup.empty()) {
        return c1_root_bonus(post_root, player, root_coins);
    }
    rs::DefenseSimulator projected = post_root.clone();
    for (int turn = 1; turn <= 2; ++turn) {
        apply_operations(projected, resolve_followup_operations(projected, player, followup, turn));
    }
    return c1_root_bonus(projected, player, root_coins);
}

inline double c1_terminal_bonus(const rs::DefenseSimulator &, int) {
    return 0.0;
}

inline EvalBreakdown evaluate_terminal(const rs::DefenseSimulator &simulator, int player) {
    EvalBreakdown out;
    out.base_hp_raw = static_cast<double>(simulator.base_hp);
    out.base_hp_score = out.base_hp_raw * v2_lure_config().base_hp_weight;
    out.tower_value_raw = tower_full_salvage_value(simulator);
    out.tower_value_score = out.tower_value_raw * v2_lure_config().tower_value_weight;
    out.money_raw = simulator.coins;
    out.money_score = out.money_raw * v2_lure_config().money_weight;
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
    rs::FastRng rng(rollout_seed);
    if (first_round_forced_moves != nullptr) {
        simulator.simulate_round(rng, *first_round_forced_moves);
    } else {
        simulator.simulate_round(rng);
    }
    RolloutEvaluation out;
    if (plan.has_lightning) {
        rs::DefenseSimulator control = root.clone();
        if (!plan.ops.empty()) {
            apply_operations(control, strip_lightning_operations(plan.ops));
        }
        rs::FastRng control_rng(rollout_seed);
        if (first_round_forced_moves != nullptr) {
            control.simulate_round(control_rng, *first_round_forced_moves);
        } else {
            control.simulate_round(control_rng);
        }
        out.lightning_bonus_raw = lightning_counterfactual_bonus(simulator, control, player) + plan.lightning_static_bonus;
        out.lightning_bonus_score = out.lightning_bonus_raw;
    }
    EvalBreakdown mid_eval;
    bool has_mid_eval = false;
    double reactive_penalty = 0.0;
    double mid_reactive_penalty = 0.0;
    const int mid_horizon = std::max(0, std::min(plan.horizon, v2_lure_config().mid_eval_horizon));
    int step = 1;
    auto capture_mid_eval = [&]() {
        if (!has_mid_eval && step >= mid_horizon) {
            mid_eval = evaluate_terminal(simulator, player);
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
    const EvalBreakdown terminal_eval = evaluate_terminal(simulator, player);
    if (!has_mid_eval) {
        mid_eval = terminal_eval;
        mid_reactive_penalty = reactive_penalty;
    }
    out.terminal = combine_eval_breakdowns(mid_eval, terminal_eval, v2_lure_config().mid_eval_weight);
    const double mid_weight = std::max(0.0, std::min(1.0, v2_lure_config().mid_eval_weight));
    out.reactive_operation_penalty = mid_weight * mid_reactive_penalty + (1.0 - mid_weight) * reactive_penalty;
    out.total_score = out.terminal.total_score + out.lightning_bonus_score - out.reactive_operation_penalty;
    return out;
}

struct EvaluatedPlan {
    std::size_t root_index = 0;
    CombinedPlan plan;
    RolloutEvaluation mean_rollout;
    double mean_rollout_score = -std::numeric_limits<double>::infinity();
    double mean_score = -std::numeric_limits<double>::infinity();
    double rollout_weight_sum = 0.0;
    int rollout_count = 0;
};

inline std::vector<EvaluatedPlan> evaluate_root_plans(
    const PublicState &state,
    const rs::DefenseSimulator &defense_root,
    int player,
    std::uint64_t serial,
    int rollout_count,
    const RootPlanSet &root_plans) {
    std::vector<EvaluatedPlan> evaluated;
    evaluated.reserve(root_plans.plans.size());

    auto evaluate_one = [&](
                            std::size_t index,
                            const CombinedPlan &plan,
                            int effective_rollouts,
                            std::uint64_t assignment_salt = 0) {
        EvaluatedPlan item;
        item.root_index = index;
        item.plan = plan;
        item.rollout_count = effective_rollouts;

        rs::DefenseSimulator plan_root = defense_root.clone();
        if (!plan.ops.empty() && !apply_operations(plan_root, plan.ops)) {
            item.mean_rollout_score = -std::numeric_limits<double>::infinity();
            item.mean_score = -std::numeric_limits<double>::infinity();
            return item;
        }

        const RolloutForcedPlan forced_plan = build_first_round_rollout_plan(
            plan_root,
            player,
            effective_rollouts,
            plan_rollout_assignment_seed(
                state.seed,
                serial + assignment_salt,
                index,
                plan.horizon,
                effective_rollouts));

        RolloutEvaluation weighted_total;
        double weight_sum = 0.0;
        bool valid = true;
        for (int rollout = 0; rollout < effective_rollouts; ++rollout) {
            const double weight =
                rollout < static_cast<int>(forced_plan.samples.size())
                    ? std::max(forced_plan.samples[static_cast<std::size_t>(rollout)].probability, 1e-12)
                    : 1.0;
            const auto *forced_moves =
                rollout < static_cast<int>(forced_plan.samples.size())
                    ? &forced_plan.samples[static_cast<std::size_t>(rollout)].forced_moves
                    : nullptr;
            const RolloutEvaluation sample = rollout_plan_score(
                defense_root,
                player,
                plan,
                plan_rollout_seed(state.seed, serial, index, rollout + static_cast<int>(assignment_salt), plan.horizon),
                forced_moves);
            if (!std::isfinite(sample.total_score)) {
                valid = false;
                break;
            }
            weighted_total += sample.scaled(weight);
            weight_sum += weight;
        }

        if (!valid || weight_sum <= 0.0) {
            item.mean_rollout_score = -std::numeric_limits<double>::infinity();
            item.mean_score = -std::numeric_limits<double>::infinity();
            item.rollout_weight_sum = 0.0;
            return item;
        }

        item.rollout_weight_sum = weight_sum;
        item.mean_rollout = weighted_total.scaled(1.0 / weight_sum);
        const double root_c1_bonus = c1_root_bonus_for_plan(plan_root, player, defense_root.coins, plan.followup);
        item.mean_rollout.terminal.c1_bonus_raw = root_c1_bonus;
        item.mean_rollout.terminal.c1_bonus_score = root_c1_bonus;
        item.mean_rollout.terminal.total_score += root_c1_bonus;
        item.mean_rollout.total_score += root_c1_bonus;
        item.mean_rollout_score = item.mean_rollout.total_score;
        item.mean_score = item.mean_rollout_score + plan.heuristic;
        return item;
    };

    struct UcbArm {
        std::size_t root_index = 0;
        CombinedPlan plan;
        RolloutForcedPlan forced_plan;
        RolloutEvaluation weighted_total;
        double weight_sum = 0.0;
        double root_c1_bonus = 0.0;
        int samples = 0;
        bool valid = true;
    };

    std::vector<UcbArm> lightning_arms;

    for (std::size_t index = 0; index < root_plans.plans.size(); ++index) {
        const auto &plan = root_plans.plans[index];
        const int normal_rollouts = rollout_count > 0 ? rollout_count : std::max(1, v2_lure_config().rollout_count);
        if (plan.has_lightning) {
            UcbArm arm;
            arm.root_index = index;
            arm.plan = plan;
            lightning_arms.push_back(std::move(arm));
            continue;
        }
        evaluated.push_back(evaluate_one(index, plan, normal_rollouts));
    }

    if (!lightning_arms.empty() && v2_lure_config().lightning_ucb_total_rollouts > 0) {
        const int budget = std::max(1, v2_lure_config().lightning_ucb_total_rollouts);
        for (auto &arm : lightning_arms) {
            rs::DefenseSimulator plan_root = defense_root.clone();
            if (!arm.plan.ops.empty() && !apply_operations(plan_root, arm.plan.ops)) {
                arm.valid = false;
                continue;
            }
            arm.root_c1_bonus = c1_root_bonus_for_plan(plan_root, player, defense_root.coins, arm.plan.followup);
            arm.forced_plan = build_first_round_rollout_plan(
                plan_root,
                player,
                budget,
                plan_rollout_assignment_seed(state.seed, serial, arm.root_index, arm.plan.horizon, budget));
        }
        auto arm_mean_score = [](const UcbArm &arm) {
            return arm.weight_sum > 0.0
                       ? arm.weighted_total.total_score / arm.weight_sum + arm.plan.heuristic
                       : -std::numeric_limits<double>::infinity();
        };
        auto sample_arm = [&](UcbArm &arm) {
            if (!arm.valid || arm.samples >= budget) {
                return false;
            }
            const int rollout = arm.samples;
            const double weight =
                rollout < static_cast<int>(arm.forced_plan.samples.size())
                    ? std::max(arm.forced_plan.samples[static_cast<std::size_t>(rollout)].probability, 1e-12)
                    : 1.0;
            const auto *forced_moves =
                rollout < static_cast<int>(arm.forced_plan.samples.size())
                    ? &arm.forced_plan.samples[static_cast<std::size_t>(rollout)].forced_moves
                    : nullptr;
            RolloutEvaluation sample = rollout_plan_score(
                defense_root,
                player,
                arm.plan,
                plan_rollout_seed(state.seed, serial, arm.root_index, rollout, arm.plan.horizon),
                forced_moves);
            if (!std::isfinite(sample.total_score)) {
                arm.valid = false;
                return false;
            }
            sample.terminal.c1_bonus_raw = arm.root_c1_bonus;
            sample.terminal.c1_bonus_score = arm.root_c1_bonus;
            sample.terminal.total_score += arm.root_c1_bonus;
            sample.total_score += arm.root_c1_bonus;
            arm.weighted_total += sample.scaled(weight);
            arm.weight_sum += weight;
            ++arm.samples;
            return true;
        };

        int total_samples = 0;
        for (auto &arm : lightning_arms) {
            if (total_samples >= budget) {
                break;
            }
            if (sample_arm(arm)) {
                ++total_samples;
            }
        }
        while (total_samples < budget) {
            int best_index = -1;
            double best_ucb = -std::numeric_limits<double>::infinity();
            for (std::size_t arm_index = 0; arm_index < lightning_arms.size(); ++arm_index) {
                const auto &arm = lightning_arms[arm_index];
                if (arm.samples <= 0) {
                    continue;
                }
                const double mean = arm_mean_score(arm);
                const double explore =
                    v2_lure_config().lightning_ucb_exploration *
                    std::sqrt(std::log(static_cast<double>(total_samples + 1)) / static_cast<double>(arm.samples));
                const double ucb = mean + explore;
                if (ucb > best_ucb) {
                    best_ucb = ucb;
                    best_index = static_cast<int>(arm_index);
                }
            }
            if (best_index < 0) {
                break;
            }
            auto &arm = lightning_arms[static_cast<std::size_t>(best_index)];
            sample_arm(arm);
            ++total_samples;
        }
        for (auto &arm : lightning_arms) {
            if (arm.samples <= 0 || arm.weight_sum <= 0.0) {
                continue;
            }
            EvaluatedPlan item;
            item.root_index = arm.root_index;
            item.plan = arm.plan;
            item.rollout_count = arm.samples;
            item.rollout_weight_sum = arm.weight_sum;
            item.mean_rollout = arm.weighted_total.scaled(1.0 / arm.weight_sum);
            item.mean_rollout_score = item.mean_rollout.total_score;
            item.mean_score = item.mean_rollout_score + item.plan.heuristic;
            evaluated.push_back(item);
        }
    }

    std::sort(evaluated.begin(), evaluated.end(), [](const EvaluatedPlan &lhs, const EvaluatedPlan &rhs) {
        if (lhs.mean_score != rhs.mean_score) {
            return lhs.mean_score > rhs.mean_score;
        }
        return lhs.plan.key < rhs.plan.key;
    });
    return evaluated;
}

} // namespace lure_strategy_detail

inline std::vector<Operation> decide_lure_strategy(
    const LureStrategyDecisionContext &context,
    LureStrategySession *session = nullptr) {
    using namespace lure_strategy_detail;

    if (context.state == nullptr) {
        return {};
    }
    if (session != nullptr) {
        session->observe(*context.state, context.player);
    }

    const DebugMode debug = debug_mode();
    const bool emit_summary = debug != DebugMode::None;
    const bool emit_plans = debug == DebugMode::Plans;
    const auto decision_begin = std::chrono::steady_clock::now();

    PublicState state = context.state->clone();
    if (session != nullptr) {
        session->apply_inferred_last_moves(state, context.player);
    }
    rs::DefenseSimulator defense_root = rs::make_defense_simulator(state, context.simulator, context.player);
    defense_root.ignore_enemy_spawns = true;
    const RootPlanSet root_plans = generate_root_plans(state, &defense_root, context.player);

    const std::uint64_t serial = session != nullptr ? session->decision_serial[context.player] : 0ULL;
    const std::vector<EvaluatedPlan> evaluated =
        evaluate_root_plans(state, defense_root, context.player, serial, v2_lure_config().rollout_count, root_plans);

    const auto decision_end = std::chrono::steady_clock::now();
    const auto elapsed_us = std::chrono::duration_cast<std::chrono::microseconds>(decision_end - decision_begin).count();

    if (emit_summary) {
        if (emit_plans) {
            for (std::size_t rank = 0; rank < evaluated.size(); ++rank) {
                const auto &item = evaluated[rank];
                std::cerr
                    << "{\"kind\":\"plan\""
                    << ",\"round\":" << state.round_index
                    << ",\"player\":" << context.player
                    << ",\"serial\":" << serial
                    << ",\"rank\":" << (rank + 1)
                    << ",\"key\":\"" << debug_json_escape(item.plan.key) << '"'
                    << ",\"name\":\"" << debug_json_escape(item.plan.name) << '"'
                    << ",\"base_name\":\"" << debug_json_escape(item.plan.base_name) << '"'
                    << ",\"lure_name\":\"" << debug_json_escape(item.plan.lure_name) << '"'
                    << ",\"lightning_name\":\"" << debug_json_escape(item.plan.lightning_name) << '"'
                    << ",\"first\":\"" << debug_json_escape(ops_text(item.plan.ops)) << '"'
                    << ",\"pretty\":\"" << debug_json_escape(pretty_ops_text(state, context.player, item.plan.ops)) << '"'
                    << ",\"second\":\"" << debug_json_escape(followup_text(item.plan.followup)) << '"'
                    << ",\"base_heuristic\":" << item.plan.base_heuristic
                    << ",\"lure_heuristic\":" << item.plan.lure_heuristic
                    << ",\"lightning_heuristic\":" << item.plan.lightning_heuristic
                    << ",\"operation_penalty\":" << item.plan.operation_penalty
                    << ",\"heuristic\":" << item.plan.heuristic
                    << ",\"score_before_heuristic\":" << item.mean_rollout_score
                    << ",\"score_before_penalty\":" << item.mean_score
                    << ",\"rollouts\":" << item.rollout_count
                    << ",\"mean_base_hp_raw\":" << item.mean_rollout.terminal.base_hp_raw
                    << ",\"mean_base_hp_score\":" << item.mean_rollout.terminal.base_hp_score
                    << ",\"mean_tower_value_raw\":" << item.mean_rollout.terminal.tower_value_raw
                    << ",\"mean_tower_value_score\":" << item.mean_rollout.terminal.tower_value_score
                    << ",\"mean_money_raw\":" << item.mean_rollout.terminal.money_raw
                    << ",\"mean_money_score\":" << item.mean_rollout.terminal.money_score
                    << ",\"mean_c1_bonus_raw\":" << item.mean_rollout.terminal.c1_bonus_raw
                    << ",\"mean_c1_bonus_score\":" << item.mean_rollout.terminal.c1_bonus_score
                    << ",\"mean_worker_threat_raw\":" << item.mean_rollout.terminal.worker_threat_raw
                    << ",\"mean_worker_threat_score\":" << item.mean_rollout.terminal.worker_threat_score
                    << ",\"mean_combat_threat_raw\":" << item.mean_rollout.terminal.combat_threat_raw
                    << ",\"mean_combat_threat_score\":" << item.mean_rollout.terminal.combat_threat_score
                    << ",\"mean_terminal_score\":" << item.mean_rollout.terminal.total_score
                    << ",\"mean_lightning_bonus_raw\":" << item.mean_rollout.lightning_bonus_raw
                    << ",\"mean_lightning_bonus_score\":" << item.mean_rollout.lightning_bonus_score
                    << ",\"mean_reactive_operation_penalty\":" << item.mean_rollout.reactive_operation_penalty
                    << ",\"score\":" << item.mean_score
                    << "}\n";
            }
        }

        int enemy_ant_count = 0;
        int enemy_combat_ring1 = 0;
        int enemy_combat_ring2 = 0;
        double combat_pressure = 0.0;
        double tower_pressure = 0.0;
        const auto [base_x, base_y] = kPlayerBases[context.player];
        for (const auto &ant : state.ants) {
            if (ant.player == context.player || !ant.is_alive()) {
                continue;
            }
            ++enemy_ant_count;
            if (ant.kind == AntKind::Combat) {
                const int d = hex_distance(ant.x, ant.y, base_x, base_y);
                if (d <= 1) {
                    ++enemy_combat_ring1;
                }
                if (d <= 2) {
                    ++enemy_combat_ring2;
                }
                combat_pressure += 1.0 / std::max(1, d);
            }
        }
        for (const auto &tower : state.towers) {
            if (tower.player != context.player || !is_base_slot_code(code_at(tower, context.player))) {
                continue;
            }
            for (const auto &ant : state.ants) {
                if (ant.player == context.player || ant.kind != AntKind::Combat || !ant.is_alive()) {
                    continue;
                }
                tower_pressure += 1.0 / std::max(1, hex_distance(ant.x, ant.y, tower.x, tower.y));
            }
        }

        const auto &best = evaluated.empty() ? CombinedPlan{} : evaluated.front().plan;
        const auto &best_eval = evaluated.empty() ? EvaluatedPlan{} : evaluated.front();
        std::cerr
            << "{\"kind\":\"decision\""
            << ",\"round\":" << state.round_index
            << ",\"player\":" << context.player
            << ",\"serial\":" << serial
            << ",\"base_candidates\":" << root_plans.base_count
            << ",\"lure_candidates\":" << root_plans.lure_count
            << ",\"lightning_candidates\":" << root_plans.lightning_count
            << ",\"raw_combo_count\":" << root_plans.raw_combo_count
            << ",\"raw_plan_count\":" << root_plans.raw_plan_count
            << ",\"plans_total\":" << root_plans.plans.size()
            << ",\"plans_unique\":" << root_plans.plans.size()
            << ",\"best_key\":\"" << debug_json_escape(best.key.empty() ? "hold" : best.key) << '"'
            << ",\"best_name\":\"" << debug_json_escape(best.name.empty() ? "hold" : best.name) << '"'
            << ",\"best_base_name\":\"" << debug_json_escape(best.base_name.empty() ? "none" : best.base_name) << '"'
            << ",\"best_lure_name\":\"" << debug_json_escape(best.lure_name.empty() ? "none" : best.lure_name) << '"'
            << ",\"best_lightning_name\":\"" << debug_json_escape(best.lightning_name.empty() ? "none" : best.lightning_name) << '"'
            << ",\"best_first\":\"" << debug_json_escape(ops_text(best.ops)) << '"'
            << ",\"best_pretty\":\"" << debug_json_escape(pretty_ops_text(state, context.player, best.ops)) << '"'
            << ",\"best_second\":\"" << debug_json_escape(followup_text(best.followup)) << '"'
            << ",\"action_legend\":\"" << action_legend_text() << '"'
            << ",\"best_base_heuristic\":" << best.base_heuristic
            << ",\"best_lure_heuristic\":" << best.lure_heuristic
            << ",\"best_lightning_heuristic\":" << best.lightning_heuristic
            << ",\"best_operation_penalty\":" << best.operation_penalty
            << ",\"best_heuristic\":" << best.heuristic
            << ",\"best_score_before_heuristic\":" << best_eval.mean_rollout_score
            << ",\"best_mean_base_hp_raw\":" << best_eval.mean_rollout.terminal.base_hp_raw
            << ",\"best_mean_base_hp_score\":" << best_eval.mean_rollout.terminal.base_hp_score
            << ",\"best_mean_tower_value_raw\":" << best_eval.mean_rollout.terminal.tower_value_raw
            << ",\"best_mean_tower_value_score\":" << best_eval.mean_rollout.terminal.tower_value_score
            << ",\"best_mean_money_raw\":" << best_eval.mean_rollout.terminal.money_raw
            << ",\"best_mean_money_score\":" << best_eval.mean_rollout.terminal.money_score
            << ",\"best_mean_c1_bonus_raw\":" << best_eval.mean_rollout.terminal.c1_bonus_raw
            << ",\"best_mean_c1_bonus_score\":" << best_eval.mean_rollout.terminal.c1_bonus_score
            << ",\"best_mean_worker_threat_raw\":" << best_eval.mean_rollout.terminal.worker_threat_raw
            << ",\"best_mean_worker_threat_score\":" << best_eval.mean_rollout.terminal.worker_threat_score
            << ",\"best_mean_combat_threat_raw\":" << best_eval.mean_rollout.terminal.combat_threat_raw
            << ",\"best_mean_combat_threat_score\":" << best_eval.mean_rollout.terminal.combat_threat_score
            << ",\"best_mean_terminal_score\":" << best_eval.mean_rollout.terminal.total_score
            << ",\"best_mean_lightning_bonus_raw\":" << best_eval.mean_rollout.lightning_bonus_raw
            << ",\"best_mean_lightning_bonus_score\":" << best_eval.mean_rollout.lightning_bonus_score
            << ",\"best_mean_reactive_operation_penalty\":" << best_eval.mean_rollout.reactive_operation_penalty
            << ",\"coins\":" << state.coins[context.player]
            << ",\"base_hp\":" << state.bases[context.player].hp
            << ",\"tower_count\":" << state.tower_count(context.player)
            << ",\"root_enemy_ants\":\"" << debug_json_escape(enemy_ant_state_text(state, context.player)) << '"'
            << ",\"sim_enemy_ants\":\"" << debug_json_escape(sim_enemy_ant_state_text(defense_root)) << '"'
            << ",\"root_own_towers\":\"" << debug_json_escape(own_tower_state_text(state, context.player)) << '"'
            << ",\"enemy_ant_count\":" << enemy_ant_count
            << ",\"enemy_combat_ring1\":" << enemy_combat_ring1
            << ",\"enemy_combat_ring2\":" << enemy_combat_ring2
            << ",\"combat_pressure\":" << combat_pressure
            << ",\"tower_pressure\":" << tower_pressure
            << ",\"best_score\":" << (evaluated.empty() ? 0.0 : evaluated.front().mean_score)
            << ",\"elapsed_us\":" << elapsed_us
            << "}\n";
    }

    if (evaluated.empty()) {
        return {};
    }
    return evaluated.front().plan.ops;
}

inline std::vector<Operation> decide_lure_strategy(const PublicState &state, int player) {
    LureStrategyDecisionContext context;
    context.state = &state;
    context.player = player;
    return decide_lure_strategy(context, nullptr);
}

} // namespace antgame::sdk
