#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <tuple>
#include <unordered_set>
#include <utility>
#include <vector>

#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/random_search_params.hpp"
#include "antgame_sdk/sdk.hpp"

namespace antgame::sdk {

struct RandomSearchDecisionContext {
    const PublicState *state = nullptr;
    const NativeSimulator *simulator = nullptr;
    int player = 0;
    bool opponent_ops_already_applied = false;
};

struct RandomSearchSession {
    std::array<int, 2> last_round_seen = {-1, -1};
    std::array<std::uint64_t, 2> decision_serial = {0, 0};

    void observe(const PublicState &state, int player) {
        if (last_round_seen[player] == state.round_index) {
            return;
        }
        last_round_seen[player] = state.round_index;
        ++decision_serial[player];
    }
};

namespace random_search_detail {

constexpr int kMoveOpposite[6] = {3, 4, 5, 0, 1, 2};
constexpr int kCombatTowerAttackDamage = 5;
constexpr int kCombatSelfDestructDamage = 10;
constexpr int kCombatSelfDestructRange = 1;
constexpr int kNoMove = -1;
constexpr int kBehaviorDecayTurns = 5;
constexpr int kTeleportInterval = 10;
constexpr double kTeleportRatio = 0.1;
constexpr int kLightningAntDamage = 20;
constexpr int kLightningTowerDamage = 3;
constexpr int kLightningTowerInterval = 5;
constexpr int kMaxSimTowers = 64;
constexpr int kMaxSimAnts = 512;
constexpr int kMaxSimEffects = 32;
constexpr int kMaxMoveCandidates = 6;
constexpr int kMaxImportantAnts = 5;
constexpr int kMaxValidCells = kMapSize * kMapSize;
constexpr int kMaxReverseHeapEntries = 8192;
constexpr int kMaxCachedRange = 4;
constexpr int kMaxRangeCells = 61;

[[noreturn]] inline void fixed_storage_overflow(const char *label) {
    std::cerr << "random_search_baseline fixed storage overflow: " << label << '\n';
    std::abort();
}

template <typename T, int Capacity>
struct FixedList {
    int count = 0;
    T data[Capacity]{};

    int size() const { return count; }
    bool empty() const { return count <= 0; }
    void clear() { count = 0; }
    void reserve(int) {}

    T &operator[](int index) { return data[index]; }
    const T &operator[](int index) const { return data[index]; }

    T *begin() { return data; }
    T *end() { return data + count; }
    const T *begin() const { return data; }
    const T *end() const { return data + count; }

    T &back() { return data[count - 1]; }
    const T &back() const { return data[count - 1]; }

    void push_back(const T &value) {
        if (count >= Capacity) {
            fixed_storage_overflow(__PRETTY_FUNCTION__);
        }
        data[count++] = value;
    }

    template <typename... Args>
    T &emplace_back(Args... args) {
        if (count >= Capacity) {
            fixed_storage_overflow(__PRETTY_FUNCTION__);
        }
        data[count] = T{args...};
        ++count;
        return data[count - 1];
    }

    void pop_back() {
        if (count > 0) {
            --count;
        }
    }

    void resize(int new_size) {
        if (new_size < 0 || new_size > Capacity) {
            fixed_storage_overflow(__PRETTY_FUNCTION__);
        }
        if (new_size > count) {
            for (int index = count; index < new_size; ++index) {
                data[index] = T{};
            }
        }
        count = new_size;
    }

    void erase_at(int index) {
        if (index < 0 || index >= count) {
            return;
        }
        for (int pos = index + 1; pos < count; ++pos) {
            data[pos - 1] = data[pos];
        }
        --count;
    }
};

struct DoubleGrid {
    float data[kMapSize][kMapSize]{};

    float *operator[](int x) { return data[x]; }
    const float *operator[](int x) const { return data[x]; }
};

struct IntGrid {
    int data[kMapSize][kMapSize]{};

    int *operator[](int x) { return data[x]; }
    const int *operator[](int x) const { return data[x]; }
};

struct FloatCells {
    float data[kMaxValidCells]{};

    float &operator[](int index) { return data[index]; }
    const float &operator[](int index) const { return data[index]; }
};

struct IntPair {
    int first = -1;
    int second = -1;
};

struct MoveCandidate {
    int direction = kNoMove;
    int nx = -1;
    int ny = -1;
};

struct GeometryCache {
    int valid_count = 0;
    int index_by_cell[kMapSize][kMapSize]{};
    int cell_x[kMaxValidCells]{};
    int cell_y[kMaxValidCells]{};
    int neighbor_by_dir[kMaxValidCells][6]{};
    int distance[kMaxValidCells][kMaxValidCells]{};
    int range_count[kMaxValidCells][kMaxCachedRange + 1]{};
    int range_cells[kMaxValidCells][kMaxCachedRange + 1][kMaxRangeCells]{};
    int base_distance = 0;

    GeometryCache() {
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                index_by_cell[x][y] = -1;
            }
        }
        for (int index = 0; index < kMaxValidCells; ++index) {
            for (int direction = 0; direction < 6; ++direction) {
                neighbor_by_dir[index][direction] = -1;
            }
        }
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                if (!is_valid_pos(x, y)) {
                    continue;
                }
                index_by_cell[x][y] = valid_count;
                cell_x[valid_count] = x;
                cell_y[valid_count] = y;
                ++valid_count;
            }
        }
        for (int index = 0; index < valid_count; ++index) {
            const int x = cell_x[index];
            const int y = cell_y[index];
            for (int direction = 0; direction < 6; ++direction) {
                const int nx = x + kOffset[y & 1][direction][0];
                const int ny = y + kOffset[y & 1][direction][1];
                if (!is_valid_pos(nx, ny)) {
                    continue;
                }
                neighbor_by_dir[index][direction] = index_by_cell[nx][ny];
            }
        }
        for (int lhs = 0; lhs < valid_count; ++lhs) {
            for (int rhs = 0; rhs < valid_count; ++rhs) {
                distance[lhs][rhs] = hex_distance(cell_x[lhs], cell_y[lhs], cell_x[rhs], cell_y[rhs]);
            }
        }
        for (int center = 0; center < valid_count; ++center) {
            for (int other = 0; other < valid_count; ++other) {
                const int dist = distance[center][other];
                for (int range = dist; range <= kMaxCachedRange; ++range) {
                    const int count = range_count[center][range];
                    if (count >= kMaxRangeCells) {
                        fixed_storage_overflow("GeometryCache::range_cells");
                    }
                    range_cells[center][range][count] = other;
                    range_count[center][range] = count + 1;
                }
            }
        }
        base_distance =
            distance[index_by_cell[kPlayerBases[0].first][kPlayerBases[0].second]][index_by_cell[kPlayerBases[1].first][kPlayerBases[1].second]];
    }
};

inline const GeometryCache &geometry_cache() {
    static const GeometryCache cache;
    return cache;
}

inline int cell_index_of(int x, int y) {
    if (x < 0 || x >= kMapSize || y < 0 || y >= kMapSize) {
        return -1;
    }
    return geometry_cache().index_by_cell[x][y];
}

inline int cell_distance_by_index(int lhs, int rhs) {
    if (lhs < 0 || rhs < 0) {
        return 0;
    }
    return geometry_cache().distance[lhs][rhs];
}

inline int cell_distance_fast(int x0, int y0, int x1, int y1) {
    const int lhs = cell_index_of(x0, y0);
    const int rhs = cell_index_of(x1, y1);
    if (lhs >= 0 && rhs >= 0) {
        return cell_distance_by_index(lhs, rhs);
    }
    return hex_distance(x0, y0, x1, y1);
}

struct ForcedMove {
    int ant_id = -1;
    int direction = kNoMove;
};

struct ReverseHeapNode {
    int cell_index = -1;
    float total = 0.0f;
    float damage = 0.0f;
};

struct ReverseHeap {
    int count = 0;
    ReverseHeapNode nodes[kMaxReverseHeapEntries]{};

    static bool better(const ReverseHeapNode &lhs, const ReverseHeapNode &rhs) {
        if (lhs.total != rhs.total) {
            return lhs.total < rhs.total;
        }
        return lhs.damage < rhs.damage;
    }

    bool empty() const { return count <= 0; }

    void push(const ReverseHeapNode &node) {
        if (count >= kMaxReverseHeapEntries) {
            fixed_storage_overflow("ReverseHeap::push");
        }
        int index = count++;
        nodes[index] = node;
        while (index > 0) {
            const int parent = (index - 1) / 2;
            if (!better(nodes[index], nodes[parent])) {
                break;
            }
            std::swap(nodes[index], nodes[parent]);
            index = parent;
        }
    }

    ReverseHeapNode pop() {
        const ReverseHeapNode top = nodes[0];
        --count;
        if (count > 0) {
            nodes[0] = nodes[count];
            int index = 0;
            while (true) {
                const int left = index * 2 + 1;
                const int right = left + 1;
                int best = index;
                if (left < count && better(nodes[left], nodes[best])) {
                    best = left;
                }
                if (right < count && better(nodes[right], nodes[best])) {
                    best = right;
                }
                if (best == index) {
                    break;
                }
                std::swap(nodes[index], nodes[best]);
                index = best;
            }
        }
        return top;
    }
};

template <int Capacity>
struct IdCountMap {
    int count = 0;
    int keys[Capacity]{};
    int values[Capacity]{};

    void clear() { count = 0; }

    int get(int key) const {
        for (int index = 0; index < count; ++index) {
            if (keys[index] == key) {
                return values[index];
            }
        }
        return 0;
    }

    void increment(int key) {
        for (int index = 0; index < count; ++index) {
            if (keys[index] == key) {
                ++values[index];
                return;
            }
        }
        if (count >= Capacity) {
            fixed_storage_overflow("IdCountMap::increment");
        }
        keys[count] = key;
        values[count] = 1;
        ++count;
    }
};

