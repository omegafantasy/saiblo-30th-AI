#pragma once

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <limits>
#include <vector>

#include "antgame_ai/lure_strategy_v4_base_rules.hpp"

namespace antgame::sdk::lure_strategy_detail {

struct V4ReactiveProfile {
    std::uint64_t forced_sell_calls = 0;
    std::uint64_t forced_sell_elapsed_us = 0;
    std::uint64_t forced_sell_candidate_towers = 0;
    std::uint64_t tower_clear_calls = 0;
    std::uint64_t tower_clear_elapsed_us = 0;
    std::uint64_t tower_clear_projected_calls = 0;
    std::uint64_t tower_clear_projected_elapsed_us = 0;
    std::uint64_t tower_clear_threatening_ants = 0;
};

inline thread_local V4ReactiveProfile *v4_reactive_profile = nullptr;

struct V4ReactiveProfileScope {
    V4ReactiveProfile *previous = nullptr;

    explicit V4ReactiveProfileScope(V4ReactiveProfile *next) : previous(v4_reactive_profile) {
        v4_reactive_profile = next;
    }

    ~V4ReactiveProfileScope() {
        v4_reactive_profile = previous;
    }
};

inline std::uint64_t v4_reactive_elapsed_us(std::chrono::steady_clock::time_point begin) {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now() - begin)
            .count());
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
        if (nearest > v4_lure_config().forced_lure_sell_distance) {
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
        if (nearest > v4_lure_config().forced_lure_sell_distance) {
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
    V4ReactiveProfile *profile = v4_reactive_profile;
    const auto begin = profile != nullptr ? std::chrono::steady_clock::now() : std::chrono::steady_clock::time_point{};
    if (profile != nullptr) {
        ++profile->tower_clear_calls;
    }
    auto finish = [&]() {
        if (profile != nullptr) {
            profile->tower_clear_elapsed_us += v4_reactive_elapsed_us(begin);
        }
    };
    std::vector<int> threatening_ant_ids;
    threatening_ant_ids.reserve(4);
    for (const auto &ant : simulator.ants) {
        if (ant.kind != AntKind::Combat || !ant.alive()) {
            continue;
        }
        if (hex_distance(tower.x, tower.y, ant.x, ant.y) <= v4_lure_config().forced_lure_sell_distance) {
            threatening_ant_ids.push_back(ant.ant_id);
        }
    }
    if (threatening_ant_ids.empty()) {
        finish();
        return true;
    }
    if (profile != nullptr) {
        profile->tower_clear_threatening_ants += static_cast<std::uint64_t>(threatening_ant_ids.size());
        ++profile->tower_clear_projected_calls;
    }

    const auto projected_begin = profile != nullptr ? std::chrono::steady_clock::now() : std::chrono::steady_clock::time_point{};
    rs::DefenseSimulator projected = simulator.clone();
    rs::FastRng rng(
        static_cast<std::uint64_t>(0x9e3779b97f4a7c15ULL) ^
        static_cast<std::uint64_t>((simulator.round_index + 1) * 131 + tower.tower_id * 977));
    projected.tower_attack_phase(rng);
    if (profile != nullptr) {
        profile->tower_clear_projected_elapsed_us += v4_reactive_elapsed_us(projected_begin);
    }

    const rs::SearchTower *projected_tower = projected.tower_by_id(tower.tower_id);
    if (projected_tower == nullptr || !projected_tower->alive()) {
        finish();
        return false;
    }
    for (int ant_id : threatening_ant_ids) {
        for (const auto &ant : projected.ants) {
            if (ant.ant_id == ant_id && ant.alive()) {
                finish();
                return false;
            }
        }
    }
    finish();
    return true;
}

inline const rs::SearchTower *forced_reactive_sell_target(const rs::DefenseSimulator &simulator, int player) {
    V4ReactiveProfile *profile = v4_reactive_profile;
    const auto begin = profile != nullptr ? std::chrono::steady_clock::now() : std::chrono::steady_clock::time_point{};
    if (profile != nullptr) {
        ++profile->forced_sell_calls;
    }
    auto finish = [&]() {
        if (profile != nullptr) {
            profile->forced_sell_elapsed_us += v4_reactive_elapsed_us(begin);
        }
    };
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
        if (nearest > v4_lure_config().forced_lure_sell_distance) {
            continue;
        }
        if (profile != nullptr) {
            ++profile->forced_sell_candidate_towers;
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
    finish();
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
