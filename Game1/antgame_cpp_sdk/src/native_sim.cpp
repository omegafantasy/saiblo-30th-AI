#include "antgame_sdk/native_sim.hpp"

#include <algorithm>
#include <any>
#include <array>
#include <cmath>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#define private public
#include "../../Ant-Game/game/include/game.hpp"
#undef private

namespace sdk = antgame::sdk;

namespace {

constexpr int kInitialCoin = 50;
constexpr int kSpecialBehaviorDecayTurns = 5;
constexpr std::uint64_t kRngMask = (1ULL << 48) - 1;
constexpr std::uint64_t kRngMultiplier = 25214903917ULL;

::Operation to_game_operation(const sdk::Operation &operation) {
    switch (operation.op_type) {
    case sdk::OperationType::BuildTower:
    case sdk::OperationType::UseLightningStorm:
    case sdk::OperationType::UseEmpBlaster:
    case sdk::OperationType::UseDeflector:
    case sdk::OperationType::UseEmergencyEvasion:
        return ::Operation(static_cast<int>(operation.op_type), -1, -1, operation.arg0, operation.arg1);
    case sdk::OperationType::UpgradeTower:
        return ::Operation(static_cast<int>(operation.op_type), operation.arg0, operation.arg1, -1, -1);
    case sdk::OperationType::DowngradeTower:
        return ::Operation(static_cast<int>(operation.op_type), operation.arg0, -1, -1, -1);
    case sdk::OperationType::UpgradeGenerationSpeed:
    case sdk::OperationType::UpgradeGeneratedAnt:
        return ::Operation(static_cast<int>(operation.op_type), -1, -1, -1, -1);
    }
    return ::Operation();
}

int default_behavior_expiry(Ant::Behavior behavior) {
    switch (behavior) {
    case Ant::Behavior::Conservative:
    case Ant::Behavior::Bewitched:
    case Ant::Behavior::ControlFree:
        return kSpecialBehaviorDecayTurns;
    default:
        return 0;
    }
}

int tower_build_cost_for_count(int tower_count) {
    tower_count = std::max(tower_count, 0);
    int cost = 15;
    for (int index = 0; index < tower_count / 2; ++index) {
        cost *= 3;
    }
    if (tower_count % 2 == 1) {
        cost *= 2;
    }
    return cost;
}

void reset_items(Game &game) {
    for (int player = 0; player < 2; ++player) {
        game.item[player].clear();
        for (int index = 0; index < ItemType::Count; ++index) {
            game.item[player].emplace_back(0, 0, 0, 0);
        }
    }
}

void rewire_map(Game &game) {
    for (int x = 0; x < MAP_SIZE; ++x) {
        for (int y = 0; y < MAP_SIZE; ++y) {
            game.map.map[x][y].tower = nullptr;
            game.map.map[x][y].base_camp = nullptr;
        }
    }
    game.map.map[PLAYER_0_BASE_CAMP_X][PLAYER_0_BASE_CAMP_Y].base_camp = &game.base_camp0;
    game.map.map[PLAYER_1_BASE_CAMP_X][PLAYER_1_BASE_CAMP_Y].base_camp = &game.base_camp1;
    for (auto &tower : game.defensive_towers) {
        if (tower.destroy()) {
            continue;
        }
        game.map.map[tower.get_x()][tower.get_y()].tower = &tower;
    }
}

Game::MovementPolicy parse_movement_policy_name(const std::string &policy_name) {
    if (policy_name == "legacy") {
        return Game::MovementPolicy::Legacy;
    }
    return Game::MovementPolicy::Enhanced;
}

void init_game(Game &game, unsigned long long seed, Game::MovementPolicy movement_policy, bool cold_handle_rule_illegal) {
    game.is_end = false;
    game.winner = -1;
    game.round = 0;
    game.ant_id = 0;
    game.barrack_id = 0;
    game.tower_id = 0;
    game.err_msg.clear();
    game.random_seed = seed;
    game.movement_policy = movement_policy;
    game.cold_handle_rule_illegal = cold_handle_rule_illegal;
    game.enhanced_move_phase_active = false;
    game.enhanced_move_cache_dirty = true;
    game.rng_state = (seed ^ kRngMultiplier) & kRngMask;
    game.record_file.clear();
    game.player0 = Player();
    game.player1 = Player();
    game.player0.ant_target_x = PLAYER_1_BASE_CAMP_X;
    game.player0.ant_target_y = PLAYER_1_BASE_CAMP_Y;
    game.player1.ant_target_x = PLAYER_0_BASE_CAMP_X;
    game.player1.ant_target_y = PLAYER_0_BASE_CAMP_Y;
    game.player0.coin.coin = kInitialCoin;
    game.player1.coin.coin = kInitialCoin;
    game.player0.coin.basic_income = 3;
    game.player1.coin.basic_income = 3;
    game.player0.coin.tower_building_price = tower_build_cost_for_count(0);
    game.player1.coin.tower_building_price = tower_build_cost_for_count(0);
    game.player0.coin.penalty = 0;
    game.player1.coin.penalty = 0;
    game.map = Map();
    game.map.init_pheromon(seed);
    game.base_camp0 = Headquarter(PLAYER_0_BASE_CAMP_X, PLAYER_0_BASE_CAMP_Y, 0, 0, 0, 50);
    game.base_camp1 = Headquarter(PLAYER_1_BASE_CAMP_X, PLAYER_1_BASE_CAMP_Y, 1, 0, 0, 50);
    game.defensive_towers.clear();
    game.ants.clear();
    game.op[0].clear();
    game.op[1].clear();
    reset_items(game);
    game.state[0] = Game::AI_state::OK;
    game.state[1] = Game::AI_state::OK;
    rewire_map(game);
}

int tower_level_from_type(::TowerType tower_type) {
    if (tower_type == ::TowerType::Basic) {
        return 0;
    }
    return static_cast<int>(tower_type) < 10 ? 1 : 2;
}

int display_cooldown_to_round(const DefenseTower &tower, int cooldown) {
    const int speed = static_cast<int>(std::llround(tower.get_spd()));
    if (tower.get_spd() < 1.0) {
        return 0;
    }
    return std::max(0, speed - cooldown);
}

sdk::Tower to_sdk_tower(const DefenseTower &tower) {
    return sdk::Tower{
        tower.get_id(),
        tower.get_player(),
        tower.get_x(),
        tower.get_y(),
        static_cast<sdk::TowerType>(static_cast<int>(tower.get_type())),
        tower.get_cd(),
        tower.get_hp(),
    };
}

sdk::Ant to_sdk_ant(const Ant &ant) {
    return sdk::Ant{
        ant.get_id(),
        ant.get_player(),
        ant.get_x(),
        ant.get_y(),
        ant.get_hp(),
        ant.get_level(),
        ant.get_age(),
        static_cast<sdk::AntStatus>(static_cast<int>(ant.get_status())),
        static_cast<sdk::AntBehavior>(static_cast<int>(ant.get_behavior())),
        static_cast<sdk::AntKind>(static_cast<int>(ant.get_kind())),
        ant.get_last_move(),
    };
}

sdk::WeaponEffect to_sdk_effect(const Item &item, int item_type, int player) {
    return sdk::WeaponEffect{
        static_cast<sdk::SuperWeaponType>(item_type + 1),
        player,
        item.x,
        item.y,
        item.duration,
    };
}

void sync_terminal(Game &game, bool &terminal, int &winner) {
    terminal = game.is_end;
    winner = terminal ? game.winner : -1;
}

} // namespace

