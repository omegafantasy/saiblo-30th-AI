#include <cmath>
#include <cstdint>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "../../Ant-Game/game/include/json.hpp"
#include "antgame_ai/lure_strategy_v4.hpp"
#include "antgame_sdk/native_sim.hpp"
#include "antgame_sdk/sdk.hpp"

using json = nlohmann::json;

namespace antgame::sdk::examples {

namespace ls = ::antgame::sdk::lure_strategy_detail;
namespace rs = ::antgame::sdk::random_search_detail;

struct ReplayRoundStart {
    std::uint64_t seed = 0;
    int round = 0;
    json replay_record;
    PublicState public_state;
    NativeSimulator native;

    explicit ReplayRoundStart(std::uint64_t seed_in)
        : seed(seed_in), public_state(seed_in), native(seed_in) {}
};

using EvaluatedPlanWithIndex = ls::EvaluatedPlan;

struct MoveTraceSummary {
    json moves = json::array();
    double log_probability = 0.0;
};

std::pair<std::string, std::string> action_category(const ls::CombinedPlan &plan) {
    if (plan.has_lightning) {
        if (plan.base_name.rfind("combat_adjacent_recycle_", 0) == 0) {
            return {"recycle_lightning", "Recycle + Lightning"};
        }
        return {"lightning", "Lightning"};
    }

    const bool has_base = !plan.base_name.empty() && plan.base_name != "none" && plan.base_name != "base_hold";
    const bool has_lure = !plan.lure_name.empty() && plan.lure_name != "none" && plan.lure_name != "lure_hold";
    const bool is_hold_followup =
        plan.ops.empty() && !plan.followup.empty() && plan.base_name == "base_hold" &&
        plan.lure_name.rfind("hold_then_", 0) == 0;

    if (plan.base_name.rfind("base_double_build_", 0) == 0) {
        return {"double_build", "Double Build"};
    }
    if (!has_base && !has_lure && plan.ops.empty() && plan.followup.empty()) {
        return {"hold", "Hold"};
    }
    if (is_hold_followup) {
        return {"hold_followup", "Hold Followup"};
    }
    if (has_base && has_lure) {
        if (plan.lure_name.rfind("lure_sell_", 0) == 0 || plan.lure_name.rfind("lure_forced_sell_", 0) == 0) {
            return {"lure_sell_base", "Lure Sell + Base"};
        }
        return {"base_lure", "Base + Lure"};
    }
    if (has_base) {
        if (plan.followup.empty()) {
            return {"base", "Base"};
        }
        return {"base_followup", "Base Followup"};
    }
    if (has_lure) {
        return {"lure", "Lure"};
    }
    if (!plan.followup.empty()) {
        return {"followup", "Followup"};
    }
    return {"other", "Other"};
}

json v4_tuning_to_json() {
    const auto &tuning = v4_lure_config();
    return {
        {"strategy_version", "v4"},
        {"action_ucb_exploration", tuning.action_ucb_exploration},
        {"action_target_time_ms", tuning.action_target_time_ms},
        {"action_target_total_multiplier", tuning.action_target_total_multiplier},
        {"action_probe_min_samples", tuning.action_probe_min_samples},
        {"action_target_rollouts_per_action", tuning.action_target_rollouts_per_action},
        {"action_max_rollouts_per_batch", tuning.action_max_rollouts_per_batch},
        {"action_time_budget_ms", tuning.action_time_budget_ms},
        {"rollout_static_risk_cache_enabled", tuning.rollout_static_risk_cache_enabled},
        {"rollout_static_risk_cache_entries", tuning.rollout_static_risk_cache_entries},
        {"rollout_reverse_path_cache_enabled", tuning.rollout_reverse_path_cache_enabled},
        {"rollout_reverse_path_cache_entries", tuning.rollout_reverse_path_cache_entries},
        {"rollout_move_cache_memo_enabled", tuning.rollout_move_cache_memo_enabled},
        {"rollout_move_cache_memo_entries", tuning.rollout_move_cache_memo_entries},
        {"lightning_ucb_total_rollouts", tuning.lightning_ucb_total_rollouts},
        {"lightning_ucb_batch_rollouts", tuning.lightning_ucb_batch_rollouts},
        {"lightning_ucb_exploration", tuning.lightning_ucb_exploration},
        {"mid_eval_horizon", tuning.mid_eval_horizon},
        {"long_eval_horizon", tuning.long_eval_horizon},
        {"mid_eval_weight", tuning.mid_eval_weight},
        {"lightning_horizon", tuning.lightning_horizon},
        {"lightning_center_radius", tuning.lightning_center_radius},
        {"forced_lure_sell_distance", tuning.forced_lure_sell_distance},
        {"max_non_lure_towers", tuning.max_non_lure_towers},
        {"rich_max_non_lure_towers", tuning.rich_max_non_lure_towers},
        {"c1_quick_transition_coin_threshold", tuning.c1_quick_transition_coin_threshold},
        {"hold_bonus", tuning.hold_bonus},
        {"followup_plan_penalty", tuning.followup_plan_penalty},
        {"c1_build_bonus", tuning.c1_build_bonus},
        {"c1_heavy_bonus", tuning.c1_heavy_bonus},
        {"c1_heavy_side_trans_bonus", tuning.c1_heavy_side_trans_bonus},
        {"c1_quick_trans_bonus", tuning.c1_quick_trans_bonus},
        {"c1_sniper_trans_bonus", tuning.c1_sniper_trans_bonus},
        {"sniper_downgrade_penalty", tuning.sniper_downgrade_penalty},
        {"enable_producer_medic_branch", tuning.enable_producer_medic_branch},
        {"producer_medic_equivalent_money_threshold", tuning.producer_medic_equivalent_money_threshold},
        {"producer_upgrade_bonus", tuning.producer_upgrade_bonus},
        {"medic_upgrade_bonus", tuning.medic_upgrade_bonus},
        {"producer_downgrade_penalty", tuning.producer_downgrade_penalty},
        {"medic_downgrade_penalty", tuning.medic_downgrade_penalty},
        {"base_hp_weight", tuning.base_hp_weight},
        {"tower_value_weight", tuning.tower_value_weight},
        {"money_weight", tuning.money_weight},
        {"money_decay_threshold", tuning.money_decay_threshold},
        {"money_weight_above_threshold", tuning.money_weight_above_threshold},
        {"worker_threat_unit", tuning.worker_threat_unit},
        {"combat_base_threat_unit", tuning.combat_base_threat_unit},
        {"combat_anchor_threat_coin_ratio", tuning.combat_anchor_threat_coin_ratio},
        {"combat_anchor_ring_distance", tuning.combat_anchor_ring_distance},
        {"combat_anchor_ring1_bonus_ratio", tuning.combat_anchor_ring1_bonus_ratio},
        {"randomized_threat_scale", tuning.randomized_threat_scale},
        {"bewitched_threat_scale", tuning.bewitched_threat_scale},
        {"future_threat_eval_enabled", tuning.future_threat_eval_enabled},
        {"future_threat_horizon", tuning.future_threat_horizon},
        {"future_threat_blend", tuning.future_threat_blend},
        {"future_base_damage_scale", tuning.future_base_damage_scale},
        {"future_worker_residual_scale", tuning.future_worker_residual_scale},
        {"future_combat_residual_scale", tuning.future_combat_residual_scale},
        {"future_threat_apply_to_mid_eval", tuning.future_threat_apply_to_mid_eval},
        {"future_threat_apply_teleport", tuning.future_threat_apply_teleport},
        {"future_threat_drift_effects", tuning.future_threat_drift_effects},
        {"hold_followup_enabled", tuning.hold_followup_enabled},
        {"hold_followup_delay_turn", tuning.hold_followup_delay_turn},
        {"hold_followup_heuristic_scale", tuning.hold_followup_heuristic_scale},
        {"lightning_enemy_super_bonus", tuning.lightning_enemy_super_bonus},
        {"lightning_no_enemy_super_penalty", tuning.lightning_no_enemy_super_penalty},
        {"lightning_shield_break_bonus", tuning.lightning_shield_break_bonus},
        {"lightning_damage_bonus_per_hp", tuning.lightning_damage_bonus_per_hp},
        {"lightning_tower_value_ratio", tuning.lightning_tower_value_ratio},
        {"offensive_evasion_min_enemy_lightning_cd", tuning.offensive_evasion_min_enemy_lightning_cd},
        {"offensive_evasion_min_post_action_coins", tuning.offensive_evasion_min_post_action_coins},
        {"offensive_evasion_min_worker_count", tuning.offensive_evasion_min_worker_count},
        {"offensive_emp_combat_to_top_tower_distance", tuning.offensive_emp_combat_to_top_tower_distance},
    };
}

bool parse_bool_override(const json &value, bool fallback) {
    if (value.is_boolean()) {
        return value.get<bool>();
    }
    if (value.is_number_integer()) {
        return value.get<int>() != 0;
    }
    if (value.is_string()) {
        const std::string text = value.get<std::string>();
        return text == "1" || text == "true" || text == "on" || text == "yes";
    }
    return fallback;
}

void apply_bool_override(const json &overrides, const char *name, bool &target) {
    if (!overrides.contains(name)) {
        return;
    }
    target = parse_bool_override(overrides.at(name), target);
}

int parse_int_override(const json &value, int fallback) {
    if (value.is_number_integer()) {
        return value.get<int>();
    }
    if (value.is_string()) {
        try {
            return std::stoi(value.get<std::string>());
        } catch (const std::exception &) {
            return fallback;
        }
    }
    return fallback;
}

void apply_int_override(const json &overrides, const char *name, int &target) {
    if (!overrides.contains(name)) {
        return;
    }
    target = parse_int_override(overrides.at(name), target);
}

void apply_strategy_overrides(const json &request) {
    reset_v4_lure_config();
    if (!request.contains("strategy_overrides") || !request.at("strategy_overrides").is_object()) {
        return;
    }
    auto &tuning = v4_lure_config_mutable();
    const json &overrides = request.at("strategy_overrides");
    apply_bool_override(overrides, "future_threat_eval_enabled", tuning.future_threat_eval_enabled);
    apply_bool_override(overrides, "hold_followup_enabled", tuning.hold_followup_enabled);
    apply_bool_override(overrides, "rollout_static_risk_cache_enabled", tuning.rollout_static_risk_cache_enabled);
    apply_int_override(overrides, "rollout_static_risk_cache_entries", tuning.rollout_static_risk_cache_entries);
    apply_bool_override(overrides, "rollout_reverse_path_cache_enabled", tuning.rollout_reverse_path_cache_enabled);
    apply_int_override(overrides, "rollout_reverse_path_cache_entries", tuning.rollout_reverse_path_cache_entries);
    apply_bool_override(overrides, "rollout_move_cache_memo_enabled", tuning.rollout_move_cache_memo_enabled);
    apply_int_override(overrides, "rollout_move_cache_memo_entries", tuning.rollout_move_cache_memo_entries);
    apply_int_override(overrides, "action_target_time_ms", tuning.action_target_time_ms);
    apply_int_override(overrides, "action_time_budget_ms", tuning.action_time_budget_ms);
    apply_int_override(overrides, "action_probe_min_samples", tuning.action_probe_min_samples);
    apply_int_override(overrides, "action_target_rollouts_per_action", tuning.action_target_rollouts_per_action);
    apply_int_override(overrides, "action_max_rollouts_per_batch", tuning.action_max_rollouts_per_batch);
    apply_int_override(overrides, "lightning_ucb_total_rollouts", tuning.lightning_ucb_total_rollouts);
    apply_int_override(overrides, "lightning_ucb_batch_rollouts", tuning.lightning_ucb_batch_rollouts);
}

const char *tower_type_name(TowerType type) {
    switch (type) {
    case TowerType::Basic:
        return "Basic";
    case TowerType::Heavy:
        return "Heavy";
    case TowerType::Quick:
        return "Quick";
    case TowerType::Mortar:
        return "Mortar";
    case TowerType::Producer:
        return "Producer";
    case TowerType::HeavyPlus:
        return "HeavyPlus";
    case TowerType::Ice:
        return "Ice";
    case TowerType::Bewitch:
        return "Bewitch";
    case TowerType::QuickPlus:
        return "QuickPlus";
    case TowerType::Double:
        return "Double";
    case TowerType::Sniper:
        return "Sniper";
    case TowerType::MortarPlus:
        return "MortarPlus";
    case TowerType::Pulse:
        return "Pulse";
    case TowerType::Missile:
        return "Missile";
    case TowerType::ProducerFast:
        return "ProducerFast";
    case TowerType::ProducerSiege:
        return "ProducerSiege";
    case TowerType::ProducerMedic:
        return "ProducerMedic";
    default:
        return "Unknown";
    }
}

const char *behavior_name(AntBehavior behavior) {
    switch (behavior) {
    case AntBehavior::Default:
        return "Default";
    case AntBehavior::Conservative:
        return "Conservative";
    case AntBehavior::Random:
        return "Random";
    case AntBehavior::Bewitched:
        return "Bewitched";
    case AntBehavior::ControlFree:
        return "ControlFree";
    default:
        return "Unknown";
    }
}

const char *kind_name(AntKind kind) {
    switch (kind) {
    case AntKind::Worker:
        return "Worker";
    case AntKind::Combat:
        return "Combat";
    default:
        return "Unknown";
    }
}

const char *weapon_name(SuperWeaponType type) {
    switch (type) {
    case SuperWeaponType::LightningStorm:
        return "LightningStorm";
    case SuperWeaponType::EmpBlaster:
        return "EmpBlaster";
    case SuperWeaponType::Deflector:
        return "Deflector";
    case SuperWeaponType::EmergencyEvasion:
        return "EmergencyEvasion";
    default:
        return "Unknown";
    }
}

json operation_to_json(const Operation &operation) {
    json out;
    out["type"] = static_cast<int>(operation.op_type);
    out["arg0"] = operation.arg0;
    out["arg1"] = operation.arg1;
    out["tokens"] = operation.to_protocol_tokens();
    return out;
}

json tower_to_json(const Tower &tower) {
    json out;
    out["id"] = tower.tower_id;
    out["player"] = tower.player;
    out["x"] = tower.x;
    out["y"] = tower.y;
    out["type"] = static_cast<int>(tower.tower_type);
    out["type_name"] = tower_type_name(tower.tower_type);
    out["cooldown"] = tower.cooldown;
    out["hp"] = tower.hp;
    out["max_hp"] = tower.max_hp();
    return out;
}

json ant_to_json(const Ant &ant) {
    json out;
    out["id"] = ant.ant_id;
    out["player"] = ant.player;
    out["x"] = ant.x;
    out["y"] = ant.y;
    out["hp"] = ant.hp;
    out["max_hp"] = ant.max_hp();
    out["level"] = ant.level;
    out["age"] = ant.age;
    out["status"] = static_cast<int>(ant.status);
    out["behavior"] = static_cast<int>(ant.behavior);
    out["behavior_name"] = behavior_name(ant.behavior);
    out["kind"] = static_cast<int>(ant.kind);
    out["kind_name"] = kind_name(ant.kind);
    out["last_move"] = ant.last_move;
    return out;
}

json effect_to_json(const WeaponEffect &effect) {
    json out;
    out["weapon_type"] = static_cast<int>(effect.weapon_type);
    out["weapon_name"] = weapon_name(effect.weapon_type);
    out["player"] = effect.player;
    out["x"] = effect.x;
    out["y"] = effect.y;
    out["remaining_turns"] = effect.remaining_turns;
    return out;
}

json public_round_state_to_json(const PublicRoundState &state) {
    json out;
    out["round_index"] = state.round_index;
    out["coins"] = json::array({state.coins[0], state.coins[1]});
    out["camps_hp"] = json::array({state.camps_hp[0], state.camps_hp[1]});
    out["speed_lv"] = json::array({state.speed_lv[0], state.speed_lv[1]});
    out["anthp_lv"] = json::array({state.anthp_lv[0], state.anthp_lv[1]});
    out["weapon_cooldowns"] = json::array();
    for (int player = 0; player < 2; ++player) {
        out["weapon_cooldowns"].push_back(json::array(
            {state.weapon_cooldowns[player][0], state.weapon_cooldowns[player][1], state.weapon_cooldowns[player][2],
             state.weapon_cooldowns[player][3], state.weapon_cooldowns[player][4]}));
    }
    out["towers"] = json::array();
    for (const auto &tower : state.towers) {
        out["towers"].push_back(tower_to_json(tower));
    }
    out["ants"] = json::array();
    for (const auto &ant : state.ants) {
        out["ants"].push_back(ant_to_json(ant));
    }
    out["active_effects"] = json::array();
    for (const auto &effect : state.active_effects) {
        out["active_effects"].push_back(effect_to_json(effect));
    }
    return out;
}

json search_tower_to_json(const rs::SearchTower &tower) {
    json out;
    out["id"] = tower.tower_id;
    out["x"] = tower.x;
    out["y"] = tower.y;
    out["type"] = static_cast<int>(tower.tower_type);
    out["type_name"] = tower_type_name(tower.tower_type);
    out["cooldown"] = tower.cooldown;
    out["hp"] = tower.hp;
    out["max_hp"] = tower.max_hp();
    return out;
}

json search_ant_to_json(const rs::SearchAnt &ant) {
    json out;
    out["id"] = ant.ant_id;
    out["x"] = ant.x;
    out["y"] = ant.y;
    out["hp"] = ant.hp;
    out["max_hp"] = ant.max_hp();
    out["level"] = ant.level;
    out["age"] = ant.age;
    out["last_move"] = ant.last_move;
    out["behavior"] = static_cast<int>(ant.behavior);
    out["behavior_name"] = behavior_name(ant.behavior);
    out["kind"] = static_cast<int>(ant.kind);
    out["kind_name"] = kind_name(ant.kind);
    out["shield"] = ant.shield;
    out["defend"] = ant.defend;
    out["control_free_on_break"] = ant.control_free_on_break;
    out["is_frozen"] = ant.is_frozen;
    out["behavior_rounds"] = ant.behavior_rounds;
    out["behavior_expiry"] = ant.behavior_expiry;
    out["target_x"] = ant.target_x;
    out["target_y"] = ant.target_y;
    return out;
}

json search_effect_to_json(const rs::SearchEffect &effect) {
    json out;
    out["weapon_type"] = static_cast<int>(effect.weapon_type);
    out["weapon_name"] = weapon_name(effect.weapon_type);
    out["x"] = effect.x;
    out["y"] = effect.y;
    out["remaining_turns"] = effect.remaining_turns;
    return out;
}

json defense_sim_to_json(const rs::DefenseSimulator &simulator) {
    json out;
    out["round_index"] = simulator.round_index;
    out["player"] = simulator.player;
    out["enemy"] = simulator.enemy;
    out["coins"] = simulator.coins;
    out["base_hp"] = simulator.base_hp;
    out["enemy_generation_level"] = simulator.enemy_generation_level;
    out["enemy_ant_level"] = simulator.enemy_ant_level;
    out["next_ant_id"] = simulator.next_ant_id;
    out["next_tower_id"] = simulator.next_tower_id;
    out["lightning_cooldown"] = simulator.lightning_cooldown;
    out["terminal"] = simulator.terminal;
    out["ignore_enemy_spawns"] = simulator.ignore_enemy_spawns;
    out["towers"] = json::array();
    for (const auto &tower : simulator.towers) {
        out["towers"].push_back(search_tower_to_json(tower));
    }
    out["ants"] = json::array();
    for (const auto &ant : simulator.ants) {
        out["ants"].push_back(search_ant_to_json(ant));
    }
    out["my_effects"] = json::array();
    for (const auto &effect : simulator.my_effects) {
        out["my_effects"].push_back(search_effect_to_json(effect));
    }
    out["enemy_effects"] = json::array();
    for (const auto &effect : simulator.enemy_effects) {
        out["enemy_effects"].push_back(search_effect_to_json(effect));
    }
    return out;
}

json native_move_debug_to_json(const NativeAntMoveDebug &row) {
    json out;
    out["ant_id"] = row.ant_id;
    out["x"] = row.x;
    out["y"] = row.y;
    out["hp"] = row.hp;
    out["last_move"] = row.last_move;
    out["behavior"] = static_cast<int>(row.behavior);
    out["behavior_name"] = behavior_name(row.behavior);
    out["kind"] = static_cast<int>(row.kind);
    out["kind_name"] = kind_name(row.kind);
    out["options"] = json::array();
    for (const auto &option : row.options) {
        out["options"].push_back({
            {"direction", option.direction},
            {"nx", option.x},
            {"ny", option.y},
            {"score", option.score},
            {"raw_score", option.raw_score},
            {"probability", option.probability},
            {"annotated_x", option.annotated_x},
            {"annotated_y", option.annotated_y},
            {"annotated_tower_id", option.annotated_tower_id},
        });
    }
    return out;
}

json simulator_move_debug_to_json(rs::DefenseSimulator &simulator) {
    json rows = json::array();
    simulator.ensure_move_cache(true);
    for (const auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || ant.is_frozen) {
            continue;
        }
        const auto evaluated = simulator.evaluate_move_options(ant);
        json row = search_ant_to_json(ant);
        row["options"] = json::array();
        for (int index = 0; index < evaluated.options.size(); ++index) {
            const auto &option = evaluated.options[index];
            row["options"].push_back({
                {"direction", option.direction},
                {"nx", option.nx},
                {"ny", option.ny},
                {"probability", option.probability},
                {"danger", option.danger},
                {"annotated_x", index < evaluated.annotated_cells.size() ? evaluated.annotated_cells[index].first : -1},
                {"annotated_y", index < evaluated.annotated_cells.size() ? evaluated.annotated_cells[index].second : -1},
                {"annotated_tower_id", index < evaluated.annotated_towers.size() ? evaluated.annotated_towers[index] : -1},
            });
        }
        rows.push_back(std::move(row));
    }
    return rows;
}

