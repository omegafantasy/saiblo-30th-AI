#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "../../Ant-Game/game/include/json.hpp"

using json = nlohmann::json;

namespace {
constexpr int kMapSize = 19;
constexpr int kPlayerCount = 2;
constexpr int kDefaultBehavior = 0;
constexpr int kConservativeBehavior = 1;
constexpr int kRandomBehavior = 2;
constexpr int kBewitchedBehavior = 3;
constexpr int kControlFreeBehavior = 4;
constexpr int kStatusSuccess = 1;
constexpr int kStatusFail = 2;
constexpr int kStatusTooOld = 3;
constexpr int kStatusFrozen = 4;
constexpr int kBaseX[2] = {2, 16};
constexpr int kBaseY[2] = {9, 9};
constexpr double kDefaultMoveTemperature = 4.0;
constexpr double kBewitchMoveTemperature = 1.5;
constexpr double kCrowdingPenalty = 1.25;
constexpr int kRandomDecayTurns = 5;
constexpr int kSpecialDecayTurns = 5;
constexpr int kLastMoveStates = 7;
constexpr int kNoMoveIndex = 6;

const int kOffset[2][6][2] = {
    {{0, 1}, {-1, 0}, {0, -1}, {1, -1}, {1, 0}, {1, 1}},
    {{-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, 0}, {0, 1}},
};

struct AntState {
    int id = -1;
    int player = 0;
    int x = 0;
    int y = 0;
    int level = 0;
    double hp = 0.0;
    int status = 0;
    int behavior = 0;
    int behavior_turns = 0;
    int behavior_expiry = 0;
    int last_move = -1;
    bool frozen = false;
    int bewitch_target_x = -1;
    int bewitch_target_y = -1;
};

struct TowerState {
    int id = -1;
    int player = 0;
    int x = 0;
    int y = 0;
    int type = 0;
    int cooldown = 0;
};

struct MoveRow {
    int direction = -1;
    int x = -1;
    int y = -1;
    double prob = 0.0;
    double raw_score = 0.0;
    double score = 0.0;
};

struct DistributionResult {
    const char *kind = "stuck";
    int count = 0;
    std::array<MoveRow, 6> moves{};
};

struct Layout {
    std::array<std::array<bool, kMapSize>, kMapSize> valid{};
    std::array<std::array<int, kMapSize>, kMapSize> owner{};
    std::array<std::array<bool, kMapSize>, kMapSize> path{};
    std::array<std::array<int, kMapSize>, kMapSize> cell_index{};
    std::array<std::array<int, 6>, kMapSize * kMapSize> neighbor_cell{};
    std::array<int, kMapSize * kMapSize> neighbor_count{};
    std::array<std::array<int, kMapSize * kMapSize>, 2> distance_to_base{};
    std::array<std::array<bool, kMapSize * kMapSize>, 2> own_half{};

    Layout() {
        for (auto &row : owner) {
            row.fill(-1);
        }
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                cell_index[x][y] = x * kMapSize + y;
            }
        }

        int k = 19;
        for (int y = 9; y >= 0; --y) {
            for (int j = 0; j < k; ++j) {
                valid[(9 - y) / 2 + j][y] = true;
            }
            --k;
        }
        k = 19;
        for (int y = 9; y <= 18; ++y) {
            for (int j = 0; j < k; ++j) {
                valid[(y - 9) / 2 + j][y] = true;
            }
            --k;
        }

        const std::array<std::pair<int, int>, 100> invalid_blocks = {{
            {6, 1}, {7, 1}, {9, 1}, {11, 1}, {12, 1}, {4, 2}, {6, 2}, {8, 2}, {9, 2}, {11, 2},
            {13, 2}, {4, 3}, {5, 3}, {13, 3}, {14, 3}, {6, 4}, {8, 4}, {9, 4}, {11, 4}, {3, 5},
            {4, 5}, {7, 5}, {9, 5}, {11, 5}, {14, 5}, {15, 5}, {3, 6}, {5, 6}, {12, 6}, {14, 6},
            {2, 7}, {5, 7}, {6, 7}, {8, 7}, {9, 7}, {10, 7}, {12, 7}, {13, 7}, {16, 7}, {1, 8},
            {2, 8}, {7, 8}, {10, 8}, {15, 8}, {16, 8}, {0, 9}, {4, 9}, {5, 9}, {6, 9}, {9, 9},
            {12, 9}, {13, 9}, {14, 9}, {18, 9}, {1, 10}, {2, 10}, {7, 10}, {10, 10}, {15, 10}, {16, 10},
            {2, 11}, {5, 11}, {6, 11}, {8, 11}, {9, 11}, {10, 11}, {12, 11}, {13, 11}, {16, 11}, {3, 12},
            {5, 12}, {12, 12}, {14, 12}, {3, 13}, {4, 13}, {7, 13}, {9, 13}, {11, 13}, {14, 13}, {15, 13},
            {6, 14}, {8, 14}, {9, 14}, {11, 14}, {4, 15}, {5, 15}, {13, 15}, {14, 15}, {4, 16}, {6, 16},
            {8, 16}, {9, 16}, {11, 16}, {13, 16}, {6, 17}, {7, 17}, {9, 17}, {11, 17}, {12, 17}, {0, 0},
        }};
        for (const auto &[x, y] : invalid_blocks) {
            if (x == 0 && y == 0) {
                continue;
            }
            valid[x][y] = false;
        }