inline std::uint64_t mix_seed(std::uint64_t seed, std::uint64_t value) {
    std::uint64_t mixed = seed + 0x9e3779b97f4a7c15ULL + (value << 1U);
    mixed = (mixed ^ (mixed >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    mixed = (mixed ^ (mixed >> 27U)) * 0x94d049bb133111ebULL;
    return mixed ^ (mixed >> 31U);
}

struct FastRng {
    std::uint64_t state = 0;

    explicit FastRng(std::uint64_t seed) : state(seed ? seed : 0x853c49e6748fea9bULL) {}

    std::uint64_t next_u64() {
        state ^= state >> 12U;
        state ^= state << 25U;
        state ^= state >> 27U;
        return state * 2685821657736338717ULL;
    }

    int next_int(int bound) {
        if (bound <= 1) {
            return 0;
        }
        return static_cast<int>(next_u64() % static_cast<std::uint64_t>(bound));
    }

    double next_double() {
        constexpr double kInv = 1.0 / static_cast<double>(1ULL << 53U);
        return static_cast<double>(next_u64() >> 11U) * kInv;
    }
};

struct SearchTower {
    int tower_id = -1;
    int x = -1;
    int y = -1;
    TowerType tower_type = TowerType::Basic;
    int hp = 0;
    int cooldown = 0;

    int max_hp() const { return tower_stats(tower_type).max_hp; }
    int damage() const { return tower_stats(tower_type).damage; }
    int attack_range() const { return tower_stats(tower_type).attack_range; }
    bool alive() const { return hp > 0; }
};

struct SearchAnt {
    int ant_id = -1;
    int x = -1;
    int y = -1;
    int hp = 0;
    int level = 0;
    int age = 0;
    int last_move = kNoMove;
    AntBehavior behavior = AntBehavior::Default;
    AntKind kind = AntKind::Worker;
    int shield = 0;
    bool defend = false;
    bool control_free_on_break = false;
    bool is_frozen = false;
    int behavior_rounds = 0;
    int behavior_expiry = 0;
    int target_x = -1;
    int target_y = -1;
    std::uint64_t trail_mask[kTrailMaskWords]{};

    int max_hp() const { return kind == AntKind::Combat ? 30 : ant_max_hp(level); }
    int kill_reward() const { return kind == AntKind::Combat ? 18 : ant_kill_reward(level); }
    bool alive() const { return hp > 0; }
    bool too_old() const { return kind != AntKind::Combat && age > 64; }
    bool control_immune() const { return behavior == AntBehavior::ControlFree; }
    bool reached_target() const { return target_x == x && target_y == y; }
};

inline void mark_ant_trail(SearchAnt &ant, int x, int y) {
    if (x < 0 || x >= kMapSize || y < 0 || y >= kMapSize) {
        return;
    }
    const int bit_index = x * kMapSize + y;
    ant.trail_mask[bit_index / 64] |= 1ULL << (bit_index % 64);
}

struct SearchEffect {
    SuperWeaponType weapon_type = SuperWeaponType::LightningStorm;
    int x = -1;
    int y = -1;
    int remaining_turns = 0;

    bool active() const { return remaining_turns > 0; }
    bool in_range(int tx, int ty) const {
        return active() && cell_distance_fast(x, y, tx, ty) <= weapon_stats(weapon_type).attack_range;
    }
};

struct MoveOption {
    int direction = kNoMove;
    int nx = -1;
    int ny = -1;
    double probability = 1.0;
    double danger = 0.0;
};

struct MoveOptionsResult {
    FixedList<MoveOption, kMaxMoveCandidates> options;
    FixedList<IntPair, kMaxMoveCandidates> annotated_cells;
    FixedList<int, kMaxMoveCandidates> annotated_towers;
};

struct ComboRolloutSpec {
    FixedList<ForcedMove, kMaxImportantAnts> forced_moves;
    double probability = 1.0;
    double danger = 0.0;
    int samples = 1;
};

struct OffensiveExpectation {
    std::array<double, 8> money_gain_by_round = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
};

struct OperationCandidate {
    Operation operation;
    std::string label;
    double heuristic = 0.0;
};

struct SearchPlan {
    std::string name;
    bool has_first = false;
    Operation first;
    bool has_second = false;
    Operation second;
    int blocked_x = -1;
    int blocked_y = -1;
    int blocked_tower_id = -1;
    double terminal_bonus = 0.0;
    double heuristic = 0.0;
    double penalty = 0.0;
};

struct PlanResult {
    double score = -std::numeric_limits<double>::infinity();
    std::vector<Operation> operations;
};

struct PenaltyBreakdown {
    double downgrade = 0.0;
    double lightning = 0.0;
    double hold_bias = 0.0;
    double emergency_discount = 0.0;
    double total = 0.0;
};

struct TerminalEvaluationBreakdown {
    double base_hp_raw = 0.0;
    double base_hp_score = 0.0;
    double tower_value_raw = 0.0;
    double tower_value_score = 0.0;
    double tower_bonus_score = 0.0;
    double ant_threat_raw = 0.0;
    double ant_threat_score = 0.0;
    double money_raw = 0.0;
    double money_score = 0.0;
    double terminal_bonus_score = 0.0;
    double total = 0.0;

    TerminalEvaluationBreakdown &operator+=(const TerminalEvaluationBreakdown &other) {
        base_hp_raw += other.base_hp_raw;
        base_hp_score += other.base_hp_score;
        tower_value_raw += other.tower_value_raw;
        tower_value_score += other.tower_value_score;
        tower_bonus_score += other.tower_bonus_score;
        ant_threat_raw += other.ant_threat_raw;
        ant_threat_score += other.ant_threat_score;
        money_raw += other.money_raw;
        money_score += other.money_score;
        terminal_bonus_score += other.terminal_bonus_score;
        total += other.total;
        return *this;
    }
};

struct EvaluatedPlanDebug {
    std::size_t eval_index = 0;
    std::string key;
    std::string name;
    std::string first_text;
    std::string second_text;
    double score = -std::numeric_limits<double>::infinity();
    double score_before_penalty = -std::numeric_limits<double>::infinity();
    double heuristic = 0.0;
    double penalty = 0.0;
    int rollouts = 0;
    TerminalEvaluationBreakdown terminal;
    PenaltyBreakdown penalty_breakdown;
};

inline bool is_edge_cell(int x, int y) {
    return x == 0 || y == 0 || x == kMapSize - 1 || y == kMapSize - 1;
}

inline int distance_to_boundary(int x, int y) {
    int best = std::min({x, y, kMapSize - 1 - x, kMapSize - 1 - y});
    for (int ny = 0; ny < kMapSize; ++ny) {
        if (!is_valid_pos(x, ny)) {
            best = std::min(best, std::abs(y - ny));
        }
    }
    for (int nx = 0; nx < kMapSize; ++nx) {
        if (!is_valid_pos(nx, y)) {
            best = std::min(best, std::abs(x - nx));
        }
    }
    return best;
}

inline std::string op_key(const Operation &operation) {
    std::ostringstream oss;
    oss << static_cast<int>(operation.op_type) << ':' << operation.arg0 << ':' << operation.arg1;
    return oss.str();
}

enum class DebugMode : int {
    None = 0,
    Summary = 1,
    Plans = 2,
};

inline DebugMode debug_mode() {
    static const DebugMode mode = []() {
        const char *value = std::getenv("ANTGAME_CPP_BASELINE_DEBUG");
        if (value == nullptr || *value == '\0') {
            return DebugMode::None;
        }
        const std::string text(value);
        if (text == "0" || text == "off" || text == "false") {
            return DebugMode::None;
        }
        if (text == "1" || text == "summary") {
            return DebugMode::Summary;
        }
        return DebugMode::Plans;
    }();
    return mode;
}

inline std::string debug_json_escape(const std::string &text) {
    std::ostringstream oss;
    for (char ch : text) {
        switch (ch) {
        case '\\':
            oss << "\\\\";
            break;
        case '"':
            oss << "\\\"";
            break;
        case '\n':
            oss << "\\n";
            break;
        case '\r':
            oss << "\\r";
            break;
        case '\t':
            oss << "\\t";
            break;
        default:
            if (static_cast<unsigned char>(ch) < 0x20U) {
                oss << '?';
            } else {
                oss << ch;
            }
            break;
        }
    }
    return oss.str();
}

inline std::string debug_operation_text(const Operation &operation) {
    std::ostringstream oss;
    const auto tokens = operation.to_protocol_tokens();
    for (std::size_t index = 0; index < tokens.size(); ++index) {
        if (index > 0) {
            oss << ' ';
        }
        oss << tokens[index];
    }
    return oss.str();
}

inline double behavior_threat_scale(AntBehavior behavior) {
    const auto &cfg = config();
    switch (behavior) {
    case AntBehavior::Random:
        return cfg.randomized_threat_scale;
    case AntBehavior::Bewitched:
        return cfg.bewitched_threat_scale;
    case AntBehavior::ControlFree:
        return cfg.control_free_threat_scale;
    default:
        return 1.0;
    }
}

inline int lightning_active_turn(int remaining_duration) {
    return weapon_stats(SuperWeaponType::LightningStorm).duration - remaining_duration + 1;
}

inline bool lightning_tower_strike_turn(int remaining_duration) {
    const int active_turn = lightning_active_turn(remaining_duration);
    return active_turn > 0 && active_turn % kLightningTowerInterval == 0;
}

inline bool enemy_superweapon_window_active(const PublicState &state, int player) {
    const int enemy = 1 - player;
    for (const auto &effect : state.active_effects) {
        if (effect.player == enemy && effect.remaining_turns > 0) {
            return true;
        }
    }
    return false;
}

inline int attack_cooldown_reset(TowerType type) {
    const double speed = tower_stats(type).speed;
    if (speed < 1.0) {
        return 0;
    }
    return std::max(0, static_cast<int>(std::llround(speed)));
}

inline int ant_tower_attack_damage(const SearchAnt &ant) {
    if (ant.kind == AntKind::Combat) {
        return kCombatTowerAttackDamage;
    }
    constexpr int worker_damage[3] = {1, 2, 4};
    return worker_damage[std::clamp(ant.level, 0, 2)];
}

inline bool should_self_destruct(const SearchAnt &ant) {
    return ant.kind == AntKind::Combat && ant.hp * 2 < ant.max_hp();
}

inline double ant_pheromone_weight(const SearchAnt &ant) {
    return ant.kind == AntKind::Combat ? 0.05 : 0.15;
}

inline int half_plane_delta(int player, int x, int y) {
    const auto [own_x, own_y] = kPlayerBases[player];
    const auto [enemy_x, enemy_y] = kPlayerBases[1 - player];
    return cell_distance_fast(x, y, own_x, own_y) - cell_distance_fast(x, y, enemy_x, enemy_y);
}

inline bool ant_in_own_half(int player, int x, int y) {
    return half_plane_delta(player, x, y) <= 0;
}

struct ImmediateThreatContext {
    int nearest_combat_base_distance = 99;
    int nearest_worker_base_distance = 99;
    int combat_ring1 = 0;
    int combat_ring2 = 0;
    double combat_pressure = 0.0;
    double tower_pressure = 0.0;

    bool urgent() const { return combat_ring2 > 0 || tower_pressure >= 20.0; }
    bool critical() const { return combat_ring1 > 0; }
};

inline ImmediateThreatContext immediate_threat_context(const PublicState &state, int player) {
    ImmediateThreatContext context;
    const int enemy = 1 - player;
    const auto [base_x, base_y] = kPlayerBases[player];
    for (const auto &ant : state.ants) {
        if (ant.player != enemy || !ant.is_alive()) {
            continue;
        }
        const int base_distance = cell_distance_fast(base_x, base_y, ant.x, ant.y);
        const double behavior_scale = behavior_threat_scale(ant.behavior);
        if (ant.kind == AntKind::Combat) {
            context.nearest_combat_base_distance = std::min(context.nearest_combat_base_distance, base_distance);
            if (base_distance <= 1) {
                ++context.combat_ring1;
            }
            if (base_distance <= 2) {
                ++context.combat_ring2;
            }
            context.combat_pressure += (8.0 + static_cast<double>(ant.hp) * 0.35) * behavior_scale /
                                       (1.0 + static_cast<double>(base_distance));
            for (const auto &tower : state.towers) {
                if (tower.player != player || tower.hp <= 0) {
                    continue;
                }
                const int distance = cell_distance_fast(tower.x, tower.y, ant.x, ant.y);
                if (distance > 3) {
                    continue;
                }
                double tower_value = static_cast<double>(tower.hp);
                if (tower.tower_type == TowerType::Bewitch) {
                    tower_value += 18.0;
                } else if (tower.tower_type == TowerType::QuickPlus) {
                    tower_value += 12.0;
                } else if (tower.tower_type == TowerType::Heavy) {
                    tower_value += 10.0;
                }
                context.tower_pressure += tower_value * behavior_scale / (1.0 + static_cast<double>(distance));
            }
        } else {
            context.nearest_worker_base_distance = std::min(context.nearest_worker_base_distance, base_distance);
        }
    }
    return context;
}

inline PenaltyBreakdown operation_penalty_breakdown(const PublicState &state, int player, const SearchPlan &plan) {
    const auto &cfg = config();
    PenaltyBreakdown penalty;
    const bool enemy_superweapon_window = enemy_superweapon_window_active(state, player);
    auto apply_single = [&](const Operation &operation) {
        switch (operation.op_type) {
        case OperationType::DowngradeTower:
            penalty.downgrade += cfg.downgrade_penalty;
            {
                const int refund = state.operation_income(player, operation);
                if (refund > 0) {
                    penalty.downgrade += static_cast<double>(refund) * cfg.money_weight *
                                         cfg.downgrade_refund_penalty_scale;
                }
            }
            break;
        case OperationType::UseLightningStorm:
            penalty.lightning += cfg.lightning_penalty;
            if (enemy_superweapon_window) {
                penalty.emergency_discount += cfg.enemy_superweapon_window_lightning_bonus;
            }
            break;
        default:
            break;
        }
    };
    if (plan.has_first) {
        apply_single(plan.first);
    }
    if (plan.has_second) {
        apply_single(plan.second);
    }
    if (!plan.has_first && !plan.has_second) {
        penalty.hold_bias += cfg.hold_bias;
    }
    penalty.total = penalty.downgrade + penalty.lightning - penalty.hold_bias - penalty.emergency_discount;
    return penalty;
}

inline double operation_penalty(const PublicState &state, int player, const SearchPlan &plan) {
    return operation_penalty_breakdown(state, player, plan).total;
}

inline TowerType downgrade_target_type(TowerType tower_type) {
    if (tower_type == TowerType::Basic) {
        return TowerType::Basic;
    }
    return static_cast<TowerType>(static_cast<int>(tower_type) / 10);
}

inline int exact_destroy_tower_income(int tower_count, int hp, int max_hp) {
    const double refund =
        static_cast<double>(tower_build_cost_for_count(std::max(tower_count - 1, 0))) * kTowerDowngradeRefundRatio;
    return static_cast<int>(refund * static_cast<double>(std::max(hp, 0)) / std::max(1, max_hp));
}

inline int exact_downgrade_tower_income(TowerType tower_type, int hp, int max_hp) {
    const double refund = static_cast<double>(upgrade_tower_cost(tower_type)) * kTowerDowngradeRefundRatio;
    return static_cast<int>(refund * static_cast<double>(std::max(hp, 0)) / std::max(1, max_hp));
}

template <typename TowerList>
inline double tower_full_salvage_value(const TowerList &towers) {
    struct BasicRefund {
        int hp = 0;
    };

    double total = 0.0;
    BasicRefund basics[kMaxSimTowers]{};
    int basic_count = 0;

    for (const auto &tower : towers) {
        if (!tower.alive()) {
            continue;
        }
        TowerType current_type = tower.tower_type;
        int current_hp = tower.hp;
        while (current_type != TowerType::Basic) {
            total += static_cast<double>(
                exact_downgrade_tower_income(current_type, current_hp, tower_stats(current_type).max_hp));
            const int previous_max_hp = tower_stats(current_type).max_hp;
            current_type = downgrade_target_type(current_type);
            const int downgraded_max_hp = tower_stats(current_type).max_hp;
            current_hp = previous_max_hp > 0
                             ? std::max(1, (downgraded_max_hp * current_hp + previous_max_hp - 1) / previous_max_hp)
                             : downgraded_max_hp;
        }
        if (basic_count >= kMaxSimTowers) {
            fixed_storage_overflow("tower_full_salvage_value basics");
        }
        basics[basic_count++] = BasicRefund{std::max(current_hp, 0)};
    }

    for (int i = 0; i < basic_count; ++i) {
        int best = i;
        for (int j = i + 1; j < basic_count; ++j) {
            if (basics[j].hp > basics[best].hp) {
                best = j;
            }
        }
        if (best != i) {
            const BasicRefund tmp = basics[i];
            basics[i] = basics[best];
            basics[best] = tmp;
        }
    }
    int tower_count = basic_count;
    for (int index = 0; index < basic_count; ++index) {
        total += static_cast<double>(exact_destroy_tower_income(
            tower_count, basics[index].hp, tower_stats(TowerType::Basic).max_hp));
        --tower_count;
    }
    return total;
}

inline double tower_estimated_salvage_value(const SearchTower &tower, int tower_count_hint) {
    if (!tower.alive()) {
        return 0.0;
    }

    double total = 0.0;
    TowerType current_type = tower.tower_type;
    int current_hp = tower.hp;
    while (current_type != TowerType::Basic) {
        total += static_cast<double>(
            exact_downgrade_tower_income(current_type, current_hp, tower_stats(current_type).max_hp));
        const int previous_max_hp = tower_stats(current_type).max_hp;
        current_type = downgrade_target_type(current_type);
        const int downgraded_max_hp = tower_stats(current_type).max_hp;
        current_hp = previous_max_hp > 0
                         ? std::max(1, (downgraded_max_hp * current_hp + previous_max_hp - 1) / previous_max_hp)
                         : downgraded_max_hp;
    }

    total += static_cast<double>(
        exact_destroy_tower_income(tower_count_hint, current_hp, tower_stats(TowerType::Basic).max_hp));
    return total;
}

inline double tower_type_bonus(TowerType tower_type) {
    const auto &cfg = config();
    if (tower_type == TowerType::Heavy) {
        return cfg.heavy_tower_bonus;
    }
    if (tower_type == TowerType::Bewitch) {
        return cfg.bewitch_tower_bonus;
    }
    return 0.0;
}

inline double tower_position_bonus(int player, int x, int y) {
    return random_search_position_bonus(old_ai_position_code_at(player, x, y));
}

inline bool is_two_step_core_slot(int player, int x, int y) {
    return is_core_build_position(old_ai_position_code_at(player, x, y));
}

inline double ant_base_distance_factor(int base_distance) {
    switch (base_distance) {
    case 0:
        return 1.0;
    case 1:
        return 0.8;
    case 2:
        return 0.6;
    case 3:
        return 0.42;
    case 4:
        return 0.28;
    case 5:
        return 0.18;
    case 6:
        return 0.10;
    default:
        return 0.05;
    }
}

struct DefenseSimulatorProfile {
    std::uint64_t rounds = 0;
    std::uint64_t tower_attack_ns = 0;
    std::uint64_t move_ns = 0;
    std::uint64_t move_cache_ns = 0;
    std::uint64_t move_sample_ns = 0;
    std::uint64_t move_random_ns = 0;
    std::uint64_t move_resolve_ns = 0;
    std::uint64_t teleport_ns = 0;
    std::uint64_t pheromone_ns = 0;
    std::uint64_t pheromone_trail_ns = 0;
    std::uint64_t manage_ns = 0;
    std::uint64_t spawn_ns = 0;
    std::uint64_t age_ns = 0;
    std::uint64_t income_ns = 0;
    std::uint64_t effects_ns = 0;
    std::uint64_t move_sample_calls = 0;
    std::uint64_t move_random_calls = 0;
    std::uint64_t move_resolve_calls = 0;
    std::uint64_t move_cache_calls = 0;
};

inline std::uint64_t profile_now_ns() {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch())
            .count());
}

class DefenseSimulator {
  public:
    int player = 0;
    int enemy = 1;
    int round_index = 0;
    double coins = 0.0;
    int base_hp = kBaseHp;
    int enemy_generation_level = 0;
    int enemy_ant_level = 0;
    int next_ant_id = 0;
    int next_tower_id = 0;
    int lightning_cooldown = 0;
    bool terminal = false;
    bool ignore_enemy_spawns = false;
    DefenseSimulatorProfile *profile = nullptr;

    FixedList<SearchTower, kMaxSimTowers> towers;
    FixedList<SearchAnt, kMaxSimAnts> ants;
    FixedList<SearchEffect, kMaxSimEffects> my_effects;
    FixedList<SearchEffect, kMaxSimEffects> enemy_effects;
    float pheromone[kMapSize][kMapSize]{};

    DefenseSimulator clone() const {
        DefenseSimulator out;
        out.player = player;
        out.enemy = enemy;
        out.round_index = round_index;
        out.coins = coins;
        out.base_hp = base_hp;
        out.enemy_generation_level = enemy_generation_level;
        out.enemy_ant_level = enemy_ant_level;
        out.next_ant_id = next_ant_id;
        out.next_tower_id = next_tower_id;
        out.lightning_cooldown = lightning_cooldown;
        out.terminal = terminal;
        out.ignore_enemy_spawns = ignore_enemy_spawns;
        out.profile = profile;
        out.towers = towers;
        out.ants = ants;
        out.my_effects = my_effects;
        out.enemy_effects = enemy_effects;
        std::memcpy(out.pheromone, pheromone, sizeof(pheromone));
        // Movement and tower-lookup caches are derived from the fields above.
        // Avoid copying them on every rollout clone; they are rebuilt lazily.
        out.move_cache.static_risk_dirty = true;
        out.move_cache.move_cache_dirty = true;
        out.tower_lookup.dirty = true;
        return out;
    }