json move_probability_delta_json(const json &sim_rows, const json &native_rows) {
    json out = json::array();
    for (const auto &sim_row : sim_rows) {
        const int ant_id = sim_row.value("id", -1);
        const json *native_row = nullptr;
        for (const auto &candidate : native_rows) {
            if (candidate.value("ant_id", -2) == ant_id) {
                native_row = &candidate;
                break;
            }
        }
        if (native_row == nullptr) {
            continue;
        }
        json row;
        row["ant_id"] = ant_id;
        row["sim"] = sim_row;
        row["native"] = *native_row;
        row["option_delta"] = json::array();
        for (const auto &native_option : (*native_row)["options"]) {
            const int direction = native_option.value("direction", -99);
            double sim_probability = 0.0;
            for (const auto &sim_option : sim_row["options"]) {
                if (sim_option.value("direction", -98) == direction) {
                    sim_probability = sim_option.value("probability", 0.0);
                    break;
                }
            }
            const double native_probability = native_option.value("probability", 0.0);
            row["option_delta"].push_back({
                {"direction", direction},
                {"native_probability", native_probability},
                {"sim_probability", sim_probability},
                {"sim_minus_native", sim_probability - native_probability},
            });
        }
        out.push_back(std::move(row));
    }
    return out;
}

json public_defense_projection_summary(const PublicRoundState &state, int player) {
    const int enemy = 1 - player;
    json out;
    out["round_index"] = state.round_index;
    out["player"] = player;
    out["coins"] = state.coins[player];
    out["base_hp"] = state.camps_hp[player];
    out["enemy_generation_level"] = state.speed_lv[enemy];
    out["enemy_ant_level"] = state.anthp_lv[enemy];
    int tower_count = 0;
    int tower_hp = 0;
    int worker_count = 0;
    int combat_count = 0;
    int ant_hp = 0;
    for (const auto &tower : state.towers) {
        if (tower.player != player || tower.hp <= 0) {
            continue;
        }
        ++tower_count;
        tower_hp += tower.hp;
    }
    for (const auto &ant : state.ants) {
        if (ant.player != enemy || !ant.is_alive()) {
            continue;
        }
        if (ant.kind == AntKind::Combat) {
            ++combat_count;
        } else {
            ++worker_count;
        }
        ant_hp += ant.hp;
    }
    out["tower_count"] = tower_count;
    out["tower_hp"] = tower_hp;
    out["worker_count"] = worker_count;
    out["combat_count"] = combat_count;
    out["ant_count"] = worker_count + combat_count;
    out["ant_hp"] = ant_hp;
    return out;
}

json defense_projection_summary(const rs::DefenseSimulator &simulator, int player) {
    const auto [base_x, base_y] = kPlayerBases[player];
    json out;
    out["round_index"] = simulator.round_index;
    out["player"] = player;
    out["coins"] = simulator.coins;
    out["base_hp"] = simulator.base_hp;
    out["enemy_generation_level"] = simulator.enemy_generation_level;
    out["enemy_ant_level"] = simulator.enemy_ant_level;
    int tower_hp = 0;
    int worker_count = 0;
    int combat_count = 0;
    int ant_hp = 0;
    for (const auto &tower : simulator.towers) {
        if (!tower.alive()) {
            continue;
        }
        tower_hp += tower.hp;
    }
    for (const auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || (ant.x == base_x && ant.y == base_y)) {
            continue;
        }
        if (ant.kind == AntKind::Combat) {
            ++combat_count;
        } else {
            ++worker_count;
        }
        ant_hp += ant.hp;
    }
    out["tower_count"] = simulator.towers.size();
    out["tower_hp"] = tower_hp;
    out["worker_count"] = worker_count;
    out["combat_count"] = combat_count;
    out["ant_count"] = worker_count + combat_count;
    out["ant_hp"] = ant_hp;
    return out;
}

json projection_delta_summary(const json &sim, const json &standard) {
    json out;
    const std::vector<std::string> fields = {
        "base_hp",
        "coins",
        "tower_count",
        "tower_hp",
        "worker_count",
        "combat_count",
        "ant_count",
        "ant_hp",
        "enemy_generation_level",
        "enemy_ant_level",
    };
    for (const auto &field : fields) {
        const double lhs = sim.value(field, 0.0);
        const double rhs = standard.value(field, 0.0);
        out[field] = lhs - rhs;
    }
    return out;
}

json eval_breakdown_to_json(const ls::EvalBreakdown &value) {
    json out;
    out["base_hp_raw"] = value.base_hp_raw;
    out["base_hp_score"] = value.base_hp_score;
    out["tower_value_raw"] = value.tower_value_raw;
    out["tower_value_score"] = value.tower_value_score;
    out["money_raw"] = value.money_raw;
    out["money_score"] = value.money_score;
    out["c1_bonus_raw"] = value.c1_bonus_raw;
    out["c1_bonus_score"] = value.c1_bonus_score;
    out["worker_threat_raw"] = value.worker_threat_raw;
    out["worker_threat_score"] = value.worker_threat_score;
    out["combat_threat_raw"] = value.combat_threat_raw;
    out["combat_threat_score"] = value.combat_threat_score;
    out["future_base_damage_raw"] = value.future_base_damage_raw;
    out["future_base_damage_score"] = value.future_base_damage_score;
    out["future_worker_threat_raw"] = value.future_worker_threat_raw;
    out["future_combat_threat_raw"] = value.future_combat_threat_raw;
    out["future_projected_threat_raw"] = value.future_projected_threat_raw;
    out["future_adjusted_threat_raw"] = value.future_adjusted_threat_raw;
    out["future_threat_adjustment_score"] = value.future_threat_adjustment_score;
    out["total_score"] = value.total_score;
    return out;
}

struct RunningStat {
    std::vector<double> values;

    void add(double value) { values.push_back(value); }
};

double quantile_from_sorted(const std::vector<double> &sorted, double q) {
    if (sorted.empty()) {
        return 0.0;
    }
    if (sorted.size() == 1) {
        return sorted.front();
    }
    const double position = std::clamp(q, 0.0, 1.0) * static_cast<double>(sorted.size() - 1);
    const auto lower = static_cast<std::size_t>(std::floor(position));
    const auto upper = static_cast<std::size_t>(std::ceil(position));
    const double fraction = position - static_cast<double>(lower);
    return sorted[lower] * (1.0 - fraction) + sorted[upper] * fraction;
}

json running_stat_to_json(const RunningStat &stat) {
    json out;
    const int count = static_cast<int>(stat.values.size());
    out["count"] = count;
    if (count <= 0) {
        out["mean"] = 0.0;
        out["sd"] = 0.0;
        out["se"] = 0.0;
        out["min"] = 0.0;
        out["p05"] = 0.0;
        out["p50"] = 0.0;
        out["p95"] = 0.0;
        out["max"] = 0.0;
        return out;
    }
    double sum = 0.0;
    for (double value : stat.values) {
        sum += value;
    }
    const double mean = sum / static_cast<double>(count);
    double variance_sum = 0.0;
    for (double value : stat.values) {
        const double delta = value - mean;
        variance_sum += delta * delta;
    }
    const double sd = count > 1 ? std::sqrt(variance_sum / static_cast<double>(count - 1)) : 0.0;
    std::vector<double> sorted = stat.values;
    std::sort(sorted.begin(), sorted.end());
    out["mean"] = mean;
    out["sd"] = sd;
    out["se"] = sd / std::sqrt(static_cast<double>(std::max(1, count)));
    out["min"] = sorted.front();
    out["p05"] = quantile_from_sorted(sorted, 0.05);
    out["p50"] = quantile_from_sorted(sorted, 0.50);
    out["p95"] = quantile_from_sorted(sorted, 0.95);
    out["max"] = sorted.back();
    return out;
}