        const std::array<std::pair<int, int>, 33> player0_highlands = {{
            {6, 1}, {7, 1}, {4, 2}, {6, 2}, {8, 2}, {4, 3}, {5, 3}, {6, 4}, {8, 4}, {7, 5}, {5, 6},
            {5, 7}, {6, 7}, {8, 7}, {7, 8}, {4, 9}, {5, 9}, {6, 9}, {7, 10}, {5, 11}, {6, 11}, {8, 11},
            {5, 12}, {7, 13}, {6, 14}, {8, 14}, {4, 15}, {5, 15}, {4, 16}, {6, 16}, {8, 16}, {6, 17},
            {7, 17},
        }};
        for (const auto &[x, y] : player0_highlands) {
            owner[x][y] = 0;
        }
        const std::array<std::pair<int, int>, 33> player1_highlands = {{
            {11, 1}, {12, 1}, {9, 2}, {11, 2}, {13, 2}, {13, 3}, {14, 3}, {9, 4}, {11, 4}, {11, 5}, {12, 6},
            {10, 7}, {12, 7}, {13, 7}, {10, 8}, {12, 9}, {13, 9}, {14, 9}, {10, 10}, {10, 11}, {12, 11},
            {13, 11}, {12, 12}, {11, 13}, {9, 14}, {11, 14}, {13, 15}, {14, 15}, {9, 16}, {11, 16}, {13, 16},
            {11, 17}, {12, 17},
        }};
        for (const auto &[x, y] : player1_highlands) {
            owner[x][y] = 1;
        }

        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                const bool is_base = (x == kBaseX[0] && y == kBaseY[0]) || (x == kBaseX[1] && y == kBaseY[1]);
                path[x][y] = valid[x][y] && owner[x][y] == -1 && !is_base;
            }
        }

        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                const int idx = cell_index[x][y];
                int count = 0;
                for (int direction = 0; direction < 6; ++direction) {
                    const int nx = x + kOffset[y % 2][direction][0];
                    const int ny = y + kOffset[y % 2][direction][1];
                    if (0 <= nx && nx < kMapSize && 0 <= ny && ny < kMapSize && valid[nx][ny]) {
                        neighbor_cell[idx][count++] = cell_index[nx][ny];
                    }
                }
                neighbor_count[idx] = count;
            }
        }

        for (int player = 0; player < kPlayerCount; ++player) {
            for (int x = 0; x < kMapSize; ++x) {
                for (int y = 0; y < kMapSize; ++y) {
                    const int idx = cell_index[x][y];
                    distance_to_base[player][idx] = hex_distance(x, y, kBaseX[1 - player], kBaseY[1 - player]);
                    const int own_distance = hex_distance(x, y, kBaseX[player], kBaseY[player]);
                    const int enemy_distance = hex_distance(x, y, kBaseX[1 - player], kBaseY[1 - player]);
                    own_half[player][idx] = own_distance <= enemy_distance;
                }
            }
        }
    }

    static int hex_distance(int x0, int y0, int x1, int y1) {
        const int dy = std::abs(y0 - y1);
        int dx = 0;
        if (dy % 2) {
            if (x0 > x1) {
                dx = std::max(0, std::abs(x0 - x1) - dy / 2 - (y0 % 2));
            } else {
                dx = std::max(0, std::abs(x0 - x1) - dy / 2 - (1 - (y0 % 2)));
            }
        } else {
            dx = std::max(0, std::abs(x0 - x1) - dy / 2);
        }
        return dx + dy;
    }
};

const Layout &layout() {
    static const Layout kLayout;
    return kLayout;
}

int hex_distance(int x0, int y0, int x1, int y1) {
    return Layout::hex_distance(x0, y0, x1, y1);
}

bool is_base_cell(int x, int y) {
    return (x == kBaseX[0] && y == kBaseY[0]) || (x == kBaseX[1] && y == kBaseY[1]);
}

bool is_walkable_cell(int x, int y) {
    const auto &g = layout();
    if (x < 0 || x >= kMapSize || y < 0 || y >= kMapSize || !g.valid[x][y]) {
        return false;
    }
    return g.path[x][y] || is_base_cell(x, y);
}

void softmax_small(const std::array<double, 6> &scores, int count, double temperature, std::array<double, 6> &out) {
    if (count <= 0) {
        return;
    }
    const double scale = std::max(temperature, 1e-6);
    double max_score = scores[0];
    for (int index = 1; index < count; ++index) {
        max_score = std::max(max_score, scores[index]);
    }
    double total = 0.0;
    for (int index = 0; index < count; ++index) {
        out[index] = std::exp((scores[index] - max_score) / scale);
        total += out[index];
    }
    if (total <= 0.0) {
        const double uniform = 1.0 / static_cast<double>(count);
        for (int index = 0; index < count; ++index) {
            out[index] = uniform;
        }
        return;
    }
    for (int index = 0; index < count; ++index) {
        out[index] /= total;
    }
}

std::vector<AntState> parse_ants(const json &payload) {
    std::vector<AntState> ants;
    if (!payload.contains("ants")) {
        return ants;
    }
    for (const auto &row : payload.at("ants")) {
        AntState ant;
        ant.id = row.value("id", -1);
        ant.player = row.value("player", 0);
        ant.x = row.value("x", 0);
        ant.y = row.value("y", 0);
        ant.level = row.value("level", 0);
        ant.hp = row.value("hp", 10.0);
        ant.status = row.value("status", 0);
        ant.behavior = row.value("behavior", 0);
        ant.behavior_turns = row.value("behavior_turns", 0);
        ant.behavior_expiry = row.value("behavior_expiry", ant.behavior == kDefaultBehavior || ant.behavior == kRandomBehavior ? 0 : kSpecialDecayTurns);
        ant.last_move = row.value("last_move", -1);
        ant.frozen = row.value("frozen", ant.status == kStatusFrozen);
        ant.bewitch_target_x = row.value("bewitch_target_x", -1);
        ant.bewitch_target_y = row.value("bewitch_target_y", -1);
        ants.push_back(ant);
    }
    return ants;
}

std::vector<TowerState> parse_towers(const json &payload) {
    std::vector<TowerState> towers;
    if (!payload.contains("towers")) {
        return towers;
    }
    towers.reserve(payload.at("towers").size());
    for (const auto &row : payload.at("towers")) {
        TowerState tower;
        tower.id = row.value("id", -1);
        tower.player = row.value("player", 0);
        tower.x = row.value("x", 0);
        tower.y = row.value("y", 0);
        tower.type = row.value("type", 0);
        tower.cooldown = row.value("cooldown", 0);
        towers.push_back(tower);
    }
    return towers;
}