    void refresh_tower_lookup() const {
        if (!tower_lookup.dirty) {
            return;
        }
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                tower_lookup.index_by_cell[x][y] = -1;
            }
        }
        for (int index = 0; index < towers.size(); ++index) {
            const auto &tower = towers[index];
            if (!tower.alive()) {
                continue;
            }
            tower_lookup.index_by_cell[tower.x][tower.y] = index;
        }
        tower_lookup.dirty = false;
    }

    void invalidate_tower_lookup() {
        tower_lookup.dirty = true;
    }

    const SearchTower *tower_at(int x, int y) const {
        if (!is_valid_pos(x, y)) {
            return nullptr;
        }
        refresh_tower_lookup();
        const int index = tower_lookup.index_by_cell[x][y];
        return index >= 0 ? &towers[static_cast<std::size_t>(index)] : nullptr;
    }

    SearchTower *tower_by_id(int tower_id) {
        for (int index = 0; index < towers.size(); ++index) {
            if (towers[index].tower_id == tower_id) {
                return &towers[index];
            }
        }
        return nullptr;
    }

    const SearchTower *tower_by_id(int tower_id) const {
        for (int index = 0; index < towers.size(); ++index) {
            if (towers[index].tower_id == tower_id) {
                return &towers[index];
            }
        }
        return nullptr;
    }

    bool emp_blocks(int x, int y) const {
        for (const auto &effect : enemy_effects) {
            if (effect.weapon_type == SuperWeaponType::EmpBlaster && effect.in_range(x, y)) {
                return true;
            }
        }
        return false;
    }

    bool ant_can_walk_to(int x, int y, int /*ant_player*/) const {
        if (!is_ant_walkable_cell(x, y)) {
            return false;
        }
        refresh_tower_lookup();
        return tower_lookup.index_by_cell[x][y] < 0;
    }

    bool ant_can_target_cell(const SearchAnt & /*ant*/, int x, int y) const {
        if (ant_can_walk_to(x, y, enemy)) {
            return true;
        }
        const SearchTower *tower = tower_at(x, y);
        return tower != nullptr && tower->alive();
    }

    FixedList<MoveCandidate, kMaxMoveCandidates> legal_move_candidates(const SearchAnt &ant) const {
        FixedList<MoveCandidate, kMaxMoveCandidates> out;
        bool allow_backtrack = ant.behavior == AntBehavior::Random || ant.behavior == AntBehavior::Bewitched;
        auto collect = [&](bool allow_reverse) {
            out.clear();
            for (int direction = 0; direction < 6; ++direction) {
                const int nx = ant.x + kOffset[ant.y & 1][direction][0];
                const int ny = ant.y + kOffset[ant.y & 1][direction][1];
                if (!allow_reverse && ant.last_move >= 0 && ant.last_move == kMoveOpposite[direction]) {
                    continue;
                }
                if (!ant_can_target_cell(ant, nx, ny)) {
                    continue;
                }
                out.push_back(MoveCandidate{direction, nx, ny});
            }
        };
        collect(allow_backtrack);
        if (out.empty() && !allow_backtrack) {
            collect(true);
        }
        if (out.empty()) {
            out.push_back(MoveCandidate{kNoMove, ant.x, ant.y});
        }
        return out;
    }

    using Grid = DoubleGrid;

    struct ReversePathPlan {
        FloatCells total_cost{};
        FloatCells damage_cost{};
    };

    struct TowerPathCache {
        int tower_id = -1;
        ReversePathPlan plan{};
    };

    struct MoveCache {
        bool static_risk_dirty = true;
        bool move_cache_dirty = true;
        unsigned char walkable_cells[kMaxValidCells]{};
        unsigned char walkable_neighbor_count[kMaxValidCells]{};
        int walkable_neighbors[kMaxValidCells][6]{};
        Grid damage_risk_field{};
        Grid control_risk_field{};
        Grid effect_pull_field{};
        Grid traffic_field{};
        IntGrid occupied_count{};
        IntGrid adjacent_count{};
        FloatCells worker_costs{};
        FloatCells combat_base_costs{};
        Grid reservations{};
        FixedList<TowerPathCache, kMaxSimTowers> tower_plans;
        IdCountMap<kMaxSimTowers> tower_claims;
    };

    struct TowerLookupCache {
        bool dirty = true;
        IntGrid index_by_cell{};
    };

    mutable MoveCache move_cache;
    mutable TowerLookupCache tower_lookup;

    double ant_progress_weight(const SearchAnt &ant) const { return ant.kind == AntKind::Combat ? 1.3 : 1.05; }
    double ant_crowding_weight(const SearchAnt &ant) const { return ant.kind == AntKind::Combat ? 0.15 : 0.4; }
    double ant_expected_damage_weight(const SearchAnt &ant) const { return ant.kind == AntKind::Combat ? 1.1 : 2.0; }
    double ant_control_risk_weight(const SearchAnt &ant) const { return ant.kind == AntKind::Combat ? 0.45 : 1.15; }
    double ant_tower_pull_weight(const SearchAnt &ant) const { return ant.kind == AntKind::Combat ? 1.75 : 0.45; }
    double ant_effect_pull_weight(const SearchAnt &ant) const { return ant.kind == AntKind::Combat ? 0.35 : 0.55; }

    double crowding_penalty(const SearchAnt &ant, int x, int y) const {
        double penalty =
            static_cast<double>(move_cache.occupied_count[x][y]) + 0.35 * static_cast<double>(move_cache.adjacent_count[x][y]);
        const int self_distance = cell_distance_fast(x, y, ant.x, ant.y);
        if (self_distance == 0) {
            penalty -= 1.0;
        } else if (self_distance == 1) {
            penalty -= 0.35;
        }
        return penalty;
    }

    double move_progress_score(const SearchAnt &ant, int x, int y, int target_x, int target_y) const {
        const int current_distance = cell_distance_fast(ant.x, ant.y, target_x, target_y);
        const int next_distance = cell_distance_fast(x, y, target_x, target_y);
        const int base_distance = geometry_cache().base_distance;

        double score = static_cast<double>(current_distance - next_distance);
        if (next_distance == current_distance) {
            score -= 0.35;
        } else if (next_distance > current_distance) {
            score -= 0.8 * static_cast<double>(next_distance - current_distance);
        }
        score += std::max(0.0, static_cast<double>(base_distance - next_distance)) * 0.18;
        return score;
    }

    double move_pheromone_score(int x, int y) const {
        return is_valid_pos(x, y) ? static_cast<double>(pheromone[x][y]) : 0.0;
    }

    void mark_risk_fields_dirty() {
        move_cache.static_risk_dirty = true;
        move_cache.move_cache_dirty = true;
    }

    void mark_move_cache_dirty() {
        move_cache.move_cache_dirty = true;
    }

    double cell_damage_hp(int x, int y) const {
        refresh_static_risk_fields();
        return move_cache.damage_risk_field[x][y] * 25.0;
    }

    double cell_control_risk(int x, int y) const {
        refresh_static_risk_fields();
        return move_cache.control_risk_field[x][y];
    }

    double cell_effect_pull(int x, int y) const {
        refresh_static_risk_fields();
        return move_cache.effect_pull_field[x][y];
    }

    Grid compute_traffic_field() const {
        Grid traffic{};
        const auto &geometry = geometry_cache();
        for (const auto &ant : ants) {
            if (!ant.alive()) {
                continue;
            }
            traffic[ant.x][ant.y] += 1.0;
            const int ant_index = cell_index_of(ant.x, ant.y);
            if (ant_index < 0) {
                continue;
            }
            for (int slot = 0; slot < move_cache.walkable_neighbor_count[ant_index]; ++slot) {
                const int neighbor_index = move_cache.walkable_neighbors[ant_index][slot];
                const int nx = geometry.cell_x[neighbor_index];
                const int ny = geometry.cell_y[neighbor_index];
                traffic[nx][ny] += 0.35;
            }
        }
        return traffic;
    }

    void refresh_crowding_fields() const {
        const auto &geometry = geometry_cache();
        for (int index = 0; index < geometry.valid_count; ++index) {
            const int x = geometry.cell_x[index];
            const int y = geometry.cell_y[index];
            move_cache.occupied_count[x][y] = 0;
            move_cache.adjacent_count[x][y] = 0;
        }
        for (const auto &ant : ants) {
            if (!ant.alive()) {
                continue;
            }
            ++move_cache.occupied_count[ant.x][ant.y];
            const int ant_index = cell_index_of(ant.x, ant.y);
            if (ant_index < 0) {
                continue;
            }
            for (int direction = 0; direction < 6; ++direction) {
                const int neighbor_index = geometry.neighbor_by_dir[ant_index][direction];
                if (neighbor_index < 0) {
                    continue;
                }
                ++move_cache.adjacent_count[geometry.cell_x[neighbor_index]][geometry.cell_y[neighbor_index]];
            }
        }
    }

    void refresh_static_risk_fields() const {
        if (!move_cache.static_risk_dirty) {
            return;
        }
        refresh_tower_lookup();
        const auto &geometry = geometry_cache();
        for (int index = 0; index < geometry.valid_count; ++index) {
            const int x = geometry.cell_x[index];
            const int y = geometry.cell_y[index];
            move_cache.walkable_cells[index] =
                static_cast<unsigned char>(is_ant_walkable_cell(x, y) && tower_lookup.index_by_cell[x][y] < 0);
            move_cache.damage_risk_field[x][y] = 0.0;
            move_cache.control_risk_field[x][y] = 0.0;
            move_cache.effect_pull_field[x][y] = 0.0;
        }
        for (int index = 0; index < geometry.valid_count; ++index) {
            int count = 0;
            for (int direction = 0; direction < 6; ++direction) {
                const int neighbor_index = geometry.neighbor_by_dir[index][direction];
                if (neighbor_index < 0 || move_cache.walkable_cells[neighbor_index] == 0) {
                    continue;
                }
                move_cache.walkable_neighbors[index][count++] = neighbor_index;
            }
            move_cache.walkable_neighbor_count[index] = static_cast<unsigned char>(count);
        }

        for (const auto &tower : towers) {
            if (!tower.alive()) {
                continue;
            }
            const int tower_index = cell_index_of(tower.x, tower.y);
            const int attack_range = std::min(tower.attack_range(), kMaxCachedRange);
            const double damage_value = static_cast<double>(tower.damage()) / 25.0;
            double control_value = 0.0;
            switch (tower.tower_type) {
            case TowerType::Ice:
                control_value = 1.0;
                break;
            case TowerType::Bewitch:
                control_value = 1.3;
                break;
            case TowerType::Pulse:
                control_value = 0.7;
                break;
            default:
                break;
            }
            for (int slot = 0; slot < geometry.range_count[tower_index][attack_range]; ++slot) {
                const int index = geometry.range_cells[tower_index][attack_range][slot];
                if (move_cache.walkable_cells[index] == 0) {
                    continue;
                }
                const int x = geometry.cell_x[index];
                const int y = geometry.cell_y[index];
                move_cache.damage_risk_field[x][y] += damage_value;
                if (control_value > 0.0) {
                    move_cache.control_risk_field[x][y] += control_value;
                }
            }
        }

        const double storm_damage = static_cast<double>(kLightningAntDamage) / 25.0;
        for (const auto &effect : my_effects) {
            if (!effect.active() || effect.weapon_type != SuperWeaponType::LightningStorm) {
                continue;
            }
            const int effect_index = cell_index_of(effect.x, effect.y);
            const int attack_range = std::min(weapon_stats(effect.weapon_type).attack_range, kMaxCachedRange);
            for (int slot = 0; slot < geometry.range_count[effect_index][attack_range]; ++slot) {
                const int index = geometry.range_cells[effect_index][attack_range][slot];
                if (move_cache.walkable_cells[index] == 0) {
                    continue;
                }
                const int x = geometry.cell_x[index];
                const int y = geometry.cell_y[index];
                move_cache.damage_risk_field[x][y] += storm_damage;
            }
        }

        for (const auto &effect : enemy_effects) {
            if (!effect.active()) {
                continue;
            }
            if (effect.weapon_type != SuperWeaponType::Deflector &&
                effect.weapon_type != SuperWeaponType::EmergencyEvasion) {
                continue;
            }
            const int effect_index = cell_index_of(effect.x, effect.y);
            const double pull = effect.weapon_type == SuperWeaponType::Deflector ? 1.0 : 1.35;
            const int attack_range = std::min(weapon_stats(effect.weapon_type).attack_range, kMaxCachedRange);
            for (int slot = 0; slot < geometry.range_count[effect_index][attack_range]; ++slot) {
                const int index = geometry.range_cells[effect_index][attack_range][slot];
                if (move_cache.walkable_cells[index] == 0) {
                    continue;
                }
                const int x = geometry.cell_x[index];
                const int y = geometry.cell_y[index];
                move_cache.effect_pull_field[x][y] += pull;
            }
        }

        move_cache.static_risk_dirty = false;
    }

    void prepare_move_cache(bool reset_reservations) const {
        refresh_static_risk_fields();
        move_cache.traffic_field = compute_traffic_field();
        refresh_crowding_fields();

        bool has_worker = false;
        bool has_combat = false;
        for (const auto &ant : ants) {
            if (!ant.alive() || ant.too_old() || ant.is_frozen) {
                continue;
            }
            if (ant.kind == AntKind::Combat) {
                has_combat = true;
            } else {
                has_worker = true;
            }
        }

        const auto [base_x, base_y] = kPlayerBases[player];
        float step_damage[kMaxValidCells]{};
        float worker_step_total[kMaxValidCells]{};
        float combat_step_total[kMaxValidCells]{};
        if (has_worker || has_combat) {
            const auto &geometry = geometry_cache();
            for (int index = 0; index < geometry.valid_count; ++index) {
                const int x = geometry.cell_x[index];
                const int y = geometry.cell_y[index];
                const float damage = move_cache.damage_risk_field[x][y] * 25.0f;
                const float control = move_cache.control_risk_field[x][y];
                const float traffic = move_cache.traffic_field[x][y];
                const float effect = move_cache.effect_pull_field[x][y];
                step_damage[index] = damage;
                if (has_worker) {
                    worker_step_total[index] =
                        std::max(0.15f, 1.0f + 0.20f * damage + 1.80f * control + 0.75f * traffic - 0.35f * effect);
                }
                if (has_combat) {
                    combat_step_total[index] =
                        std::max(0.15f, 1.0f + 0.08f * damage + 0.45f * control + 0.25f * traffic - 0.20f * effect);
                }
            }
        }
        if (has_worker) {
            FixedList<IntPair, 6> sources;
            sources.push_back(IntPair{base_x, base_y});
            const ReversePathPlan worker_plan = reverse_weighted_plan(sources, worker_step_total, step_damage);
            move_cache.worker_costs = worker_plan.total_cost;
        }

        move_cache.tower_plans.clear();
        if (has_combat) {
            for (const auto &tower : towers) {
                if (!tower.alive()) {
                    continue;
                }
                FixedList<IntPair, 6> sources;
                for (int direction = 0; direction < 6; ++direction) {
                    const int nx = tower.x + kOffset[tower.y & 1][direction][0];
                    const int ny = tower.y + kOffset[tower.y & 1][direction][1];
                    const int neighbor_index = cell_index_of(nx, ny);
                    if (neighbor_index >= 0 && move_cache.walkable_cells[neighbor_index] != 0) {
                        sources.push_back(IntPair{nx, ny});
                    }
                }
                if (sources.empty()) {
                    continue;
                }
                move_cache.tower_plans.push_back(
                    TowerPathCache{tower.tower_id, reverse_weighted_plan(sources, combat_step_total, step_damage)});
            }
        }
        if (has_combat && move_cache.tower_plans.empty()) {
            FixedList<IntPair, 6> sources;
            sources.push_back(IntPair{base_x, base_y});
            const ReversePathPlan combat_base_plan = reverse_weighted_plan(sources, combat_step_total, step_damage);
            move_cache.combat_base_costs = combat_base_plan.total_cost;
        }

        if (reset_reservations) {
            move_cache.tower_claims.clear();
            for (int x = 0; x < kMapSize; ++x) {
                for (int y = 0; y < kMapSize; ++y) {
                    move_cache.reservations[x][y] = 0.0;
                }
            }
        }
        move_cache.move_cache_dirty = false;
    }

    void clear_move_annotations() const {
        move_cache.tower_claims.clear();
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                move_cache.reservations[x][y] = 0.0;
            }
        }
    }

    void ensure_move_cache(bool reset_reservations = false) const {
        if (move_cache.move_cache_dirty) {
            prepare_move_cache(reset_reservations);
        } else if (reset_reservations) {
            clear_move_annotations();
        }
    }

    const TowerPathCache *tower_plan_for(int tower_id) const {
        for (const auto &plan : move_cache.tower_plans) {
            if (plan.tower_id == tower_id) {
                return &plan;
            }
        }
        return nullptr;
    }

    int tower_claim_count(int tower_id) const {
        return move_cache.tower_claims.get(tower_id);
    }

    void record_move_annotation(int move, int cell_x, int cell_y, int tower_id) const {
        if (move != kNoMove && cell_x >= 0 && cell_y >= 0) {
            move_cache.reservations[cell_x][cell_y] += 1.0;
        }
        if (tower_id >= 0) {
            move_cache.tower_claims.increment(tower_id);
        }
    }

    void clear_move_cache() {
        if (move_cache.move_cache_dirty) {
            return;
        }
        move_cache.move_cache_dirty = true;
        clear_move_annotations();
    }

    ReversePathPlan reverse_weighted_plan(
        const FixedList<IntPair, 6> &sources,
        const float step_total[kMaxValidCells],
        const float step_damage[kMaxValidCells]) const {
        ReversePathPlan plan;
        const float inf = std::numeric_limits<float>::infinity();
        const auto &geometry = geometry_cache();
        unsigned char visited[kMaxValidCells]{};
        ReverseHeap heap;
        for (int index = 0; index < geometry.valid_count; ++index) {
            plan.total_cost[index] = inf;
            plan.damage_cost[index] = inf;
        }
        for (const auto &[x, y] : sources) {
            const int index = cell_index_of(x, y);
            if (index < 0 || move_cache.walkable_cells[index] == 0) {
                continue;
            }
            if (plan.total_cost[index] <= 0.0f) {
                continue;
            }
            plan.total_cost[index] = 0.0f;
            plan.damage_cost[index] = 0.0f;
            heap.push(ReverseHeapNode{index, 0.0f, 0.0f});
        }

        while (!heap.empty()) {
            const ReverseHeapNode node = heap.pop();
            const int cell_index = node.cell_index;
            if (cell_index < 0 || visited[cell_index] != 0) {
                continue;
            }
            visited[cell_index] = 1;
            const float best_total = node.total;
            const float best_damage = node.damage;

            for (int slot = 0; slot < move_cache.walkable_neighbor_count[cell_index]; ++slot) {
                const int previous_index = move_cache.walkable_neighbors[cell_index][slot];
                const float next_total = best_total + step_total[cell_index];
                const float next_damage = best_damage + step_damage[cell_index];
                if (next_total + 1e-6f < plan.total_cost[previous_index] ||
                    (std::fabs(next_total - plan.total_cost[previous_index]) <= 1e-6f &&
                     next_damage + 1e-6f < plan.damage_cost[previous_index])) {
                    plan.total_cost[previous_index] = next_total;
                    plan.damage_cost[previous_index] = next_damage;
                    heap.push(ReverseHeapNode{previous_index, next_total, next_damage});
                }
            }
        }
        return plan;
    }

    double tower_attack_value(const SearchAnt &ant, const SearchTower &tower, double arrival_hp) const {
        if (arrival_hp <= 0.0) {
            return -1e18;
        }
        if (ant.kind == AntKind::Combat && arrival_hp * 2.0 < static_cast<double>(ant.max_hp())) {
            double total_damage = 0.0;
            int destroyed = 0;
            for (const auto &other : towers) {
                if (!other.alive()) {
                    continue;
                }
                if (cell_distance_fast(tower.x, tower.y, other.x, other.y) > kCombatSelfDestructRange) {
                    continue;
                }
                total_damage += std::min(kCombatSelfDestructDamage, other.hp);
                if (other.hp <= kCombatSelfDestructDamage) {
                    ++destroyed;
                }
            }
            return total_damage + static_cast<double>(destroyed) * 3.0 + 0.15 * arrival_hp;
        }
        const double direct_damage = static_cast<double>(std::min(ant_tower_attack_damage(ant), tower.hp));
        const double destroy_bonus = tower.hp <= ant_tower_attack_damage(ant) ? 3.0 : 0.0;
        return direct_damage + destroy_bonus + 0.15 * arrival_hp;
    }

    double tower_pull_score(const SearchAnt &ant, int x, int y, const SearchTower *tower_target) const {
        if (tower_target != nullptr) {
            double bonus = ant.kind == AntKind::Combat ? 8.0 : 2.75;
            if (ant.kind == AntKind::Combat && should_self_destruct(ant)) {
                bonus += 3.0;
            }
            return bonus;
        }
        if (ant.kind != AntKind::Combat) {
            return 0.0;
        }
        double best = 0.0;
        const double self_destruct_bonus = should_self_destruct(ant) ? 3.0 : 0.0;
        for (const auto &tower : towers) {
            if (!tower.alive()) {
                continue;
            }
            const double distance_score = std::max(0.0, 8.0 - static_cast<double>(cell_distance_fast(x, y, tower.x, tower.y)));
            best = std::max(best, distance_score + self_destruct_bonus);
        }
        return best;
    }

    IntPair random_bewitch_target(const SearchAnt &ant, FastRng &rng) const {
        IntPair chosen{kPlayerBases[enemy].first, kPlayerBases[enemy].second};
        int seen = 0;
        const int anchor_delta = half_plane_delta(enemy, ant.x, ant.y);
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                if (!ant_can_walk_to(x, y, enemy)) {
                    continue;
                }
                if (x == ant.x && y == ant.y) {
                    continue;
                }
                if (half_plane_delta(enemy, x, y) <= anchor_delta) {
                    ++seen;
                    if (rng.next_int(seen) == 0) {
                        chosen = IntPair{x, y};
                    }
                }
            }
        }
        return chosen;
    }

    void set_ant_behavior(SearchAnt &ant, AntBehavior behavior, int target_x = -1, int target_y = -1) {
        if (ant.control_immune() && behavior != AntBehavior::ControlFree) {
            return;
        }
        ant.behavior = behavior;
        ant.behavior_rounds = 0;
        ant.behavior_expiry = (behavior == AntBehavior::Default || behavior == AntBehavior::Random)
                                  ? 0
                                  : kBehaviorDecayTurns;
        if (behavior == AntBehavior::Bewitched) {
            ant.target_x = target_x;
            ant.target_y = target_y;
        } else {
            ant.target_x = -1;
            ant.target_y = -1;
        }
    }

    void apply_damage(SearchAnt &ant, int damage) {
        if (damage <= 0 || !ant.alive()) {
            return;
        }
        if (ant.shield > 0) {
            --ant.shield;
            if (ant.shield == 0 && ant.control_free_on_break && !ant.control_immune()) {
                ant.control_free_on_break = false;
                set_ant_behavior(ant, AntBehavior::ControlFree);
            }
            return;
        }
        if (ant.defend && damage * 2 < ant.max_hp()) {
            return;
        }
        ant.hp -= damage;
    }

    void apply_tower_hit(SearchTower &tower, SearchAnt &ant, FastRng &rng) {
        if (!ant.alive()) {
            return;
        }
        apply_damage(ant, tower.damage());
        if (!ant.alive()) {
            return;
        }
        if (tower.tower_type == TowerType::Bewitch && !ant.control_immune()) {
            int target_x = ant.target_x;
            int target_y = ant.target_y;
            if (ant_in_own_half(enemy, ant.x, ant.y)) {
                target_x = kPlayerBases[enemy].first;
                target_y = kPlayerBases[enemy].second;
            } else {
                const auto target = random_bewitch_target(ant, rng);
                target_x = target.first;
                target_y = target.second;
            }
            set_ant_behavior(ant, AntBehavior::Bewitched, target_x, target_y);
        }
    }

    const SearchAnt *tower_pick_target(const SearchTower &tower) const {
        const SearchAnt *best = nullptr;
        int best_distance = std::numeric_limits<int>::max();
        for (const auto &ant : ants) {
            if (!ant.alive()) {
                continue;
            }
            const int distance = cell_distance_fast(tower.x, tower.y, ant.x, ant.y);
            if (distance > tower.attack_range()) {
                continue;
            }
            if (distance < best_distance) {
                best_distance = distance;
                best = &ant;
            }
        }
        return best;
    }

    MoveOptionsResult evaluate_move_options(const SearchAnt &ant) const {
        const auto candidates = legal_move_candidates(ant);
        const int candidate_count = candidates.size();
        MoveOptionsResult result;
        auto danger_for_cell = [&](int nx, int ny, bool tower_target) {
            double danger =
                static_cast<double>(12 - std::min(12, cell_distance_fast(nx, ny, kPlayerBases[player].first, kPlayerBases[player].second)));
            if (tower_target) {
                danger += 8.0;
            }
            if (is_base_cell(nx, ny) && nx == kPlayerBases[player].first && ny == kPlayerBases[player].second) {
                danger += 20.0;
            }
            return danger;
        };
        if (ant.behavior == AntBehavior::Random) {
            const double uniform = 1.0 / static_cast<double>(std::max(1, candidate_count));
            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                const int direction = candidate.direction;
                const int nx = candidate.nx;
                const int ny = candidate.ny;
                result.options.push_back(MoveOption{direction, nx, ny, uniform, danger_for_cell(nx, ny, tower_at(nx, ny) != nullptr)});
            }
            return result;
        }

        double scores[kMaxMoveCandidates]{};
        double raw_scores[kMaxMoveCandidates]{};
        FixedList<IntPair, kMaxMoveCandidates> annotated_cells;
        FixedList<int, kMaxMoveCandidates> annotated_towers;

        if (ant.behavior == AntBehavior::Bewitched) {
            const int target_x = ant.target_x >= 0 ? ant.target_x : kPlayerBases[enemy].first;
            const int target_y = ant.target_y >= 0 ? ant.target_y : kPlayerBases[enemy].second;
            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                const int nx = candidate.nx;
                const int ny = candidate.ny;
                const SearchTower *tower_target = tower_at(nx, ny);
                const int eval_x = tower_target != nullptr ? ant.x : nx;
                const int eval_y = tower_target != nullptr ? ant.y : ny;
                const double progress = move_progress_score(ant, eval_x, eval_y, target_x, target_y);
                const double damage = cell_damage_hp(eval_x, eval_y);
                const double control = ant.control_immune() ? 0.0 : cell_control_risk(eval_x, eval_y);
                const double effect = cell_effect_pull(eval_x, eval_y);
                const double tower_pull = tower_pull_score(ant, eval_x, eval_y, tower_target);
                const double score = ant_progress_weight(ant) * progress -
                                     ant_crowding_weight(ant) * crowding_penalty(ant, eval_x, eval_y) -
                                     ant_expected_damage_weight(ant) * damage -
                                     ant_control_risk_weight(ant) * control +
                                     ant_pheromone_weight(ant) * move_pheromone_score(eval_x, eval_y) +
                                     ant_tower_pull_weight(ant) * tower_pull +
                                     ant_effect_pull_weight(ant) * effect + (tower_target != nullptr ? 4.0 : 0.0);
                scores[index] = score;
                raw_scores[index] = score + effect;
            }
        } else if (ant.kind == AntKind::Worker) {
            ensure_move_cache();
            const int current_index = cell_index_of(ant.x, ant.y);
            const double current_cost =
                current_index >= 0 ? static_cast<double>(move_cache.worker_costs[current_index]) : std::numeric_limits<double>::infinity();

            double best_walk_remaining = std::numeric_limits<double>::infinity();
            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                const int nx = candidate.nx;
                const int ny = candidate.ny;
                if (tower_at(nx, ny) != nullptr) {
                    continue;
                }
                const int candidate_index = cell_index_of(nx, ny);
                if (candidate_index >= 0) {
                    best_walk_remaining =
                        std::min(best_walk_remaining, static_cast<double>(move_cache.worker_costs[candidate_index]));
                }
            }
            const double reroute_gain =
                (std::isfinite(current_cost) && std::isfinite(best_walk_remaining))
                    ? std::max(0.0, current_cost - best_walk_remaining)
                    : 0.0;
            const bool blocked = !std::isfinite(best_walk_remaining) || !std::isfinite(current_cost) ||
                                 current_cost - best_walk_remaining <= 0.50;

            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                const int nx = candidate.nx;
                const int ny = candidate.ny;
                const SearchTower *tower_target = tower_at(nx, ny);
                double score = -1e18;
                if (tower_target != nullptr) {
                    score = std::isfinite(current_cost) ? -current_cost : 0.0;
                    score += 1.2 * static_cast<double>(std::min(ant_tower_attack_damage(ant), tower_target->hp));
                    if (tower_target->hp <= ant_tower_attack_damage(ant)) {
                        score += 3.0;
                    }
                    if (blocked) {
                        score += 6.0;
                    } else {
                        score -= reroute_gain;
                    }
                    score -= static_cast<double>(tower_claim_count(tower_target->tower_id));
                    score += ant_pheromone_weight(ant) * move_pheromone_score(ant.x, ant.y);
                    annotated_cells.push_back(IntPair{-1, -1});
                    annotated_towers.push_back(tower_target->tower_id);
                } else {
                    const int candidate_index = cell_index_of(nx, ny);
                    const double remaining =
                        candidate_index >= 0 ? static_cast<double>(move_cache.worker_costs[candidate_index])
                                             : std::numeric_limits<double>::infinity();
                    if (std::isfinite(remaining)) {
                        score = -remaining;
                        score -= 1.4 * move_cache.reservations[nx][ny];
                        score -= 0.25 * crowding_penalty(ant, nx, ny);
                        score += ant_pheromone_weight(ant) * move_pheromone_score(nx, ny);
                    }
                    annotated_cells.push_back(IntPair{nx, ny});
                    annotated_towers.push_back(-1);
                }
                scores[index] = score;
                raw_scores[index] = score;
            }
        } else {
            ensure_move_cache();
            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                const int nx = candidate.nx;
                const int ny = candidate.ny;
                const SearchTower *tower_target = tower_at(nx, ny);
                double score = -1e18;
                int best_tower_id = -1;
                if (tower_target != nullptr) {
                    score = tower_attack_value(ant, *tower_target, static_cast<double>(ant.hp)) + 1.5;
                    best_tower_id = tower_target->tower_id;
                    score -= 0.85 * static_cast<double>(tower_claim_count(best_tower_id));
                    score += ant_pheromone_weight(ant) * move_pheromone_score(ant.x, ant.y);
                    annotated_cells.push_back(IntPair{-1, -1});
                } else if (!move_cache.tower_plans.empty()) {
                    const int candidate_index = cell_index_of(nx, ny);
                    for (const auto &entry : move_cache.tower_plans) {
                        const SearchTower *tower = tower_by_id(entry.tower_id);
                        if (tower == nullptr) {
                            continue;
                        }
                        if (candidate_index < 0) {
                            continue;
                        }
                        const double travel_cost = static_cast<double>(entry.plan.total_cost[candidate_index]);
                        if (!std::isfinite(travel_cost)) {
                            continue;
                        }
                        const double arrival_hp = static_cast<double>(ant.hp) - static_cast<double>(entry.plan.damage_cost[candidate_index]);
                        double utility = tower_attack_value(ant, *tower, arrival_hp) - 0.90 * travel_cost;
                        utility -= 0.85 * static_cast<double>(tower_claim_count(entry.tower_id));
                        if (utility > score) {
                            score = utility;
                            best_tower_id = entry.tower_id;
                        }
                    }
                    if (std::isfinite(score)) {
                        score -= 0.45 * move_cache.reservations[nx][ny];
                        score += ant_pheromone_weight(ant) * move_pheromone_score(nx, ny);
                    }
                    annotated_cells.push_back(IntPair{nx, ny});
                } else {
                    const int candidate_index = cell_index_of(nx, ny);
                    const double remaining =
                        candidate_index >= 0 ? static_cast<double>(move_cache.combat_base_costs[candidate_index])
                                             : std::numeric_limits<double>::infinity();
                    if (std::isfinite(remaining)) {
                        score = -remaining;
                        score -= 0.45 * move_cache.reservations[nx][ny];
                        score += ant_pheromone_weight(ant) * move_pheromone_score(nx, ny);
                    }
                    annotated_cells.push_back(IntPair{nx, ny});
                }
                scores[index] = score;
                raw_scores[index] = score;
                annotated_towers.push_back(best_tower_id);
            }
        }

        const bool has_annotations = annotated_cells.size() == candidate_count && annotated_towers.size() == candidate_count;

        double max_score = -1e18;
        for (int index = 0; index < candidate_count; ++index) {
            max_score = std::max(max_score, scores[index]);
        }
        if (ant.behavior == AntBehavior::Conservative || ant.behavior == AntBehavior::ControlFree) {
            int best = 0;
            for (int index = 1; index < candidate_count; ++index) {
                if (scores[index] > scores[best] ||
                    (scores[index] == scores[best] && raw_scores[index] > raw_scores[best])) {
                    best = index;
                }
            }
            for (int index = 0; index < candidate_count; ++index) {
                const auto &candidate = candidates[index];
                const int direction = candidate.direction;
                const int nx = candidate.nx;
                const int ny = candidate.ny;
                const SearchTower *tower_target = tower_at(nx, ny);
                result.options.push_back(MoveOption{
                    direction, nx, ny, static_cast<int>(index) == best ? 1.0 : 0.0, danger_for_cell(nx, ny, tower_target != nullptr)});
                if (has_annotations) {
                    result.annotated_cells.push_back(annotated_cells[index]);
                    result.annotated_towers.push_back(annotated_towers[index]);
                }
            }
            return result;
        }

        const double temperature = ant.behavior == AntBehavior::Bewitched ? 1.5 : 1.75;
        double total = 0.0;
        for (int index = 0; index < candidate_count; ++index) {
            total += std::exp((scores[index] - max_score) / temperature);
        }
        for (int index = 0; index < candidate_count; ++index) {
            const auto &candidate = candidates[index];
            const int direction = candidate.direction;
            const int nx = candidate.nx;
            const int ny = candidate.ny;
            const double probability = total > 0.0 ? std::exp((scores[index] - max_score) / temperature) / total : 1.0;
            const SearchTower *tower_target = tower_at(nx, ny);
            result.options.push_back(MoveOption{direction, nx, ny, probability, danger_for_cell(nx, ny, tower_target != nullptr)});
            if (has_annotations) {
                result.annotated_cells.push_back(annotated_cells[index]);
                result.annotated_towers.push_back(annotated_towers[index]);
            }
        }
        int order[kMaxMoveCandidates]{};
        const int option_count = result.options.size();
        for (int index = 0; index < option_count; ++index) {
            order[index] = index;
        }
        for (int left = 0; left < option_count; ++left) {
            int best = left;
            for (int right = left + 1; right < option_count; ++right) {
                const auto &best_option = result.options[order[best]];
                const auto &candidate_option = result.options[order[right]];
                if (candidate_option.probability > best_option.probability ||
                    (candidate_option.probability == best_option.probability && candidate_option.danger > best_option.danger)) {
                    best = right;
                }
            }
            if (best != left) {
                std::swap(order[left], order[best]);
            }
        }

        MoveOptionsResult sorted;
        for (int pos = 0; pos < option_count; ++pos) {
            const int index = order[pos];
            sorted.options.push_back(result.options[index]);
            if (index < result.annotated_cells.size()) {
                sorted.annotated_cells.push_back(result.annotated_cells[index]);
            }
            if (index < result.annotated_towers.size()) {
                sorted.annotated_towers.push_back(result.annotated_towers[index]);
            }
        }

        if (sorted.options.size() > config().move_option_limit) {
            sorted.options.resize(config().move_option_limit);
            if (sorted.annotated_cells.size() > sorted.options.size()) {
                sorted.annotated_cells.resize(sorted.options.size());
            }
            if (sorted.annotated_towers.size() > sorted.options.size()) {
                sorted.annotated_towers.resize(sorted.options.size());
            }
            double sub_total = 0.0;
            for (const auto &item : sorted.options) {
                sub_total += item.probability;
            }
            if (sub_total > 0.0) {
                for (auto &item : sorted.options) {
                    item.probability /= sub_total;
                }
            }
        }
        return sorted;
    }

    FixedList<MoveOption, kMaxMoveCandidates> move_options_for(const SearchAnt &ant) const {
        return evaluate_move_options(ant).options;
    }

    int sample_move(const SearchAnt &ant, FastRng &rng, bool record_annotation = false) const {
        const auto evaluated = evaluate_move_options(ant);
        if (evaluated.options.empty()) {
            return kNoMove;
        }
        double threshold = rng.next_double();
        double cumulative = 0.0;
        int chosen_index = evaluated.options.size() - 1;
        for (int index = 0; index < evaluated.options.size(); ++index) {
            cumulative += evaluated.options[index].probability;
            if (threshold <= cumulative) {
                chosen_index = index;
                break;
            }
        }
        if (record_annotation) {
            const auto &option = evaluated.options[chosen_index];
            const int cell_x = chosen_index < evaluated.annotated_cells.size()
                                   ? evaluated.annotated_cells[chosen_index].first
                                   : -1;
            const int cell_y = chosen_index < evaluated.annotated_cells.size()
                                   ? evaluated.annotated_cells[chosen_index].second
                                   : -1;
            const int tower_id = chosen_index < evaluated.annotated_towers.size()
                                     ? evaluated.annotated_towers[chosen_index]
                                     : -1;
            record_move_annotation(option.direction, cell_x, cell_y, tower_id);
        }
        return evaluated.options[chosen_index].direction;
    }

    void record_move_annotation_for_direction(const SearchAnt &ant, int chosen_direction) const {
        const auto evaluated = evaluate_move_options(ant);
        for (int index = 0; index < evaluated.options.size(); ++index) {
            if (evaluated.options[index].direction != chosen_direction) {
                continue;
            }
            const int cell_x = index < evaluated.annotated_cells.size() ? evaluated.annotated_cells[index].first : -1;
            const int cell_y = index < evaluated.annotated_cells.size() ? evaluated.annotated_cells[index].second : -1;
            const int tower_id = index < evaluated.annotated_towers.size() ? evaluated.annotated_towers[index] : -1;
            record_move_annotation(chosen_direction, cell_x, cell_y, tower_id);
            return;
        }
    }

    int random_legal_move(const SearchAnt &ant, FastRng &rng) const {
        const auto candidates = legal_move_candidates(ant);
        return candidates[rng.next_int(candidates.size())].direction;
    }

    void attack_tower_from_ant(SearchAnt &ant, SearchTower &tower) {
        if (should_self_destruct(ant)) {
            for (auto &other : towers) {
                if (!other.alive()) {
                    continue;
                }
                if (cell_distance_fast(tower.x, tower.y, other.x, other.y) > kCombatSelfDestructRange) {
                    continue;
                }
                other.hp -= kCombatSelfDestructDamage;
            }
            ant.hp = 0;
            purge_dead_towers();
            return;
        }
        tower.hp -= ant_tower_attack_damage(ant);
        ant.last_move = kNoMove;
        purge_dead_towers();
    }

    void resolve_ant_step(SearchAnt &ant, int move) {
        if (!ant.alive()) {
            return;
        }
        if (move == kNoMove) {
            ant.last_move = kNoMove;
            return;
        }
        const int nx = ant.x + kOffset[ant.y & 1][move][0];
        const int ny = ant.y + kOffset[ant.y & 1][move][1];
        const SearchTower *target_tower = tower_at(nx, ny);
        SearchTower *tower = target_tower != nullptr ? tower_by_id(target_tower->tower_id) : nullptr;
        if (tower != nullptr) {
            attack_tower_from_ant(ant, *tower);
            return;
        }
        ant.x = nx;
        ant.y = ny;
        ant.last_move = move;
        mark_ant_trail(ant, ant.x, ant.y);
    }

    void purge_dead_towers() {
        int write_index = 0;
        for (int read_index = 0; read_index < towers.size(); ++read_index) {
            if (towers[read_index].hp <= 0) {
                continue;
            }
            if (write_index != read_index) {
                towers[write_index] = towers[read_index];
            }
            ++write_index;
        }
        if (write_index != towers.size()) {
            towers.resize(write_index);
            invalidate_tower_lookup();
            mark_risk_fields_dirty();
        }
    }

    void prepare_enemy_effects() {
        for (auto &ant : ants) {
            bool current_deflect = false;
            bool current_evasion = false;
            for (const auto &effect : enemy_effects) {
                if (!effect.active()) {
                    continue;
                }
                if (!effect.in_range(ant.x, ant.y)) {
                    continue;
                }
                if (effect.weapon_type == SuperWeaponType::Deflector) {
                    current_deflect = true;
                } else if (effect.weapon_type == SuperWeaponType::EmergencyEvasion) {
                    current_evasion = true;
                }
            }
            if (ant.defend && !current_deflect && ant.behavior != AntBehavior::ControlFree) {
                set_ant_behavior(ant, AntBehavior::ControlFree);
            }
            ant.defend = current_deflect;
            if (current_evasion) {
                ant.shield = std::max(ant.shield, 2);
                ant.control_free_on_break = ant.control_free_on_break || true;
            }
        }
    }

    void tower_attack_phase(FastRng &rng) {
        prepare_enemy_effects();

        for (const auto &effect : my_effects) {
            if (!effect.active() || effect.weapon_type != SuperWeaponType::LightningStorm) {
                continue;
            }
            for (auto &ant : ants) {
                if (effect.in_range(ant.x, ant.y)) {
                    apply_damage(ant, kLightningAntDamage);
                }
            }
        }

        for (const auto &effect : enemy_effects) {
            if (!effect.active() || effect.weapon_type != SuperWeaponType::LightningStorm) {
                continue;
            }
            if (!lightning_tower_strike_turn(effect.remaining_turns)) {
                continue;
            }
            for (auto &tower : towers) {
                if (effect.in_range(tower.x, tower.y)) {
                    tower.hp -= kLightningTowerDamage;
                }
            }
        }
        purge_dead_towers();

        for (auto &tower : towers) {
            if (!tower.alive() || emp_blocks(tower.x, tower.y)) {
                continue;
            }
            if (tower.cooldown > 0) {
                --tower.cooldown;
            }
            if (tower.cooldown > 0) {
                continue;
            }
            const SearchAnt *target_ptr = tower_pick_target(tower);
            if (target_ptr == nullptr) {
                continue;
            }
            const int target_id = target_ptr->ant_id;
            auto find_ant = [&](int ant_id) -> SearchAnt * {
                for (auto &ant : ants) {
                    if (ant.ant_id == ant_id) {
                        return &ant;
                    }
                }
                return nullptr;
            };

            if (tower.tower_type == TowerType::Mortar) {
                        SearchAnt *center = find_ant(target_id);
                if (center != nullptr) {
                    const int cx = center->x;
                    const int cy = center->y;
                    for (auto &ant : ants) {
                        if (ant.alive() && cell_distance_fast(ant.x, ant.y, cx, cy) <= tower.attack_range()) {
                            apply_tower_hit(tower, ant, rng);
                        }
                    }
                }
            } else if (tower.tower_type == TowerType::QuickPlus) {
                SearchAnt *first = find_ant(target_id);
                if (first != nullptr) {
                    apply_tower_hit(tower, *first, rng);
                }
                const SearchAnt *next_target = tower_pick_target(tower);
                if (next_target != nullptr) {
                    SearchAnt *second = find_ant(next_target->ant_id);
                    if (second != nullptr) {
                        apply_tower_hit(tower, *second, rng);
                    }
                }
            } else {
                SearchAnt *target = find_ant(target_id);
                if (target != nullptr) {
                    apply_tower_hit(tower, *target, rng);
                }
            }
            tower.cooldown = attack_cooldown_reset(tower.tower_type);
        }
    }

    void move_phase(FastRng &rng) {
        FixedList<ForcedMove, kMaxImportantAnts> empty_forced_moves;
        move_phase(rng, empty_forced_moves);
    }

    void move_phase(FastRng &rng, const FixedList<ForcedMove, kMaxImportantAnts> &forced_moves) {
        bool need_enhanced_cache = false;
        for (const auto &ant : ants) {
            if (!ant.alive() || ant.too_old() || ant.is_frozen) {
                continue;
            }
            if (ant.behavior != AntBehavior::Random && ant.behavior != AntBehavior::Bewitched) {
                need_enhanced_cache = true;
                break;
            }
        }
        if (need_enhanced_cache) {
            if (profile == nullptr) {
                ensure_move_cache(true);
            } else {
                const std::uint64_t begin_ns = profile_now_ns();
                ensure_move_cache(true);
                profile->move_cache_ns += profile_now_ns() - begin_ns;
                ++profile->move_cache_calls;
            }
        }
        auto forced_move_for = [&](int ant_id) {
            for (int index = 0; index < forced_moves.size(); ++index) {
                if (forced_moves[index].ant_id == ant_id) {
                    return forced_moves[index].direction;
                }
            }
            return kNoMove;
        };
        for (auto &ant : ants) {
            if (!ant.alive() || ant.too_old() || ant.is_frozen) {
                continue;
            }
            int move = kNoMove;
            const int forced_move = forced_move_for(ant.ant_id);
            if (forced_move != kNoMove) {
                move = forced_move;
            } else if (ant.behavior == AntBehavior::Random) {
                if (profile == nullptr) {
                    move = random_legal_move(ant, rng);
                } else {
                    const std::uint64_t begin_ns = profile_now_ns();
                    move = random_legal_move(ant, rng);
                    profile->move_random_ns += profile_now_ns() - begin_ns;
                    ++profile->move_random_calls;
                }
            } else {
                if (profile == nullptr) {
                    move = sample_move(ant, rng, true);
                } else {
                    const std::uint64_t begin_ns = profile_now_ns();
                    move = sample_move(ant, rng, true);
                    profile->move_sample_ns += profile_now_ns() - begin_ns;
                    ++profile->move_sample_calls;
                }
            }
            if (profile == nullptr) {
                resolve_ant_step(ant, move);
            } else {
                const std::uint64_t begin_ns = profile_now_ns();
                resolve_ant_step(ant, move);
                profile->move_resolve_ns += profile_now_ns() - begin_ns;
                ++profile->move_resolve_calls;
            }
        }
        if (!config().ignore_periodic_random_move &&
            need_enhanced_cache && kTeleportInterval > 0 && (round_index + 1) % kTeleportInterval == 0) {
            clear_move_cache();
        }
    }

    void teleport_phase(FastRng &rng) {
        if (config().ignore_periodic_random_move) {
            return;
        }
        if (kTeleportInterval <= 0 || (round_index + 1) % kTeleportInterval != 0) {
            return;
        }
        int eligible_ids[kMaxSimAnts]{};
        int eligible_count = 0;
        for (const auto &ant : ants) {
            if (!ant.alive() || ant.too_old() || ant.behavior == AntBehavior::ControlFree) {
                continue;
            }
            eligible_ids[eligible_count++] = ant.ant_id;
        }
        if (eligible_count <= 0) {
            return;
        }
        int teleport_count = std::max(1, static_cast<int>(std::llround(static_cast<double>(eligible_count) * kTeleportRatio)));
        if (teleport_count > eligible_count) {
            teleport_count = eligible_count;
        }
        for (int index = 0; index < teleport_count; ++index) {
            const int pick = index + rng.next_int(eligible_count - index);
            std::swap(eligible_ids[index], eligible_ids[pick]);
        }
        for (int index = 0; index < teleport_count; ++index) {
            const int ant_id = eligible_ids[index];
            for (int step = 0; step < 3; ++step) {
                SearchAnt *selected = nullptr;
                for (auto &ant : ants) {
                    if (ant.ant_id == ant_id) {
                        selected = &ant;
                        break;
                    }
                }
                if (selected == nullptr || !selected->alive() || selected->too_old()) {
                    break;
                }
                const int move = rng.next_int(3) < 2 ? random_legal_move(*selected, rng) : sample_move(*selected, rng);
                resolve_ant_step(*selected, move);
            }
        }
    }

    void manage_ants() {
        const auto [base_x, base_y] = kPlayerBases[player];
        auto update_trail = [&](const SearchAnt &ant, float delta) {
            if (profile == nullptr) {
                add_trail_pheromone(ant, delta);
                return;
            }
            const std::uint64_t begin_ns = profile_now_ns();
            add_trail_pheromone(ant, delta);
            profile->pheromone_trail_ns += profile_now_ns() - begin_ns;
        };
        int write_index = 0;
        const int original_count = ants.size();
        for (int read_index = 0; read_index < original_count; ++read_index) {
            SearchAnt &ant = ants[read_index];
            if (ant.x == base_x && ant.y == base_y && ant.alive()) {
                --base_hp;
                update_trail(ant, 10.0f);
                if (base_hp <= 0) {
                    terminal = true;
                }
                continue;
            }
            if (!ant.alive()) {
                coins += static_cast<double>(ant.kill_reward());
                update_trail(ant, -5.0f);
                continue;
            }
            if (ant.too_old()) {
                update_trail(ant, -3.0f);
                continue;
            }
            if (write_index != read_index) {
                ants[write_index] = ant;
            }
            ++write_index;
        }
        ants.resize(write_index);
    }

    void spawn_enemy_ant(FastRng &rng) {
        Base enemy_base;
        enemy_base.player = enemy;
        enemy_base.generation_level = enemy_generation_level;
        enemy_base.ant_level = enemy_ant_level;
        if (!enemy_base.should_spawn(round_index)) {
            return;
        }
        SearchAnt ant;
        ant.ant_id = next_ant_id++;
        ant.x = kPlayerBases[enemy].first;
        ant.y = kPlayerBases[enemy].second;
        ant.level = enemy_ant_level;
        ant.hp = ant_max_hp(enemy_ant_level);
        ant.age = 0;
        ant.last_move = kNoMove;
        const double roll = rng.next_double();
        if (roll < 0.40) {
            ant.behavior = AntBehavior::Default;
            ant.kind = AntKind::Worker;
            ant.behavior_expiry = 0;
        } else if (roll < 0.75) {
            ant.behavior = AntBehavior::Conservative;
            ant.kind = AntKind::Worker;
            ant.behavior_expiry = kBehaviorDecayTurns;
        } else if (roll < 0.85) {
            ant.behavior = AntBehavior::Random;
            ant.kind = AntKind::Worker;
            ant.behavior_expiry = 0;
        } else {
            ant.behavior = AntBehavior::Default;
            ant.kind = AntKind::Combat;
            ant.hp = 30;
            ant.shield = 3;
            ant.control_free_on_break = true;
            ant.behavior_expiry = 0;
        }
        mark_ant_trail(ant, ant.x, ant.y);
        ants.push_back(ant);
    }

    void increase_ant_age() {
        for (auto &ant : ants) {
            ++ant.age;
            ++ant.behavior_rounds;
            if (ant.behavior == AntBehavior::Random && ant.behavior_rounds >= kBehaviorDecayTurns) {
                set_ant_behavior(ant, AntBehavior::Default);
            } else if (ant.behavior == AntBehavior::Bewitched && ant.reached_target()) {
                set_ant_behavior(ant, AntBehavior::Default);
            } else if (ant.behavior_expiry > 0) {
                --ant.behavior_expiry;
                if (ant.behavior != AntBehavior::Default && ant.behavior != AntBehavior::Random && ant.behavior_expiry <= 0) {
                    set_ant_behavior(ant, AntBehavior::Default);
                }
            }
        }
    }

    bool drift_effects(FastRng &rng, FixedList<SearchEffect, kMaxSimEffects> &effects) {
        bool changed = false;
        for (auto &effect : effects) {
            if (!effect.active()) {
                continue;
            }
            if (effect.weapon_type != SuperWeaponType::LightningStorm && effect.weapon_type != SuperWeaponType::EmpBlaster) {
                continue;
            }
            IntPair cells[7]{};
            int cell_count = 0;
            cells[cell_count++] = IntPair{effect.x, effect.y};
            for (int direction = 0; direction < 6; ++direction) {
                const int nx = effect.x + kOffset[effect.y & 1][direction][0];
                const int ny = effect.y + kOffset[effect.y & 1][direction][1];
                if (is_valid_pos(nx, ny)) {
                    cells[cell_count++] = IntPair{nx, ny};
                }
            }
            const IntPair &selected = cells[rng.next_int(cell_count)];
            changed = changed || selected.first != effect.x || selected.second != effect.y;
            effect.x = selected.first;
            effect.y = selected.second;
        }
        return changed;
    }

    void update_effects(FastRng &rng) {
        bool static_risk_changed = false;
        static_risk_changed = drift_effects(rng, my_effects) || static_risk_changed;
        static_risk_changed = drift_effects(rng, enemy_effects) || static_risk_changed;
        if (lightning_cooldown > 0) {
            --lightning_cooldown;
        }
        auto decay = [](FixedList<SearchEffect, kMaxSimEffects> &effects) {
            int write_index = 0;
            bool expired = false;
            for (int read_index = 0; read_index < effects.size(); ++read_index) {
                SearchEffect effect = effects[read_index];
                if (effect.remaining_turns > 0) {
                    --effect.remaining_turns;
                }
                if (effect.remaining_turns <= 0) {
                    expired = true;
                    continue;
                }
                effects[write_index++] = effect;
            }
            effects.resize(write_index);
            return expired;
        };
        static_risk_changed = decay(my_effects) || static_risk_changed;
        static_risk_changed = decay(enemy_effects) || static_risk_changed;
        if (static_risk_changed) {
            mark_risk_fields_dirty();
        } else {
            mark_move_cache_dirty();
        }
    }

    void update_income() {
        if ((round_index + 1) % kBasicIncomeInterval == 0) {
            coins += static_cast<double>(kBasicIncome);
        }
    }

    void decay_pheromone() {
        const auto &geometry = geometry_cache();
        for (int index = 0; index < geometry.valid_count; ++index) {
            const int x = geometry.cell_x[index];
            const int y = geometry.cell_y[index];
            const int scaled = static_cast<int>(pheromone[x][y] * 10000.0f + 0.5f);
            const int decayed = std::max(0, (97 * scaled + 3000 + 50) / 100);
            pheromone[x][y] = static_cast<float>(decayed) / 10000.0f;
        }
    }

    void add_trail_pheromone(const SearchAnt &ant, float delta) {
        if (delta == 0.0f) {
            return;
        }
        const auto &geometry = geometry_cache();
        for (int index = 0; index < geometry.valid_count; ++index) {
            const int bit_index = geometry.cell_x[index] * kMapSize + geometry.cell_y[index];
            if ((ant.trail_mask[bit_index / 64] & (1ULL << (bit_index % 64))) == 0ULL) {
                continue;
            }
            float &value = pheromone[geometry.cell_x[index]][geometry.cell_y[index]];
            value = std::max(0.0f, value + delta);
        }
    }

    void simulate_round(FastRng &rng) {
        FixedList<ForcedMove, kMaxImportantAnts> empty_forced_moves;
        simulate_round(rng, empty_forced_moves);
    }

    void simulate_round(FastRng &rng, const FixedList<ForcedMove, kMaxImportantAnts> &forced_moves) {
        if (terminal) {
            return;
        }
        if (profile == nullptr) {
            tower_attack_phase(rng);
            move_phase(rng, forced_moves);
            teleport_phase(rng);
            decay_pheromone();
            manage_ants();
            if (!ignore_enemy_spawns) {
                spawn_enemy_ant(rng);
            }
            increase_ant_age();
            update_income();
            update_effects(rng);
        } else {
            auto measure = [&](std::uint64_t &accumulator, auto &&fn) {
                const std::uint64_t begin_ns = profile_now_ns();
                fn();
                accumulator += profile_now_ns() - begin_ns;
            };
            measure(profile->tower_attack_ns, [&]() { tower_attack_phase(rng); });
            measure(profile->move_ns, [&]() { move_phase(rng, forced_moves); });
            measure(profile->teleport_ns, [&]() { teleport_phase(rng); });
            measure(profile->pheromone_ns, [&]() { decay_pheromone(); });
            measure(profile->manage_ns, [&]() { manage_ants(); });
            if (!ignore_enemy_spawns) {
                measure(profile->spawn_ns, [&]() { spawn_enemy_ant(rng); });
            }
            measure(profile->age_ns, [&]() { increase_ant_age(); });
            measure(profile->income_ns, [&]() { update_income(); });
            measure(profile->effects_ns, [&]() { update_effects(rng); });
            ++profile->rounds;
        }
        ++round_index;
        if (base_hp <= 0) {
            terminal = true;
        }
    }

    bool can_apply_operation(const Operation &operation, int blocked_x = -1, int blocked_y = -1, int blocked_tower_id = -1) const {
        if (blocked_tower_id >= 0) {
            if ((operation.op_type == OperationType::UpgradeTower || operation.op_type == OperationType::DowngradeTower) &&
                operation.arg0 == blocked_tower_id) {
                return false;
            }
        }
        if (blocked_x >= 0 && blocked_y >= 0) {
            if (operation.op_type == OperationType::BuildTower && operation.arg0 == blocked_x && operation.arg1 == blocked_y) {
                return false;
            }
            const SearchTower *tower = tower_by_id(operation.arg0);
            if (tower != nullptr && tower->x == blocked_x && tower->y == blocked_y &&
                (operation.op_type == OperationType::UpgradeTower || operation.op_type == OperationType::DowngradeTower)) {
                return false;
            }
        }

        switch (operation.op_type) {
        case OperationType::BuildTower:
            if (!is_highland(player, operation.arg0, operation.arg1) || is_base_cell(operation.arg0, operation.arg1)) {
                return false;
            }
            if (tower_at(operation.arg0, operation.arg1) != nullptr || emp_blocks(operation.arg0, operation.arg1)) {
                return false;
            }
            return coins + 1e-9 >= static_cast<double>(tower_build_cost_for_count(static_cast<int>(towers.size())));
        case OperationType::UpgradeTower: {
            const SearchTower *tower = tower_by_id(operation.arg0);
            if (tower == nullptr || emp_blocks(tower->x, tower->y)) {
                return false;
            }
            const Tower current{tower->tower_id, player, tower->x, tower->y, tower->tower_type, tower->cooldown, tower->hp};
            const TowerType target = static_cast<TowerType>(operation.arg1);
            if (!current.is_upgrade_type_valid(target)) {
                return false;
            }
            return coins + 1e-9 >= static_cast<double>(upgrade_tower_cost(target));
        }
        case OperationType::DowngradeTower: {
            const SearchTower *tower = tower_by_id(operation.arg0);
            return tower != nullptr && !emp_blocks(tower->x, tower->y);
        }
        case OperationType::UseLightningStorm:
            return is_valid_pos(operation.arg0, operation.arg1) && lightning_cooldown <= 0 &&
                   coins + 1e-9 >= static_cast<double>(weapon_stats(SuperWeaponType::LightningStorm).cost);
        default:
            return false;
        }
    }

    bool apply_operation(const Operation &operation) {
        if (!can_apply_operation(operation)) {
            return false;
        }
        switch (operation.op_type) {
        case OperationType::BuildTower:
            coins -= static_cast<double>(tower_build_cost_for_count(static_cast<int>(towers.size())));
            towers.push_back(SearchTower{next_tower_id++, operation.arg0, operation.arg1, TowerType::Basic, 10, 2});
            invalidate_tower_lookup();
            mark_risk_fields_dirty();
            return true;
        case OperationType::UpgradeTower: {
            SearchTower *tower = tower_by_id(operation.arg0);
            if (tower == nullptr) {
                return false;
            }
            const TowerType target = static_cast<TowerType>(operation.arg1);
            coins -= static_cast<double>(upgrade_tower_cost(target));
            tower->tower_type = target;
            tower->hp = tower_stats(target).max_hp;
            tower->cooldown = attack_cooldown_reset(target);
            mark_risk_fields_dirty();
            return true;
        }
        case OperationType::DowngradeTower: {
            SearchTower *tower = tower_by_id(operation.arg0);
            if (tower == nullptr) {
                return false;
            }
            if (tower->tower_type == TowerType::Basic) {
                coins += static_cast<double>(exact_destroy_tower_income(
                    static_cast<int>(towers.size()), tower->hp, tower->max_hp()));
                for (int index = 0; index < towers.size(); ++index) {
                    if (towers[index].tower_id == operation.arg0) {
                        towers.erase_at(index);
                        break;
                    }
                }
                invalidate_tower_lookup();
                mark_risk_fields_dirty();
                return true;
            }
            coins += static_cast<double>(
                exact_downgrade_tower_income(tower->tower_type, tower->hp, tower->max_hp()));
            const int previous_max = tower->max_hp();
            const int previous_hp = std::max(0, tower->hp);
            tower->tower_type = downgrade_target_type(tower->tower_type);
            const int downgraded_max = tower_stats(tower->tower_type).max_hp;
            tower->hp = previous_max > 0 ? std::max(1, (downgraded_max * previous_hp + previous_max - 1) / previous_max) : downgraded_max;
            tower->cooldown = attack_cooldown_reset(tower->tower_type);
            mark_risk_fields_dirty();
            return true;
        }
        case OperationType::UseLightningStorm:
            coins -= static_cast<double>(weapon_stats(SuperWeaponType::LightningStorm).cost);
            lightning_cooldown = weapon_stats(SuperWeaponType::LightningStorm).cooldown;
            my_effects.push_back(SearchEffect{SuperWeaponType::LightningStorm, operation.arg0, operation.arg1,
                                             weapon_stats(SuperWeaponType::LightningStorm).duration});
            mark_risk_fields_dirty();
            return true;
        default:
            return false;
        }
    }
};

