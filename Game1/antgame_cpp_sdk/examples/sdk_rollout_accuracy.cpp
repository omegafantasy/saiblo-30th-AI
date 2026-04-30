#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

#include "json.hpp"

#include "antgame_ai/lure_strategy_v3.hpp"
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/random_search_baseline.hpp"
#include "antgame_sdk/sdk.hpp"

using json = nlohmann::json;

using antgame::sdk::NativeSimulator;
using antgame::sdk::Operation;
using antgame::sdk::OperationType;
using antgame::sdk::PublicState;

namespace ls = antgame::sdk::lure_strategy_detail;
namespace rs = antgame::sdk::random_search_detail;

namespace {

struct ReplaySnapshot {
    PublicState state;
    NativeSimulator simulator;
};

struct CaseSpec {
    std::string replay_path;
    int round = 0;
    int player = 0;
};

struct Outcome {
    double final_base_hp = 0.0;
    double final_money = 0.0;
    double final_worker_threat = 0.0;
    double final_combat_threat = 0.0;
    double final_threat = 0.0;
    double final_value_total = 0.0;
    double v3_total_score = 0.0;
};

struct Estimate {
    Outcome mean;
    double weight_sum = 0.0;
    int samples = 0;
};

int json_int_or(const json &obj, const char *key, int fallback) {
    if (!obj.is_object() || !obj.contains(key) || !obj[key].is_number_integer()) {
        return fallback;
    }
    return obj[key].get<int>();
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
        const auto type = static_cast<OperationType>(json_int_or(item, "type", -1));
        const int id = json_int_or(item, "id", -1);
        const int args = json_int_or(item, "args", -1);
        int x = -1;
        int y = -1;
        if (item.contains("pos") && item["pos"].is_object()) {
            x = json_int_or(item["pos"], "x", -1);
            y = json_int_or(item["pos"], "y", -1);
        }
        switch (type) {
        case OperationType::BuildTower:
        case OperationType::UseLightningStorm:
        case OperationType::UseEmpBlaster:
        case OperationType::UseDeflector:
        case OperationType::UseEmergencyEvasion:
            out.emplace_back(type, x, y);
            break;
        case OperationType::UpgradeTower:
            out.emplace_back(type, id, args);
            break;
        case OperationType::DowngradeTower:
            out.emplace_back(type, id);
            break;
        case OperationType::UpgradeGenerationSpeed:
        case OperationType::UpgradeGeneratedAnt:
            out.emplace_back(type);
            break;
        default:
            break;
        }
    }
    return out;
}

std::uint64_t replay_seed(const json &records) {
    if (!records.is_array()) {
        throw std::runtime_error("replay is not an array");
    }
    for (const auto &record : records) {
        if (!record.is_object() || !record.contains("seed")) {
            continue;
        }
        if (record["seed"].is_number_unsigned()) {
            return record["seed"].get<std::uint64_t>();
        }
        if (record["seed"].is_number_integer()) {
            return static_cast<std::uint64_t>(record["seed"].get<long long>());
        }
    }
    throw std::runtime_error("failed to locate replay seed");
}

ReplaySnapshot replay_to_round(const json &records, int target_round) {
    const std::uint64_t seed = replay_seed(records);
    NativeSimulator simulator(seed);
    for (int round = 0; round < target_round; ++round) {
        if (round >= static_cast<int>(records.size())) {
            break;
        }
        const auto &record = records.at(static_cast<std::size_t>(round));
        if (!record.is_object()) {
            continue;
        }
        const auto ops0 = parse_replay_ops(record.value("op0", json::array()));
        const auto ops1 = parse_replay_ops(record.value("op1", json::array()));
        simulator.resolve_turn(ops0, ops1);
    }
    PublicState state(seed, simulator.movement_policy(), simulator.cold_handle_rule_illegal());
    state.sync_public_round_state(simulator.to_public_round_state());
    return ReplaySnapshot{state, simulator.clone()};
}

