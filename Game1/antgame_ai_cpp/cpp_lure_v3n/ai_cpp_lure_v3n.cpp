#include <chrono>
#include <cstdint>
#include <iostream>
#include <vector>

#include "antgame_ai/lure_strategy_v3_evaluation.hpp"
#include "antgame_ai/lure_strategy_v3_root_plans.hpp"
#include "antgame_ai/lure_strategy_v3_session.hpp"
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/sdk.hpp"

using antgame::sdk::LureStrategySession;
using antgame::sdk::NativeSimulator;
using antgame::sdk::Operation;
using antgame::sdk::ProtocolIO;
using antgame::sdk::PublicRoundState;
using antgame::sdk::PublicState;

namespace {

namespace ls = antgame::sdk::lure_strategy_detail;
namespace rs = antgame::sdk::random_search_detail;

struct AiRuntime {
    int player = 0;
    int opponent = 1;
    PublicState public_state;
    NativeSimulator simulator;
    LureStrategySession session;
    bool opponent_ops_already_applied = false;

    explicit AiRuntime(int player_in, unsigned long long seed_in)
        : player(player_in),
          opponent(1 - player_in),
          public_state(seed_in),
          simulator(seed_in) {}
};

struct PerfSample {
    int plan_count = 0;
    int simulations = 0;
    long long elapsed_ns = 0;
};

bool is_active_lure_plan(const ls::CombinedPlan &plan) {
    return !plan.has_lightning && !plan.lure_name.empty() && plan.lure_name != "none" &&
           plan.lure_name != "lure_hold";
}

ls::RootPlanSet filtered_plans(const ls::RootPlanSet &root_plans, bool lightning) {
    ls::RootPlanSet out;
    for (const auto &plan : root_plans.plans) {
        if (lightning ? plan.has_lightning : is_active_lure_plan(plan)) {
            out.plans.push_back(plan);
        }
    }
    return out;
}

PerfSample measure_plan_group(
    const PublicState &state,
    const rs::DefenseSimulator &defense_root,
    int player,
    std::uint64_t serial,
    const ls::RootPlanSet &plans) {
    PerfSample sample;
    sample.plan_count = static_cast<int>(plans.plans.size());
    if (plans.plans.empty()) {
        return sample;
    }

    ls::UcbEvaluationTrace trace;
    const auto begin = std::chrono::steady_clock::now();
    volatile std::size_t evaluated_count = ls::evaluate_root_plans(
                                               state,
                                               defense_root,
                                               player,
                                               serial,
                                               antgame::sdk::v3_lure_config().rollout_count,
                                               plans,
                                               &trace)
                                               .size();
    (void)evaluated_count;
    const auto end = std::chrono::steady_clock::now();

    sample.simulations = trace.total_samples;
    sample.elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end - begin).count();
    return sample;
}

void compute_and_log_probe(AiRuntime &runtime) {
    runtime.session.observe(runtime.public_state, runtime.player);

    PublicState state = runtime.public_state.clone();
    runtime.session.apply_inferred_last_moves(state, runtime.player);

    rs::DefenseSimulator defense_root = rs::make_defense_simulator(state, &runtime.simulator, runtime.player);
    defense_root.ignore_enemy_spawns = true;
    const ls::RootPlanSet root_plans = ls::generate_root_plans(state, &defense_root, runtime.player);

    const ls::RootPlanSet lure_plans = filtered_plans(root_plans, false);
    const ls::RootPlanSet lightning_plans = filtered_plans(root_plans, true);
    const std::uint64_t serial = runtime.session.decision_serial[static_cast<std::size_t>(runtime.player)];

    const PerfSample lure = measure_plan_group(state, defense_root, runtime.player, serial * 2ULL + 1ULL, lure_plans);
    const PerfSample lightning =
        measure_plan_group(state, defense_root, runtime.player, serial * 2ULL + 2ULL, lightning_plans);

    std::cerr << "{\"kind\":\"v3n_perf\""
              << ",\"round\":" << state.round_index
              << ",\"player\":" << runtime.player
              << ",\"serial\":" << serial
              << ",\"lure_plans\":" << lure.plan_count
              << ",\"lure_simulations\":" << lure.simulations
              << ",\"lure_elapsed_ns\":" << lure.elapsed_ns
              << ",\"lightning_plans\":" << lightning.plan_count
              << ",\"lightning_simulations\":" << lightning.simulations
              << ",\"lightning_elapsed_ns\":" << lightning.elapsed_ns
              << "}\n";
}

bool receive_and_apply_opponent(AiRuntime &runtime, ProtocolIO &io) {
    try {
        const auto operations = io.recv_operations();
        runtime.public_state.apply_operation_list(runtime.opponent, operations);
        runtime.simulator.apply_operation_list(runtime.opponent, operations);
        runtime.opponent_ops_already_applied = true;
        return true;
    } catch (const std::exception &exc) {
        io.log(std::string("receive_opponent failed: ") + exc.what());
        return false;
    }
}

bool receive_and_sync_round(AiRuntime &runtime, ProtocolIO &io) {
    try {
        PublicRoundState round_state;
        if (!io.recv_round_state(round_state)) {
            return false;
        }
        runtime.public_state.sync_public_round_state(round_state);
        runtime.simulator.sync_public_round_state(round_state);
        return true;
    } catch (const std::exception &exc) {
        io.log(std::string("sync_round failed: ") + exc.what());
        return false;
    }
}

void perform_self_turn(AiRuntime &runtime, ProtocolIO &io) {
    compute_and_log_probe(runtime);
    io.send_operations(std::vector<Operation>{});
}

void finalize_local_round(AiRuntime &runtime) {
    runtime.simulator.advance_round();
    runtime.opponent_ops_already_applied = false;
}

} // namespace

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    try {
        ProtocolIO io;
        const auto init = io.recv_init();
        AiRuntime runtime(init.player, static_cast<unsigned long long>(init.seed));

        while (true) {
            if (runtime.player == 0) {
                perform_self_turn(runtime, io);
                if (!receive_and_apply_opponent(runtime, io)) {
                    break;
                }
                finalize_local_round(runtime);
                if (!receive_and_sync_round(runtime, io)) {
                    break;
                }
            } else {
                if (!receive_and_apply_opponent(runtime, io)) {
                    break;
                }
                perform_self_turn(runtime, io);
                finalize_local_round(runtime);
                if (!receive_and_sync_round(runtime, io)) {
                    break;
                }
            }
        }
    } catch (const std::exception &exc) {
        std::cerr << "[cpp_sdk] fatal: " << exc.what() << '\n';
        return 1;
    }
    return 0;
}
