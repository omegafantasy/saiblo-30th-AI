#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {
constexpr int kBuildTower = 11;
constexpr int kUpgradeTower = 12;
constexpr int kUseLightningStorm = 21;
constexpr int kUseEmpBlaster = 22;
constexpr int kUseDeflector = 23;
constexpr int kUseEmergencyEvasion = 24;
constexpr int kUpgradeGenerationSpeed = 31;
constexpr int kUpgradeGeneratedAnt = 32;
constexpr int kPlayerCount = 2;
constexpr int kMapSize = 19;
constexpr int kBaseUpgradeCost[2] = {200, 250};
constexpr int kOwnBaseX[2] = {2, 16};
constexpr int kOwnBaseY[2] = {9, 9};

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
    int cooldown = 0;
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
    std::string branch;
    int group = 0;
    int x = -1;
    int y = -1;
    double priority = 0.0;
    bool build_legal = false;
    int tower_id = -1;
    int tower_type = -1;
};

struct RoundState {
    int round = 0;
    std::vector<TowerInfo> towers;
    std::vector<AntInfo> ants;
    std::array<int, 2> coins = {50, 50};
    std::array<int, 2> camps_hp = {50, 50};
};

struct Snapshot {
    int player = 0;
    int round = 0;
    int safe_coin_threshold = 0;
    int nearest_enemy_distance = 32;
    int frontline_distance = 32;
    std::vector<int> coins = {50, 50};
    std::vector<int> die_count = {0, 0};
    std::vector<int> old_count = {0, 0};
    std::vector<std::vector<int>> weapon_cooldowns = std::vector<std::vector<int>>(2, std::vector<int>(5, 0));
    std::vector<BaseInfo> bases;
    std::vector<TowerInfo> towers;
    std::vector<AntInfo> ants;
    std::vector<EffectInfo> effects;
    std::vector<SlotInfo> slots;
};

struct ScoreBreakdown {
    double total = -1e18;
    std::string reason;
};

const std::array<std::array<std::pair<int, int>, 35>, 2> kStrategicSlots = {{
    {{{2, 9}, {4, 9}, {5, 9}, {5, 7}, {6, 9}, {5, 11}, {5, 6}, {6, 7}, {6, 11},
      {5, 12}, {4, 3}, {5, 3}, {7, 8}, {7, 10}, {4, 15}, {5, 15}, {4, 2}, {6, 4},
      {7, 5}, {8, 7}, {8, 11}, {7, 13}, {6, 14}, {4, 16}, {6, 1}, {6, 2}, {6, 16},
      {6, 17}, {7, 1}, {8, 4}, {8, 14}, {7, 17}, {8, 2}, {8, 16}, {3, 9}}},
    {{{16, 9}, {14, 9}, {13, 9}, {13, 7}, {12, 9}, {13, 11}, {12, 6}, {12, 7}, {12, 11},
      {12, 12}, {14, 3}, {13, 3}, {10, 8}, {10, 10}, {14, 15}, {13, 15}, {13, 2}, {11, 4},
      {11, 5}, {10, 7}, {10, 11}, {11, 13}, {11, 14}, {13, 16}, {12, 1}, {11, 2}, {11, 16},
      {12, 17}, {11, 1}, {9, 4}, {9, 14}, {11, 17}, {9, 2}, {9, 16}, {15, 9}}},
}};

struct Tracker {
    std::array<std::array<int, 5>, 2> weapon_cd{};
    std::array<int, 2> generation_level = {0, 0};
    std::array<int, 2> ant_level = {0, 0};
    std::array<int, 2> die_count = {0, 0};
    std::array<int, 2> old_count = {0, 0};
    std::vector<EffectInfo> effects;
    std::unordered_map<int, AntInfo> prev_ants;
};