std::array<std::array<std::array<int, kMapSize>, kMapSize>, kPlayerCount> parse_pheromone(const json &payload) {
    std::array<std::array<std::array<int, kMapSize>, kMapSize>, kPlayerCount> pheromone{};
    if (!payload.contains("pheromone")) {
        pheromone[0].fill(std::array<int, kMapSize>{});
        pheromone[1].fill(std::array<int, kMapSize>{});
        return pheromone;
    }
    for (int player = 0; player < kPlayerCount; ++player) {
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                pheromone[player][x][y] = payload.at("pheromone").at(player).at(x).at(y).get<int>();
            }
        }
    }
    return pheromone;
}

std::vector<int> parse_query_ids(const json &payload, const std::vector<AntState> &ants) {
    if (!payload.contains("query_ant_ids")) {
        std::vector<int> all;
        all.reserve(ants.size());
        for (const auto &ant : ants) {
            all.push_back(ant.id);
        }
        return all;
    }
    return payload.at("query_ant_ids").get<std::vector<int>>();
}

int last_move_index(int last_move) {
    return (0 <= last_move && last_move < 6) ? last_move : kNoMoveIndex;
}

int last_move_from_index(int index) {
    return (0 <= index && index < 6) ? index : -1;
}

double level_weight(int level) {
    static const double kWeights[3] = {1.0, 1.8, 2.8};
    return kWeights[std::clamp(level, 0, 2)];
}

int tower_damage(int tower_type) {
    switch (tower_type) {
    case 0: return 5;
    case 1: return 20;
    case 2: return 6;
    case 3: return 16;
    case 11: return 35;
    case 12: return 15;
    case 13: return 10;
    case 21: return 8;
    case 22: return 7;
    case 23: return 15;
    case 31: return 35;
    case 32: return 12;
    case 33: return 45;
    default: return 0;
    }
}

double tower_speed(int tower_type) {
    switch (tower_type) {
    case 0: return 2.0;
    case 1: return 2.0;
    case 2: return 1.0;
    case 3: return 4.0;
    case 11: return 2.0;
    case 12: return 2.0;
    case 13: return 3.0;
    case 21: return 0.5;
    case 22: return 1.0;
    case 23: return 2.0;
    case 31: return 4.0;
    case 32: return 3.0;
    case 33: return 6.0;
    default: return 1.0;
    }
}

int tower_range(int tower_type) {
    switch (tower_type) {
    case 0: return 2;
    case 1: return 2;
    case 2: return 3;
    case 3: return 3;
    case 11: return 3;
    case 12: return 2;
    case 13: return 3;
    case 21: return 3;
    case 22: return 4;
    case 23: return 6;
    case 31: return 4;
    case 32: return 2;
    case 33: return 5;
    default: return 0;
    }
}

int tower_target_num(int tower_type) {
    return tower_type == 22 ? 2 : 1;
}

struct ForecastAnt {
    AntState meta;
    int frozen_turns = 0;
    std::array<double, kMapSize * kMapSize * kLastMoveStates> current{};
    std::array<double, kMapSize * kMapSize * kLastMoveStates> next{};
};

int forecast_index(int cell, int last_move_idx) {
    return cell * kLastMoveStates + last_move_idx;
}

void decay_behavior(AntState &ant) {
    ant.behavior_turns += 1;
    if (ant.behavior == kRandomBehavior && ant.behavior_turns >= kRandomDecayTurns) {
        ant.behavior = kDefaultBehavior;
        ant.behavior_turns = 0;
        ant.behavior_expiry = 0;
        ant.bewitch_target_x = -1;
        ant.bewitch_target_y = -1;
        return;
    }
    if (ant.behavior == kBewitchedBehavior || ant.behavior == kConservativeBehavior || ant.behavior == kControlFreeBehavior) {
        if (ant.behavior_expiry > 0) {
            ant.behavior_expiry -= 1;
            if (ant.behavior_expiry <= 0) {
                ant.behavior = kDefaultBehavior;
                ant.behavior_turns = 0;
                ant.bewitch_target_x = -1;
                ant.bewitch_target_y = -1;
            }
        }
    }
}

struct KernelState {
    std::vector<AntState> ants;
    std::vector<TowerState> towers;
    std::array<std::array<std::array<int, kMapSize>, kMapSize>, kPlayerCount> pheromone{};
    std::array<std::array<int, kMapSize * kMapSize>, kPlayerCount> occ{};
    std::array<std::array<int, kMapSize * kMapSize>, kPlayerCount> adj_occ{};

    void rebuild_occupancy() {
        for (auto &player_occ : occ) {
            player_occ.fill(0);
        }
        for (auto &player_adj : adj_occ) {
            player_adj.fill(0);
        }
        for (const auto &ant : ants) {
            if (ant.status == kStatusFail || ant.status == kStatusTooOld) {
                continue;
            }
            const int idx = ant.x * kMapSize + ant.y;
            occ[ant.player][idx] += 1;
        }
        const auto &g = layout();
        for (int player = 0; player < kPlayerCount; ++player) {
            for (int idx = 0; idx < kMapSize * kMapSize; ++idx) {
                int sum = 0;
                for (int ni = 0; ni < g.neighbor_count[idx]; ++ni) {
                    sum += occ[player][g.neighbor_cell[idx][ni]];
                }
                adj_occ[player][idx] = sum;
            }
        }
    }

    double crowding_penalty(const AntState &ant, int nx, int ny) const {
        const int target_idx = nx * kMapSize + ny;
        int same = occ[ant.player][target_idx];
        int adj = adj_occ[ant.player][target_idx];
        if (ant.x == nx && ant.y == ny) {
            same -= 1;
        }
        if (hex_distance(nx, ny, ant.x, ant.y) == 1) {
            adj -= 1;
        }
        same = std::max(0, same);
        adj = std::max(0, adj);
        return static_cast<double>(same) + 0.35 * static_cast<double>(adj);
    }