inline DefenseSimulator make_defense_simulator(const PublicState &state, const NativeSimulator *simulator, int player) {
    DefenseSimulator sim;
    sim.player = player;
    sim.enemy = 1 - player;
    sim.round_index = state.round_index;
    sim.coins = static_cast<double>(state.coins[player]);
    sim.base_hp = state.bases[player].hp;
    sim.enemy_generation_level = state.bases[sim.enemy].generation_level;
    sim.enemy_ant_level = state.bases[sim.enemy].ant_level;
    sim.next_ant_id = state.next_ant_id;
    sim.next_tower_id = state.next_tower_id;
    sim.lightning_cooldown = state.weapon_cooldowns[player][static_cast<int>(SuperWeaponType::LightningStorm)];

    const std::vector<NativeAntHiddenState> hidden_rows =
        simulator != nullptr ? simulator->ant_hidden_states() : std::vector<NativeAntHiddenState>{};
    if (simulator != nullptr) {
        const auto native_pheromone = simulator->pheromone_for_player(sim.enemy);
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                sim.pheromone[x][y] = static_cast<float>(native_pheromone[x][y]);
            }
        }
    }

    for (const auto &tower : state.towers) {
        if (tower.player != player) {
            continue;
        }
        sim.towers.push_back(SearchTower{tower.tower_id, tower.x, tower.y, tower.tower_type, tower.hp, tower.cooldown});
    }
    for (const auto &ant : state.ants) {
        if (ant.player != sim.enemy || !ant.is_alive()) {
            continue;
        }
        SearchAnt item;
        item.ant_id = ant.ant_id;
        item.x = ant.x;
        item.y = ant.y;
        item.hp = ant.hp;
        item.level = ant.level;
        item.age = ant.age;
        item.last_move = ant.last_move;
        item.behavior = ant.behavior;
        item.kind = ant.kind;
        const NativeAntHiddenState *hidden = nullptr;
        for (const auto &row : hidden_rows) {
            if (row.ant_id == ant.ant_id) {
                hidden = &row;
                break;
            }
        }
        if (hidden != nullptr) {
            if (item.last_move < 0) {
                item.last_move = hidden->last_move;
            }
            item.shield = hidden->shield;
            item.defend = hidden->defend;
            item.control_free_on_break = hidden->evasion_control_free_on_break;
            item.is_frozen = hidden->is_frozen;
            item.behavior_rounds = hidden->behavior_rounds;
            item.behavior_expiry = hidden->behavior_expiry;
            item.target_x = hidden->target_x;
            item.target_y = hidden->target_y;
            for (int word = 0; word < kTrailMaskWords; ++word) {
                item.trail_mask[word] = hidden->trail_mask[static_cast<std::size_t>(word)];
            }
        } else {
            item.shield = 0;
            item.defend = false;
            item.control_free_on_break = false;
            item.is_frozen = ant.status == AntStatus::Frozen;
            item.behavior_rounds = 0;
            item.behavior_expiry =
                (ant.behavior == AntBehavior::Conservative || ant.behavior == AntBehavior::Bewitched || ant.behavior == AntBehavior::ControlFree)
                    ? kBehaviorDecayTurns
                    : 0;
        }
        mark_ant_trail(item, item.x, item.y);
        sim.ants.push_back(item);
    }
    for (const auto &effect : state.active_effects) {
        if (effect.player == player) {
            if (effect.weapon_type == SuperWeaponType::LightningStorm) {
                sim.my_effects.push_back(SearchEffect{effect.weapon_type, effect.x, effect.y, effect.remaining_turns});
            }
        } else {
            sim.enemy_effects.push_back(SearchEffect{effect.weapon_type, effect.x, effect.y, effect.remaining_turns});
        }
    }
    return sim;
}

