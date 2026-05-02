#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

#include "antgame_ai/lure_strategy_v4_rollout_sampling.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline bool apply_operations(rs::DefenseSimulator &simulator, const std::vector<Operation> &operations) {
    for (const auto &operation : sort_operations(simulator, operations)) {
        if (!simulator.apply_operation(operation)) {
            return false;
        }
    }
    return true;
}

inline double c1_state_bonus(TowerType tower_type, bool transition_phase) {
    switch (tower_type) {
    case TowerType::Heavy:
    case TowerType::HeavyPlus:
    case TowerType::Ice:
    case TowerType::Bewitch:
        return transition_phase ? v4_lure_config().c1_heavy_side_trans_bonus : v4_lure_config().c1_heavy_bonus;
    case TowerType::Quick:
    case TowerType::QuickPlus:
    case TowerType::Double:
        return transition_phase ? v4_lure_config().c1_quick_trans_bonus : 0.0;
    case TowerType::Sniper:
        return transition_phase ? v4_lure_config().c1_sniper_trans_bonus : 0.0;
    default:
        return 0.0;
    }
}

inline double own_equivalent_total_coins(const rs::DefenseSimulator &simulator) {
    return simulator.coins + tower_full_salvage_value(simulator);
}

inline bool c1_transition_phase_from_action_start(const rs::DefenseSimulator &action_start) {
    return own_equivalent_total_coins(action_start) >=
           static_cast<double>(v4_lure_config().c1_quick_transition_coin_threshold);
}

inline double c1_root_bonus(const rs::DefenseSimulator &post_root, int player, bool transition_phase) {
    const rs::SearchTower *c1 = tower_at_code(post_root, player, C1);
    if (c1 == nullptr || !c1->alive()) {
        return 0.0;
    }
    return c1_state_bonus(c1->tower_type, transition_phase);
}

inline double c1_root_bonus_for_plan(
    const rs::DefenseSimulator &post_root,
    int player,
    const FollowupAction &followup,
    bool transition_phase) {
    if (followup.empty()) {
        return c1_root_bonus(post_root, player, transition_phase);
    }
    rs::DefenseSimulator projected = post_root.clone();
    int max_turn = 0;
    for (int index = 0; index < followup.count; ++index) {
        const FollowupStep &step = followup.steps[static_cast<std::size_t>(index)];
        if (!step.empty()) {
            max_turn = std::max(max_turn, step.turn);
        }
    }
    for (int turn = 1; turn <= max_turn; ++turn) {
        projected.update_income();
        ++projected.round_index;
        apply_operations(projected, resolve_followup_operations(projected, player, followup, turn));
    }
    return c1_root_bonus(projected, player, transition_phase);
}

inline double c1_terminal_bonus(const rs::DefenseSimulator &, int) {
    return 0.0;
}

inline double own_equivalent_money_score(double equivalent_money) {
    const double threshold = v4_lure_config().money_decay_threshold;
    const double below = std::min(equivalent_money, threshold);
    const double above = std::max(0.0, equivalent_money - threshold);
    return below * v4_lure_config().money_weight +
           above * v4_lure_config().money_weight_above_threshold;
}

struct FutureThreatProjection {
    double base_damage = 0.0;
    double base_damage_score = 0.0;
    double worker_threat = 0.0;
    double combat_threat = 0.0;
    double projected_threat = 0.0;
    double adjusted_threat = 0.0;
    double adjustment_score = 0.0;
};

inline bool future_move_option_attacks_tower(const rs::DefenseSimulator &simulator, const rs::MoveOption &option) {
    if (option.direction == rs::kNoMove) {
        return false;
    }
    return simulator.tower_at(option.nx, option.ny) != nullptr;
}

inline bool future_move_option_better(
    const rs::MoveOption &candidate,
    const rs::MoveOption &best,
    bool has_best,
    int player) {
    if (!has_best) {
        return true;
    }
    constexpr double kEps = 1e-12;
    if (std::fabs(candidate.probability - best.probability) > kEps) {
        return candidate.probability > best.probability;
    }
    if (std::fabs(candidate.danger - best.danger) > kEps) {
        return candidate.danger > best.danger;
    }
    const auto [base_x, base_y] = kPlayerBases[player];
    const int candidate_distance = hex_distance(candidate.nx, candidate.ny, base_x, base_y);
    const int best_distance = hex_distance(best.nx, best.ny, base_x, base_y);
    if (candidate_distance != best_distance) {
        return candidate_distance < best_distance;
    }
    return candidate.direction < best.direction;
}

inline rs::MoveOption future_best_non_attack_move_option(
    const rs::DefenseSimulator &simulator,
    const rs::SearchAnt &ant,
    int player) {
    rs::MoveOption best{rs::kNoMove, ant.x, ant.y, 1.0, 0.0};
    bool has_best = false;
    const auto options = simulator.move_options_for(ant);
    for (int index = 0; index < options.size(); ++index) {
        const rs::MoveOption &option = options[index];
        if (future_move_option_attacks_tower(simulator, option)) {
            continue;
        }
        if (future_move_option_better(option, best, has_best, player)) {
            best = option;
            has_best = true;
        }
    }
    return has_best ? best : rs::MoveOption{rs::kNoMove, ant.x, ant.y, 1.0, 0.0};
}

inline void future_non_attack_move_phase(rs::DefenseSimulator &simulator, int player) {
    simulator.ensure_move_cache(true);
    for (auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || ant.is_frozen) {
            continue;
        }
        const rs::MoveOption option = future_best_non_attack_move_option(simulator, ant, player);
        simulator.record_move_annotation_for_direction(ant, option.direction);
        if (option.direction == rs::kNoMove) {
            ant.last_move = rs::kNoMove;
            continue;
        }
        ant.x = option.nx;
        ant.y = option.ny;
        ant.last_move = option.direction;
        rs::mark_ant_trail(ant, ant.x, ant.y);
    }
}