struct sdk::NativeSimulator::Impl {
    Game game;
    bool terminal_flag = false;
    int winner_value = -1;
    unsigned long long seed_value = 0;
    bool cold_handle_rule_illegal_value = false;
    std::string movement_policy_value = "enhanced";
    std::array<int, 2> old_count_value = {0, 0};

    Impl(unsigned long long init_seed, std::string movement_policy_in, bool cold_handle_rule_illegal_in)
        : seed_value(init_seed),
          cold_handle_rule_illegal_value(cold_handle_rule_illegal_in),
          movement_policy_value(std::move(movement_policy_in)) {
        init_game(game, seed_value, parse_movement_policy_name(movement_policy_value), cold_handle_rule_illegal_value);
        sync_terminal(game, terminal_flag, winner_value);
    }

    Impl(const Impl &other)
        : game(other.game),
          terminal_flag(other.terminal_flag),
          winner_value(other.winner_value),
          seed_value(other.seed_value),
          cold_handle_rule_illegal_value(other.cold_handle_rule_illegal_value),
          movement_policy_value(other.movement_policy_value),
          old_count_value(other.old_count_value) {
        rewire_map(game);
    }

    sdk::PublicRoundState to_public_round_state() const {
        sdk::PublicRoundState out;
        out.round_index = game.round;
        out.coins = {game.player0.coin.get_coin(), game.player1.coin.get_coin()};
        out.camps_hp = {game.base_camp0.get_hp(), game.base_camp1.get_hp()};
        out.speed_lv = {game.base_camp0.get_cd_level(), game.base_camp1.get_cd_level()};
        out.anthp_lv = {game.base_camp0.get_ant_level(), game.base_camp1.get_ant_level()};

        out.towers.reserve(game.defensive_towers.size());
        for (const auto &tower : game.defensive_towers) {
            if (tower.destroy()) {
                continue;
            }
            out.towers.push_back(to_sdk_tower(tower));
        }
        std::sort(out.towers.begin(), out.towers.end(), [](const sdk::Tower &lhs, const sdk::Tower &rhs) {
            return lhs.tower_id < rhs.tower_id;
        });

        out.ants.reserve(game.ants.size());
        for (const auto &ant : game.ants) {
            out.ants.push_back(to_sdk_ant(ant));
        }
        std::sort(out.ants.begin(), out.ants.end(), [](const sdk::Ant &lhs, const sdk::Ant &rhs) {
            return lhs.ant_id < rhs.ant_id;
        });

        for (int player = 0; player < 2; ++player) {
            for (int item = 0; item < ItemType::Count; ++item) {
                out.weapon_cooldowns[player][item + 1] = game.item[player][item].cd;
                if (game.item[player][item].duration > 0) {
                    out.active_effects.push_back(to_sdk_effect(game.item[player][item], item, player));
                }
            }
        }
        std::sort(out.active_effects.begin(), out.active_effects.end(), [](const sdk::WeaponEffect &lhs, const sdk::WeaponEffect &rhs) {
            return std::tie(lhs.player, lhs.x, lhs.y, lhs.remaining_turns, lhs.weapon_type) <
                   std::tie(rhs.player, rhs.x, rhs.y, rhs.remaining_turns, rhs.weapon_type);
        });
        return out;
    }

