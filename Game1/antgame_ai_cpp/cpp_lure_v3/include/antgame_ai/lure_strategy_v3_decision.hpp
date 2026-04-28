#pragma once

#include "antgame_ai/lure_strategy_v3_offense.hpp"

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
        evaluate_root_plans(state, defense_root, context.player, serial, v3_lure_config().rollout_count, root_plans);

    OffensiveEmpChoice offensive_emp;
    OffensiveEvasionChoice offensive_evasion;
    std::vector<Operation> final_ops;
    if (evaluated.empty()) {
        offensive_emp.reason = "no_evaluated_plan";
        offensive_evasion.reason = "no_evaluated_plan";
    } else {
        final_ops = evaluated.front().plan.ops;
        offensive_emp = choose_offensive_emp(state, context.player, final_ops);
        if (offensive_emp.use) {
            final_ops.push_back(offensive_emp.operation);
        }
        offensive_evasion = choose_offensive_evasion(state, context.player, final_ops);
        if (offensive_evasion.use) {
            final_ops.push_back(offensive_evasion.operation);
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
                    << ",\"mean_terminal_score\":" << item.mean_rollout.terminal.total_score
                    << ",\"mean_lightning_bonus_raw\":" << item.mean_rollout.lightning_bonus_raw
                    << ",\"mean_lightning_bonus_score\":" << item.mean_rollout.lightning_bonus_score
                    << ",\"mean_reactive_operation_penalty\":" << item.mean_rollout.reactive_operation_penalty
                    << ",\"score\":" << item.mean_score
                    << "}\n";
            }
        }

        int enemy_ant_count = 0;
        int enemy_combat_ring1 = 0;
        int enemy_combat_ring2 = 0;
        double combat_pressure = 0.0;
        double tower_pressure = 0.0;
        const auto [base_x, base_y] = kPlayerBases[context.player];
        for (const auto &ant : state.ants) {
            if (ant.player == context.player || !ant.is_alive()) {
                continue;
            }
            ++enemy_ant_count;
            if (ant.kind == AntKind::Combat) {
                const int d = hex_distance(ant.x, ant.y, base_x, base_y);
                if (d <= 1) {
                    ++enemy_combat_ring1;
                }
                if (d <= 2) {
                    ++enemy_combat_ring2;
                }
                combat_pressure += 1.0 / std::max(1, d);
            }
        }
        for (const auto &tower : state.towers) {
            if (tower.player != context.player || !is_base_slot_code(code_at(tower, context.player))) {
                continue;
            }
            for (const auto &ant : state.ants) {
                if (ant.player == context.player || ant.kind != AntKind::Combat || !ant.is_alive()) {
                    continue;
                }
                tower_pressure += 1.0 / std::max(1, hex_distance(ant.x, ant.y, tower.x, tower.y));
            }
        }

        const auto &best = evaluated.empty() ? CombinedPlan{} : evaluated.front().plan;
        const auto &best_eval = evaluated.empty() ? EvaluatedPlan{} : evaluated.front();
        std::cerr
            << "{\"kind\":\"decision\""
            << ",\"round\":" << state.round_index
            << ",\"player\":" << context.player
            << ",\"serial\":" << serial
            << ",\"base_candidates\":" << root_plans.base_count
            << ",\"lure_candidates\":" << root_plans.lure_count
            << ",\"lightning_candidates\":" << root_plans.lightning_count
            << ",\"raw_combo_count\":" << root_plans.raw_combo_count
            << ",\"raw_plan_count\":" << root_plans.raw_plan_count
            << ",\"plans_total\":" << root_plans.plans.size()
            << ",\"plans_unique\":" << root_plans.plans.size()
            << ",\"best_key\":\"" << debug_json_escape(best.key.empty() ? "hold" : best.key) << '"'
            << ",\"best_name\":\"" << debug_json_escape(best.name.empty() ? "hold" : best.name) << '"'
            << ",\"best_base_name\":\"" << debug_json_escape(best.base_name.empty() ? "none" : best.base_name) << '"'
            << ",\"best_lure_name\":\"" << debug_json_escape(best.lure_name.empty() ? "none" : best.lure_name) << '"'
            << ",\"best_lightning_name\":\"" << debug_json_escape(best.lightning_name.empty() ? "none" : best.lightning_name) << '"'
            << ",\"best_first\":\"" << debug_json_escape(ops_text(best.ops)) << '"'
            << ",\"best_pretty\":\"" << debug_json_escape(pretty_ops_text(state, context.player, best.ops)) << '"'
            << ",\"best_second\":\"" << debug_json_escape(followup_text(best.followup)) << '"'
            << ",\"final_first\":\"" << debug_json_escape(ops_text(final_ops)) << '"'
            << ",\"final_pretty\":\"" << debug_json_escape(pretty_ops_text(state, context.player, final_ops)) << '"'
            << ",\"v3_emp_used\":" << (offensive_emp.use ? "true" : "false")
            << ",\"v3_emp_reason\":\"" << debug_json_escape(offensive_emp.reason) << '"'
            << ",\"v3_emp_x\":" << offensive_emp.x
            << ",\"v3_emp_y\":" << offensive_emp.y
            << ",\"v3_emp_tower_id\":" << offensive_emp.tower_id
            << ",\"v3_emp_tower_type\":" << offensive_emp.tower_type
            << ",\"v3_emp_combat_ant_id\":" << offensive_emp.combat_ant_id
            << ",\"v3_emp_distance\":" << offensive_emp.distance
            << ",\"v3_emp_post_action_coins\":" << offensive_emp.post_action_coins
            << ",\"v3_evasion_used\":" << (offensive_evasion.use ? "true" : "false")
            << ",\"v3_evasion_reason\":\"" << debug_json_escape(offensive_evasion.reason) << '"'
            << ",\"v3_evasion_x\":" << offensive_evasion.x
            << ",\"v3_evasion_y\":" << offensive_evasion.y
            << ",\"v3_evasion_worker_count\":" << offensive_evasion.worker_count
            << ",\"v3_evasion_combat_count\":" << offensive_evasion.combat_count
            << ",\"v3_evasion_post_action_coins\":" << offensive_evasion.post_action_coins
            << ",\"v3_enemy_lightning_cd\":" << offensive_evasion.enemy_lightning_cooldown
            << ",\"action_legend\":\"" << action_legend_text() << '"'
            << ",\"best_base_heuristic\":" << best.base_heuristic
            << ",\"best_lure_heuristic\":" << best.lure_heuristic
            << ",\"best_lightning_heuristic\":" << best.lightning_heuristic
            << ",\"best_operation_penalty\":" << best.operation_penalty
            << ",\"best_heuristic\":" << best.heuristic
            << ",\"best_score_before_heuristic\":" << best_eval.mean_rollout_score
            << ",\"best_mean_base_hp_raw\":" << best_eval.mean_rollout.terminal.base_hp_raw
            << ",\"best_mean_base_hp_score\":" << best_eval.mean_rollout.terminal.base_hp_score
            << ",\"best_mean_tower_value_raw\":" << best_eval.mean_rollout.terminal.tower_value_raw
            << ",\"best_mean_tower_value_score\":" << best_eval.mean_rollout.terminal.tower_value_score
            << ",\"best_mean_money_raw\":" << best_eval.mean_rollout.terminal.money_raw
            << ",\"best_mean_money_score\":" << best_eval.mean_rollout.terminal.money_score
            << ",\"best_mean_c1_bonus_raw\":" << best_eval.mean_rollout.terminal.c1_bonus_raw
            << ",\"best_mean_c1_bonus_score\":" << best_eval.mean_rollout.terminal.c1_bonus_score
            << ",\"best_mean_worker_threat_raw\":" << best_eval.mean_rollout.terminal.worker_threat_raw
            << ",\"best_mean_worker_threat_score\":" << best_eval.mean_rollout.terminal.worker_threat_score
            << ",\"best_mean_combat_threat_raw\":" << best_eval.mean_rollout.terminal.combat_threat_raw
            << ",\"best_mean_combat_threat_score\":" << best_eval.mean_rollout.terminal.combat_threat_score
            << ",\"best_mean_terminal_score\":" << best_eval.mean_rollout.terminal.total_score
            << ",\"best_mean_lightning_bonus_raw\":" << best_eval.mean_rollout.lightning_bonus_raw
            << ",\"best_mean_lightning_bonus_score\":" << best_eval.mean_rollout.lightning_bonus_score
            << ",\"best_mean_reactive_operation_penalty\":" << best_eval.mean_rollout.reactive_operation_penalty
            << ",\"coins\":" << state.coins[context.player]
            << ",\"base_hp\":" << state.bases[context.player].hp
            << ",\"tower_count\":" << state.tower_count(context.player)
            << ",\"root_enemy_ants\":\"" << debug_json_escape(enemy_ant_state_text(state, context.player)) << '"'
            << ",\"sim_enemy_ants\":\"" << debug_json_escape(sim_enemy_ant_state_text(defense_root)) << '"'
            << ",\"root_own_towers\":\"" << debug_json_escape(own_tower_state_text(state, context.player)) << '"'
            << ",\"enemy_ant_count\":" << enemy_ant_count
            << ",\"enemy_combat_ring1\":" << enemy_combat_ring1
            << ",\"enemy_combat_ring2\":" << enemy_combat_ring2
            << ",\"combat_pressure\":" << combat_pressure
            << ",\"tower_pressure\":" << tower_pressure
            << ",\"best_score\":" << (evaluated.empty() ? 0.0 : evaluated.front().mean_score)
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
