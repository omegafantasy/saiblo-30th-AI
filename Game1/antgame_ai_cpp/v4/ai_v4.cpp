#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "../../Ant-Game/game/include/json.hpp"

using json = nlohmann::json;

namespace {
constexpr int kBuildTower = 11;
constexpr int kUpgradeTower = 12;
constexpr int kDowngradeTower = 13;
constexpr int kUseLightningStorm = 21;
constexpr int kUpgradeGenerationSpeed = 31;
constexpr int kUpgradeGeneratedAnt = 32;
constexpr int kPlayerCount = 2;
constexpr int kMapSize = 19;
constexpr int kMapArea = kMapSize * kMapSize;
constexpr int kNoMove = -1;
constexpr int kDefaultBehavior = 0;
constexpr int kConservativeBehavior = 1;
constexpr int kRandomBehavior = 2;
constexpr int kBewitchedBehavior = 3;
constexpr int kControlFreeBehavior = 4;
constexpr int kStatusAlive = 0;
constexpr int kStatusSuccess = 1;
constexpr int kStatusFail = 2;
constexpr int kStatusTooOld = 3;
constexpr int kStatusFrozen = 4;
constexpr int kTowerBasic = 0;
constexpr int kTowerHeavy = 1;
constexpr int kTowerQuick = 2;
constexpr int kTowerMortar = 3;
constexpr int kTowerHeavyPlus = 11;
constexpr int kTowerIce = 12;
constexpr int kTowerCannon = 13;
constexpr int kTowerQuickPlus = 21;
constexpr int kTowerDouble = 22;
constexpr int kTowerSniper = 23;
constexpr int kTowerMortarPlus = 31;
constexpr int kTowerPulse = 32;
constexpr int kTowerMissile = 33;
constexpr int kBaseX[2] = {2, 16};
constexpr int kBaseY[2] = {9, 9};
constexpr int kBaseUpgradeCost[2] = {200, 250};
constexpr int kAntMaxHp[3] = {10, 25, 50};
constexpr int kAntKillReward[3] = {3, 5, 7};
constexpr int kAntGenerationCycle[3] = {4, 2, 1};
constexpr int kRandomDecayTurns = 5;
constexpr int kSpecialDecayTurns = 5;
constexpr int kAgeLimit = 32;
constexpr int kRolloutHorizon = 16;
constexpr int kCriticalAnts = 3;
constexpr int kStrataRepeats = 1;
constexpr int kTopBuildCandidates = 4;
constexpr int kTopUpgradeCandidates = 5;
constexpr int kTopDowngradeCandidates = 2;
constexpr int kMaxEvaluatedCandidates = 14;
constexpr double kCrowdingPenalty = 1.25;
constexpr double kDefaultMoveTemperature = 4.0;
constexpr double kBewitchMoveTemperature = 1.5;
constexpr uint64_t kSeedMul = 0x9E3779B97F4A7C15ULL;

const int kOffset[2][6][2] = {
    {{0, 1}, {-1, 0}, {0, -1}, {1, -1}, {1, 0}, {1, 1}},
    {{-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, 0}, {0, 1}},
};

struct Op {
    int type = -1;
    int arg0 = -1;
    int arg1 = -1;
};

struct TowerInfo {
    int id = -1;
    int player = -1;
    int x = -1;
    int y = -1;
    int type = -1;
    double cooldown = 0.0;
};

struct AntInfo {
    int id = -1;
    int player = -1;
    int x = -1;
    int y = -1;
    int hp = 0;
    int level = 0;
    int age = 0;
    int status = 0;
    int behavior = 0;
    int last_move = kNoMove;
    int behavior_turns = 0;
    int behavior_expiry = 0;
    bool frozen = false;
    int bewitch_target_x = -1;
    int bewitch_target_y = -1;
};

struct BaseInfo {
    int player = -1;
    int x = -1;
    int y = -1;
    int hp = 50;
    int generation_level = 0;
    int ant_level = 0;
};

struct EffectInfo {
    int type = -1;
    int player = -1;
    int x = -1;
    int y = -1;
    int remaining = 0;
};

struct SlotInfo {
    std::string code;
    std::string branch;
    int x = -1;
    int y = -1;
    double priority = 0.0;
    bool build_legal = false;
    int tower_id = -1;
    int tower_type = -1;
};

struct Snapshot {
    int player = 0;
    int round = 0;
    int safe_coin_threshold = 0;
    int nearest_enemy_distance = 32;
    int frontline_distance = 32;
    std::array<int, 2> coins = {50, 50};
    std::array<int, 2> die_count = {0, 0};
    std::array<int, 2> old_count = {0, 0};
    std::array<std::array<int, 5>, 2> weapon_cooldowns{};
    std::vector<BaseInfo> bases;
    std::vector<TowerInfo> towers;
    std::vector<AntInfo> ants;
    std::vector<EffectInfo> effects;
    std::vector<SlotInfo> slots;
    std::array<std::array<std::array<int, kMapSize>, kMapSize>, 2> pheromone{};
};

struct Layout {
    std::array<std::array<bool, kMapSize>, kMapSize> valid{};
    std::array<std::array<int, kMapSize>, kMapSize> owner{};
    std::array<std::array<bool, kMapSize>, kMapSize> path{};
    std::array<std::array<int, 6>, kMapArea> neighbors{};
    std::array<int, kMapArea> neighbor_count{};

    Layout() {
        for (auto &row : owner) {
            row.fill(-1);
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
        const std::array<std::pair<int, int>, 99> invalid_blocks = {{
            {6, 1}, {7, 1}, {9, 1}, {11, 1}, {12, 1}, {4, 2}, {6, 2}, {8, 2}, {9, 2}, {11, 2},
            {13, 2}, {4, 3}, {5, 3}, {13, 3}, {14, 3}, {6, 4}, {8, 4}, {9, 4}, {11, 4}, {3, 5},
            {4, 5}, {7, 5}, {9, 5}, {11, 5}, {14, 5}, {15, 5}, {3, 6}, {5, 6}, {12, 6}, {14, 6},
            {2, 7}, {5, 7}, {6, 7}, {8, 7}, {9, 7}, {10, 7}, {12, 7}, {13, 7}, {16, 7}, {1, 8},
            {2, 8}, {7, 8}, {10, 8}, {15, 8}, {16, 8}, {0, 9}, {4, 9}, {5, 9}, {6, 9}, {9, 9},
            {12, 9}, {13, 9}, {14, 9}, {18, 9}, {1, 10}, {2, 10}, {7, 10}, {10, 10}, {15, 10}, {16, 10},
            {2, 11}, {5, 11}, {6, 11}, {8, 11}, {9, 11}, {10, 11}, {12, 11}, {13, 11}, {16, 11}, {3, 12},
            {5, 12}, {12, 12}, {14, 12}, {3, 13}, {4, 13}, {7, 13}, {9, 13}, {11, 13}, {14, 13}, {15, 13},
            {6, 14}, {8, 14}, {9, 14}, {11, 14}, {4, 15}, {5, 15}, {13, 15}, {14, 15}, {4, 16}, {6, 16},
            {8, 16}, {9, 16}, {11, 16}, {13, 16}, {6, 17}, {7, 17}, {9, 17}, {11, 17}, {12, 17},
        }};
        for (const auto &[x, y] : invalid_blocks) {
            valid[x][y] = false;
        }
        const std::array<std::pair<int, int>, 33> p0_high = {{
            {6, 1}, {7, 1}, {4, 2}, {6, 2}, {8, 2}, {4, 3}, {5, 3}, {6, 4}, {8, 4}, {7, 5}, {5, 6},
            {5, 7}, {6, 7}, {8, 7}, {7, 8}, {4, 9}, {5, 9}, {6, 9}, {7, 10}, {5, 11}, {6, 11}, {8, 11},
            {5, 12}, {7, 13}, {6, 14}, {8, 14}, {4, 15}, {5, 15}, {4, 16}, {6, 16}, {8, 16}, {6, 17}, {7, 17},
        }};
        for (const auto &[x, y] : p0_high) owner[x][y] = 0;
        const std::array<std::pair<int, int>, 33> p1_high = {{
            {11, 1}, {12, 1}, {9, 2}, {11, 2}, {13, 2}, {13, 3}, {14, 3}, {9, 4}, {11, 4}, {11, 5}, {12, 6},
            {10, 7}, {12, 7}, {13, 7}, {10, 8}, {12, 9}, {13, 9}, {14, 9}, {10, 10}, {10, 11}, {12, 11},
            {13, 11}, {12, 12}, {11, 13}, {9, 14}, {11, 14}, {13, 15}, {14, 15}, {9, 16}, {11, 16}, {13, 16},
            {11, 17}, {12, 17},
        }};
        for (const auto &[x, y] : p1_high) owner[x][y] = 1;
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                const bool base_cell = (x == kBaseX[0] && y == kBaseY[0]) || (x == kBaseX[1] && y == kBaseY[1]);
                path[x][y] = valid[x][y] && (owner[x][y] < 0 || base_cell);
                const int idx = x * kMapSize + y;
                int count = 0;
                if (!path[x][y]) {
                    neighbor_count[idx] = 0;
                    continue;
                }
                for (int d = 0; d < 6; ++d) {
                    const int nx = x + kOffset[y % 2][d][0];
                    const int ny = y + kOffset[y % 2][d][1];
                    if (0 <= nx && nx < kMapSize && 0 <= ny && ny < kMapSize && path[nx][ny]) {
                        neighbors[idx][count++] = nx * kMapSize + ny;
                    }
                }
                neighbor_count[idx] = count;
            }
        }
    }
};

