#pragma once

#include <algorithm>
#include <limits>

#include "antgame_ai/lure_strategy_v4_candidates.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline double worker_threat_score(const PublicState &state, int player) {
    const auto [base_x, base_y] = kPlayerBases[player];
    double threat = 0.0;
    for (const auto &ant : state.ants) {
        if (ant.player == player || ant.kind != AntKind::Worker || !ant.is_alive()) {
            continue;
        }
        const int distance = std::max(1, hex_distance(ant.x, ant.y, base_x, base_y));
        threat += v4_lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
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
        double tower_threat = value * v4_lure_config().combat_anchor_threat_coin_ratio / distance;
        if (distance <= v4_lure_config().combat_anchor_ring_distance) {
            tower_threat += value * v4_lure_config().combat_anchor_ring1_bonus_ratio;
        }
        threat = std::max(threat, tower_threat);
    }
    return threat;
}

inline double combat_threat_at(const PublicState &state, int player, const Ant &ant, int x, int y) {
    const auto [base_x, base_y] = kPlayerBases[player];
    const int distance = std::max(1, hex_distance(x, y, base_x, base_y));
    double threat = v4_lure_config().combat_base_threat_unit / distance;
    threat = std::max(threat, combat_anchor_threat_at(state, player, x, y));
    threat *= behavior_threat_scale(ant.behavior);
    return threat;
}

inline double worker_threat_score(const rs::DefenseSimulator &simulator, int player) {
    const auto [base_x, base_y] = kPlayerBases[player];
    double threat = 0.0;
    for (const auto &ant : simulator.ants) {
        if (ant.kind != AntKind::Worker || !ant.alive() || ant.too_old() ||
            (ant.x == base_x && ant.y == base_y)) {
            continue;
        }
        const int distance = std::max(1, hex_distance(ant.x, ant.y, base_x, base_y));
        threat += v4_lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
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
        double tower_threat = value * v4_lure_config().combat_anchor_threat_coin_ratio / distance;
        if (distance <= v4_lure_config().combat_anchor_ring_distance) {
            tower_threat += value * v4_lure_config().combat_anchor_ring1_bonus_ratio;
        }
        threat = std::max(threat, tower_threat);
    }
    return threat;
}

inline double combat_threat_at(const rs::DefenseSimulator &simulator, int player, const rs::SearchAnt &ant, int x, int y) {
    const auto [base_x, base_y] = kPlayerBases[player];
    const int distance = std::max(1, hex_distance(x, y, base_x, base_y));
    double threat = v4_lure_config().combat_base_threat_unit / distance;
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
    double threat = v4_lure_config().worker_threat_unit * std::max(ant.hp, 0) / std::max(1, ant.max_hp()) / distance;
    if (ant.behavior == AntBehavior::Random) {
        threat *= v4_lure_config().randomized_threat_scale;
    } else if (ant.behavior == AntBehavior::Bewitched) {
        threat *= v4_lure_config().bewitched_threat_scale;
    }
    return threat;
}

inline double combat_threat_score(const rs::DefenseSimulator &terminal_simulator, int player) {
    const auto [base_x, base_y] = kPlayerBases[player];
    double threat = 0.0;
    for (const auto &ant : terminal_simulator.ants) {
        if (ant.kind != AntKind::Combat || !ant.alive() || ant.too_old() ||
            (ant.x == base_x && ant.y == base_y)) {
            continue;
        }
        threat += combat_threat_at(terminal_simulator, player, ant, ant.x, ant.y);
    }
    return threat;
}

} // namespace antgame::sdk::lure_strategy_detail