    std::vector<sdk::NativeAntHiddenState> ant_hidden_states() const {
        std::vector<sdk::NativeAntHiddenState> out;
        out.reserve(game.ants.size());
        for (const auto &ant : game.ants) {
            out.push_back(sdk::NativeAntHiddenState{
                ant.get_id(),
                ant.shield,
                ant.defend,
                ant.evasion_control_free_on_break,
                ant.is_frozen || ant.all_frozen,
                ant.behavior_rounds,
                ant.behavior_expiry,
                ant.target_x,
                ant.target_y,
                ant.has_pending_behavior,
                static_cast<sdk::AntBehavior>(static_cast<int>(ant.pending_behavior)),
            });
        }
        std::sort(out.begin(), out.end(), [](const sdk::NativeAntHiddenState &lhs, const sdk::NativeAntHiddenState &rhs) {
            return lhs.ant_id < rhs.ant_id;
        });
        return out;
    }

    std::vector<sdk::Operation> apply_operation_list(int player_id, const std::vector<sdk::Operation> &operations) {
        std::vector<sdk::Operation> illegal;
        illegal.reserve(operations.size());
        std::unordered_set<int> used_towers;
        bool base_upgraded = false;
        sdk::PublicState mirror(seed_value, movement_policy_value, cold_handle_rule_illegal_value);
        mirror.sync_public_round_state(to_public_round_state());
        for (const auto &operation : operations) {
            if ((operation.op_type == sdk::OperationType::UpgradeTower ||
                 operation.op_type == sdk::OperationType::DowngradeTower) &&
                used_towers.find(operation.arg0) != used_towers.end()) {
                illegal.push_back(operation);
                if (!cold_handle_rule_illegal_value) {
                    game.is_end = true;
                    game.winner = 1 - player_id;
                    break;
                }
                continue;
            }
            if (sdk::is_base_upgrade_operation(operation.op_type) && base_upgraded) {
                illegal.push_back(operation);
                if (!cold_handle_rule_illegal_value) {
                    game.is_end = true;
                    game.winner = 1 - player_id;
                    break;
                }
                continue;
            }
            if (!mirror.can_apply_operation(player_id, operation)) {
                illegal.push_back(operation);
                if (!cold_handle_rule_illegal_value) {
                    game.is_end = true;
                    game.winner = 1 - player_id;
                    break;
                }
                continue;
            }

            const int pending_tower_id = game.tower_id;
            std::string err_msg;
            Game::OperationErrorKind error_kind = Game::OperationErrorKind::None;
            if (!game.apply_operation(std::vector<::Operation>{to_game_operation(operation)}, player_id, err_msg, &error_kind)) {
                illegal.push_back(operation);
                if (error_kind == Game::OperationErrorKind::Protocol || !cold_handle_rule_illegal_value) {
                    game.is_end = true;
                    game.winner = 1 - player_id;
                    break;
                }
                continue;
            }

            if (operation.op_type == sdk::OperationType::BuildTower) {
                used_towers.insert(pending_tower_id);
            } else if (operation.op_type == sdk::OperationType::UpgradeTower ||
                       operation.op_type == sdk::OperationType::DowngradeTower) {
                used_towers.insert(operation.arg0);
            }
            if (sdk::is_base_upgrade_operation(operation.op_type)) {
                base_upgraded = true;
            }
            mirror.apply_operation_list(player_id, std::vector<sdk::Operation>{operation});
        }
        sync_terminal(game, terminal_flag, winner_value);
        return illegal;
    }

