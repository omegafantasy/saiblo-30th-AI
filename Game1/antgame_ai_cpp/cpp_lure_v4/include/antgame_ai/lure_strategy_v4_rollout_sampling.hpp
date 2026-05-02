#pragma once

#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>

#include "antgame_ai/lure_strategy_v4_threat.hpp"

namespace antgame::sdk::lure_strategy_detail {

inline std::vector<rs::MoveOption> positive_rollout_move_options_for(
    const rs::DefenseSimulator &simulator,
    const rs::SearchAnt &ant) {
    std::vector<rs::MoveOption> options;
    const auto fixed = simulator.move_options_for(ant);
    options.reserve(static_cast<std::size_t>(fixed.size()));
    for (int index = 0; index < fixed.size(); ++index) {
        if (fixed[index].probability > 1e-12) {
            options.push_back(fixed[index]);
        }
    }
    if (options.empty()) {
        options.push_back(rs::MoveOption{rs::kNoMove, ant.x, ant.y, 1.0, 0.0});
    }
    return options;
}

inline std::vector<int> rollout_option_sequence_indices(
    const std::vector<rs::MoveOption> &options,
    int rollout_count,
    rs::FastRng &rng) {
    std::vector<int> sequence;
    if (rollout_count <= 0 || options.empty()) {
        return sequence;
    }

    const int option_count = static_cast<int>(options.size());
    std::vector<int> counts(static_cast<std::size_t>(option_count), 0);
    std::vector<int> order(static_cast<std::size_t>(option_count), 0);
    std::iota(order.begin(), order.end(), 0);
    for (int index = option_count - 1; index > 0; --index) {
        std::swap(order[static_cast<std::size_t>(index)], order[static_cast<std::size_t>(rng.next_int(index + 1))]);
    }

    if (option_count >= rollout_count) {
        std::stable_sort(order.begin(), order.end(), [&](int lhs, int rhs) {
            if (options[static_cast<std::size_t>(lhs)].probability != options[static_cast<std::size_t>(rhs)].probability) {
                return options[static_cast<std::size_t>(lhs)].probability > options[static_cast<std::size_t>(rhs)].probability;
            }
            return lhs < rhs;
        });
        for (int index = 0; index < rollout_count; ++index) {
            counts[static_cast<std::size_t>(order[static_cast<std::size_t>(index)])] = 1;
        }
    } else {
        for (int index = 0; index < option_count; ++index) {
            counts[static_cast<std::size_t>(index)] = 1;
        }
        int remaining = rollout_count - option_count;
        std::vector<double> fractional(static_cast<std::size_t>(option_count), 0.0);
        for (int index = 0; index < option_count; ++index) {
            const double desired_extra =
                std::max(0.0, options[static_cast<std::size_t>(index)].probability * static_cast<double>(rollout_count) - 1.0);
            const int extra = static_cast<int>(std::floor(desired_extra + 1e-9));
            counts[static_cast<std::size_t>(index)] += extra;
            remaining -= extra;
            fractional[static_cast<std::size_t>(index)] = desired_extra - static_cast<double>(extra);
        }
        std::stable_sort(order.begin(), order.end(), [&](int lhs, int rhs) {
            const double lhs_fractional = fractional[static_cast<std::size_t>(lhs)];
            const double rhs_fractional = fractional[static_cast<std::size_t>(rhs)];
            if (lhs_fractional != rhs_fractional) {
                return lhs_fractional > rhs_fractional;
            }
            if (options[static_cast<std::size_t>(lhs)].probability != options[static_cast<std::size_t>(rhs)].probability) {
                return options[static_cast<std::size_t>(lhs)].probability > options[static_cast<std::size_t>(rhs)].probability;
            }
            return lhs < rhs;
        });
        for (int index = 0; index < remaining; ++index) {
            counts[static_cast<std::size_t>(order[static_cast<std::size_t>(index)])] += 1;
        }
    }

    sequence.reserve(static_cast<std::size_t>(rollout_count));
    for (int index = 0; index < option_count; ++index) {
        for (int count = 0; count < counts[static_cast<std::size_t>(index)]; ++count) {
            sequence.push_back(index);
        }
    }
    if (sequence.empty()) {
        sequence.push_back(0);
    }
    while (static_cast<int>(sequence.size()) < rollout_count) {
        sequence.push_back(order.empty() ? 0 : order.front());
    }
    if (static_cast<int>(sequence.size()) > rollout_count) {
        sequence.resize(static_cast<std::size_t>(rollout_count));
    }
    for (int index = rollout_count - 1; index > 0; --index) {
        std::swap(sequence[static_cast<std::size_t>(index)], sequence[static_cast<std::size_t>(rng.next_int(index + 1))]);
    }
    return sequence;
}

inline RolloutForcedPlan build_first_round_rollout_plan(
    const rs::DefenseSimulator &simulator,
    int player,
    int rollout_count,
    std::uint64_t schedule_seed) {
    RolloutForcedPlan out;
    const int effective_rollouts = std::max(1, rollout_count);
    out.samples.resize(static_cast<std::size_t>(effective_rollouts));
    for (auto &sample : out.samples) {
        sample.probability = 1.0;
    }

    std::vector<const rs::SearchAnt *> ranked;
    ranked.reserve(static_cast<std::size_t>(simulator.ants.size()));
    for (const auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || ant.is_frozen) {
            continue;
        }
        ranked.push_back(&ant);
    }
    std::stable_sort(ranked.begin(), ranked.end(), [&](const rs::SearchAnt *lhs, const rs::SearchAnt *rhs) {
        const double lhs_priority = forced_rollout_ant_priority(simulator, player, *lhs);
        const double rhs_priority = forced_rollout_ant_priority(simulator, player, *rhs);
        if (lhs_priority != rhs_priority) {
            return lhs_priority > rhs_priority;
        }
        return lhs->ant_id < rhs->ant_id;
    });

    const int limit = rs::kMaxImportantAnts;
    if (static_cast<int>(ranked.size()) > limit) {
        ranked.resize(static_cast<std::size_t>(limit));
    }
    out.selected_ant_count = static_cast<int>(ranked.size());

    rs::FastRng rng(schedule_seed);
    for (const rs::SearchAnt *ant : ranked) {
        const auto options = positive_rollout_move_options_for(simulator, *ant);
        const auto sequence = rollout_option_sequence_indices(options, effective_rollouts, rng);
        for (int rollout = 0; rollout < effective_rollouts; ++rollout) {
            const int option_index = sequence[static_cast<std::size_t>(rollout)];
            const auto &option = options[static_cast<std::size_t>(option_index)];
            if (option.direction != rs::kNoMove) {
                out.samples[static_cast<std::size_t>(rollout)].forced_moves.push_back(
                    rs::ForcedMove{ant->ant_id, option.direction});
            }
            out.samples[static_cast<std::size_t>(rollout)].probability *= std::max(option.probability, 1e-12);
        }
    }
    return out;
}

} // namespace antgame::sdk::lure_strategy_detail
