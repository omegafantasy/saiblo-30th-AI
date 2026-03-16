#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "../../Ant-Game/game/include/json.hpp"

using json = nlohmann::json;

namespace {
constexpr int kBuildTower = 11;
constexpr int kUpgradeTower = 12;
constexpr int kUseLightningStorm = 21;
constexpr int kUseEmpBlaster = 22;
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

class AntGameAI {
  public:
    std::vector<Op> decide(const Snapshot &snapshot) {
        if (snapshot.round == 0) {
            attack_commit_ = false;
        }
        update_attack_mode(snapshot);

        const bool severe_threat = enemy_threat(snapshot) >= 28.0 || snapshot.nearest_enemy_distance <= 3;

        if (auto lightning = maybe_emergency_lightning(snapshot, severe_threat)) {
            return {*lightning};
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

    static bool is_alive_status(int status) {
        return status == 0 || status == 4;
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

    static int build_cost(int tower_count) {
        int cost = 15;
        for (int i = 0; i < tower_count; ++i) {
            cost *= 2;
        }
        return cost;
    }

    static int upgrade_cost(int target_type) {
        return target_type < 10 ? 60 : 200;
    }

    static int weapon_cost(int type) {
        switch (type) {
        case kUseLightningStorm:
        case kUseEmpBlaster:
            return 150;
        default:
            return 0;
        }
    }

    static int tower_damage(int tower_type) {
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

    static int tower_range(int tower_type) {
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

    static double tower_static_value(int tower_type) {
        switch (tower_type) {
        case 0: return 20.0;
        case 1: return 54.0;
        case 2: return 34.0;
        case 3: return 42.0;
        case 11: return 92.0;
        case 12: return 82.0;
        case 13: return 84.0;
        case 21: return 58.0;
        case 22: return 66.0;
        case 23: return 78.0;
        case 31: return 94.0;
        case 32: return 88.0;
        case 33: return 100.0;
        default: return 0.0;
        }
    }

    static double ant_weight(const AntInfo &ant) {
        static const double level_weight[3] = {1.0, 1.8, 2.8};
        const int level = std::clamp(ant.level, 0, 2);
        return level_weight[level] + ant.hp * 0.03;
    }

    static int own_tower_count(const Snapshot &snapshot) {
        int count = 0;
        for (const auto &tower : snapshot.towers) {
            if (tower.player == snapshot.player) {
                ++count;
            }
        }
        return count;
    }

    static int count_type(const Snapshot &snapshot, int tower_type) {
        int count = 0;
        for (const auto &tower : snapshot.towers) {
            if (tower.player == snapshot.player && tower.type == tower_type) {
                ++count;
            }
        }
        return count;
    }

    static const TowerInfo *find_tower(const Snapshot &snapshot, int tower_id) {
        for (const auto &tower : snapshot.towers) {
            if (tower.id == tower_id) {
                return &tower;
            }
        }
        return nullptr;
    }

    static TowerInfo *find_tower_mut(Snapshot &snapshot, int tower_id) {
        for (auto &tower : snapshot.towers) {
            if (tower.id == tower_id) {
                return &tower;
            }
        }
        return nullptr;
    }

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

    void update_attack_mode(const Snapshot &snapshot) {
        const int me = snapshot.player;
        const int enemy = 1 - me;
        const int hp_diff = snapshot.bases[me].hp - snapshot.bases[enemy].hp;
        if (hp_diff < 0) {
            attack_commit_ = true;
            return;
        }
        if (hp_diff > 0) {
            attack_commit_ = false;
            return;
        }
        const double pressure = own_pressure(snapshot);
        const double threat = enemy_threat(snapshot);
        if (snapshot.round >= 450 && pressure >= threat * 0.85) {
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
        int coins = snapshot.coins[me];
        const int reserve = snapshot.safe_coin_threshold;
        if (severe_threat) {
            return std::nullopt;
        }
        if (snapshot.round > 460) {
            return std::nullopt;
        }
        if (snapshot.bases[me].ant_level < 2) {
            const int cost = kBaseUpgradeCost[snapshot.bases[me].ant_level];
            if (coins - reserve >= cost && own_tower_count(snapshot) >= 2) {
                return Op{kUpgradeGeneratedAnt, -1, -1};
            }
        }
        if (snapshot.bases[me].ant_level >= 2 && snapshot.bases[me].generation_level < 2) {
            const int cost = kBaseUpgradeCost[snapshot.bases[me].generation_level];
            if (coins - reserve >= cost && attack_commit_) {
                return Op{kUpgradeGenerationSpeed, -1, -1};
            }
        }
        return std::nullopt;
    }

    std::optional<Op> maybe_emergency_lightning(const Snapshot &snapshot, bool severe_threat) const {
        const int me = snapshot.player;
        if (snapshot.weapon_cooldowns[me][1] > 0) {
            return std::nullopt;
        }
        if (snapshot.coins[me] < weapon_cost(kUseLightningStorm)) {
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
        if (snapshot.weapon_cooldowns[me][2] > 0) {
            return std::nullopt;
        }
        if (snapshot.coins[me] < weapon_cost(kUseEmpBlaster)) {
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
                    score += 10.0;
                }
            }
            if (score > best_score) {
                best_score = score;
                best_center = {tower.x, tower.y};
            }
        }
        if (best_score >= 150.0 && best_center.first >= 0) {
            return Op{kUseEmpBlaster, best_center.first, best_center.second};
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
            if (++added >= 6) {
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
                if (++added >= 12) {
                    return;
                }
            }
        }
    }

    void append_combo_candidates(const Snapshot &snapshot, std::vector<std::vector<Op>> &candidates) const {
        std::vector<SlotInfo> build_slots;
        std::vector<std::pair<SlotInfo, int>> upgrades;
        for (const auto &slot : snapshot.slots) {
            if (slot.build_legal && build_slots.size() < 3) {
                build_slots.push_back(slot);
            }
            if (slot.tower_id >= 0 && upgrades.size() < 5) {
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

    static void apply_operation_abstract(Snapshot &snapshot, const Op &op) {
        const int me = snapshot.player;
        if (op.type == kBuildTower) {
            const int cost = build_cost(own_tower_count(snapshot));
            snapshot.coins[me] -= cost;
            TowerInfo tower;
            tower.id = 100000 + static_cast<int>(snapshot.towers.size());
            tower.player = me;
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
            snapshot.coins[me] -= upgrade_cost(op.arg1);
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
            snapshot.coins[me] -= kBaseUpgradeCost[snapshot.bases[me].ant_level];
            snapshot.bases[me].ant_level = std::min(snapshot.bases[me].ant_level + 1, 2);
            return;
        }
        if (op.type == kUpgradeGenerationSpeed) {
            snapshot.coins[me] -= kBaseUpgradeCost[snapshot.bases[me].generation_level];
            snapshot.bases[me].generation_level = std::min(snapshot.bases[me].generation_level + 1, 2);
            return;
        }
        if (op.type == kUseLightningStorm) {
            snapshot.coins[me] -= weapon_cost(op.type);
            return;
        }
        if (op.type == kUseEmpBlaster) {
            snapshot.coins[me] -= weapon_cost(op.type);
            return;
        }
    }

    ScoreBreakdown evaluate_candidate(const Snapshot &snapshot, const std::vector<Op> &ops) const {
        Snapshot sim = snapshot;
        for (const auto &op : ops) {
            apply_operation_abstract(sim, op);
        }

        const int me = sim.player;
        const int enemy = 1 - me;
        const int reserve = sim.safe_coin_threshold;
        if (sim.coins[me] < 0) {
            return {-1e18, "insufficient_coins"};
        }
        double score = 0.0;

        score += (sim.bases[me].hp - sim.bases[enemy].hp) * 900.0;
        score += (sim.die_count[enemy] - sim.die_count[me]) * 35.0;
        score -= (sim.old_count[me] - sim.old_count[enemy]) * 12.0;

        const double threat = enemy_threat(sim);
        const double pressure = own_pressure(sim);
        score -= threat * 7.0;
        score += pressure * (attack_commit_ ? 5.5 : 3.2);
        score += sim.nearest_enemy_distance * 6.0;
        score -= sim.frontline_distance * (attack_commit_ ? 2.5 : 1.0);

        for (const auto &tower : sim.towers) {
            if (tower.player != me) {
                continue;
            }
            double tower_score = tower_static_value(tower.type);
            for (const auto &slot : sim.slots) {
                if (slot.x == tower.x && slot.y == tower.y) {
                    tower_score += slot.priority * 0.7;
                    break;
                }
            }
            score += tower_score;
        }

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
            if (!is_alive_status(ant.status)) {
                continue;
            }
            if (ant.player == me) {
                continue;
            }
            const int dist_to_base = hex_distance(ant.x, ant.y, sim.bases[me].x, sim.bases[me].y);
            double cover = 0.0;
            for (const auto &tower : sim.towers) {
                if (tower.player != me) {
                    continue;
                }
                if (hex_distance(tower.x, tower.y, ant.x, ant.y) <= tower_range(tower.type)) {
                    cover += tower_damage(tower.type);
                }
            }
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
            }
        }

        return {score, "heuristic"};
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
        out.coins = j.at("coins").get<std::vector<int>>();
    }
    if (j.contains("die_count")) {
        out.die_count = j.at("die_count").get<std::vector<int>>();
    }
    if (j.contains("old_count")) {
        out.old_count = j.at("old_count").get<std::vector<int>>();
    }
    if (j.contains("weapon_cooldowns")) {
        out.weapon_cooldowns = j.at("weapon_cooldowns").get<std::vector<std::vector<int>>>();
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
        tower.cooldown = tower_j.value("cooldown", 0);
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
    return out;
}

void print_ops(const std::vector<Op> &ops) {
    std::cout << ops.size() << '\n';
    for (const auto &op : ops) {
        if (op.type == kBuildTower || op.type == kUseLightningStorm || op.type == kUseEmpBlaster) {
            std::cout << op.type << ' ' << op.arg0 << ' ' << op.arg1 << '\n';
        } else if (op.type == kUpgradeTower) {
            std::cout << op.type << ' ' << op.arg0 << ' ' << op.arg1 << '\n';
        } else if (op.type == kUpgradeGenerationSpeed || op.type == kUpgradeGeneratedAnt) {
            std::cout << op.type << '\n';
        }
    }
    std::cout.flush();
}
} // namespace

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string init_line;
    if (!std::getline(std::cin, init_line)) {
        return 0;
    }

    AntGameAI ai;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) {
            continue;
        }
        json snapshot_json;
        try {
            snapshot_json = json::parse(line);
        } catch (const std::exception &exc) {
            std::cerr << "[cpp_v1] snapshot parse error: " << exc.what() << '\n';
            print_ops({});
            continue;
        }
        Snapshot snapshot = parse_snapshot(snapshot_json);
        const std::vector<Op> ops = ai.decide(snapshot);
        print_ops(ops);
    }
    return 0;
}
