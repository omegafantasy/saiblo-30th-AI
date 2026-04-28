#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>
#include <vector>

#include "antgame_ai/lure_strategy_v3_rollout_score.hpp"

namespace antgame::sdk::lure_strategy_detail {

struct EvaluatedPlan {
    std::size_t root_index = 0;
    CombinedPlan plan;
    RolloutEvaluation mean_rollout;
    double mean_rollout_score = -std::numeric_limits<double>::infinity();
    double mean_score = -std::numeric_limits<double>::infinity();
    double rollout_weight_sum = 0.0;
    int rollout_count = 0;
};

struct UcbRolloutRecord {
    std::size_t root_index = 0;
    int global_sample_index = 0;
    int arm_sample_index = 0;
    int batch_index = 0;
    int batch_local_index = 0;
    int batch_size = 0;
    std::uint64_t assignment_serial = 0;
    std::uint64_t assignment_seed = 0;
    std::uint64_t rollout_seed = 0;
    double probability = 1.0;
    RolloutEvaluation evaluation;
    RolloutForcedSample forced_sample;
};

struct UcbBatchRecord {
    std::size_t root_index = 0;
    int batch_index = 0;
    int start_arm_sample_index = 0;
    int requested_count = 0;
    int added_count = 0;
    std::uint64_t assignment_serial = 0;
    std::uint64_t assignment_seed = 0;
    double elapsed_us = 0.0;
};

struct UcbEvaluationTrace {
    std::vector<UcbRolloutRecord> samples;
    std::vector<UcbBatchRecord> batches;
    int target_total = 0;
    int total_samples = 0;
    double total_elapsed_us = 0.0;