CaseSpec parse_case_spec(const std::string &text) {
    const std::size_t last_colon = text.rfind(':');
    if (last_colon == std::string::npos) {
        throw std::runtime_error("case spec must be replay:round:player");
    }
    const std::size_t prev_colon = text.rfind(':', last_colon - 1);
    if (prev_colon == std::string::npos) {
        throw std::runtime_error("case spec must be replay:round:player");
    }
    CaseSpec spec;
    spec.replay_path = text.substr(0, prev_colon);
    spec.round = std::stoi(text.substr(prev_colon + 1, last_colon - prev_colon - 1));
    spec.player = std::stoi(text.substr(last_colon + 1));
    return spec;
}

json outcome_to_json(const Outcome &out) {
    return json{
        {"final_base_hp", out.final_base_hp},
        {"final_money", out.final_money},
        {"final_worker_threat", out.final_worker_threat},
        {"final_combat_threat", out.final_combat_threat},
        {"final_threat", out.final_threat},
        {"final_value_total", out.final_value_total},
        {"v3_total_score", out.v3_total_score},
    };
}

json estimate_to_json(const Estimate &estimate, const Outcome &truth) {
    json out;
    out["samples"] = estimate.samples;
    out["weight_sum"] = estimate.weight_sum;
    out["mean"] = outcome_to_json(estimate.mean);
    out["abs_error"] = json{
        {"final_base_hp", std::abs(estimate.mean.final_base_hp - truth.final_base_hp)},
        {"final_money", std::abs(estimate.mean.final_money - truth.final_money)},
        {"final_threat", std::abs(estimate.mean.final_threat - truth.final_threat)},
        {"final_value_total", std::abs(estimate.mean.final_value_total - truth.final_value_total)},
        {"v3_total_score", std::abs(estimate.mean.v3_total_score - truth.v3_total_score)},
    };
    return out;
}

Outcome scale_outcome(Outcome out, double factor) {
    out.final_base_hp *= factor;
    out.final_money *= factor;
    out.final_worker_threat *= factor;
    out.final_combat_threat *= factor;
    out.final_threat *= factor;
    out.final_value_total *= factor;
    out.v3_total_score *= factor;
    return out;
}

Outcome &add_scaled(Outcome &target, const Outcome &value, double weight) {
    target.final_base_hp += value.final_base_hp * weight;
    target.final_money += value.final_money * weight;
    target.final_worker_threat += value.final_worker_threat * weight;
    target.final_combat_threat += value.final_combat_threat * weight;
    target.final_threat += value.final_threat * weight;
    target.final_value_total += value.final_value_total * weight;
    target.v3_total_score += value.v3_total_score * weight;
    return target;
}

