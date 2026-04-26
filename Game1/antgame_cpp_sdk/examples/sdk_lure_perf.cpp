#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <sstream>
#include <string>
#include <vector>

#include "json.hpp"

#include "antgame_sdk/lure_strategy.hpp"
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/random_search_baseline.hpp"
#include "antgame_sdk/sdk.hpp"

using json = nlohmann::json;

using antgame::sdk::LureStrategyDecisionContext;
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
    int round = 0;
};

struct TimeSeries {
    std::vector<double> values;

    void push(double value) { values.push_back(value); }

    double avg() const {
        if (values.empty()) {
            return 0.0;
        }
        return std::accumulate(values.begin(), values.end(), 0.0) / static_cast<double>(values.size());
    }

    double max() const {
        if (values.empty()) {
            return 0.0;
        }
        double best = values.front();
        for (double value : values) {
            if (value > best) {
                best = value;
            }
        }
        return best;
    }
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
    return ReplaySnapshot{state, simulator.clone(), target_round};
}

std::vector<int> build_rounds(int start, int stop, int step) {
    if (step <= 0) {
        throw std::runtime_error("round step must be positive");
    }
    std::vector<int> rounds;
    for (int round = start; round <= stop; round += step) {
        rounds.push_back(round);
    }
    return rounds;
}

template <typename Fn>
double average_time_us(int iterations, Fn &&fn) {
    double total_us = 0.0;
    for (int iter = 0; iter < iterations; ++iter) {
        const auto begin = std::chrono::steady_clock::now();
        fn(iter);
        const auto end = std::chrono::steady_clock::now();
        total_us += static_cast<double>(
            std::chrono::duration_cast<std::chrono::microseconds>(end - begin).count());
    }
    return iterations > 0 ? total_us / static_cast<double>(iterations) : 0.0;
}

void print_profile(const char *label, const rs::DefenseSimulatorProfile &profile) {
    const double rounds = profile.rounds > 0 ? static_cast<double>(profile.rounds) : 1.0;
    const double total_ns = static_cast<double>(
        profile.tower_attack_ns + profile.move_ns + profile.teleport_ns + profile.pheromone_ns +
        profile.manage_ns + profile.spawn_ns + profile.age_ns + profile.income_ns + profile.effects_ns);
    auto pct = [&](std::uint64_t value) {
        return total_ns > 0.0 ? (100.0 * static_cast<double>(value) / total_ns) : 0.0;
    };
    std::cout << label
              << " rounds=" << profile.rounds
              << " round_us=" << (total_ns / rounds / 1000.0)
              << " tower_us=" << (static_cast<double>(profile.tower_attack_ns) / rounds / 1000.0)
              << " move_us=" << (static_cast<double>(profile.move_ns) / rounds / 1000.0)
              << " teleport_us=" << (static_cast<double>(profile.teleport_ns) / rounds / 1000.0)
              << " pheromone_us=" << (static_cast<double>(profile.pheromone_ns) / rounds / 1000.0)
              << " pheromone_trail_us=" << (static_cast<double>(profile.pheromone_trail_ns) / rounds / 1000.0)
              << " manage_us=" << (static_cast<double>(profile.manage_ns) / rounds / 1000.0)
              << " spawn_us=" << (static_cast<double>(profile.spawn_ns) / rounds / 1000.0)
              << " effects_us=" << (static_cast<double>(profile.effects_ns) / rounds / 1000.0)
              << " move_cache_us=" << (static_cast<double>(profile.move_cache_ns) / rounds / 1000.0)
              << " move_sample_us=" << (static_cast<double>(profile.move_sample_ns) / rounds / 1000.0)
              << " move_random_us=" << (static_cast<double>(profile.move_random_ns) / rounds / 1000.0)
              << " move_resolve_us=" << (static_cast<double>(profile.move_resolve_ns) / rounds / 1000.0)
              << " move_sample_calls_per_round="
              << (static_cast<double>(profile.move_sample_calls) / rounds)
              << " move_random_calls_per_round="
              << (static_cast<double>(profile.move_random_calls) / rounds)
              << " move_resolve_calls_per_round="
              << (static_cast<double>(profile.move_resolve_calls) / rounds)
              << " move_pct=" << pct(profile.move_ns)
              << " tower_pct=" << pct(profile.tower_attack_ns)
              << " teleport_pct=" << pct(profile.teleport_ns)
              << " pheromone_pct=" << pct(profile.pheromone_ns)
              << " manage_pct=" << pct(profile.manage_ns)
              << " effects_pct=" << pct(profile.effects_ns)
              << '\n';
}

