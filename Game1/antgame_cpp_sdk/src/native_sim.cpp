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
constexpr double kSpawnBehaviorProbs[4] = {0.4, 0.35, 0.10, 0.15};
constexpr double DEFAULT_MOVE_TEMPERATURE = 1.75;
constexpr double BEWITCH_MOVE_TEMPERATURE = 1.5;
constexpr double WORKER_RESERVATION_WEIGHT = 1.40;
constexpr double WORKER_TOWER_CLAIM_WEIGHT = 1.00;
constexpr double WORKER_BLOCKED_ATTACK_BONUS = 6.00;
constexpr double WORKER_ROUTE_IMPROVEMENT_EPS = 0.50;
constexpr double COMBAT_RESERVATION_WEIGHT = 0.45;
constexpr double COMBAT_TOWER_CLAIM_WEIGHT = 0.85;
constexpr double COMBAT_TRAVEL_COST_WEIGHT = 0.90;
constexpr double ATTACK_FINISH_BONUS = 3.00;
constexpr double ENHANCED_COMBAT_ATTACK_EXECUTION_BONUS = 1.50;
constexpr double WORKER_REROUTE_ATTACK_PENALTY_WEIGHT = 1.0;

struct NativeSpawnProfile {
    ::Ant::Kind kind;
    ::Ant::Behavior behavior;
};

constexpr NativeSpawnProfile kSpawnProfiles[4] = {
    {::Ant::Kind::Worker, ::Ant::Behavior::Default},
    {::Ant::Kind::Worker, ::Ant::Behavior::Conservative},
    {::Ant::Kind::Worker, ::Ant::Behavior::Randomized},
    {::Ant::Kind::Combat, ::Ant::Behavior::Default},
};

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

void mark_trail_cell(std::array<std::uint64_t, sdk::kTrailMaskWords> &mask, int x, int y) {
    if (x < 0 || x >= sdk::kMapSize || y < 0 || y >= sdk::kMapSize) {
        return;
    }
    const int bit_index = x * sdk::kMapSize + y;
    mask[static_cast<std::size_t>(bit_index / 64)] |= 1ULL << (bit_index % 64);
}

int infer_last_move_from_positions(int from_x, int from_y, int to_x, int to_y) {
    if (from_x == to_x && from_y == to_y) {
        return ::Ant::NoMove;
    }
    for (int direction = 0; direction < 6; ++direction) {
        const int nx = from_x + sdk::kOffset[from_y & 1][direction][0];
        const int ny = from_y + sdk::kOffset[from_y & 1][direction][1];
        if (nx == to_x && ny == to_y) {
            return direction;
        }
    }
    return ::Ant::NoMove;
}

