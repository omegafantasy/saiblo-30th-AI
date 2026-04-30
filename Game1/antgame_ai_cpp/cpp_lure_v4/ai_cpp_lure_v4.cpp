#include <iostream>
#include <vector>

#include "antgame_ai/lure_strategy_v4.hpp"
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/sdk.hpp"

using antgame::sdk::NativeSimulator;
using antgame::sdk::LureStrategyDecisionContext;
using antgame::sdk::LureStrategySession;
using antgame::sdk::Operation;
using antgame::sdk::ProtocolIO;
using antgame::sdk::PublicRoundState;
using antgame::sdk::PublicState;

namespace {

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

std::vector<Operation> compute_turn(AiRuntime &runtime) {
    LureStrategyDecisionContext ctx;
    ctx.state = &runtime.public_state;
    ctx.simulator = &runtime.simulator;
    ctx.player = runtime.player;
    ctx.opponent_ops_already_applied = runtime.opponent_ops_already_applied;
    return antgame::sdk::decide_lure_strategy(ctx, &runtime.session);
}

void perform_self_turn(AiRuntime &runtime, ProtocolIO &io) {
    const auto proposed = compute_turn(runtime);
    std::vector<Operation> accepted;
    for (const auto &operation : proposed) {
        if (runtime.public_state.can_apply_operation(runtime.player, operation, accepted)) {
            accepted.push_back(operation);
        }
    }
    runtime.public_state.apply_operation_list(runtime.player, accepted);
    runtime.simulator.apply_operation_list(runtime.player, accepted);
    io.send_operations(accepted);
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