struct RolloutMetricSet {
    double base_hp = 0.0;
    double coins = 0.0;
    double tower_value = 0.0;
    double worker_threat = 0.0;
    double combat_threat = 0.0;
    double total_threat = 0.0;
    double total_score = 0.0;
    double tower_count = 0.0;
    double tower_hp = 0.0;
    double worker_count = 0.0;
    double combat_count = 0.0;
    double ant_hp = 0.0;
};

std::vector<std::pair<std::string, double>> rollout_metric_values(const RolloutMetricSet &metrics) {
    return {
        {"base_hp", metrics.base_hp},
        {"coins", metrics.coins},
        {"tower_value", metrics.tower_value},
        {"worker_threat", metrics.worker_threat},
        {"combat_threat", metrics.combat_threat},
        {"total_threat", metrics.total_threat},
        {"total_score", metrics.total_score},
        {"tower_count", metrics.tower_count},
        {"tower_hp", metrics.tower_hp},
        {"worker_count", metrics.worker_count},
        {"combat_count", metrics.combat_count},
        {"ant_hp", metrics.ant_hp},
    };
}

RolloutMetricSet rollout_metrics_from_defense(const rs::DefenseSimulator &simulator, int player) {
    const auto [base_x, base_y] = kPlayerBases[player];
    RolloutMetricSet out;
    const ls::EvalBreakdown eval = ls::evaluate_terminal(simulator, player, false);
    out.base_hp = eval.base_hp_raw;
    out.coins = eval.money_raw;
    out.tower_value = eval.tower_value_raw;
    out.worker_threat = eval.worker_threat_raw;
    out.combat_threat = eval.combat_threat_raw;
    out.total_threat = eval.worker_threat_raw + eval.combat_threat_raw;
    out.total_score = eval.total_score;
    for (const auto &tower : simulator.towers) {
        if (!tower.alive()) {
            continue;
        }
        out.tower_count += 1.0;
        out.tower_hp += static_cast<double>(tower.hp);
    }
    for (const auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || (ant.x == base_x && ant.y == base_y)) {
            continue;
        }
        if (ant.kind == AntKind::Combat) {
            out.combat_count += 1.0;
        } else {
            out.worker_count += 1.0;
        }
        out.ant_hp += static_cast<double>(ant.hp);
    }
    return out;
}

PublicRoundState defense_only_round_state(const PublicRoundState &state, int player) {
    const int enemy = 1 - player;
    PublicRoundState out = state;
    out.towers.clear();
    for (const auto &tower : state.towers) {
        if (tower.player == player) {
            out.towers.push_back(tower);
        }
    }
    out.ants.clear();
    for (const auto &ant : state.ants) {
        if (ant.player == enemy && ant.is_alive()) {
            out.ants.push_back(ant);
        }
    }
    return out;
}

RolloutMetricSet rollout_metrics_from_native(NativeSimulator &native, int player) {
    PublicState final_state(native.seed(), native.movement_policy(), native.cold_handle_rule_illegal());
    final_state.sync_public_round_state(native.to_public_round_state());
    rs::DefenseSimulator projected = rs::make_defense_simulator(final_state, &native, player);
    projected.ignore_enemy_spawns = true;
    return rollout_metrics_from_defense(projected, player);
}

json compare_metric_stats(
    const std::vector<std::pair<std::string, RunningStat>> &standard_stats,
    const std::vector<std::pair<std::string, RunningStat>> &simulator_stats,
    const std::vector<std::pair<std::string, RunningStat>> &delta_stats) {
    json out;
    for (std::size_t index = 0; index < standard_stats.size(); ++index) {
        const std::string &name = standard_stats[index].first;
        const json standard = running_stat_to_json(standard_stats[index].second);
        const json simulator = running_stat_to_json(simulator_stats[index].second);
        json delta = running_stat_to_json(delta_stats[index].second);
        const double standard_se = standard.value("se", 0.0);
        const double simulator_se = simulator.value("se", 0.0);
        const double two_sample_se = std::sqrt(standard_se * standard_se + simulator_se * simulator_se);
        delta["two_sample_se"] = two_sample_se;
        delta["mean_abs_over_two_sample_se"] =
            two_sample_se > 0.0 ? std::fabs(delta.value("mean", 0.0)) / two_sample_se : 0.0;
        out[name] = {
            {"standard", standard},
            {"simulator", simulator},
            {"sim_minus_standard", delta},
        };
    }
    return out;
}

struct EntityAlignmentStats {
    RunningStat standard_alive;
    RunningStat simulator_alive;
    RunningStat delta_alive;
    RunningStat standard_hp;
    RunningStat simulator_hp;
    RunningStat delta_hp;
    std::map<std::string, int> standard_positions;
    std::map<std::string, int> simulator_positions;
};

std::string entity_position_key(int x, int y, bool alive) {
    if (!alive) {
        return "dead";
    }
    return std::to_string(x) + "," + std::to_string(y);
}

void add_entity_sample(EntityAlignmentStats &stats, bool standard_alive, int standard_x, int standard_y, int standard_hp,
                       bool simulator_alive, int simulator_x, int simulator_y, int simulator_hp) {
    stats.standard_alive.add(standard_alive ? 1.0 : 0.0);
    stats.simulator_alive.add(simulator_alive ? 1.0 : 0.0);
    stats.delta_alive.add((simulator_alive ? 1.0 : 0.0) - (standard_alive ? 1.0 : 0.0));
    stats.standard_hp.add(standard_alive ? static_cast<double>(standard_hp) : 0.0);
    stats.simulator_hp.add(simulator_alive ? static_cast<double>(simulator_hp) : 0.0);
    stats.delta_hp.add((simulator_alive ? static_cast<double>(simulator_hp) : 0.0) -
                       (standard_alive ? static_cast<double>(standard_hp) : 0.0));
    ++stats.standard_positions[entity_position_key(standard_x, standard_y, standard_alive)];
    ++stats.simulator_positions[entity_position_key(simulator_x, simulator_y, simulator_alive)];
}

json entity_alignment_stats_to_json(const EntityAlignmentStats &stats, int samples) {
    json out;
    const json standard_alive = running_stat_to_json(stats.standard_alive);
    const json simulator_alive = running_stat_to_json(stats.simulator_alive);
    json delta_alive = running_stat_to_json(stats.delta_alive);
    const double alive_two_sample_se =
        std::sqrt(std::pow(standard_alive.value("se", 0.0), 2.0) + std::pow(simulator_alive.value("se", 0.0), 2.0));
    delta_alive["two_sample_se"] = alive_two_sample_se;
    delta_alive["mean_abs_over_two_sample_se"] =
        alive_two_sample_se > 0.0 ? std::fabs(delta_alive.value("mean", 0.0)) / alive_two_sample_se : 0.0;

    const json standard_hp = running_stat_to_json(stats.standard_hp);
    const json simulator_hp = running_stat_to_json(stats.simulator_hp);
    json delta_hp = running_stat_to_json(stats.delta_hp);
    const double hp_two_sample_se =
        std::sqrt(std::pow(standard_hp.value("se", 0.0), 2.0) + std::pow(simulator_hp.value("se", 0.0), 2.0));
    delta_hp["two_sample_se"] = hp_two_sample_se;
    delta_hp["mean_abs_over_two_sample_se"] =
        hp_two_sample_se > 0.0 ? std::fabs(delta_hp.value("mean", 0.0)) / hp_two_sample_se : 0.0;

    out["alive"] = {
        {"standard", standard_alive},
        {"simulator", simulator_alive},
        {"sim_minus_standard", delta_alive},
    };
    out["hp"] = {
        {"standard", standard_hp},
        {"simulator", simulator_hp},
        {"sim_minus_standard", delta_hp},
    };

    struct PositionDelta {
        std::string key;
        int standard_count = 0;
        int simulator_count = 0;
        int delta = 0;
    };
    std::vector<PositionDelta> positions;
    std::map<std::string, int> keys = stats.standard_positions;
    for (const auto &item : stats.simulator_positions) {
        keys.emplace(item.first, 0);
    }
    positions.reserve(keys.size());
    for (const auto &item : keys) {
        const int standard_count =
            stats.standard_positions.count(item.first) ? stats.standard_positions.at(item.first) : 0;
        const int simulator_count =
            stats.simulator_positions.count(item.first) ? stats.simulator_positions.at(item.first) : 0;
        positions.push_back(PositionDelta{item.first, standard_count, simulator_count, simulator_count - standard_count});
    }
    std::sort(positions.begin(), positions.end(), [](const PositionDelta &lhs, const PositionDelta &rhs) {
        const int lhs_abs = std::abs(lhs.delta);
        const int rhs_abs = std::abs(rhs.delta);
        if (lhs_abs != rhs_abs) {
            return lhs_abs > rhs_abs;
        }
        return lhs.key < rhs.key;
    });
    out["top_position_deltas"] = json::array();
    const int limit = std::min<int>(8, positions.size());
    for (int index = 0; index < limit; ++index) {
        const auto &item = positions[index];
        out["top_position_deltas"].push_back({
            {"position", item.key},
            {"standard_count", item.standard_count},
            {"simulator_count", item.simulator_count},
            {"delta_count", item.delta},
            {"standard_rate", samples > 0 ? static_cast<double>(item.standard_count) / static_cast<double>(samples) : 0.0},
            {"simulator_rate", samples > 0 ? static_cast<double>(item.simulator_count) / static_cast<double>(samples) : 0.0},
        });
    }
    return out;
}

json eval_delta_summary(const ls::EvalBreakdown &lhs, const ls::EvalBreakdown &rhs) {
    json out;
    out["base_hp_raw"] = lhs.base_hp_raw - rhs.base_hp_raw;
    out["tower_value_raw"] = lhs.tower_value_raw - rhs.tower_value_raw;
    out["money_raw"] = lhs.money_raw - rhs.money_raw;
    out["worker_threat_raw"] = lhs.worker_threat_raw - rhs.worker_threat_raw;
    out["combat_threat_raw"] = lhs.combat_threat_raw - rhs.combat_threat_raw;
    out["future_base_damage_raw"] = lhs.future_base_damage_raw - rhs.future_base_damage_raw;
    out["future_projected_threat_raw"] = lhs.future_projected_threat_raw - rhs.future_projected_threat_raw;
    out["total_score"] = lhs.total_score - rhs.total_score;
    return out;
}

json rollout_eval_to_json(const ls::RolloutEvaluation &value) {
    json out;
    out["terminal"] = eval_breakdown_to_json(value.terminal);
    out["lightning_bonus_raw"] = value.lightning_bonus_raw;
    out["lightning_bonus_score"] = value.lightning_bonus_score;
    out["reactive_operation_penalty"] = value.reactive_operation_penalty;
    out["total_score"] = value.total_score;
    return out;
}

json forced_sample_to_json(const ls::RolloutForcedSample &sample) {
    json out;
    out["probability"] = sample.probability;
    out["forced_moves"] = json::array();
    for (int index = 0; index < sample.forced_moves.size(); ++index) {
        const auto &move = sample.forced_moves[index];
        out["forced_moves"].push_back({
            {"ant_id", move.ant_id},
            {"direction", move.direction},
        });
    }
    return out;
}

Operation parse_replay_operation(const json &raw) {
    const int type = raw.value("type", -1);
    const int id = raw.value("id", -1);
    const int args = raw.value("args", -1);
    const int x = raw.value("pos", json::object()).value("x", -1);
    const int y = raw.value("pos", json::object()).value("y", -1);
    switch (static_cast<OperationType>(type)) {
    case OperationType::BuildTower:
        return Operation(OperationType::BuildTower, x, y);
    case OperationType::UpgradeTower:
        return Operation(OperationType::UpgradeTower, id, args);
    case OperationType::DowngradeTower:
        return Operation(OperationType::DowngradeTower, id);
    case OperationType::UseLightningStorm:
        return Operation(OperationType::UseLightningStorm, x, y);
    case OperationType::UseEmpBlaster:
        return Operation(OperationType::UseEmpBlaster, x, y);
    case OperationType::UseDeflector:
        return Operation(OperationType::UseDeflector, x, y);
    case OperationType::UseEmergencyEvasion:
        return Operation(OperationType::UseEmergencyEvasion, x, y);
    case OperationType::UpgradeGenerationSpeed:
        return Operation(OperationType::UpgradeGenerationSpeed);
    case OperationType::UpgradeGeneratedAnt:
        return Operation(OperationType::UpgradeGeneratedAnt);
    default:
        return Operation(static_cast<OperationType>(-1));
    }
}

std::vector<Operation> parse_replay_operations(const json &ops_raw) {
    std::vector<Operation> operations;
    if (!ops_raw.is_array()) {
        return operations;
    }
    operations.reserve(ops_raw.size());
    for (const auto &item : ops_raw) {
        const Operation operation = parse_replay_operation(item);
        if (static_cast<int>(operation.op_type) < 0) {
            continue;
        }
        operations.push_back(operation);
    }
    return operations;
}