const Layout &layout() {
    static const Layout g;
    return g;
}

int hex_distance(int x0, int y0, int x1, int y1) {
    const int dy = std::abs(y0 - y1);
    int dx = 0;
    if (dy % 2 != 0) {
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

bool is_path_cell(int x, int y) {
    return 0 <= x && x < kMapSize && 0 <= y && y < kMapSize && layout().path[x][y];
}

int build_cost(int tower_count) {
    int cost = 15;
    for (int i = 0; i < tower_count; ++i) {
        cost *= 2;
    }
    return cost;
}

int upgrade_cost(int target_type) {
    return target_type < 10 ? 60 : 200;
}

int destroy_income(int tower_count) {
    return static_cast<int>(build_cost(tower_count - 1) * 0.8);
}

int downgrade_income(int tower_type) {
    return static_cast<int>(upgrade_cost(tower_type) * 0.8);
}

int tower_damage(int tower_type) {
    switch (tower_type) {
    case kTowerBasic: return 5;
    case kTowerHeavy: return 20;
    case kTowerQuick: return 6;
    case kTowerMortar: return 16;
    case kTowerHeavyPlus: return 35;
    case kTowerIce: return 15;
    case kTowerCannon: return 10;
    case kTowerQuickPlus: return 8;
    case kTowerDouble: return 7;
    case kTowerSniper: return 15;
    case kTowerMortarPlus: return 35;
    case kTowerPulse: return 12;
    case kTowerMissile: return 45;
    default: return 0;
    }
}

double tower_speed(int tower_type) {
    switch (tower_type) {
    case kTowerBasic: return 2.0;
    case kTowerHeavy: return 2.0;
    case kTowerQuick: return 1.0;
    case kTowerMortar: return 4.0;
    case kTowerHeavyPlus: return 2.0;
    case kTowerIce: return 2.0;
    case kTowerCannon: return 3.0;
    case kTowerQuickPlus: return 0.5;
    case kTowerDouble: return 1.0;
    case kTowerSniper: return 2.0;
    case kTowerMortarPlus: return 4.0;
    case kTowerPulse: return 3.0;
    case kTowerMissile: return 6.0;
    default: return 1.0;
    }
}

int tower_range(int tower_type) {
    switch (tower_type) {
    case kTowerBasic: return 2;
    case kTowerHeavy: return 2;
    case kTowerQuick: return 3;
    case kTowerMortar: return 3;
    case kTowerHeavyPlus: return 3;
    case kTowerIce: return 2;
    case kTowerCannon: return 3;
    case kTowerQuickPlus: return 3;
    case kTowerDouble: return 4;
    case kTowerSniper: return 6;
    case kTowerMortarPlus: return 4;
    case kTowerPulse: return 2;
    case kTowerMissile: return 5;
    default: return 0;
    }
}

bool tower_is_allowed_branch_target(int tower_type) {
    return tower_type == kTowerQuick || tower_type == kTowerMortar || tower_type == kTowerQuickPlus ||
           tower_type == kTowerDouble || tower_type == kTowerMortarPlus || tower_type == kTowerMissile;
}

bool is_alive_status(int status) {
    return status == kStatusAlive || status == kStatusFrozen;
}

void softmax_small(const std::array<double, 6> &scores, int count, double temperature, std::array<double, 6> &out) {
    out.fill(0.0);
    if (count <= 0) {
        return;
    }
    const double scale = std::max(temperature, 1e-6);
    double max_score = scores[0];
    for (int i = 1; i < count; ++i) {
        max_score = std::max(max_score, scores[i]);
    }
    double total = 0.0;
    for (int i = 0; i < count; ++i) {
        out[i] = std::exp((scores[i] - max_score) / scale);
        total += out[i];
    }
    if (total <= 0.0) {
        const double p = 1.0 / static_cast<double>(count);
        for (int i = 0; i < count; ++i) out[i] = p;
        return;
    }
    for (int i = 0; i < count; ++i) out[i] /= total;
}

struct FastRng {
    uint64_t state;

    explicit FastRng(uint64_t seed) : state(seed ? seed : 0x1234ULL) {}

    uint64_t next_u64() {
        uint64_t z = (state += kSeedMul);
        z = (z ^ (z >> 30U)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27U)) * 0x94D049BB133111EBULL;
        return z ^ (z >> 31U);
    }

    double next_double() {
        return static_cast<double>((next_u64() >> 11U)) * (1.0 / 9007199254740992.0);
    }

    int next_int(int bound) {
        if (bound <= 1) return 0;
        return static_cast<int>(next_u64() % static_cast<uint64_t>(bound));
    }
};

struct ThreatInfo {
    int ant_id = -1;
    double score = 0.0;
    int dist_now = 32;
    int min_path_dist = 32;
    double nominal_damage = 0.0;
    double upper_damage = 0.0;
    int top_dir0 = kNoMove;
    int top_dir1 = kNoMove;
    double top_prob0 = 1.0;
    double top_prob1 = 0.0;
};

struct Scenario {
    uint64_t seed = 0;
    std::unordered_map<int, int> first_move_override;
};

struct EvalKey {
    int min_base_hp = -1000;
    int damage_count = 1000000;
    int first_damage_round = -1;
    double tail_base_hp = -1e18;
    double mean_base_hp = -1e18;
    int min_safe_slack = -1000000;
    double mean_safe_slack = -1e18;
    int kill_reward = -1000000;
    int enemy_arrivals = 1000000;
    int action_penalty = -1000000;
    std::string note;
};

bool better_key(const EvalKey &lhs, const EvalKey &rhs) {
    if (lhs.min_base_hp != rhs.min_base_hp) return lhs.min_base_hp > rhs.min_base_hp;
    if (lhs.damage_count != rhs.damage_count) return lhs.damage_count < rhs.damage_count;
    if (lhs.first_damage_round != rhs.first_damage_round) return lhs.first_damage_round > rhs.first_damage_round;
    if (std::abs(lhs.tail_base_hp - rhs.tail_base_hp) > 1e-9) return lhs.tail_base_hp > rhs.tail_base_hp;
    if (std::abs(lhs.mean_base_hp - rhs.mean_base_hp) > 1e-9) return lhs.mean_base_hp > rhs.mean_base_hp;
    if (lhs.min_safe_slack != rhs.min_safe_slack) return lhs.min_safe_slack > rhs.min_safe_slack;
    if (std::abs(lhs.mean_safe_slack - rhs.mean_safe_slack) > 1e-9) return lhs.mean_safe_slack > rhs.mean_safe_slack;
    if (lhs.kill_reward != rhs.kill_reward) return lhs.kill_reward > rhs.kill_reward;
    if (lhs.enemy_arrivals != rhs.enemy_arrivals) return lhs.enemy_arrivals < rhs.enemy_arrivals;
    if (lhs.action_penalty != rhs.action_penalty) return lhs.action_penalty > rhs.action_penalty;
    return false;
}

struct MoveOption {
    int direction = kNoMove;
    int x = -1;
    int y = -1;
    double prob = 0.0;
    double raw = 0.0;
    double score = 0.0;
};

struct MoveSet {
    int count = 0;
    std::array<MoveOption, 6> items{};
};

struct SimState {
    int me = 0;
    int enemy = 1;
    int round = 0;
    int my_base_hp = 50;
    int my_coins = 50;
    int enemy_coins = 50;
    int safe_coin_threshold = 0;
    BaseInfo enemy_base;
    std::vector<TowerInfo> towers;
    std::vector<AntInfo> ants;
    std::vector<EffectInfo> emp_effects;
    std::array<std::array<std::array<int, kMapSize>, kMapSize>, 2> pheromone{};
    std::array<int, kMapArea> occ{};
    std::array<int, kMapArea> adj{};
    int kill_reward_acc = 0;
    int enemy_arrivals = 0;

    void rebuild_occ() {
        occ.fill(0);
        adj.fill(0);
        for (const auto &ant : ants) {
            if (!is_alive_status(ant.status) || ant.hp <= 0) continue;
            occ[ant.x * kMapSize + ant.y] += 1;
        }
        for (int cell = 0; cell < kMapArea; ++cell) {
            if (!layout().path[cell / kMapSize][cell % kMapSize]) continue;
            int sum = 0;
            for (int ni = 0; ni < layout().neighbor_count[cell]; ++ni) {
                sum += occ[layout().neighbors[cell][ni]];
            }
            adj[cell] = sum;
        }
    }

    void update_occ_move(int sx, int sy, int tx, int ty) {
        const int src = sx * kMapSize + sy;
        const int dst = tx * kMapSize + ty;
        if (src == dst) return;
        occ[src] -= 1;
        occ[dst] += 1;
        for (int i = 0; i < layout().neighbor_count[src]; ++i) {
            adj[layout().neighbors[src][i]] -= 1;
        }
        for (int i = 0; i < layout().neighbor_count[dst]; ++i) {
            adj[layout().neighbors[dst][i]] += 1;
        }
    }
};

int ant_max_hp(int level) {
    return kAntMaxHp[std::clamp(level, 0, 2)];
}

int ant_kill_reward(int level) {
    return kAntKillReward[std::clamp(level, 0, 2)];
}

int level_weight_int(int level) {
    static const int weights[3] = {10, 18, 28};
    return weights[std::clamp(level, 0, 2)];
}

MoveSet compute_moves_for_ant(const SimState &state, const AntInfo &ant) {
    MoveSet out;
    const bool allow_backtrack = ant.behavior == kRandomBehavior || ant.behavior == kBewitchedBehavior;
    auto collect = [&](bool allow_reverse) {
        out.count = 0;
        for (int dir = 0; dir < 6; ++dir) {
            const int nx = ant.x + kOffset[ant.y % 2][dir][0];
            const int ny = ant.y + kOffset[ant.y % 2][dir][1];
            if (!allow_reverse && ant.last_move >= 0 && ant.last_move == ((dir + 3) % 6)) {
                continue;
            }
            if (!is_path_cell(nx, ny)) {
                continue;
            }
            out.items[out.count++] = {dir, nx, ny, 0.0, 0.0, 0.0};
        }
    };
    collect(allow_backtrack);
    if (out.count == 0 && !allow_backtrack) collect(true);
    if (out.count == 0) return out;
    if (ant.behavior == kRandomBehavior) {
        const double p = 1.0 / static_cast<double>(out.count);
        for (int i = 0; i < out.count; ++i) out.items[i].prob = p;
        return out;
    }
    const int target_x = (ant.behavior == kBewitchedBehavior && ant.bewitch_target_x >= 0) ? ant.bewitch_target_x : kBaseX[1 - ant.player];
    const int target_y = (ant.behavior == kBewitchedBehavior && ant.bewitch_target_y >= 0) ? ant.bewitch_target_y : kBaseY[1 - ant.player];
    const int current_distance = hex_distance(ant.x, ant.y, target_x, target_y);
    std::array<double, 6> scores{};
    for (int i = 0; i < out.count; ++i) {
        const auto &m = out.items[i];
        const int idx = m.x * kMapSize + m.y;
        const double same = static_cast<double>(std::max(0, state.occ[idx]));
        const double adj = static_cast<double>(std::max(0, state.adj[idx] - (hex_distance(ant.x, ant.y, m.x, m.y) == 1 ? 1 : 0)));
        const double crowd = same + 0.35 * adj;
        if (ant.behavior == kBewitchedBehavior && ant.bewitch_target_x >= 0 && ant.bewitch_target_y >= 0) {
            const int next_distance = hex_distance(m.x, m.y, target_x, target_y);
            out.items[i].raw = static_cast<double>(current_distance - next_distance) * 4.0;
        } else {
            const int next_distance = hex_distance(m.x, m.y, target_x, target_y);
            double weight = 1.0;
            if (next_distance < current_distance) weight = 1.25;
            else if (next_distance > current_distance) weight = 0.75;
            out.items[i].raw = static_cast<double>(state.pheromone[ant.player][m.x][m.y]) * weight;
        }
        out.items[i].score = out.items[i].raw - kCrowdingPenalty * crowd;
        scores[i] = out.items[i].score;
    }
    if (ant.behavior == kConservativeBehavior || ant.behavior == kControlFreeBehavior) {
        int best = 0;
        for (int i = 1; i < out.count; ++i) {
            if (out.items[i].raw > out.items[best].raw ||
                (std::abs(out.items[i].raw - out.items[best].raw) <= 1e-9 && out.items[i].direction < out.items[best].direction)) {
                best = i;
            }
        }
        out.items[best].prob = 1.0;
        return out;
    }
    std::array<double, 6> probs{};
    const double temp = (ant.behavior == kBewitchedBehavior && ant.bewitch_target_x >= 0) ? kBewitchMoveTemperature : kDefaultMoveTemperature;
    softmax_small(scores, out.count, temp, probs);
    for (int i = 0; i < out.count; ++i) out.items[i].prob = probs[i];
    return out;
}

int sample_direction_from_moves(const MoveSet &moves, FastRng &rng) {
    if (moves.count <= 0) return kNoMove;
    double r = rng.next_double();
    double acc = 0.0;
    for (int i = 0; i < moves.count; ++i) {
        acc += moves.items[i].prob;
        if (r <= acc + 1e-12) return moves.items[i].direction;
    }
    return moves.items[moves.count - 1].direction;
}

int choose_override_or_sample(const MoveSet &moves, const std::optional<int> &forced_dir, FastRng &rng) {
    if (forced_dir.has_value()) {
        for (int i = 0; i < moves.count; ++i) {
            if (moves.items[i].direction == *forced_dir) {
                return *forced_dir;
            }
        }
    }
    return sample_direction_from_moves(moves, rng);
}

void decay_behavior(AntInfo &ant) {
    ant.behavior_turns += 1;
    if (ant.behavior == kRandomBehavior && ant.behavior_turns >= kRandomDecayTurns) {
        ant.behavior = kDefaultBehavior;
        ant.behavior_turns = 0;
        ant.behavior_expiry = 0;
        ant.bewitch_target_x = -1;
        ant.bewitch_target_y = -1;
        return;
    }
    if (ant.behavior == kBewitchedBehavior && ant.bewitch_target_x == ant.x && ant.bewitch_target_y == ant.y) {
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

bool tower_emp_shielded(const SimState &state, const TowerInfo &tower) {
    for (const auto &effect : state.emp_effects) {
        if (effect.player == tower.player) continue;
        if (effect.remaining <= 0) continue;
        if (hex_distance(effect.x, effect.y, tower.x, tower.y) <= 3) return true;
    }
    return false;
}

void tick_tower(TowerInfo &tower) {
    if (tower.cooldown > 0.0) {
        tower.cooldown -= 1.0;
    }
}

bool tower_ready(const TowerInfo &tower) {
    if (tower_speed(tower.type) < 1.0) return true;
    return tower.cooldown <= 0.0;
}

void tower_reset(TowerInfo &tower) {
    const double speed = tower_speed(tower.type);
    if (speed < 1.0) {
        tower.cooldown = 0.0;
    } else {
        tower.cooldown = std::round(speed);
    }
}

std::vector<int> find_tower_targets(const SimState &state, const TowerInfo &tower) {
    std::vector<int> candidates;
    for (int i = 0; i < static_cast<int>(state.ants.size()); ++i) {
        const auto &ant = state.ants[i];
        if (!is_alive_status(ant.status) || ant.hp <= 0) continue;
        if (ant.player == tower.player) continue;
        if (hex_distance(ant.x, ant.y, tower.x, tower.y) <= tower_range(tower.type)) {
            candidates.push_back(i);
        }
    }
    std::sort(candidates.begin(), candidates.end(), [&](int lhs, int rhs) {
        const auto &a = state.ants[lhs];
        const auto &b = state.ants[rhs];
        const int da = hex_distance(a.x, a.y, tower.x, tower.y);
        const int db = hex_distance(b.x, b.y, tower.x, tower.y);
        if (da != db) return da < db;
        return a.id < b.id;
    });
    if (tower.type == kTowerDouble && static_cast<int>(candidates.size()) > 2) {
        candidates.resize(2);
    } else if (static_cast<int>(candidates.size()) > 1) {
        candidates.resize(1);
    }
    return candidates;
}

void damage_ant(AntInfo &ant, int amount) {
    ant.hp -= amount;
    if (ant.hp <= 0) ant.status = kStatusFail;
}

void apply_tower_attack(SimState &state, TowerInfo &tower) {
    if (tower_emp_shielded(state, tower)) return;
    tick_tower(tower);
    if (!tower_ready(tower)) return;
    const int repetitions = tower_speed(tower.type) < 1.0 ? std::max(1, static_cast<int>(std::round(1.0 / tower_speed(tower.type)))) : 1;
    bool attacked = false;
    for (int rep = 0; rep < repetitions; ++rep) {
        const auto targets = find_tower_targets(state, tower);
        if (targets.empty()) break;
        for (int target_index : targets) {
            const auto center = state.ants[target_index];
            for (auto &ant : state.ants) {
                if (!is_alive_status(ant.status) || ant.hp <= 0 || ant.player == tower.player) continue;
                int radius = 0;
                if (tower.type == kTowerMortar || tower.type == kTowerMortarPlus) radius = 1;
                else if (tower.type == kTowerMissile) radius = 2;
                else if (tower.type == kTowerPulse) radius = tower_range(tower.type);
                if (tower.type == kTowerMortar || tower.type == kTowerMortarPlus || tower.type == kTowerMissile) {
                    if (hex_distance(ant.x, ant.y, center.x, center.y) <= radius) {
                        damage_ant(ant, tower_damage(tower.type));
                    }
                } else if (tower.type == kTowerPulse) {
                    if (hex_distance(ant.x, ant.y, tower.x, tower.y) <= radius) {
                        damage_ant(ant, tower_damage(tower.type));
                    }
                } else if (ant.id == center.id) {
                    damage_ant(ant, tower_damage(tower.type));
                }
            }
            attacked = true;
        }
    }
    if (attacked) tower_reset(tower);
}

void resolve_lifecycle(SimState &state) {
    std::vector<AntInfo> next;
    next.reserve(state.ants.size());
    for (auto &ant : state.ants) {
        if (ant.hp <= 0) ant.status = kStatusFail;
        if (ant.x == kBaseX[state.me] && ant.y == kBaseY[state.me]) {
            ant.status = kStatusSuccess;
        } else if (ant.age > kAgeLimit) {
            ant.status = kStatusTooOld;
        }
        if (ant.status == kStatusSuccess) {
            state.my_base_hp -= 1;
            state.enemy_coins += 5;
            state.enemy_arrivals += 1;
        } else if (ant.status == kStatusFail) {
            const int reward = ant_kill_reward(ant.level);
            state.my_coins += reward;
            state.kill_reward_acc += reward;
        } else if (ant.status == kStatusTooOld) {
            // drop
        } else {
            next.push_back(ant);
        }
    }
    state.ants.swap(next);
}

int draw_spawn_behavior(FastRng &rng) {
    const double r = rng.next_double();
    if (r <= 0.4) return kDefaultBehavior;
    if (r <= 0.7) return kConservativeBehavior;
    if (r <= 0.95) return kRandomBehavior;
    return kControlFreeBehavior;
}

void maybe_spawn_enemy_ant(SimState &state, FastRng &rng) {
    const int cycle = kAntGenerationCycle[std::clamp(state.enemy_base.generation_level, 0, 2)];
    if (cycle <= 0 || state.round % cycle != 0) return;
    AntInfo ant;
    ant.id = 1000000 + state.round * 64 + static_cast<int>(state.ants.size());
    ant.player = state.enemy;
    ant.x = state.enemy_base.x;
    ant.y = state.enemy_base.y;
    ant.level = std::clamp(state.enemy_base.ant_level, 0, 2);
    ant.hp = ant_max_hp(ant.level);
    ant.status = kStatusAlive;
    ant.behavior = draw_spawn_behavior(rng);
    ant.behavior_turns = 0;
    ant.behavior_expiry = (ant.behavior == kConservativeBehavior || ant.behavior == kControlFreeBehavior || ant.behavior == kBewitchedBehavior) ? kSpecialDecayTurns : 0;
    state.ants.push_back(ant);
}

void age_and_decay(SimState &state) {
    for (auto &ant : state.ants) {
        ant.age += 1;
        if (ant.frozen) {
            ant.frozen = false;
        }
        decay_behavior(ant);
    }
    for (auto &effect : state.emp_effects) {
        if (effect.remaining > 0) effect.remaining -= 1;
    }
}

struct CandidateEstimate {
    std::vector<Op> ops;
    double priority = 0.0;
};

struct CandidateAction {
    std::vector<Op> ops;
    EvalKey key;
};

class V4AI {
  public:
    std::vector<Op> decide(const Snapshot &snapshot) {
        const bool severe = severe_threat(snapshot);
        if (auto storm = maybe_emergency_storm(snapshot, severe)) {
            return {*storm};
        }

        std::vector<CandidateEstimate> estimates;
        estimates.push_back({{}, 1e9});
        append_build_candidates(snapshot, estimates);
        append_upgrade_candidates(snapshot, estimates);
        append_downgrade_candidates(snapshot, estimates);
        append_combo_candidates(snapshot, estimates);
        append_base_upgrade_candidates(snapshot, estimates);
        std::stable_sort(estimates.begin(), estimates.end(), [](const CandidateEstimate &lhs, const CandidateEstimate &rhs) {
            return lhs.priority > rhs.priority;
        });
        if (static_cast<int>(estimates.size()) > kMaxEvaluatedCandidates) {
            estimates.resize(kMaxEvaluatedCandidates);
        }

        std::vector<CandidateAction> actions;
        actions.reserve(estimates.size());
        for (const auto &cand : estimates) {
            if (!ops_legal_and_affordable(snapshot, cand.ops)) continue;
            actions.push_back({cand.ops, evaluate_candidate(snapshot, cand.ops)});
        }
        CandidateAction best{{}, EvalKey{}};
        bool has_best = false;
        for (const auto &cand : actions) {
            if (!has_best || better_key(cand.key, best.key)) {
                best = cand;
                has_best = true;
            }
        }
        return best.ops;
    }

    json sample_first_moves(const Snapshot &snapshot, const std::vector<int> &query_ids, int loops) {
        SimState base = build_sim_state(snapshot);
        base.rebuild_occ();
        json out = json::object();
        for (int ant_id : query_ids) {
            std::array<int, 6> counts{};
            int total = 0;
            for (int loop = 0; loop < loops; ++loop) {
                FastRng rng(static_cast<uint64_t>(snapshot.round + 1) * 1315423911ULL + static_cast<uint64_t>(ant_id * 17 + loop));
                SimState sim = base;
                sim.rebuild_occ();
                for (auto &ant : sim.ants) {
                    if (ant.id != ant_id) continue;
                    const MoveSet moves = compute_moves_for_ant(sim, ant);
                    const int dir = sample_direction_from_moves(moves, rng);
                    if (0 <= dir && dir < 6) {
                        counts[dir] += 1;
                        total += 1;
                    }
                    break;
                }
            }
            json row = json::object();
            for (int dir = 0; dir < 6; ++dir) {
                row[std::to_string(dir)] = total > 0 ? static_cast<double>(counts[dir]) / static_cast<double>(total) : 0.0;
            }
            out[std::to_string(ant_id)] = row;
        }
        return out;
    }

  private:
    static bool emp_shielded_snapshot(const Snapshot &snapshot, int player, int x, int y) {
        for (const auto &effect : snapshot.effects) {
            if (effect.type != 2 || effect.player == player || effect.remaining <= 0) continue;
            if (hex_distance(effect.x, effect.y, x, y) <= 3) return true;
        }
        return false;
    }

    static const TowerInfo *find_tower_const(const Snapshot &snapshot, int tower_id) {
        for (const auto &tower : snapshot.towers) {
            if (tower.id == tower_id) return &tower;
        }
        return nullptr;
    }

    static bool ops_legal_and_affordable(const Snapshot &snapshot, const std::vector<Op> &ops) {
        const int me = snapshot.player;
        int coins = snapshot.coins[me];
        int tower_count = own_tower_count(snapshot);
        std::set<int> touched_towers;
        bool touched_base = false;
        for (const auto &op : ops) {
            if (op.type == kBuildTower) {
                bool ok = false;
                for (const auto &slot : snapshot.slots) {
                    if (slot.x == op.arg0 && slot.y == op.arg1 && slot.build_legal) {
                        ok = true;
                        break;
                    }
                }
                if (!ok) return false;
                const int cost = build_cost(tower_count);
                if (coins < cost) return false;
                coins -= cost;
                tower_count += 1;
                continue;
            }
            if (op.type == kUpgradeTower) {
                if (touched_towers.count(op.arg0) > 0) return false;
                const TowerInfo *tower = find_tower_const(snapshot, op.arg0);
                if (tower == nullptr || tower->player != me) return false;
                if (emp_shielded_snapshot(snapshot, me, tower->x, tower->y)) return false;
                bool valid_target = false;
                for (const auto &slot : snapshot.slots) {
                    if (slot.tower_id != op.arg0) continue;
                    const auto ups = allowed_upgrades_for_slot(slot);
                    valid_target = std::find(ups.begin(), ups.end(), op.arg1) != ups.end();
                    break;
                }
                if (!valid_target) return false;
                const int cost = upgrade_cost(op.arg1);
                if (coins < cost) return false;
                coins -= cost;
                touched_towers.insert(op.arg0);
                continue;
            }
            if (op.type == kDowngradeTower) {
                if (touched_towers.count(op.arg0) > 0) return false;
                const TowerInfo *tower = find_tower_const(snapshot, op.arg0);
                if (tower == nullptr || tower->player != me) return false;
                if (emp_shielded_snapshot(snapshot, me, tower->x, tower->y)) return false;
                coins += (tower->type == kTowerBasic) ? destroy_income(tower_count) : downgrade_income(tower->type);
                if (tower->type == kTowerBasic) tower_count -= 1;
                touched_towers.insert(op.arg0);
                continue;
            }
            if (op.type == kUpgradeGeneratedAnt) {
                if (touched_base || snapshot.bases[me].ant_level >= 2) return false;
                const int cost = kBaseUpgradeCost[snapshot.bases[me].ant_level];
                if (coins < cost) return false;
                coins -= cost;
                touched_base = true;
                continue;
            }
            if (op.type == kUpgradeGenerationSpeed) {
                if (touched_base || snapshot.bases[me].generation_level >= 2) return false;
                const int cost = kBaseUpgradeCost[snapshot.bases[me].generation_level];
                if (coins < cost) return false;
                coins -= cost;
                touched_base = true;
                continue;
            }
            if (op.type == kUseLightningStorm) {
                if (snapshot.weapon_cooldowns[me][1] > 0 || coins < 150) return false;
                coins -= 150;
                continue;
            }
            return false;
        }
        return true;
    }

    static bool severe_threat(const Snapshot &snapshot) {
        return snapshot.nearest_enemy_distance <= 3 || enemy_pressure(snapshot) >= 36.0;
    }

    static double enemy_pressure(const Snapshot &snapshot) {
        const int me = snapshot.player;
        double total = 0.0;
        for (const auto &ant : snapshot.ants) {
            if (ant.player == me || !is_alive_status(ant.status) || ant.hp <= 0) continue;
            const int dist = hex_distance(ant.x, ant.y, snapshot.bases[me].x, snapshot.bases[me].y);
            total += static_cast<double>(level_weight_int(ant.level)) * std::max(0, 11 - dist) * 0.1;
        }
        return total;
    }

    static std::optional<Op> maybe_emergency_storm(const Snapshot &snapshot, bool severe) {
        if (!severe) return std::nullopt;
        const int me = snapshot.player;
        if (snapshot.weapon_cooldowns[me][1] > 0) return std::nullopt;
        if (snapshot.coins[me] < 150) return std::nullopt;
        double best_score = -1.0;
        int best_x = -1;
        int best_y = -1;
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                if (!layout().valid[x][y]) continue;
                double score = 0.0;
                for (const auto &ant : snapshot.ants) {
                    if (ant.player == me || !is_alive_status(ant.status) || ant.hp <= 0) continue;
                    const int d = hex_distance(x, y, ant.x, ant.y);
                    if (d <= 3) {
                        score += 40.0 + level_weight_int(ant.level) + std::max(0, 9 - hex_distance(ant.x, ant.y, snapshot.bases[me].x, snapshot.bases[me].y)) * 6.0;
                    }
                }
                if (score > best_score) {
                    best_score = score;
                    best_x = x;
                    best_y = y;
                }
            }
        }
        if (best_score >= 120.0 && best_x >= 0) {
            return Op{kUseLightningStorm, best_x, best_y};
        }
        return std::nullopt;
    }

    static int own_tower_count(const Snapshot &snapshot) {
        int count = 0;
        for (const auto &tower : snapshot.towers) if (tower.player == snapshot.player) ++count;
        return count;
    }

    static int find_slot_index(const Snapshot &snapshot, int x, int y) {
        for (int i = 0; i < static_cast<int>(snapshot.slots.size()); ++i) {
            if (snapshot.slots[i].x == x && snapshot.slots[i].y == y) return i;
        }
        return -1;
    }

    static std::vector<int> allowed_upgrades_for_slot(const SlotInfo &slot) {
        std::vector<int> out;
        if (slot.tower_type == kTowerBasic) {
            if (slot.branch == "mortar") out.push_back(kTowerMortar);
            else out.push_back(kTowerQuick);
            return out;
        }
        if (slot.tower_type == kTowerQuick) {
            out.push_back(kTowerDouble);
            out.push_back(kTowerQuickPlus);
            return out;
        }
        if (slot.tower_type == kTowerMortar) {
            out.push_back(kTowerMortarPlus);
            out.push_back(kTowerMissile);
            return out;
        }
        return out;
    }

    static double slot_risk_bonus(const Snapshot &snapshot, int x, int y) {
        const int me = snapshot.player;
        double bonus = 0.0;
        for (const auto &ant : snapshot.ants) {
            if (ant.player == me || !is_alive_status(ant.status) || ant.hp <= 0) continue;
            const int base_dist = hex_distance(ant.x, ant.y, snapshot.bases[me].x, snapshot.bases[me].y);
            const int slot_dist = hex_distance(ant.x, ant.y, x, y);
            bonus += std::max(0, 10 - base_dist) * std::max(0, 5 - slot_dist) * (1.0 + 0.2 * ant.level);
        }
        return bonus;
    }

    static double tower_value_for_sale(const Snapshot &snapshot, const SlotInfo &slot) {
        const int me = snapshot.player;
        if (slot.tower_id < 0) return -1e18;
        double value = slot.priority * 3.0;
        if (tower_is_allowed_branch_target(slot.tower_type)) value += 25.0;
        if (slot.tower_type == kTowerBasic) value -= 12.0;
        value -= slot_risk_bonus(snapshot, slot.x, slot.y);
        for (const auto &ant : snapshot.ants) {
            if (ant.player == me || !is_alive_status(ant.status) || ant.hp <= 0) continue;
            const int d = hex_distance(ant.x, ant.y, slot.x, slot.y);
            if (d <= tower_range(slot.tower_type < 0 ? kTowerBasic : slot.tower_type)) {
                value += 4.0 + ant.level;
            }
        }
        return value;
    }

    static bool emergency_sell_allowed(const Snapshot &snapshot) {
        const int me = snapshot.player;
        if (snapshot.coins[me] < snapshot.safe_coin_threshold) return true;
        if (snapshot.nearest_enemy_distance <= 4) return true;
        if (snapshot.frontline_distance <= 4) return true;
        for (const auto &ant : snapshot.ants) {
            if (ant.player == me || !is_alive_status(ant.status) || ant.hp <= 0) continue;
            const int base_dist = hex_distance(ant.x, ant.y, snapshot.bases[me].x, snapshot.bases[me].y);
            if (base_dist <= 4) return true;
            if (ant.level >= 1 && base_dist <= 6) return true;
        }
        return false;
    }

    static void append_build_candidates(const Snapshot &snapshot, std::vector<CandidateEstimate> &out) {
        std::vector<std::pair<double, Op>> ranked;
        ranked.reserve(snapshot.slots.size());
        for (const auto &slot : snapshot.slots) {
            if (!slot.build_legal) continue;
            const double score = slot.priority * 5.0 + slot_risk_bonus(snapshot, slot.x, slot.y);
            ranked.push_back({score, Op{kBuildTower, slot.x, slot.y}});
        }
        std::sort(ranked.begin(), ranked.end(), [](const auto &lhs, const auto &rhs) { return lhs.first > rhs.first; });
        const int keep = std::min<int>(kTopBuildCandidates, static_cast<int>(ranked.size()));
        for (int i = 0; i < keep; ++i) out.push_back({{ranked[i].second}, ranked[i].first});
    }

    static void append_upgrade_candidates(const Snapshot &snapshot, std::vector<CandidateEstimate> &out) {
        std::vector<std::pair<double, Op>> ranked;
        for (const auto &slot : snapshot.slots) {
            if (slot.tower_id < 0) continue;
            for (int target : allowed_upgrades_for_slot(slot)) {
                const double score = slot.priority * 4.0 + slot_risk_bonus(snapshot, slot.x, slot.y) + tower_damage(target) * 0.8 + tower_range(target) * 2.0;
                ranked.push_back({score, Op{kUpgradeTower, slot.tower_id, target}});
            }
        }
        std::sort(ranked.begin(), ranked.end(), [](const auto &lhs, const auto &rhs) { return lhs.first > rhs.first; });
        const int keep = std::min<int>(kTopUpgradeCandidates, static_cast<int>(ranked.size()));
        for (int i = 0; i < keep; ++i) out.push_back({{ranked[i].second}, ranked[i].first});
    }

    static void append_downgrade_candidates(const Snapshot &snapshot, std::vector<CandidateEstimate> &out) {
        if (!emergency_sell_allowed(snapshot)) return;
        std::vector<std::pair<double, Op>> ranked;
        for (const auto &slot : snapshot.slots) {
            if (slot.tower_id < 0) continue;
            const double sale_value = tower_value_for_sale(snapshot, slot);
            ranked.push_back({sale_value, Op{kDowngradeTower, slot.tower_id, -1}});
        }
        std::sort(ranked.begin(), ranked.end(), [](const auto &lhs, const auto &rhs) { return lhs.first < rhs.first; });
        const int keep = std::min<int>(1, static_cast<int>(ranked.size()));
        for (int i = 0; i < keep; ++i) {
            if (ranked[i].first < 6.0) out.push_back({{ranked[i].second}, -ranked[i].first});
        }
    }

    static void append_combo_candidates(const Snapshot &snapshot, std::vector<CandidateEstimate> &out) {
        const int me = snapshot.player;
        if (!emergency_sell_allowed(snapshot) && snapshot.coins[me] >= snapshot.safe_coin_threshold + 40) {
            return;
        }
        std::vector<Op> top_builds;
        std::vector<Op> top_upgrades;
        std::vector<Op> top_downs;
        for (const auto &slot : snapshot.slots) {
            if (slot.build_legal && static_cast<int>(top_builds.size()) < 2) top_builds.push_back(Op{kBuildTower, slot.x, slot.y});
            if (slot.tower_id >= 0 && static_cast<int>(top_downs.size()) < 1) {
                const double sale_value = tower_value_for_sale(snapshot, slot);
                if (sale_value < 2.0) top_downs.push_back(Op{kDowngradeTower, slot.tower_id, -1});
            }
            if (slot.tower_id >= 0 && static_cast<int>(top_upgrades.size()) < 2) {
                const auto ups = allowed_upgrades_for_slot(slot);
                if (!ups.empty()) top_upgrades.push_back(Op{kUpgradeTower, slot.tower_id, ups.front()});
            }
        }
        for (const auto &down : top_downs) {
            for (const auto &build : top_builds) {
                out.push_back({{down, build}, 1.0});
            }
            for (const auto &up : top_upgrades) {
                if (up.arg0 == down.arg0) continue;
                out.push_back({{down, up}, 1.0});
            }
        }
    }

    static void append_base_upgrade_candidates(const Snapshot &snapshot, std::vector<CandidateEstimate> &out) {
        const int me = snapshot.player;
        const int coin = snapshot.coins[me];
        const int reserve = snapshot.safe_coin_threshold;
        const bool stable_front = snapshot.nearest_enemy_distance >= 7 && snapshot.frontline_distance >= 7;
        if (stable_front && snapshot.bases[me].ant_level < 2 && coin - kBaseUpgradeCost[snapshot.bases[me].ant_level] >= reserve + 120) {
            out.push_back({{Op{kUpgradeGeneratedAnt, -1, -1}}, 0.5});
        }
        if (stable_front && snapshot.bases[me].ant_level >= 1 && snapshot.bases[me].generation_level < 2 &&
            coin - kBaseUpgradeCost[snapshot.bases[me].generation_level] >= reserve + 220 && snapshot.nearest_enemy_distance >= 9) {
            out.push_back({{Op{kUpgradeGenerationSpeed, -1, -1}}, 0.3});
        }
    }

    static std::optional<TowerInfo *> find_tower(std::vector<TowerInfo> &towers, int tower_id) {
        for (auto &tower : towers) if (tower.id == tower_id) return &tower;
        return std::nullopt;
    }

    static void apply_ops_abstract(Snapshot &snapshot, const std::vector<Op> &ops) {
        const int me = snapshot.player;
        int tower_count = own_tower_count(snapshot);
        for (const auto &op : ops) {
            if (op.type == kBuildTower) {
                const int cost = build_cost(tower_count);
                snapshot.coins[me] -= cost;
                TowerInfo tower;
                tower.id = 100000 + tower_count;
                tower.player = me;
                tower.x = op.arg0;
                tower.y = op.arg1;
                tower.type = kTowerBasic;
                tower.cooldown = std::round(tower_speed(kTowerBasic));
                snapshot.towers.push_back(tower);
                const int slot_index = find_slot_index(snapshot, op.arg0, op.arg1);
                if (slot_index >= 0) {
                    snapshot.slots[slot_index].tower_id = tower.id;
                    snapshot.slots[slot_index].tower_type = tower.type;
                    snapshot.slots[slot_index].build_legal = false;
                }
                tower_count += 1;
            } else if (op.type == kUpgradeTower) {
                snapshot.coins[me] -= upgrade_cost(op.arg1);
                auto tower_ptr = find_tower(snapshot.towers, op.arg0);
                if (!tower_ptr.has_value()) continue;
                tower_ptr.value()->type = op.arg1;
                tower_ptr.value()->cooldown = std::round(tower_speed(op.arg1));
                for (auto &slot : snapshot.slots) {
                    if (slot.tower_id == op.arg0) {
                        slot.tower_type = op.arg1;
                    }
                }
            } else if (op.type == kDowngradeTower) {
                auto tower_ptr = find_tower(snapshot.towers, op.arg0);
                if (!tower_ptr.has_value()) continue;
                TowerInfo &tower = *tower_ptr.value();
                if (tower.type == kTowerBasic) {
                    snapshot.coins[me] += destroy_income(tower_count);
                    tower_count -= 1;
                    snapshot.towers.erase(std::remove_if(snapshot.towers.begin(), snapshot.towers.end(), [&](const TowerInfo &item) {
                        return item.id == op.arg0;
                    }), snapshot.towers.end());
                    for (auto &slot : snapshot.slots) {
                        if (slot.tower_id == op.arg0) {
                            slot.tower_id = -1;
                            slot.tower_type = -1;
                            slot.build_legal = true;
                        }
                    }
                } else {
                    snapshot.coins[me] += downgrade_income(tower.type);
                    tower.type = tower.type / 10;
                    tower.cooldown = std::round(tower_speed(tower.type));
                    for (auto &slot : snapshot.slots) {
                        if (slot.tower_id == op.arg0) slot.tower_type = tower.type;
                    }
                }
            } else if (op.type == kUpgradeGeneratedAnt) {
                snapshot.coins[me] -= kBaseUpgradeCost[snapshot.bases[me].ant_level];
                snapshot.bases[me].ant_level += 1;
            } else if (op.type == kUpgradeGenerationSpeed) {
                snapshot.coins[me] -= kBaseUpgradeCost[snapshot.bases[me].generation_level];
                snapshot.bases[me].generation_level += 1;
            }
        }
    }

    static SimState build_sim_state(const Snapshot &snapshot) {
        SimState sim;
        sim.me = snapshot.player;
        sim.enemy = 1 - snapshot.player;
        sim.round = snapshot.round;
        sim.my_base_hp = snapshot.bases[sim.me].hp;
        sim.my_coins = snapshot.coins[sim.me];
        sim.enemy_coins = snapshot.coins[sim.enemy];
        sim.safe_coin_threshold = snapshot.safe_coin_threshold;
        sim.enemy_base = snapshot.bases[sim.enemy];
        sim.pheromone = snapshot.pheromone;
        for (const auto &tower : snapshot.towers) {
            if (tower.player == sim.me) sim.towers.push_back(tower);
        }
        for (const auto &ant : snapshot.ants) {
            if (ant.player == sim.enemy && is_alive_status(ant.status) && ant.hp > 0) {
                sim.ants.push_back(ant);
            }
        }
        for (const auto &effect : snapshot.effects) {
            if (effect.type == 2) sim.emp_effects.push_back(effect);
        }
        sim.rebuild_occ();
        return sim;
    }

    static ThreatInfo compute_single_threat(const Snapshot &snapshot, const AntInfo &ant) {
        ThreatInfo info;
        info.ant_id = ant.id;
        const int me = snapshot.player;
        info.dist_now = hex_distance(ant.x, ant.y, snapshot.bases[me].x, snapshot.bases[me].y);
        AntInfo probe = ant;
        probe.last_move = ant.last_move;
        SimState sim = build_sim_state(snapshot);
        sim.ants.clear();
        sim.ants.push_back(probe);
        sim.rebuild_occ();
        const int horizon = 10;
        int cx = probe.x;
        int cy = probe.y;
        double nominal = 0.0;
        double upper = 0.0;
        int min_dist = info.dist_now;
        for (int step = 0; step < horizon; ++step) {
            const MoveSet moves = compute_moves_for_ant(sim, sim.ants[0]);
            if (moves.count <= 0) break;
            int best = 0;
            for (int i = 1; i < moves.count; ++i) {
                if (moves.items[i].prob > moves.items[best].prob) best = i;
            }
            cx = moves.items[best].x;
            cy = moves.items[best].y;
            sim.update_occ_move(sim.ants[0].x, sim.ants[0].y, cx, cy);
            sim.ants[0].x = cx;
            sim.ants[0].y = cy;
            sim.ants[0].last_move = moves.items[best].direction;
            min_dist = std::min(min_dist, hex_distance(cx, cy, snapshot.bases[me].x, snapshot.bases[me].y));
            for (const auto &tower : snapshot.towers) {
                if (tower.player != me) continue;
                if (hex_distance(tower.x, tower.y, cx, cy) <= tower_range(tower.type)) {
                    upper += tower_damage(tower.type);
                    nominal += tower_damage(tower.type) / std::max(0.5, tower_speed(tower.type));
                }
            }
        }
        info.min_path_dist = min_dist;
        info.nominal_damage = nominal;
        info.upper_damage = upper;
        const double remain_nom = std::max(0.0, static_cast<double>(ant.hp) - nominal);
        const double remain_up = std::max(0.0, static_cast<double>(ant.hp) - upper);
        info.score = std::max(0, 12 - info.dist_now) * 15.0 + std::max(0, 10 - min_dist) * 12.0 + remain_nom * 1.2 + remain_up * 2.0 + ant.level * 9.0;
        SimState current = build_sim_state(snapshot);
        current.ants.clear();
        current.ants.push_back(ant);
        current.rebuild_occ();
        const MoveSet first = compute_moves_for_ant(current, current.ants[0]);
        int first_best = -1;
        int second_best = -1;
        for (int i = 0; i < first.count; ++i) {
            if (first_best < 0 || first.items[i].prob > first.items[first_best].prob) {
                second_best = first_best;
                first_best = i;
            } else if (second_best < 0 || first.items[i].prob > first.items[second_best].prob) {
                second_best = i;
            }
        }
        if (first_best >= 0) {
            info.top_dir0 = first.items[first_best].direction;
            info.top_prob0 = first.items[first_best].prob;
        }
        if (second_best >= 0) {
            info.top_dir1 = first.items[second_best].direction;
            info.top_prob1 = first.items[second_best].prob;
        } else {
            info.top_dir1 = info.top_dir0;
            info.top_prob1 = info.top_prob0;
        }
        return info;
    }

    static std::vector<ThreatInfo> compute_threats(const Snapshot &snapshot) {
        std::vector<ThreatInfo> out;
        for (const auto &ant : snapshot.ants) {
            if (ant.player == snapshot.player || !is_alive_status(ant.status) || ant.hp <= 0) continue;
            out.push_back(compute_single_threat(snapshot, ant));
        }
        std::sort(out.begin(), out.end(), [](const ThreatInfo &lhs, const ThreatInfo &rhs) {
            if (std::abs(lhs.score - rhs.score) > 1e-9) return lhs.score > rhs.score;
            return lhs.ant_id < rhs.ant_id;
        });
        if (static_cast<int>(out.size()) > kCriticalAnts) out.resize(kCriticalAnts);
        return out;
    }

    static std::vector<Scenario> build_scenarios(const Snapshot &snapshot, const std::vector<ThreatInfo> &threats) {
        const int strata = 1 << std::min<int>(kCriticalAnts, static_cast<int>(threats.size()));
        const int repeats = kStrataRepeats;
        std::vector<Scenario> out;
        out.reserve(strata * repeats);
        for (int s = 0; s < strata; ++s) {
            for (int rep = 0; rep < repeats; ++rep) {
                Scenario sc;
                sc.seed = static_cast<uint64_t>(snapshot.round + 1) * 1000003ULL + static_cast<uint64_t>(s * 97 + rep * 131);
                for (int i = 0; i < static_cast<int>(threats.size()); ++i) {
                    const auto &th = threats[i];
                    const bool choose_alt = ((s >> i) & 1) != 0;
                    sc.first_move_override[th.ant_id] = choose_alt ? th.top_dir1 : th.top_dir0;
                }
                out.push_back(sc);
            }
        }
        if (out.empty()) out.push_back(Scenario{});
        return out;
    }

    static EvalKey simulate_candidate(const Snapshot &snapshot) {
        const std::vector<ThreatInfo> threats = compute_threats(snapshot);
        const std::vector<Scenario> scenarios = build_scenarios(snapshot, threats);
        std::vector<int> base_hp_samples;
        std::vector<int> safe_samples;
        base_hp_samples.reserve(scenarios.size());
        safe_samples.reserve(scenarios.size());
        int min_base_hp = 1 << 30;
        int damage_count = 0;
        int first_damage_round_best = kRolloutHorizon + 1;
        int kill_reward_sum = 0;
        int arrivals_sum = 0;
        double mean_base = 0.0;
        double mean_safe = 0.0;
        for (const auto &scenario : scenarios) {
            SimState sim = build_sim_state(snapshot);
            FastRng rng(scenario.seed);
            int first_damage_round = kRolloutHorizon + 1;
            for (int step = 0; step < kRolloutHorizon; ++step) {
                for (auto &tower : sim.towers) {
                    apply_tower_attack(sim, tower);
                }
                sim.rebuild_occ();
                std::sort(sim.ants.begin(), sim.ants.end(), [](const AntInfo &lhs, const AntInfo &rhs) { return lhs.id < rhs.id; });
                for (auto &ant : sim.ants) {
                    if (!is_alive_status(ant.status) || ant.hp <= 0) continue;
                    if (ant.frozen) {
                        ant.frozen = false;
                        continue;
                    }
                    const MoveSet moves = compute_moves_for_ant(sim, ant);
                    std::optional<int> forced;
                    if (step == 0) {
                        auto it = scenario.first_move_override.find(ant.id);
                        if (it != scenario.first_move_override.end()) forced = it->second;
                    }
                    const int dir = choose_override_or_sample(moves, forced, rng);
                    if (dir < 0) continue;
                    const int nx = ant.x + kOffset[ant.y % 2][dir][0];
                    const int ny = ant.y + kOffset[ant.y % 2][dir][1];
                    if (!is_path_cell(nx, ny)) continue;
                    sim.update_occ_move(ant.x, ant.y, nx, ny);
                    ant.x = nx;
                    ant.y = ny;
                    ant.last_move = dir;
                }
                resolve_lifecycle(sim);
                if (sim.my_base_hp < snapshot.bases[snapshot.player].hp && first_damage_round == kRolloutHorizon + 1) {
                    first_damage_round = step + 1;
                }
                maybe_spawn_enemy_ant(sim, rng);
                age_and_decay(sim);
                sim.my_coins += 1;
                sim.enemy_coins += 1;
                sim.round += 1;
                sim.rebuild_occ();
            }
            min_base_hp = std::min(min_base_hp, sim.my_base_hp);
            if (sim.my_base_hp < snapshot.bases[snapshot.player].hp) damage_count += 1;
            first_damage_round_best = std::min(first_damage_round_best, first_damage_round);
            kill_reward_sum += sim.kill_reward_acc;
            arrivals_sum += sim.enemy_arrivals;
            base_hp_samples.push_back(sim.my_base_hp);
            safe_samples.push_back(sim.my_coins - sim.safe_coin_threshold);
            mean_base += sim.my_base_hp;
            mean_safe += static_cast<double>(sim.my_coins - sim.safe_coin_threshold);
        }
        std::sort(base_hp_samples.begin(), base_hp_samples.end());
        const int tail_count = std::max<int>(1, (static_cast<int>(base_hp_samples.size()) + 3) / 4);
        double tail_base = 0.0;
        for (int i = 0; i < tail_count; ++i) tail_base += base_hp_samples[i];
        tail_base /= static_cast<double>(tail_count);
        const int min_safe = *std::min_element(safe_samples.begin(), safe_samples.end());
        mean_base /= static_cast<double>(scenarios.size());
        mean_safe /= static_cast<double>(scenarios.size());
        EvalKey key;
        key.min_base_hp = min_base_hp;
        key.damage_count = damage_count;
        key.first_damage_round = first_damage_round_best == kRolloutHorizon + 1 ? (kRolloutHorizon + 1) : first_damage_round_best;
        key.tail_base_hp = tail_base;
        key.mean_base_hp = mean_base;
        key.min_safe_slack = min_safe;
        key.mean_safe_slack = mean_safe;
        key.kill_reward = kill_reward_sum;
        key.enemy_arrivals = arrivals_sum;
        return key;
    }

    static EvalKey evaluate_candidate(const Snapshot &snapshot, const std::vector<Op> &ops) {
        Snapshot sim = snapshot;
        apply_ops_abstract(sim, ops);
        EvalKey key = simulate_candidate(sim);
        int action_count = static_cast<int>(ops.size());
        key.action_penalty = -action_count;
        for (const auto &op : ops) {
            if (op.type == kUpgradeGeneratedAnt) {
                if (sim.bases[sim.player].ant_level == 1) key.action_penalty += 1;
                else key.action_penalty += 0;
            } else if (op.type == kUpgradeGenerationSpeed) {
                key.action_penalty -= 2;
            } else if (op.type == kDowngradeTower) {
                key.action_penalty -= 3;
            }
        }
        key.note = "rollout16";
        return key;
    }
};

Snapshot parse_snapshot(const json &j) {
    Snapshot out;
    out.player = j.value("player", 0);
    out.round = j.value("round", 0);
    out.safe_coin_threshold = j.value("safe_coin_threshold", 0);
    out.nearest_enemy_distance = j.value("nearest_enemy_distance", 32);
    out.frontline_distance = j.value("frontline_distance", 32);
    if (j.contains("coins")) {
        const auto arr = j.at("coins").get<std::vector<int>>();
        if (arr.size() >= 2) {
            out.coins[0] = arr[0];
            out.coins[1] = arr[1];
        }
    }
    if (j.contains("die_count")) {
        const auto arr = j.at("die_count").get<std::vector<int>>();
        if (arr.size() >= 2) {
            out.die_count[0] = arr[0];
            out.die_count[1] = arr[1];
        }
    }
    if (j.contains("old_count")) {
        const auto arr = j.at("old_count").get<std::vector<int>>();
        if (arr.size() >= 2) {
            out.old_count[0] = arr[0];
            out.old_count[1] = arr[1];
        }
    }
    if (j.contains("weapon_cooldowns")) {
        const auto arr = j.at("weapon_cooldowns").get<std::vector<std::vector<int>>>();
        for (int p = 0; p < std::min<int>(2, static_cast<int>(arr.size())); ++p) {
            for (int i = 0; i < std::min<int>(5, static_cast<int>(arr[p].size())); ++i) out.weapon_cooldowns[p][i] = arr[p][i];
        }
    }
    for (const auto &base_j : j.at("bases")) {
        BaseInfo base;
        base.player = base_j.value("player", -1);
        base.x = base_j.value("x", -1);
        base.y = base_j.value("y", -1);
        base.hp = base_j.value("hp", 50);
        base.generation_level = base_j.value("generation_level", 0);
        base.ant_level = base_j.value("ant_level", 0);
        out.bases.push_back(base);
    }
    for (const auto &tower_j : j.at("towers")) {
        TowerInfo tower;
        tower.id = tower_j.value("id", -1);
        tower.player = tower_j.value("player", -1);
        tower.x = tower_j.value("x", -1);
        tower.y = tower_j.value("y", -1);
        tower.type = tower_j.value("type", -1);
        tower.cooldown = tower_j.value("cooldown", 0.0);
        out.towers.push_back(tower);
    }
    for (const auto &ant_j : j.at("ants")) {
        AntInfo ant;
        ant.id = ant_j.value("id", -1);
        ant.player = ant_j.value("player", -1);
        ant.x = ant_j.value("x", -1);
        ant.y = ant_j.value("y", -1);
        ant.hp = ant_j.value("hp", 0);
        ant.level = ant_j.value("level", 0);
        ant.age = ant_j.value("age", 0);
        ant.status = ant_j.value("status", 0);
        ant.behavior = ant_j.value("behavior", 0);
        ant.last_move = ant_j.value("last_move", -1);
        ant.behavior_turns = ant_j.value("behavior_turns", 0);
        ant.behavior_expiry = ant_j.value("behavior_expiry", 0);
        ant.frozen = ant_j.value("frozen", false);
        ant.bewitch_target_x = ant_j.value("bewitch_target_x", -1);
        ant.bewitch_target_y = ant_j.value("bewitch_target_y", -1);
        out.ants.push_back(ant);
    }
    if (j.contains("effects")) {
        for (const auto &effect_j : j.at("effects")) {
            EffectInfo effect;
            effect.type = effect_j.value("type", -1);
            effect.player = effect_j.value("player", -1);
            effect.x = effect_j.value("x", -1);
            effect.y = effect_j.value("y", -1);
            effect.remaining = effect_j.value("remaining", 0);
            out.effects.push_back(effect);
        }
    }
    if (j.contains("slots")) {
        for (const auto &slot_j : j.at("slots")) {
            SlotInfo slot;
            slot.code = slot_j.value("code", "");
            slot.branch = slot_j.value("branch", "");
            slot.x = slot_j.value("x", -1);
            slot.y = slot_j.value("y", -1);
            slot.priority = slot_j.value("priority", 0.0);
            slot.build_legal = slot_j.value("build_legal", false);
            slot.tower_id = slot_j.value("tower_id", -1);
            slot.tower_type = slot_j.value("tower_type", -1);
            out.slots.push_back(slot);
        }
    }
    if (j.contains("pheromone")) {
        for (int p = 0; p < 2; ++p) {
            for (int x = 0; x < kMapSize; ++x) {
                for (int y = 0; y < kMapSize; ++y) {
                    out.pheromone[p][x][y] = 80000;
                }
            }
        }
        const auto &ph = j.at("pheromone");
        for (int p = 0; p < std::min<int>(2, static_cast<int>(ph.size())); ++p) {
            for (int x = 0; x < std::min<int>(kMapSize, static_cast<int>(ph[p].size())); ++x) {
                for (int y = 0; y < std::min<int>(kMapSize, static_cast<int>(ph[p][x].size())); ++y) {
                    out.pheromone[p][x][y] = ph[p][x][y].get<int>();
                }
            }
        }
    } else {
        for (int p = 0; p < 2; ++p) for (int x = 0; x < kMapSize; ++x) for (int y = 0; y < kMapSize; ++y) out.pheromone[p][x][y] = 80000;
    }
    return out;
}

void print_ops(const std::vector<Op> &ops) {
    std::cout << ops.size() << '\n';
    for (const auto &op : ops) {
        if (op.type == kBuildTower || op.type == kUseLightningStorm || op.type == kUpgradeTower) {
            std::cout << op.type << ' ' << op.arg0 << ' ' << op.arg1 << '\n';
        } else if (op.type == kDowngradeTower) {
            std::cout << op.type << ' ' << op.arg0 << '\n';
        } else if (op.type == kUpgradeGenerationSpeed || op.type == kUpgradeGeneratedAnt) {
            std::cout << op.type << '\n';
        }
    }
    std::cout.flush();
}

std::vector<int> parse_query_ids(const json &payload, const Snapshot &snapshot) {
    std::vector<int> out;
    if (payload.contains("query_ant_ids")) {
        out = payload.at("query_ant_ids").get<std::vector<int>>();
    } else {
        for (const auto &ant : snapshot.ants) if (ant.player != snapshot.player) out.push_back(ant.id);
    }
    return out;
}

} // namespace

int main(int argc, char **argv) {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    if (argc >= 2 && std::string(argv[1]) == "--sample-moves") {
        const int loops = argc >= 3 ? std::max(1, std::stoi(argv[2])) : 4000;
        std::string input((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
        if (input.empty()) return 1;
        const json payload = json::parse(input);
        const Snapshot snapshot = parse_snapshot(payload);
        V4AI ai;
        const auto query_ids = parse_query_ids(payload, snapshot);
        std::cout << ai.sample_first_moves(snapshot, query_ids, loops).dump() << '\n';
        return 0;
    }

    std::string init_line;
    if (!std::getline(std::cin, init_line)) {
        return 0;
    }

    V4AI ai;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        try {
            const json snapshot_json = json::parse(line);
            const Snapshot snapshot = parse_snapshot(snapshot_json);
            print_ops(ai.decide(snapshot));
        } catch (const std::exception &exc) {
            std::cerr << "[cpp_v4] error: " << exc.what() << '\n';
            print_ops({});
        }
    }
    return 0;
}