    sdk::ResolveResult advance_round() {
        if (!game.is_end) {
            game.next_round();
        }
        sync_terminal(game, terminal_flag, winner_value);
        sdk::ResolveResult out;
        out.terminal = terminal_flag;
        out.winner = winner_value;
        return out;
    }

    void sync_public_round_state(const sdk::PublicRoundState &state) {
        const std::unordered_map<int, ::Ant> previous_ants = [&]() {
            std::unordered_map<int, ::Ant> ants_by_id;
            for (const auto &ant : game.ants) {
                ants_by_id.emplace(ant.get_id(), ant);
            }
            return ants_by_id;
        }();

        game.round = state.round_index;
        game.player0.coin.coin = state.coins[0];
        game.player1.coin.coin = state.coins[1];
        game.base_camp0.hp = state.camps_hp[0];
        game.base_camp1.hp = state.camps_hp[1];
        game.base_camp0.cd_level = state.speed_lv[0];
        game.base_camp1.cd_level = state.speed_lv[1];
        game.base_camp0.ant_level = state.anthp_lv[0];
        game.base_camp1.ant_level = state.anthp_lv[1];

        game.defensive_towers.clear();
        std::array<int, 2> tower_counts = {0, 0};
        int max_tower_id = 0;
        for (const auto &row : state.towers) {
            game.defensive_towers.emplace_back(row.x, row.y, row.player, row.tower_id, 0);
            auto &tower = game.defensive_towers.back();
            const auto native_type = static_cast<::TowerType>(static_cast<int>(row.tower_type));
            if (native_type != ::TowerType::Basic) {
                tower.upgrade(native_type);
            }
            tower.level = tower_level_from_type(native_type);
            tower.round = display_cooldown_to_round(tower, row.cooldown);
            tower.hp = row.hp;
            tower.changed = false;
            tower.attacked_ants.clear();
            if (row.player >= 0 && row.player < 2) {
                ++tower_counts[row.player];
            }
            max_tower_id = std::max(max_tower_id, row.tower_id + 1);
        }
        game.tower_id = max_tower_id;
        game.player0.coin.tower_building_price = tower_build_cost_for_count(tower_counts[0]);
        game.player1.coin.tower_building_price = tower_build_cost_for_count(tower_counts[1]);

        game.ants.clear();
        int max_ant_id = 0;
        for (const auto &row : state.ants) {
            const auto kind = static_cast<::Ant::Kind>(static_cast<int>(row.kind));
            game.ants.emplace_back(row.player, row.ant_id, row.x, row.y, row.level, kind);
            auto &ant = game.ants.back();
            auto it = previous_ants.find(row.ant_id);
            if (it != previous_ants.end()) {
                ant.trail_cells = it->second.trail_cells;
                ant.last_move = it->second.last_move;
                ant.path_len_total = it->second.path_len_total;
                ant.age = row.age;
                ant.shield = it->second.shield;
                ant.defend = it->second.defend;
                ant.evasion = it->second.evasion;
            } else {
                ant.age = row.age;
                ant.shield = 0;
                ant.defend = false;
                ant.evasion = false;
            }
            ant.pos_x = row.x;
            ant.pos_y = row.y;
            ant.hp = row.hp;
            ant.is_frozen = (row.status == sdk::AntStatus::Frozen);
            ant.all_frozen = ant.is_frozen;
            if (it != previous_ants.end()) {
                ant.behavior = it->second.behavior;
                ant.behavior_rounds = it->second.behavior_rounds;
                ant.behavior_expiry = it->second.behavior_expiry;
                ant.target_x = it->second.target_x;
                ant.target_y = it->second.target_y;
                ant.has_pending_behavior = it->second.has_pending_behavior;
                ant.pending_behavior = it->second.pending_behavior;
            }
            const auto public_behavior = static_cast<::Ant::Behavior>(static_cast<int>(row.behavior));
            if (ant.behavior != public_behavior) {
                ant.behavior_rounds = 0;
                ant.behavior_expiry = default_behavior_expiry(public_behavior);
            }
            ant.behavior = public_behavior;
            if (ant.behavior != ::Ant::Behavior::Bewitched) {
                ant.target_x = -1;
                ant.target_y = -1;
            }
            ant.set_kind(kind);
            max_ant_id = std::max(max_ant_id, row.ant_id + 1);
        }
        game.ant_id = max_ant_id;

        reset_items(game);
        for (int player = 0; player < 2; ++player) {
            for (int item = 0; item < ItemType::Count; ++item) {
                game.item[player][item].cd = state.weapon_cooldowns[player][item + 1];
            }
        }
        for (const auto &row : state.active_effects) {
            const int item_type = static_cast<int>(row.weapon_type) - 1;
            const int player = row.player;
            if (player < 0 || player >= 2 || item_type < 0 || item_type >= ItemType::Count) {
                continue;
            }
            Item &item = game.item[player][item_type];
            item.x = row.x;
            item.y = row.y;
            item.duration = row.remaining_turns;
        }

        game.is_end = false;
        game.winner = -1;
        if (game.base_camp0.get_hp() <= 0 || game.base_camp1.get_hp() <= 0) {
            game.judge_base_camp();
        } else if (game.round >= MAX_ROUND) {
            game.is_end = true;
            game.judge_winner();
        }
        rewire_map(game);
        sync_terminal(game, terminal_flag, winner_value);
    }
};