PublicRoundState parse_replay_round_state(const json &raw_state, int round_index) {
    PublicRoundState state;
    state.round_index = round_index;

    if (raw_state.contains("towers") && raw_state.at("towers").is_array()) {
        for (const auto &row : raw_state.at("towers")) {
            const int type = row.value("type", -1);
            if (type < 0) {
                continue;
            }
            state.towers.push_back(Tower{
                row.value("id", -1),
                row.value("player", -1),
                row.value("pos", json::object()).value("x", -1),
                row.value("pos", json::object()).value("y", -1),
                static_cast<TowerType>(type),
                row.value("cd", 0),
                row.value("hp", tower_stats(static_cast<TowerType>(type)).max_hp),
            });
        }
    }

    if (raw_state.contains("ants") && raw_state.at("ants").is_array()) {
        for (const auto &row : raw_state.at("ants")) {
            Ant ant{
                row.value("id", -1),
                row.value("player", -1),
                row.value("pos", json::object()).value("x", -1),
                row.value("pos", json::object()).value("y", -1),
                row.value("hp", 0),
                row.value("level", 0),
                row.value("age", 0),
                static_cast<AntStatus>(row.value("status", 0)),
                static_cast<AntBehavior>(row.value("behavior", 0)),
                static_cast<AntKind>(row.value("kind", 0)),
            };
            ant.last_move = row.value("move", -1);
            state.ants.push_back(ant);
        }
    }

    const auto coins = raw_state.value("coins", std::vector<int>{kInitialCoins, kInitialCoins});
    if (coins.size() >= 2) {
        state.coins = {coins[0], coins[1]};
    }
    const auto camps = raw_state.value("camps", std::vector<int>{kBaseHp, kBaseHp});
    if (camps.size() >= 2) {
        state.camps_hp = {camps[0], camps[1]};
    }
    const auto speed_lv = raw_state.value("speedLv", std::vector<int>{0, 0});
    if (speed_lv.size() >= 2) {
        state.speed_lv = {speed_lv[0], speed_lv[1]};
    }
    const auto anthp_lv = raw_state.value("anthpLv", std::vector<int>{0, 0});
    if (anthp_lv.size() >= 2) {
        state.anthp_lv = {anthp_lv[0], anthp_lv[1]};
    }

    if (raw_state.contains("weaponCooldowns") && raw_state.at("weaponCooldowns").is_array()) {
        int player = 0;
        for (const auto &row : raw_state.at("weaponCooldowns")) {
            if (player >= 2 || !row.is_array()) {
                break;
            }
            if (row.size() == 4) {
                state.weapon_cooldowns[player] = {0, row.at(0).get<int>(), row.at(1).get<int>(), row.at(2).get<int>(),
                                                  row.at(3).get<int>()};
            } else if (row.size() >= 5) {
                state.weapon_cooldowns[player] = {row.at(0).get<int>(), row.at(1).get<int>(), row.at(2).get<int>(),
                                                  row.at(3).get<int>(), row.at(4).get<int>()};
            }
            ++player;
        }
    }

    if (raw_state.contains("activeEffects") && raw_state.at("activeEffects").is_array()) {
        for (const auto &row : raw_state.at("activeEffects")) {
            state.active_effects.push_back(WeaponEffect{
                static_cast<SuperWeaponType>(row.value("type", 1)),
                row.value("player", -1),
                row.value("x", -1),
                row.value("y", -1),
                row.value("duration", 0),
            });
        }
    }

    return state;
}

void apply_replay_tower_delta(const json &raw_state, std::unordered_map<int, Tower> &towers_by_id) {
    if (!raw_state.contains("towers") || !raw_state.at("towers").is_array()) {
        return;
    }
    for (const auto &row : raw_state.at("towers")) {
        const int tower_id = row.value("id", -1);
        if (tower_id < 0) {
            continue;
        }
        const int type = row.value("type", -1);
        if (type < 0) {
            towers_by_id.erase(tower_id);
            continue;
        }
        towers_by_id[tower_id] = Tower{
            tower_id,
            row.value("player", -1),
            row.value("pos", json::object()).value("x", -1),
            row.value("pos", json::object()).value("y", -1),
            static_cast<TowerType>(type),
            row.value("cd", 0),
            row.value("hp", tower_stats(static_cast<TowerType>(type)).max_hp),
        };
    }
}

std::vector<Tower> snapshot_replay_towers(const std::unordered_map<int, Tower> &towers_by_id) {
    std::vector<Tower> towers;
    towers.reserve(towers_by_id.size());
    for (const auto &item : towers_by_id) {
        towers.push_back(item.second);
    }
    std::sort(towers.begin(), towers.end(), [](const Tower &lhs, const Tower &rhs) {
        if (lhs.player != rhs.player) {
            return lhs.player < rhs.player;
        }
        return lhs.tower_id < rhs.tower_id;
    });
    return towers;
}

void advance_replay_tower_cooldowns(std::unordered_map<int, Tower> &towers_by_id) {
    for (auto &item : towers_by_id) {
        Tower &tower = item.second;
        if (tower.cooldown > 0) {
            --tower.cooldown;
        }
    }
}

ReplayRoundStart load_replay_round_start(const std::string &replay_path, int round) {
    std::ifstream fin(replay_path);
    if (!fin) {
        throw std::runtime_error("failed to open replay: " + replay_path);
    }
    json replay;
    fin >> replay;
    if (!replay.is_array()) {
        throw std::runtime_error("replay is not a JSON array");
    }
    if (round < 0 || round > static_cast<int>(replay.size())) {
        throw std::runtime_error("round is out of range");
    }

    std::uint64_t seed = 0;
    if (!replay.empty()) {
        seed = replay.at(0).value("seed", 0ULL);
    }
    ReplayRoundStart out(seed);
    out.round = round;
    std::unordered_map<int, Tower> towers_by_id;
    for (int index = 0; index < round; ++index) {
        const auto &record = replay.at(static_cast<std::size_t>(index));
        const auto ops0 = parse_replay_operations(record.value("op0", json::array()));
        const auto ops1 = parse_replay_operations(record.value("op1", json::array()));
        out.native.resolve_turn(ops0, ops1);
        if (record.contains("round_state") && record.at("round_state").is_object()) {
            const auto &round_state = record.at("round_state");
            advance_replay_tower_cooldowns(towers_by_id);
            apply_replay_tower_delta(round_state, towers_by_id);
            PublicRoundState public_state = parse_replay_round_state(round_state, index + 1);
            public_state.towers = snapshot_replay_towers(towers_by_id);
            out.native.sync_public_round_state(public_state);
        }
    }

    if (round < static_cast<int>(replay.size())) {
        out.replay_record = replay.at(static_cast<std::size_t>(round));
    }
    out.public_state.sync_public_round_state(out.native.to_public_round_state());
    return out;
}

std::uint64_t rollout_serial_for_round(int round) {
    return static_cast<std::uint64_t>(std::max(0, round) + 1);
}

std::uint64_t plan_rollout_seed(const PublicState &state, std::uint64_t serial, std::size_t root_index, int rollout, int horizon) {
    return ls::plan_rollout_seed(state.seed, serial, root_index, rollout, horizon);
}

std::vector<EvaluatedPlanWithIndex> evaluate_root_plans(
    const PublicState &state,
    const NativeSimulator *native,
    int player,
    std::uint64_t serial,
    ls::UcbEvaluationTrace *trace = nullptr) {
    rs::DefenseSimulator defense_root = rs::make_defense_simulator(state, native, player);
    defense_root.ignore_enemy_spawns = true;
    if (trace != nullptr) {
        defense_root.profile = &trace->simulator_profile;
    }

    const ls::RootPlanSet root_plans = ls::generate_root_plans(state, &defense_root, player);
    return ls::evaluate_root_plans(state, defense_root, player, serial, root_plans, trace);
}

const EvaluatedPlanWithIndex &require_plan_by_key(const std::vector<EvaluatedPlanWithIndex> &plans, const std::string &key) {
    for (const auto &item : plans) {
        if (item.plan.key == key) {
            return item;
        }
    }
    throw std::runtime_error("plan key not found: " + key);
}

std::vector<const ls::UcbRolloutRecord *> ucb_samples_for(
    const ls::UcbEvaluationTrace &trace,
    std::size_t root_index) {
    std::vector<const ls::UcbRolloutRecord *> out;
    for (const auto &sample : trace.samples) {
        if (sample.root_index == root_index) {
            out.push_back(&sample);
        }
    }
    std::sort(out.begin(), out.end(), [](const auto *lhs, const auto *rhs) {
        return lhs->arm_sample_index < rhs->arm_sample_index;
    });
    return out;
}

std::vector<const ls::UcbBatchRecord *> ucb_batches_for(
    const ls::UcbEvaluationTrace &trace,
    std::size_t root_index) {
    std::vector<const ls::UcbBatchRecord *> out;
    for (const auto &batch : trace.batches) {
        if (batch.root_index == root_index) {
            out.push_back(&batch);
        }
    }
    std::sort(out.begin(), out.end(), [](const auto *lhs, const auto *rhs) {
        return lhs->batch_index < rhs->batch_index;
    });
    return out;
}

const ls::UcbRolloutRecord *ucb_sample_for(
    const ls::UcbEvaluationTrace &trace,
    std::size_t root_index,
    int sample_index) {
    const ls::UcbRolloutRecord *fallback = nullptr;
    for (const auto &sample : trace.samples) {
        if (sample.root_index != root_index) {
            continue;
        }
        if (fallback == nullptr || sample.arm_sample_index < fallback->arm_sample_index) {
            fallback = &sample;
        }
        if (sample.arm_sample_index == sample_index) {
            return &sample;
        }
    }
    return fallback;
}

json evaluated_plan_to_json(
    const PublicState &state,
    int player,
    const EvaluatedPlanWithIndex &item,
    const ls::UcbEvaluationTrace *trace = nullptr) {
    json out;
    const auto [category, category_label] = action_category(item.plan);
    out["root_index"] = item.root_index;
    out["key"] = item.plan.key;
    out["name"] = item.plan.name;
    out["category"] = category;
    out["category_label"] = category_label;
    out["base_name"] = item.plan.base_name;
    out["lure_name"] = item.plan.lure_name;
    out["lightning_name"] = item.plan.lightning_name;
    out["has_lightning"] = item.plan.has_lightning;
    out["horizon"] = item.plan.horizon;
    out["followup"] = ls::followup_text(item.plan.followup);
    out["heuristic"] = item.plan.heuristic;
    out["base_heuristic"] = item.plan.base_heuristic;
    out["lure_heuristic"] = item.plan.lure_heuristic;
    out["lightning_heuristic"] = item.plan.lightning_heuristic;
    out["operation_penalty"] = item.plan.operation_penalty;
    out["lightning_static_bonus"] = item.plan.lightning_static_bonus;
    out["mean_rollout_score"] = item.mean_rollout_score;
    out["mean_score"] = item.mean_score;
    out["rollout_count"] = item.rollout_count;
    out["rollout_weight_sum"] = item.rollout_weight_sum;
    out["pretty"] = ls::pretty_ops_text(state, player, item.plan.ops);
    out["ops"] = json::array();
    for (const auto &operation : item.plan.ops) {
        out["ops"].push_back(operation_to_json(operation));
    }
    out["mean_rollout"] = rollout_eval_to_json(item.mean_rollout);
    if (trace != nullptr) {
        const auto samples = ucb_samples_for(*trace, item.root_index);
        const auto batches = ucb_batches_for(*trace, item.root_index);
        double elapsed_us = 0.0;
        for (const auto *batch : batches) {
            elapsed_us += batch->elapsed_us;
        }
        out["ucb_elapsed_us"] = elapsed_us;
        out["ucb_batch_count"] = static_cast<int>(batches.size());
        out["ucb_sample_count"] = static_cast<int>(samples.size());
    }
    return out;
}

json single_plan_to_json(const PublicState &state, int player, const ls::SinglePlan &plan) {
    json out;
    out["name"] = plan.name;
    out["followup"] = ls::followup_text(plan.followup);
    out["heuristic"] = plan.heuristic;
    out["pretty"] = ls::pretty_ops_text(state, player, plan.ops);
    out["ops"] = json::array();
    for (const auto &operation : plan.ops) {
        out["ops"].push_back(operation_to_json(operation));
    }
    return out;
}

MoveTraceSummary trace_move_phase(
    rs::DefenseSimulator &simulator,
    rs::FastRng &rng,
    const rs::FixedList<rs::ForcedMove, rs::kMaxImportantAnts> *forced_moves = nullptr) {
    MoveTraceSummary summary;
    bool need_enhanced_cache = false;
    for (const auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || ant.is_frozen) {
            continue;
        }
        if (ant.behavior != AntBehavior::Random && ant.behavior != AntBehavior::Bewitched) {
            need_enhanced_cache = true;
            break;
        }
    }
    if (need_enhanced_cache) {
        simulator.ensure_move_cache(true);
    }

    auto forced_move_for = [&](int ant_id) {
        if (forced_moves == nullptr) {
            return rs::kNoMove;
        }
        for (int index = 0; index < forced_moves->size(); ++index) {
            if ((*forced_moves)[index].ant_id == ant_id) {
                return (*forced_moves)[index].direction;
            }
        }
        return rs::kNoMove;
    };

    for (auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || ant.is_frozen) {
            continue;
        }
        json row;
        row["ant_before"] = search_ant_to_json(ant);

        int move = rs::kNoMove;
        double chosen_probability = 1.0;
        std::string source = "sample";
        json options = json::array();
        bool attacked_tower = false;
        int attacked_tower_id = -1;
        const int forced_move = forced_move_for(ant.ant_id);

        if (forced_move != rs::kNoMove) {
            source = "forced_schedule";
            if (ant.behavior == AntBehavior::Random) {
                const auto candidates = simulator.legal_move_candidates(ant);
                const double probability = 1.0 / static_cast<double>(std::max(1, candidates.size()));
                for (int index = 0; index < candidates.size(); ++index) {
                    const auto &candidate = candidates[index];
                    options.push_back(json{
                        {"direction", candidate.direction},
                        {"nx", candidate.nx},
                        {"ny", candidate.ny},
                        {"probability", probability},
                    });
                    if (candidate.direction == forced_move) {
                        chosen_probability = probability;
                    }
                }
                move = forced_move;
            } else {
                const auto evaluated = simulator.evaluate_move_options(ant);
                move = forced_move;
                for (int index = 0; index < evaluated.options.size(); ++index) {
                    const auto &option = evaluated.options[index];
                    options.push_back(json{
                        {"direction", option.direction},
                        {"nx", option.nx},
                        {"ny", option.ny},
                        {"probability", option.probability},
                        {"danger", option.danger},
                    });
                    if (option.direction == forced_move) {
                        chosen_probability = option.probability;
                        const int cell_x =
                            index < evaluated.annotated_cells.size() ? evaluated.annotated_cells[index].first : -1;
                        const int cell_y =
                            index < evaluated.annotated_cells.size() ? evaluated.annotated_cells[index].second : -1;
                        const int tower_id =
                            index < evaluated.annotated_towers.size() ? evaluated.annotated_towers[index] : -1;
                        simulator.record_move_annotation(option.direction, cell_x, cell_y, tower_id);
                    }
                }
            }
        } else if (ant.behavior == AntBehavior::Random) {
            source = "uniform_random";
            const auto candidates = simulator.legal_move_candidates(ant);
            const double probability = 1.0 / static_cast<double>(std::max(1, candidates.size()));
            for (int index = 0; index < candidates.size(); ++index) {
                const auto &candidate = candidates[index];
                options.push_back(json{
                    {"direction", candidate.direction},
                    {"nx", candidate.nx},
                    {"ny", candidate.ny},
                    {"probability", probability},
                });
            }
            const int pick = rng.next_int(candidates.size());
            move = candidates[pick].direction;
            chosen_probability = probability;
        } else {
            const auto evaluated = simulator.evaluate_move_options(ant);
            double threshold = rng.next_double();
            double cumulative = 0.0;
            int chosen_index = std::max(0, evaluated.options.size() - 1);
            for (int index = 0; index < evaluated.options.size(); ++index) {
                const auto &option = evaluated.options[index];
                options.push_back(json{
                    {"direction", option.direction},
                    {"nx", option.nx},
                    {"ny", option.ny},
                    {"probability", option.probability},
                    {"danger", option.danger},
                });
                cumulative += option.probability;
                if (threshold <= cumulative && chosen_index == evaluated.options.size() - 1) {
                    chosen_index = index;
                }
            }
            if (evaluated.options.empty()) {
                move = rs::kNoMove;
                chosen_probability = 1.0;
            } else {
                const auto &chosen = evaluated.options[chosen_index];
                move = chosen.direction;
                chosen_probability = chosen.probability;
                const int cell_x =
                    chosen_index < evaluated.annotated_cells.size() ? evaluated.annotated_cells[chosen_index].first : -1;
                const int cell_y =
                    chosen_index < evaluated.annotated_cells.size() ? evaluated.annotated_cells[chosen_index].second : -1;
                const int tower_id =
                    chosen_index < evaluated.annotated_towers.size() ? evaluated.annotated_towers[chosen_index] : -1;
                simulator.record_move_annotation(chosen.direction, cell_x, cell_y, tower_id);
            }
        }

        if (move != rs::kNoMove) {
            const int nx = ant.x + kOffset[ant.y & 1][move][0];
            const int ny = ant.y + kOffset[ant.y & 1][move][1];
            if (const rs::SearchTower *tower = simulator.tower_at(nx, ny); tower != nullptr) {
                attacked_tower = true;
                attacked_tower_id = tower->tower_id;
            }
        }

        simulator.resolve_ant_step(ant, move);

        row["choice_source"] = source;
        row["chosen_direction"] = move;
        row["chosen_probability"] = chosen_probability;
        row["options"] = options;
        row["attacked_tower"] = attacked_tower;
        row["attacked_tower_id"] = attacked_tower_id;
        row["ant_after"] = search_ant_to_json(ant);
        summary.moves.push_back(row);
        summary.log_probability += std::log(std::max(chosen_probability, 1e-12));
    }

    if (!config().ignore_periodic_random_move && need_enhanced_cache && rs::kTeleportInterval > 0 &&
        (simulator.round_index + 1) % rs::kTeleportInterval == 0) {
        simulator.clear_move_cache();
    }
    return summary;
}

