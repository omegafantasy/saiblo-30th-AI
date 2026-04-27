#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "../../Ant-Game/game/include/json.hpp"
#include "antgame_sdk/lure_strategy_v2.hpp"
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/sdk.hpp"

using json = nlohmann::json;

namespace antgame::sdk::examples {

namespace ls = ::antgame::sdk::lure_strategy_detail;
namespace rs = ::antgame::sdk::random_search_detail;

struct MeanEval {
    double base_hp_raw = 0.0;
    double base_hp_score = 0.0;
    double tower_value_raw = 0.0;
    double tower_value_score = 0.0;
    double money_raw = 0.0;
    double money_score = 0.0;
    double c1_bonus_raw = 0.0;
    double c1_bonus_score = 0.0;
    double worker_threat_raw = 0.0;
    double worker_threat_score = 0.0;
    double combat_threat_raw = 0.0;
    double combat_threat_score = 0.0;
    double total_score = 0.0;
    double ants = 0.0;
    double towers = 0.0;
    double terminal = 0.0;

    void add(const ls::EvalBreakdown &value, const rs::DefenseSimulator &simulator) {
        base_hp_raw += value.base_hp_raw;
        base_hp_score += value.base_hp_score;
        tower_value_raw += value.tower_value_raw;
        tower_value_score += value.tower_value_score;
        money_raw += value.money_raw;
        money_score += value.money_score;
        c1_bonus_raw += value.c1_bonus_raw;
        c1_bonus_score += value.c1_bonus_score;
        worker_threat_raw += value.worker_threat_raw;
        worker_threat_score += value.worker_threat_score;
        combat_threat_raw += value.combat_threat_raw;
        combat_threat_score += value.combat_threat_score;
        total_score += value.total_score;
        ants += simulator.ants.size();
        int alive_towers = 0;
        for (const auto &tower : simulator.towers) {
            if (tower.alive()) {
                ++alive_towers;
            }
        }
        towers += alive_towers;
        terminal += simulator.terminal ? 1.0 : 0.0;
    }