Outcome simulate_plan_outcome(
    const rs::DefenseSimulator &root,
    int player,
    const ls::CombinedPlan &plan,
    std::uint64_t rollout_seed,
    double root_c1_bonus,
    const rs::FixedList<rs::ForcedMove, rs::kMaxImportantAnts> *first_round_forced_moves) {
    rs::DefenseSimulator simulator = root.clone();
    if (!plan.ops.empty() && !ls::apply_operations(simulator, plan.ops)) {
        Outcome failed;
        failed.v3_total_score = -std::numeric_limits<double>::infinity();
        failed.final_value_total = -std::numeric_limits<double>::infinity();
        return failed;
    }

    rs::FastRng rng(rollout_seed);
    if (first_round_forced_moves != nullptr) {
        simulator.simulate_round(rng, *first_round_forced_moves);
    } else {
        simulator.simulate_round(rng);
    }

    double lightning_bonus_score = 0.0;
    if (plan.has_lightning) {
        rs::DefenseSimulator control = root.clone();
        if (!plan.ops.empty()) {
            ls::apply_operations(control, ls::strip_lightning_operations(plan.ops));
        }
        rs::FastRng control_rng(rollout_seed);
        if (first_round_forced_moves != nullptr) {
            control.simulate_round(control_rng, *first_round_forced_moves);
        } else {
            control.simulate_round(control_rng);
        }
        lightning_bonus_score = ls::lightning_counterfactual_bonus(simulator, control, player) + plan.lightning_static_bonus;
    }

    ls::EvalBreakdown mid_eval;
    bool has_mid_eval = false;
    double reactive_penalty = 0.0;
    double mid_reactive_penalty = 0.0;
    const int mid_horizon = std::max(0, std::min(plan.horizon, antgame::sdk::v3_lure_config().mid_eval_horizon));
    int step = 1;
    auto capture_mid_eval = [&]() {
        if (!has_mid_eval && step >= mid_horizon) {
            mid_eval = ls::evaluate_terminal(simulator, player);
            mid_reactive_penalty = reactive_penalty;
            has_mid_eval = true;
        }
    };

    capture_mid_eval();
    while (step < plan.horizon && !simulator.terminal) {
        if (ls::followup_has_turn(plan.followup, step)) {
            const auto followup_ops = ls::resolve_followup_operations(simulator, player, plan.followup, step);
            ls::apply_operations(simulator, followup_ops);
        } else {
            reactive_penalty += ls::apply_reactive_turn_operations_with_penalty(simulator, player);
        }
        simulator.simulate_round(rng);
        ++step;
        capture_mid_eval();
    }

    const ls::EvalBreakdown final_eval = ls::evaluate_terminal(simulator, player);
    if (!has_mid_eval) {
        mid_eval = final_eval;
        mid_reactive_penalty = reactive_penalty;
    }
    const ls::EvalBreakdown combined =
        ls::combine_eval_breakdowns(mid_eval, final_eval, antgame::sdk::v3_lure_config().mid_eval_weight);
    const double mid_weight = std::max(0.0, std::min(1.0, antgame::sdk::v3_lure_config().mid_eval_weight));
    const double weighted_reactive_penalty = mid_weight * mid_reactive_penalty + (1.0 - mid_weight) * reactive_penalty;

    Outcome out;
    out.final_base_hp = final_eval.base_hp_raw;
    out.final_money = final_eval.money_raw;
    out.final_worker_threat = final_eval.worker_threat_raw;
    out.final_combat_threat = final_eval.combat_threat_raw;
    out.final_threat = final_eval.worker_threat_raw + final_eval.combat_threat_raw;
    out.final_value_total = final_eval.total_score + root_c1_bonus;
    out.v3_total_score = combined.total_score + lightning_bonus_score - weighted_reactive_penalty + root_c1_bonus;
    return out;
}

double root_c1_bonus_for(const rs::DefenseSimulator &defense_root, int player, const ls::CombinedPlan &plan) {
    const bool c1_transition_phase = ls::c1_transition_phase_from_action_start(defense_root);
    rs::DefenseSimulator plan_root = defense_root.clone();
    if (!plan.ops.empty()) {
        ls::apply_operations(plan_root, plan.ops);
    }
    return ls::c1_root_bonus_for_plan(plan_root, player, plan.followup, c1_transition_phase);
}

Estimate estimate_random_equal(
    const rs::DefenseSimulator &root,
    int player,
    const ls::CombinedPlan &plan,
    int samples,
    std::uint64_t seed_base,
    double root_c1_bonus) {
    Estimate estimate;
    estimate.samples = samples;
    estimate.weight_sum = static_cast<double>(samples);
    for (int index = 0; index < samples; ++index) {
        const Outcome outcome = simulate_plan_outcome(
            root,
            player,
            plan,
            rs::mix_seed(seed_base, static_cast<std::uint64_t>(index + 1)),
            root_c1_bonus,
            nullptr);
        add_scaled(estimate.mean, outcome, 1.0);
    }
    estimate.mean = scale_outcome(estimate.mean, samples > 0 ? 1.0 / static_cast<double>(samples) : 0.0);
    return estimate;
}

