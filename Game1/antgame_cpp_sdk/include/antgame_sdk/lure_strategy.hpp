#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "antgame_sdk/lure_strategy_params.hpp"
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
    std::array<int, 2> last_round_seen = {-1, -1};
    std::array<std::uint64_t, 2> decision_serial = {0, 0};

    void observe(const PublicState &state, int player) {
        if (last_round_seen[player] == state.round_index) {
            return;
        }
        last_round_seen[player] = state.round_index;
        ++decision_serial[player];
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
    for (std::size_t index = 0; index < operations.size(); ++index) {
        if (index) {
            oss << ';';
        }
        oss << pretty_op_text(state, player, operations[index]);
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
    case L1:
    case R1:
    case C2:
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

inline std::array<int, 3> near_base_codes() {
    return {L1, R1, C2};
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
        return lure_config().randomized_threat_scale;
    }
    if (behavior == AntBehavior::Bewitched) {
        return lure_config().bewitched_threat_scale;
    }
    return 1.0;
}

struct WeightedDefenseState {
    rs::DefenseSimulator simulator;
    double weight = 1.0;
};

inline double combat_threat_at(const PublicState &state, int player, const Ant &ant, int x, int y);
inline double combat_threat_at(const rs::DefenseSimulator &simulator, int player, const rs::SearchAnt &ant, int x, int y);

inline int distance_to_boundary(int x, int y) {
    int best = std::min({x, y, kMapSize - 1 - x, kMapSize - 1 - y});
    for (int ny = 0; ny < kMapSize; ++ny) {
        if (!is_valid_pos(x, ny)) {
            best = std::min(best, std::abs(y - ny));
        }
    }
    for (int nx = 0; nx < kMapSize; ++nx) {
        if (!is_valid_pos(nx, y)) {
            best = std::min(best, std::abs(x - nx));
        }
    }
    return best;
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

inline std::vector<WeightedDefenseState> project_future_states(
    const rs::DefenseSimulator &root,
    int horizon,
    int samples,
    std::uint64_t seed_salt) {
    std::vector<WeightedDefenseState> out;
    out.push_back(WeightedDefenseState{root.clone(), 1.0});
    if (horizon <= 0 || samples <= 0) {
        return out;
    }

    const double per_sample = 1.0 / static_cast<double>(std::max(samples, 1));
    for (int sample = 0; sample < samples; ++sample) {
        rs::DefenseSimulator branch = root.clone();
        rs::FastRng rng(mix_seed(seed_salt, static_cast<std::uint64_t>((root.round_index + 1) * 131 + sample + 1)));
        double weight = per_sample;
        for (int step = 1; step <= horizon && !branch.terminal; ++step) {
            branch.simulate_round(rng);
            weight *= lure_config().projected_state_decay;
            out.push_back(WeightedDefenseState{branch.clone(), weight});
        }
    }
    return out;
}

struct SinglePlan {
    enum class Followup : int {
        None = 0,
        C1UpgradeMortar = 1,
        C1UpgradeQuick = 2,
    };

    std::string name;
    std::vector<Operation> ops;
    double heuristic = 0.0;
    Followup followup = Followup::None;
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
    bool has_lightning = false;
    int horizon = 0;
    SinglePlan::Followup followup = SinglePlan::Followup::None;
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
    double total_score = 0.0;

    RolloutEvaluation &operator+=(const RolloutEvaluation &other) {
        terminal += other.terminal;
        lightning_bonus_raw += other.lightning_bonus_raw;
        lightning_bonus_score += other.lightning_bonus_score;
        total_score += other.total_score;
        return *this;
    }

    RolloutEvaluation scaled(double factor) const {
        RolloutEvaluation out = *this;
        out.terminal = out.terminal.scaled(factor);
        out.lightning_bonus_raw *= factor;
        out.lightning_bonus_score *= factor;
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

inline const char *followup_name(SinglePlan::Followup followup) {
    switch (followup) {
    case SinglePlan::Followup::C1UpgradeMortar:
        return "C1_to_Mortar";
    case SinglePlan::Followup::C1UpgradeQuick:
        return "C1_to_Quick";
    case SinglePlan::Followup::None:
    default:
        return "";
    }
}

inline std::string followup_key(SinglePlan::Followup followup) {
    switch (followup) {
    case SinglePlan::Followup::C1UpgradeMortar:
        return "F:C1M";
    case SinglePlan::Followup::C1UpgradeQuick:
        return "F:C1Q";
    case SinglePlan::Followup::None:
    default:
        return "";
    }
}

inline std::string followup_text(SinglePlan::Followup followup) {
    switch (followup) {
    case SinglePlan::Followup::C1UpgradeMortar:
        return "C1-8";
    case SinglePlan::Followup::C1UpgradeQuick:
        return "C1-3";
    case SinglePlan::Followup::None:
    default:
        return "";
    }
}

inline std::string plan_key(const std::vector<Operation> &operations, SinglePlan::Followup followup) {
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
        if (nearest > lure_config().forced_lure_sell_distance) {
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
        if (nearest > lure_config().forced_lure_sell_distance) {
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
        if (nearest > lure_config().forced_lure_sell_distance) {
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

inline std::vector<SinglePlan> generate_base_candidates(const PublicState &state, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"base_hold", {}, lure_config().base_hold_bonus});

    const int coins = state.coins[player];
    const Tower *c1 = tower_at_code(state, player, C1);

    if (c1 == nullptr) {
        const Operation build = build_at_code(player, C1);
        if (!legalize_operations(state, player, {build}).empty()) {
            plans.push_back(SinglePlan{"base_build_C1", {build}, lure_config().c1_build_bonus});
            plans.push_back(SinglePlan{
                "base_build_C1_then_Mortar",
                {build},
                lure_config().c1_build_bonus,
                SinglePlan::Followup::C1UpgradeMortar,
            });
            plans.push_back(SinglePlan{
                "base_build_C1_then_Quick",
                {build},
                lure_config().c1_build_bonus,
                SinglePlan::Followup::C1UpgradeQuick,
            });
        }
        return plans;
    }

    append_downgrade_candidate(state, player, c1, "base_C1_downgrade", plans);

    if (c1->tower_type != TowerType::Sniper) {
        if (c1->tower_type == TowerType::Basic) {
            if (coins < lure_config().c1_quick_transition_coin_threshold) {
                const Operation upgrade(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(TowerType::Mortar));
                if (!legalize_operations(state, player, {upgrade}).empty()) {
                    plans.push_back(SinglePlan{"base_C1_to_Mortar", {upgrade}, 0.0});
                }
            } else {
                const Operation upgrade(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(TowerType::Quick));
                if (!legalize_operations(state, player, {upgrade}).empty()) {
                    plans.push_back(SinglePlan{"base_C1_to_Quick", {upgrade}, 0.0});
                }
                const Operation mortar_upgrade(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(TowerType::Mortar));
                if (!legalize_operations(state, player, {mortar_upgrade}).empty()) {
                    plans.push_back(SinglePlan{"base_C1_to_Mortar", {mortar_upgrade}, 0.0});
                }
            }
        } else if (c1->tower_type == TowerType::Quick) {
            const Operation upgrade(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(TowerType::Sniper));
            if (!legalize_operations(state, player, {upgrade}).empty()) {
                plans.push_back(SinglePlan{"base_C1_to_Sniper", {upgrade}, 0.0});
            }
        } else if (c1->tower_type == TowerType::Mortar) {
            plans.push_back(SinglePlan{
                "base_C1_downgrade_then_Quick",
                {Operation(OperationType::DowngradeTower, c1->tower_id)},
                0.0,
                SinglePlan::Followup::C1UpgradeQuick,
            });
        }
        return plans;
    }

    for (int code : near_base_codes()) {
        const Tower *tower = tower_at_code(state, player, code);
        if (tower == nullptr) {
            const Operation build = build_at_code(player, code);
            if (!legalize_operations(state, player, {build}).empty()) {
                plans.push_back(SinglePlan{"base_build_" + code_name(code), {build}, 0.0});
            }
            continue;
        }
        append_downgrade_candidate(state, player, tower, "base_" + code_name(code) + "_downgrade", plans);
        if (tower->tower_type == TowerType::Basic) {
            const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Quick));
            if (!legalize_operations(state, player, {upgrade}).empty()) {
                plans.push_back(SinglePlan{"base_" + code_name(code) + "_to_Quick", {upgrade}, 0.0});
            }
        } else if (tower->tower_type == TowerType::Quick) {
            const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Sniper));
            if (!legalize_operations(state, player, {upgrade}).empty()) {
                plans.push_back(SinglePlan{"base_" + code_name(code) + "_to_Sniper", {upgrade}, 0.0});
            }
        }
    }

    return plans;
}

inline std::vector<SinglePlan> generate_base_candidates(const rs::DefenseSimulator &simulator, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"base_hold", {}, lure_config().base_hold_bonus});

    const int coins = static_cast<int>(std::floor(simulator.coins + 1e-9));
    const rs::SearchTower *c1 = tower_at_code(simulator, player, C1);

    if (c1 == nullptr) {
        const Operation build = build_at_code(player, C1);
        if (!legalize_operations(simulator, {build}).empty()) {
            plans.push_back(SinglePlan{"base_build_C1", {build}, lure_config().c1_build_bonus});
        }
        return plans;
    }

    append_downgrade_candidate(simulator, player, c1, "base_C1_downgrade", plans);

    if (c1->tower_type != TowerType::Sniper) {
        if (c1->tower_type == TowerType::Basic) {
            if (coins < lure_config().c1_quick_transition_coin_threshold) {
                const Operation mortar(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(TowerType::Mortar));
                if (!legalize_operations(simulator, {mortar}).empty()) {
                    plans.push_back(SinglePlan{"base_C1_to_Mortar", {mortar}, 0.0});
                }
            } else {
                const Operation quick(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(TowerType::Quick));
                if (!legalize_operations(simulator, {quick}).empty()) {
                    plans.push_back(SinglePlan{"base_C1_to_Quick", {quick}, 0.0});
                }
                const Operation mortar(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(TowerType::Mortar));
                if (!legalize_operations(simulator, {mortar}).empty()) {
                    plans.push_back(SinglePlan{"base_C1_to_Mortar", {mortar}, 0.0});
                }
            }
        } else if (c1->tower_type == TowerType::Quick) {
            const Operation sniper(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(TowerType::Sniper));
            if (!legalize_operations(simulator, {sniper}).empty()) {
                plans.push_back(SinglePlan{"base_C1_to_Sniper", {sniper}, 0.0});
            }
        }
        return plans;
    }

    for (int code : near_base_codes()) {
        const rs::SearchTower *tower = tower_at_code(simulator, player, code);
        if (tower == nullptr) {
            const Operation build = build_at_code(player, code);
            if (!legalize_operations(simulator, {build}).empty()) {
                plans.push_back(SinglePlan{"base_build_" + code_name(code), {build}, 0.0});
            }
            continue;
        }
        append_downgrade_candidate(simulator, player, tower, "base_" + code_name(code) + "_downgrade", plans);
        if (tower->tower_type == TowerType::Basic) {
            const Operation quick(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Quick));
            if (!legalize_operations(simulator, {quick}).empty()) {
                plans.push_back(SinglePlan{"base_" + code_name(code) + "_to_Quick", {quick}, 0.0});
            }
        } else if (tower->tower_type == TowerType::Quick) {
            const Operation sniper(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Sniper));
            if (!legalize_operations(simulator, {sniper}).empty()) {
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
    plans.push_back(SinglePlan{"lure_hold", {}, lure_config().lure_hold_bonus});

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
    plans.push_back(SinglePlan{"lure_hold", {}, lure_config().lure_hold_bonus});

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
    const int strikes = lightning_tower_strikes_within_horizon(lure_config().lightning_horizon);
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
        score += (before - after) * lure_config().tower_value_weight * lure_config().lightning_tower_value_ratio;
    }
    return score;
}