sdk::NativeSimulator::NativeSimulator(uint64_t seed, std::string movement_policy, bool cold_handle_rule_illegal)
    : impl_(std::make_unique<Impl>(seed, std::move(movement_policy), cold_handle_rule_illegal)) {}

sdk::NativeSimulator::NativeSimulator(std::unique_ptr<Impl> impl) : impl_(std::move(impl)) {}

sdk::NativeSimulator::~NativeSimulator() = default;

sdk::NativeSimulator::NativeSimulator(NativeSimulator &&) noexcept = default;

sdk::NativeSimulator &sdk::NativeSimulator::operator=(NativeSimulator &&) noexcept = default;

sdk::NativeSimulator sdk::NativeSimulator::clone() const {
    return NativeSimulator(std::make_unique<Impl>(*impl_));
}

int sdk::NativeSimulator::round_index() const {
    return impl_->game.round;
}

std::array<int, 2> sdk::NativeSimulator::coins() const {
    return {impl_->game.player0.coin.get_coin(), impl_->game.player1.coin.get_coin()};
}

std::array<int, 2> sdk::NativeSimulator::old_count() const {
    return impl_->old_count_value;
}

std::array<int, 2> sdk::NativeSimulator::die_count() const {
    return {impl_->game.player1.opponent_killed_ant, impl_->game.player0.opponent_killed_ant};
}

