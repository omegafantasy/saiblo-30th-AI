#pragma once

#include "antgame_sdk/lure_strategy_v2_params.hpp"

namespace antgame::sdk {

using LureStrategyTuning = V2LureStrategyTuning;

inline constexpr const LureStrategyTuning &lure_config() {
    return v2_lure_config();
}

} // namespace antgame::sdk
