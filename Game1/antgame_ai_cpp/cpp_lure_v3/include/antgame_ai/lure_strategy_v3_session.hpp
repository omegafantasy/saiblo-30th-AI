#pragma once

#include <array>
#include <cstdint>
#include <unordered_map>
#include <utility>

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

} // namespace antgame::sdk
