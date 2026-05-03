#pragma once

#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "antgame_sdk/sdk.hpp"

namespace antgame::sdk {

struct NativeAntHiddenState {
    int ant_id = -1;
    int last_move = -1;
    int shield = 0;
    bool defend = false;
    bool evasion_control_free_on_break = false;
    bool is_frozen = false;
    int behavior_rounds = 0;
    int behavior_expiry = 0;
    int target_x = -1;
    int target_y = -1;
    bool has_pending_behavior = false;
    AntBehavior pending_behavior = AntBehavior::Default;
    std::array<std::uint64_t, kTrailMaskWords> trail_mask{};
};

struct NativeMoveOptionDebug {
    int direction = -1;
    int x = -1;
    int y = -1;
    double score = 0.0;
    double raw_score = 0.0;
    double probability = 0.0;
    int annotated_x = -1;
    int annotated_y = -1;
    int annotated_tower_id = -1;
};

struct NativeAntMoveDebug {
    int ant_id = -1;
    int x = -1;
    int y = -1;
    int hp = 0;
    int last_move = -1;
    AntBehavior behavior = AntBehavior::Default;
    AntKind kind = AntKind::Worker;
    std::vector<NativeMoveOptionDebug> options;
};

struct ResolveResult {
    bool terminal = false;
    int winner = -1;
    std::vector<Operation> illegal0;
    std::vector<Operation> illegal1;
};

class NativeSimulator {
  public:
    explicit NativeSimulator(
        uint64_t seed = 0,
        std::string movement_policy = "enhanced",
        bool cold_handle_rule_illegal = false);
    ~NativeSimulator();

    NativeSimulator(NativeSimulator &&) noexcept;
    NativeSimulator &operator=(NativeSimulator &&) noexcept;

    NativeSimulator(const NativeSimulator &) = delete;
    NativeSimulator &operator=(const NativeSimulator &) = delete;

    NativeSimulator clone() const;

    int round_index() const;
    std::array<int, 2> coins() const;
    std::array<int, 2> old_count() const;
    std::array<int, 2> die_count() const;
    std::array<int, 2> super_weapon_usage() const;
    std::array<int, 2> ai_time() const;
    std::array<std::array<int, 5>, 2> weapon_cooldowns() const;
    int next_ant_id() const;
    int next_tower_id() const;
    bool terminal() const;
    int winner() const;
    std::vector<NativeAntHiddenState> ant_hidden_states() const;
    std::vector<NativeAntMoveDebug> move_debug_for_player(int player) const;
    std::array<std::array<double, kMapSize>, kMapSize> pheromone_for_player(int player) const;
    const std::string &movement_policy() const;
    uint64_t seed() const;
    bool cold_handle_rule_illegal() const;

    PublicRoundState to_public_round_state() const;
    void reseed_future(uint64_t seed);
    std::vector<Operation> apply_operation_list(int player, const std::vector<Operation> &operations);
    ResolveResult advance_round();
    ResolveResult advance_round_without_base_spawns();
    ResolveResult advance_round_without_base_spawns_no_teleport();
    ResolveResult resolve_turn(const std::vector<Operation> &ops0, const std::vector<Operation> &ops1);
    void sync_public_round_state(const PublicRoundState &state);

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;

    explicit NativeSimulator(std::unique_ptr<Impl> impl);
};

} // namespace antgame::sdk