    void scale(double factor) {
        base_hp_raw *= factor;
        base_hp_score *= factor;
        tower_value_raw *= factor;
        tower_value_score *= factor;
        money_raw *= factor;
        money_score *= factor;
        c1_bonus_raw *= factor;
        c1_bonus_score *= factor;
        worker_threat_raw *= factor;
        worker_threat_score *= factor;
        combat_threat_raw *= factor;
        combat_threat_score *= factor;
        total_score *= factor;
        ants *= factor;
        towers *= factor;
        terminal *= factor;
    }
};

struct RunEval {
    MeanEval terminal;
    std::vector<MeanEval> steps;
};

json diff_to_json(const MeanEval &fast, const MeanEval &native);

json mean_to_json(const MeanEval &value) {
    return json{
        {"base_hp_raw", value.base_hp_raw},
        {"base_hp_score", value.base_hp_score},
        {"tower_value_raw", value.tower_value_raw},
        {"tower_value_score", value.tower_value_score},
        {"money_raw", value.money_raw},
        {"money_score", value.money_score},
        {"c1_bonus_raw", value.c1_bonus_raw},
        {"c1_bonus_score", value.c1_bonus_score},
        {"worker_threat_raw", value.worker_threat_raw},
        {"worker_threat_score", value.worker_threat_score},
        {"combat_threat_raw", value.combat_threat_raw},
        {"combat_threat_score", value.combat_threat_score},
        {"total_score", value.total_score},
        {"ants", value.ants},
        {"towers", value.towers},
        {"terminal_rate", value.terminal},
    };
}

json run_to_json(const RunEval &value) {
    json steps = json::array();
    for (const auto &step : value.steps) {
        steps.push_back(mean_to_json(step));
    }
    return json{{"terminal", mean_to_json(value.terminal)}, {"steps", steps}};
}

json run_diff_to_json(const RunEval &fast, const RunEval &native) {
    json steps = json::array();
    const std::size_t count = std::min(fast.steps.size(), native.steps.size());
    for (std::size_t index = 0; index < count; ++index) {
        steps.push_back(diff_to_json(fast.steps[index], native.steps[index]));
    }
    return json{{"terminal", diff_to_json(fast.terminal, native.terminal)}, {"steps", steps}};
}

json diff_to_json(const MeanEval &fast, const MeanEval &native) {
    return json{
        {"base_hp_raw", fast.base_hp_raw - native.base_hp_raw},
        {"tower_value_raw", fast.tower_value_raw - native.tower_value_raw},
        {"money_raw", fast.money_raw - native.money_raw},
        {"worker_threat_raw", fast.worker_threat_raw - native.worker_threat_raw},
        {"combat_threat_raw", fast.combat_threat_raw - native.combat_threat_raw},
        {"total_score", fast.total_score - native.total_score},
        {"ants", fast.ants - native.ants},
        {"towers", fast.towers - native.towers},
        {"terminal_rate", fast.terminal - native.terminal},
    };
}

Operation parse_replay_operation(const json &raw) {
    const int type = raw.value("type", -1);
    const int id = raw.value("id", -1);
    const int args = raw.value("args", -1);
    const int x = raw.value("pos", json::object()).value("x", -1);
    const int y = raw.value("pos", json::object()).value("y", -1);
    switch (static_cast<OperationType>(type)) {
    case OperationType::BuildTower:
        return Operation(OperationType::BuildTower, x, y);
    case OperationType::UpgradeTower:
        return Operation(OperationType::UpgradeTower, id, args);
    case OperationType::DowngradeTower:
        return Operation(OperationType::DowngradeTower, id);
    case OperationType::UseLightningStorm:
        return Operation(OperationType::UseLightningStorm, x, y);
    case OperationType::UseEmpBlaster:
        return Operation(OperationType::UseEmpBlaster, x, y);
    case OperationType::UseDeflector:
        return Operation(OperationType::UseDeflector, x, y);
    case OperationType::UseEmergencyEvasion:
        return Operation(OperationType::UseEmergencyEvasion, x, y);
    case OperationType::UpgradeGenerationSpeed:
        return Operation(OperationType::UpgradeGenerationSpeed);
    case OperationType::UpgradeGeneratedAnt:
        return Operation(OperationType::UpgradeGeneratedAnt);
    default:
        return Operation(static_cast<OperationType>(-1));
    }
}

std::vector<Operation> parse_replay_operations(const json &ops_raw) {
    std::vector<Operation> operations;
    if (!ops_raw.is_array()) {
        return operations;
    }
    operations.reserve(ops_raw.size());
    for (const auto &item : ops_raw) {
        const Operation operation = parse_replay_operation(item);
        if (static_cast<int>(operation.op_type) >= 0) {
            operations.push_back(operation);
        }
    }
    return operations;
}

std::uint64_t replay_seed(const json &replay) {
    if (!replay.is_array() || replay.empty()) {
        throw std::runtime_error("invalid replay");
    }
    return replay.at(0).value("seed", 0ULL);
}

PublicRoundState parse_replay_round_state(const json &raw_state, int round_index) {
    PublicRoundState state;
    state.round_index = round_index;

    if (raw_state.contains("towers") && raw_state.at("towers").is_array()) {
        for (const auto &row : raw_state.at("towers")) {
            const int type = row.value("type", -1);
            if (type < 0) {
                continue;
            }
            state.towers.push_back(Tower{
                row.value("id", -1),
                row.value("player", -1),
                row.value("pos", json::object()).value("x", -1),
                row.value("pos", json::object()).value("y", -1),
                static_cast<TowerType>(type),
                row.value("cd", 0),
                row.value("hp", tower_stats(static_cast<TowerType>(type)).max_hp),
            });
        }
    }

    if (raw_state.contains("ants") && raw_state.at("ants").is_array()) {
        for (const auto &row : raw_state.at("ants")) {
            Ant ant{
                row.value("id", -1),
                row.value("player", -1),
                row.value("pos", json::object()).value("x", -1),
                row.value("pos", json::object()).value("y", -1),
                row.value("hp", 0),
                row.value("level", 0),
                row.value("age", 0),
                static_cast<AntStatus>(row.value("status", 0)),
                static_cast<AntBehavior>(row.value("behavior", 0)),
                static_cast<AntKind>(row.value("kind", 0)),
            };
            ant.last_move = row.value("move", -1);
            state.ants.push_back(ant);
        }
    }

    const auto coins = raw_state.value("coins", std::vector<int>{kInitialCoins, kInitialCoins});
    if (coins.size() >= 2) {
        state.coins = {coins[0], coins[1]};
    }
    const auto camps = raw_state.value("camps", std::vector<int>{kBaseHp, kBaseHp});
    if (camps.size() >= 2) {
        state.camps_hp = {camps[0], camps[1]};
    }
    const auto speed_lv = raw_state.value("speedLv", std::vector<int>{0, 0});
    if (speed_lv.size() >= 2) {
        state.speed_lv = {speed_lv[0], speed_lv[1]};
    }
    const auto anthp_lv = raw_state.value("anthpLv", std::vector<int>{0, 0});
    if (anthp_lv.size() >= 2) {
        state.anthp_lv = {anthp_lv[0], anthp_lv[1]};
    }

    if (raw_state.contains("weaponCooldowns") && raw_state.at("weaponCooldowns").is_array()) {
        int player = 0;
        for (const auto &row : raw_state.at("weaponCooldowns")) {
            if (player >= 2 || !row.is_array()) {
                break;
            }
            if (row.size() == 4) {
                state.weapon_cooldowns[player] = {
                    0,
                    row.at(0).get<int>(),
                    row.at(1).get<int>(),
                    row.at(2).get<int>(),
                    row.at(3).get<int>(),
                };
            } else if (row.size() >= 5) {
                state.weapon_cooldowns[player] = {
                    row.at(0).get<int>(),
                    row.at(1).get<int>(),
                    row.at(2).get<int>(),
                    row.at(3).get<int>(),
                    row.at(4).get<int>(),
                };
            }
            ++player;
        }
    }

    if (raw_state.contains("activeEffects") && raw_state.at("activeEffects").is_array()) {
        for (const auto &row : raw_state.at("activeEffects")) {
            state.active_effects.push_back(WeaponEffect{
                static_cast<SuperWeaponType>(row.value("type", 1)),
                row.value("player", -1),
                row.value("x", -1),
                row.value("y", -1),
                row.value("duration", 0),
            });
        }
    }

    return state;
}

void apply_replay_tower_delta(const json &raw_state, std::unordered_map<int, Tower> &towers_by_id) {
    if (!raw_state.contains("towers") || !raw_state.at("towers").is_array()) {
        return;
    }
    for (const auto &row : raw_state.at("towers")) {
        const int tower_id = row.value("id", -1);
        if (tower_id < 0) {
            continue;
        }
        const int type = row.value("type", -1);
        if (type < 0) {
            towers_by_id.erase(tower_id);
            continue;
        }
        towers_by_id[tower_id] = Tower{
            tower_id,
            row.value("player", -1),
            row.value("pos", json::object()).value("x", -1),
            row.value("pos", json::object()).value("y", -1),
            static_cast<TowerType>(type),
            row.value("cd", 0),
            row.value("hp", tower_stats(static_cast<TowerType>(type)).max_hp),
        };
    }
}

std::vector<Tower> snapshot_replay_towers(const std::unordered_map<int, Tower> &towers_by_id) {
    std::vector<Tower> towers;
    towers.reserve(towers_by_id.size());
    for (const auto &item : towers_by_id) {
        towers.push_back(item.second);
    }
    std::sort(towers.begin(), towers.end(), [](const Tower &lhs, const Tower &rhs) {
        if (lhs.player != rhs.player) {
            return lhs.player < rhs.player;
        }
        return lhs.tower_id < rhs.tower_id;
    });
    return towers;
}

void advance_replay_tower_cooldowns(std::unordered_map<int, Tower> &towers_by_id) {
    for (auto &item : towers_by_id) {
        Tower &tower = item.second;
        if (tower.cooldown > 0) {
            --tower.cooldown;
        }
    }
}

NativeSimulator load_replay_round(const json &replay, int target_round) {
    NativeSimulator simulator(replay_seed(replay));
    const int limit = std::min(target_round, static_cast<int>(replay.size()));
    std::unordered_map<int, Tower> towers_by_id;
    for (int round = 0; round < limit; ++round) {
        const auto &record = replay.at(static_cast<std::size_t>(round));
        const auto ops0 = parse_replay_operations(record.value("op0", json::array()));
        const auto ops1 = parse_replay_operations(record.value("op1", json::array()));
        simulator.resolve_turn(ops0, ops1);
        if (record.contains("round_state") && record.at("round_state").is_object()) {
            const auto &round_state = record.at("round_state");
            advance_replay_tower_cooldowns(towers_by_id);
            apply_replay_tower_delta(round_state, towers_by_id);
            PublicRoundState public_state = parse_replay_round_state(round_state, round + 1);
            public_state.towers = snapshot_replay_towers(towers_by_id);
            simulator.sync_public_round_state(public_state);
        }
    }
    return simulator;
}

void prune_defense_state(
    PublicRoundState &state,
    int player,
    const std::unordered_set<int> &root_ant_ids,
    const std::unordered_set<int> &root_tower_ids) {
    const int enemy = 1 - player;

    std::vector<Tower> towers;
    towers.reserve(state.towers.size());
    for (const auto &tower : state.towers) {
        if (tower.player == player && root_tower_ids.count(tower.tower_id) != 0) {
            towers.push_back(tower);
        }
    }
    state.towers = std::move(towers);

    std::vector<Ant> ants;
    ants.reserve(state.ants.size());
    for (const auto &ant : state.ants) {
        if (ant.player == enemy && root_ant_ids.count(ant.ant_id) != 0 && ant.is_alive()) {
            ants.push_back(ant);
        }
    }
    state.ants = std::move(ants);

    std::vector<WeaponEffect> effects;
    effects.reserve(state.active_effects.size());
    for (const auto &effect : state.active_effects) {
        if ((effect.player == player && effect.weapon_type == SuperWeaponType::LightningStorm) ||
            effect.player == enemy) {
            effects.push_back(effect);
        }
    }
    state.active_effects = std::move(effects);
}

rs::DefenseSimulator defense_simulator_from_public(
    const PublicRoundState &round_state,
    std::uint64_t seed,
    const NativeSimulator &native,
    int player) {
    PublicState state(seed, native.movement_policy(), native.cold_handle_rule_illegal());
    state.sync_public_round_state(round_state);
    rs::DefenseSimulator simulator = rs::make_defense_simulator(state, &native, player);
    simulator.ignore_enemy_spawns = true;
    return simulator;
}

RunEval run_fast(
    const rs::DefenseSimulator &root,
    int player,
    int rollouts,
    int horizon,
    std::uint64_t seed_base) {
    RunEval total;
    total.steps.resize(std::max(0, horizon));
    for (int rollout = 0; rollout < rollouts; ++rollout) {
        rs::DefenseSimulator simulator = root.clone();
        rs::FastRng rng(rs::mix_seed(seed_base, static_cast<std::uint64_t>(rollout + 1)));
        for (int step = 0; step < horizon; ++step) {
            if (!simulator.terminal) {
                simulator.simulate_round(rng);
            }
            total.steps[static_cast<std::size_t>(step)].add(ls::evaluate_terminal(simulator, player), simulator);
        }
        total.terminal.add(ls::evaluate_terminal(simulator, player), simulator);
    }
    const double factor = 1.0 / std::max(1, rollouts);
    total.terminal.scale(factor);
    for (auto &step : total.steps) {
        step.scale(factor);
    }
    return total;
}

RunEval run_native(
    const NativeSimulator &native_root,
    int player,
    const std::unordered_set<int> &root_ant_ids,
    const std::unordered_set<int> &root_tower_ids,
    int rollouts,
    int horizon,
    std::uint64_t seed_base) {
    RunEval total;
    total.steps.resize(std::max(0, horizon));
    for (int rollout = 0; rollout < rollouts; ++rollout) {
        NativeSimulator native = native_root.clone();
        native.reseed_future(rs::mix_seed(seed_base, static_cast<std::uint64_t>(0x9e3779b9U + rollout)));
        PublicRoundState current = native.to_public_round_state();
        for (int step = 0; step < horizon; ++step) {
            if (!native.terminal()) {
                native.advance_round_without_base_spawns();
                current = native.to_public_round_state();
                prune_defense_state(current, player, root_ant_ids, root_tower_ids);
                native.sync_public_round_state(current);
            }
            current = native.to_public_round_state();
            prune_defense_state(current, player, root_ant_ids, root_tower_ids);
            rs::DefenseSimulator snapshot = defense_simulator_from_public(current, native.seed(), native, player);
            total.steps[static_cast<std::size_t>(step)].add(ls::evaluate_terminal(snapshot, player), snapshot);
        }
        current = native.to_public_round_state();
        prune_defense_state(current, player, root_ant_ids, root_tower_ids);
        rs::DefenseSimulator terminal = defense_simulator_from_public(current, native.seed(), native, player);
        total.terminal.add(ls::evaluate_terminal(terminal, player), terminal);
    }
    const double factor = 1.0 / std::max(1, rollouts);
    total.terminal.scale(factor);
    for (auto &step : total.steps) {
        step.scale(factor);
    }
    return total;
}

json root_state_to_json(const PublicRoundState &state, const NativeSimulator &native) {
    std::unordered_map<int, NativeAntHiddenState> hidden_by_id;
    for (const auto &row : native.ant_hidden_states()) {
        hidden_by_id.emplace(row.ant_id, row);
    }
    json ants = json::array();
    for (const auto &ant : state.ants) {
        json row{
            {"id", ant.ant_id},
            {"player", ant.player},
            {"x", ant.x},
            {"y", ant.y},
            {"hp", ant.hp},
            {"level", ant.level},
            {"age", ant.age},
            {"status", static_cast<int>(ant.status)},
            {"behavior", static_cast<int>(ant.behavior)},
            {"kind", static_cast<int>(ant.kind)},
            {"last_move", ant.last_move},
        };
        auto it = hidden_by_id.find(ant.ant_id);
        if (it != hidden_by_id.end()) {
            row["shield"] = it->second.shield;
            row["defend"] = it->second.defend;
            row["frozen"] = it->second.is_frozen;
            row["behavior_rounds"] = it->second.behavior_rounds;
            row["behavior_expiry"] = it->second.behavior_expiry;
            row["target_x"] = it->second.target_x;
            row["target_y"] = it->second.target_y;
        }
        ants.push_back(row);
    }
    json towers = json::array();
    for (const auto &tower : state.towers) {
        towers.push_back(json{
            {"id", tower.tower_id},
            {"player", tower.player},
            {"x", tower.x},
            {"y", tower.y},
            {"type", static_cast<int>(tower.tower_type)},
            {"hp", tower.hp},
            {"cooldown", tower.cooldown},
        });
    }
    json effects = json::array();
    for (const auto &effect : state.active_effects) {
        effects.push_back(json{
            {"player", effect.player},
            {"type", static_cast<int>(effect.weapon_type)},
            {"x", effect.x},
            {"y", effect.y},
            {"remaining", effect.remaining_turns},
        });
    }
    return json{{"ants", ants}, {"towers", towers}, {"effects", effects}};
}

json fast_move_options_to_json(const rs::DefenseSimulator &simulator) {
    json out = json::array();
    for (const auto &ant : simulator.ants) {
        json options = json::array();
        const auto evaluated = simulator.evaluate_move_options(ant);
        for (const auto &option : evaluated.options) {
            options.push_back(json{
                {"direction", option.direction},
                {"x", option.nx},
                {"y", option.ny},
                {"probability", option.probability},
                {"danger", option.danger},
            });
        }
        out.push_back(json{
            {"id", ant.ant_id},
            {"x", ant.x},
            {"y", ant.y},
            {"kind", static_cast<int>(ant.kind)},
            {"behavior", static_cast<int>(ant.behavior)},
            {"last_move", ant.last_move},
            {"options", options},
        });
    }
    return out;
}

} // namespace antgame::sdk::examples