    DistributionResult compute_distribution(const AntState &ant) const {
        struct Candidate {
            int direction;
            int x;
            int y;
        };
        std::array<Candidate, 6> candidates{};
        int candidate_count = 0;
        auto collect = [&](bool allow_backtrack) {
            candidate_count = 0;
            for (int direction = 0; direction < 6; ++direction) {
                const int nx = ant.x + kOffset[ant.y % 2][direction][0];
                const int ny = ant.y + kOffset[ant.y % 2][direction][1];
                if (!allow_backtrack && ant.last_move >= 0 && ant.last_move == ((direction + 3) % 6)) {
                    continue;
                }
                if (!is_walkable_cell(nx, ny)) {
                    continue;
                }
                candidates[candidate_count++] = {direction, nx, ny};
            }
        };

        const bool allow_backtrack = ant.behavior == kRandomBehavior || ant.behavior == kBewitchedBehavior;
        collect(allow_backtrack);
        if (candidate_count == 0 && !allow_backtrack) {
            collect(true);
        }
        if (candidate_count == 0) {
            return {"stuck", 0, {}};
        }

        std::array<double, 6> raw_scores{};
        std::array<double, 6> scores{};
        std::array<double, 6> probabilities{};
        DistributionResult result;

        if (ant.behavior == kRandomBehavior) {
            const double probability = 1.0 / static_cast<double>(candidate_count);
            result.kind = "uniform";
            result.count = candidate_count;
            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                result.moves[index] = {candidate.direction, candidate.x, candidate.y, probability, 0.0, 0.0};
            }
            return result;
        }

        if (ant.behavior == kBewitchedBehavior && ant.bewitch_target_x >= 0 && ant.bewitch_target_y >= 0) {
            const int current_distance = hex_distance(ant.x, ant.y, ant.bewitch_target_x, ant.bewitch_target_y);
            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                const int next_distance = hex_distance(candidate.x, candidate.y, ant.bewitch_target_x, ant.bewitch_target_y);
                const double crowd = crowding_penalty(ant, candidate.x, candidate.y);
                const double score = static_cast<double>(current_distance - next_distance) * 4.0 - kCrowdingPenalty * crowd;
                raw_scores[index] = score;
                scores[index] = score;
            }
            softmax_small(scores, candidate_count, kBewitchMoveTemperature, probabilities);
        } else {
            const int enemy_x = kBaseX[1 - ant.player];
            const int enemy_y = kBaseY[1 - ant.player];
            const int current_distance = hex_distance(ant.x, ant.y, enemy_x, enemy_y);
            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                const int next_distance = hex_distance(candidate.x, candidate.y, enemy_x, enemy_y);
                const double weight = next_distance < current_distance ? 1.25 : (next_distance == current_distance ? 1.0 : 0.75);
                const double raw = static_cast<double>(pheromone[ant.player][candidate.x][candidate.y]) * weight;
                const double score = raw - kCrowdingPenalty * crowding_penalty(ant, candidate.x, candidate.y);
                raw_scores[index] = raw;
                scores[index] = score;
            }
            if (ant.behavior == kConservativeBehavior || ant.behavior == kControlFreeBehavior) {
                int best = 0;
                for (int index = 1; index < candidate_count; ++index) {
                    if (raw_scores[index] > raw_scores[best]) {
                        best = index;
                    }
                }
                probabilities[best] = 1.0;
            } else {
                softmax_small(scores, candidate_count, kDefaultMoveTemperature, probabilities);
            }
        }

        result.count = candidate_count;
        for (int index = 0; index < candidate_count; ++index) {
            result.moves[index] = {
                candidates[index].direction,
                candidates[index].x,
                candidates[index].y,
                probabilities[index],
                raw_scores[index],
                scores[index],
            };
        }
        std::sort(result.moves.begin(), result.moves.begin() + candidate_count, [](const MoveRow &lhs, const MoveRow &rhs) {
            if (lhs.prob != rhs.prob) {
                return lhs.prob > rhs.prob;
            }
            return lhs.direction < rhs.direction;
        });
        result.kind = "default";
        if (ant.behavior == kConservativeBehavior) {
            result.kind = "conservative";
        } else if (ant.behavior == kControlFreeBehavior) {
            result.kind = "control_free";
        } else if (ant.behavior == kBewitchedBehavior) {
            result.kind = "bewitched";
        }
        return result;
    }

    json exact_distribution(const AntState &ant) const {
        const DistributionResult distribution = compute_distribution(ant);
        json moves = json::array();
        for (int index = 0; index < distribution.count; ++index) {
            const auto &row = distribution.moves[index];
            if (std::string_view(distribution.kind) == "uniform") {
                moves.push_back({
                    {"direction", row.direction},
                    {"x", row.x},
                    {"y", row.y},
                    {"prob", row.prob},
                    {"raw_score", nullptr},
                    {"score", nullptr},
                });
            } else {
                moves.push_back({
                    {"direction", row.direction},
                    {"x", row.x},
                    {"y", row.y},
                    {"prob", row.prob},
                    {"raw_score", row.raw_score},
                    {"score", row.score},
                });
            }
        }
        return json{{"id", ant.id}, {"kind", distribution.kind}, {"moves", moves}};
    }
};

KernelState load_state_from_json(const json &payload) {
    KernelState state;
    state.ants = parse_ants(payload);
    state.towers = parse_towers(payload);
    state.pheromone = parse_pheromone(payload);
    state.rebuild_occupancy();
    return state;
}

json run_cli_from_payload(const json &payload) {
    KernelState state = load_state_from_json(payload);
    const std::vector<int> query_ids = parse_query_ids(payload, state.ants);
    json distributions = json::array();
    for (int ant_id : query_ids) {
        auto it = std::find_if(state.ants.begin(), state.ants.end(), [&](const AntState &ant) { return ant.id == ant_id; });
        if (it == state.ants.end()) {
            continue;
        }
        distributions.push_back(state.exact_distribution(*it));
    }
    return json{
        {"ant_count", state.ants.size()},
        {"query_count", distributions.size()},
        {"distributions", distributions},
    };
}