inline void future_decay_effects_no_drift(rs::DefenseSimulator &simulator) {
    if (simulator.lightning_cooldown > 0) {
        --simulator.lightning_cooldown;
    }
    auto decay = [](auto &effects) {
        int write_index = 0;
        for (int read_index = 0; read_index < effects.size(); ++read_index) {
            auto effect = effects[read_index];
            if (effect.remaining_turns > 0) {
                --effect.remaining_turns;
            }
            if (effect.remaining_turns <= 0) {
                continue;
            }
            effects[write_index++] = effect;
        }
        effects.resize(write_index);
    };
    decay(simulator.my_effects);
    decay(simulator.enemy_effects);
    simulator.mark_risk_fields_dirty();
}

inline void simulate_future_threat_round(rs::DefenseSimulator &simulator, int player, rs::FastRng &rng) {
    if (simulator.terminal) {
        return;
    }
    simulator.tower_attack_phase(rng);
    future_non_attack_move_phase(simulator, player);
    if (v4_lure_config().future_threat_apply_teleport) {
        simulator.teleport_phase(rng);
    }
    simulator.decay_pheromone();
    simulator.manage_ants();
    simulator.increase_ant_age();
    if (v4_lure_config().future_threat_drift_effects) {
        simulator.update_effects(rng);
    } else {
        future_decay_effects_no_drift(simulator);
    }
    ++simulator.round_index;
    if (simulator.base_hp <= 0) {
        simulator.terminal = true;
    }
}

inline std::uint64_t future_threat_seed(const rs::DefenseSimulator &simulator, int player) {
    return 0x8f4c2e7b6a09d531ULL ^
           (static_cast<std::uint64_t>(std::max(0, simulator.round_index)) * 0x9e3779b185ebca87ULL) ^
           (static_cast<std::uint64_t>(player + 1) * 0xc2b2ae3d27d4eb4fULL);
}

inline FutureThreatProjection future_threat_projection(
    const rs::DefenseSimulator &simulator,
    int player,
    double static_threat) {
    FutureThreatProjection out;
    if (!v4_lure_config().future_threat_eval_enabled || v4_lure_config().future_threat_horizon <= 0) {
        return out;
    }

    rs::DefenseSimulator projected = simulator.clone();
    const int start_base_hp = projected.base_hp;
    rs::FastRng rng(future_threat_seed(projected, player));
    for (int step = 0; step < v4_lure_config().future_threat_horizon && !projected.terminal; ++step) {
        simulate_future_threat_round(projected, player, rng);
    }

    out.base_damage = static_cast<double>(std::max(0, start_base_hp - projected.base_hp));
    out.base_damage_score =
        out.base_damage * v4_lure_config().base_hp_weight * v4_lure_config().future_base_damage_scale;
    out.worker_threat = worker_threat_score(projected, player);
    out.combat_threat = combat_threat_score(projected, player);
    out.projected_threat =
        out.base_damage_score +
        out.worker_threat * v4_lure_config().future_worker_residual_scale +
        out.combat_threat * v4_lure_config().future_combat_residual_scale;

    const double blend = std::max(0.0, std::min(1.0, v4_lure_config().future_threat_blend));
    out.adjusted_threat = static_threat * (1.0 - blend) + out.projected_threat * blend;
    out.adjustment_score = static_threat - out.adjusted_threat;
    return out;
}

inline EvalBreakdown evaluate_terminal(const rs::DefenseSimulator &simulator, int player, bool apply_future_threat = true) {
    EvalBreakdown out;
    out.base_hp_raw = static_cast<double>(simulator.base_hp);
    out.base_hp_score = out.base_hp_raw * v4_lure_config().base_hp_weight;
    out.tower_value_raw = tower_full_salvage_value(simulator);
    out.money_raw = simulator.coins;
    const double equivalent_money = own_equivalent_total_coins(simulator);
    const double equivalent_money_score = own_equivalent_money_score(equivalent_money);
    if (equivalent_money > 0.0) {
        out.tower_value_score = equivalent_money_score * out.tower_value_raw / equivalent_money;
        out.money_score = equivalent_money_score * out.money_raw / equivalent_money;
    }
    out.c1_bonus_raw = c1_terminal_bonus(simulator, player);
    out.c1_bonus_score = out.c1_bonus_raw;
    out.worker_threat_raw = worker_threat_score(simulator, player);
    out.worker_threat_score = -out.worker_threat_raw;
    out.combat_threat_raw = combat_threat_score(simulator, player);
    out.combat_threat_score = -out.combat_threat_raw;
    out.total_score = out.base_hp_score + out.tower_value_score + out.money_score + out.c1_bonus_score +
                      out.worker_threat_score + out.combat_threat_score;
    if (apply_future_threat) {
        const double static_threat = out.worker_threat_raw + out.combat_threat_raw;
        const FutureThreatProjection future = future_threat_projection(simulator, player, static_threat);
        out.future_base_damage_raw = future.base_damage;
        out.future_base_damage_score = future.base_damage_score;
        out.future_worker_threat_raw = future.worker_threat;
        out.future_combat_threat_raw = future.combat_threat;
        out.future_projected_threat_raw = future.projected_threat;
        out.future_adjusted_threat_raw = future.adjusted_threat;
        out.future_threat_adjustment_score = future.adjustment_score;
        out.total_score += out.future_threat_adjustment_score;
    }
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

} // namespace antgame::sdk::lure_strategy_detail
