#pragma once

#include "antgame_ai/lure_strategy_v4_evaluation.hpp"

namespace antgame::sdk::lure_strategy_detail {

struct OffensivePostActionGate {
    bool ok = false;
    PublicState post_action;
    std::string reason = "not_checked";
    int post_action_coins = 0;
    int enemy_lightning_cooldown = 0;

    explicit OffensivePostActionGate(std::uint64_t seed)
        : post_action(seed) {}
};

struct OffensiveEvasionChoice {
    bool use = false;
    Operation operation = Operation(OperationType::UseEmergencyEvasion, -1, -1);
    std::string reason = "not_checked";
    int x = -1;
    int y = -1;
    int worker_count = 0;
    int combat_count = 0;
    int post_action_coins = 0;
    int enemy_lightning_cooldown = 0;
};

struct OffensiveEmpChoice {
    bool use = false;
    Operation operation = Operation(OperationType::UseEmpBlaster, -1, -1);
    std::string reason = "not_checked";
    int x = -1;
    int y = -1;
    int post_action_coins = 0;
    int enemy_lightning_cooldown = 0;
    int tower_id = -1;
    int tower_type = -1;
    int combat_ant_id = -1;
    int distance = 1000;
    int frontline_ant_count = 0;
};

struct OffensiveAntUpgradeChoice {
    bool use = false;
    Operation operation = Operation(OperationType::UpgradeGeneratedAnt);
    std::string reason = "not_checked";
    int post_action_coins = 0;
    int remaining_coins = 0;
    double equivalent_money = 0.0;
    int current_ant_level = 0;
};

inline bool enemy_lightning_active(const PublicState &state, int player) {
    const int enemy = 1 - player;
    for (const auto &effect : state.active_effects) {
        if (effect.player == enemy && effect.weapon_type == SuperWeaponType::LightningStorm &&
            effect.remaining_turns > 0) {
            return true;
        }
    }
    return false;
}

inline bool own_has_sniper(const PublicState &state, int player) {
    for (const auto &tower : state.towers) {
        if (tower.player == player && tower.tower_type == TowerType::Sniper) {
            return true;
        }
    }
    return false;
}

inline OffensivePostActionGate make_offensive_post_action_gate(
    const PublicState &state,
    int player,
    const std::vector<Operation> &ops) {
    OffensivePostActionGate gate(state.seed);
    const int enemy = 1 - player;
    gate.enemy_lightning_cooldown =
        state.weapon_cooldowns[enemy][static_cast<int>(SuperWeaponType::LightningStorm)];
    if (enemy_lightning_active(state, player)) {
        gate.reason = "enemy_lightning_active";
        return gate;
    }
    if (gate.enemy_lightning_cooldown < v4_lure_config().offensive_evasion_min_enemy_lightning_cd) {
        gate.reason = "enemy_lightning_cd_too_low";
        return gate;
    }

    gate.post_action = state.clone();
    const auto illegal = gate.post_action.apply_operation_list(player, ops);
    if (!illegal.empty()) {
        gate.reason = "best_ops_illegal";
        return gate;
    }
    gate.post_action_coins = gate.post_action.coins[player];
    if (gate.post_action_coins <= v4_lure_config().offensive_evasion_min_post_action_coins) {
        gate.reason = "post_action_coins_too_low";
        return gate;
    }
    gate.ok = true;
    gate.reason = "ok";
    return gate;
}

inline OffensiveEmpChoice choose_offensive_emp(
    const PublicState &state,
    int player,
    const std::vector<Operation> &best_ops) {
    OffensiveEmpChoice out;
    const OffensivePostActionGate gate = make_offensive_post_action_gate(state, player, best_ops);
    out.post_action_coins = gate.post_action_coins;
    out.enemy_lightning_cooldown = gate.enemy_lightning_cooldown;
    if (!gate.ok) {
        out.reason = gate.reason;
        return out;
    }
    if (!c1_has_sniper(gate.post_action, player)) {
        out.reason = "no_c1_sniper";
        return out;
    }
    if (gate.post_action.weapon_cooldowns[player][static_cast<int>(SuperWeaponType::EmpBlaster)] > 0) {
        out.reason = "own_emp_cd";
        return out;
    }

    const int enemy = 1 - player;
    const int trigger_distance = v4_lure_config().offensive_emp_combat_to_top_tower_distance;
    double best_tower_value = -1.0;
    int best_tower_distance_to_base = 1000;
    const auto [enemy_base_x, enemy_base_y] = kPlayerBases[enemy];
    const int enemy_tower_count = gate.post_action.tower_count(enemy);
    for (const auto &tower : gate.post_action.towers) {
        if (tower.player != enemy || tower_level(tower.tower_type) < 2) {
            continue;
        }
        int nearest_distance = 1000;
        int nearest_ant_id = -1;
        for (const auto &ant : gate.post_action.ants) {
            if (ant.player != player || ant.kind != AntKind::Combat || !ant.is_alive()) {
                continue;
            }
            const int distance = hex_distance(ant.x, ant.y, tower.x, tower.y);
            if (distance < nearest_distance || (distance == nearest_distance && ant.ant_id < nearest_ant_id)) {
                nearest_distance = distance;
                nearest_ant_id = ant.ant_id;
            }
        }
        if (nearest_distance > trigger_distance) {
            continue;
        }

        const Operation operation(OperationType::UseEmpBlaster, tower.x, tower.y);
        if (!gate.post_action.can_apply_operation(player, operation)) {
            continue;
        }
        const double tower_value = tower_salvage_value(gate.post_action, tower, enemy_tower_count);
        const int tower_distance_to_base = hex_distance(tower.x, tower.y, enemy_base_x, enemy_base_y);
        if (!out.use || nearest_distance < out.distance ||
            (nearest_distance == out.distance && tower_value > best_tower_value) ||
            (nearest_distance == out.distance && tower_value == best_tower_value &&
             tower_distance_to_base < best_tower_distance_to_base) ||
            (nearest_distance == out.distance && tower_value == best_tower_value &&
             tower_distance_to_base == best_tower_distance_to_base && tower.tower_id < out.tower_id)) {
            out.use = true;
            out.operation = operation;
            out.reason = "use";
            out.x = tower.x;
            out.y = tower.y;
            out.tower_id = tower.tower_id;
            out.tower_type = static_cast<int>(tower.tower_type);
            out.combat_ant_id = nearest_ant_id;
            out.distance = nearest_distance;
            best_tower_value = tower_value;
            best_tower_distance_to_base = tower_distance_to_base;
        }
    }

    if (!out.use) {
        const int emp_cost = weapon_stats(SuperWeaponType::EmpBlaster).cost;
        const int min_remaining_coins = v4_lure_config().offensive_surplus_emp_min_remaining_coins;
        if (gate.post_action_coins < emp_cost + min_remaining_coins) {
            out.reason = "surplus_emp_coins_too_low";
            return out;
        }

        const int min_frontline_ants = v4_lure_config().offensive_surplus_emp_min_frontline_ants;
        const int frontline_distance = v4_lure_config().offensive_surplus_emp_frontline_base_distance;
        for (const auto &ant : gate.post_action.ants) {
            if (ant.player != player || !ant.is_alive()) {
                continue;
            }
            if (hex_distance(ant.x, ant.y, enemy_base_x, enemy_base_y) <= frontline_distance) {
                ++out.frontline_ant_count;
            }
        }
        if (out.frontline_ant_count < min_frontline_ants) {
            out.reason = "surplus_emp_insufficient_frontline_ants";
            return out;
        }

        double surplus_best_tower_value = -1.0;
        for (int code : {C1, C2, C3, L1, L2, L3, R1, R2, R3}) {
            const Tower *tower = tower_at_code(gate.post_action, enemy, code);
            if (tower == nullptr || tower->player != enemy ||
                (tower->tower_type != TowerType::Sniper && tower_level(tower->tower_type) < 2)) {
                continue;
            }

            const Operation operation(OperationType::UseEmpBlaster, tower->x, tower->y);
            if (!gate.post_action.can_apply_operation(player, operation)) {
                continue;
            }
            const int tower_distance_to_base = hex_distance(tower->x, tower->y, enemy_base_x, enemy_base_y);
            const double tower_value = tower_salvage_value(gate.post_action, *tower, enemy_tower_count);
            if (!out.use || tower_distance_to_base < best_tower_distance_to_base ||
                (tower_distance_to_base == best_tower_distance_to_base && tower_value > surplus_best_tower_value) ||
                (tower_distance_to_base == best_tower_distance_to_base && tower_value == surplus_best_tower_value &&
                 tower->tower_id < out.tower_id)) {
                out.use = true;
                out.operation = operation;
                out.reason = "surplus_use";
                out.x = tower->x;
                out.y = tower->y;
                out.tower_id = tower->tower_id;
                out.tower_type = static_cast<int>(tower->tower_type);
                out.combat_ant_id = -1;
                out.distance = tower_distance_to_base;
                best_tower_distance_to_base = tower_distance_to_base;
                surplus_best_tower_value = tower_value;
            }
        }

        if (!out.use) {
            out.reason = "surplus_emp_no_core_level3_tower";
        }
    }
    return out;
}

inline OffensiveEvasionChoice choose_offensive_evasion(
    const PublicState &state,
    int player,
    const std::vector<Operation> &best_ops) {
    OffensiveEvasionChoice out;
    const OffensivePostActionGate gate = make_offensive_post_action_gate(state, player, best_ops);
    out.post_action_coins = gate.post_action_coins;
    out.enemy_lightning_cooldown = gate.enemy_lightning_cooldown;
    if (!gate.ok) {
        out.reason = gate.reason;
        return out;
    }
    const PublicState &post_action = gate.post_action;
    const int enemy = 1 - player;
    if (!c1_has_sniper(post_action, player)) {
        out.reason = "no_c1_sniper";
        return out;
    }
    if (post_action.weapon_cooldowns[player][static_cast<int>(SuperWeaponType::EmergencyEvasion)] > 0) {
        out.reason = "own_evasion_cd";
        return out;
    }

    const int range = weapon_stats(SuperWeaponType::EmergencyEvasion).attack_range;
    const auto [enemy_base_x, enemy_base_y] = kPlayerBases[enemy];
    int best_enemy_base_distance = 1000;
    for (int x = 0; x < kMapSize; ++x) {
        for (int y = 0; y < kMapSize; ++y) {
            const Operation operation(OperationType::UseEmergencyEvasion, x, y);
            if (!post_action.can_apply_operation(player, operation)) {
                continue;
            }
            int workers = 0;
            int combats = 0;
            for (const auto &ant : post_action.ants) {
                if (ant.player != player || !ant.is_alive() || hex_distance(x, y, ant.x, ant.y) > range) {
                    continue;
                }
                if (ant.kind == AntKind::Worker) {
                    ++workers;
                } else if (ant.kind == AntKind::Combat) {
                    ++combats;
                }
            }
            const int enemy_base_distance = hex_distance(x, y, enemy_base_x, enemy_base_y);
            if (workers > out.worker_count ||
                (workers == out.worker_count && enemy_base_distance < best_enemy_base_distance) ||
                (workers == out.worker_count && enemy_base_distance == best_enemy_base_distance &&
                 combats < out.combat_count) ||
                (workers == out.worker_count && enemy_base_distance == best_enemy_base_distance &&
                 combats == out.combat_count && (x < out.x || (x == out.x && y < out.y)))) {
                out.operation = operation;
                out.x = x;
                out.y = y;
                out.worker_count = workers;
                out.combat_count = combats;
                best_enemy_base_distance = enemy_base_distance;
            }
        }
    }

    if (out.worker_count < v4_lure_config().offensive_evasion_min_worker_count) {
        out.reason = "insufficient_worker_coverage";
        return out;
    }
    out.use = true;
    out.reason = "use";
    return out;
}

inline OffensiveAntUpgradeChoice choose_offensive_ant_upgrade(
    const PublicState &state,
    int player,
    const std::vector<Operation> &best_ops) {
    OffensiveAntUpgradeChoice out;
    if (state.round_index > v4_lure_config().offensive_ant_upgrade_latest_round) {
        out.reason = "round_too_late";
        return out;
    }

    PublicState post_action = state.clone();
    const auto illegal = post_action.apply_operation_list(player, best_ops);
    if (!illegal.empty()) {
        out.reason = "best_ops_illegal";
        return out;
    }

    out.post_action_coins = post_action.coins[player];
    out.current_ant_level = post_action.bases[player].ant_level;
    if (out.current_ant_level != 0) {
        out.reason = "already_level1_or_higher";
        return out;
    }
    if (!own_has_sniper(post_action, player)) {
        out.reason = "no_own_sniper";
        return out;
    }

    const Operation operation(OperationType::UpgradeGeneratedAnt);
    const int upgrade_cost = upgrade_base_cost(post_action.bases[player].ant_level);
    out.remaining_coins = out.post_action_coins - upgrade_cost;
    if (!state.can_apply_operation(player, operation, best_ops)) {
        out.reason = "operation_illegal";
        return out;
    }
    out.equivalent_money = static_cast<double>(out.remaining_coins) + tower_full_salvage_value(post_action, player);
    if (out.equivalent_money < v4_lure_config().offensive_ant_upgrade_min_equivalent_money) {
        out.reason = "equivalent_money_too_low";
        return out;
    }

    out.use = true;
    out.operation = operation;
    out.reason = "use";
    return out;
}

} // namespace antgame::sdk::lure_strategy_detail