json summarize_top_cells(const std::array<double, kMapSize * kMapSize> &mass, int limit) {
    struct CellMass {
        int cell = -1;
        double mass = 0.0;
    };
    std::vector<CellMass> rows;
    rows.reserve(kMapSize * kMapSize);
    for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
        if (mass[cell] <= 1e-12) {
            continue;
        }
        rows.push_back({cell, mass[cell]});
    }
    std::sort(rows.begin(), rows.end(), [](const CellMass &lhs, const CellMass &rhs) {
        if (lhs.mass != rhs.mass) {
            return lhs.mass > rhs.mass;
        }
        return lhs.cell < rhs.cell;
    });
    json out = json::array();
    const int count = std::min<int>(limit, rows.size());
    for (int index = 0; index < count; ++index) {
        const int cell = rows[index].cell;
        out.push_back({
            {"x", cell / kMapSize},
            {"y", cell % kMapSize},
            {"mass", rows[index].mass},
        });
    }
    return out;
}

json run_expected_front(const json &payload) {
    const int steps = std::max(1, payload.value("steps", 4));
    const int focus_player = payload.value("focus_player", 0);
    const int top_k = std::max(1, payload.value("top_k", 8));
    KernelState base = load_state_from_json(payload);
    const std::vector<int> query_ids = parse_query_ids(payload, base.ants);

    std::vector<ForecastAnt> ants;
    ants.reserve(base.ants.size());
    for (const auto &ant : base.ants) {
        ForecastAnt forecast;
        forecast.meta = ant;
        forecast.frozen_turns = ant.frozen ? 1 : 0;
        if (ant.status != kStatusFail && ant.status != kStatusTooOld && ant.status != kStatusSuccess) {
            const int cell = ant.x * kMapSize + ant.y;
            forecast.current[forecast_index(cell, last_move_index(ant.last_move))] = 1.0;
        }
        ants.push_back(forecast);
    }
    std::vector<TowerState> tower_states = base.towers;

    auto aggregate_cell_mass = [&](const ForecastAnt &ant) {
        std::array<double, kMapSize * kMapSize> cell_mass{};
        for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
            double sum = 0.0;
            for (int last = 0; last < kLastMoveStates; ++last) {
                sum += ant.current[forecast_index(cell, last)];
            }
            cell_mass[cell] = sum;
        }
        return cell_mass;
    };

    auto aggregate_adj_mass = [&](const std::array<double, kMapSize * kMapSize> &cell_mass) {
        std::array<double, kMapSize * kMapSize> adj{};
        const auto &g = layout();
        for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
            double sum = 0.0;
            for (int ni = 0; ni < g.neighbor_count[cell]; ++ni) {
                sum += cell_mass[g.neighbor_cell[cell][ni]];
            }
            adj[cell] = sum;
        }
        return adj;
    };

    auto emit_round = [&](int round_index) {
        std::array<std::array<double, kMapSize * kMapSize>, kPlayerCount> player_mass{};
        std::array<double, kMapSize * kMapSize> query_mass{};
        double enemy_pressure = 0.0;
        double own_pressure = 0.0;
        for (const auto &ant : ants) {
            const auto cell_mass = aggregate_cell_mass(ant);
            for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                player_mass[ant.meta.player][cell] += cell_mass[cell];
            }
            if (std::find(query_ids.begin(), query_ids.end(), ant.meta.id) != query_ids.end()) {
                for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                    query_mass[cell] += cell_mass[cell];
                }
            }
            for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                if (cell_mass[cell] <= 1e-12) {
                    continue;
                }
                const int x = cell / kMapSize;
                const int y = cell % kMapSize;
                const double weight = level_weight(ant.meta.level);
                if (ant.meta.player == 1 - focus_player) {
                    enemy_pressure += cell_mass[cell] * weight * std::max(0, 10 - hex_distance(x, y, kBaseX[focus_player], kBaseY[focus_player]));
                } else if (ant.meta.player == focus_player) {
                    own_pressure += cell_mass[cell] * weight * std::max(0, 10 - hex_distance(x, y, kBaseX[1 - focus_player], kBaseY[1 - focus_player]));
                }
            }
        }
        return json{
            {"round", round_index},
            {"enemy_pressure", enemy_pressure},
            {"own_pressure", own_pressure},
            {"query_top_positions", summarize_top_cells(query_mass, top_k)},
            {"player0_top_positions", summarize_top_cells(player_mass[0], top_k)},
            {"player1_top_positions", summarize_top_cells(player_mass[1], top_k)},
        };
    };

    auto aggregate_all_masses =
        [&](const std::vector<ForecastAnt> &src_ants,
            std::array<std::array<double, kMapSize * kMapSize>, kPlayerCount> &player_mass,
            std::vector<std::array<double, kMapSize * kMapSize>> &self_occ,
            std::vector<std::array<double, kMapSize * kMapSize>> &self_adj) {
            player_mass = {};
            self_occ.clear();
            self_adj.clear();
            self_occ.reserve(src_ants.size());
            self_adj.reserve(src_ants.size());
            for (const auto &ant : src_ants) {
                auto cell_mass = aggregate_cell_mass(ant);
                self_occ.push_back(cell_mass);
                self_adj.push_back(aggregate_adj_mass(cell_mass));
                for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                    player_mass[ant.meta.player][cell] += cell_mass[cell];
                }
            }
        };

    auto compute_damage_maps =
        [&](const std::array<std::array<double, kMapSize * kMapSize>, kPlayerCount> &player_mass) {
            std::array<std::array<double, kMapSize * kMapSize>, kPlayerCount> damage_on_player{};
            struct CandidateCell {
                int cell = -1;
                int dist = 0;
                double mass = 0.0;
            };
            auto add_radius = [&](int attacked_player, int center_cell, int radius, double amount) {
                const int cx = center_cell / kMapSize;
                const int cy = center_cell % kMapSize;
                for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                    const int x = cell / kMapSize;
                    const int y = cell % kMapSize;
                    if (!layout().valid[x][y]) {
                        continue;
                    }
                    if (hex_distance(cx, cy, x, y) <= radius) {
                        damage_on_player[attacked_player][cell] += amount;
                    }
                }
            };
            for (auto &tower : tower_states) {
                const int attacked_player = 1 - tower.player;
                const double speed = tower_speed(tower.type);
                if (speed >= 1.0 && tower.cooldown > 0) {
                    tower.cooldown -= 1;
                }
                const bool ready = speed < 1.0 ? true : tower.cooldown <= 0;
                std::vector<CandidateCell> candidates;
                for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                    if (player_mass[attacked_player][cell] <= 1e-12) {
                        continue;
                    }
                    const int x = cell / kMapSize;
                    const int y = cell % kMapSize;
                    const int dist = hex_distance(tower.x, tower.y, x, y);
                    if (dist <= tower_range(tower.type)) {
                        candidates.push_back({cell, dist, player_mass[attacked_player][cell]});
                    }
                }
                std::sort(candidates.begin(), candidates.end(), [](const CandidateCell &lhs, const CandidateCell &rhs) {
                    if (lhs.dist != rhs.dist) {
                        return lhs.dist < rhs.dist;
                    }
                    if (lhs.mass != rhs.mass) {
                        return lhs.mass > rhs.mass;
                    }
                    return lhs.cell < rhs.cell;
                });
                if (!ready || candidates.empty()) {
                    continue;
                }
                const int repetitions = speed < 1.0 ? std::max(1, static_cast<int>(std::round(1.0 / speed))) : 1;
                const int target_count = std::min<int>(tower_target_num(tower.type), candidates.size());
                const double shot_budget = static_cast<double>(tower_damage(tower.type));
                for (int rep = 0; rep < repetitions; ++rep) {
                    if (tower.type == 32) {
                        for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                            const int x = cell / kMapSize;
                            const int y = cell % kMapSize;
                            if (player_mass[attacked_player][cell] <= 1e-12) {
                                continue;
                            }
                            if (hex_distance(tower.x, tower.y, x, y) <= tower_range(tower.type)) {
                                damage_on_player[attacked_player][cell] += shot_budget;
                            }
                        }
                        continue;
                    }
                    for (int index = 0; index < target_count; ++index) {
                        const int target_cell = candidates[index].cell;
                        if (tower.type == 3 || tower.type == 31) {
                            add_radius(attacked_player, target_cell, 1, shot_budget);
                        } else if (tower.type == 33) {
                            add_radius(attacked_player, target_cell, 2, shot_budget);
                        } else {
                            damage_on_player[attacked_player][target_cell] += shot_budget;
                        }
                    }
                }
                if (speed >= 1.0) {
                    tower.cooldown = static_cast<int>(std::round(speed));
                }
            }
            return damage_on_player;
        };

    json rounds = json::array();
    rounds.push_back(emit_round(0));

    for (int step = 0; step < steps; ++step) {
        std::array<std::array<double, kMapSize * kMapSize>, kPlayerCount> occ_all{};
        std::vector<std::array<double, kMapSize * kMapSize>> self_occ;
        std::vector<std::array<double, kMapSize * kMapSize>> self_adj;
        aggregate_all_masses(ants, occ_all, self_occ, self_adj);

        const auto damage_on_player = compute_damage_maps(occ_all);
        for (std::size_t ant_index = 0; ant_index < ants.size(); ++ant_index) {
            auto &ant = ants[ant_index];
            if (ant.meta.hp <= 1e-9) {
                ant.current.fill(0.0);
                continue;
            }
            double avg_damage = 0.0;
            for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                const double damage = damage_on_player[ant.meta.player][cell];
                if (damage <= 1e-12) {
                    continue;
                }
                for (int last = 0; last < kLastMoveStates; ++last) {
                    const int idx = forecast_index(cell, last);
                    const double mass = ant.current[idx];
                    if (mass <= 1e-12) {
                        continue;
                    }
                    avg_damage += mass * std::min(damage, ant.meta.hp);
                    const double survive = std::max(0.0, 1.0 - damage / std::max(ant.meta.hp, 1e-9));
                    ant.current[idx] *= survive;
                }
            }
            ant.meta.hp = std::max(0.0, ant.meta.hp - avg_damage);
            if (ant.meta.hp <= 1e-9) {
                ant.current.fill(0.0);
            }
        }

        aggregate_all_masses(ants, occ_all, self_occ, self_adj);
        std::array<std::array<double, kMapSize * kMapSize>, kPlayerCount> adj_all{};
        for (int player = 0; player < kPlayerCount; ++player) {
            adj_all[player] = aggregate_adj_mass(occ_all[player]);
        }

        for (std::size_t ant_index = 0; ant_index < ants.size(); ++ant_index) {
            auto &ant = ants[ant_index];
            ant.next.fill(0.0);
            if (ant.frozen_turns > 0) {
                for (int idx = 0; idx < kMapSize * kMapSize * kLastMoveStates; ++idx) {
                    const double mass = ant.current[idx];
                    if (mass <= 1e-12) {
                        continue;
                    }
                    const int cell = idx / kLastMoveStates;
                    ant.next[forecast_index(cell, kNoMoveIndex)] += mass;
                }
                continue;
            }
            for (int cell = 0; cell < kMapSize * kMapSize; ++cell) {
                const int x = cell / kMapSize;
                const int y = cell % kMapSize;
                for (int last_idx = 0; last_idx < kLastMoveStates; ++last_idx) {
                    const double state_mass = ant.current[forecast_index(cell, last_idx)];
                    if (state_mass <= 1e-12) {
                        continue;
                    }
                    int behavior = ant.meta.behavior;
                    if (behavior == kBewitchedBehavior && x == ant.meta.bewitch_target_x && y == ant.meta.bewitch_target_y) {
                        behavior = kDefaultBehavior;
                    }
                    const bool allow_backtrack = behavior == kRandomBehavior || behavior == kBewitchedBehavior;
                    std::array<int, 6> dir{};
                    std::array<int, 6> next_cell{};
                    std::array<double, 6> raw_scores{};
                    std::array<double, 6> scores{};
                    std::array<double, 6> probs{};
                    int candidate_count = 0;
                    auto collect = [&](bool allow_reverse) {
                        candidate_count = 0;
                        for (int direction = 0; direction < 6; ++direction) {
                            const int nx = x + kOffset[y % 2][direction][0];
                            const int ny = y + kOffset[y % 2][direction][1];
                            if (!allow_reverse && last_move_from_index(last_idx) >= 0 && last_move_from_index(last_idx) == ((direction + 3) % 6)) {
                                continue;
                            }
                            if (!is_walkable_cell(nx, ny)) {
                                continue;
                            }
                            dir[candidate_count] = direction;
                            next_cell[candidate_count] = nx * kMapSize + ny;
                            candidate_count += 1;
                        }
                    };
                    collect(allow_backtrack);
                    if (candidate_count == 0 && !allow_backtrack) {
                        collect(true);
                    }
                    if (candidate_count == 0) {
                        ant.next[forecast_index(cell, kNoMoveIndex)] += state_mass;
                        continue;
                    }
                    if (behavior == kRandomBehavior) {
                        const double prob = 1.0 / static_cast<double>(candidate_count);
                        for (int index = 0; index < candidate_count; ++index) {
                            ant.next[forecast_index(next_cell[index], dir[index])] += state_mass * prob;
                        }
                        continue;
                    }
                    for (int index = 0; index < candidate_count; ++index) {
                        const int to_cell = next_cell[index];
                        const int nx = to_cell / kMapSize;
                        const int ny = to_cell % kMapSize;
                        const double same = std::max(0.0, occ_all[ant.meta.player][to_cell] - self_occ[ant_index][to_cell]);
                        const double adj = std::max(0.0, adj_all[ant.meta.player][to_cell] - self_adj[ant_index][to_cell]);
                        const double crowd = same + 0.35 * adj;
                        if (behavior == kBewitchedBehavior && ant.meta.bewitch_target_x >= 0 && ant.meta.bewitch_target_y >= 0) {
                            const int current_distance = hex_distance(x, y, ant.meta.bewitch_target_x, ant.meta.bewitch_target_y);
                            const int next_distance = hex_distance(nx, ny, ant.meta.bewitch_target_x, ant.meta.bewitch_target_y);
                            raw_scores[index] = static_cast<double>(current_distance - next_distance) * 4.0 - kCrowdingPenalty * crowd;
                            scores[index] = raw_scores[index];
                        } else {
                            const int current_distance = hex_distance(x, y, kBaseX[1 - ant.meta.player], kBaseY[1 - ant.meta.player]);
                            const int next_distance = hex_distance(nx, ny, kBaseX[1 - ant.meta.player], kBaseY[1 - ant.meta.player]);
                            const double weight = next_distance < current_distance ? 1.25 : (next_distance == current_distance ? 1.0 : 0.75);
                            raw_scores[index] = static_cast<double>(base.pheromone[ant.meta.player][nx][ny]) * weight;
                            scores[index] = raw_scores[index] - kCrowdingPenalty * crowd;
                        }
                    }
                    if (behavior == kConservativeBehavior || behavior == kControlFreeBehavior) {
                        int best = 0;
                        for (int index = 1; index < candidate_count; ++index) {
                            if (raw_scores[index] > raw_scores[best]) {
                                best = index;
                            }
                        }
                        probs[best] = 1.0;
                    } else if (behavior == kBewitchedBehavior && ant.meta.bewitch_target_x >= 0 && ant.meta.bewitch_target_y >= 0) {
                        softmax_small(scores, candidate_count, kBewitchMoveTemperature, probs);
                    } else {
                        softmax_small(scores, candidate_count, kDefaultMoveTemperature, probs);
                    }
                    for (int index = 0; index < candidate_count; ++index) {
                        ant.next[forecast_index(next_cell[index], dir[index])] += state_mass * probs[index];
                    }
                }
            }
        }

        for (auto &ant : ants) {
            ant.current = ant.next;
            ant.next.fill(0.0);
            if (ant.frozen_turns > 0) {
                ant.frozen_turns -= 1;
            }
            decay_behavior(ant.meta);
        }
        rounds.push_back(emit_round(step + 1));
    }

    return json{
        {"mode", "expected_front"},
        {"steps", steps},
        {"focus_player", focus_player},
        {"query_ant_ids", query_ids},
        {"rounds", rounds},
    };
}

