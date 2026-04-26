#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "json.hpp"

#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/random_search_baseline.hpp"
#include "antgame_sdk/sdk.hpp"

using json = nlohmann::json;

using antgame::sdk::NativeSimulator;
using antgame::sdk::Operation;
using antgame::sdk::OperationType;
using antgame::sdk::PublicState;

namespace rs = antgame::sdk::random_search_detail;

namespace {

int json_int_or(const json &obj, const char *key, int fallback) {
    if (!obj.is_object() || !obj.contains(key)) {
        return fallback;
    }
    const auto &value = obj[key];
    if (!value.is_number_integer()) {
        return fallback;
    }
    return value.get<int>();
}

Operation parse_operation_spec(const std::string &spec) {
    std::vector<int> parts;
    std::stringstream ss(spec);
    std::string token;
    while (std::getline(ss, token, ':')) {
        if (token.empty()) {
            continue;
        }
        parts.push_back(std::stoi(token));
    }
    if (parts.empty()) {
        throw std::runtime_error("empty operation spec");
    }
    const auto type = static_cast<OperationType>(parts[0]);
    if (parts.size() == 1) {
        return Operation(type);
    }
    if (parts.size() == 2) {
        return Operation(type, parts[1]);
    }
    return Operation(type, parts[1], parts[2]);
}

std::vector<Operation> parse_replay_ops(const json &value) {
    std::vector<Operation> out;
    if (!value.is_array()) {
        return out;
    }
    for (const auto &item : value) {
        if (!item.is_object()) {
            continue;
        }
        const int type = json_int_or(item, "type", -1);
        const int id = json_int_or(item, "id", -1);
        const int args = json_int_or(item, "args", -1);
        int x = -1;
        int y = -1;
        if (item.contains("pos") && item["pos"].is_object()) {
            x = json_int_or(item["pos"], "x", -1);
            y = json_int_or(item["pos"], "y", -1);
        }
        const auto op_type = static_cast<OperationType>(type);
        switch (op_type) {
        case OperationType::BuildTower:
        case OperationType::UseLightningStorm:
        case OperationType::UseEmpBlaster:
        case OperationType::UseDeflector:
        case OperationType::UseEmergencyEvasion:
            out.emplace_back(op_type, x, y);
            break;
        case OperationType::UpgradeTower:
            out.emplace_back(op_type, id, args);
            break;
        case OperationType::DowngradeTower:
            out.emplace_back(op_type, id);
            break;
        case OperationType::UpgradeGenerationSpeed:
        case OperationType::UpgradeGeneratedAnt:
            out.emplace_back(op_type);
            break;
        default:
            break;
        }
    }
    return out;
}

NativeSimulator replay_to_round(const json &records, int target_round) {
    if (!records.is_array() || records.empty()) {
        throw std::runtime_error("invalid replay records");
    }
    std::uint64_t seed = 0ULL;
    std::size_t start_index = 0;
    for (std::size_t index = 0; index < records.size(); ++index) {
        const auto &record = records.at(index);
        if (!record.is_object()) {
            continue;
        }
        if (record.contains("seed") && record["seed"].is_number_unsigned()) {
            seed = record["seed"].get<std::uint64_t>();
            start_index = index;
            break;
        }
        if (record.contains("seed") && record["seed"].is_number_integer()) {
            seed = static_cast<std::uint64_t>(record["seed"].get<long long>());
            start_index = index;
            break;
        }
    }
    NativeSimulator simulator(seed);
    for (int round = 0; round < target_round; ++round) {
        const std::size_t record_index = start_index + static_cast<std::size_t>(round);
        if (record_index >= records.size()) {
            break;
        }
        const auto &record = records.at(record_index);
        if (!record.is_object()) {
            continue;
        }
        const auto ops0 = parse_replay_ops(record.value("op0", json::array()));
        const auto ops1 = parse_replay_ops(record.value("op1", json::array()));
        simulator.resolve_turn(ops0, ops1);
    }
    return simulator;
}

rs::SearchPlan parse_plan_spec(const PublicState &state, int player, const std::string &spec) {
    rs::SearchPlan plan;
    plan.name = spec;
    if (spec == "hold") {
        plan.penalty = rs::operation_penalty_breakdown(state, player, plan).total;
        return plan;
    }

    std::stringstream ss(spec);
    std::string op_spec;
    std::vector<Operation> ops;
    while (std::getline(ss, op_spec, '|')) {
        if (!op_spec.empty()) {
            ops.push_back(parse_operation_spec(op_spec));
        }
    }
    if (ops.empty() || ops.size() > 2) {
        throw std::runtime_error("plan spec must be hold or 1-2 operations");
    }
    plan.has_first = true;
    plan.first = ops[0];
    if (ops.size() == 2) {
        plan.has_second = true;
        plan.second = ops[1];
    }
    if (plan.first.op_type == OperationType::DowngradeTower) {
        const auto *tower = state.tower_by_id(plan.first.arg0);
        if (tower != nullptr) {
            plan.blocked_x = tower->x;
            plan.blocked_y = tower->y;
            plan.blocked_tower_id = tower->tower_id;
        }
    }
    plan.penalty = rs::operation_penalty_breakdown(state, player, plan).total;
    return plan;
}

rs::TerminalEvaluationBreakdown average_breakdown(const rs::TerminalEvaluationBreakdown &sum, int samples) {
    rs::TerminalEvaluationBreakdown out = sum;
    const double inv = samples > 0 ? 1.0 / static_cast<double>(samples) : 0.0;
    out.base_hp_raw *= inv;
    out.base_hp_score *= inv;
    out.tower_value_raw *= inv;
    out.tower_value_score *= inv;
    out.tower_bonus_score *= inv;
    out.ant_threat_raw *= inv;
    out.ant_threat_score *= inv;
    out.money_raw *= inv;
    out.money_score *= inv;
    out.total *= inv;
    return out;
}

rs::TerminalEvaluationBreakdown direct_mc_plan(
    const rs::DefenseSimulator &root,
    const rs::SearchPlan &plan,
    const rs::OffensiveExpectation &offense,
    std::uint64_t seed_base,
    int rollouts) {
    rs::TerminalEvaluationBreakdown total;
    for (int rollout = 0; rollout < rollouts; ++rollout) {
        rs::DefenseSimulator sim = root.clone();
        if (plan.has_first) {
            sim.apply_operation(plan.first);
        }
        rs::FastRng rng(rs::mix_seed(seed_base, static_cast<std::uint64_t>(rollout + 1)));
        for (int step = 0; step < antgame::sdk::config().defense_horizon && !sim.terminal; ++step) {
            if (step == 1 && plan.has_second &&
                sim.can_apply_operation(plan.second, plan.blocked_x, plan.blocked_y, plan.blocked_tower_id)) {
                sim.apply_operation(plan.second);
            }
            sim.simulate_round(rng);
            sim.coins += offense.money_gain_by_round[static_cast<std::size_t>(step)];
        }
        total += rs::terminal_evaluation_breakdown(sim);
    }
    return average_breakdown(total, rollouts);
}

bool can_apply_native_second_operation(const NativeSimulator &native, int player, const rs::SearchPlan &plan) {
    if (!plan.has_second) {
        return false;
    }
    PublicState state(native.seed(), native.movement_policy(), native.cold_handle_rule_illegal());
    state.sync_public_round_state(native.to_public_round_state());
    if (!state.can_apply_operation(player, plan.second)) {
        return false;
    }
    if (plan.blocked_x >= 0 && plan.second.op_type == OperationType::BuildTower &&
        plan.second.arg0 == plan.blocked_x && plan.second.arg1 == plan.blocked_y) {
        return false;
    }
    if (plan.blocked_tower_id >= 0 &&
        (plan.second.op_type == OperationType::UpgradeTower || plan.second.op_type == OperationType::DowngradeTower) &&
        plan.second.arg0 == plan.blocked_tower_id) {
        return false;
    }
    return true;
}

rs::TerminalEvaluationBreakdown native_mc_plan(
    const NativeSimulator &native_root,
    int player,
    const rs::SearchPlan &plan,
    std::uint64_t seed_base,
    int rollouts) {
    rs::TerminalEvaluationBreakdown total;
    for (int rollout = 0; rollout < rollouts; ++rollout) {
        NativeSimulator native = native_root.clone();
        native.reseed_future(rs::mix_seed(seed_base, static_cast<std::uint64_t>(rollout + 1)));
        if (plan.has_first) {
            const auto illegal = native.apply_operation_list(player, {plan.first});
            if (!illegal.empty()) {
                throw std::runtime_error("native first operation became illegal");
            }
        }
        for (int step = 0; step < antgame::sdk::config().defense_horizon && !native.terminal(); ++step) {
            const auto result = native.advance_round_without_base_spawns();
            if (result.terminal) {
                break;
            }
            if (step == 0 && can_apply_native_second_operation(native, player, plan)) {
                const auto illegal = native.apply_operation_list(player, {plan.second});
                if (!illegal.empty()) {
                    throw std::runtime_error("native second operation became illegal");
                }
            }
        }
        PublicState terminal_state(native.seed(), native.movement_policy(), native.cold_handle_rule_illegal());
        terminal_state.sync_public_round_state(native.to_public_round_state());
        const auto terminal_sim = rs::make_defense_simulator(terminal_state, &native, player);
        total += rs::terminal_evaluation_breakdown(terminal_sim);
    }
    return average_breakdown(total, rollouts);
}

} // namespace