json simulate_traced_round(
    rs::DefenseSimulator &simulator,
    rs::FastRng &rng,
    const rs::FixedList<rs::ForcedMove, rs::kMaxImportantAnts> *forced_moves = nullptr) {
    json out;
    out["state_start"] = defense_sim_to_json(simulator);
    simulator.tower_attack_phase(rng);
    out["state_after_tower_phase"] = defense_sim_to_json(simulator);
    const MoveTraceSummary move_summary = trace_move_phase(simulator, rng, forced_moves);
    out["move_assignments"] = move_summary.moves;
    out["move_log_probability"] = move_summary.log_probability;
    out["move_path_probability"] = std::exp(std::max(-700.0, move_summary.log_probability));
    out["state_after_move_phase"] = defense_sim_to_json(simulator);
    simulator.teleport_phase(rng);
    out["state_after_teleport_phase"] = defense_sim_to_json(simulator);
    simulator.decay_pheromone();
    simulator.manage_ants();
    if (!simulator.ignore_enemy_spawns) {
        simulator.spawn_enemy_ant(rng);
    }
    simulator.increase_ant_age();
    simulator.update_income();
    simulator.update_effects(rng);
    ++simulator.round_index;
    if (simulator.base_hp <= 0) {
        simulator.terminal = true;
    }
    out["state_end"] = defense_sim_to_json(simulator);
    return out;
}

MoveTraceSummary trace_future_threat_move_phase(rs::DefenseSimulator &simulator, int player) {
    MoveTraceSummary summary;
    simulator.ensure_move_cache(true);

    for (auto &ant : simulator.ants) {
        if (!ant.alive() || ant.too_old() || ant.is_frozen) {
            continue;
        }

        json row;
        row["ant_before"] = search_ant_to_json(ant);

        rs::MoveOption best{rs::kNoMove, ant.x, ant.y, 1.0, 0.0};
        bool has_best = false;
        bool filtered_attack_option = false;
        json options = json::array();
        const auto evaluated = simulator.move_options_for(ant);
        for (int index = 0; index < evaluated.size(); ++index) {
            const rs::MoveOption &option = evaluated[index];
            const bool attacks_tower = ls::future_move_option_attacks_tower(simulator, option);
            options.push_back(json{
                {"direction", option.direction},
                {"nx", option.nx},
                {"ny", option.ny},
                {"probability", option.probability},
                {"danger", option.danger},
                {"attacks_tower", attacks_tower},
                {"future_allowed", !attacks_tower},
            });
            if (attacks_tower) {
                filtered_attack_option = true;
                continue;
            }
            if (ls::future_move_option_better(option, best, has_best, player)) {
                best = option;
                has_best = true;
            }
        }

        const rs::MoveOption chosen =
            has_best ? best : rs::MoveOption{rs::kNoMove, ant.x, ant.y, 1.0, 0.0};
        simulator.record_move_annotation_for_direction(ant, chosen.direction);
        if (chosen.direction == rs::kNoMove) {
            ant.last_move = rs::kNoMove;
        } else {
            ant.x = chosen.nx;
            ant.y = chosen.ny;
            ant.last_move = chosen.direction;
            rs::mark_ant_trail(ant, ant.x, ant.y);
        }

        row["choice_source"] = has_best ? "future_best_non_attack" : "future_no_non_attack";
        row["chosen_direction"] = chosen.direction;
        row["chosen_probability"] = chosen.probability;
        row["options"] = options;
        row["filtered_attack_option"] = filtered_attack_option;
        row["attacked_tower"] = false;
        row["attacked_tower_id"] = -1;
        row["ant_after"] = search_ant_to_json(ant);
        summary.moves.push_back(row);
        summary.log_probability += std::log(std::max(chosen.probability, 1e-12));
    }

    return summary;
}

json simulate_future_threat_traced_round(rs::DefenseSimulator &simulator, int player, rs::FastRng &rng) {
    json out;
    out["state_start"] = defense_sim_to_json(simulator);
    if (simulator.terminal) {
        out["state_after_tower_phase"] = defense_sim_to_json(simulator);
        out["move_assignments"] = json::array();
        out["move_log_probability"] = 0.0;
        out["move_path_probability"] = 1.0;
        out["state_after_move_phase"] = defense_sim_to_json(simulator);
        out["state_after_teleport_phase"] = defense_sim_to_json(simulator);
        out["state_end"] = defense_sim_to_json(simulator);
        return out;
    }

    simulator.tower_attack_phase(rng);
    out["state_after_tower_phase"] = defense_sim_to_json(simulator);
    const MoveTraceSummary move_summary = trace_future_threat_move_phase(simulator, player);
    out["move_assignments"] = move_summary.moves;
    out["move_log_probability"] = move_summary.log_probability;
    out["move_path_probability"] = std::exp(std::max(-700.0, move_summary.log_probability));
    out["state_after_move_phase"] = defense_sim_to_json(simulator);
    if (v4_lure_config().future_threat_apply_teleport) {
        simulator.teleport_phase(rng);
    }
    out["future_teleport_applied"] = v4_lure_config().future_threat_apply_teleport;
    out["state_after_teleport_phase"] = defense_sim_to_json(simulator);
    simulator.decay_pheromone();
    simulator.manage_ants();
    simulator.increase_ant_age();
    if (v4_lure_config().future_threat_drift_effects) {
        simulator.update_effects(rng);
    } else {
        ls::future_decay_effects_no_drift(simulator);
    }
    ++simulator.round_index;
    if (simulator.base_hp <= 0) {
        simulator.terminal = true;
    }
    out["state_end"] = defense_sim_to_json(simulator);
    return out;
}

json future_threat_trace_rounds(const rs::DefenseSimulator &terminal_simulator, int player) {
    json out;
    out["enabled"] = v4_lure_config().future_threat_eval_enabled;
    out["horizon"] = v4_lure_config().future_threat_horizon;
    out["rounds"] = json::array();
    if (!v4_lure_config().future_threat_eval_enabled || v4_lure_config().future_threat_horizon <= 0) {
        return out;
    }

    rs::DefenseSimulator projected = terminal_simulator.clone();
    const int start_base_hp = projected.base_hp;
    out["start_base_hp"] = start_base_hp;
    rs::FastRng rng(ls::future_threat_seed(projected, player));
    for (int step = 0; step < v4_lure_config().future_threat_horizon && !projected.terminal; ++step) {
        json row;
        row["phase"] = "future_threat";
        row["step"] = step;
        row["applied_operations_pretty"] = "FUTURE-THREAT";
        row["applied_operations"] = json::array();
        row["trace"] = simulate_future_threat_traced_round(projected, player, rng);
        out["rounds"].push_back(row);
    }
    out["end_base_hp"] = projected.base_hp;
    out["base_damage"] = std::max(0, start_base_hp - projected.base_hp);
    out["state_end"] = defense_sim_to_json(projected);
    return out;
}

json plan_sample_trace(
    const PublicState &state,
    const NativeSimulator *native,
    int player,
    std::uint64_t serial,
    const EvaluatedPlanWithIndex &selected,
    int rollout_index,
    int sample_count,
    const ls::UcbRolloutRecord *ucb_sample = nullptr) {
    rs::DefenseSimulator root = rs::make_defense_simulator(state, native, player);
    root.ignore_enemy_spawns = true;

    rs::DefenseSimulator forced_root = root.clone();
    if (!selected.plan.ops.empty() && !ls::apply_operations(forced_root, selected.plan.ops)) {
        throw std::runtime_error("failed to apply selected plan for rollout schedule");
    }
    const int effective_sample_count = ucb_sample != nullptr
                                           ? std::max(1, ucb_sample->batch_size)
                                           : std::max(1, sample_count);
    const std::uint64_t assignment_seed = ucb_sample != nullptr
                                              ? ucb_sample->assignment_seed
                                              : ls::plan_rollout_assignment_seed(
                                                    state.seed,
                                                    serial,
                                                    selected.root_index,
                                                    selected.plan.horizon,
                                                    effective_sample_count);
    ls::RolloutForcedPlan forced_plan;
    if (ucb_sample != nullptr) {
        forced_plan.samples.push_back(ucb_sample->forced_sample);
        forced_plan.selected_ant_count = ucb_sample->forced_sample.forced_moves.size();
    } else {
        forced_plan = ls::build_first_round_rollout_plan(forced_root, player, effective_sample_count, assignment_seed);
    }
    const int forced_rollout_index = ucb_sample != nullptr ? 0 : rollout_index;
    const auto *first_round_forced_moves =
        forced_rollout_index >= 0 && forced_rollout_index < static_cast<int>(forced_plan.samples.size())
            ? &forced_plan.samples[static_cast<std::size_t>(forced_rollout_index)].forced_moves
            : nullptr;
    const double rollout_weight_probability =
        forced_rollout_index >= 0 && forced_rollout_index < static_cast<int>(forced_plan.samples.size())
            ? forced_plan.samples[static_cast<std::size_t>(forced_rollout_index)].probability
            : 1.0;

    rs::DefenseSimulator simulator = root.clone();
    rs::DefenseSimulator control = root.clone();
    const bool c1_transition_phase = ls::c1_transition_phase_from_action_start(root);
    double root_c1_bonus = 0.0;
    if (!selected.plan.ops.empty()) {
        if (!ls::apply_operations(simulator, selected.plan.ops)) {
            throw std::runtime_error("failed to apply selected plan");
        }
        if (selected.plan.has_lightning) {
            ls::apply_operations(control, ls::strip_lightning_operations(selected.plan.ops));
        }
    }
    root_c1_bonus = ls::c1_root_bonus_for_plan(simulator, player, selected.plan.followup, c1_transition_phase);

    const std::uint64_t seed = ucb_sample != nullptr
                                   ? ucb_sample->rollout_seed
                                   : plan_rollout_seed(state, serial, selected.root_index, rollout_index, selected.plan.horizon);
    rs::FastRng rng(seed);
    json rounds = json::array();

    double cumulative_log_probability = 0.0;
    bool lightning_bonus_computed = false;
    double lightning_bonus_raw = 0.0;
    double lightning_bonus_score = 0.0;
    double reactive_penalty = 0.0;
    double mid_reactive_penalty = 0.0;
    ls::EvalBreakdown mid_eval;
    bool has_mid_eval = false;
    const int mid_horizon = std::max(0, std::min(selected.plan.horizon, v4_lure_config().mid_eval_horizon));
    auto capture_mid_eval = [&](int simulated_rounds) {
        if (!has_mid_eval && simulated_rounds >= mid_horizon) {
            mid_eval = ls::evaluate_terminal(simulator, player);
            mid_reactive_penalty = reactive_penalty;
            has_mid_eval = true;
        }
    };

    int step = 0;
    while (step < selected.plan.horizon && !simulator.terminal) {
        json row;
        if (step == 0) {
            row["phase"] = "root";
            row["applied_operations_pretty"] = ls::pretty_ops_text(state, player, selected.plan.ops);
        } else if (ls::followup_has_turn(selected.plan.followup, step)) {
            const auto followup_ops = ls::resolve_followup_operations(simulator, player, selected.plan.followup, step);
            ls::apply_operations(simulator, followup_ops);
            row["phase"] = "followup";
            row["applied_operations_pretty"] = ls::pretty_ops_text(state, player, followup_ops);
            row["applied_operations"] = json::array();
            for (const auto &operation : followup_ops) {
                row["applied_operations"].push_back(operation_to_json(operation));
            }
        } else {
            std::vector<Operation> reactive_ops;
            if (const rs::SearchTower *forced = ls::forced_reactive_sell_target(simulator, player); forced != nullptr) {
                const Operation downgrade(OperationType::DowngradeTower, forced->tower_id);
                const double penalty = ls::downgrade_operation_penalty(simulator, downgrade);
                if (simulator.apply_operation(downgrade)) {
                    reactive_ops.push_back(downgrade);
                    reactive_penalty += penalty;
                }
            }
            row["phase"] = "reactive";
            row["applied_operations_pretty"] = ls::pretty_ops_text(state, player, reactive_ops);
            row["applied_operations"] = json::array();
            for (const auto &operation : reactive_ops) {
                row["applied_operations"].push_back(operation_to_json(operation));
            }
        }

        if (step == 0) {
            row["applied_operations"] = json::array();
            for (const auto &operation : selected.plan.ops) {
                row["applied_operations"].push_back(operation_to_json(operation));
            }
        }

        const json traced = simulate_traced_round(simulator, rng, step == 0 ? first_round_forced_moves : nullptr);
        row["step"] = step;
        row["trace"] = traced;
        cumulative_log_probability += traced.value("move_log_probability", 0.0);
        rounds.push_back(row);
        capture_mid_eval(step + 1);

        if (selected.plan.has_lightning && !lightning_bonus_computed) {
            rs::FastRng control_rng(seed);
            if (first_round_forced_moves != nullptr) {
                control.simulate_round(control_rng, *first_round_forced_moves);
            } else {
                control.simulate_round(control_rng);
            }
            lightning_bonus_raw =
                ls::lightning_counterfactual_bonus(simulator, control) + selected.plan.lightning_static_bonus;
            lightning_bonus_score = lightning_bonus_raw;
            lightning_bonus_computed = true;
        }
        ++step;
    }

    const ls::EvalBreakdown final_terminal = ls::evaluate_terminal(simulator, player);
    if (!has_mid_eval) {
        mid_eval = final_terminal;
        mid_reactive_penalty = reactive_penalty;
    }
    ls::EvalBreakdown terminal =
        ls::combine_eval_breakdowns(mid_eval, final_terminal, v4_lure_config().mid_eval_weight);
    terminal.c1_bonus_raw = root_c1_bonus;
    terminal.c1_bonus_score = root_c1_bonus;
    terminal.total_score += root_c1_bonus;
    const double weighted_reactive_penalty =
        std::max(0.0, std::min(1.0, v4_lure_config().mid_eval_weight)) * mid_reactive_penalty +
        (1.0 - std::max(0.0, std::min(1.0, v4_lure_config().mid_eval_weight))) * reactive_penalty;
    json out;
    out["seed"] = seed;
    out["sample_index"] = rollout_index;
    out["sample_count"] = effective_sample_count;
    out["ucb_actual_sample"] = ucb_sample != nullptr;
    if (ucb_sample != nullptr) {
        out["global_sample_index"] = ucb_sample->global_sample_index;
        out["batch_index"] = ucb_sample->batch_index;
        out["batch_local_index"] = ucb_sample->batch_local_index;
        out["batch_size"] = ucb_sample->batch_size;
        out["assignment_serial"] = ucb_sample->assignment_serial;
        out["assignment_seed"] = ucb_sample->assignment_seed;
    }
    out["path_log_probability"] = cumulative_log_probability;
    out["path_probability"] = std::exp(std::max(-700.0, cumulative_log_probability));
    out["rollout_weight_probability"] = rollout_weight_probability;
    out["forced_selected_ant_count"] = forced_plan.selected_ant_count;
    out["uniform_weight"] = 1.0;
    out["importance_weight"] = rollout_weight_probability;
    out["rounds"] = rounds;
    out["terminal"] = eval_breakdown_to_json(terminal);
    out["mid_terminal"] = eval_breakdown_to_json(mid_eval);
    out["final_terminal"] = eval_breakdown_to_json(final_terminal);
    out["future_trace"] = future_threat_trace_rounds(simulator, player);
    out["future_rounds"] = out["future_trace"]["rounds"];
    out["root_c1_bonus"] = root_c1_bonus;
    out["lightning_bonus_raw"] = lightning_bonus_raw;
    out["lightning_bonus_score"] = lightning_bonus_score;
    out["reactive_operation_penalty"] = weighted_reactive_penalty;
    out["total_score"] = terminal.total_score + lightning_bonus_score - weighted_reactive_penalty;
    out["state_final"] = defense_sim_to_json(simulator);
    return out;
}

