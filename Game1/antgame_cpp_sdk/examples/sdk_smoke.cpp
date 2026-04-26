#include <iostream>
#include <vector>

#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/random_search_baseline.hpp"

using antgame::sdk::NativeSimulator;
using antgame::sdk::Operation;
using antgame::sdk::OperationType;
using antgame::sdk::PublicState;
namespace rs = antgame::sdk::random_search_detail;

int main() {
    PublicState public_state(7);
    const Operation build(OperationType::BuildTower, 8, 7);
    if (!public_state.can_apply_operation(0, build)) {
        std::cerr << "public_state rejected valid build\n";
        return 1;
    }
    public_state.apply_operation_list(0, {build});
    if (public_state.tower_count(0) != 1 || public_state.coins[0] != 35) {
        std::cerr << "public_state build accounting mismatch\n";
        return 1;
    }

    NativeSimulator simulator(7);
    const auto result = simulator.resolve_turn({build}, {});
    if (result.terminal) {
        std::cerr << "native simulator terminated unexpectedly\n";
        return 1;
    }

    const auto round_state = simulator.to_public_round_state();
    if (round_state.towers.empty()) {
        std::cerr << "native simulator did not create tower\n";
        return 1;
    }

    PublicState synced(7);
    synced.sync_public_round_state(round_state);
    if (synced.tower_count(0) == 0) {
        std::cerr << "sync_public_round_state lost tower state\n";
        return 1;
    }

    rs::DefenseSimulator defense;
    defense.player = 0;
    defense.enemy = 1;
    defense.base_hp = 50;
    rs::SearchAnt ant;
    ant.ant_id = 1;
    ant.x = 0;
    ant.y = 8;
    ant.hp = 20;
    ant.level = 0;
    ant.behavior = antgame::sdk::AntBehavior::Default;
    ant.kind = antgame::sdk::AntKind::Worker;
    defense.ants.push_back(ant);
    const auto options = defense.legal_move_candidates(defense.ants[0]);
    for (int index = 0; index < options.size(); ++index) {
        if (options[index].nx == 0 && options[index].ny == 9) {
            std::cerr << "defense simulator allowed walking onto forbidden highland\n";
            return 1;
        }
    }

    std::cout << "cpp_sdk smoke ok\n";
    return 0;
}
