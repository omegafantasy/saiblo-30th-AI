#pragma once

namespace antgame::sdk {

struct V4LureStrategyTuning {
    int rollout_count = 50;
    int action_ucb_batch_rollouts = 40;
    double action_ucb_exploration = 600.0;
    int action_target_time_ms = 3000;
    double action_target_total_multiplier = 1.25;
    int action_probe_min_samples = 10;
    int action_probe_max_samples = 256;
    int action_probe_samples_per_action = 1;
    int action_timing_guard_ms = 150;
    int action_target_rollouts_per_action = 125;
    int action_max_rollouts_per_batch = 100;
    int action_time_budget_ms = 4000;
    int lightning_ucb_total_rollouts = 600;
    int lightning_ucb_batch_rollouts = 2;
    double lightning_ucb_exploration = 300.0;
    int rollout_forced_ant_limit = 5;
    int mid_eval_horizon = 4;
    int long_eval_horizon = 8;
    double mid_eval_weight = 0.0;
    int lightning_horizon = 10;

    // Lightning centers are legal when hex_distance(board_center, center) <= lightning_center_radius.
    int lightning_center_radius = 5;

    int forced_lure_sell_distance = 1;
    int max_non_lure_towers = 2;
    int c1_quick_transition_coin_threshold = 290;

    // root_score(plan) = mean_rollout_score(plan) + plan_heuristic(plan).
    // plan_heuristic =
    //   base_heuristic + lure_heuristic + lightning_heuristic
    // - operation_penalty - followup_plan_penalty(if the plan depends on future-turn followup).
    double hold_bonus = 80.0;
    double followup_plan_penalty = 20.0;

    double c1_build_bonus = 50.0;
    double c1_heavy_bonus = 60.0;
    double c1_heavy_side_trans_bonus = -300.0;
    double c1_quick_trans_bonus = 100.0;
    double c1_sniper_trans_bonus = 400.0;

    double downgrade_refund_penalty_scale = 0.0;
    double sniper_downgrade_penalty = 400.0;
    double non_lure_adjacent_combat_downgrade_bonus = 0.0;

    // terminal_score =
    //   base_hp * base_hp_weight
    // + stepped_own_equivalent_money_score(full_tower_salvage_coin + coin)
    // + c1_terminal_bonus
    // - worker_threat
    // - combat_threat.
    //
    // full_tower_salvage_coin is the estimated coin value after optimally downgrading all towers
    // to basic and selling basic towers in descending HP order.
    double base_hp_weight = 200.0;
    double tower_value_weight = 10.0;
    double money_weight = 10.0;
    double money_decay_threshold = 400.0;
    double money_weight_above_threshold = 6.0;

    // worker_threat = sum(worker_threat_unit * hp / max_hp / max(1, distance_to_own_base)).
    double worker_threat_unit = 160.0;

    // combat_threat = sum(max(base_threat, core_tower_anchor_threat) * behavior_scale).
    double combat_base_threat_unit = 300.0;
    double combat_anchor_threat_coin_ratio = 0.2;
    int combat_anchor_ring_distance = 1;
    double combat_anchor_ring1_bonus_ratio = 0.2;

    double randomized_threat_scale = 0.6;
    double bewitched_threat_scale = 0.3;

    bool future_threat_eval_enabled = false;
    int future_threat_horizon = 4;
    double future_threat_blend = 0.5;
    double future_base_damage_scale = 1.0;
    double future_worker_residual_scale = 1.0;
    double future_combat_residual_scale = 1.0;
    bool future_threat_apply_to_mid_eval = false;
    bool future_threat_apply_teleport = false;
    bool future_threat_drift_effects = false;

    bool hold_followup_enabled = false;
    int hold_followup_delay_turn = 2;
    double hold_followup_heuristic_scale = 1.0;

    // lightning_bonus is added to terminal_score:
    //   enemy_super_bonus + enemy_tower_damage_value + combat_threat_reduction * ratio
    // + shield_break_bonus + hp_damage_bonus + kill_bonus.
    double lightning_enemy_super_bonus = 100.0;
    double lightning_no_enemy_super_penalty = -200.0;
    double lightning_combat_threat_ratio = 0.0;
    double lightning_shield_break_bonus = 25.0;
    double lightning_damage_bonus_per_hp = 1.5;
    double lightning_kill_bonus = 0.0;
    double lightning_tower_value_ratio = 0.4;

    bool offensive_evasion_enabled = true;
    int offensive_evasion_min_enemy_lightning_cd = 5;
    int offensive_evasion_min_post_action_coins = 30;
    int offensive_evasion_min_worker_count = 4;

    bool offensive_emp_enabled = true;
    int offensive_emp_combat_to_top_tower_distance = 2;
};

inline constexpr V4LureStrategyTuning kV4LureStrategyTuning{};

inline V4LureStrategyTuning &v4_lure_config_mutable() {
    static V4LureStrategyTuning tuning = kV4LureStrategyTuning;
    return tuning;
}

inline const V4LureStrategyTuning &v4_lure_config() {
    return v4_lure_config_mutable();
}

inline void reset_v4_lure_config() {
    v4_lure_config_mutable() = kV4LureStrategyTuning;
}

} // namespace antgame::sdk