json inspect_round_request(const json &request) {
    const std::string replay_path = request.at("replay_path").get<std::string>();
    const int round = request.at("round").get<int>();
    const int player = request.value("player", 0);

    ReplayRoundStart start = load_replay_round_start(replay_path, round);
    const std::uint64_t serial = request.value("serial", rollout_serial_for_round(round));
    ls::UcbEvaluationTrace ucb_trace;
    const auto evaluated = evaluate_root_plans(start.public_state, &start.native, player, serial, &ucb_trace);

    rs::DefenseSimulator defense_root = rs::make_defense_simulator(start.public_state, &start.native, player);
    defense_root.ignore_enemy_spawns = true;
    const ls::RootPlanSet root_plans = ls::generate_root_plans(start.public_state, &defense_root, player);

    json out;
    out["mode"] = "round_summary";
    out["replay_path"] = replay_path;
    out["round"] = round;
    out["player"] = player;
    out["seed"] = start.seed;
    out["serial"] = serial;
    out["strategy_params"] = v4_tuning_to_json();
    out["ucb"] = {
        {"target_total", ucb_trace.target_total},
        {"total_samples", ucb_trace.total_samples},
        {"lightning_target_total", ucb_trace.lightning_target_total},
        {"action_normal_arm_count", ucb_trace.action_normal_arm_count},
        {"action_probe_samples", ucb_trace.action_probe_samples},
        {"action_probe_elapsed_us", ucb_trace.action_probe_elapsed_us},
        {"action_estimated_us_per_sample", ucb_trace.action_estimated_us_per_sample},
        {"action_remaining_target_ms", ucb_trace.action_remaining_target_ms},
        {"action_effective_base_total_rollouts", ucb_trace.action_effective_base_total_rollouts},
        {"action_effective_target_total_rollouts", ucb_trace.action_effective_target_total_rollouts},
        {"action_normal_batch_size", ucb_trace.action_normal_batch_size},
        {"action_normal_guaranteed_total", ucb_trace.action_normal_guaranteed_total},
        {"total_elapsed_us", ucb_trace.total_elapsed_us},
        {"simulator_profile", {
            {"rounds", ucb_trace.simulator_profile.rounds},
            {"tower_attack_ns", ucb_trace.simulator_profile.tower_attack_ns},
            {"move_ns", ucb_trace.simulator_profile.move_ns},
            {"move_cache_ns", ucb_trace.simulator_profile.move_cache_ns},
            {"move_cache_static_ns", ucb_trace.simulator_profile.move_cache_static_ns},
            {"move_cache_dynamic_ns", ucb_trace.simulator_profile.move_cache_dynamic_ns},
            {"move_cache_weight_ns", ucb_trace.simulator_profile.move_cache_weight_ns},
            {"move_cache_worker_path_ns", ucb_trace.simulator_profile.move_cache_worker_path_ns},
            {"move_cache_tower_path_ns", ucb_trace.simulator_profile.move_cache_tower_path_ns},
            {"move_cache_annotation_ns", ucb_trace.simulator_profile.move_cache_annotation_ns},
            {"move_cache_worker_path_calls", ucb_trace.simulator_profile.move_cache_worker_path_calls},
            {"move_cache_tower_path_calls", ucb_trace.simulator_profile.move_cache_tower_path_calls},
            {"move_cache_tower_path_skipped", ucb_trace.simulator_profile.move_cache_tower_path_skipped},
            {"reverse_path_cache_lookups", ucb_trace.simulator_profile.reverse_path_cache_lookups},
            {"reverse_path_cache_hits", ucb_trace.simulator_profile.reverse_path_cache_hits},
            {"reverse_path_cache_misses", ucb_trace.simulator_profile.reverse_path_cache_misses},
            {"reverse_path_cache_stores", ucb_trace.simulator_profile.reverse_path_cache_stores},
            {"move_sample_ns", ucb_trace.simulator_profile.move_sample_ns},
            {"move_random_ns", ucb_trace.simulator_profile.move_random_ns},
            {"move_resolve_ns", ucb_trace.simulator_profile.move_resolve_ns},
            {"teleport_ns", ucb_trace.simulator_profile.teleport_ns},
            {"pheromone_ns", ucb_trace.simulator_profile.pheromone_ns},
            {"manage_ns", ucb_trace.simulator_profile.manage_ns},
            {"spawn_ns", ucb_trace.simulator_profile.spawn_ns},
            {"age_ns", ucb_trace.simulator_profile.age_ns},
            {"income_ns", ucb_trace.simulator_profile.income_ns},
            {"effects_ns", ucb_trace.simulator_profile.effects_ns},
            {"move_sample_calls", ucb_trace.simulator_profile.move_sample_calls},
            {"move_random_calls", ucb_trace.simulator_profile.move_random_calls},
            {"move_resolve_calls", ucb_trace.simulator_profile.move_resolve_calls},
            {"move_cache_calls", ucb_trace.simulator_profile.move_cache_calls},
            {"move_cache_memo_key_ns", ucb_trace.simulator_profile.move_cache_memo_key_ns},
            {"move_cache_memo_lookup_ns", ucb_trace.simulator_profile.move_cache_memo_lookup_ns},
            {"move_cache_memo_restore_ns", ucb_trace.simulator_profile.move_cache_memo_restore_ns},
            {"move_cache_memo_store_ns", ucb_trace.simulator_profile.move_cache_memo_store_ns},
            {"move_cache_memo_lookups", ucb_trace.simulator_profile.move_cache_memo_lookups},
            {"move_cache_memo_hits", ucb_trace.simulator_profile.move_cache_memo_hits},
            {"move_cache_memo_misses", ucb_trace.simulator_profile.move_cache_memo_misses},
            {"move_cache_memo_stores", ucb_trace.simulator_profile.move_cache_memo_stores},
            {"static_risk_cache_lookups", ucb_trace.simulator_profile.static_risk_cache_lookups},
            {"static_risk_cache_hits", ucb_trace.simulator_profile.static_risk_cache_hits},
            {"static_risk_cache_misses", ucb_trace.simulator_profile.static_risk_cache_misses},
            {"static_risk_cache_stores", ucb_trace.simulator_profile.static_risk_cache_stores},
        }},
        {"reactive_profile", {
            {"forced_sell_calls", ucb_trace.reactive_profile.forced_sell_calls},
            {"forced_sell_elapsed_us", ucb_trace.reactive_profile.forced_sell_elapsed_us},
            {"forced_sell_candidate_towers", ucb_trace.reactive_profile.forced_sell_candidate_towers},
            {"tower_clear_calls", ucb_trace.reactive_profile.tower_clear_calls},
            {"tower_clear_elapsed_us", ucb_trace.reactive_profile.tower_clear_elapsed_us},
            {"tower_clear_projected_calls", ucb_trace.reactive_profile.tower_clear_projected_calls},
            {"tower_clear_projected_elapsed_us", ucb_trace.reactive_profile.tower_clear_projected_elapsed_us},
            {"tower_clear_threatening_ants", ucb_trace.reactive_profile.tower_clear_threatening_ants},
        }},
    };
    out["start_state"] = public_round_state_to_json(start.native.to_public_round_state());
    out["defense_start_state"] = defense_sim_to_json(defense_root);
    out["root_plan_counts"] = {
        {"base_count", root_plans.base_count},
        {"lure_count", root_plans.lure_count},
        {"lightning_count", root_plans.lightning_count},
        {"raw_combo_count", root_plans.raw_combo_count},
        {"raw_plan_count", root_plans.raw_plan_count},
        {"unique_plan_count", static_cast<int>(root_plans.plans.size())},
    };
    out["action_category_counts"] = json::object();
    out["action_categories"] = json::array();
    std::unordered_map<std::string, std::pair<std::string, int>> category_counts;
    for (const auto &item : evaluated) {
        const auto [category, label] = action_category(item.plan);
        auto &entry = category_counts[category];
        entry.first = label;
        ++entry.second;
    }
    const std::vector<std::pair<std::string, std::string>> category_order = {
        {"all", "All"},
        {"hold", "Hold"},
        {"hold_followup", "Hold Followup"},
        {"double_build", "Double Build"},
        {"base", "Base"},
        {"base_followup", "Base Followup"},
        {"lure", "Lure"},
        {"lure_sell_base", "Lure Sell + Base"},
        {"base_lure", "Base + Lure"},
        {"lightning", "Lightning"},
        {"recycle_lightning", "Recycle + Lightning"},
        {"followup", "Followup"},
        {"other", "Other"},
    };
    out["action_category_counts"]["all"] = static_cast<int>(evaluated.size());
    out["action_categories"].push_back({
        {"key", "all"},
        {"label", "All"},
        {"count", static_cast<int>(evaluated.size())},
    });
    for (const auto &[key, label] : category_order) {
        if (key == "all") {
            continue;
        }
        const auto found = category_counts.find(key);
        const int count = found == category_counts.end() ? 0 : found->second.second;
        out["action_category_counts"][key] = count;
        if (count > 0) {
            out["action_categories"].push_back({
                {"key", key},
                {"label", label},
                {"count", count},
            });
        }
    }
    out["action_category_timing"] = json::object();
    struct TimingAgg {
        int actions = 0;
        int samples = 0;
        int batches = 0;
        double elapsed_us = 0.0;
    };
    std::unordered_map<std::string, TimingAgg> timing;
    for (const auto &item : evaluated) {
        const auto [category, label] = action_category(item.plan);
        auto &agg = timing[category];
        ++agg.actions;
        agg.samples += item.rollout_count;
        const auto batches = ucb_batches_for(ucb_trace, item.root_index);
        agg.batches += static_cast<int>(batches.size());
        for (const auto *batch : batches) {
            agg.elapsed_us += batch->elapsed_us;
        }
    }
    TimingAgg all_timing;
    for (const auto &[_, agg] : timing) {
        all_timing.actions += agg.actions;
        all_timing.samples += agg.samples;
        all_timing.batches += agg.batches;
        all_timing.elapsed_us += agg.elapsed_us;
    }
    auto timing_to_json = [](const TimingAgg &agg) {
        return json{
            {"actions", agg.actions},
            {"samples", agg.samples},
            {"batches", agg.batches},
            {"elapsed_us", agg.elapsed_us},
        };
    };
    out["action_category_timing"]["all"] = timing_to_json(all_timing);
    for (const auto &[key, _] : category_order) {
        if (key == "all") {
            continue;
        }
        out["action_category_timing"][key] = timing_to_json(timing[key]);
    }
    out["root_plan_sources"] = {
        {"base", json::array()},
        {"lure", json::array()},
        {"lightning_prep", json::array()},
        {"lightning_center", json::array()},
    };
    for (const auto &plan : root_plans.base_candidates) {
        out["root_plan_sources"]["base"].push_back(single_plan_to_json(start.public_state, player, plan));
    }
    for (const auto &plan : root_plans.lure_candidates) {
        out["root_plan_sources"]["lure"].push_back(single_plan_to_json(start.public_state, player, plan));
    }
    for (const auto &plan : root_plans.lightning_prep_candidates) {
        out["root_plan_sources"]["lightning_prep"].push_back(single_plan_to_json(start.public_state, player, plan));
    }
    for (const auto &plan : root_plans.lightning_center_candidates) {
        out["root_plan_sources"]["lightning_center"].push_back(single_plan_to_json(start.public_state, player, plan));
    }
    out["plans"] = json::array();
    for (const auto &item : evaluated) {
        out["plans"].push_back(evaluated_plan_to_json(start.public_state, player, item, &ucb_trace));
    }
    return out;
}

