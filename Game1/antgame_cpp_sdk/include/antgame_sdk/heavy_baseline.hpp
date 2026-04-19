#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/sdk.hpp"

namespace antgame::sdk {

struct BaselineDecisionContext {
    const PublicState *state = nullptr;
    const NativeSimulator *simulator = nullptr;
    int player = 0;
    bool opponent_ops_already_applied = false;
};

struct BaselineSession {
    std::array<int, 2> last_round_seen = {-1, -1};
    std::array<int, 2> quiet_rounds_since_combat_breach = {0, 0};
    std::array<int, 2> recent_combat_breach_round = {-1000, -1000};

    void observe(const PublicState &state, int player) {
        if (last_round_seen[player] == state.round_index) {
            return;
        }
        last_round_seen[player] = state.round_index;
        const int enemy = 1 - player;
        const auto [base_x, base_y] = kPlayerBases[player];
        bool combat_near_base = false;
        for (const auto *ant : state.ants_of(enemy)) {
            if (ant->kind != AntKind::Combat) {
                continue;
            }
            if (hex_distance(ant->x, ant->y, base_x, base_y) <= 2) {
                combat_near_base = true;
                break;
            }
        }
        if (combat_near_base) {
            quiet_rounds_since_combat_breach[player] = 0;
            recent_combat_breach_round[player] = state.round_index;
        } else {
            ++quiet_rounds_since_combat_breach[player];
        }
    }
};

struct BaselineBundle {
    std::string name;
    std::vector<Operation> operations;
    double prior_score = 0.0;
};

struct BaselineConfig {
    std::pair<int, int> base_front_slot = {4, 9};
    std::array<std::pair<int, int>, 4> quick_support_slots{{{5, 7}, {5, 11}, {6, 7}, {6, 11}}};
    std::array<std::pair<int, int>, 4> build_search_slots{{{4, 9}, {5, 7}, {5, 11}, {6, 9}}};
    int quiet_rounds_for_heavy = 5;
    int quiet_rounds_for_bewitch = 9;
    int combat_empty_city_distance = 4;
    int combat_danger_distance = 5;
    int normal_pressure_distance = 6;
    int max_rollout_candidates = 8;
    int rollout_count = 6;
    int rollout_horizon = 4;
    int action_penalty_per_op = 22;
    int build_penalty = 20;
    int upgrade_penalty = 16;
    int downgrade_penalty = 7;
    int lightning_penalty = 28;
    int ant_upgrade_penalty = 18;
    int hold_bonus = 4;
    double threatened_tower_hp_ratio = 0.58;
};

inline const BaselineConfig &baseline_config() {
    static const BaselineConfig config;
    return config;
}

inline std::pair<int, int> mirror_slot(const std::pair<int, int> &slot, int player) {
    if (player == 0) {
        return slot;
    }
    return {kMapSize - 1 - slot.first, slot.second};
}

template <std::size_t N>
inline std::array<std::pair<int, int>, N> mirror_slots(const std::array<std::pair<int, int>, N> &slots, int player) {
    std::array<std::pair<int, int>, N> out{};
    for (std::size_t index = 0; index < N; ++index) {
        out[index] = mirror_slot(slots[index], player);
    }
    return out;
}

inline std::uint64_t mix_seed(std::uint64_t seed, std::uint64_t value) {
    seed ^= value + 0x9e3779b97f4a7c15ULL + (seed << 6U) + (seed >> 2U);
    return seed;
}

inline std::uint64_t bundle_hash(const std::vector<Operation> &operations) {
    std::uint64_t seed = 0x243f6a8885a308d3ULL;
    for (const auto &op : operations) {
        seed = mix_seed(seed, static_cast<std::uint64_t>(static_cast<int>(op.op_type) + 37));
        seed = mix_seed(seed, static_cast<std::uint64_t>(op.arg0 + 257));
        seed = mix_seed(seed, static_cast<std::uint64_t>(op.arg1 + 911));
    }
    return seed;
}

inline int enemy_combat_near_base(const PublicState &state, int player, int max_dist) {
    const int enemy = 1 - player;
    const auto [base_x, base_y] = kPlayerBases[player];
    int count = 0;
    for (const auto *ant : state.ants_of(enemy)) {
        if (ant->kind == AntKind::Combat && hex_distance(ant->x, ant->y, base_x, base_y) <= max_dist) {
            ++count;
        }
    }
    return count;
}

inline int enemy_workers_near_base(const PublicState &state, int player, int max_dist) {
    const int enemy = 1 - player;
    const auto [base_x, base_y] = kPlayerBases[player];
    int count = 0;
    for (const auto *ant : state.ants_of(enemy)) {
        if (ant->kind == AntKind::Worker && hex_distance(ant->x, ant->y, base_x, base_y) <= max_dist) {
            ++count;
        }
    }
    return count;
}

inline double local_enemy_pressure(const PublicState &state, int player, int x, int y) {
    const int enemy = 1 - player;
    double score = 0.0;
    for (const auto *ant : state.ants_of(enemy)) {
        const int dist = hex_distance(ant->x, ant->y, x, y);
        if (dist > 7) {
            continue;
        }
        const double base = ant->kind == AntKind::Combat ? 5.6 : 1.5;
        const double hp_scale = static_cast<double>(std::max(ant->hp, 1)) / std::max(ant->max_hp(), 1);
        score += base * hp_scale / (1.0 + static_cast<double>(dist));
    }
    return score;
}

inline double enemy_cluster_value(const PublicState &state, int player, int x, int y, int range) {
    const int enemy = 1 - player;
    double value = 0.0;
    for (const auto *ant : state.ants_of(enemy)) {
        const int dist = hex_distance(ant->x, ant->y, x, y);
        if (dist > range) {
            continue;
        }
        value += ant->kind == AntKind::Combat ? 2.5 : 1.0;
        value += static_cast<double>(std::min(ant->hp, 20)) / 20.0;
    }
    return value;
}

inline bool is_combat_empty_city_window(const PublicState &state, int player) {
    const auto &cfg = baseline_config();
    return enemy_combat_near_base(state, player, cfg.combat_empty_city_distance) > 0;
}

inline const Tower *owned_tower_at(const PublicState &state, int player, const std::pair<int, int> &slot) {
    const Tower *tower = state.tower_at(slot.first, slot.second);
    if (tower == nullptr || tower->player != player) {
        return nullptr;
    }
    return tower;
}

inline bool tower_is_threatened(const PublicState &state, int player, const Tower &tower) {
    const auto &cfg = baseline_config();
    const double hp_ratio = static_cast<double>(std::max(tower.hp, 0)) / std::max(tower.max_hp(), 1);
    if (enemy_combat_near_base(state, player, cfg.combat_danger_distance) == 0) {
        return false;
    }
    return hp_ratio <= cfg.threatened_tower_hp_ratio || local_enemy_pressure(state, player, tower.x, tower.y) >= 6.5;
}

inline int count_owned_type(const PublicState &state, int player, TowerType type) {
    int total = 0;
    for (const auto *tower : state.towers_of(player)) {
        if (tower->tower_type == type) {
            ++total;
        }
    }
    return total;
}

inline double operation_penalty(const PublicState &state, int player, const std::vector<Operation> &operations) {
    const auto &cfg = baseline_config();
    double penalty = static_cast<double>(cfg.action_penalty_per_op * static_cast<int>(operations.size()));
    for (const auto &operation : operations) {
        switch (operation.op_type) {
        case OperationType::BuildTower:
            penalty += cfg.build_penalty;
            penalty += state.build_tower_cost(state.tower_count(player)) * 0.16;
            break;
        case OperationType::UpgradeTower:
            penalty += cfg.upgrade_penalty;
            penalty += std::abs(state.operation_income(player, operation)) * 0.08;
            break;
        case OperationType::DowngradeTower:
            penalty += cfg.downgrade_penalty;
            break;
        case OperationType::UseLightningStorm:
            penalty += cfg.lightning_penalty;
            break;
        case OperationType::UpgradeGeneratedAnt:
            penalty += cfg.ant_upgrade_penalty;
            penalty += std::abs(state.operation_income(player, operation)) * 0.03;
            break;
        default:
            penalty += 12.0;
            break;
        }
    }
    return penalty;
}

inline double static_state_value(const PublicState &state, int player) {
    const int enemy = 1 - player;
    const auto &my_base = state.bases[player];
    const auto &enemy_base = state.bases[enemy];

    double score = 0.0;
    score += static_cast<double>(my_base.hp - enemy_base.hp) * 120.0;
    score += static_cast<double>(state.coins[player] - state.coins[enemy]) * 1.2;
    score += static_cast<double>(my_base.ant_level - enemy_base.ant_level) * 18.0;
    score += static_cast<double>(my_base.generation_level - enemy_base.generation_level) * 10.0;

    double my_tower_value = 0.0;
    double enemy_tower_value = 0.0;
    for (const auto *tower : state.towers_of(player)) {
        const double hp_ratio = static_cast<double>(std::max(tower->hp, 0)) / std::max(tower->max_hp(), 1);
        my_tower_value += 18.0 + tower->level() * 10.0 + hp_ratio * 8.0;
        if (tower->tower_type == TowerType::Bewitch) {
            my_tower_value += 18.0;
        } else if (tower->tower_type == TowerType::Heavy) {
            my_tower_value += 10.0;
        } else if (tower->tower_type == TowerType::Quick) {
            my_tower_value += 6.0;
        }
    }
    for (const auto *tower : state.towers_of(enemy)) {
        const double hp_ratio = static_cast<double>(std::max(tower->hp, 0)) / std::max(tower->max_hp(), 1);
        enemy_tower_value += 18.0 + tower->level() * 10.0 + hp_ratio * 8.0;
    }
    score += my_tower_value - enemy_tower_value * 0.72;

    double my_ant_pressure = 0.0;
    double enemy_ant_pressure = 0.0;
    const auto [enemy_base_x, enemy_base_y] = kPlayerBases[enemy];
    const auto [my_base_x, my_base_y] = kPlayerBases[player];
    for (const auto *ant : state.ants_of(player)) {
        const int dist = hex_distance(ant->x, ant->y, enemy_base_x, enemy_base_y);
        my_ant_pressure += (ant->kind == AntKind::Combat ? 11.0 : 5.0) + std::max(0, 12 - dist) * 1.6;
        my_ant_pressure += static_cast<double>(ant->hp) / std::max(ant->max_hp(), 1) * 2.0;
    }
    for (const auto *ant : state.ants_of(enemy)) {
        const int dist = hex_distance(ant->x, ant->y, my_base_x, my_base_y);
        enemy_ant_pressure += (ant->kind == AntKind::Combat ? 16.0 : 6.0) + std::max(0, 12 - dist) * 2.2;
        enemy_ant_pressure += static_cast<double>(ant->hp) / std::max(ant->max_hp(), 1) * 2.5;
    }
    score += my_ant_pressure - enemy_ant_pressure;

    const int combat_close = enemy_combat_near_base(state, player, 4);
    const int worker_close = enemy_workers_near_base(state, player, 4);
    score -= static_cast<double>(combat_close) * 35.0;
    score -= static_cast<double>(worker_close) * 9.0;

    const auto front_slot = mirror_slot(baseline_config().base_front_slot, player);
    const Tower *front_tower = owned_tower_at(state, player, front_slot);
    if (front_tower != nullptr) {
        if (front_tower->tower_type == TowerType::Bewitch) {
            score += 26.0;
        } else if (front_tower->tower_type == TowerType::Heavy) {
            score += 10.0;
        }
        if (tower_is_threatened(state, player, *front_tower) && front_tower->tower_type == TowerType::Bewitch) {
            score -= 55.0;
        }
    }

    return score;
}

inline std::vector<Operation> sanitize_operations(const PublicState &state, int player, const std::vector<Operation> &proposed) {
    std::vector<Operation> accepted;
    accepted.reserve(proposed.size());
    for (const auto &operation : proposed) {
        if (state.can_apply_operation(player, operation, accepted)) {
            accepted.push_back(operation);
        }
    }
    return accepted;
}

inline const Tower *front_tower(const PublicState &state, int player) {
    return owned_tower_at(state, player, mirror_slot(baseline_config().base_front_slot, player));
}

inline std::vector<Operation> scripted_policy(const PublicState &state, int player, BaselineSession *session) {
    const auto &cfg = baseline_config();
    if (session != nullptr) {
        session->observe(state, player);
    }

    const auto front_slot = mirror_slot(cfg.base_front_slot, player);
    const auto quick_slots = mirror_slots(cfg.quick_support_slots, player);
    const int quiet_rounds = session != nullptr ? session->quiet_rounds_since_combat_breach[player] : 0;
    const int combat_near = enemy_combat_near_base(state, player, cfg.combat_danger_distance);
    const int worker_near = enemy_workers_near_base(state, player, cfg.normal_pressure_distance);
    const Tower *front = front_tower(state, player);

    if (front != nullptr && combat_near > 0) {
        if (front->tower_type == TowerType::Bewitch || front->tower_type == TowerType::Heavy || front->tower_type == TowerType::Quick) {
            const Operation downgrade(OperationType::DowngradeTower, front->tower_id);
            if (state.can_apply_operation(player, downgrade)) {
                return {downgrade};
            }
        }
    }

    for (const auto *tower : state.towers_of(player)) {
        if (!tower_is_threatened(state, player, *tower)) {
            continue;
        }
        if (tower->tower_type == TowerType::Bewitch) {
            const Operation downgrade(OperationType::DowngradeTower, tower->tower_id);
            if (state.can_apply_operation(player, downgrade)) {
                return {downgrade};
            }
        }
    }

    if (state.bases[player].ant_level == 0) {
        const Operation upgrade_ant(OperationType::UpgradeGeneratedAnt);
        if (state.can_apply_operation(player, upgrade_ant) &&
            state.coins[player] >= upgrade_base_cost(state.bases[player].ant_level) &&
            quiet_rounds >= 2) {
            return {upgrade_ant};
        }
    }

    if (is_combat_empty_city_window(state, player)) {
        return {};
    }

    if (front == nullptr && quiet_rounds >= cfg.quiet_rounds_for_heavy && worker_near > 0) {
        const Operation build(OperationType::BuildTower, front_slot.first, front_slot.second);
        if (state.can_apply_operation(player, build)) {
            return {build};
        }
    }

    if (front != nullptr && front->tower_type == TowerType::Basic &&
        quiet_rounds >= cfg.quiet_rounds_for_heavy && worker_near > 0) {
        const Operation upgrade(OperationType::UpgradeTower, front->tower_id, static_cast<int>(TowerType::Heavy));
        if (state.can_apply_operation(player, upgrade)) {
            return {upgrade};
        }
    }

    if (front != nullptr && front->tower_type == TowerType::Heavy &&
        quiet_rounds >= cfg.quiet_rounds_for_bewitch && combat_near == 0 &&
        state.coins[player] >= upgrade_tower_cost(TowerType::Bewitch) + 30) {
        const Operation upgrade(OperationType::UpgradeTower, front->tower_id, static_cast<int>(TowerType::Bewitch));
        if (state.can_apply_operation(player, upgrade)) {
            return {upgrade};
        }
    }

    if (front != nullptr && front->tower_type == TowerType::Bewitch && combat_near == 0) {
        for (const auto &slot : quick_slots) {
            const Tower *tower = owned_tower_at(state, player, slot);
            if (tower == nullptr) {
                const Operation build(OperationType::BuildTower, slot.first, slot.second);
                if (state.can_apply_operation(player, build)) {
                    return {build};
                }
                continue;
            }
            if (tower->tower_type == TowerType::Basic) {
                const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Quick));
                if (state.can_apply_operation(player, upgrade)) {
                    return {upgrade};
                }
            }
        }
    }

    return {};
}

