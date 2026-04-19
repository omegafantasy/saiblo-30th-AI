#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <vector>

#include "antgame_sdk/heavy_baseline.hpp"
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/sdk.hpp"

using antgame::sdk::NativeSimulator;
using antgame::sdk::Operation;
using antgame::sdk::BaselineDecisionContext;
using antgame::sdk::PublicState;

namespace {

struct BenchSnapshot {
    PublicState state;
    NativeSimulator simulator;
};

std::vector<BenchSnapshot> collect_states(unsigned long long seed, int max_rounds) {
    NativeSimulator simulator(seed);
    std::vector<BenchSnapshot> states;
    states.reserve(static_cast<std::size_t>(max_rounds));

    for (int round = 0; round < max_rounds && !simulator.terminal(); ++round) {
        PublicState state(seed);
        state.sync_public_round_state(simulator.to_public_round_state());
        states.push_back(BenchSnapshot{state, simulator.clone()});

        PublicState player0_view = state.clone();
        PublicState player1_view = state.clone();
        BaselineDecisionContext ctx0;
        ctx0.state = &player0_view;
        ctx0.simulator = &simulator;
        ctx0.player = 0;
        BaselineDecisionContext ctx1;
        ctx1.state = &player1_view;
        ctx1.simulator = &simulator;
        ctx1.player = 1;
        const auto ops0 = antgame::sdk::decide_heavy_baseline(ctx0);
        const auto ops1 = antgame::sdk::decide_heavy_baseline(ctx1);
        simulator.resolve_turn(ops0, ops1);
    }

    return states;
}

} // namespace

int main() {
    constexpr unsigned long long kSeed = 7ULL;
    constexpr int kCollectionRounds = 48;
    constexpr int kIterations = 24;

    const auto states = collect_states(kSeed, kCollectionRounds);
    if (states.empty()) {
        std::cerr << "no benchmark states collected\n";
        return 1;
    }

    std::vector<std::uint64_t> durations_us;
    durations_us.reserve(states.size() * 2U * static_cast<std::size_t>(kIterations));

    for (int iteration = 0; iteration < kIterations; ++iteration) {
        for (const auto &snapshot : states) {
            for (int player = 0; player < 2; ++player) {
                PublicState state = snapshot.state.clone();
                NativeSimulator sim = snapshot.simulator.clone();
                BaselineDecisionContext ctx;
                ctx.state = &state;
                ctx.simulator = &sim;
                ctx.player = player;
                const auto begin = std::chrono::high_resolution_clock::now();
                const auto operations = antgame::sdk::decide_heavy_baseline(ctx);
                const auto end = std::chrono::high_resolution_clock::now();
                (void)operations;
                durations_us.push_back(static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::microseconds>(end - begin).count()));
            }
        }
    }

    std::sort(durations_us.begin(), durations_us.end());
    const std::uint64_t total_calls = static_cast<std::uint64_t>(durations_us.size());
    std::uint64_t total_us = 0;
    for (const auto value : durations_us) {
        total_us += value;
    }

    const auto p50 = durations_us[durations_us.size() / 2];
    const auto p95 = durations_us[(durations_us.size() * 95) / 100];
    const auto p99 = durations_us[(durations_us.size() * 99) / 100];
    const auto p100 = durations_us.back();
    const double avg_us = static_cast<double>(total_us) / static_cast<double>(total_calls);

    std::cout << "states=" << states.size()
              << " calls=" << total_calls
              << " avg_us=" << avg_us
              << " p50_us=" << p50
              << " p95_us=" << p95
              << " p99_us=" << p99
              << " max_us=" << p100
              << '\n';
    return 0;
}