json inspect_alignment_check_request(const json &request) {
    const std::string replay_path = request.at("replay_path").get<std::string>();
    const int player = request.value("player", 0);
    const int horizon = request.value("horizon", v4_lure_config().long_eval_horizon);
    const bool include_ucb = request.value("include_ucb", true);

    std::vector<int> rounds;
    if (request.contains("rounds") && request.at("rounds").is_array()) {
        for (const auto &item : request.at("rounds")) {
            rounds.push_back(item.get<int>());
        }
    } else {
        rounds.push_back(request.at("round").get<int>());
    }

    json out;
    out["mode"] = "alignment_check";
    out["replay_path"] = replay_path;
    out["player"] = player;
    out["horizon"] = horizon;
    out["strategy_params"] = v4_tuning_to_json();
    out["rounds"] = json::array();

    for (const int round : rounds) {
        ReplayRoundStart start = load_replay_round_start(replay_path, round);
        ReplayRoundStart future = load_replay_round_start(replay_path, round + horizon);

        rs::DefenseSimulator root = rs::make_defense_simulator(start.public_state, &start.native, player);
        root.ignore_enemy_spawns = true;
        rs::DefenseSimulator actual_future = rs::make_defense_simulator(future.public_state, &future.native, player);
        actual_future.ignore_enemy_spawns = true;

        const PublicRoundState standard_start = start.native.to_public_round_state();
        const PublicRoundState standard_future = future.native.to_public_round_state();
        const json start_standard_summary = public_defense_projection_summary(standard_start, player);
        const json start_sim_summary = defense_projection_summary(root, player);
        const json future_standard_summary = public_defense_projection_summary(standard_future, player);
        const json future_sim_summary = defense_projection_summary(actual_future, player);
        const ls::EvalBreakdown root_eval = ls::evaluate_terminal(root, player);
        const ls::EvalBreakdown actual_future_eval = ls::evaluate_terminal(actual_future, player);

        json row;
        row["round"] = round;
        row["future_round"] = round + horizon;
        row["start_standard"] = start_standard_summary;
        row["start_simulator"] = start_sim_summary;
        row["start_delta_sim_minus_standard"] = projection_delta_summary(start_sim_summary, start_standard_summary);
        row["future_standard"] = future_standard_summary;
        row["future_simulator"] = future_sim_summary;
        row["future_delta_sim_minus_standard"] = projection_delta_summary(future_sim_summary, future_standard_summary);
        row["start_eval"] = eval_breakdown_to_json(root_eval);
        row["actual_future_eval"] = eval_breakdown_to_json(actual_future_eval);

        if (include_ucb) {
            const std::uint64_t serial = request.value("serial", rollout_serial_for_round(round));
            ls::UcbEvaluationTrace ucb_trace;
            const auto evaluated = evaluate_root_plans(start.public_state, &start.native, player, serial, &ucb_trace);
            row["ucb"] = {
                {"total_samples", ucb_trace.total_samples},
                {"total_elapsed_us", ucb_trace.total_elapsed_us},
                {"action_estimated_us_per_sample", ucb_trace.action_estimated_us_per_sample},
                {"move_cache_memo_hits", ucb_trace.simulator_profile.move_cache_memo_hits},
                {"move_cache_memo_stores", ucb_trace.simulator_profile.move_cache_memo_stores},
                {"move_cache_ns", ucb_trace.simulator_profile.move_cache_ns},
                {"move_cache_memo_key_ns", ucb_trace.simulator_profile.move_cache_memo_key_ns},
                {"move_cache_memo_lookup_ns", ucb_trace.simulator_profile.move_cache_memo_lookup_ns},
                {"move_cache_memo_restore_ns", ucb_trace.simulator_profile.move_cache_memo_restore_ns},
                {"move_cache_memo_store_ns", ucb_trace.simulator_profile.move_cache_memo_store_ns},
                {"move_cache_worker_path_ns", ucb_trace.simulator_profile.move_cache_worker_path_ns},
                {"move_cache_tower_path_ns", ucb_trace.simulator_profile.move_cache_tower_path_ns},
            };
            if (!evaluated.empty()) {
                const auto &best = evaluated.front();
                row["best_plan"] = {
                    {"key", best.plan.key},
                    {"name", best.plan.name},
                    {"pretty", ls::pretty_ops_text(start.public_state, player, best.plan.ops)},
                    {"horizon", best.plan.horizon},
                    {"rollout_count", best.rollout_count},
                    {"mean_score", best.mean_score},
                    {"mean_rollout_score", best.mean_rollout.total_score},
                };
                row["predicted_terminal"] = eval_breakdown_to_json(best.mean_rollout.terminal);
                row["predicted_minus_actual_future"] =
                    eval_delta_summary(best.mean_rollout.terminal, actual_future_eval);
            }
        }

        out["rounds"].push_back(row);
    }
    return out;
}

json inspect_rollout_alignment_batch_request(const json &request) {
    const std::string replay_path = request.at("replay_path").get<std::string>();
    const int player = request.value("player", 0);
    const int horizon = request.value("horizon", v4_lure_config().long_eval_horizon);
    const int samples = request.value("samples", 5000);
    const std::uint64_t seed_base = request.value("seed_base", 0x9e3779b97f4a7c15ULL);
    const bool simulator_limit_paths = request.value("simulator_limit_paths", true);
    const bool ignore_periodic_random_move = request.value("ignore_periodic_random_move", config().ignore_periodic_random_move);
    const int simulator_move_option_limit =
        request.value("simulator_move_option_limit", config().move_option_limit);
    if (horizon <= 0) {
        throw std::runtime_error("horizon must be positive");
    }
    if (samples <= 0) {
        throw std::runtime_error("samples must be positive");
    }

    std::vector<int> rounds;
    if (request.contains("rounds") && request.at("rounds").is_array()) {
        for (const auto &item : request.at("rounds")) {
            rounds.push_back(item.get<int>());
        }
    } else if (request.contains("round")) {
        rounds.push_back(request.at("round").get<int>());
    } else {
        rounds = {80, 101, 140, 180};
    }
    if (rounds.empty()) {
        throw std::runtime_error("at least one round is required");
    }

    json out;
    out["mode"] = "rollout_alignment_batch";
    out["replay_path"] = replay_path;
    out["player"] = player;
    out["horizon"] = horizon;
    out["samples"] = samples;
    out["seed_base"] = seed_base;
    out["simulator_limit_paths"] = simulator_limit_paths;
    out["simulator_move_option_limit"] = simulator_move_option_limit;
    out["ignore_periodic_random_move"] = ignore_periodic_random_move;
    out["strategy_params"] = v4_tuning_to_json();
    out["standard_logic"] = ignore_periodic_random_move
                                ? "NativeSimulator defense-only advance_round_without_base_spawns_no_teleport"
                                : "NativeSimulator defense-only advance_round_without_base_spawns";
    out["simulator_logic"] =
        "DefenseSimulator simulate_round with ignore_enemy_spawns=true and matching periodic teleport policy";
    out["teleport_policy"] =
        ignore_periodic_random_move ? "periodic random teleport skipped by both standard and simulator"
                                    : "round windows are rejected if they cross a periodic teleport turn";
    out["rounds"] = json::array();

    const std::vector<std::pair<std::string, double>> metric_template = rollout_metric_values(RolloutMetricSet{});
    for (const int round : rounds) {
        if (!ignore_periodic_random_move) {
            for (int step = 0; step < horizon; ++step) {
                if ((round + step + 1) % rs::kTeleportInterval == 0) {
                    throw std::runtime_error(
                        "round window crosses a teleport turn; choose rounds whose horizon avoids every 10th turn");
                }
            }
        }

        ReplayRoundStart start = load_replay_round_start(replay_path, round);
        rs::DefenseSimulator root = rs::make_defense_simulator(start.public_state, &start.native, player);
        root.ignore_enemy_spawns = true;
        root.limit_move_phase_paths_to_targets = simulator_limit_paths;
        root.move_option_limit = simulator_move_option_limit;
        const PublicRoundState standard_root_state =
            defense_only_round_state(start.native.to_public_round_state(), player);

        std::vector<std::pair<std::string, RunningStat>> standard_stats;
        std::vector<std::pair<std::string, RunningStat>> simulator_stats;
        std::vector<std::pair<std::string, RunningStat>> delta_stats;
        for (const auto &item : metric_template) {
            standard_stats.push_back({item.first, RunningStat{}});
            simulator_stats.push_back({item.first, RunningStat{}});
            delta_stats.push_back({item.first, RunningStat{}});
        }

        for (int sample = 0; sample < samples; ++sample) {
            const std::uint64_t sample_seed = rs::mix_seed(
                seed_base,
                static_cast<std::uint64_t>(round) * 0xd1b54a32d192ed03ULL +
                    static_cast<std::uint64_t>(sample) * 0x94d049bb133111ebULL +
                    static_cast<std::uint64_t>(player) * 0x2545f4914f6cdd1dULL);

            NativeSimulator standard = start.native.clone();
            standard.sync_public_round_state(standard_root_state);
            standard.reseed_future(sample_seed);
            for (int step = 0; step < horizon && !standard.terminal(); ++step) {
                if (ignore_periodic_random_move) {
                    standard.advance_round_without_base_spawns_no_teleport();
                } else {
                    standard.advance_round_without_base_spawns();
                }
            }

            rs::DefenseSimulator simulator = root.clone();
            simulator.ignore_periodic_random_move = ignore_periodic_random_move;
            rs::FastRng rng(sample_seed);
            for (int step = 0; step < horizon && !simulator.terminal; ++step) {
                simulator.simulate_round(rng);
            }

            const auto standard_values = rollout_metric_values(rollout_metrics_from_native(standard, player));
            const auto simulator_values = rollout_metric_values(rollout_metrics_from_defense(simulator, player));
            for (std::size_t index = 0; index < standard_values.size(); ++index) {
                const double standard_value = standard_values[index].second;
                const double simulator_value = simulator_values[index].second;
                standard_stats[index].second.add(standard_value);
                simulator_stats[index].second.add(simulator_value);
                delta_stats[index].second.add(simulator_value - standard_value);
            }
        }

        json row;
        row["round"] = round;
        row["future_round"] = round + horizon;
        row["start_standard"] = public_defense_projection_summary(standard_root_state, player);
        row["start_simulator"] = defense_projection_summary(root, player);
        row["start_delta_sim_minus_standard"] =
            projection_delta_summary(row["start_simulator"], row["start_standard"]);
        row["metrics"] = compare_metric_stats(standard_stats, simulator_stats, delta_stats);
        out["rounds"].push_back(std::move(row));
    }
    return out;
}