inline double ant_threat_score(const DefenseSimulator &sim, const SearchAnt &ant) {
    const auto &cfg = config();
    const auto [base_x, base_y] = kPlayerBases[sim.player];
    const int base_distance = cell_distance_fast(ant.x, ant.y, base_x, base_y);
    const double hp_ratio = static_cast<double>(std::max(ant.hp, 0)) / std::max(1, ant.max_hp());
    const double behavior_scale = behavior_threat_scale(ant.behavior);
    double threat = cfg.base_ant_threat_cap * ant_base_distance_factor(base_distance) * hp_ratio * behavior_scale;

    if (ant.kind == AntKind::Combat) {
        int alive_tower_count = 0;
        for (const auto &tower : sim.towers) {
            if (tower.alive()) {
                ++alive_tower_count;
            }
        }
        static constexpr double kTowerRiskByDistance[6] = {0.0, 1.0, 0.60, 0.35, 0.20, 0.10};
        for (const auto &tower : sim.towers) {
            const int distance = cell_distance_fast(ant.x, ant.y, tower.x, tower.y);
            if (distance > 5) {
                continue;
            }
            threat += tower_estimated_salvage_value(tower, alive_tower_count) * cfg.combat_tower_threat_coin_ratio *
                      cfg.money_weight * kTowerRiskByDistance[distance] * hp_ratio * behavior_scale;
        }
    }
    return threat;
}

