#pragma once

namespace antgame::sdk {

struct V2LureStrategyTuning {
    int rollout_count = 50;
    int rollout_forced_ant_limit = 5;
    int mid_eval_horizon = 6;
    int long_eval_horizon = 10;
    double mid_eval_weight = 0.5;
    int lightning_horizon = 10;

    // Lightning uses UCB over legal centers with hex_distance(board_center, center) <= lightning_center_radius.
    // UCB = mean_score + lightning_ucb_exploration * sqrt(log(total_samples + 1) / samples_at_cell).
    int lightning_ucb_total_rollouts = 500;
    double lightning_ucb_exploration = 200.0;
    int lightning_center_radius = 5;

    int forced_lure_sell_distance = 1;
    int max_non_lure_towers = 2;
    int c1_quick_transition_coin_threshold = 210;

    // root_score(plan) = mean_rollout_score(plan) + plan_heuristic(plan).
    // plan_heuristic = base_heuristic + lure_heuristic + lightning_heuristic - operation_penalty.
    double hold_bonus = 60.0;

    double c1_build_bonus = 50.0;
    double c1_heavy_bonus = 60.0;
    double c1_heavy_side_trans_bonus = -300.0;
    double c1_quick_trans_bonus = 100.0;
    double c1_sniper_trans_bonus = 400.0;

    double downgrade_refund_penalty_scale = 0.0;
    double sniper_downgrade_penalty = 200.0;

    // terminal_score =
    //   base_hp * base_hp_weight
    // + full_tower_salvage_coin * tower_value_weight
    // + coin * money_weight
    // + c1_terminal_bonus
    // - worker_threat
    // - combat_threat.
    //
    // full_tower_salvage_coin is the estimated coin value after optimally downgrading all towers
    // to basic and selling basic towers in descending HP order.
    double base_hp_weight = 200.0;
    double tower_value_weight = 10.0;
    double money_weight = 10.0;

    // worker_threat = sum(worker_threat_unit * hp / max_hp / max(1, distance_to_own_base)).
    double worker_threat_unit = 160.0;

    // combat_threat = sum(max(base_threat, core_tower_anchor_threat) * behavior_scale).
    double combat_base_threat_unit = 300.0;
    double combat_anchor_threat_coin_ratio = 0.2;
    int combat_anchor_ring_distance = 1;
    double combat_anchor_ring1_bonus_ratio = 0.2;

    double randomized_threat_scale = 0.6;
    double bewitched_threat_scale = 0.3;

    // lightning_bonus is added to terminal_score:
    //   enemy_super_bonus + enemy_tower_damage_value + combat_threat_reduction * ratio
    // + shield_break_bonus + hp_damage_bonus + kill_bonus.
    double lightning_enemy_super_bonus = 100.0;
    double lightning_no_enemy_super_penalty = -100.0;
    double lightning_combat_threat_ratio = 0.0;
    double lightning_shield_break_bonus = 25.0;
    double lightning_damage_bonus_per_hp = 1.5;
    double lightning_kill_bonus = 0.0;
    double lightning_tower_value_ratio = 0.5;
};

inline constexpr V2LureStrategyTuning kV2LureStrategyTuning{};

inline constexpr const V2LureStrategyTuning &v2_lure_config() {
    return kV2LureStrategyTuning;
}

} // namespace antgame::sdk