inline double lightning_cell_score(
    const PublicState &state,
    const std::vector<WeightedDefenseState> &projections,
    int player,
    int x,
    int y) {
    double score = enemy_tower_lightning_damage_score(state, player, x, y);
    if (enemy_super_effect_active(state, player)) {
        score += lure_config().lightning_enemy_super_bonus;
    }

    for (std::size_t index = 0; index < projections.size(); ++index) {
        const auto &view = projections[index];
        for (const auto &ant : view.simulator.ants) {
            if (!ant.alive()) {
                continue;
            }
            if (hex_distance(x, y, ant.x, ant.y) > weapon_stats(SuperWeaponType::LightningStorm).attack_range) {
                continue;
            }
            if (ant.kind == AntKind::Combat) {
                score += view.weight * combat_threat_at(view.simulator, player, ant, ant.x, ant.y) *
                         lure_config().lightning_combat_threat_ratio;
                if (index == 0 && ant.shield > 0) {
                    score += lure_config().lightning_shield_break_bonus;
                }
            }
        }
    }
    return score;
}

inline std::vector<SinglePlan> generate_lightning_center_candidates(
    const PublicState &state,
    const rs::DefenseSimulator *simulator,
    int player) {
    std::vector<SinglePlan> plans;
    if (state.weapon_cooldowns[player][static_cast<int>(SuperWeaponType::LightningStorm)] > 0) {
        return plans;
    }

    struct CellScore {
        double score = 0.0;
        int x = -1;
        int y = -1;
    };
    const auto projections = simulator != nullptr
                                 ? project_future_states(
                                       *simulator,
                                       lure_config().lightning_projection_horizon,
                                       lure_config().lightning_projection_samples,
                                       0x4c49474854ULL)
                                 : std::vector<WeightedDefenseState>{};
    std::vector<CellScore> scored;
    scored.reserve(kMapSize * kMapSize);
    for (int x = 0; x < kMapSize; ++x) {
        for (int y = 0; y < kMapSize; ++y) {
            if (!is_valid_pos(x, y)) {
                continue;
            }
            if (distance_to_boundary(x, y) < lure_config().lightning_min_boundary_distance) {
                continue;
            }
            const double score = lightning_cell_score(state, projections, player, x, y);
            if (score <= 0.0) {
                continue;
            }
            scored.push_back(CellScore{score, x, y});
        }
    }
    std::sort(scored.begin(), scored.end(), [](const CellScore &lhs, const CellScore &rhs) {
        return lhs.score > rhs.score;
    });

    std::vector<CellScore> selected;
    for (const auto &cell : scored) {
        bool too_close = false;
        for (const auto &keep : selected) {
            if (hex_distance(cell.x, cell.y, keep.x, keep.y) <= lure_config().lightning_cluster_separation) {
                too_close = true;
                break;
            }
        }
        if (too_close) {
            continue;
        }
        selected.push_back(cell);
        if (static_cast<int>(selected.size()) >= lure_config().lightning_center_limit) {
            break;
        }
    }

    for (const auto &cell : selected) {
        plans.push_back(SinglePlan{
            "lightning_" + std::to_string(cell.x) + "_" + std::to_string(cell.y),
            {Operation(OperationType::UseLightningStorm, cell.x, cell.y)},
            cell.score,
        });
    }
    return plans;
}