    void clear() {
        samples.clear();
        batches.clear();
        target_total = 0;
        total_samples = 0;
        total_elapsed_us = 0.0;
    }
};

inline std::vector<EvaluatedPlan> evaluate_root_plans(
    const PublicState &state,
    const rs::DefenseSimulator &defense_root,
    int player,
    std::uint64_t serial,
    int rollout_count,
    const RootPlanSet &root_plans,
    UcbEvaluationTrace *trace = nullptr) {
    if (trace != nullptr) {
        trace->clear();
    }
    std::vector<EvaluatedPlan> evaluated;
    evaluated.reserve(root_plans.plans.size());

    struct UcbArm {
        std::size_t root_index = 0;
        CombinedPlan plan;
        rs::DefenseSimulator plan_root;
        RolloutEvaluation weighted_total;
        double weight_sum = 0.0;
        double root_c1_bonus = 0.0;
        RolloutForcedPlan forced_plan;
        bool has_prebuilt_forced_plan = false;
        int samples = 0;
        int batches = 0;
        bool valid = true;
    };

    std::vector<UcbArm> arms;
    arms.reserve(root_plans.plans.size());
    for (std::size_t index = 0; index < root_plans.plans.size(); ++index) {
        const auto &plan = root_plans.plans[index];
        UcbArm arm;
        arm.root_index = index;
        arm.plan = plan;
        arm.plan_root = defense_root.clone();
        if (!plan.ops.empty() && !apply_operations(arm.plan_root, plan.ops)) {
            arm.valid = false;
        } else {
            arm.root_c1_bonus = c1_root_bonus_for_plan(arm.plan_root, player, plan.followup);
        }
        arms.push_back(std::move(arm));
    }

    std::vector<std::size_t> normal_arm_indices;
    std::vector<std::size_t> lightning_arm_indices;
    normal_arm_indices.reserve(arms.size());
    lightning_arm_indices.reserve(arms.size());
    for (std::size_t index = 0; index < arms.size(); ++index) {
        if (arms[index].plan.has_lightning) {
            lightning_arm_indices.push_back(index);
        } else {
            normal_arm_indices.push_back(index);
        }
    }

    const int normal_target_average = rollout_count > 0 ? rollout_count : std::max(1, v3_lure_config().rollout_count);
    const int normal_batch_size = std::max(1, v3_lure_config().action_ucb_batch_rollouts);
    const int normal_target_total = normal_arm_indices.empty()
                                        ? 0
                                        : static_cast<int>(
                                              std::ceil(static_cast<double>(normal_arm_indices.size() * normal_target_average) /
                                                        static_cast<double>(normal_batch_size))) *
                                              normal_batch_size;
    const int lightning_batch_size = std::max(1, v3_lure_config().lightning_ucb_batch_rollouts);
    const int lightning_budget = lightning_arm_indices.empty()
                                     ? 0
                                     : std::max(0, v3_lure_config().lightning_ucb_total_rollouts);
    const int lightning_target_total = lightning_budget <= 0
                                           ? 0
                                           : static_cast<int>(
                                                 std::ceil(static_cast<double>(lightning_budget) /
                                                           static_cast<double>(lightning_batch_size))) *
                                                 lightning_batch_size;
    const int target_total = normal_target_total + lightning_target_total;
    if (trace != nullptr) {
        trace->target_total = target_total;
    }

    auto arm_mean_score = [](const UcbArm &arm) {
        return arm.valid && arm.weight_sum > 0.0
                   ? arm.weighted_total.total_score / arm.weight_sum + arm.plan.heuristic
                   : -std::numeric_limits<double>::infinity();
    };

    auto sample_arm_batch = [&](UcbArm &arm, int count) {
        if (!arm.valid || count <= 0) {
            return 0;
        }
        const auto batch_begin = std::chrono::steady_clock::now();
        const int batch_index = arm.batches;
        const int start_sample = arm.samples;
        const std::uint64_t assignment_serial = serial + static_cast<std::uint64_t>(start_sample + 1);
        const std::uint64_t assignment_seed =
            arm.has_prebuilt_forced_plan
                ? plan_rollout_assignment_seed(
                      state.seed,
                      serial,
                      arm.root_index,
                      arm.plan.horizon,
                      std::max(1, v3_lure_config().lightning_ucb_total_rollouts))
                : plan_rollout_assignment_seed(
                      state.seed,
                      assignment_serial,
                      arm.root_index,
                      arm.plan.horizon,
                      count);
        RolloutForcedPlan local_forced_plan;
        const RolloutForcedPlan *forced_plan = nullptr;
        if (arm.has_prebuilt_forced_plan) {
            forced_plan = &arm.forced_plan;
        } else {
            local_forced_plan = build_first_round_rollout_plan(
                arm.plan_root,
                player,
                count,
                assignment_seed);
            forced_plan = &local_forced_plan;
        }

        int added = 0;
        for (int rollout = 0; rollout < count; ++rollout) {
            const int arm_sample_index = start_sample + rollout;
            const double weight =
                arm_sample_index < static_cast<int>(forced_plan->samples.size())
                    ? std::max(forced_plan->samples[static_cast<std::size_t>(arm_sample_index)].probability, 1e-12)
                    : 1.0;
            const auto *forced_moves =
                arm_sample_index < static_cast<int>(forced_plan->samples.size())
                    ? &forced_plan->samples[static_cast<std::size_t>(arm_sample_index)].forced_moves
                    : nullptr;
            const std::uint64_t rollout_seed =
                plan_rollout_seed(state.seed, serial, arm.root_index, arm_sample_index, arm.plan.horizon);
            RolloutEvaluation sample = rollout_plan_score(
                defense_root,
                player,
                arm.plan,
                rollout_seed,
                forced_moves);
            if (!std::isfinite(sample.total_score)) {
                arm.valid = false;
                arm.weighted_total = RolloutEvaluation{};
                arm.weight_sum = 0.0;
                arm.samples = 0;
                return 0;
            }
            sample.terminal.c1_bonus_raw = arm.root_c1_bonus;
            sample.terminal.c1_bonus_score = arm.root_c1_bonus;
            sample.terminal.total_score += arm.root_c1_bonus;
            sample.total_score += arm.root_c1_bonus;
            if (trace != nullptr) {
                UcbRolloutRecord record;
                record.root_index = arm.root_index;
                record.global_sample_index = trace->total_samples + added;
                record.arm_sample_index = arm_sample_index;
                record.batch_index = batch_index;
                record.batch_local_index = rollout;
                record.batch_size = count;
                record.assignment_serial = assignment_serial;
                record.assignment_seed = assignment_seed;
                record.rollout_seed = rollout_seed;
                record.probability = weight;
                record.evaluation = sample;
                if (arm_sample_index < static_cast<int>(forced_plan->samples.size())) {
                    record.forced_sample = forced_plan->samples[static_cast<std::size_t>(arm_sample_index)];
                }
                trace->samples.push_back(std::move(record));
            }
            arm.weighted_total += sample.scaled(weight);
            arm.weight_sum += weight;
            ++added;
        }
        arm.samples += added;
        ++arm.batches;
        const auto batch_end = std::chrono::steady_clock::now();
        const double elapsed_us =
            static_cast<double>(
                std::chrono::duration_cast<std::chrono::microseconds>(batch_end - batch_begin).count());
        if (trace != nullptr) {
            UcbBatchRecord record;
            record.root_index = arm.root_index;
            record.batch_index = batch_index;
            record.start_arm_sample_index = start_sample;
            record.requested_count = count;
            record.added_count = added;
            record.assignment_serial = assignment_serial;
            record.assignment_seed = assignment_seed;
            record.elapsed_us = elapsed_us;
            trace->batches.push_back(record);
            trace->total_samples += added;
            trace->total_elapsed_us += elapsed_us;
        }
        return added;
    };

    auto run_ucb_group = [&](const std::vector<std::size_t> &indices,
                             int batch_size,
                             int group_target_total,
                             double exploration,
                             bool prebuild_forced_plan) {
        if (indices.empty() || batch_size <= 0 || group_target_total <= 0) {
            return 0;
        }
        if (prebuild_forced_plan) {
            const int forced_count = std::max(1, v3_lure_config().lightning_ucb_total_rollouts);
            for (std::size_t arm_index : indices) {
                auto &arm = arms[arm_index];
                if (!arm.valid) {
                    continue;
                }
                const std::uint64_t assignment_seed = plan_rollout_assignment_seed(
                    state.seed,
                    serial,
                    arm.root_index,
                    arm.plan.horizon,
                    forced_count);
                arm.forced_plan = build_first_round_rollout_plan(arm.plan_root, player, forced_count, assignment_seed);
                arm.has_prebuilt_forced_plan = true;
            }
        }

        int group_samples = 0;
        for (std::size_t arm_index : indices) {
            if (group_samples >= group_target_total) {
                break;
            }
            const int count = std::min(batch_size, group_target_total - group_samples);
            group_samples += sample_arm_batch(arms[arm_index], count);
        }
        while (group_samples < group_target_total) {
            int best_index = -1;
            double best_ucb = -std::numeric_limits<double>::infinity();
            for (std::size_t arm_index : indices) {
                const auto &arm = arms[arm_index];
                if (!arm.valid || arm.samples <= 0) {
                    continue;
                }
                const double mean = arm_mean_score(arm);
                const double explore =
                    exploration *
                    std::sqrt(std::log(static_cast<double>(std::max(2, group_samples + 1))) /
                              static_cast<double>(arm.samples));
                const double ucb = mean + explore;
                if (ucb > best_ucb) {
                    best_ucb = ucb;
                    best_index = static_cast<int>(arm_index);
                }
            }
            if (best_index < 0) {
                break;
            }
            const int count = std::min(batch_size, group_target_total - group_samples);
            const int added = sample_arm_batch(arms[static_cast<std::size_t>(best_index)], count);
            if (added <= 0) {
                continue;
            }
            group_samples += added;
        }
        return group_samples;
    };

    run_ucb_group(normal_arm_indices, normal_batch_size, normal_target_total, v3_lure_config().action_ucb_exploration, false);
    run_ucb_group(
        lightning_arm_indices,
        lightning_batch_size,
        lightning_target_total,
        v3_lure_config().lightning_ucb_exploration,
        true);

    for (auto &arm : arms) {
        if (!arm.valid || arm.samples <= 0 || arm.weight_sum <= 0.0) {
            continue;
        }
        EvaluatedPlan item;
        item.root_index = arm.root_index;
        item.plan = arm.plan;
        item.rollout_count = arm.samples;
        item.rollout_weight_sum = arm.weight_sum;
        item.mean_rollout = arm.weighted_total.scaled(1.0 / arm.weight_sum);
        item.mean_rollout_score = item.mean_rollout.total_score;
        item.mean_score = item.mean_rollout_score + item.plan.heuristic;
        evaluated.push_back(item);
    }

    std::sort(evaluated.begin(), evaluated.end(), [](const EvaluatedPlan &lhs, const EvaluatedPlan &rhs) {
        if (lhs.mean_score != rhs.mean_score) {
            return lhs.mean_score > rhs.mean_score;
        }
        return lhs.plan.key < rhs.plan.key;
    });
    return evaluated;
}

} // namespace antgame::sdk::lure_strategy_detail