Estimate estimate_forced(
    const rs::DefenseSimulator &root,
    int player,
    const ls::CombinedPlan &plan,
    int samples,
    std::uint64_t seed_base,
    double root_c1_bonus,
    bool probability_weighted) {
    rs::DefenseSimulator plan_root = root.clone();
    if (!plan.ops.empty()) {
        ls::apply_operations(plan_root, plan.ops);
    }
    const ls::RolloutForcedPlan forced_plan =
        ls::build_first_round_rollout_plan(plan_root, player, samples, rs::mix_seed(seed_base, 0x9e3779b97f4a7c15ULL));

    Estimate estimate;
    estimate.samples = samples;
    for (int index = 0; index < samples; ++index) {
        const auto *forced_moves =
            index < static_cast<int>(forced_plan.samples.size()) ? &forced_plan.samples[static_cast<std::size_t>(index)].forced_moves : nullptr;
        const double weight =
            probability_weighted && index < static_cast<int>(forced_plan.samples.size())
                ? std::max(forced_plan.samples[static_cast<std::size_t>(index)].probability, 1e-12)
                : 1.0;
        const Outcome outcome = simulate_plan_outcome(
            root,
            player,
            plan,
            rs::mix_seed(seed_base, static_cast<std::uint64_t>(index + 1)),
            root_c1_bonus,
            forced_moves);
        add_scaled(estimate.mean, outcome, weight);
        estimate.weight_sum += weight;
    }
    estimate.mean = scale_outcome(estimate.mean, estimate.weight_sum > 0.0 ? 1.0 / estimate.weight_sum : 0.0);
    return estimate;
}

json plan_to_json(const PublicState &state, int player, const ls::CombinedPlan &plan) {
    return json{
        {"key", plan.key},
        {"name", plan.name},
        {"base_name", plan.base_name},
        {"lure_name", plan.lure_name},
        {"lightning_name", plan.lightning_name},
        {"has_lightning", plan.has_lightning},
        {"horizon", plan.horizon},
        {"heuristic", plan.heuristic},
        {"ops", ls::ops_text(plan.ops)},
        {"pretty", ls::pretty_ops_text(state, player, plan.ops)},
        {"followup", ls::followup_text(plan.followup)},
    };
}

json run_case(const CaseSpec &spec, int estimate_samples, int truth_samples, int case_index) {
    json replay;
    {
        std::ifstream fin(spec.replay_path);
        if (!fin) {
            throw std::runtime_error("failed to open replay: " + spec.replay_path);
        }
        fin >> replay;
    }

    const ReplaySnapshot snapshot = replay_to_round(replay, spec.round);
    PublicState state = snapshot.state.clone();
    rs::DefenseSimulator defense_root = rs::make_defense_simulator(state, &snapshot.simulator, spec.player);
    defense_root.ignore_enemy_spawns = true;
    const ls::RootPlanSet root_plans = ls::generate_root_plans(state, &defense_root, spec.player);
    ls::UcbEvaluationTrace trace;
    const std::uint64_t serial = static_cast<std::uint64_t>(1000003 + case_index * 7919);
    const std::vector<ls::EvaluatedPlan> evaluated =
        ls::evaluate_root_plans(state, defense_root, spec.player, serial, estimate_samples, root_plans, &trace);
    if (evaluated.empty()) {
        throw std::runtime_error("no evaluated plans for case: " + spec.replay_path);
    }
    const ls::CombinedPlan plan = evaluated.front().plan;
    const double root_c1_bonus = root_c1_bonus_for(defense_root, spec.player, plan);
    const std::uint64_t seed_base =
        rs::mix_seed(state.seed, static_cast<std::uint64_t>(0xD1B54A32D192ED03ULL + case_index * 10000019ULL + spec.round));

    const Estimate truth = estimate_random_equal(
        defense_root,
        spec.player,
        plan,
        truth_samples,
        rs::mix_seed(seed_base, 0x1000ULL),
        root_c1_bonus);
    const Estimate current_forced_weighted = estimate_forced(
        defense_root,
        spec.player,
        plan,
        estimate_samples,
        rs::mix_seed(seed_base, 0x2000ULL),
        root_c1_bonus,
        true);
    const Estimate random_equal = estimate_random_equal(
        defense_root,
        spec.player,
        plan,
        estimate_samples,
        rs::mix_seed(seed_base, 0x3000ULL),
        root_c1_bonus);
    const Estimate forced_equal = estimate_forced(
        defense_root,
        spec.player,
        plan,
        estimate_samples,
        rs::mix_seed(seed_base, 0x4000ULL),
        root_c1_bonus,
        false);

    json out;
    out["replay_path"] = spec.replay_path;
    out["round"] = spec.round;
    out["player"] = spec.player;
    out["seed"] = state.seed;
    out["plans_total"] = root_plans.plans.size();
    out["base_candidates"] = root_plans.base_count;
    out["lure_candidates"] = root_plans.lure_count;
    out["lightning_candidates"] = root_plans.lightning_count;
    out["selected_plan"] = plan_to_json(state, spec.player, plan);
    out["root_c1_bonus"] = root_c1_bonus;
    out["truth_random_equal_5000"] = outcome_to_json(truth.mean);
    out["current_forced_weighted_50"] = estimate_to_json(current_forced_weighted, truth.mean);
    out["random_equal_50"] = estimate_to_json(random_equal, truth.mean);
    out["forced_equal_50"] = estimate_to_json(forced_equal, truth.mean);
    return out;
}

