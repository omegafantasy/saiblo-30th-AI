#include <algorithm>
#include <array>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>

#include "../../game/include/json.hpp"
#define private public
#include "../../game/include/game.hpp"
#undef private
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/sdk.hpp"

using json = nlohmann::json;

namespace {

bool debug_runner_enabled() {
    static const bool enabled = std::getenv("ANTGAME_DEBUG_JSON_RUNNER") != nullptr;
    return enabled;
}

antgame::sdk::Operation parse_operation_tokens(const json &raw) {
    if (!raw.is_array() || raw.empty()) {
        throw std::runtime_error("operation tokens must be a non-empty array");
    }
    const auto type = static_cast<antgame::sdk::OperationType>(raw.at(0).get<int>());
    const int arg0 = raw.size() >= 2 ? raw.at(1).get<int>() : -1;
    const int arg1 = raw.size() >= 3 ? raw.at(2).get<int>() : -1;
    return antgame::sdk::Operation(type, arg0, arg1);
}

json operation_to_json(const antgame::sdk::Operation &operation) {
    return operation.to_protocol_tokens();
}

std::vector<antgame::sdk::Operation> parse_operations(const json &raw) {
    std::vector<antgame::sdk::Operation> operations;
    if (!raw.is_array()) {
        return operations;
    }
    operations.reserve(raw.size());
    for (const auto &item : raw) {
        operations.push_back(parse_operation_tokens(item));
    }
    return operations;
}

json tower_to_json(const antgame::sdk::Tower &tower) {
    return json::array(
        {tower.tower_id, tower.player, tower.x, tower.y, static_cast<int>(tower.tower_type), tower.cooldown, tower.hp});
}

json ant_to_json(const antgame::sdk::Ant &ant) {
    return json::array({ant.ant_id, ant.player, ant.x, ant.y, ant.hp, ant.level, ant.age, static_cast<int>(ant.status),
                        static_cast<int>(ant.behavior), static_cast<int>(ant.kind)});
}

json effect_to_json(const antgame::sdk::WeaponEffect &effect) {
    return json::array({static_cast<int>(effect.weapon_type), effect.player, effect.x, effect.y, effect.remaining_turns});
}

::Operation to_game_operation(const antgame::sdk::Operation &operation) {
    switch (operation.op_type) {
    case antgame::sdk::OperationType::BuildTower:
    case antgame::sdk::OperationType::UseLightningStorm:
    case antgame::sdk::OperationType::UseEmpBlaster:
    case antgame::sdk::OperationType::UseDeflector:
    case antgame::sdk::OperationType::UseEmergencyEvasion:
        return ::Operation(static_cast<int>(operation.op_type), -1, -1, operation.arg0, operation.arg1);
    case antgame::sdk::OperationType::UpgradeTower:
        return ::Operation(static_cast<int>(operation.op_type), operation.arg0, operation.arg1, -1, -1);
    case antgame::sdk::OperationType::DowngradeTower:
        return ::Operation(static_cast<int>(operation.op_type), operation.arg0, -1, -1, -1);
    case antgame::sdk::OperationType::UpgradeGenerationSpeed:
    case antgame::sdk::OperationType::UpgradeGeneratedAnt:
        return ::Operation(static_cast<int>(operation.op_type), -1, -1, -1, -1);
    }
    return ::Operation();
}

Game::MovementPolicy parse_movement_policy_name(const std::string &policy_name) {
    if (policy_name == "legacy") {
        return Game::MovementPolicy::Legacy;
    }
    return Game::MovementPolicy::Enhanced;
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
        if (!tower.destroy()) {
            game.map.map[tower.get_x()][tower.get_y()].tower = &tower;
        }
    }
}

