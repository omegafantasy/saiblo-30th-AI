#pragma once

#include <array>
#include <utility>

namespace antgame::sdk {

enum PositionCode : int {
    BASE = 0,
    C1 = 1,
    C2 = 2,
    L1 = 3,
    C3 = 4,
    R1 = 5,
    L2 = 6,
    L3 = 7,
    R3 = 8,
    R2 = 9,
    LL1 = 10,
    LL3 = 11,
    M2 = 12,
    M3 = 13,
    RR1 = 14,
    RR3 = 15,
    LL2 = 16,
    ML1 = 17,
    ML2 = 18,
    M1 = 19,
    M4 = 20,
    MR2 = 21,
    MR1 = 22,
    RR2 = 23,
    FL1 = 24,
    FL2 = 25,
    FR2 = 26,
    FR1 = 27,
    FL3 = 28,
    F2 = 29,
    F3 = 30,
    FR3 = 31,
    F1 = 32,
    F4 = 33,
    STORM = 34,
};

inline constexpr int kPositionCodeCount = 35;

inline constexpr std::array<std::array<std::pair<int, int>, kPositionCodeCount>, 2> kOldAiPositions = {{
    {{{2, 9},  {4, 9},  {5, 9},  {5, 7},  {6, 9},  {5, 11}, {5, 6},  {6, 7},  {6, 11},
      {5, 12}, {4, 3},  {5, 3},  {7, 8},  {7, 10}, {4, 15}, {5, 15}, {4, 2},  {6, 4},
      {7, 5},  {8, 7},  {8, 11}, {7, 13}, {6, 14}, {4, 16}, {6, 1},  {6, 2},  {6, 16},
      {6, 17}, {7, 1},  {8, 4},  {8, 14}, {7, 17}, {8, 2},  {8, 16}, {3, 9}}},
    {{{16, 9}, {14, 9}, {13, 9}, {13, 7}, {12, 9}, {13, 11}, {12, 6}, {12, 7}, {12, 11},
      {12, 12}, {14, 3}, {13, 3}, {10, 8}, {10, 10}, {14, 15}, {13, 15}, {13, 2}, {11, 4},
      {11, 5}, {10, 7}, {10, 11}, {11, 13}, {11, 14}, {13, 16}, {12, 1}, {11, 2}, {11, 16},
      {12, 17}, {11, 1}, {9, 4},  {9, 14}, {11, 17}, {9, 2},  {9, 16}, {15, 9}}},
}};

inline constexpr const std::array<std::pair<int, int>, kPositionCodeCount> &old_ai_positions(int player) {
    return kOldAiPositions[player < 0 ? 0 : (player > 1 ? 1 : player)];
}

inline constexpr std::pair<int, int> old_ai_position(int player, int code) {
    return old_ai_positions(player)[code];
}

inline constexpr int old_ai_position_code_at(int player, int x, int y) {
    const auto &slots = old_ai_positions(player);
    for (int code = 0; code < kPositionCodeCount; ++code) {
        if (slots[code].first == x && slots[code].second == y) {
            return code;
        }
    }
    return -1;
}

inline constexpr const char *position_code_name(int code) {
    switch (code) {
    case BASE:
        return "BASE";
    case C1:
        return "C1";
    case C2:
        return "C2";
    case L1:
        return "L1";
    case C3:
        return "C3";
    case R1:
        return "R1";
    case L2:
        return "L2";
    case L3:
        return "L3";
    case R3:
        return "R3";
    case R2:
        return "R2";
    case LL1:
        return "LL1";
    case LL3:
        return "LL3";
    case M2:
        return "M2";
    case M3:
        return "M3";
    case RR1:
        return "RR1";
    case RR3:
        return "RR3";
    case LL2:
        return "LL2";
    case ML1:
        return "ML1";
    case ML2:
        return "ML2";
    case M1:
        return "M1";
    case M4:
        return "M4";
    case MR2:
        return "MR2";
    case MR1:
        return "MR1";
    case RR2:
        return "RR2";
    case FL1:
        return "FL1";
    case FL2:
        return "FL2";
    case FR2:
        return "FR2";
    case FR1:
        return "FR1";
    case FL3:
        return "FL3";
    case F2:
        return "F2";
    case F3:
        return "F3";
    case FR3:
        return "FR3";
    case F1:
        return "F1";
    case F4:
        return "F4";
    case STORM:
        return "STORM";
    default:
        return "UNKNOWN";
    }
}

inline constexpr bool is_core_build_position(int code) {
    switch (code) {
    case C1:
    case C2:
    case C3:
    case L1:
    case L2:
    case L3:
    case R1:
    case R2:
    case R3:
        return true;
    default:
        return false;
    }
}

inline constexpr double centerline_slot_weight(int code) {
    switch (code) {
    case C1:
        return 1.1;
    case C2:
        return 1.15;
    case C3:
        return 1.2;
    default:
        return 1.0;
    }
}

} // namespace antgame::sdk