void accumulate_method_errors(json &summary, const json &case_result, const std::string &method) {
    static const std::vector<std::string> metrics = {
        "final_base_hp",
        "final_money",
        "final_threat",
        "final_value_total",
        "v3_total_score",
    };
    for (const std::string &metric : metrics) {
        if (!summary.contains(method) || !summary[method].is_object()) {
            summary[method] = json::object();
        }
        if (!summary[method].contains(metric) || !summary[method][metric].is_object()) {
            summary[method][metric] = json::object();
        }
        summary[method][metric]["sum_abs_error"] =
            summary[method][metric].value("sum_abs_error", 0.0) +
            case_result.at(method).at("abs_error").at(metric).get<double>();
    }
}

void finalize_summary(json &summary, int case_count) {
    static const std::vector<std::string> methods = {
        "current_forced_weighted_50",
        "random_equal_50",
        "forced_equal_50",
    };
    static const std::vector<std::string> metrics = {
        "final_base_hp",
        "final_money",
        "final_threat",
        "final_value_total",
        "v3_total_score",
    };
    for (const std::string &method : methods) {
        for (const std::string &metric : metrics) {
            const double sum = summary[method][metric].value("sum_abs_error", 0.0);
            summary[method][metric]["mean_abs_error"] =
                case_count > 0 ? sum / static_cast<double>(case_count) : 0.0;
        }
    }
}

} // namespace

int main(int argc, char **argv) {
    if (argc < 5) {
        std::cerr << "usage: sdk_rollout_accuracy <output.json> <estimate_samples> <truth_samples> "
                     "<replay.json:round:player>...\n";
        return 1;
    }

    const std::string output_path = argv[1];
    const int estimate_samples = std::stoi(argv[2]);
    const int truth_samples = std::stoi(argv[3]);
    std::vector<CaseSpec> cases;
    for (int index = 4; index < argc; ++index) {
        cases.push_back(parse_case_spec(argv[index]));
    }

    json report;
    report["config"] = {
        {"estimate_samples", estimate_samples},
        {"truth_samples", truth_samples},
        {"case_count", cases.size()},
        {"rollout_forced_ant_limit", antgame::sdk::v3_lure_config().rollout_forced_ant_limit},
        {"mid_eval_weight", antgame::sdk::v3_lure_config().mid_eval_weight},
    };
    report["cases"] = json::array();
    report["summary"] = json::object();

    for (std::size_t index = 0; index < cases.size(); ++index) {
        std::cerr << "case " << (index + 1) << "/" << cases.size()
                  << " round=" << cases[index].round
                  << " player=" << cases[index].player
                  << " replay=" << cases[index].replay_path << '\n';
        json case_result = run_case(cases[index], estimate_samples, truth_samples, static_cast<int>(index));
        accumulate_method_errors(report["summary"], case_result, "current_forced_weighted_50");
        accumulate_method_errors(report["summary"], case_result, "random_equal_50");
        accumulate_method_errors(report["summary"], case_result, "forced_equal_50");
        report["cases"].push_back(std::move(case_result));
    }
    finalize_summary(report["summary"], static_cast<int>(cases.size()));

    std::ofstream fout(output_path);
    if (!fout) {
        throw std::runtime_error("failed to open output path");
    }
    fout << std::setw(2) << report << '\n';
    std::cout << output_path << '\n';
    return 0;
}