int hex_distance(int x0, int y0, int x1, int y1) {
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

bool is_alive_status(int status) {
    return status == 0 || status == 4;
}

int ant_weight(const AntInfo &ant) {
    return 2 + ant.level * 2;
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

int weapon_cost(int type) {
    switch (type) {
    case kUseLightningStorm:
    case kUseEmpBlaster: return 150;
    case kUseDeflector:
    case kUseEmergencyEvasion: return 100;
    default: return 0;
    }
}

int weapon_duration(int type) {
    switch (type) {
    case kUseLightningStorm:
    case kUseEmpBlaster: return 20;
    case kUseDeflector: return 10;
    case kUseEmergencyEvasion: return 1;
    default: return 0;
    }
}

int weapon_cooldown(int type) {
    switch (type) {
    case kUseLightningStorm:
    case kUseEmpBlaster: return 100;
    case kUseDeflector:
    case kUseEmergencyEvasion: return 50;
    default: return 0;
    }
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

int tower_level(int tower_type) {
    if (tower_type < 0) {
        return 0;
    }
    if (tower_type == 0) {
        return 0;
    }
    if (tower_type < 10) {
        return 1;
    }
    return 2;
}

double tower_static_value(int tower_type) {
    switch (tower_type) {
    case 0: return 20.0;
    case 1: return 54.0;
    case 2: return 34.0;
    case 3: return 42.0;
    case 11: return 92.0;
    case 12: return 82.0;
    case 13: return 75.0;
    case 21: return 82.0;
    case 22: return 86.0;
    case 23: return 90.0;
    case 31: return 110.0;
    case 32: return 88.0;
    case 33: return 118.0;
    default: return 0.0;
    }
}

int op_weapon_index(int op_type) {
    if (op_type < 21 || op_type > 24) {
        return 0;
    }
    return op_type % 10;
}

int count_type(const Snapshot &snapshot, int tower_type) {
    int count = 0;
    for (const auto &tower : snapshot.towers) {
        if (tower.player == snapshot.player && tower.type == tower_type) {
            ++count;
        }
    }
    return count;
}

int own_tower_count(const Snapshot &snapshot, int player) {
    int count = 0;
    for (const auto &tower : snapshot.towers) {
        if (tower.player == player) {
            ++count;
        }
    }
    return count;
}

bool effect_covers(const EffectInfo &effect, int x, int y) {
    return hex_distance(effect.x, effect.y, x, y) <= 3;
}

bool build_blocked_by_emp(const Snapshot &snapshot, int player, int x, int y) {
    for (const auto &effect : snapshot.effects) {
        if (effect.type == 2 && effect.player != player && effect_covers(effect, x, y)) {
            return true;
        }
    }
    return false;
}

double centerline_weight(int player, int x, int y) {
    if (player == 0) {
        if ((x == 2 || x == 16) && y == 9) return 1.0;
        if ((x == 4 || x == 14) && y == 9) return 1.1;
        if ((x == 5 || x == 13) && y == 9) return 1.15;
        if ((x == 6 || x == 12) && y == 9) return 1.2;
    }
    if ((x == 2 || x == 16) && y == 9) return 1.0;
    if ((x == 4 || x == 14) && y == 9) return 1.1;
    if ((x == 5 || x == 13) && y == 9) return 1.15;
    if ((x == 6 || x == 12) && y == 9) return 1.2;
    return 1.0;
}

double slot_priority(int player, int x, int y) {
    int order = 34;
    const auto &slots = kStrategicSlots[player];
    for (size_t i = 0; i < slots.size(); ++i) {
        if (slots[i].first == x && slots[i].second == y) {
            order = static_cast<int>(i);
            break;
        }
    }
    double priority = std::max(0.0, 24.0 - order * 0.6);
    priority *= centerline_weight(player, x, y);
    priority += hex_distance(x, y, kOwnBaseX[player], kOwnBaseY[player]) * 0.4;
    return priority;
}

std::string slot_branch(int player, int x, int y) {
    const int enemy_x = kOwnBaseX[1 - player];
    const int forward = hex_distance(x, y, enemy_x, kOwnBaseY[1 - player]);
    const int lane = std::abs(y - 9);
    if (lane >= 5) {
        return "mortar";
    }
    if (forward <= 8 || lane <= 2) {
        return "heavy";
    }
    return "quick";
}

int slot_group(int, int, int y) {
    if (y <= 4) return 0;
    if (y <= 7) return 1;
    if (y <= 11) return 2;
    if (y <= 14) return 3;
    return 4;
}

void send_packet(const std::vector<Op> &ops) {
    std::ostringstream out;
    out << ops.size() << '\n';
    for (const auto &op : ops) {
        if (op.type == kBuildTower || op.type == kUpgradeTower || (op.type >= 21 && op.type <= 24)) {
            out << op.type << ' ' << op.arg0 << ' ' << op.arg1 << '\n';
        } else {
            out << op.type << '\n';
        }
    }
    std::string payload = out.str();
    uint32_t n = static_cast<uint32_t>(payload.size());
    unsigned char hdr[4];
    hdr[0] = static_cast<unsigned char>((n >> 24) & 0xFF);
    hdr[1] = static_cast<unsigned char>((n >> 16) & 0xFF);
    hdr[2] = static_cast<unsigned char>((n >> 8) & 0xFF);
    hdr[3] = static_cast<unsigned char>(n & 0xFF);
    std::cout.write(reinterpret_cast<const char *>(hdr), 4);
    std::cout << payload;
    std::cout.flush();
}

bool recv_line(std::string &line) {
    return static_cast<bool>(std::getline(std::cin, line));
}

bool recv_operations(std::vector<Op> &ops) {
    std::string line;
    if (!recv_line(line)) {
        return false;
    }
    int count = 0;
    try {
        count = std::stoi(line);
    } catch (...) {
        count = 0;
    }
    ops.clear();
    for (int i = 0; i < count; ++i) {
        if (!recv_line(line)) {
            return false;
        }
        std::istringstream iss(line);
        Op op;
        iss >> op.type;
        if (!(iss >> op.arg0)) {
            op.arg0 = -1;
        }
        if (!(iss >> op.arg1)) {
            op.arg1 = -1;
        }
        ops.push_back(op);
    }
    return true;
}

bool recv_round_state(RoundState &state) {
    std::string line;
    if (!recv_line(line)) {
        return false;
    }
    state.round = std::stoi(line);
    if (!recv_line(line)) {
        return false;
    }
    int tower_count = std::stoi(line);
    state.towers.clear();
    for (int i = 0; i < tower_count; ++i) {
        if (!recv_line(line)) {
            return false;
        }
        std::istringstream iss(line);
        TowerInfo tower;
        iss >> tower.id >> tower.player >> tower.x >> tower.y >> tower.type >> tower.cooldown;
        state.towers.push_back(tower);
    }
    if (!recv_line(line)) {
        return false;
    }
    int ant_count = std::stoi(line);
    state.ants.clear();
    for (int i = 0; i < ant_count; ++i) {
        if (!recv_line(line)) {
            return false;
        }
        std::istringstream iss(line);
        AntInfo ant;
        iss >> ant.id >> ant.player >> ant.x >> ant.y >> ant.hp >> ant.level >> ant.age >> ant.status >> ant.behavior;
        state.ants.push_back(ant);
    }
    if (!recv_line(line)) {
        return false;
    }
    {
        std::istringstream iss(line);
        iss >> state.coins[0] >> state.coins[1];
    }
    if (!recv_line(line)) {
        return false;
    }
    {
        std::istringstream iss(line);
        iss >> state.camps_hp[0] >> state.camps_hp[1];
    }
    return true;
}

const TowerInfo *find_tower(const Snapshot &snapshot, int tower_id) {
    for (const auto &tower : snapshot.towers) {
        if (tower.id == tower_id) {
            return &tower;
        }
    }
    return nullptr;
}

TowerInfo *find_tower_mut(Snapshot &snapshot, int tower_id) {
    for (auto &tower : snapshot.towers) {
        if (tower.id == tower_id) {
            return &tower;
        }
    }
    return nullptr;
}

void apply_operation_abstract(Snapshot &snapshot, const Op &op, int actor) {
    if (actor < 0 || actor >= kPlayerCount) {
        return;
    }
    if (op.type == kBuildTower) {
        const int cost = build_cost(own_tower_count(snapshot, actor));
        snapshot.coins[actor] -= cost;
        TowerInfo tower;
        tower.id = 100000 + static_cast<int>(snapshot.towers.size());
        tower.player = actor;
        tower.x = op.arg0;
        tower.y = op.arg1;
        tower.type = 0;
        snapshot.towers.push_back(tower);
        for (auto &slot : snapshot.slots) {
            if (slot.x == op.arg0 && slot.y == op.arg1) {
                slot.build_legal = false;
                slot.tower_id = tower.id;
                slot.tower_type = 0;
            }
        }
        return;
    }
    if (op.type == kUpgradeTower) {
        snapshot.coins[actor] -= upgrade_cost(op.arg1);
        if (TowerInfo *tower = find_tower_mut(snapshot, op.arg0)) {
            tower->type = op.arg1;
        }
        for (auto &slot : snapshot.slots) {
            if (slot.tower_id == op.arg0) {
                slot.tower_type = op.arg1;
            }
        }
        return;
    }
    if (op.type == kUpgradeGeneratedAnt) {
        snapshot.coins[actor] -= kBaseUpgradeCost[snapshot.bases[actor].ant_level];
        snapshot.bases[actor].ant_level = std::min(snapshot.bases[actor].ant_level + 1, 2);
        return;
    }
    if (op.type == kUpgradeGenerationSpeed) {
        snapshot.coins[actor] -= kBaseUpgradeCost[snapshot.bases[actor].generation_level];
        snapshot.bases[actor].generation_level = std::min(snapshot.bases[actor].generation_level + 1, 2);
        return;
    }
    if (op.type >= 21 && op.type <= 24) {
        snapshot.coins[actor] -= weapon_cost(op.type);
        const int weapon_index = op_weapon_index(op.type);
        if (weapon_index > 0) {
            snapshot.weapon_cooldowns[actor][weapon_index] = weapon_cooldown(op.type) - 1;
            snapshot.effects.push_back(EffectInfo{weapon_index, actor, op.arg0, op.arg1, std::max(0, weapon_duration(op.type) - 1)});
        }
        return;
    }
}

Snapshot build_snapshot(const RoundState &state, const Tracker &tracker, int player) {
    Snapshot snapshot;
    snapshot.player = player;
    snapshot.round = state.round;
    snapshot.coins = {state.coins[0], state.coins[1]};
    snapshot.die_count = {tracker.die_count[0], tracker.die_count[1]};
    snapshot.old_count = {tracker.old_count[0], tracker.old_count[1]};
    snapshot.weapon_cooldowns = std::vector<std::vector<int>>(2, std::vector<int>(5, 0));
    for (int p = 0; p < 2; ++p) {
        for (int i = 0; i < 5; ++i) {
            snapshot.weapon_cooldowns[p][i] = tracker.weapon_cd[p][i];
        }
        snapshot.bases.push_back(BaseInfo{p, kOwnBaseX[p], kOwnBaseY[p], state.camps_hp[p], tracker.generation_level[p], tracker.ant_level[p]});
    }
    snapshot.towers = state.towers;
    snapshot.ants = state.ants;
    snapshot.effects = tracker.effects;
    for (const auto &ant : state.ants) {
        if (!is_alive_status(ant.status)) {
            continue;
        }
        if (ant.player != player) {
            snapshot.nearest_enemy_distance = std::min(snapshot.nearest_enemy_distance, hex_distance(ant.x, ant.y, kOwnBaseX[player], kOwnBaseY[player]));
        } else {
            snapshot.frontline_distance = std::min(snapshot.frontline_distance, hex_distance(ant.x, ant.y, kOwnBaseX[1 - player], kOwnBaseY[1 - player]));
        }
    }
    const int enemy = 1 - player;
    const int emp_cd = tracker.weapon_cd[enemy][2];
    const int enemy_coin = state.coins[enemy];
    if (emp_cd >= 90) {
        snapshot.safe_coin_threshold = 0;
    } else if (emp_cd > 0) {
        snapshot.safe_coin_threshold = std::max(static_cast<int>(std::min(enemy_coin, 149) - emp_cd * 1.66), 0);
    } else {
        snapshot.safe_coin_threshold = std::min(enemy_coin, 149);
    }

    const auto &slots = kStrategicSlots[player];
    for (const auto &[x, y] : slots) {
        if (x == kOwnBaseX[player] && y == kOwnBaseY[player]) {
            continue;
        }
        SlotInfo slot;
        slot.x = x;
        slot.y = y;
        slot.branch = slot_branch(player, x, y);
        slot.group = slot_group(player, x, y);
        slot.priority = slot_priority(player, x, y);
        slot.build_legal = true;
        for (const auto &tower : state.towers) {
            if (tower.x == x && tower.y == y) {
                slot.build_legal = false;
                slot.tower_id = tower.id;
                slot.tower_type = tower.type;
                break;
            }
        }
        if (build_blocked_by_emp(snapshot, player, x, y)) {
            slot.build_legal = false;
        }
        snapshot.slots.push_back(slot);
    }
    return snapshot;
}

void update_tracker_after_round(Tracker &tracker, const RoundState &state, const std::vector<Op> &ops0, const std::vector<Op> &ops1) {
    for (int p = 0; p < 2; ++p) {
        for (int i = 0; i < 5; ++i) {
            if (tracker.weapon_cd[p][i] > 0) {
                --tracker.weapon_cd[p][i];
            }
        }
    }
    std::vector<EffectInfo> next_effects;
    for (auto effect : tracker.effects) {
        if (effect.remaining > 0) {
            --effect.remaining;
        }
        if (effect.remaining > 0 && effect.type != 4) {
            next_effects.push_back(effect);
        }
    }
    tracker.effects.swap(next_effects);

    const std::array<std::vector<Op>, 2> ops = {ops0, ops1};
    for (int p = 0; p < 2; ++p) {
        for (const auto &op : ops[p]) {
            if (op.type == kUpgradeGeneratedAnt) {
                tracker.ant_level[p] = std::min(tracker.ant_level[p] + 1, 2);
            } else if (op.type == kUpgradeGenerationSpeed) {
                tracker.generation_level[p] = std::min(tracker.generation_level[p] + 1, 2);
            } else if (op.type >= 21 && op.type <= 24) {
                const int index = op_weapon_index(op.type);
                tracker.weapon_cd[p][index] = std::max(0, weapon_cooldown(op.type) - 1);
                int remaining = std::max(0, weapon_duration(op.type) - 1);
                if (op.type != kUseEmergencyEvasion || remaining > 0) {
                    if (remaining > 0) {
                        tracker.effects.push_back(EffectInfo{index, p, op.arg0, op.arg1, remaining});
                    }
                }
            }
        }
    }

    std::unordered_map<int, AntInfo> current_ants;
    for (const auto &ant : state.ants) {
        if (is_alive_status(ant.status)) {
            current_ants[ant.id] = ant;
        }
    }
    for (const auto &[ant_id, ant] : tracker.prev_ants) {
        if (current_ants.find(ant_id) != current_ants.end()) {
            continue;
        }
        if (ant.status == 3 || ant.age >= 32) {
            ++tracker.old_count[ant.player];
        } else if (!(ant.x == kOwnBaseX[1 - ant.player] && ant.y == kOwnBaseY[1 - ant.player])) {
            ++tracker.die_count[ant.player];
        }
    }
    tracker.prev_ants.swap(current_ants);
}

class AntGameAI {
  public:
    std::vector<Op> decide(const Snapshot &snapshot) {
        if (snapshot.round == 0) {
            attack_commit_ = false;
        }
        update_attack_mode(snapshot);

        const bool severe_threat = enemy_threat(snapshot) >= 28.0 || snapshot.nearest_enemy_distance <= 3;

        if (auto evasion = maybe_emergency_evasion(snapshot, severe_threat)) {
            return {*evasion};
        }
        if (auto lightning = maybe_emergency_lightning(snapshot, severe_threat)) {
            return {*lightning};
        }
        if (auto deflector = maybe_attack_deflector(snapshot, severe_threat)) {
            return {*deflector};
        }
        if (auto emp = maybe_attack_emp(snapshot, severe_threat)) {
            return {*emp};
        }
        if (auto upgrade = maybe_base_upgrade(snapshot, severe_threat)) {
            return {*upgrade};
        }

        std::vector<std::vector<Op>> candidates;
        candidates.push_back({});
        append_build_candidates(snapshot, candidates);
        append_upgrade_candidates(snapshot, candidates);
        append_combo_candidates(snapshot, candidates);

        ScoreBreakdown best;
        std::vector<Op> best_ops;
        for (const auto &ops : candidates) {
            ScoreBreakdown score = evaluate_candidate(snapshot, ops);
            if (score.total > best.total) {
                best = score;
                best_ops = ops;
            }
        }

        if (best_ops.empty() && severe_threat) {
            if (auto fallback = defensive_upgrade(snapshot)) {
                return {*fallback};
            }
        }
        return best_ops;
    }

  private:
    bool attack_commit_ = false;

    static double enemy_threat(const Snapshot &snapshot) {
        const int me = snapshot.player;
        const BaseInfo &base = snapshot.bases[me];
        double threat = 0.0;
        for (const auto &ant : snapshot.ants) {
            if (ant.player == me || !is_alive_status(ant.status)) {
                continue;
            }
            const int dist = hex_distance(ant.x, ant.y, base.x, base.y);
            threat += std::max(0, 10 - dist) * ant_weight(ant);
        }
        return threat;
    }

    static double own_pressure(const Snapshot &snapshot) {
        const int me = snapshot.player;
        const BaseInfo &enemy_base = snapshot.bases[1 - me];
        double pressure = 0.0;
        for (const auto &ant : snapshot.ants) {
            if (ant.player != me || !is_alive_status(ant.status)) {
                continue;
            }
            const int dist = hex_distance(ant.x, ant.y, enemy_base.x, enemy_base.y);
            pressure += std::max(0, 10 - dist) * ant_weight(ant);
        }
        return pressure;
    }

    static double defensive_cover(const Snapshot &snapshot, int player, int x, int y) {
        double cover = 0.0;
        for (const auto &tower : snapshot.towers) {
            if (tower.player != player) {
                continue;
            }
            if (hex_distance(tower.x, tower.y, x, y) <= tower_range(tower.type)) {
                cover += tower_damage(tower.type);
            }
        }
        return cover;
    }

    static double danger_forecast(const Snapshot &snapshot) {
        const int me = snapshot.player;
        double risk = 0.0;
        for (const auto &ant : snapshot.ants) {
            if (ant.player == me || !is_alive_status(ant.status)) {
                continue;
            }
            const int dist = hex_distance(ant.x, ant.y, snapshot.bases[me].x, snapshot.bases[me].y);
            if (dist > 8) {
                continue;
            }
            double cover = defensive_cover(snapshot, me, ant.x, ant.y);
            double remain = std::max(0.0, static_cast<double>(ant.hp) - cover);
            risk += remain * std::max(0, 9 - dist) * (1.0 + ant.level * 0.35);
        }
        return risk;
    }

    void update_attack_mode(const Snapshot &snapshot) {
        const int me = snapshot.player;
        const int enemy = 1 - me;
        const int hp_diff = snapshot.bases[me].hp - snapshot.bases[enemy].hp;
        if (hp_diff < 0) {
            attack_commit_ = true;
            return;
        }
        if (hp_diff > 6) {
            attack_commit_ = false;
            return;
        }
        const double pressure = own_pressure(snapshot);
        const double threat = enemy_threat(snapshot);
        if (snapshot.round >= 430 && pressure >= threat * 0.85) {
            attack_commit_ = true;
            return;
        }
        if (pressure - threat >= 8.0) {
            attack_commit_ = true;
        } else if (threat - pressure >= 14.0) {
            attack_commit_ = false;
        }
    }

    std::optional<Op> maybe_base_upgrade(const Snapshot &snapshot, bool severe_threat) const {
        const int me = snapshot.player;
        const int reserve = snapshot.safe_coin_threshold;
        if (severe_threat || snapshot.round > 460) {
            return std::nullopt;
        }
        if (snapshot.bases[me].ant_level < 2) {
            const int cost = kBaseUpgradeCost[snapshot.bases[me].ant_level];
            if (snapshot.coins[me] - reserve >= cost && own_tower_count(snapshot, me) >= 2) {
                return Op{kUpgradeGeneratedAnt, -1, -1};
            }
        }
        if (snapshot.bases[me].ant_level >= 2 && snapshot.bases[me].generation_level < 2) {
            const int cost = kBaseUpgradeCost[snapshot.bases[me].generation_level];
            if (snapshot.coins[me] - reserve >= cost && attack_commit_) {
                return Op{kUpgradeGenerationSpeed, -1, -1};
            }
        }
        return std::nullopt;
    }

    std::optional<Op> maybe_emergency_lightning(const Snapshot &snapshot, bool severe_threat) const {
        const int me = snapshot.player;
        if (snapshot.weapon_cooldowns[me][1] > 0 || snapshot.coins[me] < weapon_cost(kUseLightningStorm)) {
            return std::nullopt;
        }
        double best_score = -1.0;
        std::pair<int, int> best_center = {-1, -1};
        for (const auto &ant : snapshot.ants) {
            if (ant.player == me || !is_alive_status(ant.status)) {
                continue;
            }
            double score = 0.0;
            for (const auto &other : snapshot.ants) {
                if (other.player == me || !is_alive_status(other.status)) {
                    continue;
                }
                if (hex_distance(ant.x, ant.y, other.x, other.y) <= 3) {
                    score += 45.0 + 10.0 * other.level;
                }
            }
            const int base_dist = hex_distance(ant.x, ant.y, snapshot.bases[me].x, snapshot.bases[me].y);
            score += std::max(0, 7 - base_dist) * 18.0;
            if (score > best_score) {
                best_score = score;
                best_center = {ant.x, ant.y};
            }
        }
        if (best_score >= (severe_threat ? 120.0 : 170.0) && best_center.first >= 0) {
            return Op{kUseLightningStorm, best_center.first, best_center.second};
        }
        return std::nullopt;
    }

    std::optional<Op> maybe_attack_emp(const Snapshot &snapshot, bool severe_threat) const {
        const int me = snapshot.player;
        if (severe_threat || !attack_commit_) {
            return std::nullopt;
        }
        if (snapshot.weapon_cooldowns[me][2] > 0 || snapshot.coins[me] < weapon_cost(kUseEmpBlaster)) {
            return std::nullopt;
        }
        double best_score = -1.0;
        std::pair<int, int> best_center = {-1, -1};
        for (const auto &tower : snapshot.towers) {
            if (tower.player == me) {
                continue;
            }
            double score = 0.0;
            for (const auto &other : snapshot.towers) {
                if (other.player == me) {
                    continue;
                }
                if (hex_distance(tower.x, tower.y, other.x, other.y) <= 3) {
                    score += tower_static_value(other.type) * 0.8;
                }
            }
            for (const auto &ant : snapshot.ants) {
                if (ant.player != me || !is_alive_status(ant.status)) {
                    continue;
                }
                if (hex_distance(tower.x, tower.y, ant.x, ant.y) <= 6) {
                    score += 8.0 + 2.0 * ant.level;
                }
            }
            if (score > best_score) {
                best_score = score;
                best_center = {tower.x, tower.y};
            }
        }
        if (best_score >= 140.0 && best_center.first >= 0) {
            return Op{kUseEmpBlaster, best_center.first, best_center.second};
        }
        return std::nullopt;
    }

    std::optional<Op> maybe_attack_deflector(const Snapshot &snapshot, bool severe_threat) const {
        const int me = snapshot.player;
        if (severe_threat || !attack_commit_) {
            return std::nullopt;
        }
        if (snapshot.weapon_cooldowns[me][3] > 0 || snapshot.coins[me] < weapon_cost(kUseDeflector)) {
            return std::nullopt;
        }
        double best_score = -1.0;
        std::pair<int, int> best_center = {-1, -1};
        for (const auto &ant : snapshot.ants) {
            if (ant.player != me || !is_alive_status(ant.status)) {
                continue;
            }
            double score = 0.0;
            for (const auto &other : snapshot.ants) {
                if (other.player != me || !is_alive_status(other.status)) {
                    continue;
                }
                if (hex_distance(ant.x, ant.y, other.x, other.y) <= 3) {
                    score += 0.8 + other.level * 0.8;
                    const int dist = hex_distance(other.x, other.y, snapshot.bases[1 - me].x, snapshot.bases[1 - me].y);
                    score += std::max(0, 8 - dist) * 0.6;
                }
            }
            if (score > best_score) {
                best_score = score;
                best_center = {ant.x, ant.y};
            }
        }
        if (best_score >= 10.0 && best_center.first >= 0) {
            return Op{kUseDeflector, best_center.first, best_center.second};
        }
        return std::nullopt;
    }

    std::optional<Op> maybe_emergency_evasion(const Snapshot &snapshot, bool severe_threat) const {
        const int me = snapshot.player;
        if (!severe_threat) {
            return std::nullopt;
        }
        if (snapshot.weapon_cooldowns[me][4] > 0 || snapshot.coins[me] < weapon_cost(kUseEmergencyEvasion)) {
            return std::nullopt;
        }
        double best_score = -1.0;
        std::pair<int, int> best_center = {-1, -1};
        for (const auto &ant : snapshot.ants) {
            if (ant.player != me || !is_alive_status(ant.status)) {
                continue;
            }
            double score = 0.0;
            for (const auto &other : snapshot.ants) {
                if (other.player != me || !is_alive_status(other.status)) {
                    continue;
                }
                if (hex_distance(ant.x, ant.y, other.x, other.y) <= 3) {
                    score += 0.6 + other.level * 0.7;
                }
            }
            score += std::max(0, 6 - hex_distance(ant.x, ant.y, snapshot.bases[me].x, snapshot.bases[me].y)) * 1.6;
            if (score > best_score) {
                best_score = score;
                best_center = {ant.x, ant.y};
            }
        }
        if (best_score >= 8.5 && best_center.first >= 0) {
            return Op{kUseEmergencyEvasion, best_center.first, best_center.second};
        }
        return std::nullopt;
    }

    std::optional<Op> defensive_upgrade(const Snapshot &snapshot) const {
        for (const auto &slot : snapshot.slots) {
            if (slot.tower_id < 0 || slot.tower_type != 0) {
                continue;
            }
            if (slot.branch != "heavy" && slot.branch != "mortar") {
                continue;
            }
            const int target = slot.branch == "heavy" ? 1 : 3;
            const int me = snapshot.player;
            if (snapshot.coins[me] >= upgrade_cost(target)) {
                return Op{kUpgradeTower, slot.tower_id, target};
            }
        }
        return std::nullopt;
    }

    void append_build_candidates(const Snapshot &snapshot, std::vector<std::vector<Op>> &candidates) const {
        int added = 0;
        for (const auto &slot : snapshot.slots) {
            if (!slot.build_legal) {
                continue;
            }
            candidates.push_back({Op{kBuildTower, slot.x, slot.y}});
            if (++added >= 8) {
                break;
            }
        }
    }

    std::vector<int> preferred_targets(const Snapshot &snapshot, const SlotInfo &slot) const {
        std::vector<int> out;
        const double threat = enemy_threat(snapshot);
        if (slot.tower_type == 0) {
            if (slot.branch == "heavy") {
                out.push_back(1);
            } else if (slot.branch == "quick") {
                out.push_back(2);
            } else {
                out.push_back(3);
            }
            return out;
        }
        if (slot.tower_type == 1) {
            if (threat >= 24.0 && count_type(snapshot, 12) == 0) {
                out.push_back(12);
            }
            if (attack_commit_ && count_type(snapshot, 13) == 0) {
                out.push_back(13);
            }
            out.push_back(11);
        } else if (slot.tower_type == 2) {
            if (attack_commit_) {
                out.push_back(23);
            }
            out.push_back(22);
            out.push_back(21);
        } else if (slot.tower_type == 3) {
            if (threat >= 28.0) {
                out.push_back(32);
            }
            if (attack_commit_) {
                out.push_back(33);
            }
            out.push_back(31);
        }
        std::sort(out.begin(), out.end());
        out.erase(std::unique(out.begin(), out.end()), out.end());
        std::reverse(out.begin(), out.end());
        return out;
    }

    void append_upgrade_candidates(const Snapshot &snapshot, std::vector<std::vector<Op>> &candidates) const {
        int added = 0;
        for (const auto &slot : snapshot.slots) {
            if (slot.tower_id < 0) {
                continue;
            }
            for (int target : preferred_targets(snapshot, slot)) {
                candidates.push_back({Op{kUpgradeTower, slot.tower_id, target}});
                if (++added >= 14) {
                    return;
                }
            }
        }
    }

    void append_combo_candidates(const Snapshot &snapshot, std::vector<std::vector<Op>> &candidates) const {
        std::vector<SlotInfo> build_slots;
        std::vector<std::pair<SlotInfo, int>> upgrades;
        for (const auto &slot : snapshot.slots) {
            if (slot.build_legal && build_slots.size() < 4) {
                build_slots.push_back(slot);
            }
            if (slot.tower_id >= 0 && upgrades.size() < 6) {
                auto targets = preferred_targets(snapshot, slot);
                if (!targets.empty()) {
                    upgrades.emplace_back(slot, targets.front());
                }
            }
        }
        for (const auto &upgrade : upgrades) {
            for (const auto &build : build_slots) {
                if (upgrade.first.x == build.x && upgrade.first.y == build.y) {
                    continue;
                }
                candidates.push_back({
                    Op{kUpgradeTower, upgrade.first.tower_id, upgrade.second},
                    Op{kBuildTower, build.x, build.y},
                });
            }
        }
    }

    ScoreBreakdown evaluate_candidate(const Snapshot &snapshot, const std::vector<Op> &ops) const {
        Snapshot sim = snapshot;
        for (const auto &op : ops) {
            apply_operation_abstract(sim, op, sim.player);
        }
        const int me = sim.player;
        const int enemy = 1 - me;
        const int reserve = sim.safe_coin_threshold;
        if (sim.coins[me] < 0) {
            return {-1e18, "insufficient_coins"};
        }
        double score = 0.0;
        score += (sim.bases[me].hp - sim.bases[enemy].hp) * 900.0;
        score += (sim.die_count[enemy] - sim.die_count[me]) * 30.0;
        score -= (sim.old_count[me] - sim.old_count[enemy]) * 12.0;

        const double threat = enemy_threat(sim);
        const double pressure = own_pressure(sim);
        const double base_danger_before = danger_forecast(snapshot);
        const double base_danger_after = danger_forecast(sim);
        score -= threat * 7.0;
        score += pressure * (attack_commit_ ? 5.2 : 3.0);
        score += sim.nearest_enemy_distance * 6.0;
        score -= sim.frontline_distance * (attack_commit_ ? 2.6 : 1.0);
        score -= base_danger_after * 2.2;
        score += (base_danger_before - base_danger_after) * 3.3;

        for (const auto &tower : sim.towers) {
            if (tower.player != me) {
                continue;
            }
            double tower_score = tower_static_value(tower.type);
            for (const auto &slot : sim.slots) {
                if (slot.x == tower.x && slot.y == tower.y) {
                    tower_score += slot.priority * 0.75;
                    break;
                }
            }
            score += tower_score;
        }

        std::array<int, 5> groups = {0, 0, 0, 0, 0};
        std::array<int, 3> branches = {0, 0, 0};
        for (const auto &slot : sim.slots) {
            if (slot.tower_id < 0) {
                continue;
            }
            if (slot.group >= 0 && slot.group < static_cast<int>(groups.size())) {
                ++groups[slot.group];
            }
            if (slot.branch == "heavy") {
                ++branches[0];
            } else if (slot.branch == "quick") {
                ++branches[1];
            } else {
                ++branches[2];
            }
        }
        for (int count : groups) {
            if (count > 3) {
                score -= (count - 3) * 8.0;
            }
        }
        int max_branch = std::max({branches[0], branches[1], branches[2]});
        int min_branch = std::min({branches[0], branches[1], branches[2]});
        score -= std::max(0, max_branch - min_branch - 4) * 5.0;

        for (size_t i = 0; i < sim.towers.size(); ++i) {
            if (sim.towers[i].player != me) {
                continue;
            }
            for (size_t j = i + 1; j < sim.towers.size(); ++j) {
                if (sim.towers[j].player != me) {
                    continue;
                }
                const int dist = hex_distance(sim.towers[i].x, sim.towers[i].y, sim.towers[j].x, sim.towers[j].y);
                if (dist <= 3) {
                    score -= 6.0;
                } else if (dist <= 6) {
                    score -= 2.0;
                }
            }
        }

        for (const auto &ant : sim.ants) {
            if (!is_alive_status(ant.status) || ant.player == me) {
                continue;
            }
            const int dist_to_base = hex_distance(ant.x, ant.y, sim.bases[me].x, sim.bases[me].y);
            const double cover = defensive_cover(sim, me, ant.x, ant.y);
            score += std::min(cover, static_cast<double>(ant.hp)) * std::max(0, 8 - dist_to_base) * 0.9;
        }

        if (sim.coins[me] < reserve) {
            score -= (reserve - sim.coins[me]) * (enemy_threat(snapshot) >= 20.0 ? 5.0 : 3.0);
        } else {
            score += std::min(sim.coins[me] - reserve, 120) * 0.3;
        }

        if (sim.bases[me].ant_level > snapshot.bases[me].ant_level) {
            score += sim.bases[me].ant_level == 1 ? 130.0 : 170.0;
        }
        if (sim.bases[me].generation_level > snapshot.bases[me].generation_level) {
            score += 150.0;
        }
        for (const auto &op : ops) {
            if (op.type == kUseLightningStorm) {
                score += 110.0;
            } else if (op.type == kUseEmpBlaster) {
                score += 95.0;
            } else if (op.type == kUseDeflector) {
                score += 60.0;
            } else if (op.type == kUseEmergencyEvasion) {
                score += 75.0;
            }
        }
        return {score, "heuristic"};
    }
};

} // namespace

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string init;
    if (!std::getline(std::cin, init)) {
        return 0;
    }
    std::istringstream iss(init);
    int player = 0;
    int seed = 0;
    iss >> player >> seed;
    (void)seed;

    RoundState state;
    Tracker tracker;
    AntGameAI ai;
    std::vector<Op> own_ops;
    std::vector<Op> opp_ops;

    while (true) {
        if (player == 0) {
            Snapshot view = build_snapshot(state, tracker, player);
            own_ops = ai.decide(view);
            send_packet(own_ops);
            if (!recv_operations(opp_ops)) {
                break;
            }
            if (!recv_round_state(state)) {
                break;
            }
            update_tracker_after_round(tracker, state, own_ops, opp_ops);
        } else {
            if (!recv_operations(opp_ops)) {
                break;
            }
            Snapshot view = build_snapshot(state, tracker, player);
            for (const auto &op : opp_ops) {
                apply_operation_abstract(view, op, 0);
            }
            own_ops = ai.decide(view);
            send_packet(own_ops);
            if (!recv_round_state(state)) {
                break;
            }
            update_tracker_after_round(tracker, state, opp_ops, own_ops);
        }
    }
    return 0;
}