int main(int argc, char **argv) {
    using namespace antgame::sdk;
    using namespace antgame::sdk::examples;

    try {
        if (argc < 7) {
            throw std::runtime_error(
                "usage: sdk_defense_parity <replay.json> <round> <player> <rollouts> <horizon> <seed>");
        }
        const std::string replay_path = argv[1];
        const int round = std::stoi(argv[2]);
        const int player = std::stoi(argv[3]);
        const int rollouts = std::stoi(argv[4]);
        const int horizon = std::stoi(argv[5]);
        const std::uint64_t seed_base = static_cast<std::uint64_t>(std::stoull(argv[6]));

        std::ifstream fin(replay_path);
        if (!fin) {
            throw std::runtime_error("failed to open replay: " + replay_path);
        }
        json replay;
        fin >> replay;

        NativeSimulator native = load_replay_round(replay, round);
        PublicRoundState root_round = native.to_public_round_state();

        std::unordered_set<int> root_ant_ids;
        std::unordered_set<int> root_tower_ids;
        for (const auto &ant : root_round.ants) {
            if (ant.player == 1 - player && ant.is_alive()) {
                root_ant_ids.insert(ant.ant_id);
            }
        }
        for (const auto &tower : root_round.towers) {
            if (tower.player == player) {
                root_tower_ids.insert(tower.tower_id);
            }
        }

        prune_defense_state(root_round, player, root_ant_ids, root_tower_ids);
        native.sync_public_round_state(root_round);
        rs::DefenseSimulator fast_root = defense_simulator_from_public(root_round, replay_seed(replay), native, player);

        const RunEval fast = run_fast(fast_root, player, rollouts, horizon, seed_base);
        const RunEval native_mean = run_native(native, player, root_ant_ids, root_tower_ids, rollouts, horizon, seed_base);

        json out;
        out["ok"] = true;
        out["replay"] = replay_path;
        out["round"] = round;
        out["player"] = player;
        out["rollouts"] = rollouts;
        out["horizon"] = horizon;
        out["seed"] = seed_base;
        out["root_towers"] = root_round.towers.size();
        out["root_ants"] = root_round.ants.size();
        out["root_effects"] = root_round.active_effects.size();
        out["root_state"] = root_state_to_json(root_round, native);
        out["root_fast_move_options"] = fast_move_options_to_json(fast_root);
        out["fast"] = run_to_json(fast);
        out["native"] = run_to_json(native_mean);
        out["diff_fast_minus_native"] = run_diff_to_json(fast, native_mean);
        std::cout << out.dump() << '\n';
        return 0;
    } catch (const std::exception &exc) {
        json out;
        out["ok"] = false;
        out["error"] = exc.what();
        std::cout << out.dump() << '\n';
        return 1;
    }
}
