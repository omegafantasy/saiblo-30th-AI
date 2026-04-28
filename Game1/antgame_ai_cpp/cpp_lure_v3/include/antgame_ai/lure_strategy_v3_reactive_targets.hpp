#pragma once

#include <algorithm>
#include <limits>
#include <vector>

#include "antgame_ai/lure_strategy_v3_base_rules.hpp"

namespace antgame::sdk::lure_strategy_detail {

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
        if (nearest > v3_lure_config().forced_lure_sell_distance) {
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
        if (nearest > v3_lure_config().forced_lure_sell_distance) {
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

inline bool tower_threats_cleared_by_next_attack_phase(const rs::DefenseSimulator &simulator, const rs::SearchTower &tower) {
    std::vector<int> threatening_ant_ids;
    threatening_ant_ids.reserve(4);
    for (const auto &ant : simulator.ants) {
        if (ant.kind != AntKind::Combat || !ant.alive()) {
            continue;
        }
        if (hex_distance(tower.x, tower.y, ant.x, ant.y) <= v3_lure_config().forced_lure_sell_distance) {
            threatening_ant_ids.push_back(ant.ant_id);
        }
    }
    if (threatening_ant_ids.empty()) {
        return true;
    }

    rs::DefenseSimulator projected = simulator.clone();
    rs::FastRng rng(
        static_cast<std::uint64_t>(0x9e3779b97f4a7c15ULL) ^
        static_cast<std::uint64_t>((simulator.round_index + 1) * 131 + tower.tower_id * 977));
    projected.tower_attack_phase(rng);

    const rs::SearchTower *projected_tower = projected.tower_by_id(tower.tower_id);
    if (projected_tower == nullptr || !projected_tower->alive()) {
        return false;
    }
    for (int ant_id : threatening_ant_ids) {
        for (const auto &ant : projected.ants) {
            if (ant.ant_id == ant_id && ant.alive()) {
                return false;
            }
        }
    }
    return true;
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
        if (nearest > v3_lure_config().forced_lure_sell_distance) {
            continue;
        }
        if (tower_threats_cleared_by_next_attack_phase(simulator, tower)) {
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

} // namespace antgame::sdk::lure_strategy_detail