void init_game(Game &game, unsigned long long seed, Game::MovementPolicy movement_policy, bool cold_handle_rule_illegal) {
    constexpr int kInitialCoin = 50;
    constexpr std::uint64_t kRngMask = (1ULL << 48) - 1;
    constexpr std::uint64_t kRngMultiplier = 25214903917ULL;

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
    game.player0.coin.tower_building_price = antgame::sdk::tower_build_cost_for_count(0);
    game.player1.coin.tower_building_price = antgame::sdk::tower_build_cost_for_count(0);
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

json game_public_state_to_json(const Game &game) {
    json out;
    out["round_index"] = game.round;
    out["coins"] = json::array({game.player0.coin.get_coin(), game.player1.coin.get_coin()});
    out["camps_hp"] = json::array({game.base_camp0.get_hp(), game.base_camp1.get_hp()});
    out["speed_lv"] = json::array({game.base_camp0.get_cd_level(), game.base_camp1.get_cd_level()});
    out["anthp_lv"] = json::array({game.base_camp0.get_ant_level(), game.base_camp1.get_ant_level()});

    std::vector<json> towers;
    towers.reserve(game.defensive_towers.size());
    for (const auto &tower : game.defensive_towers) {
        if (!tower.destroy()) {
            towers.push_back(json::array(
                {tower.get_id(), tower.get_player(), tower.get_x(), tower.get_y(), static_cast<int>(tower.get_type()),
                 tower.get_cd(), tower.get_hp()}));
        }
    }
    std::sort(towers.begin(), towers.end(), [](const json &lhs, const json &rhs) { return lhs.at(0).get<int>() < rhs.at(0).get<int>(); });
    out["towers"] = towers;

    std::vector<json> ants;
    ants.reserve(game.ants.size());
    for (const auto &ant : game.ants) {
        ants.push_back(json::array(
            {ant.get_id(), ant.get_player(), ant.get_x(), ant.get_y(), ant.get_hp(), ant.get_level(), ant.get_age(),
             static_cast<int>(ant.get_status()), static_cast<int>(ant.get_behavior()), static_cast<int>(ant.get_kind())}));
    }
    std::sort(ants.begin(), ants.end(), [](const json &lhs, const json &rhs) { return lhs.at(0).get<int>() < rhs.at(0).get<int>(); });
    out["ants"] = ants;

    out["weapon_cooldowns"] = json::array();
    for (int player = 0; player < 2; ++player) {
        std::array<int, 5> row{};
        for (int item = 0; item < ItemType::Count; ++item) {
            row[item + 1] = game.item[player][item].cd;
        }
        out["weapon_cooldowns"].push_back(json::array({row[0], row[1], row[2], row[3], row[4]}));
    }

    std::vector<json> effects;
    for (int player = 0; player < 2; ++player) {
        for (int item = 0; item < ItemType::Count; ++item) {
            const Item &effect = game.item[player][item];
            if (effect.duration > 0) {
                effects.push_back(json::array({item + 1, player, effect.x, effect.y, effect.duration}));
            }
        }
    }
    std::sort(effects.begin(), effects.end(), [](const json &lhs, const json &rhs) {
        return std::make_tuple(
                   lhs.at(1).get<int>(),
                   lhs.at(2).get<int>(),
                   lhs.at(3).get<int>(),
                   lhs.at(4).get<int>(),
                   lhs.at(0).get<int>()) <
               std::make_tuple(
                   rhs.at(1).get<int>(),
                   rhs.at(2).get<int>(),
                   rhs.at(3).get<int>(),
                   rhs.at(4).get<int>(),
                   rhs.at(0).get<int>());
    });
    out["active_effects"] = effects;
    return out;
}

std::vector<antgame::sdk::Operation> apply_game_operations(
    Game &game,
    antgame::sdk::PublicState *mirror_state,
    int player,
    const std::vector<antgame::sdk::Operation> &operations,
    bool cold_handle_rule_illegal) {
    std::vector<antgame::sdk::Operation> illegal;
    if (!cold_handle_rule_illegal) {
        std::vector<::Operation> game_operations;
        game_operations.reserve(operations.size());
        for (const auto &operation : operations) {
            game_operations.push_back(to_game_operation(operation));
        }
        std::string err_msg;
        if (!game.apply_operation(game_operations, player, err_msg)) {
            throw std::runtime_error("authoritative game rejected player" + std::to_string(player) + " operation list: " + err_msg);
        }
        if (mirror_state != nullptr) {
            mirror_state->apply_operation_list(player, operations);
        }
        return illegal;
    }

    std::vector<int> used_towers;
    bool base_upgraded = false;
    for (const auto &operation : operations) {
        if ((operation.op_type == antgame::sdk::OperationType::UpgradeTower ||
             operation.op_type == antgame::sdk::OperationType::DowngradeTower) &&
            std::find(used_towers.begin(), used_towers.end(), operation.arg0) != used_towers.end()) {
            illegal.push_back(operation);
            continue;
        }
        if (antgame::sdk::is_base_upgrade_operation(operation.op_type) && base_upgraded) {
            illegal.push_back(operation);
            if (debug_runner_enabled()) {
                std::cerr << "player " << player << " op " << static_cast<int>(operation.op_type)
                          << " rejected by base-upgrade guard\n";
            }
            continue;
        }
        if (mirror_state != nullptr && !mirror_state->can_apply_operation(player, operation)) {
            illegal.push_back(operation);
            if (debug_runner_enabled()) {
                std::cerr << "player " << player << " op " << static_cast<int>(operation.op_type)
                          << " (" << operation.arg0 << "," << operation.arg1 << ") rejected by mirror can_apply\n";
            }
            continue;
        }

        const int pending_tower_id = game.tower_id;
        std::string err_msg;
        Game::OperationErrorKind error_kind = Game::OperationErrorKind::None;
        if (!game.apply_operation(std::vector<::Operation>{to_game_operation(operation)}, player, err_msg, &error_kind)) {
            if (debug_runner_enabled()) {
                std::cerr << "player " << player << " op " << static_cast<int>(operation.op_type)
                          << " (" << operation.arg0 << "," << operation.arg1 << ") rejected by raw game, kind="
                          << static_cast<int>(error_kind) << " msg=" << err_msg << '\n';
            }
            if (error_kind == Game::OperationErrorKind::Protocol) {
                throw std::runtime_error("authoritative game rejected player" + std::to_string(player) + " operation list: " + err_msg);
            }
            illegal.push_back(operation);
            continue;
        }

        if (operation.op_type == antgame::sdk::OperationType::BuildTower) {
            used_towers.push_back(pending_tower_id);
        } else if (operation.op_type == antgame::sdk::OperationType::UpgradeTower ||
                   operation.op_type == antgame::sdk::OperationType::DowngradeTower) {
            used_towers.push_back(operation.arg0);
        }
        if (antgame::sdk::is_base_upgrade_operation(operation.op_type)) {
            base_upgraded = true;
        }
        if (mirror_state != nullptr) {
            mirror_state->apply_operation_list(player, std::vector<antgame::sdk::Operation>{operation});
        }
    }

    return illegal;
}

antgame::sdk::Tower parse_tower_row(const json &row) {
    return antgame::sdk::Tower{
        row.at(0).get<int>(),
        row.at(1).get<int>(),
        row.at(2).get<int>(),
        row.at(3).get<int>(),
        static_cast<antgame::sdk::TowerType>(row.at(4).get<int>()),
        row.at(5).get<int>(),
        row.at(6).get<int>(),
    };
}

antgame::sdk::Ant parse_ant_row(const json &row) {
    return antgame::sdk::Ant{
        row.at(0).get<int>(),
        row.at(1).get<int>(),
        row.at(2).get<int>(),
        row.at(3).get<int>(),
        row.at(4).get<int>(),
        row.at(5).get<int>(),
        row.at(6).get<int>(),
        static_cast<antgame::sdk::AntStatus>(row.at(7).get<int>()),
        static_cast<antgame::sdk::AntBehavior>(row.at(8).get<int>()),
        static_cast<antgame::sdk::AntKind>(row.at(9).get<int>()),
        -1,
    };
}

antgame::sdk::WeaponEffect parse_effect_row(const json &row) {
    return antgame::sdk::WeaponEffect{
        static_cast<antgame::sdk::SuperWeaponType>(row.at(0).get<int>()),
        row.at(1).get<int>(),
        row.at(2).get<int>(),
        row.at(3).get<int>(),
        row.at(4).get<int>(),
    };
}

antgame::sdk::PublicRoundState parse_public_round_state(const json &raw) {
    antgame::sdk::PublicRoundState state;
    state.round_index = raw.at("round_index").get<int>();
    for (const auto &row : raw.at("towers")) {
        state.towers.push_back(parse_tower_row(row));
    }
    for (const auto &row : raw.at("ants")) {
        state.ants.push_back(parse_ant_row(row));
    }
    state.coins = {raw.at("coins").at(0).get<int>(), raw.at("coins").at(1).get<int>()};
    state.camps_hp = {raw.at("camps_hp").at(0).get<int>(), raw.at("camps_hp").at(1).get<int>()};
    state.speed_lv = {raw.at("speed_lv").at(0).get<int>(), raw.at("speed_lv").at(1).get<int>()};
    state.anthp_lv = {raw.at("anthp_lv").at(0).get<int>(), raw.at("anthp_lv").at(1).get<int>()};
    if (raw.contains("weapon_cooldowns")) {
        const auto &rows = raw.at("weapon_cooldowns");
        for (std::size_t player = 0; player < rows.size() && player < 2; ++player) {
            for (std::size_t item = 0; item < rows[player].size() && item < 5; ++item) {
                state.weapon_cooldowns[player][item] = rows[player][item].get<int>();
            }
        }
    }
    if (raw.contains("active_effects")) {
        for (const auto &row : raw.at("active_effects")) {
            state.active_effects.push_back(parse_effect_row(row));
        }
    }
    return state;
}

json public_round_state_to_json(const antgame::sdk::PublicRoundState &state) {
    json out;
    out["round_index"] = state.round_index;
    out["towers"] = json::array();
    for (const auto &tower : state.towers) {
        out["towers"].push_back(tower_to_json(tower));
    }
    out["ants"] = json::array();
    for (const auto &ant : state.ants) {
        out["ants"].push_back(ant_to_json(ant));
    }
    out["coins"] = json::array({state.coins[0], state.coins[1]});
    out["camps_hp"] = json::array({state.camps_hp[0], state.camps_hp[1]});
    out["speed_lv"] = json::array({state.speed_lv[0], state.speed_lv[1]});
    out["anthp_lv"] = json::array({state.anthp_lv[0], state.anthp_lv[1]});
    out["weapon_cooldowns"] = json::array();
    for (int player = 0; player < 2; ++player) {
        out["weapon_cooldowns"].push_back(json::array(
            {state.weapon_cooldowns[player][0], state.weapon_cooldowns[player][1], state.weapon_cooldowns[player][2],
             state.weapon_cooldowns[player][3], state.weapon_cooldowns[player][4]}));
    }
    out["active_effects"] = json::array();
    for (const auto &effect : state.active_effects) {
        out["active_effects"].push_back(effect_to_json(effect));
    }
    return out;
}

json run_public_eval(const json &request) {
    const auto public_state = parse_public_round_state(request.at("public_state"));
    const int player = request.at("player").get<int>();
    antgame::sdk::PublicState state(
        request.value("seed", 0ULL),
        request.value("movement_policy", std::string("enhanced")),
        request.value("cold_handle_rule_illegal", false));
    state.sync_public_round_state(public_state);

    const auto query_operations = parse_operations(request.value("query_operations", json::array()));
    std::vector<bool> can_apply;
    std::vector<int> incomes;
    can_apply.reserve(query_operations.size());
    incomes.reserve(query_operations.size());
    for (const auto &operation : query_operations) {
        can_apply.push_back(state.can_apply_operation(player, operation));
        incomes.push_back(state.operation_income(player, operation));
    }

    json slot_priorities = json::array();
    for (const auto &point : request.value("slot_points", json::array())) {
        const int x = point.at(0).get<int>();
        const int y = point.at(1).get<int>();
        slot_priorities.push_back(state.slot_priority(player, x, y));
    }

    json metrics;
    metrics["tower_count"] = state.tower_count(player);
    metrics["nearest_ant_distance"] = state.nearest_ant_distance(player);
    metrics["frontline_distance"] = state.frontline_distance(player);
    metrics["safe_coin_threshold"] = state.safe_coin_threshold(player);
    metrics["tower_spread_score"] = state.tower_spread_score(player);
    metrics["slot_priorities"] = slot_priorities;

    const auto apply_operations = parse_operations(request.value("apply_operations", json::array()));
    const auto illegal = state.apply_operation_list(player, apply_operations);

    json out;
    out["can_apply"] = can_apply;
    out["operation_income"] = incomes;
    out["illegal"] = json::array();
    for (const auto &operation : illegal) {
        out["illegal"].push_back(operation_to_json(operation));
    }
    out["metrics"] = metrics;
    out["terminal"] = state.terminal;
    out["winner"] = state.winner;
    out["state"] = public_round_state_to_json(state.to_public_round_state());
    return out;
}

json run_native_trace(const json &request) {
    antgame::sdk::NativeSimulator simulator(
        request.value("seed", 0ULL),
        request.value("movement_policy", std::string("enhanced")),
        request.value("cold_handle_rule_illegal", false));

    json trace = json::array();
    for (const auto &turn : request.at("turns")) {
        const auto ops0 = parse_operations(turn.value("ops0", json::array()));
        const auto ops1 = parse_operations(turn.value("ops1", json::array()));
        const auto result = simulator.resolve_turn(ops0, ops1);
        json row;
        row["illegal0"] = json::array();
        for (const auto &operation : result.illegal0) {
            row["illegal0"].push_back(operation_to_json(operation));
        }
        row["illegal1"] = json::array();
        for (const auto &operation : result.illegal1) {
            row["illegal1"].push_back(operation_to_json(operation));
        }
        row["terminal"] = result.terminal;
        row["winner"] = result.winner;
        row["state"] = public_round_state_to_json(simulator.to_public_round_state());
        trace.push_back(row);
        if (result.terminal) {
            break;
        }
    }
    return json{{"trace", trace}};
}

json run_public_advance(const json &request) {
    antgame::sdk::NativeSimulator simulator(
        request.value("seed", 0ULL),
        request.value("movement_policy", std::string("enhanced")),
        request.value("cold_handle_rule_illegal", false));
    simulator.sync_public_round_state(parse_public_round_state(request.at("public_state")));
    const int steps = std::max(request.value("steps", 1), 0);
    for (int step = 0; step < steps && !simulator.terminal(); ++step) {
        simulator.advance_round();
    }

    json out;
    out["terminal"] = simulator.terminal();
    out["winner"] = simulator.winner();
    out["state"] = public_round_state_to_json(simulator.to_public_round_state());
    return out;
}

json run_game_trace(const json &request) {
    const bool cold_handle_rule_illegal = request.value("cold_handle_rule_illegal", false);
    Game game;
    init_game(
        game,
        request.value("seed", 0ULL),
        parse_movement_policy_name(request.value("movement_policy", std::string("enhanced"))),
        cold_handle_rule_illegal);
    antgame::sdk::PublicState mirror_state(
        request.value("seed", 0ULL),
        request.value("movement_policy", std::string("enhanced")),
        cold_handle_rule_illegal);
    mirror_state.sync_public_round_state(parse_public_round_state(game_public_state_to_json(game)));

    json trace = json::array();
    for (const auto &turn : request.at("turns")) {
        const auto ops0 = parse_operations(turn.value("ops0", json::array()));
        const auto ops1 = parse_operations(turn.value("ops1", json::array()));
        const auto illegal0 = apply_game_operations(game, &mirror_state, 0, ops0, cold_handle_rule_illegal);
        const auto illegal1 = game.is_end
                                  ? std::vector<antgame::sdk::Operation>()
                                  : apply_game_operations(game, &mirror_state, 1, ops1, cold_handle_rule_illegal);
        if (!game.is_end) {
            game.next_round();
            mirror_state.sync_public_round_state(parse_public_round_state(game_public_state_to_json(game)));
        }

        json row;
        row["illegal0"] = json::array();
        for (const auto &operation : illegal0) {
            row["illegal0"].push_back(operation_to_json(operation));
        }
        row["illegal1"] = json::array();
        for (const auto &operation : illegal1) {
            row["illegal1"].push_back(operation_to_json(operation));
        }
        row["terminal"] = game.is_end;
        row["winner"] = game.is_end ? game.winner : -1;
        row["state"] = game_public_state_to_json(game);
        trace.push_back(row);
        if (game.is_end) {
            break;
        }
    }

    return json{{"trace", trace}};
}

} // namespace

int main() {
    try {
        json request;
        std::cin >> request;
        const std::string mode = request.at("mode").get<std::string>();
        json response;
        if (mode == "public_eval") {
            response = run_public_eval(request);
        } else if (mode == "native_trace") {
            response = run_native_trace(request);
        } else if (mode == "public_advance") {
            response = run_public_advance(request);
        } else if (mode == "game_trace") {
            response = run_game_trace(request);
        } else {
            throw std::runtime_error("unknown mode");
        }
        std::cout << response.dump();
        return 0;
    } catch (const std::exception &exc) {
        json error;
        error["error"] = exc.what();
        std::cout << error.dump();
        return 1;
    }
}