json inspect_rollout_entity_alignment_request(const json &request) {
    const std::string replay_path = request.at("replay_path").get<std::string>();
    const int round = request.at("round").get<int>();
    const int player = request.value("player", 0);
    const int horizon = request.value("horizon", v4_lure_config().long_eval_horizon);
    const int samples = request.value("samples", 5000);
    const std::uint64_t seed_base = request.value("seed_base", 0x9e3779b97f4a7c15ULL);
    const bool simulator_limit_paths = request.value("simulator_limit_paths", true);
    const bool ignore_periodic_random_move = request.value("ignore_periodic_random_move", config().ignore_periodic_random_move);
    const int simulator_move_option_limit =
        request.value("simulator_move_option_limit", config().move_option_limit);
    if (horizon <= 0) {
        throw std::runtime_error("horizon must be positive");
    }
    if (samples <= 0) {
        throw std::runtime_error("samples must be positive");
    }
    if (!ignore_periodic_random_move) {
        for (int step = 0; step < horizon; ++step) {
            if ((round + step + 1) % rs::kTeleportInterval == 0) {
                throw std::runtime_error(
                    "round window crosses a teleport turn; choose rounds whose horizon avoids every 10th turn");
            }
        }
    }

    ReplayRoundStart start = load_replay_round_start(replay_path, round);
    rs::DefenseSimulator root = rs::make_defense_simulator(start.public_state, &start.native, player);
    root.ignore_enemy_spawns = true;
    root.limit_move_phase_paths_to_targets = simulator_limit_paths;
    root.move_option_limit = simulator_move_option_limit;
    const PublicRoundState standard_root_state = defense_only_round_state(start.native.to_public_round_state(), player);

    std::map<int, EntityAlignmentStats> ant_stats;
    std::map<int, EntityAlignmentStats> tower_stats_by_id;
    for (const auto &ant : root.ants) {
        ant_stats.emplace(ant.ant_id, EntityAlignmentStats{});
    }
    for (const auto &tower : root.towers) {
        tower_stats_by_id.emplace(tower.tower_id, EntityAlignmentStats{});
    }
    std::map<std::string, int> standard_effect_positions;
    std::map<std::string, int> simulator_effect_positions;

    for (int sample = 0; sample < samples; ++sample) {
        const std::uint64_t sample_seed = rs::mix_seed(
            seed_base,
            static_cast<std::uint64_t>(round) * 0xd1b54a32d192ed03ULL +
                static_cast<std::uint64_t>(sample) * 0x94d049bb133111ebULL +
                static_cast<std::uint64_t>(player) * 0x2545f4914f6cdd1dULL);

        NativeSimulator standard = start.native.clone();
        standard.sync_public_round_state(standard_root_state);
        standard.reseed_future(sample_seed);
        for (int step = 0; step < horizon && !standard.terminal(); ++step) {
            if (ignore_periodic_random_move) {
                standard.advance_round_without_base_spawns_no_teleport();
            } else {
                standard.advance_round_without_base_spawns();
            }
        }

        rs::DefenseSimulator simulator = root.clone();
        simulator.ignore_periodic_random_move = ignore_periodic_random_move;
        rs::FastRng rng(sample_seed);
        for (int step = 0; step < horizon && !simulator.terminal; ++step) {
            simulator.simulate_round(rng);
        }

        PublicState standard_state(standard.seed(), standard.movement_policy(), standard.cold_handle_rule_illegal());
        standard_state.sync_public_round_state(standard.to_public_round_state());
        auto first_standard_effect_key = [&]() {
            for (const auto &effect : standard_state.active_effects) {
                if (effect.player == player && effect.weapon_type == SuperWeaponType::LightningStorm) {
                    return std::to_string(effect.x) + "," + std::to_string(effect.y) + ":" +
                           std::to_string(effect.remaining_turns);
                }
            }
            return std::string("none");
        };
        auto first_simulator_effect_key = [&]() {
            for (const auto &effect : simulator.my_effects) {
                if (effect.weapon_type == SuperWeaponType::LightningStorm && effect.active()) {
                    return std::to_string(effect.x) + "," + std::to_string(effect.y) + ":" +
                           std::to_string(effect.remaining_turns);
                }
            }
            return std::string("none");
        };
        ++standard_effect_positions[first_standard_effect_key()];
        ++simulator_effect_positions[first_simulator_effect_key()];
        auto standard_ant_for = [&](int ant_id) -> const Ant * {
            for (const auto &ant : standard_state.ants) {
                if (ant.ant_id == ant_id && ant.player == 1 - player && ant.is_alive()) {
                    return &ant;
                }
            }
            return nullptr;
        };
        auto standard_tower_for = [&](int tower_id) -> const Tower * {
            for (const auto &tower : standard_state.towers) {
                if (tower.tower_id == tower_id && tower.player == player && tower.hp > 0) {
                    return &tower;
                }
            }
            return nullptr;
        };
        auto simulator_ant_for = [&](int ant_id) -> const rs::SearchAnt * {
            const auto [base_x, base_y] = kPlayerBases[player];
            for (const auto &ant : simulator.ants) {
                if (ant.ant_id == ant_id && ant.alive() && !ant.too_old() &&
                    !(ant.x == base_x && ant.y == base_y)) {
                    return &ant;
                }
            }
            return nullptr;
        };
        auto simulator_tower_for = [&](int tower_id) -> const rs::SearchTower * {
            for (const auto &tower : simulator.towers) {
                if (tower.tower_id == tower_id && tower.alive()) {
                    return &tower;
                }
            }
            return nullptr;
        };

        for (auto &item : ant_stats) {
            const int ant_id = item.first;
            const Ant *standard_ant = standard_ant_for(ant_id);
            const rs::SearchAnt *simulator_ant = simulator_ant_for(ant_id);
            add_entity_sample(
                item.second,
                standard_ant != nullptr,
                standard_ant != nullptr ? standard_ant->x : -1,
                standard_ant != nullptr ? standard_ant->y : -1,
                standard_ant != nullptr ? standard_ant->hp : 0,
                simulator_ant != nullptr,
                simulator_ant != nullptr ? simulator_ant->x : -1,
                simulator_ant != nullptr ? simulator_ant->y : -1,
                simulator_ant != nullptr ? simulator_ant->hp : 0);
        }

        for (auto &item : tower_stats_by_id) {
            const int tower_id = item.first;
            const Tower *standard_tower = standard_tower_for(tower_id);
            const rs::SearchTower *simulator_tower = simulator_tower_for(tower_id);
            add_entity_sample(
                item.second,
                standard_tower != nullptr,
                standard_tower != nullptr ? standard_tower->x : -1,
                standard_tower != nullptr ? standard_tower->y : -1,
                standard_tower != nullptr ? standard_tower->hp : 0,
                simulator_tower != nullptr,
                simulator_tower != nullptr ? simulator_tower->x : -1,
                simulator_tower != nullptr ? simulator_tower->y : -1,
                simulator_tower != nullptr ? simulator_tower->hp : 0);
        }
    }

    json out;
    out["mode"] = "rollout_entity_alignment";
    out["replay_path"] = replay_path;
    out["round"] = round;
    out["player"] = player;
    out["horizon"] = horizon;
    out["future_round"] = round + horizon;
    out["samples"] = samples;
    out["seed_base"] = seed_base;
    out["simulator_limit_paths"] = simulator_limit_paths;
    out["simulator_move_option_limit"] = simulator_move_option_limit;
    out["ignore_periodic_random_move"] = ignore_periodic_random_move;
    out["ants"] = json::array();
    for (const auto &item : ant_stats) {
        json row = entity_alignment_stats_to_json(item.second, samples);
        row["id"] = item.first;
        out["ants"].push_back(std::move(row));
    }
    out["towers"] = json::array();
    for (const auto &item : tower_stats_by_id) {
        json row = entity_alignment_stats_to_json(item.second, samples);
        row["id"] = item.first;
        out["towers"].push_back(std::move(row));
    }
    std::map<std::string, int> effect_keys = standard_effect_positions;
    for (const auto &item : simulator_effect_positions) {
        effect_keys.emplace(item.first, 0);
    }
    struct EffectPositionDelta {
        std::string key;
        int standard_count = 0;
        int simulator_count = 0;
        int delta = 0;
    };
    std::vector<EffectPositionDelta> effect_deltas;
    effect_deltas.reserve(effect_keys.size());
    for (const auto &item : effect_keys) {
        const int standard_count =
            standard_effect_positions.count(item.first) ? standard_effect_positions.at(item.first) : 0;
        const int simulator_count =
            simulator_effect_positions.count(item.first) ? simulator_effect_positions.at(item.first) : 0;
        effect_deltas.push_back(EffectPositionDelta{item.first, standard_count, simulator_count, simulator_count - standard_count});
    }
    std::sort(effect_deltas.begin(), effect_deltas.end(), [](const EffectPositionDelta &lhs, const EffectPositionDelta &rhs) {
        const int lhs_abs = std::abs(lhs.delta);
        const int rhs_abs = std::abs(rhs.delta);
        if (lhs_abs != rhs_abs) {
            return lhs_abs > rhs_abs;
        }
        return lhs.key < rhs.key;
    });
    out["my_lightning_position_deltas"] = json::array();
    const int effect_limit = std::min<int>(16, effect_deltas.size());
    for (int index = 0; index < effect_limit; ++index) {
        const auto &item = effect_deltas[index];
        out["my_lightning_position_deltas"].push_back({
            {"position", item.key},
            {"standard_count", item.standard_count},
            {"simulator_count", item.simulator_count},
            {"delta_count", item.delta},
            {"standard_rate", samples > 0 ? static_cast<double>(item.standard_count) / static_cast<double>(samples) : 0.0},
            {"simulator_rate", samples > 0 ? static_cast<double>(item.simulator_count) / static_cast<double>(samples) : 0.0},
        });
    }
    return out;
}

json inspect_plan_rollouts_request(const json &request) {
    const std::string replay_path = request.at("replay_path").get<std::string>();
    const int round = request.at("round").get<int>();
    const int player = request.value("player", 0);
    const std::string plan_key = request.at("plan_key").get<std::string>();

    ReplayRoundStart start = load_replay_round_start(replay_path, round);
    const std::uint64_t serial = request.value("serial", rollout_serial_for_round(round));
    ls::UcbEvaluationTrace ucb_trace;
    const auto evaluated = evaluate_root_plans(start.public_state, &start.native, player, serial, &ucb_trace);
    const auto &selected = require_plan_by_key(evaluated, plan_key);

    json out;
    out["mode"] = "plan_rollouts";
    out["replay_path"] = replay_path;
    out["round"] = round;
    out["player"] = player;
    out["serial"] = serial;
    out["strategy_params"] = v4_tuning_to_json();
    out["plan"] = evaluated_plan_to_json(start.public_state, player, selected, &ucb_trace);
    out["samples"] = json::array();

    const auto ucb_samples = ucb_samples_for(ucb_trace, selected.root_index);
    const double uniform_weight = 1.0 / static_cast<double>(std::max<std::size_t>(1, ucb_samples.size()));
    std::vector<json> summaries;
    summaries.reserve(ucb_samples.size());
    double path_probability_sum = 0.0;
    for (const auto *sample : ucb_samples) {
        json summary;
        summary["sample_index"] = sample->arm_sample_index;
        summary["global_sample_index"] = sample->global_sample_index;
        summary["batch_index"] = sample->batch_index;
        summary["batch_local_index"] = sample->batch_local_index;
        summary["batch_size"] = sample->batch_size;
        summary["assignment_serial"] = sample->assignment_serial;
        summary["assignment_seed"] = sample->assignment_seed;
        summary["seed"] = sample->rollout_seed;
        summary["uniform_weight"] = uniform_weight;
        const double rollout_weight = sample->probability;
        summary["importance_weight"] = rollout_weight;
        summary["path_probability"] = rollout_weight;
        summary["path_log_probability"] = std::log(std::max(rollout_weight, 1e-12));
        summary["total_score"] = sample->evaluation.total_score;
        summary["lightning_bonus_raw"] = sample->evaluation.lightning_bonus_raw;
        summary["lightning_bonus_score"] = sample->evaluation.lightning_bonus_score;
        summary["terminal"] = eval_breakdown_to_json(sample->evaluation.terminal);
        summary["rollout_weight_probability"] = rollout_weight;
        summary["forced_selected_ant_count"] = sample->forced_sample.forced_moves.size();
        summary["first_round_phase"] = "ucb_actual";
        summary["first_round_ops_pretty"] = ls::pretty_ops_text(start.public_state, player, selected.plan.ops);
        summary["first_round_move_assignments"] = forced_sample_to_json(sample->forced_sample).at("forced_moves");
        summary["first_round_move_path_probability"] = rollout_weight;
        path_probability_sum += rollout_weight;
        summaries.push_back(std::move(summary));
    }
    for (auto &summary : summaries) {
        const double rollout_weight = summary.value("rollout_weight_probability", 0.0);
        summary["normalized_path_weight"] = path_probability_sum > 0.0 ? rollout_weight / path_probability_sum : uniform_weight;
        out["samples"].push_back(std::move(summary));
    }
    return out;
}

json inspect_plan_trace_request(const json &request) {
    const std::string replay_path = request.at("replay_path").get<std::string>();
    const int round = request.at("round").get<int>();
    const int player = request.value("player", 0);
    const std::string plan_key = request.at("plan_key").get<std::string>();
    const int sample_index = request.value("sample_index", 0);
    const int sample_count = request.value("sample_count", 50);
    const bool use_ucb_actual_sample = request.value("ucb_actual_sample", true);

    ReplayRoundStart start = load_replay_round_start(replay_path, round);
    const std::uint64_t serial = request.value("serial", rollout_serial_for_round(round));
    ls::UcbEvaluationTrace ucb_trace;
    const auto evaluated = evaluate_root_plans(start.public_state, &start.native, player, serial, &ucb_trace);
    const auto &selected = require_plan_by_key(evaluated, plan_key);
    const ls::UcbRolloutRecord *ucb_sample =
        use_ucb_actual_sample ? ucb_sample_for(ucb_trace, selected.root_index, sample_index) : nullptr;

    json out;
    out["mode"] = "plan_trace";
    out["replay_path"] = replay_path;
    out["round"] = round;
    out["player"] = player;
    out["serial"] = serial;
    out["strategy_params"] = v4_tuning_to_json();
    out["plan"] = evaluated_plan_to_json(start.public_state, player, selected, &ucb_trace);
    out["trace"] =
        plan_sample_trace(start.public_state, &start.native, player, serial, selected, sample_index, sample_count, ucb_sample);
    return out;
}

json inspect_move_debug_request(const json &request) {
    const std::string replay_path = request.at("replay_path").get<std::string>();
    const int round = request.at("round").get<int>();
    const int player = request.value("player", 0);
    const int simulator_move_option_limit =
        request.value("simulator_move_option_limit", config().move_option_limit);

    ReplayRoundStart start = load_replay_round_start(replay_path, round);
    const PublicRoundState standard_root_state =
        defense_only_round_state(start.native.to_public_round_state(), player);
    NativeSimulator standard = start.native.clone();
    standard.sync_public_round_state(standard_root_state);

    rs::DefenseSimulator simulator = rs::make_defense_simulator(start.public_state, &start.native, player);
    simulator.ignore_enemy_spawns = true;
    simulator.move_option_limit = simulator_move_option_limit;

    json native_rows = json::array();
    for (const auto &row : standard.move_debug_for_player(1 - player)) {
        native_rows.push_back(native_move_debug_to_json(row));
    }
    json simulator_rows = simulator_move_debug_to_json(simulator);

    json out;
    out["mode"] = "move_debug";
    out["replay_path"] = replay_path;
    out["round"] = round;
    out["player"] = player;
    out["simulator_move_option_limit"] = simulator_move_option_limit;
    out["start_delta_sim_minus_standard"] =
        projection_delta_summary(defense_projection_summary(simulator, player),
                                 public_defense_projection_summary(standard_root_state, player));
    out["native"] = native_rows;
    out["simulator"] = simulator_rows;
    out["deltas"] = move_probability_delta_json(simulator_rows, native_rows);
    return out;
}

} // namespace antgame::sdk::examples

int main() {
    using namespace antgame::sdk::examples;

    try {
        json request;
        std::cin >> request;
        const std::string mode = request.value("mode", std::string());
        apply_strategy_overrides(request);
        json response;
        if (mode == "round_summary") {
            response = inspect_round_request(request);
        } else if (mode == "alignment_check") {
            response = inspect_alignment_check_request(request);
        } else if (mode == "rollout_alignment_batch") {
            response = inspect_rollout_alignment_batch_request(request);
        } else if (mode == "rollout_entity_alignment") {
            response = inspect_rollout_entity_alignment_request(request);
        } else if (mode == "plan_rollouts") {
            response = inspect_plan_rollouts_request(request);
        } else if (mode == "plan_trace") {
            response = inspect_plan_trace_request(request);
        } else if (mode == "move_debug") {
            response = inspect_move_debug_request(request);
        } else {
            throw std::runtime_error("unsupported mode");
        }
        std::cout << response.dump() << '\n';
        return 0;
    } catch (const std::exception &exc) {
        json error;
        error["ok"] = false;
        error["error"] = exc.what();
        std::cout << error.dump() << '\n';
        return 1;
    }
}