inline TerminalEvaluationBreakdown terminal_evaluation_breakdown(const DefenseSimulator &sim) {
    const auto &cfg = config();
    TerminalEvaluationBreakdown breakdown;
    breakdown.base_hp_raw = static_cast<double>(sim.base_hp);
    breakdown.base_hp_score = breakdown.base_hp_raw * cfg.base_hp_weight;
    breakdown.tower_value_raw = tower_full_salvage_value(sim.towers);
    for (const auto &tower : sim.towers) {
        if (!tower.alive()) {
            continue;
        }
        const double hp_ratio = static_cast<double>(std::max(tower.hp, 0)) / std::max(1, tower.max_hp());
        breakdown.tower_bonus_score += tower_type_bonus(tower.tower_type) * hp_ratio;
        breakdown.tower_bonus_score += tower_position_bonus(sim.player, tower.x, tower.y) * hp_ratio;
    }
    for (const auto &ant : sim.ants) {
        if (!ant.alive()) {
            continue;
        }
        breakdown.ant_threat_raw += ant_threat_score(sim, ant);
    }
    breakdown.tower_value_score = breakdown.tower_value_raw * cfg.tower_value_weight;
    breakdown.ant_threat_score = -breakdown.ant_threat_raw * cfg.ant_threat_weight;
    breakdown.money_raw = sim.coins;
    breakdown.money_score = breakdown.money_raw * cfg.money_weight;
    breakdown.total = breakdown.base_hp_score + breakdown.tower_value_score + breakdown.tower_bonus_score +
                      breakdown.ant_threat_score + breakdown.money_score;
    return breakdown;
}

inline double terminal_evaluation(const DefenseSimulator &sim) {
    return terminal_evaluation_breakdown(sim).total;
}

inline double ant_selection_threat(const DefenseSimulator &sim, const SearchAnt &ant) {
    return ant_threat_score(sim, ant);
}

inline FixedList<const SearchAnt *, kMaxImportantAnts> important_ants(const DefenseSimulator &sim) {
    FixedList<const SearchAnt *, kMaxImportantAnts> ordered;
    const int limit = std::min(config().important_ant_limit, kMaxImportantAnts);
    for (const auto &ant : sim.ants) {
        if (!ant.alive()) {
            continue;
        }
        const double current_threat = ant_selection_threat(sim, ant);
        if (ordered.size() < limit) {
            ordered.push_back(&ant);
        } else {
            int worst = 0;
            for (int index = 1; index < ordered.size(); ++index) {
                if (ant_selection_threat(sim, *ordered[index]) < ant_selection_threat(sim, *ordered[worst])) {
                    worst = index;
                }
            }
            if (current_threat <= ant_selection_threat(sim, *ordered[worst])) {
                continue;
            }
            ordered[worst] = &ant;
        }
        for (int left = 0; left < ordered.size(); ++left) {
            int best = left;
            for (int right = left + 1; right < ordered.size(); ++right) {
                if (ant_selection_threat(sim, *ordered[right]) > ant_selection_threat(sim, *ordered[best])) {
                    best = right;
                }
            }
            if (best != left) {
                std::swap(ordered[left], ordered[best]);
            }
        }
    }
    return ordered;
}

inline std::vector<ComboRolloutSpec> rollout_combos_for(const DefenseSimulator &sim) {
    const auto key_ants = important_ants(sim);
    if (key_ants.empty()) {
        return {ComboRolloutSpec{}};
    }

    FixedList<MoveOption, kMaxMoveCandidates> options[kMaxImportantAnts]{};
    for (int index = 0; index < key_ants.size(); ++index) {
        const SearchAnt *ant = key_ants[index];
        options[index] = sim.move_options_for(*ant);
        if (options[index].empty()) {
            options[index].push_back(MoveOption{kNoMove, ant->x, ant->y, 1.0, 0.0});
        }
    }

    std::vector<ComboRolloutSpec> combos;
    FixedList<ForcedMove, kMaxImportantAnts> forced;
    auto dfs = [&](auto &&self, int index, double probability, double danger) -> void {
        if (index >= key_ants.size()) {
            combos.push_back(ComboRolloutSpec{forced, probability, danger, 1});
            return;
        }
        for (const auto &option : options[index]) {
            forced.push_back(ForcedMove{key_ants[index]->ant_id, option.direction});
            self(self, index + 1, probability * option.probability,
                 danger + option.danger * ant_selection_threat(sim, *key_ants[index]));
            forced.pop_back();
        }
    };
    dfs(dfs, 0, 1.0, 0.0);

    if (combos.empty()) {
        return {ComboRolloutSpec{}};
    }

    double probability_sum = 0.0;
    for (const auto &combo : combos) {
        probability_sum += combo.probability;
    }
    if (probability_sum <= 0.0) {
        probability_sum = 1.0;
    }
    for (auto &combo : combos) {
        combo.probability /= probability_sum;
    }

    int remaining = config().defense_rollouts;
    std::vector<double> remainders(combos.size(), 0.0);
    for (std::size_t index = 0; index < combos.size(); ++index) {
        const double exact = combos[index].probability * static_cast<double>(config().defense_rollouts);
        combos[index].samples = std::max(1, static_cast<int>(std::floor(exact)));
        remainders[index] = exact - std::floor(exact);
        remaining -= combos[index].samples;
    }
    while (remaining > 0) {
        std::size_t best_index = 0;
        for (std::size_t index = 1; index < combos.size(); ++index) {
            if (remainders[index] > remainders[best_index]) {
                best_index = index;
            }
        }
        ++combos[best_index].samples;
        remainders[best_index] = 0.0;
        --remaining;
    }
    while (remaining < 0) {
        std::size_t worst_index = combos.size();
        double worst_remainder = 1e18;
        for (std::size_t index = 0; index < combos.size(); ++index) {
            if (combos[index].samples <= 1) {
                continue;
            }
            if (remainders[index] < worst_remainder) {
                worst_remainder = remainders[index];
                worst_index = index;
            }
        }
        if (worst_index == combos.size()) {
            break;
        }
        --combos[worst_index].samples;
        ++remaining;
    }
    return combos;
}

inline OffensiveExpectation compute_offense_expectation(const PublicState &state, int player) {
    OffensiveExpectation out;
    if (config().offense_rollouts <= 0) {
        (void)state;
        (void)player;
        return out;
    }
    bool has_live_ant = false;
    for (const auto &ant : state.ants) {
        if (ant.player == player && ant.is_alive()) {
            has_live_ant = true;
            break;
        }
    }
    if (!has_live_ant) {
        for (int step = 0; step < config().offense_horizon; ++step) {
            if ((state.round_index + step + 1) % kBasicIncomeInterval == 0) {
                out.money_gain_by_round[static_cast<std::size_t>(step)] += static_cast<double>(kBasicIncome);
            }
        }
        return out;
    }
    const auto round_state = state.to_public_round_state();
    for (int rollout = 0; rollout < config().offense_rollouts; ++rollout) {
        NativeSimulator simulator(mix_seed(state.seed, static_cast<std::uint64_t>(0x85ebca6bU + rollout)),
                                  state.movement_policy, state.cold_handle_rule_illegal);
        simulator.sync_public_round_state(round_state);
        double previous = static_cast<double>(round_state.coins[player]);
        for (int step = 0; step < config().offense_horizon; ++step) {
            simulator.advance_round_without_base_spawns();
            const auto next_round = simulator.to_public_round_state();
            const double current = static_cast<double>(next_round.coins[player]);
            out.money_gain_by_round[static_cast<std::size_t>(step)] += current - previous;
            previous = current;
        }
    }
    for (double &value : out.money_gain_by_round) {
        value /= static_cast<double>(config().offense_rollouts);
    }
    return out;
}

inline double build_slot_score(const PublicState &state, int player, int x, int y) {
    (void)state;
    const int code = old_ai_position_code_at(player, x, y);
    const int bounded_code = code >= 0 ? code : kPositionCodeCount;
    return tower_position_bonus(player, x, y) +
           std::max(0.0, static_cast<double>(kPositionCodeCount - bounded_code)) * 0.001;
}

inline std::vector<OperationCandidate> generate_build_candidates(const PublicState &state, int player) {
    std::vector<OperationCandidate> out;
    const auto &slots = strategic_slot_order()[player];
    for (const auto &[x, y] : slots) {
        Operation operation(OperationType::BuildTower, x, y);
        if (!state.can_apply_operation(player, operation)) {
            continue;
        }
        out.push_back(OperationCandidate{operation, "build", build_slot_score(state, player, x, y)});
    }
    std::sort(out.begin(), out.end(), [](const OperationCandidate &lhs, const OperationCandidate &rhs) {
        return lhs.heuristic > rhs.heuristic;
    });
    return out;
}

inline double upgrade_score(const PublicState &state, int player, const Tower &tower, TowerType target) {
    (void)state;
    return tower_position_bonus(player, tower.x, tower.y) + tower_type_bonus(target);
}

inline std::vector<OperationCandidate> generate_upgrade_candidates(const PublicState &state, int player) {
    std::vector<OperationCandidate> out;
    for (const auto &tower : state.towers) {
        if (tower.player != player) {
            continue;
        }
        std::vector<TowerType> targets;
        if (tower.tower_type == TowerType::Basic) {
            targets = {TowerType::Heavy, TowerType::Mortar, TowerType::Quick};
        } else if (tower.tower_type == TowerType::Heavy) {
            targets = {TowerType::Bewitch};
        } else if (tower.tower_type == TowerType::Mortar) {
            targets = {TowerType::Pulse};
        } else if (tower.tower_type == TowerType::Quick) {
            targets = {TowerType::QuickPlus, TowerType::Sniper};
        }
        for (TowerType target : targets) {
            Operation operation(OperationType::UpgradeTower, tower.tower_id, static_cast<int>(target));
            if (!state.can_apply_operation(player, operation)) {
                continue;
            }
            out.push_back(OperationCandidate{operation, "upgrade", upgrade_score(state, player, tower, target)});
        }
    }
    std::sort(out.begin(), out.end(), [](const OperationCandidate &lhs, const OperationCandidate &rhs) {
        return lhs.heuristic > rhs.heuristic;
    });
    return out;
}

inline double downgrade_score(const PublicState &state, int player, const Tower &tower) {
    const Operation operation(OperationType::DowngradeTower, tower.tower_id);
    const double refund = static_cast<double>(state.operation_income(player, operation));
    return -(tower_position_bonus(player, tower.x, tower.y) + tower_type_bonus(tower.tower_type) + refund * 0.1);
}

inline std::vector<OperationCandidate> generate_downgrade_candidates(const PublicState &state, int player) {
    std::vector<OperationCandidate> out;
    for (const auto &tower : state.towers) {
        if (tower.player != player) {
            continue;
        }
        Operation operation(OperationType::DowngradeTower, tower.tower_id);
        if (!state.can_apply_operation(player, operation)) {
            continue;
        }
        out.push_back(OperationCandidate{operation, "downgrade", downgrade_score(state, player, tower)});
    }
    std::sort(out.begin(), out.end(), [](const OperationCandidate &lhs, const OperationCandidate &rhs) {
        return lhs.heuristic > rhs.heuristic;
    });
    return out;
}