inline std::vector<SinglePlan> generate_lightning_prep_candidates(const PublicState &state, int player) {
    std::vector<SinglePlan> plans;
    plans.push_back(SinglePlan{"lightning_hold", {}, 0.0});
    for (const auto &tower : state.towers) {
        if (tower.player != player) {
            continue;
        }
        const std::string action = tower.tower_type == TowerType::Basic ? "lightning_sell_" : "lightning_downgrade_";
        append_downgrade_candidate(state, player, &tower, action + tower_slot_name(tower, player), plans);
    }
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
    out.lightning_count = static_cast<int>(lightning_prep.size() * lightning_center.size());
    out.raw_combo_count = out.base_count * out.lure_count;
    out.raw_plan_count = out.raw_combo_count + out.lightning_count;

    std::vector<CombinedPlan> &plans = out.plans;
    std::unordered_map<std::string, std::size_t> seen;
    for (const auto &base_plan : base) {
        for (const auto &lure_plan : lure) {
            std::vector<Operation> raw;
            raw.insert(raw.end(), base_plan.ops.begin(), base_plan.ops.end());
            raw.insert(raw.end(), lure_plan.ops.begin(), lure_plan.ops.end());
            std::vector<Operation> combined = legalize_operations(state, player, raw);
            if (!raw.empty() && combined.empty()) {
                continue;
            }
            const SinglePlan no_lightning{"no_lightning", {}, 0.0};
            const std::string key = plan_key(combined, base_plan.followup);
            const double heuristic = base_plan.heuristic + lure_plan.heuristic;
            auto it = seen.find(key);
            if (it == seen.end()) {
                CombinedPlan item;
                item.key = key;
                item.name = summarize_plan_name(base_plan, lure_plan, no_lightning);
                item.base_name = base_plan.name;
                item.lure_name = lure_plan.name;
                item.lightning_name = no_lightning.name;
                item.ops = std::move(combined);
                item.heuristic = heuristic;
                item.base_heuristic = base_plan.heuristic;
                item.lure_heuristic = lure_plan.heuristic;
                item.lightning_heuristic = 0.0;
                item.has_lightning = false;
                item.horizon = lure_config().search_horizon;
                item.followup = base_plan.followup;
                seen.emplace(key, plans.size());
                plans.push_back(std::move(item));
            } else if (heuristic > plans[it->second].heuristic) {
                plans[it->second].name = summarize_plan_name(base_plan, lure_plan, no_lightning);
                plans[it->second].base_name = base_plan.name;
                plans[it->second].lure_name = lure_plan.name;
                plans[it->second].lightning_name = no_lightning.name;
                plans[it->second].heuristic = heuristic;
                plans[it->second].base_heuristic = base_plan.heuristic;
                plans[it->second].lure_heuristic = lure_plan.heuristic;
                plans[it->second].lightning_heuristic = 0.0;
                plans[it->second].has_lightning = false;
                plans[it->second].horizon = lure_config().search_horizon;
                plans[it->second].followup = base_plan.followup;
            }
        }
    }

    for (const auto &prep_plan : lightning_prep) {
        for (const auto &center_plan : lightning_center) {
            std::vector<Operation> raw_lightning;
            raw_lightning.insert(raw_lightning.end(), prep_plan.ops.begin(), prep_plan.ops.end());
            raw_lightning.insert(raw_lightning.end(), center_plan.ops.begin(), center_plan.ops.end());
            std::vector<Operation> lightning_ops = legalize_operations(state, player, raw_lightning);
            if (!raw_lightning.empty() && lightning_ops.empty()) {
                continue;
            }
            SinglePlan lightning_plan;
            lightning_plan.name = prep_plan.name + '+' + center_plan.name;
            lightning_plan.ops = center_plan.ops;
            lightning_plan.heuristic = prep_plan.heuristic + center_plan.heuristic;
            const std::string lightning_key = plan_key(lightning_ops, SinglePlan::Followup::None);
            const double lightning_heuristic = lightning_plan.heuristic;
            auto it = seen.find(lightning_key);
            if (it == seen.end()) {
                CombinedPlan item;
                item.key = lightning_key;
                item.name = lightning_plan.name;
                item.base_name = "none";
                item.lure_name = "none";
                item.lightning_name = lightning_plan.name;
                item.ops = std::move(lightning_ops);
                item.heuristic = lightning_heuristic;
                item.base_heuristic = 0.0;
                item.lure_heuristic = 0.0;
                item.lightning_heuristic = lightning_plan.heuristic;
                item.has_lightning = true;
                item.horizon = lure_config().lightning_horizon;
                item.followup = SinglePlan::Followup::None;
                seen.emplace(lightning_key, plans.size());
                plans.push_back(std::move(item));
            } else if (lightning_heuristic > plans[it->second].heuristic) {
                plans[it->second].name = lightning_plan.name;
                plans[it->second].base_name = "none";
                plans[it->second].lure_name = "none";
                plans[it->second].lightning_name = lightning_plan.name;
                plans[it->second].heuristic = lightning_heuristic;
                plans[it->second].base_heuristic = 0.0;
                plans[it->second].lure_heuristic = 0.0;
                plans[it->second].lightning_heuristic = lightning_plan.heuristic;
                plans[it->second].has_lightning = true;
                plans[it->second].horizon = lure_config().lightning_horizon;
                plans[it->second].followup = SinglePlan::Followup::None;
            }
        }
    }

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

    for (const auto &base_plan : base) {
        for (const auto &lure_plan : lure) {
            std::vector<Operation> raw;
            raw.insert(raw.end(), base_plan.ops.begin(), base_plan.ops.end());
            raw.insert(raw.end(), lure_plan.ops.begin(), lure_plan.ops.end());
            std::vector<Operation> combined = legalize_operations(simulator, raw);
            if (!raw.empty() && combined.empty()) {
                continue;
            }
            const double heuristic = base_plan.heuristic + lure_plan.heuristic;
            if (heuristic > best_heuristic) {
                best_heuristic = heuristic;
                best_ops = std::move(combined);
            }
        }
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

inline std::vector<Operation> resolve_followup_operations(
    const rs::DefenseSimulator &simulator,
    int player,
    SinglePlan::Followup followup) {
    if (followup == SinglePlan::Followup::None) {
        return {};
    }
    const rs::SearchTower *c1 = tower_at_code(simulator, player, C1);
    if (c1 == nullptr || !c1->alive() || c1->tower_type != TowerType::Basic) {
        return {};
    }

    TowerType target = TowerType::Basic;
    switch (followup) {
    case SinglePlan::Followup::C1UpgradeMortar:
        target = TowerType::Mortar;
        break;
    case SinglePlan::Followup::C1UpgradeQuick:
        target = TowerType::Quick;
        break;
    case SinglePlan::Followup::None:
    default:
        return {};
    }

    const Operation upgrade(OperationType::UpgradeTower, c1->tower_id, static_cast<int>(target));
    return legalize_operations(simulator, {upgrade});
}

inline double worker_threat_score(const PublicState &state, int player) {
    const auto [base_x, base_y] = kPlayerBases[player];
    double threat = 0.0;
    for (const auto &ant : state.ants) {
        if (ant.player == player || ant.kind != AntKind::Worker || !ant.is_alive()) {
            continue;
        }
        const int distance = std::max(1, hex_distance(ant.x, ant.y, base_x, base_y));
        threat += lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
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
        double tower_threat = value * lure_config().combat_anchor_threat_coin_ratio / distance;
        if (distance <= 1) {
            tower_threat += value * lure_config().combat_anchor_ring1_bonus_ratio;
        }
        threat = std::max(threat, tower_threat);
    }
    return threat;
}

inline double combat_threat_at(const PublicState &state, int player, const Ant &ant, int x, int y) {
    const auto [base_x, base_y] = kPlayerBases[player];
    const int distance = std::max(1, hex_distance(x, y, base_x, base_y));
    double threat = lure_config().combat_base_threat_unit / distance;
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
        threat += lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
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
        double tower_threat = value * lure_config().combat_anchor_threat_coin_ratio / distance;
        if (distance <= 1) {
            tower_threat += value * lure_config().combat_anchor_ring1_bonus_ratio;
        }
        threat = std::max(threat, tower_threat);
    }
    return threat;
}

inline double combat_threat_at(const rs::DefenseSimulator &simulator, int player, const rs::SearchAnt &ant, int x, int y) {
    const auto [base_x, base_y] = kPlayerBases[player];
    const int distance = std::max(1, hex_distance(x, y, base_x, base_y));
    double threat = lure_config().combat_base_threat_unit / distance;
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
    double threat = lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
    if (ant.behavior == AntBehavior::Random) {
        threat *= lure_config().randomized_threat_scale;
    } else if (ant.behavior == AntBehavior::Bewitched) {
        threat *= lure_config().bewitched_threat_scale;
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

    const int limit = std::min(lure_config().rollout_forced_ant_limit, rs::kMaxImportantAnts);
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
    int /*player*/) {
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
            bonus += lure_config().lightning_shield_break_bonus;
        }
        const int damage = std::max(0, ant.hp - with_hp);
        bonus += static_cast<double>(damage) * lure_config().lightning_damage_bonus_per_hp;
        if (with_ant == nullptr) {
            bonus += lure_config().lightning_kill_bonus;
        }
    }
    return bonus;
}

