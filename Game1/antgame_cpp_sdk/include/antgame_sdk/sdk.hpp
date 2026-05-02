#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "antgame_sdk/position_slots.hpp"

namespace antgame::sdk {

constexpr int kPlayerCount = 2;
constexpr int kEdge = 10;
constexpr int kMapSize = 2 * kEdge - 1;
constexpr int kTrailMaskCells = kMapSize * kMapSize;
constexpr int kTrailMaskWords = (kTrailMaskCells + 63) / 64;
constexpr int kMaxRound = 512;
constexpr int kBaseHp = 50;
constexpr int kInitialCoins = 50;
constexpr int kBasicIncome = 3;
constexpr int kBasicIncomeInterval = 2;
constexpr int kTowerBuildBaseCost = 15;
constexpr int kLevel2TowerUpgradeCost = 60;
constexpr int kLevel3TowerUpgradeCost = 200;
constexpr int kLightningStormAntDamage = 20;
constexpr double kTowerDowngradeRefundRatio = 0.9;

constexpr std::array<std::pair<int, int>, 2> kPlayerBases = {{{2, kEdge - 1}, {kMapSize - 3, kEdge - 1}}};

constexpr int kOffset[2][6][2] = {
    {{0, 1}, {-1, 0}, {0, -1}, {1, -1}, {1, 0}, {1, 1}},
    {{-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, 0}, {0, 1}},
};

enum class AntStatus : int {
    Alive = 0,
    Success = 1,
    Fail = 2,
    TooOld = 3,
    Frozen = 4,
};

enum class AntBehavior : int {
    Default = 0,
    Conservative = 1,
    Random = 2,
    Bewitched = 3,
    ControlFree = 4,
};

enum class AntKind : int {
    Worker = 0,
    Combat = 1,
};

enum class TowerType : int {
    Basic = 0,
    Heavy = 1,
    Quick = 2,
    Mortar = 3,
    Producer = 4,
    HeavyPlus = 11,
    Ice = 12,
    Bewitch = 13,
    QuickPlus = 21,
    Double = 22,
    Sniper = 23,
    MortarPlus = 31,
    Pulse = 32,
    Missile = 33,
    ProducerFast = 41,
    ProducerSiege = 42,
    ProducerMedic = 43,
};

enum class SuperWeaponType : int {
    LightningStorm = 1,
    EmpBlaster = 2,
    Deflector = 3,
    EmergencyEvasion = 4,
};

enum class OperationType : int {
    BuildTower = 11,
    UpgradeTower = 12,
    DowngradeTower = 13,
    UseLightningStorm = 21,
    UseEmpBlaster = 22,
    UseDeflector = 23,
    UseEmergencyEvasion = 24,
    UpgradeGenerationSpeed = 31,
    UpgradeGeneratedAnt = 32,
};

struct TowerStats {
    int damage = 0;
    double speed = 0.0;
    int attack_range = 0;
    int max_hp = 0;
    int spawn_interval = 0;
    int support_interval = 0;
    int support_range = 0;
    double siege_spawn_chance = 0.0;
    int heal_amount = 0;
};

struct WeaponStats {
    int duration = 0;
    int attack_range = 0;
    int cooldown = 0;
    int cost = 0;
};

inline constexpr TowerStats tower_stats(TowerType type) {
    switch (type) {
    case TowerType::Basic:
        return {5, 2.0, 1, 10};
    case TowerType::Heavy:
        return {12, 2.0, 1, 15};
    case TowerType::Quick:
        return {6, 1.0, 1, 15};
    case TowerType::Mortar:
        return {12, 4.0, 2, 15};
    case TowerType::Producer:
        return {0, 0.0, 0, 15, 10};
    case TowerType::HeavyPlus:
        return {24, 2.0, 1, 15};
    case TowerType::Ice:
        return {12, 2.0, 2, 15};
    case TowerType::Bewitch:
        return {14, 2.0, 2, 15};
    case TowerType::QuickPlus:
        return {6, 0.5, 1, 15};
    case TowerType::Double:
        return {6, 2.0, 3, 15};
    case TowerType::Sniper:
        return {10, 2.0, 4, 15};
    case TowerType::MortarPlus:
        return {18, 4.0, 2, 15};
    case TowerType::Pulse:
        return {14, 4.0, 2, 15};
    case TowerType::Missile:
        return {18, 6.0, 3, 15};
    case TowerType::ProducerFast:
        return {0, 0.0, 0, 15, 8};
    case TowerType::ProducerSiege:
        return {0, 0.0, 0, 15, 10, 0, 0, 0.25};
    case TowerType::ProducerMedic:
        return {0, 0.0, 0, 15, 10, 4};
    }
    return {};
}

inline constexpr WeaponStats weapon_stats(SuperWeaponType type) {
    switch (type) {
    case SuperWeaponType::LightningStorm:
        return {15, 3, 35, 90};
    case SuperWeaponType::EmpBlaster:
        return {10, 3, 45, 135};
    case SuperWeaponType::Deflector:
        return {10, 3, 25, 60};
    case SuperWeaponType::EmergencyEvasion:
        return {1, 3, 25, 60};
    }
    return {};
}

inline constexpr int ant_max_hp(int level) {
    constexpr int values[3] = {20, 25, 25};
    return values[std::clamp(level, 0, 2)];
}

inline constexpr int ant_kill_reward(int level) {
    constexpr int values[3] = {6, 10, 14};
    return values[std::clamp(level, 0, 2)];
}

inline constexpr int ant_generation_num(int level) {
    constexpr int values[3] = {9, 4, 7};
    return values[std::clamp(level, 0, 2)];
}

inline constexpr int ant_generation_den(int level) {
    constexpr int values[3] = {2, 1, 2};
    return values[std::clamp(level, 0, 2)];
}

inline constexpr int upgrade_base_cost(int level) {
    constexpr int values[2] = {200, 250};
    return values[std::clamp(level, 0, 1)];
}

inline constexpr bool is_producer_type(TowerType type) {
    return type == TowerType::Producer || type == TowerType::ProducerFast || type == TowerType::ProducerSiege ||
           type == TowerType::ProducerMedic;
}

inline constexpr int tower_level(TowerType type) {
    if (type == TowerType::Basic) {
        return 0;
    }
    return static_cast<int>(type) < 10 ? 1 : 2;
}

inline constexpr int upgrade_tower_cost(TowerType target_type) {
    return static_cast<int>(target_type) < 10 ? kLevel2TowerUpgradeCost : kLevel3TowerUpgradeCost;
}

inline constexpr bool is_build_operation(OperationType type) {
    return type == OperationType::BuildTower;
}

inline constexpr bool is_tower_operation(OperationType type) {
    return type == OperationType::BuildTower || type == OperationType::UpgradeTower || type == OperationType::DowngradeTower;
}

inline constexpr bool is_weapon_operation(OperationType type) {
    return type == OperationType::UseLightningStorm || type == OperationType::UseEmpBlaster ||
           type == OperationType::UseDeflector || type == OperationType::UseEmergencyEvasion;
}

inline constexpr bool is_base_upgrade_operation(OperationType type) {
    return type == OperationType::UpgradeGenerationSpeed || type == OperationType::UpgradeGeneratedAnt;
}

inline constexpr SuperWeaponType operation_weapon_type(OperationType type) {
    return static_cast<SuperWeaponType>(static_cast<int>(type) % 10);
}

inline int tower_build_cost_for_count(int tower_count) {
    tower_count = std::max(tower_count, 0);
    int cost = kTowerBuildBaseCost;
    for (int index = 0; index < tower_count / 2; ++index) {
        cost *= 3;
    }
    if (tower_count % 2 == 1) {
        cost *= 2;
    }
    return cost;
}

inline int hex_distance(int x0, int y0, int x1, int y1) {
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

struct Layout {
    std::array<std::array<bool, kMapSize>, kMapSize> valid{};
    std::array<std::array<int, kMapSize>, kMapSize> owner{};
    std::array<std::array<bool, kMapSize>, kMapSize> path{};

    Layout() {
        for (auto &row : owner) {
            row.fill(-1);
        }
        constexpr int map_property[kMapSize][kMapSize] = {
            {-1, -1, -1, -1, -1, -1, -1, -1, 0, 1, 0, -1, -1, -1, -1, -1, -1, -1, -1},
            {-1, -1, -1, -1, -1, -1, 0, 0, 1, 0, 1, 0, 0, -1, -1, -1, -1, -1, -1},
            {-1, -1, -1, -1, 0, 0, 0, 1, 1, 0, 1, 1, 0, 0, 0, -1, -1, -1, -1},
            {-1, -1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, -1, -1},
            {0, 0, 2, 2, 0, 1, 0, 0, 0, 2, 0, 0, 0, 1, 0, 2, 2, 0, 0},
            {0, 0, 0, 2, 0, 0, 2, 2, 0, 2, 0, 2, 2, 0, 0, 2, 0, 0, 0},
            {0, 2, 2, 0, 2, 0, 0, 2, 0, 2, 0, 2, 0, 0, 2, 0, 2, 2, 0},
            {0, 2, 0, 0, 0, 2, 0, 0, 2, 0, 2, 0, 0, 2, 0, 0, 0, 2, 0},
            {0, 0, 2, 0, 2, 0, 0, 2, 0, 0, 0, 2, 0, 0, 2, 0, 2, 0, 0},
            {0, 1, 3, 0, 3, 1, 0, 1, 0, 1, 0, 1, 0, 1, 3, 0, 3, 1, 0},
            {0, 0, 0, 0, 0, 0, 0, 3, 3, 0, 3, 3, 0, 0, 0, 0, 0, 0, 0},
            {0, 3, 3, 0, 3, 3, 0, 0, 0, 0, 0, 0, 0, 3, 3, 0, 3, 3, 0},
            {0, 3, 0, 0, 0, 0, 3, 3, 0, 3, 0, 3, 3, 0, 0, 0, 0, 3, 0},
            {0, 0, 3, 3, 0, 0, 0, 3, 0, 3, 0, 3, 0, 0, 0, 3, 3, 0, 0},
            {-1, 0, 0, 3, 0, 1, 1, 0, 0, 3, 0, 0, 1, 1, 0, 3, 0, 0, -1},
            {-1, -1, -1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, -1, -1, -1},
            {-1, -1, -1, -1, -1, 0, 0, 1, 1, 0, 1, 1, 0, 0, -1, -1, -1, -1, -1},
            {-1, -1, -1, -1, -1, -1, -1, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1},
            {-1, -1, -1, -1, -1, -1, -1, -1, -1, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1},
        };
        for (int x = 0; x < kMapSize; ++x) {
            for (int y = 0; y < kMapSize; ++y) {
                const int cell = map_property[x][y];
                const bool is_base = (x == kPlayerBases[0].first && y == kPlayerBases[0].second) ||
                                     (x == kPlayerBases[1].first && y == kPlayerBases[1].second);
                valid[x][y] = cell != -1;
                owner[x][y] = cell == 2 ? 0 : (cell == 3 ? 1 : -1);
                path[x][y] = cell == 0 && !is_base;
            }
        }
    }
};

inline const Layout &layout() {
    static const Layout value;
    return value;
}

inline bool is_valid_pos(int x, int y) {
    if (x < 0 || x >= kMapSize || y < 0 || y >= kMapSize) {
        return false;
    }
    return layout().valid[x][y];
}

inline bool is_base_cell(int x, int y) {
    return (x == kPlayerBases[0].first && y == kPlayerBases[0].second) ||
           (x == kPlayerBases[1].first && y == kPlayerBases[1].second);
}

inline bool is_path(int x, int y) {
    return is_valid_pos(x, y) && layout().path[x][y];
}

inline bool is_ant_walkable_cell(int x, int y) {
    return is_base_cell(x, y) || is_path(x, y);
}

inline bool is_highland(int player, int x, int y) {
    return is_valid_pos(x, y) && layout().owner[x][y] == player;
}

inline std::vector<std::pair<int, int>> neighbors(int x, int y) {
    std::vector<std::pair<int, int>> out;
    out.reserve(6);
    for (int direction = 0; direction < 6; ++direction) {
        const int nx = x + kOffset[y & 1][direction][0];
        const int ny = y + kOffset[y & 1][direction][1];
        if (is_valid_pos(nx, ny)) {
            out.emplace_back(nx, ny);
        }
    }
    return out;
}

inline constexpr const std::array<std::array<std::pair<int, int>, kPositionCodeCount>, 2> &strategic_slot_order() {
    return kOldAiPositions;
}

struct Operation {
    OperationType op_type = OperationType::BuildTower;
    int arg0 = -1;
    int arg1 = -1;

    Operation() = default;
    explicit Operation(OperationType type, int a0 = -1, int a1 = -1) : op_type(type), arg0(a0), arg1(a1) {}

    std::vector<int> to_protocol_tokens() const {
        if (op_type == OperationType::BuildTower || op_type == OperationType::UseLightningStorm ||
            op_type == OperationType::UseEmpBlaster || op_type == OperationType::UseDeflector ||
            op_type == OperationType::UseEmergencyEvasion || op_type == OperationType::UpgradeTower) {
            return {static_cast<int>(op_type), arg0, arg1};
        }
        if (op_type == OperationType::DowngradeTower) {
            return {static_cast<int>(op_type), arg0};
        }
        return {static_cast<int>(op_type)};
    }
};

struct Tower {
    int tower_id = -1;
    int player = -1;
    int x = -1;
    int y = -1;
    TowerType tower_type = TowerType::Basic;
    int cooldown = 0;
    int hp = 0;

    int level() const { return tower_level(tower_type); }
    int max_hp() const { return tower_stats(tower_type).max_hp; }
    int damage() const { return tower_stats(tower_type).damage; }
    int attack_range() const { return tower_stats(tower_type).attack_range; }
    double speed() const { return tower_stats(tower_type).speed; }
    bool is_producer() const { return is_producer_type(tower_type); }

    bool is_upgrade_type_valid(TowerType target) const {
        switch (tower_type) {
        case TowerType::Basic:
            return target == TowerType::Heavy || target == TowerType::Quick || target == TowerType::Mortar ||
                   target == TowerType::Producer;
        case TowerType::Heavy:
            return target == TowerType::HeavyPlus || target == TowerType::Ice || target == TowerType::Bewitch;
        case TowerType::Quick:
            return target == TowerType::QuickPlus || target == TowerType::Double || target == TowerType::Sniper;
        case TowerType::Mortar:
            return target == TowerType::MortarPlus || target == TowerType::Pulse || target == TowerType::Missile;
        case TowerType::Producer:
            return target == TowerType::ProducerFast || target == TowerType::ProducerSiege ||
                   target == TowerType::ProducerMedic;
        default:
            return false;
        }
    }
};

struct Ant {
    int ant_id = -1;
    int player = -1;
    int x = -1;
    int y = -1;
    int hp = 0;
    int level = 0;
    int age = 0;
    AntStatus status = AntStatus::Alive;
    AntBehavior behavior = AntBehavior::Default;
    AntKind kind = AntKind::Worker;
    int last_move = -1;
    int shield = 0;
    bool defend = false;
    bool evasion_control_free_on_break = false;
    bool hidden_state_known = false;

    bool is_alive() const { return (status == AntStatus::Alive || status == AntStatus::Frozen) && hp > 0; }
    int max_hp() const { return kind == AntKind::Combat ? 30 : ant_max_hp(level); }
    int kill_reward() const { return kind == AntKind::Combat ? 18 : ant_kill_reward(level); }

    void grant_evasion(int stacks, bool grant_control_free_on_deplete) {
        if (stacks <= 0) {
            return;
        }
        hidden_state_known = true;
        shield = std::max(shield, stacks);
        evasion_control_free_on_break =
            evasion_control_free_on_break || grant_control_free_on_deplete;
    }

    void apply_damage(int damage) {
        if (damage <= 0 || !is_alive()) {
            return;
        }
        if (hidden_state_known && shield > 0) {
            --shield;
            if (shield == 0 && evasion_control_free_on_break && behavior != AntBehavior::ControlFree) {
                evasion_control_free_on_break = false;
                behavior = AntBehavior::ControlFree;
            }
            return;
        }
        if (hidden_state_known && defend && damage * 2 < max_hp()) {
            return;
        }
        hp -= damage;
        if (hp <= 0) {
            status = AntStatus::Fail;
        }
    }
};

struct Base {
    int player = -1;
    int x = -1;
    int y = -1;
    int hp = kBaseHp;
    int generation_level = 0;
    int ant_level = 0;

    bool should_spawn(int round_index) const {
        const int numerator = ant_generation_num(generation_level);
        const int denominator = ant_generation_den(generation_level);
        if (round_index == 0) {
            return true;
        }
        return (round_index * denominator) / numerator > ((round_index - 1) * denominator) / numerator;
    }
};

struct WeaponEffect {
    SuperWeaponType weapon_type = SuperWeaponType::LightningStorm;
    int player = -1;
    int x = -1;
    int y = -1;
    int remaining_turns = 0;

    bool in_range(int target_x, int target_y) const {
        return hex_distance(x, y, target_x, target_y) <= weapon_stats(weapon_type).attack_range;
    }
};

struct PublicRoundState {
    int round_index = 0;
    std::vector<Tower> towers;
    std::vector<Ant> ants;
    std::array<int, 2> coins = {kInitialCoins, kInitialCoins};
    std::array<int, 2> camps_hp = {kBaseHp, kBaseHp};
    std::array<int, 2> speed_lv = {0, 0};
    std::array<int, 2> anthp_lv = {0, 0};
    std::array<std::array<int, 5>, 2> weapon_cooldowns{};
    std::vector<WeaponEffect> active_effects;
};

class PublicState {
  public:
    uint64_t seed = 0;
    std::string movement_policy = "enhanced";
    bool cold_handle_rule_illegal = false;
    int round_index = 0;
    bool terminal = false;
    int winner = -1;
    int next_ant_id = 0;
    int next_tower_id = 0;
    std::array<int, 2> coins = {kInitialCoins, kInitialCoins};
    std::array<int, 2> old_count = {0, 0};
    std::array<int, 2> die_count = {0, 0};
    std::array<int, 2> super_weapon_usage = {0, 0};
    std::array<int, 2> ai_time = {0, 0};
    std::array<std::array<int, 5>, 2> weapon_cooldowns{};
    std::array<Base, 2> bases = {
        Base{0, kPlayerBases[0].first, kPlayerBases[0].second},
        Base{1, kPlayerBases[1].first, kPlayerBases[1].second},
    };
    std::vector<Tower> towers;
    std::vector<Ant> ants;
    std::vector<WeaponEffect> active_effects;

    PublicState() = default;
    explicit PublicState(uint64_t seed_in, std::string movement_policy_in = "enhanced", bool cold_handle_rule_illegal_in = false)
        : seed(seed_in), movement_policy(std::move(movement_policy_in)), cold_handle_rule_illegal(cold_handle_rule_illegal_in) {}

    PublicState clone() const { return *this; }

    std::vector<std::pair<int, int>> strategic_slots(int player) const {
        const auto &slots = old_ai_positions(player);
        return std::vector<std::pair<int, int>>(slots.begin(), slots.end());
    }

    int tower_count(int player) const {
        int count = 0;
        for (const auto &tower : towers) {
            if (tower.player == player) {
                ++count;
            }
        }
        return count;
    }

    std::vector<const Tower *> towers_of(int player) const {
        std::vector<const Tower *> out;
        for (const auto &tower : towers) {
            if (tower.player == player) {
                out.push_back(&tower);
            }
        }
        return out;
    }

    std::vector<const Ant *> ants_of(int player) const {
        std::vector<const Ant *> out;
        for (const auto &ant : ants) {
            if (ant.player == player && ant.is_alive()) {
                out.push_back(&ant);
            }
        }
        return out;
    }

    const Tower *tower_at(int x, int y) const {
        for (const auto &tower : towers) {
            if (tower.x == x && tower.y == y) {
                return &tower;
            }
        }
        return nullptr;
    }

    const Tower *tower_by_id(int tower_id) const {
        for (const auto &tower : towers) {
            if (tower.tower_id == tower_id) {
                return &tower;
            }
        }
        return nullptr;
    }

    int build_tower_cost(int tower_count_hint = -1) const {
        return tower_build_cost_for_count(tower_count_hint >= 0 ? tower_count_hint : tower_count(0));
    }

    int destroy_tower_income(int tower_count_hint, const Tower *tower = nullptr) const {
        double refund = static_cast<double>(build_tower_cost(tower_count_hint - 1)) * kTowerDowngradeRefundRatio;
        if (tower == nullptr) {
            return static_cast<int>(refund);
        }
        return static_cast<int>(refund * std::max(tower->hp, 0) / std::max(tower->max_hp(), 1));
    }

    int downgrade_tower_income(TowerType tower_type, const Tower *tower = nullptr) const {
        double refund = static_cast<double>(upgrade_tower_cost(tower_type)) * kTowerDowngradeRefundRatio;
        if (tower == nullptr) {
            return static_cast<int>(refund);
        }
        return static_cast<int>(refund * std::max(tower->hp, 0) / std::max(tower->max_hp(), 1));
    }

    int weapon_cost(SuperWeaponType weapon_type) const {
        return weapon_stats(weapon_type).cost;
    }

    int nearest_ant_distance(int player) const {
        const auto [base_x, base_y] = kPlayerBases[player];
        int best = 32;
        for (const auto &ant : ants) {
            if (ant.player == player || !ant.is_alive()) {
                continue;
            }
            best = std::min(best, hex_distance(ant.x, ant.y, base_x, base_y));
        }
        return best;
    }

    int frontline_distance(int player) const {
        const auto [base_x, base_y] = kPlayerBases[1 - player];
        int best = 32;
        for (const auto &ant : ants) {
            if (ant.player != player || !ant.is_alive()) {
                continue;
            }
            best = std::min(best, hex_distance(ant.x, ant.y, base_x, base_y));
        }
        return best;
    }

    int safe_coin_threshold(int player) const {
        const int enemy = 1 - player;
        const auto stats = weapon_stats(SuperWeaponType::EmpBlaster);
        const int emp_cd = weapon_cooldowns[enemy][static_cast<int>(SuperWeaponType::EmpBlaster)];
        const int enemy_coin = coins[enemy];
        const int capped_cost = std::max(stats.cost - 1, 0);
        if (emp_cd >= stats.cooldown - 10) {
            return 0;
        }
        if (emp_cd > 0) {
            return std::max(static_cast<int>(std::min(enemy_coin, capped_cost) - emp_cd * 1.66), 0);
        }
        return std::min(enemy_coin, capped_cost);
    }

    bool current_and_neighbors_empty(int x, int y) const {
        if (is_base_cell(x, y) || tower_at(x, y) != nullptr) {
            return false;
        }
        for (const auto &[nx, ny] : neighbors(x, y)) {
            if (is_base_cell(nx, ny) || tower_at(nx, ny) != nullptr) {
                return false;
            }
        }
        return true;
    }

    bool is_shielded_by_emp(int player, int x, int y) const {
        for (const auto &effect : active_effects) {
            if (effect.weapon_type == SuperWeaponType::EmpBlaster && effect.player != player && effect.in_range(x, y)) {
                return true;
            }
        }
        return false;
    }

    bool is_shielded_by_deflector(const Ant &ant) const {
        for (const auto &effect : active_effects) {
            if (effect.weapon_type == SuperWeaponType::Deflector && effect.player == ant.player &&
                effect.in_range(ant.x, ant.y)) {
                return true;
            }
        }
        return false;
    }

    const WeaponEffect *weapon_effect(SuperWeaponType weapon_type, int player) const {
        for (const auto &effect : active_effects) {
            if (effect.weapon_type == weapon_type && effect.player == player) {
                return &effect;
            }
        }
        return nullptr;
    }

    double tower_spread_score(int player) const {
        auto owned = towers_of(player);
        if (owned.size() < 2) {
            return 0.0;
        }
        double penalty = 0.0;
        for (std::size_t i = 0; i + 1 < owned.size(); ++i) {
            for (std::size_t j = i + 1; j < owned.size(); ++j) {
                const int distance = hex_distance(owned[i]->x, owned[i]->y, owned[j]->x, owned[j]->y);
                if (distance <= 3) {
                    penalty += 5.0;
                } else if (distance <= 6) {
                    penalty += 2.0;
                }
            }
        }
        return -penalty;
    }

    double slot_priority(int player, int x, int y) const {
        const int order = old_ai_position_code_at(player, x, y);
        const int bounded_order = order >= 0 ? order : kPositionCodeCount;
        double priority = std::max(0.0, 24.0 - static_cast<double>(bounded_order) * 0.6);
        priority *= centerline_slot_weight(bounded_order);
        const auto [base_x, base_y] = kPlayerBases[player];
        priority += static_cast<double>(hex_distance(x, y, base_x, base_y)) * 0.4;
        return priority;
    }

    int operation_income(int player, const Operation &operation, int tower_count_hint = -1) const {
        switch (operation.op_type) {
        case OperationType::BuildTower:
            return -build_tower_cost(tower_count_hint >= 0 ? tower_count_hint : tower_count(player));
        case OperationType::UpgradeTower:
            return -upgrade_tower_cost(static_cast<TowerType>(operation.arg1));
        case OperationType::DowngradeTower: {
            const Tower *tower = tower_by_id(operation.arg0);
            if (tower == nullptr) {
                return 0;
            }
            if (tower->tower_type == TowerType::Basic) {
                return destroy_tower_income(tower_count_hint >= 0 ? tower_count_hint : tower_count(player), tower);
            }
            return downgrade_tower_income(tower->tower_type, tower);
        }
        case OperationType::UpgradeGenerationSpeed:
            return -upgrade_base_cost(bases[player].generation_level);
        case OperationType::UpgradeGeneratedAnt:
            return -upgrade_base_cost(bases[player].ant_level);
        case OperationType::UseLightningStorm:
        case OperationType::UseEmpBlaster:
        case OperationType::UseDeflector:
        case OperationType::UseEmergencyEvasion:
            return -weapon_cost(operation_weapon_type(operation.op_type));
        }
        return 0;
    }

    bool can_apply_operation(int player, const Operation &operation, const std::vector<Operation> &pending = {}) const {
        if (operation.op_type == OperationType::BuildTower) {
            if (!is_highland(player, operation.arg0, operation.arg1)) {
                return false;
            }
            if (is_base_cell(operation.arg0, operation.arg1) || tower_at(operation.arg0, operation.arg1) != nullptr) {
                return false;
            }
            if (is_shielded_by_emp(player, operation.arg0, operation.arg1)) {
                return false;
            }
            for (const auto &item : pending) {
                if (item.op_type == OperationType::BuildTower && item.arg0 == operation.arg0 && item.arg1 == operation.arg1) {
                    return false;
                }
            }
        } else if (operation.op_type == OperationType::UpgradeTower) {
            const Tower *tower = tower_by_id(operation.arg0);
            if (tower == nullptr || tower->player != player) {
                return false;
            }
            if (is_shielded_by_emp(player, tower->x, tower->y)) {
                return false;
            }
            if (!tower->is_upgrade_type_valid(static_cast<TowerType>(operation.arg1))) {
                return false;
            }
            for (const auto &item : pending) {
                if ((item.op_type == OperationType::UpgradeTower || item.op_type == OperationType::DowngradeTower) &&
                    item.arg0 == operation.arg0) {
                    return false;
                }
            }
        } else if (operation.op_type == OperationType::DowngradeTower) {
            const Tower *tower = tower_by_id(operation.arg0);
            if (tower == nullptr || tower->player != player) {
                return false;
            }
            if (is_shielded_by_emp(player, tower->x, tower->y)) {
                return false;
            }
            for (const auto &item : pending) {
                if ((item.op_type == OperationType::UpgradeTower || item.op_type == OperationType::DowngradeTower) &&
                    item.arg0 == operation.arg0) {
                    return false;
                }
            }
        } else if (is_weapon_operation(operation.op_type)) {
            if (!is_valid_pos(operation.arg0, operation.arg1)) {
                return false;
            }
            const auto weapon_type = operation_weapon_type(operation.op_type);
            if (weapon_cooldowns[player][static_cast<int>(weapon_type)] > 0) {
                return false;
            }
            for (const auto &item : pending) {
                if (item.op_type == operation.op_type) {
                    return false;
                }
            }
        } else if (operation.op_type == OperationType::UpgradeGenerationSpeed) {
            if (bases[player].generation_level >= 2) {
                return false;
            }
            for (const auto &item : pending) {
                if (is_base_upgrade_operation(item.op_type)) {
                    return false;
                }
            }
        } else if (operation.op_type == OperationType::UpgradeGeneratedAnt) {
            if (bases[player].ant_level >= 2) {
                return false;
            }
            for (const auto &item : pending) {
                if (is_base_upgrade_operation(item.op_type)) {
                    return false;
                }
            }
        } else {
            return false;
        }

        int income = 0;
        int simulated_tower_count = tower_count(player);
        for (const auto &item : pending) {
            if (item.op_type == OperationType::BuildTower) {
                income -= build_tower_cost(simulated_tower_count);
                ++simulated_tower_count;
            } else if (item.op_type == OperationType::DowngradeTower) {
                const Tower *tower = tower_by_id(item.arg0);
                if (tower == nullptr) {
                    continue;
                }
                if (tower->tower_type == TowerType::Basic) {
                    income += destroy_tower_income(simulated_tower_count, tower);
                    --simulated_tower_count;
                } else {
                    income += downgrade_tower_income(tower->tower_type, tower);
                }
            } else {
                income += operation_income(player, item, simulated_tower_count);
            }
        }
        if (operation.op_type == OperationType::BuildTower) {
            income -= build_tower_cost(simulated_tower_count);
        } else if (operation.op_type == OperationType::DowngradeTower) {
            const Tower *tower = tower_by_id(operation.arg0);
            if (tower != nullptr) {
                if (tower->tower_type == TowerType::Basic) {
                    income += destroy_tower_income(simulated_tower_count, tower);
                } else {
                    income += downgrade_tower_income(tower->tower_type, tower);
                }
            }
        } else {
            income += operation_income(player, operation, simulated_tower_count);
        }
        return coins[player] + income >= 0;
    }

    bool can_apply_operation_sequential(
        int player,
        const Operation &operation,
        const std::vector<int> &used_towers,
        bool base_upgraded) const {
        if ((operation.op_type == OperationType::UpgradeTower || operation.op_type == OperationType::DowngradeTower) &&
            std::find(used_towers.begin(), used_towers.end(), operation.arg0) != used_towers.end()) {
            return false;
        }
        if (is_base_upgrade_operation(operation.op_type) && base_upgraded) {
            return false;
        }
        return can_apply_operation(player, operation);
    }

    void record_operation_turn_usage(
        const Operation &operation,
        int built_tower_id,
        std::vector<int> &used_towers,
        bool &base_upgraded) const {
        if (operation.op_type == OperationType::BuildTower) {
            used_towers.push_back(built_tower_id);
        } else if (operation.op_type == OperationType::UpgradeTower ||
                   operation.op_type == OperationType::DowngradeTower) {
            used_towers.push_back(operation.arg0);
        }
        if (is_base_upgrade_operation(operation.op_type)) {
            base_upgraded = true;
        }
    }

    void apply_lightning_storm_now(int player, const WeaponEffect &effect) {
        for (auto &ant : ants) {
            if (ant.player == player || !effect.in_range(ant.x, ant.y)) {
                continue;
            }
            ant.apply_damage(kLightningStormAntDamage);
        }
    }

    void apply_emergency_evasion_now(int player, const WeaponEffect &effect) {
        for (auto &ant : ants) {
            if (ant.player != player || !effect.in_range(ant.x, ant.y)) {
                continue;
            }
            ant.grant_evasion(2, true);
        }
    }

    void apply_operation(int player, const Operation &operation) {
        coins[player] += operation_income(player, operation);
        switch (operation.op_type) {
        case OperationType::BuildTower:
            towers.push_back(Tower{next_tower_id++, player, operation.arg0, operation.arg1, TowerType::Basic, 2, 10});
            return;
        case OperationType::UpgradeTower:
            for (auto &tower : towers) {
                if (tower.tower_id == operation.arg0) {
                    tower.tower_type = static_cast<TowerType>(operation.arg1);
                    tower.cooldown = tower.is_producer() ? tower_stats(tower.tower_type).spawn_interval
                                                         : static_cast<int>(tower_stats(tower.tower_type).speed);
                    tower.hp = tower.max_hp();
                    return;
                }
            }
            return;
        case OperationType::DowngradeTower:
            for (std::size_t index = 0; index < towers.size(); ++index) {
                if (towers[index].tower_id != operation.arg0) {
                    continue;
                }
                if (towers[index].tower_type == TowerType::Basic) {
                    towers.erase(towers.begin() + static_cast<long>(index));
                    return;
                }
                const int previous_max_hp = towers[index].max_hp();
                const int previous_hp = std::max(towers[index].hp, 0);
                towers[index].tower_type = static_cast<TowerType>(static_cast<int>(towers[index].tower_type) / 10);
                const int downgraded_max_hp = towers[index].max_hp();
                towers[index].hp = previous_max_hp > 0 ? std::max(1, (downgraded_max_hp * previous_hp + previous_max_hp - 1) / previous_max_hp)
                                                       : downgraded_max_hp;
                towers[index].cooldown = towers[index].is_producer() ? tower_stats(towers[index].tower_type).spawn_interval
                                                                     : static_cast<int>(tower_stats(towers[index].tower_type).speed);
                return;
            }
            return;
        case OperationType::UpgradeGenerationSpeed:
            ++bases[player].generation_level;
            return;
        case OperationType::UpgradeGeneratedAnt:
            ++bases[player].ant_level;
            return;
        case OperationType::UseLightningStorm:
        case OperationType::UseEmpBlaster:
        case OperationType::UseDeflector:
        case OperationType::UseEmergencyEvasion: {
            const auto weapon_type = operation_weapon_type(operation.op_type);
            weapon_cooldowns[player][static_cast<int>(weapon_type)] = weapon_stats(weapon_type).cooldown;
            ++super_weapon_usage[player];
            WeaponEffect effect{weapon_type, player, operation.arg0, operation.arg1, weapon_stats(weapon_type).duration};
            if (weapon_type == SuperWeaponType::LightningStorm) {
                apply_lightning_storm_now(player, effect);
            } else if (weapon_type == SuperWeaponType::EmergencyEvasion) {
                apply_emergency_evasion_now(player, effect);
            }
            active_effects.push_back(effect);
            return;
        }
        }
    }

    std::vector<Operation> apply_operation_list(int player, const std::vector<Operation> &operations) {
        std::vector<Operation> illegal;
        std::vector<int> used_towers;
        bool base_upgraded = false;
        for (const auto &operation : operations) {
            const int built_tower_id = next_tower_id;
            if (can_apply_operation_sequential(player, operation, used_towers, base_upgraded)) {
                apply_operation(player, operation);
                record_operation_turn_usage(operation, built_tower_id, used_towers, base_upgraded);
            } else {
                illegal.push_back(operation);
                if (!cold_handle_rule_illegal) {
                    terminal = true;
                    winner = 1 - player;
                    break;
                }
            }
        }
        return illegal;
    }

    PublicRoundState to_public_round_state() const {
        PublicRoundState out;
        out.round_index = round_index;
        out.towers = towers;
        out.ants = ants;
        out.coins = coins;
        out.camps_hp = {bases[0].hp, bases[1].hp};
        out.speed_lv = {bases[0].generation_level, bases[1].generation_level};
        out.anthp_lv = {bases[0].ant_level, bases[1].ant_level};
        out.weapon_cooldowns = weapon_cooldowns;
        out.active_effects = active_effects;
        std::sort(out.towers.begin(), out.towers.end(), [](const Tower &lhs, const Tower &rhs) { return lhs.tower_id < rhs.tower_id; });
        std::sort(out.ants.begin(), out.ants.end(), [](const Ant &lhs, const Ant &rhs) { return lhs.ant_id < rhs.ant_id; });
        return out;
    }

    void sync_public_round_state(const PublicRoundState &public_state) {
        round_index = public_state.round_index;
        coins = public_state.coins;
        bases[0].hp = public_state.camps_hp[0];
        bases[1].hp = public_state.camps_hp[1];
        bases[0].generation_level = public_state.speed_lv[0];
        bases[1].generation_level = public_state.speed_lv[1];
        bases[0].ant_level = public_state.anthp_lv[0];
        bases[1].ant_level = public_state.anthp_lv[1];
        towers = public_state.towers;
        ants = public_state.ants;
        weapon_cooldowns = public_state.weapon_cooldowns;
        active_effects = public_state.active_effects;
        next_tower_id = 0;
        next_ant_id = 0;
        for (const auto &tower : towers) {
            next_tower_id = std::max(next_tower_id, tower.tower_id + 1);
        }
        for (const auto &ant : ants) {
            next_ant_id = std::max(next_ant_id, ant.ant_id + 1);
        }
    }
};

struct InitInfo {
    int player = 0;
    int seed = 0;
};

class ProtocolIO {
  public:
    ProtocolIO(std::istream &input = std::cin, std::ostream &output = std::cout, std::ostream &error = std::cerr)
        : in_(input), out_(output), err_(error) {}

    InitInfo recv_init() {
        const std::string line = recv_line();
        InitInfo out;
        if (std::sscanf(line.c_str(), "%d %d", &out.player, &out.seed) != 2) {
            throw std::runtime_error("invalid init line");
        }
        return out;
    }

    std::vector<Operation> recv_operations() {
        const std::string count_line = recv_line();
        if (count_line.empty() && in_.eof()) {
            throw std::runtime_error("missing operation count");
        }
        const int count = std::stoi(count_line);
        std::vector<Operation> operations;
        operations.reserve(std::max(count, 0));
        for (int index = 0; index < count; ++index) {
            const std::string line = recv_line();
            int type = -1;
            int arg0 = -1;
            int arg1 = -1;
            const int matched = std::sscanf(line.c_str(), "%d %d %d", &type, &arg0, &arg1);
            if (matched <= 0) {
                throw std::runtime_error("invalid operation line");
            }
            if (matched == 1) {
                operations.emplace_back(static_cast<OperationType>(type));
            } else if (matched == 2) {
                operations.emplace_back(static_cast<OperationType>(type), arg0);
            } else {
                operations.emplace_back(static_cast<OperationType>(type), arg0, arg1);
            }
        }
        return operations;
    }

    bool recv_round_state(PublicRoundState &state) {
        std::string line;
        if (!std::getline(in_, line)) {
            return false;
        }
        state = PublicRoundState{};
        state.round_index = std::stoi(line);

        const int tower_count = std::stoi(recv_line());
        state.towers.reserve(std::max(tower_count, 0));
        for (int index = 0; index < tower_count; ++index) {
            int tower_id = -1;
            int player = -1;
            int x = -1;
            int y = -1;
            int tower_type = 0;
            int cooldown = 0;
            int hp = 0;
            const std::string row = recv_line();
            const int matched = std::sscanf(row.c_str(), "%d %d %d %d %d %d %d", &tower_id, &player, &x, &y, &tower_type, &cooldown, &hp);
            if (matched < 6) {
                throw std::runtime_error("invalid tower row");
            }
            state.towers.push_back(Tower{
                tower_id,
                player,
                x,
                y,
                static_cast<TowerType>(tower_type),
                cooldown,
                matched >= 7 ? hp : tower_stats(static_cast<TowerType>(tower_type)).max_hp,
            });
        }

        const int ant_count = std::stoi(recv_line());
        state.ants.reserve(std::max(ant_count, 0));
        for (int index = 0; index < ant_count; ++index) {
            int ant_id = -1;
            int player = -1;
            int x = -1;
            int y = -1;
            int hp = 0;
            int level = 0;
            int age = 0;
            int status = 0;
            int behavior = 0;
            int kind = 0;
            const std::string row = recv_line();
            const int matched = std::sscanf(row.c_str(), "%d %d %d %d %d %d %d %d %d %d",
                                            &ant_id, &player, &x, &y, &hp, &level, &age, &status, &behavior, &kind);
            if (matched < 8) {
                throw std::runtime_error("invalid ant row");
            }
            state.ants.push_back(Ant{
                ant_id,
                player,
                x,
                y,
                hp,
                level,
                age,
                static_cast<AntStatus>(status),
                matched >= 9 ? static_cast<AntBehavior>(behavior) : AntBehavior::Default,
                matched >= 10 ? static_cast<AntKind>(kind) : AntKind::Worker,
            });
        }

        {
            int coin0 = 0;
            int coin1 = 0;
            if (std::sscanf(recv_line().c_str(), "%d %d", &coin0, &coin1) != 2) {
                throw std::runtime_error("invalid coin row");
            }
            state.coins = {coin0, coin1};
        }
        {
            int camp0 = 0;
            int camp1 = 0;
            int speed0 = 0;
            int speed1 = 0;
            int ant0 = 0;
            int ant1 = 0;
            const std::string row = recv_line();
            const int matched = std::sscanf(row.c_str(), "%d %d %d %d %d %d", &camp0, &camp1, &speed0, &speed1, &ant0, &ant1);
            if (matched < 2) {
                throw std::runtime_error("invalid camp row");
            }
            state.camps_hp = {camp0, camp1};
            if (matched >= 4) {
                state.speed_lv = {speed0, speed1};
            }
            if (matched >= 6) {
                state.anthp_lv = {ant0, ant1};
            }
        }
        const int cooldown_rows = std::stoi(recv_line());
        for (int row_index = 0; row_index < cooldown_rows && row_index < 2; ++row_index) {
            int v0 = 0;
            int v1 = 0;
            int v2 = 0;
            int v3 = 0;
            int v4 = 0;
            const std::string row = recv_line();
            const int matched = std::sscanf(row.c_str(), "%d %d %d %d %d", &v0, &v1, &v2, &v3, &v4);
            if (matched < 4) {
                throw std::runtime_error("invalid cooldown row");
            }
            if (matched == 4) {
                state.weapon_cooldowns[row_index] = {0, v0, v1, v2, v3};
            } else {
                state.weapon_cooldowns[row_index] = {v0, v1, v2, v3, v4};
            }
        }
        const int effect_count = std::stoi(recv_line());
        state.active_effects.reserve(std::max(effect_count, 0));
        for (int index = 0; index < effect_count; ++index) {
            int type = 0;
            int player = -1;
            int x = -1;
            int y = -1;
            int remaining = 0;
            if (std::sscanf(recv_line().c_str(), "%d %d %d %d %d", &type, &player, &x, &y, &remaining) != 5) {
                throw std::runtime_error("invalid effect row");
            }
            state.active_effects.push_back(WeaponEffect{static_cast<SuperWeaponType>(type), player, x, y, remaining});
        }
        return true;
    }

    void send_operations(const std::vector<Operation> &operations) {
        std::string payload = std::to_string(static_cast<int>(operations.size())) + "\n";
        for (const auto &operation : operations) {
            const auto tokens = operation.to_protocol_tokens();
            for (std::size_t index = 0; index < tokens.size(); ++index) {
                if (index > 0) {
                    payload.push_back(' ');
                }
                payload += std::to_string(tokens[index]);
            }
            payload.push_back('\n');
        }

        const uint32_t size = static_cast<uint32_t>(payload.size());
        const unsigned char header[4] = {
            static_cast<unsigned char>((size >> 24) & 0xFF),
            static_cast<unsigned char>((size >> 16) & 0xFF),
            static_cast<unsigned char>((size >> 8) & 0xFF),
            static_cast<unsigned char>(size & 0xFF),
        };
        out_.write(reinterpret_cast<const char *>(header), 4);
        out_.write(payload.data(), static_cast<std::streamsize>(payload.size()));
        out_.flush();
    }

    void log(const std::string &message) {
        err_ << "[cpp_sdk] " << message << '\n';
        err_.flush();
    }

  private:
    std::string recv_line() {
        std::string line;
        if (!std::getline(in_, line)) {
            throw std::runtime_error("unexpected EOF");
        }
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        return line;
    }

    std::istream &in_;
    std::ostream &out_;
    std::ostream &err_;
};

} // namespace antgame::sdk