inline std::vector<OperationCandidate> top_generic_candidates(const PublicState &state, int player) {
    std::vector<OperationCandidate> candidates;
    auto append = [&](const std::vector<OperationCandidate> &items) {
        candidates.insert(candidates.end(), items.begin(), items.end());
    };
    append(generate_build_candidates(state, player));
    append(generate_upgrade_candidates(state, player));
    append(generate_downgrade_candidates(state, player));
    std::sort(candidates.begin(), candidates.end(), [](const OperationCandidate &lhs, const OperationCandidate &rhs) {
        return lhs.heuristic > rhs.heuristic;
    });
    std::unordered_set<std::string> seen;
    std::vector<OperationCandidate> unique;
    unique.reserve(candidates.size());
    for (const auto &candidate : candidates) {
        if (seen.emplace(op_key(candidate.operation)).second) {
            unique.push_back(candidate);
        }
    }
    return unique;
}

inline std::vector<SearchPlan> generate_plans(const PublicState &state, int player) {
    std::vector<SearchPlan> plans;
    plans.push_back(SearchPlan{"hold", false, {}, false, {}, -1, -1, -1, 0.0, 0.0});

    const auto first_candidates = top_generic_candidates(state, player);
    for (const auto &candidate : first_candidates) {
        SearchPlan plan;
        plan.name = candidate.label + "_1";
        plan.has_first = true;
        plan.first = candidate.operation;
        plan.heuristic = candidate.heuristic;
        if (candidate.operation.op_type == OperationType::DowngradeTower) {
            const Tower *tower = state.tower_by_id(candidate.operation.arg0);
            if (tower != nullptr) {
                plan.blocked_x = tower->x;
                plan.blocked_y = tower->y;
                plan.blocked_tower_id = tower->tower_id;
            }
        }
        plans.push_back(plan);
    }

    for (const auto &candidate : first_candidates) {
        SearchPlan base_plan;
        base_plan.has_first = true;
        base_plan.first = candidate.operation;
        base_plan.heuristic = candidate.heuristic;
        if (candidate.operation.op_type == OperationType::BuildTower) {
            if (!is_two_step_core_slot(player, candidate.operation.arg0, candidate.operation.arg1)) {
                continue;
            }
            PublicState projected = state.clone();
            projected.apply_operation_list(player, std::vector<Operation>{candidate.operation});
            const Tower *tower = projected.tower_at(candidate.operation.arg0, candidate.operation.arg1);
            if (tower == nullptr) {
                continue;
            }
            for (TowerType target : {TowerType::Heavy, TowerType::Mortar, TowerType::Quick}) {
                Operation second(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(target));
                SearchPlan plan = base_plan;
                plan.name = "build_then_upgrade";
                plan.has_second = true;
                plan.second = second;
                plan.heuristic += upgrade_score(projected, player, *tower, target) * 0.8;
                plans.push_back(plan);
            }
            continue;
        }
        if (candidate.operation.op_type == OperationType::UseLightningStorm ||
            candidate.operation.op_type == OperationType::UpgradeTower) {
            continue;
        }
        PublicState projected = state.clone();
        projected.apply_operation_list(player, std::vector<Operation>{candidate.operation});
        const auto followups = top_generic_candidates(projected, player);
        int used = 0;
        SearchPlan seed_plan = base_plan;
        if (candidate.operation.op_type == OperationType::DowngradeTower) {
            const Tower *tower = state.tower_by_id(candidate.operation.arg0);
            if (tower != nullptr) {
                seed_plan.blocked_x = tower->x;
                seed_plan.blocked_y = tower->y;
                seed_plan.blocked_tower_id = tower->tower_id;
            }
        }
        for (const auto &followup : followups) {
            if (followup.operation.op_type == OperationType::UpgradeTower &&
                followup.operation.arg0 == seed_plan.blocked_tower_id) {
                continue;
            }
            if (followup.operation.op_type == OperationType::DowngradeTower &&
                followup.operation.arg0 == seed_plan.blocked_tower_id) {
                continue;
            }
            if (followup.operation.op_type == OperationType::BuildTower &&
                followup.operation.arg0 == seed_plan.blocked_x && followup.operation.arg1 == seed_plan.blocked_y) {
                continue;
            }
            if (candidate.operation.op_type == OperationType::DowngradeTower &&
                followup.operation.op_type == OperationType::BuildTower &&
                !is_two_step_core_slot(player, followup.operation.arg0, followup.operation.arg1)) {
                continue;
            }
            SearchPlan plan = seed_plan;
            plan.name = candidate.label + "_followup";
            plan.has_second = true;
            plan.second = followup.operation;
            plan.heuristic += followup.heuristic * 0.65;
            plans.push_back(plan);
            ++used;
        }
    }

    for (auto &plan : plans) {
        plan.penalty = operation_penalty_breakdown(state, player, plan).total;
        plan.heuristic -= plan.penalty;
    }
    std::sort(plans.begin(), plans.end(), [](const SearchPlan &lhs, const SearchPlan &rhs) {
        return lhs.heuristic > rhs.heuristic;
    });
    return plans;
}

inline TerminalEvaluationBreakdown simulate_combo(
    const DefenseSimulator &root,
    const SearchPlan &plan,
    const ComboRolloutSpec &combo,
    const OffensiveExpectation &offense,
    std::uint64_t seed) {
    DefenseSimulator sim = root.clone();
    if (plan.has_first) {
        sim.apply_operation(plan.first);
    }

    FastRng rng(seed);
    for (int step = 0; step < config().defense_horizon && !sim.terminal; ++step) {
        if (step == 1 && plan.has_second && sim.can_apply_operation(plan.second, plan.blocked_x, plan.blocked_y, plan.blocked_tower_id)) {
            sim.apply_operation(plan.second);
        }
        if (step == 0) {
            sim.simulate_round(rng, combo.forced_moves);
        } else {
            sim.simulate_round(rng);
        }
        sim.coins += offense.money_gain_by_round[static_cast<std::size_t>(step)];
    }
    TerminalEvaluationBreakdown breakdown = terminal_evaluation_breakdown(sim);
    breakdown.terminal_bonus_score += plan.terminal_bonus;
    breakdown.total += plan.terminal_bonus;
    return breakdown;
}

struct ProgressivePlanEvaluation {
    SearchPlan plan;
    std::string key;
    std::size_t eval_index = 0;
    std::vector<ComboRolloutSpec> combos;
    std::vector<int> sampled_counts;
    std::vector<double> sampled_sums;
    std::vector<TerminalEvaluationBreakdown> sampled_breakdown_sums;
    int allocated_rollouts = 0;
    std::uint64_t next_seed_serial = 0;
    std::uint64_t seed_base = 0;
    double score = -std::numeric_limits<double>::infinity();
    double score_before_penalty = -std::numeric_limits<double>::infinity();
    PenaltyBreakdown penalty_breakdown;
    TerminalEvaluationBreakdown terminal_breakdown;
};

inline double combo_coverage_priority(const ComboRolloutSpec &combo) {
    const double rarity_bonus = 0.25 / std::max(combo.probability, 0.03);
    return combo.danger * (1.0 + rarity_bonus) + combo.probability * 32.0;
}

inline std::vector<int> combo_target_counts_for_budget(
    const std::vector<ComboRolloutSpec> &combos,
    int total_budget) {
    if (combos.empty() || total_budget <= 0) {
        return {};
    }

    const int count = static_cast<int>(combos.size());
    std::vector<int> targets(static_cast<std::size_t>(count), 0);
    std::vector<int> probability_order(static_cast<std::size_t>(count), 0);
    for (int index = 0; index < count; ++index) {
        probability_order[static_cast<std::size_t>(index)] = index;
    }
    std::sort(probability_order.begin(), probability_order.end(), [&](int lhs, int rhs) {
        if (combos[static_cast<std::size_t>(lhs)].probability != combos[static_cast<std::size_t>(rhs)].probability) {
            return combos[static_cast<std::size_t>(lhs)].probability > combos[static_cast<std::size_t>(rhs)].probability;
        }
        return combos[static_cast<std::size_t>(lhs)].danger > combos[static_cast<std::size_t>(rhs)].danger;
    });

    std::vector<int> coverage_order = probability_order;
    std::sort(coverage_order.begin(), coverage_order.end(), [&](int lhs, int rhs) {
        const double lhs_priority = combo_coverage_priority(combos[static_cast<std::size_t>(lhs)]);
        const double rhs_priority = combo_coverage_priority(combos[static_cast<std::size_t>(rhs)]);
        if (lhs_priority != rhs_priority) {
            return lhs_priority > rhs_priority;
        }
        return combos[static_cast<std::size_t>(lhs)].probability > combos[static_cast<std::size_t>(rhs)].probability;
    });

    int remaining = total_budget;
    auto give_one = [&](int combo_index) {
        if (remaining <= 0 || combo_index < 0 || combo_index >= count) {
            return;
        }
        int &slot = targets[static_cast<std::size_t>(combo_index)];
        if (slot > 0) {
            return;
        }
        slot = 1;
        --remaining;
    };

    const int probability_cover = std::min(count, std::max(1, total_budget / 8));
    const int danger_cover = std::min(count, std::max(1, total_budget / 6));
    for (int index = 0; index < probability_cover; ++index) {
        give_one(probability_order[static_cast<std::size_t>(index)]);
    }
    for (int index = 0; index < danger_cover; ++index) {
        give_one(coverage_order[static_cast<std::size_t>(index)]);
    }
    for (int combo_index : coverage_order) {
        if (remaining <= 0) {
            break;
        }
        give_one(combo_index);
    }
    if (remaining <= 0) {
        return targets;
    }

    double probability_sum = 0.0;
    for (const auto &combo : combos) {
        probability_sum += combo.probability;
    }
    if (probability_sum <= 0.0) {
        probability_sum = 1.0;
    }

    std::vector<double> remainders(static_cast<std::size_t>(count), 0.0);
    int assigned = 0;
    for (int index = 0; index < count; ++index) {
        const double exact = combos[static_cast<std::size_t>(index)].probability /
                             probability_sum * static_cast<double>(remaining);
        const int base = static_cast<int>(std::floor(exact));
        targets[static_cast<std::size_t>(index)] += base;
        remainders[static_cast<std::size_t>(index)] = exact - static_cast<double>(base);
        assigned += base;
    }

    int leftover = remaining - assigned;
    while (leftover > 0) {
        int best_index = 0;
        for (int index = 1; index < count; ++index) {
            if (remainders[static_cast<std::size_t>(index)] > remainders[static_cast<std::size_t>(best_index)]) {
                best_index = index;
            }
        }
        ++targets[static_cast<std::size_t>(best_index)];
        remainders[static_cast<std::size_t>(best_index)] = -1.0;
        --leftover;
    }
    return targets;
}

inline double progressive_plan_score(const ProgressivePlanEvaluation &evaluation) {
    double weighted_sum = 0.0;
    double sampled_weight = 0.0;
    for (std::size_t index = 0; index < evaluation.combos.size(); ++index) {
        if (evaluation.sampled_counts[index] <= 0) {
            continue;
        }
        const double mean = evaluation.sampled_sums[index] / static_cast<double>(evaluation.sampled_counts[index]);
        weighted_sum += mean * evaluation.combos[index].probability;
        sampled_weight += evaluation.combos[index].probability;
    }
    if (sampled_weight <= 0.0) {
        return -std::numeric_limits<double>::infinity();
    }
    return weighted_sum / sampled_weight - evaluation.plan.penalty;
}

inline double progressive_plan_score_before_penalty(const ProgressivePlanEvaluation &evaluation) {
    double weighted_sum = 0.0;
    double sampled_weight = 0.0;
    for (std::size_t index = 0; index < evaluation.combos.size(); ++index) {
        if (evaluation.sampled_counts[index] <= 0) {
            continue;
        }
        const double mean = evaluation.sampled_sums[index] / static_cast<double>(evaluation.sampled_counts[index]);
        weighted_sum += mean * evaluation.combos[index].probability;
        sampled_weight += evaluation.combos[index].probability;
    }
    if (sampled_weight <= 0.0) {
        return -std::numeric_limits<double>::infinity();
    }
    return weighted_sum / sampled_weight;
}

inline TerminalEvaluationBreakdown progressive_plan_breakdown(const ProgressivePlanEvaluation &evaluation) {
    TerminalEvaluationBreakdown weighted;
    double sampled_weight = 0.0;
    for (std::size_t index = 0; index < evaluation.combos.size(); ++index) {
        if (evaluation.sampled_counts[index] <= 0) {
            continue;
        }
        const double combo_weight = evaluation.combos[index].probability;
        const double sample_scale = combo_weight / static_cast<double>(evaluation.sampled_counts[index]);
        TerminalEvaluationBreakdown contribution = evaluation.sampled_breakdown_sums[index];
        contribution.base_hp_raw *= sample_scale;
        contribution.base_hp_score *= sample_scale;
        contribution.tower_value_raw *= sample_scale;
        contribution.tower_value_score *= sample_scale;
        contribution.tower_bonus_score *= sample_scale;
        contribution.ant_threat_raw *= sample_scale;
        contribution.ant_threat_score *= sample_scale;
        contribution.money_raw *= sample_scale;
        contribution.money_score *= sample_scale;
        contribution.terminal_bonus_score *= sample_scale;
        contribution.total *= sample_scale;
        weighted += contribution;
        sampled_weight += combo_weight;
    }
    if (sampled_weight > 0.0 && std::abs(sampled_weight - 1.0) > 1e-9) {
        const double inv = 1.0 / sampled_weight;
        weighted.base_hp_raw *= inv;
        weighted.base_hp_score *= inv;
        weighted.tower_value_raw *= inv;
        weighted.tower_value_score *= inv;
        weighted.tower_bonus_score *= inv;
        weighted.ant_threat_raw *= inv;
        weighted.ant_threat_score *= inv;
        weighted.money_raw *= inv;
        weighted.money_score *= inv;
        weighted.terminal_bonus_score *= inv;
        weighted.total *= inv;
    }
    return weighted;
}

inline ProgressivePlanEvaluation make_progressive_plan_evaluation(
    const PublicState &state,
    int player,
    const DefenseSimulator &root,
    const SearchPlan &plan,
    std::string key,
    std::size_t eval_index,
    std::uint64_t seed_base) {
    DefenseSimulator seeded = root.clone();
    if (plan.has_first) {
        seeded.apply_operation(plan.first);
    }
    auto combos = rollout_combos_for(seeded);
    if (combos.empty()) {
        combos.push_back(ComboRolloutSpec{});
    }
    for (auto &combo : combos) {
        combo.samples = 0;
    }

    ProgressivePlanEvaluation evaluation;
    evaluation.plan = plan;
    evaluation.key = std::move(key);
    evaluation.eval_index = eval_index;
    evaluation.combos = std::move(combos);
    evaluation.sampled_counts.assign(evaluation.combos.size(), 0);
    evaluation.sampled_sums.assign(evaluation.combos.size(), 0.0);
    evaluation.sampled_breakdown_sums.assign(evaluation.combos.size(), TerminalEvaluationBreakdown{});
    evaluation.seed_base = seed_base;
    evaluation.penalty_breakdown = operation_penalty_breakdown(state, player, plan);
    return evaluation;
}

inline void advance_progressive_plan_evaluation(
    ProgressivePlanEvaluation &evaluation,
    int target_rollouts,
    const DefenseSimulator &root,
    const OffensiveExpectation &offense) {
    target_rollouts = std::clamp(target_rollouts, 0, config().defense_rollouts);
    if (target_rollouts <= evaluation.allocated_rollouts) {
        return;
    }
    const auto targets = combo_target_counts_for_budget(evaluation.combos, target_rollouts);
    for (std::size_t index = 0; index < evaluation.combos.size(); ++index) {
        const int target = index < targets.size() ? targets[index] : 0;
        while (evaluation.sampled_counts[index] < target) {
            const TerminalEvaluationBreakdown sample = simulate_combo(
                root,
                evaluation.plan,
                evaluation.combos[index],
                offense,
                mix_seed(evaluation.seed_base, evaluation.next_seed_serial++));
            evaluation.sampled_sums[index] += sample.total;
            evaluation.sampled_breakdown_sums[index] += sample;
            ++evaluation.sampled_counts[index];
        }
    }
    evaluation.allocated_rollouts = target_rollouts;
    evaluation.score = progressive_plan_score(evaluation);
    evaluation.score_before_penalty = progressive_plan_score_before_penalty(evaluation);
    evaluation.terminal_breakdown = progressive_plan_breakdown(evaluation);
}

constexpr int kLightningPredictionDepth = 2;
constexpr int kLightningPredictionBranchCapacity = 64;
constexpr int kLightningClusterSeparation = 2;

struct LightningPredictionBranch {
    int x = -1;
    int y = -1;
    int last_move = kNoMove;
    double probability = 0.0;
};

inline void add_lightning_heat(double (&heat)[kMapSize][kMapSize], int x, int y, double value) {
    if (!is_valid_pos(x, y) || value <= 0.0) {
        return;
    }
    heat[x][y] += value;
}

inline double lightning_ant_presence_weight(const SearchAnt &ant) {
    const double hp_ratio = static_cast<double>(std::max(ant.hp, 0)) / std::max(1, ant.max_hp());
    const double behavior_scale = behavior_threat_scale(ant.behavior);
    const double kind_weight = ant.kind == AntKind::Combat ? 4.5 : 1.6;
    return (kind_weight + hp_ratio) * behavior_scale;
}

inline void merge_lightning_prediction_branch(
    FixedList<LightningPredictionBranch, kLightningPredictionBranchCapacity> &branches,
    int x,
    int y,
    int last_move,
    double probability) {
    if (probability <= 0.0) {
        return;
    }
    for (int index = 0; index < branches.size(); ++index) {
        if (branches[index].x == x && branches[index].y == y && branches[index].last_move == last_move) {
            branches[index].probability += probability;
            return;
        }
    }
    branches.push_back(LightningPredictionBranch{x, y, last_move, probability});
}

