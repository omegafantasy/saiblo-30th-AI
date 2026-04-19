#include <algorithm>
#include <iostream>
#include <vector>

#include "antgame_sdk/sdk.hpp"

using antgame::sdk::Operation;
using antgame::sdk::OperationType;
using antgame::sdk::ProtocolIO;
using antgame::sdk::PublicRoundState;
using antgame::sdk::PublicState;
using antgame::sdk::TowerType;

namespace {

std::vector<Operation> decide(const PublicState &state, int player) {
    std::vector<Operation> accepted;

    if (state.bases[player].ant_level < 2) {
        const Operation upgrade_ant(OperationType::UpgradeGeneratedAnt);
        if (state.can_apply_operation(player, upgrade_ant, accepted)) {
            accepted.push_back(upgrade_ant);
        }
    }

    if (accepted.empty() && state.bases[player].generation_level < 2) {
        const Operation upgrade_gen(OperationType::UpgradeGenerationSpeed);
        if (state.can_apply_operation(player, upgrade_gen, accepted)) {
            accepted.push_back(upgrade_gen);
        }
    }

    if (accepted.empty()) {
        for (const auto &[x, y] : state.strategic_slots(player)) {
            const Operation build(OperationType::BuildTower, x, y);
            if (state.can_apply_operation(player, build, accepted)) {
                accepted.push_back(build);
                break;
            }
        }
    }

    if (accepted.empty()) {
        for (const auto *tower : state.towers_of(player)) {
            for (const TowerType target : {TowerType::Heavy, TowerType::Quick, TowerType::Mortar, TowerType::Producer}) {
                const Operation upgrade(OperationType::UpgradeTower, tower->tower_id, static_cast<int>(target));
                if (state.can_apply_operation(player, upgrade, accepted)) {
                    accepted.push_back(upgrade);
                    return accepted;
                }
            }
        }
    }

    return accepted;
}

bool receive_and_apply_opponent(PublicState &state, ProtocolIO &io, int opponent) {
    try {
        const auto operations = io.recv_operations();
        state.apply_operation_list(opponent, operations);
        return true;
    } catch (...) {
        return false;
    }
}

bool receive_and_sync_round(PublicState &state, ProtocolIO &io) {
    try {
        PublicRoundState round_state;
        if (!io.recv_round_state(round_state)) {
            return false;
        }
        state.sync_public_round_state(round_state);
        return true;
    } catch (...) {
        return false;
    }
}

void perform_self_turn(PublicState &state, ProtocolIO &io, int player) {
    const auto proposed = decide(state, player);
    std::vector<Operation> accepted;
    for (const auto &operation : proposed) {
        if (state.can_apply_operation(player, operation, accepted)) {
            accepted.push_back(operation);
        }
    }
    state.apply_operation_list(player, accepted);
    io.send_operations(accepted);
}

} // namespace

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    ProtocolIO io;
    const auto init = io.recv_init();
    const int player = init.player;
    const int opponent = 1 - player;
    PublicState state(static_cast<unsigned long long>(init.seed));

    while (true) {
        if (player == 0) {
            perform_self_turn(state, io, player);
            if (!receive_and_apply_opponent(state, io, opponent)) {
                break;
            }
            if (!receive_and_sync_round(state, io)) {
                break;
            }
        } else {
            if (!receive_and_apply_opponent(state, io, opponent)) {
                break;
            }
            perform_self_turn(state, io, player);
            if (!receive_and_sync_round(state, io)) {
                break;
            }
        }
    }
    return 0;
}
