#pragma once

#include "antgame_sdk/random_search_baseline.hpp"

namespace antgame::sdk {

using BaselineDecisionContext = RandomSearchDecisionContext;
using BaselineSession = RandomSearchSession;

inline std::vector<Operation> decide_heavy_baseline(
    const BaselineDecisionContext &context,
    BaselineSession *session = nullptr) {
    return decide_random_search_baseline(context, session);
}

inline std::vector<Operation> decide_heavy_baseline(const PublicState &state, int player) {
    return decide_random_search_baseline(state, player);
}

} // namespace antgame::sdk