inline double c1_state_bonus(TowerType tower_type, bool transition_phase) {
    switch (tower_type) {
    case TowerType::Mortar:
    case TowerType::MortarPlus:
    case TowerType::Ice:
    case TowerType::Bewitch:
        return transition_phase ? lure_config().c1_heavy_side_trans_bonus : lure_config().c1_heavy_bonus;
    case TowerType::Quick:
    case TowerType::QuickPlus:
    case TowerType::Double:
        return transition_phase ? lure_config().c1_quick_trans_bonus : 0.0;
    case TowerType::Sniper:
        return transition_phase ? lure_config().c1_sniper_trans_bonus : 0.0;
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
        root_coins > static_cast<double>(lure_config().c1_quick_transition_coin_threshold);
    return c1_state_bonus(c1->tower_type, transition_phase);
}

inline double c1_terminal_bonus(const rs::DefenseSimulator &, int) {
    return 0.0;
}

inline EvalBreakdown evaluate_terminal(const rs::DefenseSimulator &simulator, int player) {
    EvalBreakdown out;
    out.base_hp_raw = static_cast<double>(simulator.base_hp);
    out.base_hp_score = out.base_hp_raw * lure_config().base_hp_weight;
    out.tower_value_raw = tower_full_salvage_value(simulator);
    out.tower_value_score = out.tower_value_raw * lure_config().tower_value_weight;
    out.money_raw = simulator.coins;
    out.money_score = out.money_raw * lure_config().money_weight;
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
        out.lightning_bonus_raw = lightning_counterfactual_bonus(simulator, control, player);
        out.lightning_bonus_score = out.lightning_bonus_raw;
    }
    int step = 1;
    if (plan.followup != SinglePlan::Followup::None && step < plan.horizon && !simulator.terminal) {
        const auto followup_ops = resolve_followup_operations(simulator, player, plan.followup);
        apply_operations(simulator, followup_ops);
        simulator.simulate_round(rng);
        ++step;
    }
    for (; step < plan.horizon && !simulator.terminal; ++step) {
        apply_reactive_turn_operations(simulator, player);
        simulator.simulate_round(rng);
    }
    out.terminal = evaluate_terminal(simulator, player);
    out.total_score = out.terminal.total_score + out.lightning_bonus_score;
    return out;
}