inline std::vector<BaselineBundle> generate_candidate_bundles(const PublicState &state, int player, BaselineSession *session) {
    const auto &cfg = baseline_config();
    std::vector<BaselineBundle> bundles;
    bundles.reserve(20);
    bundles.push_back({"hold", {}, static_cast<double>(cfg.hold_bonus)});

    const auto scripted = sanitize_operations(state, player, scripted_policy(state, player, session));
    if (!scripted.empty()) {
        bundles.push_back({"scripted", scripted, 50.0});
    }

    const auto front_slot = mirror_slot(cfg.base_front_slot, player);
    const auto quick_slots = mirror_slots(cfg.quick_support_slots, player);
    const auto build_slots = mirror_slots(cfg.build_search_slots, player);
    const Tower *front = front_tower(state, player);
    const int combat_near = enemy_combat_near_base(state, player, cfg.combat_danger_distance);
    const int worker_near = enemy_workers_near_base(state, player, cfg.normal_pressure_distance);

    if (front == nullptr) {
        const Operation build(OperationType::BuildTower, front_slot.first, front_slot.second);
        if (state.can_apply_operation(player, build) && combat_near == 0 && worker_near > 0) {
            bundles.push_back({"build-front-basic", {build}, 14.0 + local_enemy_pressure(state, player, front_slot.first, front_slot.second)});
        }
    } else {
        if (front->tower_type == TowerType::Basic) {
            const Operation to_heavy(OperationType::UpgradeTower, front->tower_id, static_cast<int>(TowerType::Heavy));
            if (state.can_apply_operation(player, to_heavy)) {
                bundles.push_back({"front-heavy", {to_heavy}, 26.0 + worker_near * 1.5});
            }
        }
        if (front->tower_type == TowerType::Heavy) {
            const Operation to_bewitch(OperationType::UpgradeTower, front->tower_id, static_cast<int>(TowerType::Bewitch));
            if (state.can_apply_operation(player, to_bewitch) && combat_near == 0) {
                bundles.push_back({"front-bewitch", {to_bewitch}, 36.0 + worker_near * 1.0});
            }
        }
        if ((front->tower_type == TowerType::Bewitch || front->tower_type == TowerType::Heavy || front->tower_type == TowerType::Quick) &&
            combat_near > 0) {
            const Operation downgrade(OperationType::DowngradeTower, front->tower_id);
            if (state.can_apply_operation(player, downgrade)) {
                bundles.push_back({"front-salvage", {downgrade}, 48.0 + combat_near * 6.0});
            }
        }
    }

    for (const auto &slot : quick_slots) {
        const Tower *tower = owned_tower_at(state, player, slot);
        if (tower == nullptr && front != nullptr && front->tower_type == TowerType::Bewitch && combat_near == 0) {
            const Operation build(OperationType::BuildTower, slot.first, slot.second);
            if (state.can_apply_operation(player, build)) {
                bundles.push_back({"build-quick-anchor", {build}, 18.0 + local_enemy_pressure(state, player, slot.first, slot.second)});
            }
            continue;
        }
        if (tower != nullptr && tower->tower_type == TowerType::Basic && front != nullptr && front->tower_type == TowerType::Bewitch && combat_near == 0) {
            const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(TowerType::Quick));
            if (state.can_apply_operation(player, upgrade)) {
                bundles.push_back({"upgrade-quick", {upgrade}, 24.0 + local_enemy_pressure(state, player, slot.first, slot.second)});
            }
        }
        if (tower != nullptr && tower_is_threatened(state, player, *tower)) {
            const Operation downgrade(OperationType::DowngradeTower, tower->tower_id);
            if (state.can_apply_operation(player, downgrade)) {
                bundles.push_back({"salvage-threatened", {downgrade}, 34.0 + local_enemy_pressure(state, player, slot.first, slot.second)});
            }
        }
    }

    if (state.bases[player].ant_level == 0) {
        const Operation upgrade_ant(OperationType::UpgradeGeneratedAnt);
        if (state.can_apply_operation(player, upgrade_ant)) {
            bundles.push_back({"upgrade-ant", {upgrade_ant}, 22.0});
        }
    }

    if (state.weapon_cooldowns[player][static_cast<int>(SuperWeaponType::LightningStorm)] == 0 &&
        state.coins[player] >= state.weapon_cost(SuperWeaponType::LightningStorm)) {
        std::vector<std::pair<int, int>> centers;
        centers.reserve(state.ants.size() + state.towers.size() + 4);
        for (const auto *ant : state.ants_of(1 - player)) {
            centers.emplace_back(ant->x, ant->y);
        }
        for (const auto *tower : state.towers_of(player)) {
            if (tower_is_threatened(state, player, *tower)) {
                centers.emplace_back(tower->x, tower->y);
            }
        }
        if (centers.empty()) {
            centers.push_back(front_slot);
        }
        for (const auto &[x, y] : centers) {
            const Operation storm(OperationType::UseLightningStorm, x, y);
            if (!state.can_apply_operation(player, storm)) {
                continue;
            }
            const double threat = enemy_cluster_value(
                state, player, x, y, weapon_stats(SuperWeaponType::LightningStorm).attack_range);
            if (threat < 4.0) {
                continue;
            }
            bundles.push_back({"lightning", {storm}, 24.0 + threat * 4.0});
            break;
        }
    }

    for (const auto &slot : build_slots) {
        const Tower *tower = owned_tower_at(state, player, slot);
        if (tower == nullptr && front == nullptr) {
            const Operation build(OperationType::BuildTower, slot.first, slot.second);
            if (state.can_apply_operation(player, build) && combat_near == 0) {
                bundles.push_back({"build-alt", {build}, 8.0 + local_enemy_pressure(state, player, slot.first, slot.second)});
            }
        }
    }

    std::vector<BaselineBundle> unique;
    unique.reserve(bundles.size());
    for (const auto &bundle : bundles) {
        bool duplicate = false;
        for (const auto &existing : unique) {
            if (existing.operations.size() != bundle.operations.size()) {
                continue;
            }
            bool same = true;
            for (std::size_t index = 0; index < existing.operations.size(); ++index) {
                if (static_cast<int>(existing.operations[index].op_type) != static_cast<int>(bundle.operations[index].op_type) ||
                    existing.operations[index].arg0 != bundle.operations[index].arg0 ||
                    existing.operations[index].arg1 != bundle.operations[index].arg1) {
                    same = false;
                    break;
                }
            }
            if (same) {
                duplicate = true;
                break;
            }
        }
        if (!duplicate) {
            unique.push_back(bundle);
        }
    }

    std::sort(unique.begin(), unique.end(), [](const BaselineBundle &lhs, const BaselineBundle &rhs) {
        return lhs.prior_score > rhs.prior_score;
    });
    if (static_cast<int>(unique.size()) > cfg.max_rollout_candidates) {
        unique.resize(static_cast<std::size_t>(cfg.max_rollout_candidates));
    }
    return unique;
}

