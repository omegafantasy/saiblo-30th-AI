#pragma once

#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "antgame_sdk/sdk.hpp"

namespace antgame::sdk {

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
    const std::string &movement_policy() const;
    uint64_t seed() const;
    bool cold_handle_rule_illegal() const;

    PublicRoundState to_public_round_state() const;
    std::vector<Operation> apply_operation_list(int player, const std::vector<Operation> &operations);
    ResolveResult advance_round();
    ResolveResult resolve_turn(const std::vector<Operation> &ops0, const std::vector<Operation> &ops1);
    void sync_public_round_state(const PublicRoundState &state);

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;

    explicit NativeSimulator(std::unique_ptr<Impl> impl);
};

} // namespace antgame::sdk