std::array<int, 2> sdk::NativeSimulator::super_weapon_usage() const {
    return {impl_->game.player0.super_weapons_usage, impl_->game.player1.super_weapons_usage};
}

std::array<int, 2> sdk::NativeSimulator::ai_time() const {
    return {impl_->game.player0.AI_total_time, impl_->game.player1.AI_total_time};
}

std::array<std::array<int, 5>, 2> sdk::NativeSimulator::weapon_cooldowns() const {
    std::array<std::array<int, 5>, 2> out{};
    for (int player = 0; player < 2; ++player) {
        for (int item = 0; item < ItemType::Count; ++item) {
            out[player][item + 1] = impl_->game.item[player][item].cd;
        }
    }
    return out;
}

int sdk::NativeSimulator::next_ant_id() const {
    return impl_->game.ant_id;
}

int sdk::NativeSimulator::next_tower_id() const {
    return impl_->game.tower_id;
}

bool sdk::NativeSimulator::terminal() const {
    return impl_->terminal_flag;
}

int sdk::NativeSimulator::winner() const {
    return impl_->winner_value;
}

std::vector<sdk::NativeAntHiddenState> sdk::NativeSimulator::ant_hidden_states() const {
    return impl_->ant_hidden_states();
}

const std::string &sdk::NativeSimulator::movement_policy() const {
    return impl_->movement_policy_value;
}

uint64_t sdk::NativeSimulator::seed() const {
    return impl_->seed_value;
}

bool sdk::NativeSimulator::cold_handle_rule_illegal() const {
    return impl_->cold_handle_rule_illegal_value;
}

sdk::PublicRoundState sdk::NativeSimulator::to_public_round_state() const {
    return impl_->to_public_round_state();
}

void sdk::NativeSimulator::reseed_future(uint64_t seed) {
    impl_->seed_value = seed;
    impl_->game.random_seed = seed;
    impl_->game.rng_state = (seed ^ kRngMultiplier) & kRngMask;
}

std::vector<sdk::Operation> sdk::NativeSimulator::apply_operation_list(int player, const std::vector<sdk::Operation> &operations) {
    return impl_->apply_operation_list(player, operations);
}

sdk::ResolveResult sdk::NativeSimulator::advance_round() {
    return impl_->advance_round();
}

sdk::ResolveResult sdk::NativeSimulator::resolve_turn(const std::vector<sdk::Operation> &ops0,
                                                      const std::vector<sdk::Operation> &ops1) {
    sdk::ResolveResult out;
    out.illegal0 = impl_->apply_operation_list(0, ops0);
    if (!impl_->game.is_end) {
        out.illegal1 = impl_->apply_operation_list(1, ops1);
    }
    if (!impl_->game.is_end) {
        const auto round_result = impl_->advance_round();
        out.terminal = round_result.terminal;
        out.winner = round_result.winner;
    } else {
        sync_terminal(impl_->game, impl_->terminal_flag, impl_->winner_value);
        out.terminal = impl_->terminal_flag;
        out.winner = impl_->winner_value;
    }
    return out;
}

void sdk::NativeSimulator::sync_public_round_state(const sdk::PublicRoundState &state) {
    impl_->sync_public_round_state(state);
}