json run_benchmark(int ants_per_player, int loops) {
    KernelState state;
    for (int player = 0; player < kPlayerCount; ++player) {
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                state.pheromone[player][x][y] = 80000;
            }
        }
    }
    int next_id = 0;
    for (int player = 0; player < kPlayerCount; ++player) {
        std::vector<std::pair<int, int>> cells;
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                if (!layout().path[x][y]) {
                    continue;
                }
                const int own_distance = hex_distance(x, y, kBaseX[player], kBaseY[player]);
                const int enemy_distance = hex_distance(x, y, kBaseX[1 - player], kBaseY[1 - player]);
                if (own_distance >= enemy_distance) {
                    continue;
                }
                cells.emplace_back(x, y);
            }
        }
        std::sort(cells.begin(), cells.end(), [player](const auto &lhs, const auto &rhs) {
            const int lhs_dist = hex_distance(lhs.first, lhs.second, kBaseX[player], kBaseY[player]);
            const int rhs_dist = hex_distance(rhs.first, rhs.second, kBaseX[player], kBaseY[player]);
            if (lhs_dist != rhs_dist) {
                return lhs_dist < rhs_dist;
            }
            return lhs.second < rhs.second;
        });
        for (int index = 0; index < std::min<int>(ants_per_player, cells.size()); ++index) {
            const int x = cells[index].first;
            const int y = cells[index].second;
            const int behavior = index % 4;
            state.ants.push_back({next_id++, player, x, y, 0, 25.0, 0, behavior, 0, 0, -1, false, player == 0 ? kBaseX[1] : kBaseX[0], 9});
        }
    }
    state.rebuild_occupancy();

    const auto start = std::chrono::steady_clock::now();
    int eval_count = 0;
    int candidate_count = 0;
    for (int loop = 0; loop < loops; ++loop) {
        for (const auto &ant : state.ants) {
            const DistributionResult result = state.compute_distribution(ant);
            candidate_count += result.count;
            eval_count += 1;
        }
    }
    const auto end = std::chrono::steady_clock::now();
    const double seconds = std::chrono::duration<double>(end - start).count();
    return json{
        {"mode", "benchmark"},
        {"ants_per_player", ants_per_player},
        {"ant_count", state.ants.size()},
        {"loops", loops},
        {"eval_count", eval_count},
        {"candidate_count", candidate_count},
        {"mean_candidates_per_eval", eval_count > 0 ? static_cast<double>(candidate_count) / static_cast<double>(eval_count) : 0.0},
        {"seconds", seconds},
        {"evals_per_sec", seconds > 0.0 ? static_cast<double>(eval_count) / seconds : 0.0},
    };
}