struct EvaluatedPlan {
    std::size_t root_index = 0;
    CombinedPlan plan;
    RolloutEvaluation mean_rollout;
    double mean_rollout_score = -std::numeric_limits<double>::infinity();
    double mean_score = -std::numeric_limits<double>::infinity();
    double rollout_weight_sum = 0.0;
};

inline std::vector<EvaluatedPlan> evaluate_root_plans(
    const PublicState &state,
    const rs::DefenseSimulator &defense_root,
    int player,
    std::uint64_t serial,
    int rollout_count,
    const RootPlanSet &root_plans) {
    const int effective_rollouts = rollout_count > 0 ? rollout_count : std::max(1, lure_config().rollout_count);
    std::vector<EvaluatedPlan> evaluated;
    evaluated.reserve(root_plans.plans.size());

    for (std::size_t index = 0; index < root_plans.plans.size(); ++index) {
        const auto &plan = root_plans.plans[index];
        EvaluatedPlan item;
        item.root_index = index;
        item.plan = plan;

        rs::DefenseSimulator plan_root = defense_root.clone();
        if (!plan.ops.empty() && !apply_operations(plan_root, plan.ops)) {
            item.mean_rollout_score = -std::numeric_limits<double>::infinity();
            item.mean_score = -std::numeric_limits<double>::infinity();
            evaluated.push_back(item);
            continue;
        }

        const RolloutForcedPlan forced_plan = build_first_round_rollout_plan(
            plan_root,
            player,
            effective_rollouts,
            plan_rollout_assignment_seed(state.seed, serial, index, plan.horizon, effective_rollouts));

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
                plan_rollout_seed(state.seed, serial, index, rollout, plan.horizon),
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
            evaluated.push_back(item);
            continue;
        }

        item.rollout_weight_sum = weight_sum;
        item.mean_rollout = weighted_total.scaled(1.0 / weight_sum);
        const double root_c1_bonus = c1_root_bonus(plan_root, player, defense_root.coins);
        item.mean_rollout.terminal.c1_bonus_raw = root_c1_bonus;
        item.mean_rollout.terminal.c1_bonus_score = root_c1_bonus;
        item.mean_rollout.terminal.total_score += root_c1_bonus;
        item.mean_rollout.total_score += root_c1_bonus;
        item.mean_rollout_score = item.mean_rollout.total_score;
        item.mean_score = item.mean_rollout_score + plan.heuristic;
        evaluated.push_back(item);
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
    rs::DefenseSimulator defense_root = rs::make_defense_simulator(state, context.simulator, context.player);
    defense_root.ignore_enemy_spawns = true;
    const RootPlanSet root_plans = generate_root_plans(state, &defense_root, context.player);

    const std::uint64_t serial = session != nullptr ? session->decision_serial[context.player] : 0ULL;
    const std::vector<EvaluatedPlan> evaluated =
        evaluate_root_plans(state, defense_root, context.player, serial, lure_config().rollout_count, root_plans);

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
                    << ",\"heuristic\":" << item.plan.heuristic
                    << ",\"score_before_heuristic\":" << item.mean_rollout_score
                    << ",\"score_before_penalty\":" << item.mean_score
                    << ",\"rollouts\":" << lure_config().rollout_count
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
            << ",\"coins\":" << state.coins[context.player]
            << ",\"base_hp\":" << state.bases[context.player].hp
            << ",\"tower_count\":" << state.tower_count(context.player)
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