inline void add_lightning_ant_heat(
    const DefenseSimulator &sim,
    const SearchAnt &ant,
    double (&heat)[kMapSize][kMapSize]) {
    static constexpr double kStepWeight[kLightningPredictionDepth + 1] = {1.0, 0.8, 0.6};

    const auto [base_x, base_y] = kPlayerBases[sim.player];
    const double base_weight = lightning_ant_presence_weight(ant);
    add_lightning_heat(heat, ant.x, ant.y, base_weight * kStepWeight[0]);

    FixedList<LightningPredictionBranch, kLightningPredictionBranchCapacity> frontier;
    frontier.push_back(LightningPredictionBranch{ant.x, ant.y, ant.last_move, 1.0});

    for (int step = 1; step <= kLightningPredictionDepth; ++step) {
        FixedList<LightningPredictionBranch, kLightningPredictionBranchCapacity> next;
        for (int index = 0; index < frontier.size(); ++index) {
            const auto &branch = frontier[index];
            if (branch.probability <= 0.0) {
                continue;
            }
            if (branch.x == base_x && branch.y == base_y) {
                add_lightning_heat(heat, branch.x, branch.y, base_weight * branch.probability * kStepWeight[step]);
                continue;
            }

            SearchAnt projected = ant;
            projected.x = branch.x;
            projected.y = branch.y;
            projected.last_move = branch.last_move;

            const auto options = sim.move_options_for(projected);
            if (options.empty()) {
                add_lightning_heat(heat, branch.x, branch.y, base_weight * branch.probability * kStepWeight[step]);
                merge_lightning_prediction_branch(next, branch.x, branch.y, branch.last_move, branch.probability);
                continue;
            }
            for (int option_index = 0; option_index < options.size(); ++option_index) {
                const auto &option = options[option_index];
                const double probability = branch.probability * option.probability;
                add_lightning_heat(heat, option.nx, option.ny, base_weight * probability * kStepWeight[step]);
                merge_lightning_prediction_branch(next, option.nx, option.ny, option.direction, probability);
            }
        }
        frontier = next;
    }
}

inline int lightning_tower_strikes_within_horizon(int horizon) {
    const int duration = weapon_stats(SuperWeaponType::LightningStorm).duration;
    const int capped_horizon = std::max(0, std::min(horizon, duration));
    int strikes = 0;
    for (int step = 0; step < capped_horizon; ++step) {
        const int remaining_turns = duration - step;
        if (lightning_tower_strike_turn(remaining_turns)) {
            ++strikes;
        }
    }
    return strikes;
}

inline double enemy_tower_lightning_damage_score(const PublicState &state, int player, int x, int y) {
    const int enemy = 1 - player;
    const int damage = lightning_tower_strikes_within_horizon(config().lightning_horizon) * kLightningTowerDamage;
    if (damage <= 0) {
        return 0.0;
    }

    int enemy_tower_count = 0;
    for (const auto &tower : state.towers) {
        if (tower.player == enemy && tower.hp > 0) {
            ++enemy_tower_count;
        }
    }
    if (enemy_tower_count <= 0) {
        return 0.0;
    }

    double score = 0.0;
    const int attack_range = weapon_stats(SuperWeaponType::LightningStorm).attack_range;
    for (const auto &tower : state.towers) {
        if (tower.player != enemy || tower.hp <= 0) {
            continue;
        }
        if (cell_distance_fast(x, y, tower.x, tower.y) > attack_range) {
            continue;
        }
        const SearchTower before{tower.tower_id, tower.x, tower.y, tower.tower_type, tower.hp, tower.cooldown};
        const SearchTower after{tower.tower_id, tower.x, tower.y, tower.tower_type, std::max(0, tower.hp - damage), tower.cooldown};
        const double before_value = tower_estimated_salvage_value(before, enemy_tower_count);
        const double after_value = tower_estimated_salvage_value(after, enemy_tower_count);
        score += (before_value - after_value) * config().tower_value_weight;
    }
    return score;
}

inline double lightning_ant_cluster_score(double (&heat)[kMapSize][kMapSize], int x, int y, int range) {
    double score = 0.0;
    for (int tx = 0; tx < kMapSize; ++tx) {
        for (int ty = 0; ty < kMapSize; ++ty) {
            if (heat[tx][ty] <= 0.0) {
                continue;
            }
            if (cell_distance_fast(x, y, tx, ty) > range) {
                continue;
            }
            score += heat[tx][ty];
        }
    }
    return score;
}

inline std::vector<std::pair<int, int>> lightning_centers(const PublicState &state, const DefenseSimulator &root, int player) {
    struct ScoredCell {
        int x = -1;
        int y = -1;
        double score = 0.0;
    };

    double ant_heat[kMapSize][kMapSize]{};
    for (const auto &ant : root.ants) {
        if (!ant.alive()) {
            continue;
        }
        add_lightning_ant_heat(root, ant, ant_heat);
    }

    std::vector<ScoredCell> cells;
    for (int x = 0; x < kMapSize; ++x) {
        for (int y = 0; y < kMapSize; ++y) {
            if (!is_valid_pos(x, y)) {
                continue;
            }
            if (distance_to_boundary(x, y) < 3) {
                continue;
            }
            const double ant_score = lightning_ant_cluster_score(
                ant_heat, x, y, weapon_stats(SuperWeaponType::LightningStorm).attack_range);
            const double tower_score = enemy_tower_lightning_damage_score(state, player, x, y);
            const double total_score = ant_score + tower_score;
            if (total_score <= 0.0) {
                continue;
            }
            cells.push_back(ScoredCell{x, y, total_score});
        }
    }

    std::sort(cells.begin(), cells.end(), [](const ScoredCell &lhs, const ScoredCell &rhs) {
        if (lhs.score != rhs.score) {
            return lhs.score > rhs.score;
        }
        return std::tie(lhs.x, lhs.y) < std::tie(rhs.x, rhs.y);
    });

    std::vector<std::pair<int, int>> out;
    std::vector<bool> used(cells.size(), false);
    out.reserve(std::min(static_cast<int>(cells.size()), config().lightning_center_limit));

    for (std::size_t index = 0; index < cells.size(); ++index) {
        bool overlapped = false;
        for (const auto &[sx, sy] : out) {
            if (cell_distance_fast(cells[index].x, cells[index].y, sx, sy) <= kLightningClusterSeparation) {
                overlapped = true;
                break;
            }
        }
        if (overlapped) {
            continue;
        }
        out.emplace_back(cells[index].x, cells[index].y);
        used[index] = true;
        if (static_cast<int>(out.size()) >= config().lightning_center_limit) {
            return out;
        }
    }

    for (std::size_t index = 0; index < cells.size() && static_cast<int>(out.size()) < config().lightning_center_limit; ++index) {
        if (used[index]) {
            continue;
        }
        out.emplace_back(cells[index].x, cells[index].y);
    }
    return out;
}

inline double evaluate_lightning_center(
    const DefenseSimulator &root,
    int x,
    int y,
    const OffensiveExpectation &offense,
    std::uint64_t seed_base,
    double terminal_bonus) {
    SearchPlan plan;
    plan.name = "lightning";
    plan.has_first = true;
    plan.first = Operation(OperationType::UseLightningStorm, x, y);
    plan.terminal_bonus = terminal_bonus;
    plan.penalty = 0.0;
    double total = 0.0;
    for (int rollout = 0; rollout < config().lightning_rollouts_per_center; ++rollout) {
        DefenseSimulator sim = root.clone();
        if (!sim.apply_operation(plan.first)) {
            return -std::numeric_limits<double>::infinity();
        }
        FastRng rng(mix_seed(seed_base, static_cast<std::uint64_t>(rollout + 1)));
        for (int step = 0; step < config().lightning_horizon && !sim.terminal; ++step) {
            sim.simulate_round(rng);
            if (step < config().offense_horizon) {
                sim.coins += offense.money_gain_by_round[static_cast<std::size_t>(step)];
            }
        }
        total += terminal_evaluation(sim);
    }
    return total / static_cast<double>(config().lightning_rollouts_per_center);
}

inline SearchPlan best_lightning_plan(
    const PublicState &state,
    const DefenseSimulator &root,
    int player,
    const OffensiveExpectation &offense,
    std::uint64_t seed_base) {
    SearchPlan best;
    double best_score = -std::numeric_limits<double>::infinity();
    if (state.weapon_cooldowns[player][static_cast<int>(SuperWeaponType::LightningStorm)] > 0 ||
        state.coins[player] < weapon_stats(SuperWeaponType::LightningStorm).cost) {
        return best;
    }
    for (const auto &[x, y] : lightning_centers(state, root, player)) {
        const Operation operation(OperationType::UseLightningStorm, x, y);
        if (!state.can_apply_operation(player, operation)) {
            continue;
        }
        const double tower_bonus = enemy_tower_lightning_damage_score(state, player, x, y);
        const double score = evaluate_lightning_center(
            root, x, y, offense, mix_seed(seed_base, static_cast<std::uint64_t>(x * 97 + y * 131)), tower_bonus);
        if (score > best_score) {
            best_score = score;
            best = SearchPlan{"lightning", true, operation, false, {}, -1, -1, -1, tower_bonus, score, 0.0};
        }
    }
    if (best_score > -std::numeric_limits<double>::infinity()) {
        best.penalty = operation_penalty(state, player, best);
        best.heuristic = best_score - best.penalty;
    }
    return best;
}

} // namespace random_search_detail

inline std::vector<Operation> decide_random_search_baseline(
    const RandomSearchDecisionContext &context,
    RandomSearchSession *session = nullptr) {
    using namespace random_search_detail;

    if (context.state == nullptr) {
        return {};
    }
    if (session != nullptr) {
        session->observe(*context.state, context.player);
    }

    const auto debug = debug_mode();
    const bool emit_summary = debug != DebugMode::None;
    const bool emit_plans = debug == DebugMode::Plans;
    const auto decision_begin = std::chrono::steady_clock::now();

    const auto offense = compute_offense_expectation(*context.state, context.player);
    const auto defense_root = make_defense_simulator(*context.state, context.simulator, context.player);
    auto plans = generate_plans(*context.state, context.player);

    const std::uint64_t serial = session != nullptr ? session->decision_serial[context.player] : 0ULL;
    SearchPlan lightning = best_lightning_plan(*context.state, defense_root, context.player, offense,
                                               mix_seed(context.state->seed, serial ^ 0x9e3779b97f4a7c15ULL));
    if (lightning.has_first) {
        plans.push_back(lightning);
    }

    PlanResult best;
    best.operations = {};
    std::string best_key = "hold/hold";
    std::string best_name = "hold";
    std::string best_first_text;
    std::string best_second_text;
    std::size_t unique_plan_count = 0;
    std::vector<EvaluatedPlanDebug> evaluated;
    std::vector<ProgressivePlanEvaluation> plan_evaluations;
    if (emit_plans) {
        evaluated.reserve(plans.size());
    }
    plan_evaluations.reserve(plans.size());

    std::sort(plans.begin(), plans.end(), [](const SearchPlan &lhs, const SearchPlan &rhs) {
        return lhs.heuristic > rhs.heuristic;
    });
    std::unordered_set<std::string> seen_plan;
    for (std::size_t index = 0; index < plans.size(); ++index) {
        const SearchPlan &plan = plans[index];
        std::string key = plan.has_first ? op_key(plan.first) : "hold";
        key += "/";
        key += plan.has_second ? op_key(plan.second) : "hold";
        if (!seen_plan.emplace(key).second) {
            continue;
        }
        ++unique_plan_count;
        plan_evaluations.push_back(make_progressive_plan_evaluation(
            *context.state,
            context.player,
            defense_root,
            plan,
            key,
            unique_plan_count,
            mix_seed(context.state->seed, mix_seed(serial, static_cast<std::uint64_t>(index + 1)))));
    }

    if (!plan_evaluations.empty()) {
        std::vector<std::size_t> active_indices(plan_evaluations.size(), 0);
        for (std::size_t index = 0; index < plan_evaluations.size(); ++index) {
            active_indices[index] = index;
        }

        int rollout_budget = std::min(config().defense_plan_initial_rollouts, config().defense_rollouts);
        while (!active_indices.empty()) {
            for (std::size_t plan_index : active_indices) {
                advance_progressive_plan_evaluation(plan_evaluations[plan_index], rollout_budget, defense_root, offense);
            }
            if (rollout_budget >= config().defense_rollouts || active_indices.size() == 1) {
                break;
            }

            std::sort(active_indices.begin(), active_indices.end(), [&](std::size_t lhs, std::size_t rhs) {
                if (plan_evaluations[lhs].score != plan_evaluations[rhs].score) {
                    return plan_evaluations[lhs].score > plan_evaluations[rhs].score;
                }
                return plan_evaluations[lhs].plan.heuristic > plan_evaluations[rhs].plan.heuristic;
            });

            const std::size_t keep_count = std::max<std::size_t>(
                1,
                static_cast<std::size_t>(std::ceil(
                    static_cast<double>(active_indices.size()) * config().defense_plan_keep_fraction)));
            if (keep_count < active_indices.size()) {
                active_indices.resize(keep_count);
            }

            const int next_budget = std::min(config().defense_rollouts, rollout_budget + config().defense_plan_rollout_step);
            if (next_budget <= rollout_budget) {
                break;
            }
            rollout_budget = next_budget;
        }
    }

    for (const auto &evaluation : plan_evaluations) {
        if (emit_plans) {
            evaluated.push_back(EvaluatedPlanDebug{
                evaluation.eval_index,
                evaluation.key,
                evaluation.plan.name,
                evaluation.plan.has_first ? debug_operation_text(evaluation.plan.first) : "",
                evaluation.plan.has_second ? debug_operation_text(evaluation.plan.second) : "",
                evaluation.score,
                evaluation.score_before_penalty,
                evaluation.plan.heuristic,
                evaluation.plan.penalty,
                evaluation.allocated_rollouts,
                evaluation.terminal_breakdown,
                evaluation.penalty_breakdown,
            });
        }
        if (evaluation.score > best.score) {
            best.score = evaluation.score;
            best.operations.clear();
            if (evaluation.plan.has_first) {
                best.operations.push_back(evaluation.plan.first);
            }
            best_key = evaluation.key;
            best_name = evaluation.plan.name;
            best_first_text = evaluation.plan.has_first ? debug_operation_text(evaluation.plan.first) : "";
            best_second_text = evaluation.plan.has_second ? debug_operation_text(evaluation.plan.second) : "";
        }
    }

    const auto decision_end = std::chrono::steady_clock::now();
    const auto elapsed_us = std::chrono::duration_cast<std::chrono::microseconds>(decision_end - decision_begin).count();

    if (emit_summary) {
        if (emit_plans) {
            std::sort(evaluated.begin(), evaluated.end(), [](const EvaluatedPlanDebug &lhs, const EvaluatedPlanDebug &rhs) {
                if (lhs.score != rhs.score) {
                    return lhs.score > rhs.score;
                }
                return lhs.eval_index < rhs.eval_index;
            });
            for (std::size_t rank = 0; rank < evaluated.size(); ++rank) {
                const auto &item = evaluated[rank];
                std::cerr
                    << "{\"kind\":\"plan\""
                    << ",\"round\":" << context.state->round_index
                    << ",\"player\":" << context.player
                    << ",\"serial\":" << serial
                    << ",\"rank\":" << (rank + 1)
                    << ",\"eval_index\":" << item.eval_index
                    << ",\"key\":\"" << debug_json_escape(item.key) << '"'
                    << ",\"name\":\"" << debug_json_escape(item.name) << '"'
                    << ",\"first\":\"" << debug_json_escape(item.first_text) << '"'
                    << ",\"second\":\"" << debug_json_escape(item.second_text) << '"'
                    << ",\"heuristic\":" << item.heuristic
                    << ",\"penalty\":" << item.penalty
                    << ",\"score_before_penalty\":" << item.score_before_penalty
                    << ",\"rollouts\":" << item.rollouts
                    << ",\"mean_base_hp_raw\":" << item.terminal.base_hp_raw
                    << ",\"mean_base_hp_score\":" << item.terminal.base_hp_score
                    << ",\"mean_tower_value_raw\":" << item.terminal.tower_value_raw
                    << ",\"mean_tower_value_score\":" << item.terminal.tower_value_score
                    << ",\"mean_tower_bonus_score\":" << item.terminal.tower_bonus_score
                    << ",\"mean_ant_threat_raw\":" << item.terminal.ant_threat_raw
                    << ",\"mean_ant_threat_score\":" << item.terminal.ant_threat_score
                    << ",\"mean_money_raw\":" << item.terminal.money_raw
                    << ",\"mean_money_score\":" << item.terminal.money_score
                    << ",\"mean_terminal_bonus_score\":" << item.terminal.terminal_bonus_score
                    << ",\"pen_downgrade\":" << item.penalty_breakdown.downgrade
                    << ",\"pen_lightning\":" << item.penalty_breakdown.lightning
                    << ",\"pen_hold_bias\":" << item.penalty_breakdown.hold_bias
                    << ",\"pen_emergency_discount\":" << item.penalty_breakdown.emergency_discount
                    << ",\"score\":" << item.score
                    << "}\n";
            }
        }
        const auto threat = immediate_threat_context(*context.state, context.player);
        int enemy_ant_count = 0;
        for (const auto &ant : context.state->ants) {
            if (ant.player == 1 - context.player && ant.is_alive()) {
                ++enemy_ant_count;
            }
        }
        std::cerr
            << "{\"kind\":\"decision\""
            << ",\"round\":" << context.state->round_index
            << ",\"player\":" << context.player
            << ",\"serial\":" << serial
            << ",\"plans_total\":" << plans.size()
            << ",\"plans_unique\":" << unique_plan_count
            << ",\"best_key\":\"" << debug_json_escape(best_key) << '"'
            << ",\"best_name\":\"" << debug_json_escape(best_name) << '"'
            << ",\"best_first\":\"" << debug_json_escape(best_first_text) << '"'
            << ",\"best_second\":\"" << debug_json_escape(best_second_text) << '"'
            << ",\"coins\":" << context.state->coins[context.player]
            << ",\"base_hp\":" << context.state->bases[context.player].hp
            << ",\"tower_count\":" << context.state->tower_count(context.player)
            << ",\"enemy_ant_count\":" << enemy_ant_count
            << ",\"enemy_combat_ring1\":" << threat.combat_ring1
            << ",\"enemy_combat_ring2\":" << threat.combat_ring2
            << ",\"combat_pressure\":" << threat.combat_pressure
            << ",\"tower_pressure\":" << threat.tower_pressure
            << ",\"best_score\":" << best.score
            << ",\"elapsed_us\":" << elapsed_us
            << "}\n";
    }
    return best.operations;
}

inline std::vector<Operation> decide_random_search_baseline(const PublicState &state, int player) {
    RandomSearchDecisionContext context;
    context.state = &state;
    context.player = player;
    return decide_random_search_baseline(context, nullptr);
}

} // namespace antgame::sdk