void append_trail_if_needed(Ant &ant, int x, int y) {
    if (ant.trail_cells.empty() || ant.trail_cells.back().x != x || ant.trail_cells.back().y != y) {
        ant.trail_cells.emplace_back(x, y);
    }
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
        ant.shield,
        ant.defend,
        ant.evasion_control_free_on_break,
        true,
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
            sdk::NativeAntHiddenState row{
                ant.get_id(),
                ant.get_last_move(),
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
                {},
            };
            for (const auto &cell : ant.get_trail_cells()) {
                mark_trail_cell(row.trail_mask, cell.x, cell.y);
            }
            mark_trail_cell(row.trail_mask, ant.get_x(), ant.get_y());
            out.push_back(row);
        }
        std::sort(out.begin(), out.end(), [](const sdk::NativeAntHiddenState &lhs, const sdk::NativeAntHiddenState &rhs) {
            return lhs.ant_id < rhs.ant_id;
        });
        return out;
    }

    std::vector<sdk::NativeAntMoveDebug> move_debug_for_player(int player_id) const {
        Impl scratch(*this);
        Game &game = scratch.game;
        game.ensure_enhanced_move_cache();
        std::vector<sdk::NativeAntMoveDebug> out;
        for (const auto &ant : game.ants) {
            if (ant.get_player() != player_id || ant.get_status() != ::Ant::Status::Alive) {
                continue;
            }
            std::vector<std::tuple<int, int, int>> candidates = game.legal_move_candidates(ant);
            sdk::NativeAntMoveDebug row;
            row.ant_id = ant.get_id();
            row.x = ant.get_x();
            row.y = ant.get_y();
            row.hp = ant.get_hp();
            row.last_move = ant.get_last_move();
            row.behavior = static_cast<sdk::AntBehavior>(static_cast<int>(ant.get_behavior()));
            row.kind = static_cast<sdk::AntKind>(static_cast<int>(ant.get_kind()));
            if (candidates.empty()) {
                out.push_back(std::move(row));
                continue;
            }
            if (ant.get_behavior() == ::Ant::Behavior::Randomized) {
                const double probability = 1.0 / static_cast<double>(std::max(1, static_cast<int>(candidates.size())));
                for (const auto &candidate : candidates) {
                    row.options.push_back(sdk::NativeMoveOptionDebug{
                        std::get<0>(candidate),
                        std::get<1>(candidate),
                        std::get<2>(candidate),
                        0.0,
                        0.0,
                        probability,
                        std::get<1>(candidate),
                        std::get<2>(candidate),
                        -1,
                    });
                }
                out.push_back(std::move(row));
                continue;
            }

            if (ant.get_behavior() == ::Ant::Behavior::Bewitched) {
                Pos target = ant.target_x >= 0 && ant.target_y >= 0
                                 ? Pos(ant.target_x, ant.target_y)
                                 : (ant.get_player() ? Pos(PLAYER_0_BASE_CAMP_X, PLAYER_0_BASE_CAMP_Y)
                                                     : Pos(PLAYER_1_BASE_CAMP_X, PLAYER_1_BASE_CAMP_Y));
                std::vector<double> damage_scores =
                    game.directional_field_scores(ant, candidates, game.damage_risk_field);
                std::vector<double> control_scores =
                    game.directional_field_scores(ant, candidates, game.control_risk_field);
                std::vector<double> effect_scores =
                    game.directional_field_scores(ant, candidates, game.effect_pull_field);
                if (ant.is_control_immune()) {
                    std::fill(control_scores.begin(), control_scores.end(), 0.0);
                }
                std::vector<double> scores(candidates.size(), 0.0);
                std::vector<double> raw_scores(candidates.size(), 0.0);
                for (int index = 0; index < static_cast<int>(candidates.size()); ++index) {
                    const int direction = std::get<0>(candidates[index]);
                    const int nx = std::get<1>(candidates[index]);
                    const int ny = std::get<2>(candidates[index]);
                    const DefenseTower *tower_target = game.enemy_tower_at(ant.get_player(), nx, ny);
                    const int eval_x = tower_target != nullptr ? ant.get_x() : nx;
                    const int eval_y = tower_target != nullptr ? ant.get_y() : ny;
                    const double progress = game.move_progress_score(ant, eval_x, eval_y, target);
                    const double pheromone = game.move_pheromone_score(ant, eval_x, eval_y);
                    const double tower_pull = game.tower_pull_score(ant, eval_x, eval_y, tower_target);
                    const double score = ant.move_weights.progress * progress +
                                         ant.move_weights.pheromone * pheromone -
                                         ant.move_weights.crowding * game.crowding_penalty(ant, eval_x, eval_y) -
                                         ant.move_weights.expected_damage * damage_scores[index] -
                                         ant.move_weights.control_risk * control_scores[index] +
                                         ant.move_weights.tower_pull * tower_pull +
                                         ant.move_weights.effect_pull * effect_scores[index] +
                                         (tower_target != nullptr ? 4.0 : 0.0);
                    scores[index] = score;
                    raw_scores[index] = score + effect_scores[index];
                    row.options.push_back(sdk::NativeMoveOptionDebug{
                        direction,
                        nx,
                        ny,
                        score,
                        raw_scores[index],
                        0.0,
                        tower_target != nullptr ? -1 : nx,
                        tower_target != nullptr ? -1 : ny,
                        tower_target != nullptr ? tower_target->get_id() : -1,
                    });
                }
                if (ant.get_behavior() == ::Ant::Behavior::Conservative ||
                    ant.get_behavior() == ::Ant::Behavior::ControlFree) {
                    int best = 0;
                    for (int index = 1; index < static_cast<int>(scores.size()); ++index) {
                        if (scores[index] > scores[best] ||
                            (scores[index] == scores[best] && raw_scores[index] > raw_scores[best])) {
                            best = index;
                        }
                    }
                    for (int index = 0; index < static_cast<int>(row.options.size()); ++index) {
                        row.options[static_cast<std::size_t>(index)].probability = index == best ? 1.0 : 0.0;
                    }
                } else {
                    const double temperature = BEWITCH_MOVE_TEMPERATURE;
                    const double max_score = *std::max_element(scores.begin(), scores.end());
                    double total = 0.0;
                    for (double score : scores) {
                        total += std::exp((score - max_score) / temperature);
                    }
                    for (int index = 0; index < static_cast<int>(row.options.size()); ++index) {
                        row.options[static_cast<std::size_t>(index)].probability =
                            total > 0.0 ? std::exp((scores[index] - max_score) / temperature) / total : 0.0;
                    }
                }
                out.push_back(std::move(row));
                continue;
            }

            std::vector<double> scores;
            std::vector<double> raw_scores;
            std::vector<std::pair<int, int>> annotated_cells;
            std::vector<int> annotated_towers;
            scores.reserve(candidates.size());
            raw_scores.reserve(candidates.size());
            annotated_cells.reserve(candidates.size());
            annotated_towers.reserve(candidates.size());

            if (!ant.is_combat_ant()) {
                const double current_cost =
                    game.enhanced_worker_costs[ant.get_player()][ant.get_x()][ant.get_y()];
                double best_walk_remaining = std::numeric_limits<double>::infinity();
                for (const auto &candidate : candidates) {
                    const int nx = std::get<1>(candidate);
                    const int ny = std::get<2>(candidate);
                    if (game.enemy_tower_at(ant.get_player(), nx, ny) != nullptr) {
                        continue;
                    }
                    best_walk_remaining = std::min(best_walk_remaining, game.enhanced_worker_costs[ant.get_player()][nx][ny]);
                }
                const double reroute_gain =
                    (std::isfinite(current_cost) && std::isfinite(best_walk_remaining))
                        ? std::max(0.0, current_cost - best_walk_remaining)
                        : 0.0;
                const bool blocked = !std::isfinite(best_walk_remaining) || !std::isfinite(current_cost) ||
                                     (current_cost - best_walk_remaining <= WORKER_ROUTE_IMPROVEMENT_EPS);
                for (const auto &candidate : candidates) {
                    const int nx = std::get<1>(candidate);
                    const int ny = std::get<2>(candidate);
                    const DefenseTower *tower_target = game.enemy_tower_at(ant.get_player(), nx, ny);
                    double score = -1e9;
                    if (tower_target != nullptr) {
                        score = std::isfinite(current_cost) ? -current_cost : 0.0;
                        score += 1.2 * std::min(ant.get_tower_attack_damage(), tower_target->get_hp());
                        if (tower_target->get_hp() <= ant.get_tower_attack_damage()) {
                            score += ATTACK_FINISH_BONUS;
                        }
                        if (blocked) {
                            score += WORKER_BLOCKED_ATTACK_BONUS;
                        } else {
                            score -= WORKER_REROUTE_ATTACK_PENALTY_WEIGHT * reroute_gain;
                        }
                        auto claim_it = game.enhanced_tower_claims[ant.get_player()].find(tower_target->get_id());
                        if (claim_it != game.enhanced_tower_claims[ant.get_player()].end()) {
                            score -= WORKER_TOWER_CLAIM_WEIGHT * claim_it->second;
                        }
                        score += ant.move_weights.pheromone * game.move_pheromone_score(ant, ant.get_x(), ant.get_y());
                        annotated_cells.emplace_back(-1, -1);
                        annotated_towers.push_back(tower_target->get_id());
                    } else {
                        const double remaining = game.enhanced_worker_costs[ant.get_player()][nx][ny];
                        if (std::isfinite(remaining)) {
                            score = -remaining;
                            score -= WORKER_RESERVATION_WEIGHT * game.enhanced_reservations[ant.get_player()][nx][ny];
                            score -= 0.25 * game.crowding_penalty(ant, nx, ny);
                            score += ant.move_weights.pheromone * game.move_pheromone_score(ant, nx, ny);
                        }
                        annotated_cells.emplace_back(nx, ny);
                        annotated_towers.push_back(-1);
                    }
                    scores.push_back(score);
                    raw_scores.push_back(score);
                }
            } else {
                std::vector<const DefenseTower *> enemy_towers;
                for (const auto &tower : game.defensive_towers) {
                    if (!tower.destroy() && tower.get_player() != ant.get_player()) {
                        enemy_towers.push_back(&tower);
                    }
                }
                for (const auto &candidate : candidates) {
                    const int nx = std::get<1>(candidate);
                    const int ny = std::get<2>(candidate);
                    const DefenseTower *tower_target = game.enemy_tower_at(ant.get_player(), nx, ny);
                    double score = -1e9;
                    int best_tower_id = -1;
                    if (tower_target != nullptr) {
                        score = game.tower_attack_value(ant, *tower_target, ant.get_hp());
                        score += ENHANCED_COMBAT_ATTACK_EXECUTION_BONUS;
                        auto claim_it = game.enhanced_tower_claims[ant.get_player()].find(tower_target->get_id());
                        if (claim_it != game.enhanced_tower_claims[ant.get_player()].end()) {
                            score -= COMBAT_TOWER_CLAIM_WEIGHT * claim_it->second;
                        }
                        score += ant.move_weights.pheromone * game.move_pheromone_score(ant, ant.get_x(), ant.get_y());
                        best_tower_id = tower_target->get_id();
                        annotated_cells.emplace_back(-1, -1);
                    } else if (!enemy_towers.empty()) {
                        for (const DefenseTower *tower : enemy_towers) {
                            const Game::TowerPathPlan *plan = game.tower_plan_for(ant.get_player(), tower->get_id());
                            if (plan == nullptr) {
                                continue;
                            }
                            const double travel_cost = plan->plan.total_cost[nx][ny];
                            if (!std::isfinite(travel_cost)) {
                                continue;
                            }
                            const double travel_damage = plan->plan.damage_cost[nx][ny];
                            const double arrival_hp = ant.get_hp() - travel_damage;
                            double utility = game.tower_attack_value(ant, *tower, arrival_hp);
                            utility -= COMBAT_TRAVEL_COST_WEIGHT * travel_cost;
                            auto claim_it = game.enhanced_tower_claims[ant.get_player()].find(tower->get_id());
                            if (claim_it != game.enhanced_tower_claims[ant.get_player()].end()) {
                                utility -= COMBAT_TOWER_CLAIM_WEIGHT * claim_it->second;
                            }
                            if (utility > score) {
                                score = utility;
                                best_tower_id = tower->get_id();
                            }
                        }
                        if (std::isfinite(score)) {
                            score -= COMBAT_RESERVATION_WEIGHT * game.enhanced_reservations[ant.get_player()][nx][ny];
                            score += ant.move_weights.pheromone * game.move_pheromone_score(ant, nx, ny);
                        }
                        annotated_cells.emplace_back(nx, ny);
                    } else {
                        const double remaining = game.enhanced_combat_base_costs[ant.get_player()][nx][ny];
                        if (std::isfinite(remaining)) {
                            score = -remaining;
                            score -= COMBAT_RESERVATION_WEIGHT * game.enhanced_reservations[ant.get_player()][nx][ny];
                            score += ant.move_weights.pheromone * game.move_pheromone_score(ant, nx, ny);
                        }
                        annotated_cells.emplace_back(nx, ny);
                    }
                    annotated_towers.push_back(best_tower_id);
                    scores.push_back(score);
                    raw_scores.push_back(score);
                }
            }

            if (ant.get_behavior() == ::Ant::Behavior::Conservative ||
                ant.get_behavior() == ::Ant::Behavior::ControlFree) {
                int best = 0;
                for (int index = 1; index < static_cast<int>(scores.size()); ++index) {
                    if (scores[index] > scores[best] ||
                        (scores[index] == scores[best] && raw_scores[index] > raw_scores[best])) {
                        best = index;
                    }
                }
                for (int index = 0; index < static_cast<int>(candidates.size()); ++index) {
                    row.options.push_back(sdk::NativeMoveOptionDebug{
                        std::get<0>(candidates[index]),
                        std::get<1>(candidates[index]),
                        std::get<2>(candidates[index]),
                        scores[index],
                        raw_scores[index],
                        index == best ? 1.0 : 0.0,
                        annotated_cells[index].first,
                        annotated_cells[index].second,
                        annotated_towers[index],
                    });
                }
            } else {
                const double max_score = *std::max_element(scores.begin(), scores.end());
                double total = 0.0;
                for (double score : scores) {
                    total += std::exp((score - max_score) / DEFAULT_MOVE_TEMPERATURE);
                }
                for (int index = 0; index < static_cast<int>(candidates.size()); ++index) {
                    row.options.push_back(sdk::NativeMoveOptionDebug{
                        std::get<0>(candidates[index]),
                        std::get<1>(candidates[index]),
                        std::get<2>(candidates[index]),
                        scores[index],
                        raw_scores[index],
                        total > 0.0 ? std::exp((scores[index] - max_score) / DEFAULT_MOVE_TEMPERATURE) / total : 0.0,
                        annotated_cells[index].first,
                        annotated_cells[index].second,
                        annotated_towers[index],
                    });
                }
            }
            out.push_back(std::move(row));
        }
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

    NativeSpawnProfile draw_spawn_profile() {
        const double roll = game.random_float();
        double cumulative = 0.0;
        for (int index = 0; index < 4; ++index) {
            cumulative += kSpawnBehaviorProbs[index];
            if (roll <= cumulative) {
                return kSpawnProfiles[index];
            }
        }
        return kSpawnProfiles[3];
    }

    std::pair<int, int> choose_tower_spawn_cell(const DefenseTower &tower) {
        const Pos enemy = tower.get_player() ? Pos(PLAYER_0_BASE_CAMP_X, PLAYER_0_BASE_CAMP_Y)
                                             : Pos(PLAYER_1_BASE_CAMP_X, PLAYER_1_BASE_CAMP_Y);
        double best_score = -1e18;
        std::pair<int, int> best = {tower.get_x(), tower.get_y()};
        for (int direction = 0; direction < 6; ++direction) {
            const int nx = tower.get_x() + sdk::kOffset[tower.get_y() & 1][direction][0];
            const int ny = tower.get_y() + sdk::kOffset[tower.get_y() & 1][direction][1];
            if (!game.ant_can_walk_to(nx, ny)) {
                continue;
            }
            const int ant_level = tower.get_player() ? game.base_camp1.get_ant_level()
                                                     : game.base_camp0.get_ant_level();
            double score = -distance(Pos(nx, ny), enemy);
            score -= game.crowding_penalty(::Ant(tower.get_player(), -1, nx, ny, ant_level), nx, ny);
            if (score > best_score) {
                best_score = score;
                best = {nx, ny};
            }
        }
        return best;
    }

    void spawn_ant_from_tower_without_base_spawn(
        const DefenseTower &tower,
        ::Ant::Kind kind,
        ::Ant::Behavior behavior) {
        const auto cell = choose_tower_spawn_cell(tower);
        if (!game.ant_can_walk_to(cell.first, cell.second)) {
            return;
        }
        const int ant_level = tower.get_player() ? game.base_camp1.get_ant_level()
                                                 : game.base_camp0.get_ant_level();
        game.ants.push_back(::Ant(tower.get_player(), game.ant_id, cell.first, cell.second, ant_level, kind));
        game.ants.back().trail_cells = {Pos(cell.first, cell.second)};
        game.ants.back().set_behavior(behavior);
        if (kind == ::Ant::Kind::Combat) {
            game.grant_emergency_evasion(game.ants.back(), 3, true);
        }
        ++game.ant_id;
    }

    void process_producer_towers_without_base_spawn() {
        for (auto &tower : game.defensive_towers) {
            if (tower.destroy() || !tower.is_producer()) {
                continue;
            }
            ::Item it = game.item[!tower.get_player()][ItemType::EMPBlaster];
            if (it.duration && distance(Pos(tower.get_x(), tower.get_y()), Pos(it.x, it.y)) <= 3) {
                continue;
            }
            ++tower.round;
            if (tower.get_type() == ::TowerType::ProducerMedic &&
                tower.get_support_interval() > 0 &&
                tower.round % tower.get_support_interval() == 0) {
                const Pos enemy = tower.get_player() ? Pos(PLAYER_0_BASE_CAMP_X, PLAYER_0_BASE_CAMP_Y)
                                                     : Pos(PLAYER_1_BASE_CAMP_X, PLAYER_1_BASE_CAMP_Y);
                int frontline_distance = 1000000000;
                for (auto &ant : game.ants) {
                    if (ant.get_player() != tower.get_player()) {
                        continue;
                    }
                    const auto status = ant.get_status();
                    if (status != ::Ant::Status::Alive && status != ::Ant::Status::Frozen) {
                        continue;
                    }
                    frontline_distance = std::min(frontline_distance, distance(Pos(ant.get_x(), ant.get_y()), enemy));
                }
                ::Ant *target = nullptr;
                for (auto &ant : game.ants) {
                    if (ant.get_player() != tower.get_player()) {
                        continue;
                    }
                    const auto status = ant.get_status();
                    if (status != ::Ant::Status::Alive && status != ::Ant::Status::Frozen) {
                        continue;
                    }
                    const int ant_distance = distance(Pos(ant.get_x(), ant.get_y()), enemy);
                    if (ant_distance > frontline_distance + 1) {
                        continue;
                    }
                    if (target == nullptr ||
                        (target->get_kind() != ::Ant::Kind::Combat && ant.get_kind() == ::Ant::Kind::Combat) ||
                        (target->get_kind() == ant.get_kind() &&
                         (ant.get_hp() < target->get_hp() ||
                          (ant.get_hp() == target->get_hp() &&
                           (ant_distance < distance(Pos(target->get_x(), target->get_y()), enemy) ||
                            (ant_distance == distance(Pos(target->get_x(), target->get_y()), enemy) &&
                             ant.get_id() < target->get_id())))))) {
                        target = &ant;
                    }
                }
                if (target != nullptr) {
                    target->set_hp_true(target->get_hp_limit() - target->get_hp());
                    target->add_evasion(1, true);
                }
            }
            if (tower.round < tower.get_spawn_interval()) {
                continue;
            }
            const NativeSpawnProfile profile = draw_spawn_profile();
            spawn_ant_from_tower_without_base_spawn(tower, profile.kind, profile.behavior);
            if (tower.get_type() == ::TowerType::ProducerSiege &&
                game.random_float() <= tower.get_siege_spawn_chance()) {
                spawn_ant_from_tower_without_base_spawn(tower, ::Ant::Kind::Combat, ::Ant::Behavior::Default);
            }
            tower.round = 0;
        }
    }

    sdk::ResolveResult advance_round_without_base_spawns_impl(bool apply_periodic_teleport) {
        if (!game.is_end) {
            game.attack_ants();
            game.move_ants();
            if (apply_periodic_teleport) {
                game.teleport_ants();
            }
            game.update_pheromone();
            const bool should_continue = game.manage_ants();
            if (!should_continue) {
                ++game.round;
            } else {
                process_producer_towers_without_base_spawn();
                game.increase_ant_age();
                game.update_coin();
                game.update_items();
                ++game.round;
                if (game.round == MAX_ROUND) {
                    game.is_end = true;
                    game.judge_winner();
                } else {
                    game.judge_base_camp();
                }
            }
        }
        sync_terminal(game, terminal_flag, winner_value);
        sdk::ResolveResult out;
        out.terminal = terminal_flag;
        out.winner = winner_value;
        return out;
    }

    sdk::ResolveResult advance_round_without_base_spawns() {
        return advance_round_without_base_spawns_impl(true);
    }

    sdk::ResolveResult advance_round_without_base_spawns_no_teleport() {
        return advance_round_without_base_spawns_impl(false);
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

        int max_tower_id = 0;
        for (const auto &row : state.towers) {
            if (row.tower_id >= 0) {
                max_tower_id = std::max(max_tower_id, row.tower_id + 1);
            }
        }

        game.defensive_towers.clear();
        for (int tower_id = 0; tower_id < max_tower_id; ++tower_id) {
            game.defensive_towers.emplace_back(0, 0, 0, tower_id, 0);
            game.defensive_towers.back().set_destroy();
        }

        std::array<int, 2> tower_counts = {0, 0};
        for (const auto &row : state.towers) {
            if (row.tower_id < 0 || row.tower_id >= static_cast<int>(game.defensive_towers.size())) {
                continue;
            }
            game.defensive_towers[row.tower_id] = DefenseTower(row.x, row.y, row.player, row.tower_id, 0);
            auto &tower = game.defensive_towers[row.tower_id];
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
            const bool same_kind = it != previous_ants.end() && it->second.get_kind() == kind;
            if (it != previous_ants.end()) {
                ant.trail_cells = it->second.trail_cells;
                ant.last_move = row.last_move >= 0
                                    ? row.last_move
                                    : infer_last_move_from_positions(it->second.get_x(), it->second.get_y(), row.x, row.y);
                if (ant.last_move != ::Ant::NoMove || it->second.get_x() != row.x || it->second.get_y() != row.y) {
                    append_trail_if_needed(ant, row.x, row.y);
                }
                ant.path_len_total = it->second.path_len_total;
                ant.age = row.age;
                if (row.hidden_state_known) {
                    ant.shield = row.shield;
                    ant.defend = row.defend;
                    ant.evasion = ant.shield > 0;
                    ant.evasion_control_free_on_break = row.evasion_control_free_on_break;
                } else {
                    ant.shield = same_kind ? it->second.shield : 0;
                    ant.defend = same_kind ? it->second.defend : false;
                    ant.evasion = same_kind ? it->second.evasion : false;
                    ant.evasion_control_free_on_break = same_kind ? it->second.evasion_control_free_on_break : false;
                }
            } else {
                ant.age = row.age;
                ant.last_move = row.last_move >= 0 ? row.last_move : ::Ant::NoMove;
                ant.shield = row.hidden_state_known ? row.shield : 0;
                ant.defend = row.hidden_state_known ? row.defend : false;
                ant.evasion = ant.shield > 0;
                ant.evasion_control_free_on_break =
                    row.hidden_state_known ? row.evasion_control_free_on_break : false;
            }
            ant.pos_x = row.x;
            ant.pos_y = row.y;
            ant.hp = row.hp;
            ant.is_frozen = (row.status == sdk::AntStatus::Frozen);
            ant.all_frozen = ant.is_frozen;
            if (same_kind) {
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

std::vector<sdk::NativeAntMoveDebug> sdk::NativeSimulator::move_debug_for_player(int player) const {
    return impl_->move_debug_for_player(player);
}

std::array<std::array<double, sdk::kMapSize>, sdk::kMapSize> sdk::NativeSimulator::pheromone_for_player(int player) const {
    std::array<std::array<double, sdk::kMapSize>, sdk::kMapSize> out{};
    if (player < 0 || player >= 2) {
        return out;
    }
    for (int x = 0; x < sdk::kMapSize; ++x) {
        for (int y = 0; y < sdk::kMapSize; ++y) {
            out[x][y] = static_cast<double>(impl_->game.map.map[x][y].pheromone[player]) / PHEROMONE_SCALE;
        }
    }
    return out;
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

sdk::ResolveResult sdk::NativeSimulator::advance_round_without_base_spawns() {
    return impl_->advance_round_without_base_spawns();
}

sdk::ResolveResult sdk::NativeSimulator::advance_round_without_base_spawns_no_teleport() {
    return impl_->advance_round_without_base_spawns_no_teleport();
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
