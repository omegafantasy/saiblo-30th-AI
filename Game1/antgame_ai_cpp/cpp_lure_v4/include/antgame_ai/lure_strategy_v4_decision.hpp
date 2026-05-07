#pragma once

#include "antgame_ai/lure_strategy_v4_offense.hpp"

namespace antgame::sdk {

inline std::vector<Operation> decide_lure_strategy(
    const LureStrategyDecisionContext &context,
    LureStrategySession *session = nullptr) {
    using namespace lure_strategy_detail;

    if (context.state == nullptr) {
        return {};
    }
    if (session != nullptr) {
        session->observe(*context.state, context.player);
    }

    const DebugMode debug = debug_mode();
    const bool emit_summary = debug != DebugMode::None;
    const bool emit_plans = debug == DebugMode::Plans;
    const auto decision_begin = std::chrono::steady_clock::now();

    PublicState state = context.state->clone();
    if (session != nullptr) {
        session->apply_inferred_last_moves(state, context.player);
    }
    rs::DefenseSimulator defense_root = rs::make_defense_simulator(state, context.simulator, context.player);
    defense_root.ignore_enemy_spawns = true;
    const RootPlanSet root_plans = generate_root_plans(state, &defense_root, context.player);

    const std::uint64_t serial = session != nullptr ? session->decision_serial[context.player] : 0ULL;
    const std::vector<EvaluatedPlan> evaluated =
        evaluate_root_plans(state, defense_root, context.player, serial, root_plans);

    OffensiveEmpChoice offensive_emp;
    OffensiveEvasionChoice offensive_evasion;
    OffensiveAntUpgradeChoice offensive_ant_upgrade;
    std::vector<Operation> final_ops;
    if (evaluated.empty()) {
        offensive_emp.reason = "no_evaluated_plan";
        offensive_evasion.reason = "no_evaluated_plan";
        offensive_ant_upgrade.reason = "no_evaluated_plan";
    } else {
        final_ops = evaluated.front().plan.ops;
        offensive_evasion = choose_offensive_evasion(state, context.player, final_ops);
        if (offensive_evasion.use) {
            final_ops.push_back(offensive_evasion.operation);
            offensive_emp.reason = "skipped_evasion_used";
            offensive_ant_upgrade.reason = "skipped_evasion_used";
        } else {
            offensive_emp = choose_offensive_emp(state, context.player, final_ops);
            if (offensive_emp.use) {
                final_ops.push_back(offensive_emp.operation);
                offensive_ant_upgrade.reason = "skipped_emp_used";
            } else {
                offensive_ant_upgrade = choose_offensive_ant_upgrade(state, context.player, final_ops);
                if (offensive_ant_upgrade.use) {
                    final_ops.push_back(offensive_ant_upgrade.operation);
                }
            }
        }
    }

    const auto decision_end = std::chrono::steady_clock::now();
    const auto elapsed_us = std::chrono::duration_cast<std::chrono::microseconds>(decision_end - decision_begin).count();

    if (emit_summary) {
        if (emit_plans) {
            for (std::size_t rank = 0; rank < evaluated.size(); ++rank) {
                const auto &item = evaluated[rank];
                std::cerr
                    << "{\"kind\":\"plan\""
                    << ",\"round\":" << state.round_index
                    << ",\"player\":" << context.player
                    << ",\"serial\":" << serial
                    << ",\"rank\":" << (rank + 1)
                    << ",\"key\":\"" << debug_json_escape(item.plan.key) << '"'
                    << ",\"name\":\"" << debug_json_escape(item.plan.name) << '"'
                    << ",\"base_name\":\"" << debug_json_escape(item.plan.base_name) << '"'
                    << ",\"lure_name\":\"" << debug_json_escape(item.plan.lure_name) << '"'
                    << ",\"lightning_name\":\"" << debug_json_escape(item.plan.lightning_name) << '"'
                    << ",\"first\":\"" << debug_json_escape(ops_text(item.plan.ops)) << '"'
                    << ",\"pretty\":\"" << debug_json_escape(pretty_ops_text(state, context.player, item.plan.ops)) << '"'
                    << ",\"second\":\"" << debug_json_escape(followup_text(item.plan.followup)) << '"'
                    << ",\"base_heuristic\":" << item.plan.base_heuristic
                    << ",\"lure_heuristic\":" << item.plan.lure_heuristic
                    << ",\"lightning_heuristic\":" << item.plan.lightning_heuristic
                    << ",\"operation_penalty\":" << item.plan.operation_penalty
                    << ",\"followup_penalty\":" << item.plan.followup_penalty
                    << ",\"heuristic\":" << item.plan.heuristic
                    << ",\"score_before_heuristic\":" << item.mean_rollout_score
                    << ",\"score_before_penalty\":" << item.mean_score
                    << ",\"rollouts\":" << item.rollout_count
                    << ",\"mean_base_hp_raw\":" << item.mean_rollout.terminal.base_hp_raw
                    << ",\"mean_base_hp_score\":" << item.mean_rollout.terminal.base_hp_score
                    << ",\"mean_tower_value_raw\":" << item.mean_rollout.terminal.tower_value_raw
                    << ",\"mean_tower_value_score\":" << item.mean_rollout.terminal.tower_value_score
                    << ",\"mean_money_raw\":" << item.mean_rollout.terminal.money_raw
                    << ",\"mean_money_score\":" << item.mean_rollout.terminal.money_score
                    << ",\"mean_c1_bonus_raw\":" << item.mean_rollout.terminal.c1_bonus_raw
                    << ",\"mean_c1_bonus_score\":" << item.mean_rollout.terminal.c1_bonus_score
                    << ",\"mean_worker_threat_raw\":" << item.mean_rollout.terminal.worker_threat_raw
                    << ",\"mean_worker_threat_score\":" << item.mean_rollout.terminal.worker_threat_score
                    << ",\"mean_combat_threat_raw\":" << item.mean_rollout.terminal.combat_threat_raw
                    << ",\"mean_combat_threat_score\":" << item.mean_rollout.terminal.combat_threat_score
                    << ",\"mean_future_base_damage_raw\":" << item.mean_rollout.terminal.future_base_damage_raw
                    << ",\"mean_future_base_damage_score\":" << item.mean_rollout.terminal.future_base_damage_score
                    << ",\"mean_future_worker_threat_raw\":" << item.mean_rollout.terminal.future_worker_threat_raw
                    << ",\"mean_future_combat_threat_raw\":" << item.mean_rollout.terminal.future_combat_threat_raw
                    << ",\"mean_future_projected_threat_raw\":" << item.mean_rollout.terminal.future_projected_threat_raw
                    << ",\"mean_future_adjusted_threat_raw\":" << item.mean_rollout.terminal.future_adjusted_threat_raw
                    << ",\"mean_future_threat_adjustment_score\":"
                    << item.mean_rollout.terminal.future_threat_adjustment_score
                    << ",\"mean_terminal_score\":" << item.mean_rollout.terminal.total_score
                    << ",\"mean_lightning_bonus_raw\":" << item.mean_rollout.lightning_bonus_raw
                    << ",\"mean_lightning_bonus_score\":" << item.mean_rollout.lightning_bonus_score
                    << ",\"mean_reactive_operation_penalty\":" << item.mean_rollout.reactive_operation_penalty
                    << ",\"score\":" << item.mean_score
                    << "}\n";
            }
        }

        int total_rollouts = 0;
        for (const auto &item : evaluated) {
            total_rollouts += item.rollout_count;
        }
        std::cerr
            << "{\"kind\":\"decision\""
            << ",\"round\":" << state.round_index
            << ",\"player\":" << context.player
            << ",\"serial\":" << serial
            << ",\"plans_total\":" << root_plans.plans.size()
            << ",\"plans_unique\":" << root_plans.plans.size()
            << ",\"total_rollouts\":" << total_rollouts
            << ",\"action_count\":" << final_ops.size()
            << ",\"v4_emp_used\":" << (offensive_emp.use ? "true" : "false")
            << ",\"v4_evasion_used\":" << (offensive_evasion.use ? "true" : "false")
            << ",\"v4_ant_upgrade_used\":" << (offensive_ant_upgrade.use ? "true" : "false")
            << ",\"elapsed_us\":" << elapsed_us
            << "}\n";
    }

    if (evaluated.empty()) {
        return {};
    }
    return final_ops;
}

inline std::vector<Operation> decide_lure_strategy(const PublicState &state, int player) {
    LureStrategyDecisionContext context;
    context.state = &state;
    context.player = player;
    return decide_lure_strategy(context, nullptr);
}

} // namespace antgame::sdk