json build_benchmark_payload(int ants_per_player, int steps) {
    json ants = json::array();
    json pheromone = json::array();
    int next_id = 0;
    for (int player = 0; player < kPlayerCount; ++player) {
        json player_grid = json::array();
        for (int x = 0; x < kMapSize; ++x) {
            json col = json::array();
            for (int y = 0; y < kMapSize; ++y) {
                col.push_back(80000);
            }
            player_grid.push_back(col);
        }
        pheromone.push_back(player_grid);
    }
    for (int player = 0; player < kPlayerCount; ++player) {
        std::vector<std::pair<int, int>> cells;
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                if (!layout().path[x][y]) {
                    continue;
                }
                const int own_distance = hex_distance(x, y, kBaseX[player], kBaseY[player]);
                const int enemy_distance = hex_distance(x, y, kBaseX[1 - player], kBaseY[1 - player]);
                if (own_distance >= enemy_distance) {
                    continue;
                }
                cells.emplace_back(x, y);
            }
        }
        std::sort(cells.begin(), cells.end(), [player](const auto &lhs, const auto &rhs) {
            const int lhs_dist = hex_distance(lhs.first, lhs.second, kBaseX[player], kBaseY[player]);
            const int rhs_dist = hex_distance(rhs.first, rhs.second, kBaseX[player], kBaseY[player]);
            if (lhs_dist != rhs_dist) {
                return lhs_dist < rhs_dist;
            }
            return lhs.second < rhs.second;
        });
        for (int index = 0; index < std::min<int>(ants_per_player, cells.size()); ++index) {
            const int x = cells[index].first;
            const int y = cells[index].second;
            const int behavior = index % 4;
            ants.push_back({
                {"id", next_id++},
                {"player", player},
                {"x", x},
                {"y", y},
                {"level", index % 3},
                {"hp", 25.0 + 10.0 * static_cast<double>(index % 3)},
                {"status", 0},
                {"behavior", behavior},
                {"behavior_turns", 0},
                {"behavior_expiry", behavior == kDefaultBehavior || behavior == kRandomBehavior ? 0 : kSpecialDecayTurns},
                {"last_move", -1},
                {"frozen", false},
                {"bewitch_target_x", player == 0 ? kBaseX[1] : kBaseX[0]},
                {"bewitch_target_y", 9},
            });
        }
    }
    return json{
        {"ants", ants},
        {"towers", json::array()},
        {"pheromone", pheromone},
        {"steps", steps},
        {"focus_player", 0},
        {"top_k", 8},
    };
}

