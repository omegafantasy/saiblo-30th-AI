#pragma once

namespace antgame::sdk {

struct LureStrategyTuning {
    int rollout_count = 10;
    int search_horizon = 6;
    int lightning_horizon = 10;
    int lightning_center_limit = 10;
    int lightning_projection_horizon = 2;
    int lightning_projection_samples = 3;
    int lightning_cluster_separation = 2;
    int lightning_min_boundary_distance = 3;
    int forced_lure_sell_distance = 1;
    int c1_quick_transition_coin_threshold = 230;
    double projected_state_decay = 0.72;

    double base_hold_bonus = 50.0;
    double lure_hold_bonus = 60.0;
    double c1_build_bonus = 50.0;
    double c1_heavy_bonus = 60.0;
    double c1_heavy_side_trans_bonus = -300.0;
    double c1_quick_trans_bonus = 100.0;
    double c1_sniper_trans_bonus = 1000.0;

    double base_hp_weight = 200.0;
    double tower_value_weight = 10.0;
    double money_weight = 10.0;

    double worker_threat_unit = 80.0;
    double combat_base_threat_unit = 300.0;
    double combat_anchor_threat_coin_ratio = 0.2;
    double combat_anchor_ring1_bonus_ratio = 0.2;
    double randomized_threat_scale = 0.6;
    double bewitched_threat_scale = 0.3;

    double lightning_enemy_super_bonus = 120.0;
    double lightning_combat_threat_ratio = 0.1;
    double lightning_shield_break_bonus = 30.0;
    double lightning_damage_bonus_per_hp = 2.0;
    double lightning_kill_bonus = 0.0;
    double lightning_tower_value_ratio = 0.5;
};

inline constexpr LureStrategyTuning kLureStrategyTuning{};

inline constexpr const LureStrategyTuning &lure_config() {
    return kLureStrategyTuning;
}

} // namespace antgame::sdk