ls::RootPlanSet filtered_root_plans(const ls::RootPlanSet &input, bool want_lightning) {
    ls::RootPlanSet out;
    out.plans.reserve(input.plans.size());
    for (const auto &plan : input.plans) {
        if (plan.has_lightning == want_lightning) {
            out.plans.push_back(plan);
        }
    }
    out.raw_plan_count = static_cast<int>(out.plans.size());
    out.raw_combo_count = out.raw_plan_count;
    out.lightning_count = want_lightning ? out.raw_plan_count : 0;
    return out;
}

} // namespace

int main(int argc, char **argv) {
    if (argc < 6) {
        std::cerr << "usage: sdk_lure_perf <replay.json> <player> <round_from> <round_to> <round_step> "
                     "[bench_iterations=2] [rollout_repeats=64] [noop_repeats=256]\n";
        return 1;
    }

    const std::string replay_path = argv[1];
    const int player = std::stoi(argv[2]);
    const int round_from = std::stoi(argv[3]);
    const int round_to = std::stoi(argv[4]);
    const int round_step = std::stoi(argv[5]);
    const int bench_iterations = argc > 6 ? std::stoi(argv[6]) : 2;
    const int rollout_repeats = argc > 7 ? std::stoi(argv[7]) : 64;
    const int noop_repeats = argc > 8 ? std::stoi(argv[8]) : 256;

    json replay;
    {
        std::ifstream fin(replay_path);
        if (!fin) {
            throw std::runtime_error("failed to open replay");
        }
        fin >> replay;
    }

    const auto rounds = build_rounds(round_from, round_to, round_step);
    TimeSeries decision_us;
    TimeSeries generate_us;
    TimeSeries evaluate_us;
    TimeSeries normal_eval_us;
    TimeSeries lightning_eval_us;
    TimeSeries rollout_us;
    TimeSeries noop_us;
    TimeSeries native_us;

    rs::DefenseSimulatorProfile rollout_profile_sum;
    rs::DefenseSimulatorProfile noop_profile_sum;

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "config horizon=" << antgame::sdk::lure_config().search_horizon
              << " rollouts=" << antgame::sdk::lure_config().rollout_count
              << " rounds=" << rounds.size() << '\n';

    for (int round : rounds) {
        const ReplaySnapshot snapshot = replay_to_round(replay, round);
        const PublicState base_state = snapshot.state.clone();
        const NativeSimulator native_root = snapshot.simulator.clone();

        double decision_time = average_time_us(bench_iterations, [&](int) {
            PublicState state = base_state.clone();
            NativeSimulator native = native_root.clone();
            LureStrategyDecisionContext ctx;
            ctx.state = &state;
            ctx.simulator = &native;
            ctx.player = player;
            const auto ops = antgame::sdk::decide_lure_strategy(ctx, nullptr);
            static_cast<void>(ops);
        });

        PublicState state = base_state.clone();
        rs::DefenseSimulator defense_root = rs::make_defense_simulator(state, &native_root, player);
        defense_root.ignore_enemy_spawns = true;

        ls::RootPlanSet root_plans;
        double generate_time = average_time_us(bench_iterations, [&](int) {
            PublicState local_state = base_state.clone();
            rs::DefenseSimulator local_root = rs::make_defense_simulator(local_state, &native_root, player);
            local_root.ignore_enemy_spawns = true;
            root_plans = ls::generate_root_plans(local_state, &local_root, player);
        });

        std::vector<ls::EvaluatedPlan> evaluated;
        double evaluate_time = average_time_us(bench_iterations, [&](int iter) {
            PublicState local_state = base_state.clone();
            rs::DefenseSimulator local_root = rs::make_defense_simulator(local_state, &native_root, player);
            local_root.ignore_enemy_spawns = true;
            const ls::RootPlanSet local_plans = ls::generate_root_plans(local_state, &local_root, player);
            auto local_eval = ls::evaluate_root_plans(
                local_state,
                local_root,
                player,
                static_cast<std::uint64_t>(iter),
                antgame::sdk::lure_config().rollout_count,
                local_plans);
            if (iter == 0) {
                root_plans = local_plans;
                evaluated = std::move(local_eval);
            }
        });

        if (evaluated.empty()) {
            std::cout << "round=" << round << " no_evaluated_plan\n";
            continue;
        }

        const ls::RootPlanSet normal_plans = filtered_root_plans(root_plans, false);
        const ls::RootPlanSet lightning_plans = filtered_root_plans(root_plans, true);

        double normal_evaluate_time = average_time_us(bench_iterations, [&](int iter) {
            PublicState local_state = base_state.clone();
            rs::DefenseSimulator local_root = rs::make_defense_simulator(local_state, &native_root, player);
            local_root.ignore_enemy_spawns = true;
            const auto local_eval = ls::evaluate_root_plans(
                local_state,
                local_root,
                player,
                static_cast<std::uint64_t>(iter),
                antgame::sdk::lure_config().rollout_count,
                normal_plans);
            static_cast<void>(local_eval);
        });

        double lightning_evaluate_time = 0.0;
        if (!lightning_plans.plans.empty()) {
            lightning_evaluate_time = average_time_us(bench_iterations, [&](int iter) {
                PublicState local_state = base_state.clone();
                rs::DefenseSimulator local_root = rs::make_defense_simulator(local_state, &native_root, player);
                local_root.ignore_enemy_spawns = true;
                const auto local_eval = ls::evaluate_root_plans(
                    local_state,
                    local_root,
                    player,
                    static_cast<std::uint64_t>(iter),
                    antgame::sdk::lure_config().rollout_count,
                    lightning_plans);
                static_cast<void>(local_eval);
            });
        }

        const ls::CombinedPlan best_plan = evaluated.front().plan;

        rs::DefenseSimulatorProfile rollout_profile;
        double best_rollout_time = average_time_us(rollout_repeats, [&](int iter) {
            rs::DefenseSimulator local_root = defense_root.clone();
            local_root.profile = &rollout_profile;
            const auto sample = ls::rollout_plan_score(
                local_root,
                player,
                best_plan,
                rs::mix_seed(base_state.seed, static_cast<std::uint64_t>(0x1f123bb5U + iter)),
                nullptr);
            static_cast<void>(sample);
        });

        rs::DefenseSimulatorProfile noop_profile;
        double noop_time = average_time_us(noop_repeats, [&](int iter) {
            rs::DefenseSimulator sim = defense_root.clone();
            sim.profile = &noop_profile;
            rs::FastRng rng(rs::mix_seed(base_state.seed, static_cast<std::uint64_t>(0x2f123bb5U + iter)));
            for (int step = 0; step < antgame::sdk::lure_config().search_horizon && !sim.terminal; ++step) {
                sim.simulate_round(rng);
            }
        });

        double native_time = average_time_us(noop_repeats, [&](int iter) {
            NativeSimulator native = native_root.clone();
            native.reseed_future(rs::mix_seed(base_state.seed, static_cast<std::uint64_t>(0x3f123bb5U + iter)));
            for (int step = 0; step < antgame::sdk::lure_config().search_horizon && !native.terminal(); ++step) {
                native.advance_round_without_base_spawns();
            }
        });

        decision_us.push(decision_time);
        generate_us.push(generate_time);
        evaluate_us.push(evaluate_time);
        normal_eval_us.push(normal_evaluate_time);
        lightning_eval_us.push(lightning_evaluate_time);
        rollout_us.push(best_rollout_time);
        noop_us.push(noop_time);
        native_us.push(native_time);

        rollout_profile_sum.rounds += rollout_profile.rounds;
        rollout_profile_sum.tower_attack_ns += rollout_profile.tower_attack_ns;
        rollout_profile_sum.move_ns += rollout_profile.move_ns;
        rollout_profile_sum.move_cache_ns += rollout_profile.move_cache_ns;
        rollout_profile_sum.move_sample_ns += rollout_profile.move_sample_ns;
        rollout_profile_sum.move_random_ns += rollout_profile.move_random_ns;
        rollout_profile_sum.move_resolve_ns += rollout_profile.move_resolve_ns;
        rollout_profile_sum.teleport_ns += rollout_profile.teleport_ns;
        rollout_profile_sum.pheromone_ns += rollout_profile.pheromone_ns;
        rollout_profile_sum.pheromone_trail_ns += rollout_profile.pheromone_trail_ns;
        rollout_profile_sum.manage_ns += rollout_profile.manage_ns;
        rollout_profile_sum.spawn_ns += rollout_profile.spawn_ns;
        rollout_profile_sum.age_ns += rollout_profile.age_ns;
        rollout_profile_sum.income_ns += rollout_profile.income_ns;
        rollout_profile_sum.effects_ns += rollout_profile.effects_ns;
        rollout_profile_sum.move_sample_calls += rollout_profile.move_sample_calls;
        rollout_profile_sum.move_random_calls += rollout_profile.move_random_calls;
        rollout_profile_sum.move_resolve_calls += rollout_profile.move_resolve_calls;
        rollout_profile_sum.move_cache_calls += rollout_profile.move_cache_calls;

        noop_profile_sum.rounds += noop_profile.rounds;
        noop_profile_sum.tower_attack_ns += noop_profile.tower_attack_ns;
        noop_profile_sum.move_ns += noop_profile.move_ns;
        noop_profile_sum.move_cache_ns += noop_profile.move_cache_ns;
        noop_profile_sum.move_sample_ns += noop_profile.move_sample_ns;
        noop_profile_sum.move_random_ns += noop_profile.move_random_ns;
        noop_profile_sum.move_resolve_ns += noop_profile.move_resolve_ns;
        noop_profile_sum.teleport_ns += noop_profile.teleport_ns;
        noop_profile_sum.pheromone_ns += noop_profile.pheromone_ns;
        noop_profile_sum.pheromone_trail_ns += noop_profile.pheromone_trail_ns;
        noop_profile_sum.manage_ns += noop_profile.manage_ns;
        noop_profile_sum.spawn_ns += noop_profile.spawn_ns;
        noop_profile_sum.age_ns += noop_profile.age_ns;
        noop_profile_sum.income_ns += noop_profile.income_ns;
        noop_profile_sum.effects_ns += noop_profile.effects_ns;
        noop_profile_sum.move_sample_calls += noop_profile.move_sample_calls;
        noop_profile_sum.move_random_calls += noop_profile.move_random_calls;
        noop_profile_sum.move_resolve_calls += noop_profile.move_resolve_calls;
        noop_profile_sum.move_cache_calls += noop_profile.move_cache_calls;

        std::cout << "round=" << round
                  << " plans=" << root_plans.plans.size()
                  << " base=" << root_plans.base_count
                  << " lure=" << root_plans.lure_count
                  << " lightning=" << root_plans.lightning_count
                  << " decision_us=" << decision_time
                  << " gen_us=" << generate_time
                  << " eval_us=" << evaluate_time
                  << " normal_eval_us=" << normal_evaluate_time
                  << " lightning_eval_us=" << lightning_evaluate_time
                  << " best_rollout_us=" << best_rollout_time
                  << " noop6_us=" << noop_time
                  << " native6_us=" << native_time
                  << " best=" << best_plan.name
                  << '\n';
    }

    std::cout << "summary"
              << " decision_avg_us=" << decision_us.avg()
              << " decision_max_us=" << decision_us.max()
              << " gen_avg_us=" << generate_us.avg()
              << " eval_avg_us=" << evaluate_us.avg()
              << " normal_eval_avg_us=" << normal_eval_us.avg()
              << " lightning_eval_avg_us=" << lightning_eval_us.avg()
              << " best_rollout_avg_us=" << rollout_us.avg()
              << " noop_avg_us=" << noop_us.avg()
              << " native_avg_us=" << native_us.avg()
              << '\n';
    print_profile("rollout_profile", rollout_profile_sum);
    print_profile("noop_profile", noop_profile_sum);
    return 0;
}