json run_expected_front_benchmark(int ants_per_player, int loops, int steps) {
    const json payload = build_benchmark_payload(ants_per_player, steps);
    const auto start = std::chrono::steady_clock::now();
    int rounds_generated = 0;
    for (int loop = 0; loop < loops; ++loop) {
        json out = run_expected_front(payload);
        rounds_generated += out.at("rounds").size();
    }
    const auto end = std::chrono::steady_clock::now();
    const double seconds = std::chrono::duration<double>(end - start).count();
    return json{
        {"mode", "expected_front_benchmark"},
        {"ants_per_player", ants_per_player},
        {"ant_count", ants_per_player * 2},
        {"steps", steps},
        {"loops", loops},
        {"rounds_generated", rounds_generated},
        {"seconds", seconds},
        {"calls_per_sec", seconds > 0.0 ? static_cast<double>(loops) / seconds : 0.0},
        {"forecast_rounds_per_sec", seconds > 0.0 ? static_cast<double>(rounds_generated) / seconds : 0.0},
    };
}
} // namespace

int main(int argc, char **argv) {
    if (argc >= 2 && std::string(argv[1]) == "--benchmark") {
        int ants_per_player = 16;
        int loops = 20000;
        if (argc >= 3) {
            ants_per_player = std::max(1, std::stoi(argv[2]));
        }
        if (argc >= 4) {
            loops = std::max(1, std::stoi(argv[3]));
        }
        std::cout << run_benchmark(ants_per_player, loops).dump() << '\n';
        return 0;
    }
    if (argc >= 2 && std::string(argv[1]) == "--benchmark-expected-front") {
        int ants_per_player = 16;
        int loops = 2000;
        int steps = 4;
        if (argc >= 3) {
            ants_per_player = std::max(1, std::stoi(argv[2]));
        }
        if (argc >= 4) {
            loops = std::max(1, std::stoi(argv[3]));
        }
        if (argc >= 5) {
            steps = std::max(1, std::stoi(argv[4]));
        }
        std::cout << run_expected_front_benchmark(ants_per_player, loops, steps).dump() << '\n';
        return 0;
    }
    if (argc >= 2 && std::string(argv[1]) == "--expected-front") {
        std::string input((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
        if (input.empty()) {
            std::cerr << "exact_move_kernel --expected-front: empty input\n";
            return 1;
        }
        json payload = json::parse(input);
        std::cout << run_expected_front(payload).dump() << '\n';
        return 0;
    }

    std::string input((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
    if (input.empty()) {
        std::cerr << "exact_move_kernel: empty input\n";
        return 1;
    }
    json payload = json::parse(input);
    std::cout << run_cli_from_payload(payload).dump() << '\n';
    return 0;
}
