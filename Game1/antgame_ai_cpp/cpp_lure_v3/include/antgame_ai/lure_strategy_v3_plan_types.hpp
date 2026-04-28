#pragma once

#include "antgame_ai/lure_strategy_v3_core.hpp"

namespace antgame::sdk::lure_strategy_detail {

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

inline double combat_threat_at(const PublicState &state, int player, const Ant &ant, int x, int y);
inline double combat_threat_at(const rs::DefenseSimulator &simulator, int player, const rs::SearchAnt &ant, int x, int y);

inline bool is_lightning_center_candidate(int x, int y) {
    return is_valid_pos(x, y) &&
           hex_distance(kEdge - 1, kEdge - 1, x, y) <= v3_lure_config().lightning_center_radius;
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

} // namespace antgame::sdk::lure_strategy_detail