int main(int argc, char **argv) {
    if (argc < 6) {
        std::cerr << "usage: sdk_rollout_probe <replay.json> <round> <player> <rollouts> <plan...>\n";
        std::cerr << "plan example: hold or 11:4:9 or 13:126|11:4:9\n";
        return 1;
    }

    const std::string replay_path = argv[1];
    const int target_round = std::stoi(argv[2]);
    const int player = std::stoi(argv[3]);
    const int rollouts = std::stoi(argv[4]);

    json replay;
    {
        std::ifstream fin(replay_path);
        if (!fin) {
            throw std::runtime_error("failed to open replay");
        }
        fin >> replay;
    }

    NativeSimulator native = replay_to_round(replay, target_round);
    PublicState state(native.seed(), native.movement_policy(), native.cold_handle_rule_illegal());
    state.sync_public_round_state(native.to_public_round_state());

    const auto threat = rs::immediate_threat_context(state, player);
    std::cout << "{"
              << "\"round\":" << target_round
              << ",\"player\":" << player
              << ",\"coins\":" << state.coins[player]
              << ",\"base_hp\":" << state.bases[player].hp
              << ",\"tower_count\":" << state.tower_count(player)
              << ",\"enemy_ant_count\":" << state.ants_of(1 - player).size()
              << ",\"enemy_combat_ring1\":" << threat.combat_ring1
              << ",\"enemy_combat_ring2\":" << threat.combat_ring2
              << ",\"combat_pressure\":" << threat.combat_pressure
              << ",\"tower_pressure\":" << threat.tower_pressure
              << ",\"rollouts\":" << rollouts
              << ",\"towers\":[";
    bool first_tower = true;
    for (const auto &tower : state.towers) {
        if (tower.player != player || tower.hp <= 0) {
            continue;
        }
        if (!first_tower) {
            std::cout << ',';
        }
        first_tower = false;
        std::cout << "{"
                  << "\"id\":" << tower.tower_id
                  << ",\"type\":" << static_cast<int>(tower.tower_type)
                  << ",\"hp\":" << tower.hp
                  << ",\"x\":" << tower.x
                  << ",\"y\":" << tower.y
                  << "}";
    }
    std::cout << "]"
              << "}\n";

    const auto offense = rs::compute_offense_expectation(state, player);
    const auto root = rs::make_defense_simulator(state, &native, player);

    for (int index = 5; index < argc; ++index) {
        const std::string spec = argv[index];
        const auto plan = parse_plan_spec(state, player, spec);
        const auto penalty = rs::operation_penalty_breakdown(state, player, plan);
        const auto terminal = direct_mc_plan(root, plan, offense, rs::mix_seed(state.seed, static_cast<std::uint64_t>(index)), rollouts);
        const auto native_terminal = native_mc_plan(native, player, plan, rs::mix_seed(state.seed, static_cast<std::uint64_t>(0xabc000 + index)), rollouts);
        rs::DefenseSimulator seeded = root.clone();
        if (plan.has_first) {
            seeded.apply_operation(plan.first);
        }
        const auto combo_count = rs::rollout_combos_for(seeded).size();
        std::cout << "{"
                  << "\"plan\":\"" << spec << "\""
                  << ",\"score_before_penalty\":" << terminal.total
                  << ",\"score\":" << (terminal.total - penalty.total)
                  << ",\"penalty\":" << penalty.total
                  << ",\"base_hp_raw\":" << terminal.base_hp_raw
                  << ",\"tower_value_raw\":" << terminal.tower_value_raw
                  << ",\"ant_threat_raw\":" << terminal.ant_threat_raw
                  << ",\"money_raw\":" << terminal.money_raw
                  << ",\"base_hp_score\":" << terminal.base_hp_score
                  << ",\"tower_value_score\":" << terminal.tower_value_score
                  << ",\"tower_bonus_score\":" << terminal.tower_bonus_score
                  << ",\"ant_threat_score\":" << terminal.ant_threat_score
                  << ",\"money_score\":" << terminal.money_score
                  << ",\"pen_downgrade\":" << penalty.downgrade
                  << ",\"pen_lightning\":" << penalty.lightning
                  << ",\"pen_hold_bias\":" << penalty.hold_bias
                  << ",\"pen_emergency_discount\":" << penalty.emergency_discount
                  << ",\"native_score_before_penalty\":" << native_terminal.total
                  << ",\"native_score\":" << (native_terminal.total - penalty.total)
                  << ",\"native_base_hp_raw\":" << native_terminal.base_hp_raw
                  << ",\"native_tower_value_raw\":" << native_terminal.tower_value_raw
                  << ",\"native_ant_threat_raw\":" << native_terminal.ant_threat_raw
                  << ",\"native_money_raw\":" << native_terminal.money_raw
                  << ",\"native_base_hp_score\":" << native_terminal.base_hp_score
                  << ",\"native_tower_value_score\":" << native_terminal.tower_value_score
                  << ",\"native_tower_bonus_score\":" << native_terminal.tower_bonus_score
                  << ",\"native_ant_threat_score\":" << native_terminal.ant_threat_score
                  << ",\"native_money_score\":" << native_terminal.money_score
                  << ",\"combo_count\":" << combo_count
                  << "}\n";
    }
    return 0;
}