inline std::vector<Operation> rollout_policy(
    const PublicState &state,
    int player,
    const std::uint64_t salt,
    BaselineSession *session = nullptr) {
    std::vector<BaselineBundle> candidates = generate_candidate_bundles(state, player, session);
    if (candidates.empty()) {
        return {};
    }
    const std::uint64_t state_key =
        mix_seed(state.seed, static_cast<std::uint64_t>(state.round_index + 1 + player * 17)) ^ salt;
    std::sort(candidates.begin(), candidates.end(), [&](const BaselineBundle &lhs, const BaselineBundle &rhs) {
        const double lhs_bias = static_cast<double>(mix_seed(state_key, bundle_hash(lhs.operations)) & 1023ULL) / 1024.0;
        const double rhs_bias = static_cast<double>(mix_seed(state_key, bundle_hash(rhs.operations)) & 1023ULL) / 1024.0;
        return lhs.prior_score + lhs_bias * 0.18 > rhs.prior_score + rhs_bias * 0.18;
    });
    return sanitize_operations(state, player, candidates.front().operations);
}

inline double evaluate_bundle_with_rollouts(
    const BaselineDecisionContext &ctx,
    const BaselineBundle &bundle) {
    const auto &cfg = baseline_config();
    const PublicState &state = *ctx.state;
    const int player = ctx.player;
    const int enemy = 1 - player;
    const double base_penalty = operation_penalty(state, player, bundle.operations);
    double best_score = -std::numeric_limits<double>::infinity();

    if (ctx.simulator == nullptr) {
        PublicState trial = state.clone();
        trial.apply_operation_list(player, bundle.operations);
        return static_state_value(trial, player) + bundle.prior_score - base_penalty;
    }

    for (int rollout_index = 0; rollout_index < cfg.rollout_count; ++rollout_index) {
        NativeSimulator sim = ctx.simulator->clone();
        const std::uint64_t salt = static_cast<std::uint64_t>(rollout_index + 1) * 1000003ULL + bundle_hash(bundle.operations);
        if (ctx.opponent_ops_already_applied) {
            sim.apply_operation_list(player, bundle.operations);
            sim.advance_round();
        } else {
            sim.resolve_turn(
                player == 0 ? bundle.operations : rollout_policy(state, 0, salt),
                player == 0 ? rollout_policy(state, 1, salt) : bundle.operations);
        }

        double score = 0.0;
        if (sim.terminal()) {
            score += sim.winner() == player ? 100000.0 : -100000.0;
        }

        for (int depth = 0; depth < cfg.rollout_horizon && !sim.terminal(); ++depth) {
            const PublicRoundState round_state = sim.to_public_round_state();
            PublicState next_state(state.seed, state.movement_policy, state.cold_handle_rule_illegal);
            next_state.sync_public_round_state(round_state);
            const std::uint64_t step_salt = salt + static_cast<std::uint64_t>(depth + 1) * 911382323ULL;
            const auto my_ops = rollout_policy(next_state, player, step_salt);
            const auto enemy_ops = rollout_policy(next_state, enemy, step_salt ^ 0x9e3779b97f4a7c15ULL);
            sim.resolve_turn(player == 0 ? my_ops : enemy_ops, player == 0 ? enemy_ops : my_ops);
            if (sim.terminal()) {
                score += sim.winner() == player ? 100000.0 : -100000.0;
                break;
            }
        }

        const PublicRoundState final_round = sim.to_public_round_state();
        PublicState final_state(state.seed, state.movement_policy, state.cold_handle_rule_illegal);
        final_state.sync_public_round_state(final_round);
        score += static_state_value(final_state, player);
        score += bundle.prior_score;
        score -= base_penalty;

        if (bundle.operations.empty()) {
            score += baseline_config().hold_bonus;
        }

        best_score = std::max(best_score, score);
    }

    if (!std::isfinite(best_score)) {
        return static_state_value(state, player) + bundle.prior_score - base_penalty;
    }
    return best_score;
}

inline std::vector<Operation> decide_heavy_baseline(
    const BaselineDecisionContext &ctx,
    BaselineSession *session = nullptr) {
    const PublicState &state = *ctx.state;
    const int player = ctx.player;
    std::vector<BaselineBundle> candidates = generate_candidate_bundles(state, player, session);
    if (candidates.empty()) {
        return {};
    }

    int best_index = 0;
    double best_score = -std::numeric_limits<double>::infinity();
    for (int index = 0; index < static_cast<int>(candidates.size()); ++index) {
        const double score = evaluate_bundle_with_rollouts(ctx, candidates[static_cast<std::size_t>(index)]);
        if (score > best_score) {
            best_score = score;
            best_index = index;
        }
    }
    return sanitize_operations(state, player, candidates[static_cast<std::size_t>(best_index)].operations);
}

inline std::vector<Operation> decide_heavy_baseline(const PublicState &state, int player) {
    BaselineDecisionContext ctx;
    ctx.state = &state;
    ctx.player = player;
    return decide_heavy_baseline(ctx, nullptr);
}

} // namespace antgame::sdk
