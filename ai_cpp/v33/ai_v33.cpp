#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

#include "../../past_AIs/Generals-AI/include/json.hpp"

using json = nlohmann::json;

namespace {

constexpr int kRow = 15;
constexpr int kCol = 15;

constexpr int kDirs = 4;
const int kDx[kDirs] = {-1, 1, 0, 0};   // up, down, left, right
const int kDy[kDirs] = {0, 0, -1, 1};
const int kDirCode[kDirs] = {1, 2, 3, 4};

struct General {
    int id = -1;
    int player = -1;
    int type = 0;  // 1 main, 2 sub, 3 farmer
    int x = -1;
    int y = -1;
    int level_prod = 1;
    int level_def = 1;
    int level_mob = 1;
    std::array<int, 3> skill_rest{0, 0, 0};
    bool alive = true;
};

struct Weapon {
    int type = 0;  // 1 bomb, 2 enhance, 3 transmission, 4 timestop
    int player = -1;
    int x = -1;
    int y = -1;
    int rest = 0;
};

struct Cell {
    int owner = -1;
    int army = 0;
    int type = 0;  // 0 plain, 1 bog, 2 mountain
    bool has_general = false;
    int general_idx = -1;
    int general_player = -1;
    int general_type = 0;
    double general_def = 1.0;
};

struct State {
    int seat = 0;
    int round = 1;
    std::array<int, 2> coins{0, 0};
    std::array<std::array<int, 4>, 2> tech{{{1, 0, 0, 0}, {1, 0, 0, 0}}};
    std::array<std::array<Cell, kCol>, kRow> board{};
    std::vector<General> generals;
    std::vector<Weapon> weapons;

    int my_main_id = -1;
    int my_main_x = -1;
    int my_main_y = -1;
    int my_main_prod = 1;
    int my_main_def = 1;
    int my_main_mob = 1;

    int enemy_main_x = -1;
    int enemy_main_y = -1;
};

using Grid = std::array<std::array<double, kCol>, kRow>;

struct Candidate {
    bool ok = false;
    int sx = -1;
    int sy = -1;
    int dir = -1;
    int num = 0;
    double score = -1e100;
};

enum class StrategyMode {
    kDefense = 0,
    kBalanced = 1,
    kOffense = 2,
};

struct ModeSignals {
    StrategyMode mode = StrategyMode::kBalanced;
    double pressure_ratio = 0.0;
    double attack_signal = 0.0;
    double army_ratio = 1.0;
    double outer_defense = 0.0;
    double chain_pressure = 0.0;
    double advance_density = 0.0;
    double beam_like_prob = 0.0;
};

struct AntiBeamSignal {
    double chain_risk = 0.0;
    double ring_risk = 0.0;
    double pressure_risk = 0.0;
    double beam_like_prob = 0.0;
    double alert_raw = 0.0;
    double initiative_gate = 0.0;
    double alert_effective = 0.0;
};

int as_int(const json& v, int fallback = 0) {
    try {
        if (v.is_number_integer()) return v.get<int>();
        if (v.is_number_float()) return static_cast<int>(std::llround(v.get<double>()));
    } catch (...) {
    }
    return fallback;
}

bool parse_km(const std::string& line, int& seat, int& seed) {
    std::istringstream iss(line);
    int s = -1;
    int r = 0;
    if (!(iss >> s >> r)) return false;
    std::string tail;
    if (iss >> tail) return false;
    if (s != 0 && s != 1) return false;
    seat = s;
    seed = r;
    return true;
}

void send_payload(const std::string& payload) {
    const uint32_t len = static_cast<uint32_t>(payload.size());
    const unsigned char hdr[4] = {
        static_cast<unsigned char>((len >> 24) & 0xFFu),
        static_cast<unsigned char>((len >> 16) & 0xFFu),
        static_cast<unsigned char>((len >> 8) & 0xFFu),
        static_cast<unsigned char>(len & 0xFFu),
    };
    std::cout.write(reinterpret_cast<const char*>(hdr), 4);
    std::cout.write(payload.data(), static_cast<std::streamsize>(payload.size()));
    std::cout.flush();
}

std::string format_ops(const std::vector<std::vector<int>>& ops) {
    std::ostringstream oss;
    bool ended = false;
    for (const auto& op : ops) {
        if (op.empty()) continue;
        for (size_t i = 0; i < op.size(); ++i) {
            if (i) oss << ' ';
            oss << op[i];
        }
        oss << '\n';
        if (op[0] == 8) {
            ended = true;
            break;
        }
    }
    if (!ended) oss << "8\n";
    return oss.str();
}

bool in_bounds(int x, int y) {
    return x >= 0 && x < kRow && y >= 0 && y < kCol;
}

int manhattan(int x1, int y1, int x2, int y2) {
    return std::abs(x1 - x2) + std::abs(y1 - y2);
}

int move_budget_from_tier(int tier) {
    if (tier <= 1) return 2;
    if (tier == 2) return 3;
    return 5;
}

double decode_general_def(int type, int level_def) {
    if (type == 3) {
        // Farmer in replay: 1 -> 1.0, 2 -> 1.5, 3 -> 2.0, 4 -> 3.0
        if (level_def <= 1) return 1.0;
        if (level_def == 2) return 1.5;
        if (level_def == 3) return 2.0;
        return 3.0;
    }
    if (level_def <= 1) return 1.0;
    if (level_def == 2) return 2.0;
    return 3.0;
}

bool blocked_by_super_weapon(const State& st, int player, int x, int y) {
    for (const auto& w : st.weapons) {
        if (w.rest <= 0) continue;
        // transmission: own cell cannot act/move
        if (w.type == 3 && w.player == player && w.x == x && w.y == y) return true;
        // timestop: enemy 3x3 area cannot act/move
        if (w.type == 4 && w.player == (1 - player) && std::abs(w.x - x) <= 1 && std::abs(w.y - y) <= 1) return true;
    }
    return false;
}

double attack_multiplier(const State& st, int x, int y, int owner) {
    if (owner < 0) return 1.0;
    double atk = 1.0;
    for (const auto& g : st.generals) {
        if (!g.alive) continue;
        if (std::abs(g.x - x) > 2 || std::abs(g.y - y) > 2) continue;
        if (g.player == owner && g.skill_rest[0] > 0) atk *= 1.5;
        if (g.player >= 0 && g.player != owner && g.skill_rest[2] > 0) atk *= 0.75;
    }
    for (const auto& w : st.weapons) {
        if (w.rest <= 0) continue;
        if (w.type == 2 && w.player == owner && std::abs(w.x - x) <= 1 && std::abs(w.y - y) <= 1) {
            atk *= 3.0;
            break;
        }
    }
    return std::max(0.25, atk);
}

double defence_multiplier(const State& st, int x, int y, int owner) {
    double def = 1.0;
    if (owner >= 0) {
        for (const auto& g : st.generals) {
            if (!g.alive) continue;
            if (std::abs(g.x - x) > 2 || std::abs(g.y - y) > 2) continue;
            if (g.player == owner && g.skill_rest[1] > 0) def *= 1.5;
            if (g.player >= 0 && g.player != owner && g.skill_rest[2] > 0) def *= 0.75;
        }
    }

    const Cell& c = st.board[x][y];
    if (c.has_general) def *= std::max(1.0, c.general_def);

    if (owner >= 0) {
        for (const auto& w : st.weapons) {
            if (w.rest <= 0) continue;
            if (w.type == 2 && w.player == owner && std::abs(w.x - x) <= 1 && std::abs(w.y - y) <= 1) {
                def *= 3.0;
                break;
            }
        }
    }
    return std::max(0.25, def);
}

Grid compute_threat(const State& st, int enemy, int enemy_moves) {
    Grid threat{};
    for (int ex = 0; ex < kRow; ++ex) {
        for (int ey = 0; ey < kCol; ++ey) {
            const Cell& src = st.board[ex][ey];
            if (src.owner != enemy || src.army <= 0) continue;
            const double power = static_cast<double>(std::max(0, src.army - 1));
            for (int x = 0; x < kRow; ++x) {
                for (int y = 0; y < kCol; ++y) {
                    const int d = manhattan(ex, ey, x, y);
                    if (d == 0) {
                        threat[x][y] += static_cast<double>(src.army) * 0.2;
                        continue;
                    }
                    if (d > enemy_moves) continue;
                    threat[x][y] += power / static_cast<double>(d);
                }
            }
        }
    }
    return threat;
}

int count_owned_cells(const State& st, int player) {
    int cnt = 0;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            if (st.board[x][y].owner == player) ++cnt;
        }
    }
    return cnt;
}

int count_adj_mountains(const State& st, int player) {
    int cnt = 0;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            if (st.board[x][y].owner != player) continue;
            for (int d = 0; d < kDirs; ++d) {
                const int nx = x + kDx[d];
                const int ny = y + kDy[d];
                if (!in_bounds(nx, ny)) continue;
                if (st.board[nx][ny].type == 2) ++cnt;
            }
        }
    }
    return cnt;
}

bool adjacent_non_owned(const State& st, int x, int y, int player) {
    for (int d = 0; d < kDirs; ++d) {
        const int nx = x + kDx[d];
        const int ny = y + kDy[d];
        if (!in_bounds(nx, ny)) continue;
        if (st.board[nx][ny].owner != player) return true;
    }
    return false;
}

std::pair<int, int> locate_main_general(const State& st, int player) {
    for (const auto& g : st.generals) {
        if (!g.alive) continue;
        if (g.type != 1 || g.player != player) continue;
        if (in_bounds(g.x, g.y)) return {g.x, g.y};
    }
    int best_army = -1;
    int bx = -1;
    int by = -1;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            if (st.board[x][y].owner != player) continue;
            if (st.board[x][y].army > best_army) {
                best_army = st.board[x][y].army;
                bx = x;
                by = y;
            }
        }
    }
    return {bx, by};
}

int compute_main_safe_reserve(const State& st, int player, const Grid& threat_from_enemy) {
    const auto main_pos = locate_main_general(st, player);
    if (main_pos.first < 0 || main_pos.second < 0) return 3;
    const int x = main_pos.first;
    const int y = main_pos.second;
    const int army = st.board[x][y].army;
    int reserve = std::max(3, static_cast<int>(std::ceil(threat_from_enemy[x][y] * 0.55)));
    if (army <= 1) return 1;
    reserve = std::min(reserve, std::max(3, army - 1));
    return reserve;
}

double compute_main_pressure_ratio(const State& st, int player, int enemy_moves) {
    const auto my_main = locate_main_general(st, player);
    if (my_main.first < 0 || my_main.second < 0) return 0.0;
    const Grid threat = compute_threat(st, 1 - player, enemy_moves);
    const int main_army = std::max(1, st.board[my_main.first][my_main.second].army);
    return threat[my_main.first][my_main.second] / static_cast<double>(main_army);
}

double compute_army_ratio(const State& st, int player) {
    int my_army = 1;
    int enemy_army = 1;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner == player) my_army += c.army;
            else if (c.owner == (1 - player)) enemy_army += c.army;
        }
    }
    return static_cast<double>(my_army) / static_cast<double>(enemy_army);
}

double compute_attack_window_signal(const State& st, int player) {
    const auto enemy_main = locate_main_general(st, 1 - player);
    if (enemy_main.first < 0 || enemy_main.second < 0) return 0.0;
    const int ex = enemy_main.first;
    const int ey = enemy_main.second;
    const Cell& main_cell = st.board[ex][ey];
    if (main_cell.owner == player) return 120.0;

    double near_power = 0.0;
    int near_cells = 0;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner != player || c.army <= 1) continue;
            const int d = manhattan(x, y, ex, ey);
            if (d <= 2) {
                near_power += c.army * 1.25;
                near_cells += 1;
            } else if (d <= 4) {
                near_power += c.army * 0.55;
            }
        }
    }

    int ring_control = 0;
    for (int d = 0; d < kDirs; ++d) {
        const int nx = ex + kDx[d];
        const int ny = ey + kDy[d];
        if (!in_bounds(nx, ny)) continue;
        if (st.board[nx][ny].owner == player) ring_control += 1;
    }

    return near_power - main_cell.army * 1.35 + ring_control * 5.0 + near_cells * 1.2;
}

double compute_outer_ring_defense_score(const State& st, int player) {
    const auto my_main = locate_main_general(st, player);
    if (my_main.first < 0 || my_main.second < 0) return 0.0;
    const int mx = my_main.first;
    const int my = my_main.second;

    double friendly = 0.0;
    double hostile = 0.0;
    double gaps = 0.0;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            if (manhattan(x, y, mx, my) != 2) continue;
            const Cell& c = st.board[x][y];
            if (c.type == 2) {
                friendly += 1.6;
                continue;
            }
            if (c.owner == player) {
                friendly += c.army * 0.45;
                if (c.has_general && c.general_player == player) friendly += 4.0;
            } else if (c.owner == (1 - player)) {
                hostile += c.army * 0.55;
                if (c.has_general && c.general_player == (1 - player)) hostile += 5.0;
            } else {
                gaps += 1.0;
            }
        }
    }
    return friendly - hostile * 0.8 - gaps * 2.2;
}

double compute_enemy_chain_pressure_to_main(const State& st, int player) {
    const auto my_main = locate_main_general(st, player);
    if (my_main.first < 0 || my_main.second < 0) return 0.0;
    const int mx = my_main.first;
    const int my = my_main.second;
    const int enemy = 1 - player;

    double pressure = 0.0;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner != enemy || c.army <= 1) continue;
            const int d = manhattan(x, y, mx, my);
            if (d > 8) continue;

            double local = static_cast<double>(std::max(0, c.army - 1)) / static_cast<double>(d + 1);
            if (d <= 4) local *= 1.25;
            if (c.has_general && c.general_player == enemy) local *= 1.30;

            bool has_support_chain = false;
            for (int k = 0; k < kDirs; ++k) {
                const int nx = x + kDx[k];
                const int ny = y + kDy[k];
                if (!in_bounds(nx, ny)) continue;
                const Cell& n = st.board[nx][ny];
                if (n.owner == enemy && n.army > 1 && manhattan(nx, ny, mx, my) < d) {
                    has_support_chain = true;
                    break;
                }
            }
            if (has_support_chain) local *= 1.20;
            pressure += local;
        }
    }
    return pressure;
}

double compute_enemy_advance_density_to_main(const State& st, int player) {
    const auto my_main = locate_main_general(st, player);
    if (my_main.first < 0 || my_main.second < 0) return 0.0;
    const int mx = my_main.first;
    const int my = my_main.second;
    const int enemy = 1 - player;

    double weighted = 0.0;
    double norm = 0.0;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner != enemy || c.army <= 1) continue;
            const int d = manhattan(x, y, mx, my);
            if (d > 7) continue;

            const double dist_w = static_cast<double>(8 - d) / 8.0;
            double local = std::min(22.0, static_cast<double>(c.army)) / 22.0;
            if (d <= 4) local *= 1.20;
            if (c.has_general && c.general_player == enemy) local *= 1.25;

            bool linked = false;
            for (int k = 0; k < kDirs; ++k) {
                const int nx = x + kDx[k];
                const int ny = y + kDy[k];
                if (!in_bounds(nx, ny)) continue;
                const Cell& n = st.board[nx][ny];
                if (n.owner == enemy && n.army > 1 && manhattan(nx, ny, mx, my) < d) {
                    linked = true;
                    break;
                }
            }
            if (linked) local *= 1.18;

            weighted += local * dist_w;
            norm += dist_w;
        }
    }
    if (norm <= 1e-9) return 0.0;
    return std::clamp(weighted / std::max(1.6, norm * 0.86), 0.0, 1.0);
}

double estimate_beam_like_probability(
    double chain_pressure,
    double outer_defense,
    double pressure_ratio,
    double advance_density
) {
    const double chain_comp = std::clamp((chain_pressure - 12.0) / 7.0, 0.0, 1.0);
    const double ring_comp = std::clamp((8.2 - outer_defense) / 6.5, 0.0, 1.0);
    const double pressure_comp = std::clamp((pressure_ratio - 0.58) / 0.40, 0.0, 1.0);
    const double density_comp = std::clamp((advance_density - 0.20) / 0.65, 0.0, 1.0);
    return std::clamp(
        0.42 * chain_comp + 0.28 * density_comp + 0.18 * ring_comp + 0.12 * pressure_comp,
        0.0,
        1.0
    );
}

AntiBeamSignal compute_anti_beam_signal(
    double chain_pressure,
    double outer_defense,
    double pressure_ratio,
    double army_ratio,
    double attack_signal,
    double beam_like_prob = -1.0
) {
    AntiBeamSignal s;
    s.chain_risk = std::clamp((chain_pressure - 13.5) / 8.0, 0.0, 1.0);
    s.ring_risk = std::clamp((8.5 - outer_defense) / 6.0, 0.0, 1.0);
    s.pressure_risk = std::clamp((pressure_ratio - 0.62) / 0.40, 0.0, 1.0);

    s.alert_raw = std::clamp(
        (0.45 * s.chain_risk + 0.35 * s.ring_risk + 0.20 * s.pressure_risk) *
            (0.65 + 0.35 * std::max(s.chain_risk, s.ring_risk)),
        0.0,
        1.0
    );

    const auto smoothstep = [](double edge0, double edge1, double x) {
        if (edge1 <= edge0) return (x >= edge1) ? 1.0 : 0.0;
        const double t = std::clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0);
        return t * t * (3.0 - 2.0 * t);
    };
    const double attack_val = std::isfinite(attack_signal) ? attack_signal : 12.0;
    const double army_mid = smoothstep(1.08, 1.16, army_ratio);
    const double army_high = smoothstep(1.16, 1.26, army_ratio);
    const double attack_mid = smoothstep(14.0, 22.0, attack_val);
    const double attack_high = smoothstep(20.0, 30.0, attack_val);
    const double pressure_safe = 1.0 - smoothstep(0.72, 0.86, pressure_ratio);
    const double initiative_score = std::clamp(
        0.30 * army_mid + 0.30 * attack_mid + 0.25 * pressure_safe +
            0.15 * std::max(army_high, attack_high),
        0.0,
        1.0
    );
    const double mid_mix = smoothstep(0.34, 0.57, initiative_score);
    const double high_mix = smoothstep(0.70, 0.88, initiative_score);
    s.initiative_gate = 0.5 * mid_mix * (1.0 - high_mix) + high_mix;

    const double derived_beam_like =
        std::clamp(0.52 * s.chain_risk + 0.28 * s.ring_risk + 0.20 * s.pressure_risk, 0.0, 1.0);
    if (beam_like_prob >= 0.0) {
        s.beam_like_prob = std::clamp(0.55 * derived_beam_like + 0.45 * beam_like_prob, 0.0, 1.0);
    } else {
        s.beam_like_prob = derived_beam_like;
    }

    const double chain_block = std::clamp(1.0 - s.chain_risk * (0.82 + 0.14 * s.beam_like_prob), 0.0, 1.0);
    const double relax_cap = 0.10 + 0.16 * (1.0 - s.beam_like_prob);
    const double initiative_relax = 1.0 - relax_cap * s.initiative_gate * chain_block;
    const double emergency_pressure = std::clamp((pressure_ratio - 0.90) / 0.22, 0.0, 1.0);
    const double guarded_floor = s.alert_raw * (0.72 + 0.18 * s.beam_like_prob + 0.22 * emergency_pressure);
    s.alert_effective = std::clamp(s.alert_raw * initiative_relax + s.alert_raw * 0.20 * emergency_pressure, 0.0, 1.0);
    const double non_beam_relax = std::clamp((0.52 - s.beam_like_prob) / 0.52, 0.0, 1.0) *
                                  std::clamp((s.initiative_gate - 0.10) / 0.90, 0.0, 1.0) *
                                  (1.0 - emergency_pressure);
    s.alert_effective *= (1.0 - 0.12 * non_beam_relax);
    s.alert_effective = std::max(s.alert_effective, guarded_floor);
    const double conservative_floor = s.alert_raw * (0.60 + 0.28 * s.beam_like_prob + 0.12 * s.chain_risk);
    s.alert_effective = std::max(s.alert_effective, conservative_floor);
    return s;
}

ModeSignals analyze_strategy_mode(const State& st, int player, int enemy_moves) {
    ModeSignals sig;
    sig.pressure_ratio = compute_main_pressure_ratio(st, player, enemy_moves);
    sig.attack_signal = compute_attack_window_signal(st, player);
    sig.army_ratio = compute_army_ratio(st, player);
    sig.outer_defense = compute_outer_ring_defense_score(st, player);
    sig.chain_pressure = compute_enemy_chain_pressure_to_main(st, player);
    const double advance_density = compute_enemy_advance_density_to_main(st, player);
    sig.advance_density = advance_density;
    sig.beam_like_prob = estimate_beam_like_probability(
        sig.chain_pressure,
        sig.outer_defense,
        sig.pressure_ratio,
        advance_density
    );
    const AntiBeamSignal anti = compute_anti_beam_signal(
        sig.chain_pressure,
        sig.outer_defense,
        sig.pressure_ratio,
        sig.army_ratio,
        sig.attack_signal,
        sig.beam_like_prob
    );

    if (
        sig.pressure_ratio >= 0.90 ||
        (sig.pressure_ratio >= 0.75 && sig.army_ratio < 0.95) ||
        anti.alert_effective >= 0.80
    ) {
        sig.mode = StrategyMode::kDefense;
    } else if (
        sig.pressure_ratio <= 0.28 &&
        sig.attack_signal >= 14.0 &&
        sig.army_ratio >= 1.05 &&
        anti.alert_effective <= 0.28 &&
        st.round >= 60
    ) {
        sig.mode = StrategyMode::kOffense;
    } else {
        sig.mode = StrategyMode::kBalanced;
    }
    return sig;
}

double mode_switch_confidence(const ModeSignals& sig, StrategyMode target) {
    const AntiBeamSignal anti = compute_anti_beam_signal(
        sig.chain_pressure,
        sig.outer_defense,
        sig.pressure_ratio,
        sig.army_ratio,
        sig.attack_signal,
        sig.beam_like_prob
    );
    if (target == StrategyMode::kDefense) {
        return std::max(0.0, sig.pressure_ratio - 0.78) +
               std::max(0.0, 1.0 - sig.army_ratio) * 0.45 +
               std::max(0.0, sig.chain_pressure - 13.0) / 8.0 +
               std::max(0.0, 7.0 - sig.outer_defense) / 8.0 +
               anti.alert_effective * (0.62 + 0.30 * anti.beam_like_prob);
    }
    if (target == StrategyMode::kOffense) {
        const double safety_relief = 1.0 - anti.alert_effective;
        return std::max(0.0, 0.30 - sig.pressure_ratio) * 1.2 +
               std::max(0.0, sig.attack_signal - 16.0) / 26.0 +
               std::max(0.0, sig.army_ratio - 1.10) * 0.70 +
               std::max(0.0, sig.outer_defense - 8.0) / 10.0 +
               safety_relief * 0.28 +
               anti.initiative_gate * (0.10 + 0.08 * (1.0 - anti.beam_like_prob));
    }
    return std::max(0.0, 0.62 - sig.pressure_ratio) * 0.5 + std::max(0.0, 1.15 - sig.army_ratio) * 0.2;
}

StrategyMode apply_mode_hysteresis(
    const ModeSignals& raw_sig,
    int round,
    int seed,
    StrategyMode& latched_mode,
    int& hold_until_round,
    int& last_round_seen,
    int& last_seed,
    double& last_pressure_ratio,
    double& last_chain_pressure,
    double& last_beam_like_prob,
    double& last_advance_density,
    int& density_rise_streak,
    int& defense_release_streak,
    int& defense_reentry_cooldown,
    int& beam_family_state,
    int& beam_family_hold_until
) {
    const bool reset =
        (last_seed != seed) || (round <= 2) || (last_round_seen >= 0 && round < last_round_seen);
    if (reset) {
        latched_mode = raw_sig.mode;
        hold_until_round = round + 3;
        last_round_seen = round;
        last_seed = seed;
        last_pressure_ratio = raw_sig.pressure_ratio;
        last_chain_pressure = raw_sig.chain_pressure;
        last_beam_like_prob = raw_sig.beam_like_prob;
        last_advance_density = raw_sig.advance_density;
        density_rise_streak = 0;
        defense_release_streak = 0;
        defense_reentry_cooldown = 0;
        beam_family_state = (raw_sig.beam_like_prob >= 0.60 || raw_sig.chain_pressure >= 13.8) ? 1 : 0;
        beam_family_hold_until = round + 2;
        return latched_mode;
    }

    if (defense_reentry_cooldown > 0) --defense_reentry_cooldown;

    const double pressure_jump = raw_sig.pressure_ratio - last_pressure_ratio;
    const double chain_jump = raw_sig.chain_pressure - last_chain_pressure;
    const double beam_like_jump = raw_sig.beam_like_prob - last_beam_like_prob;
    const double density_jump = raw_sig.advance_density - last_advance_density;
    if (density_jump >= 0.035) {
        density_rise_streak = std::min(density_rise_streak + 1, 4);
    } else if (density_jump <= -0.025) {
        density_rise_streak = 0;
    } else {
        density_rise_streak = std::max(0, density_rise_streak - 1);
    }
    const AntiBeamSignal anti = compute_anti_beam_signal(
        raw_sig.chain_pressure,
        raw_sig.outer_defense,
        raw_sig.pressure_ratio,
        raw_sig.army_ratio,
        raw_sig.attack_signal,
        raw_sig.beam_like_prob
    );
    int desired_family = beam_family_state;
    const bool beam_family_enter =
        anti.beam_like_prob >= 0.62 || (raw_sig.chain_pressure >= 13.8 && raw_sig.advance_density >= 0.54);
    const bool non_beam_enter =
        anti.beam_like_prob <= 0.44 && raw_sig.chain_pressure <= 12.6 && raw_sig.pressure_ratio <= 0.88;
    if (beam_family_enter) desired_family = 1;
    else if (non_beam_enter) desired_family = 0;
    if (beam_family_state < 0) {
        beam_family_state = desired_family;
        beam_family_hold_until = round + 2;
    } else if (desired_family != beam_family_state && round >= beam_family_hold_until) {
        beam_family_state = desired_family;
        beam_family_hold_until = round + 2;
    }
    const bool beam_family_latched = (beam_family_state == 1);

    const double family_alert_shift = beam_family_latched ? -0.06 : 0.05;
    const double emergency_alert_base = ((defense_reentry_cooldown > 0) ? 0.60 : 0.45) + family_alert_shift;
    const double emergency_alert_th =
        std::clamp(emergency_alert_base - 0.10 * anti.beam_like_prob + 0.05 * anti.initiative_gate, 0.32, 0.80);
    const double emergency_jump_th =
        std::clamp(
            ((defense_reentry_cooldown > 0) ? 0.34 : 0.30) +
                (beam_family_latched ? -0.03 : 0.02) +
                0.03 * anti.initiative_gate,
            0.22,
            0.48
        );
    const double chain_jump_th = std::clamp(
        1.95 - 0.70 * anti.beam_like_prob + 0.30 * anti.initiative_gate + (beam_family_latched ? -0.22 : 0.16),
        1.00,
        3.00
    );
    const bool chain_surge_emergency =
        chain_jump >= chain_jump_th &&
        raw_sig.chain_pressure >= (12.0 + 2.6 * anti.beam_like_prob) &&
        density_rise_streak >= 2 &&
        (beam_like_jump >= 0.05 || anti.beam_like_prob >= 0.58 || raw_sig.advance_density >= 0.62);
    const bool v9_fast_cut =
        (beam_family_latched || anti.beam_like_prob >= 0.70) &&
        raw_sig.chain_pressure >= 13.8 &&
        (chain_jump >= 0.90 || pressure_jump >= 0.14 || raw_sig.advance_density >= 0.61);
    const bool cooldown_force =
        (defense_reentry_cooldown > 0) &&
        (raw_sig.pressure_ratio >= 0.90) &&
        (raw_sig.chain_pressure >= (beam_family_latched ? 14.6 : 15.2)) &&
        (anti.beam_like_prob >= 0.55);
    const bool emergency_defense =
        (raw_sig.pressure_ratio >= 1.05) ||
        (pressure_jump >= emergency_jump_th && anti.alert_effective >= emergency_alert_th) ||
        (anti.alert_effective >= 0.94 && raw_sig.chain_pressure >= 17.0) ||
        v9_fast_cut ||
        chain_surge_emergency ||
        cooldown_force;
    if (emergency_defense) {
        latched_mode = StrategyMode::kDefense;
        hold_until_round = round + 4;
        last_round_seen = round;
        last_pressure_ratio = raw_sig.pressure_ratio;
        last_chain_pressure = raw_sig.chain_pressure;
        last_beam_like_prob = raw_sig.beam_like_prob;
        last_advance_density = raw_sig.advance_density;
        defense_release_streak = 0;
        defense_reentry_cooldown = 0;
        beam_family_state = 1;
        beam_family_hold_until = std::max(beam_family_hold_until, round + 3);
        return latched_mode;
    }

    if (latched_mode == StrategyMode::kDefense) {
        const bool recovered_shell = raw_sig.outer_defense >= 9.5 && raw_sig.chain_pressure <= 11.5;
        const bool low_pressure = raw_sig.pressure_ratio <= 0.74;
        const bool hard_recovered =
            raw_sig.outer_defense >= 11.0 && raw_sig.chain_pressure <= 10.0 && raw_sig.pressure_ratio <= 0.68;
        const double release_alert_cap = beam_family_latched ? 0.30 : 0.35;
        const double release_beam_cap = beam_family_latched ? 0.38 : 0.46;
        const bool soft_release_ready =
            recovered_shell && low_pressure &&
            anti.alert_effective <= release_alert_cap &&
            anti.beam_like_prob <= release_beam_cap;
        if (hard_recovered || soft_release_ready) {
            ++defense_release_streak;
        } else {
            defense_release_streak = 0;
        }
        const int need_confirm = hard_recovered ? 1 : 2;
        const bool hold_ready = hard_recovered ? (round + 1 >= hold_until_round - 1) : (round + 1 >= hold_until_round);
        if (defense_release_streak >= need_confirm && hold_ready) {
            latched_mode = StrategyMode::kBalanced;
            hold_until_round = round + 2;
            last_round_seen = round;
            last_pressure_ratio = raw_sig.pressure_ratio;
            last_chain_pressure = raw_sig.chain_pressure;
            last_beam_like_prob = raw_sig.beam_like_prob;
            last_advance_density = raw_sig.advance_density;
            defense_release_streak = 0;
            defense_reentry_cooldown = 2;
            if (beam_family_latched) {
                beam_family_state = 1;
                beam_family_hold_until = std::max(beam_family_hold_until, round + 2);
            }
            return latched_mode;
        }
    } else {
        defense_release_streak = 0;
    }

    if (round < hold_until_round) {
        last_round_seen = round;
        last_pressure_ratio = raw_sig.pressure_ratio;
        last_chain_pressure = raw_sig.chain_pressure;
        last_beam_like_prob = raw_sig.beam_like_prob;
        last_advance_density = raw_sig.advance_density;
        return latched_mode;
    }

    if (raw_sig.mode == latched_mode) {
        last_round_seen = round;
        last_pressure_ratio = raw_sig.pressure_ratio;
        last_chain_pressure = raw_sig.chain_pressure;
        last_beam_like_prob = raw_sig.beam_like_prob;
        last_advance_density = raw_sig.advance_density;
        return latched_mode;
    }

    const double conf = mode_switch_confidence(raw_sig, raw_sig.mode);
    const double th = (raw_sig.mode == StrategyMode::kBalanced) ? 0.16 : 0.22;
    if (conf >= th) {
        latched_mode = raw_sig.mode;
        hold_until_round = round + ((latched_mode == StrategyMode::kBalanced) ? 3 : 5);
        defense_release_streak = 0;
        if (latched_mode == StrategyMode::kDefense) defense_reentry_cooldown = 0;
    }
    last_round_seen = round;
    last_pressure_ratio = raw_sig.pressure_ratio;
    last_chain_pressure = raw_sig.chain_pressure;
    last_beam_like_prob = raw_sig.beam_like_prob;
    last_advance_density = raw_sig.advance_density;
    return latched_mode;
}

std::pair<int, int> choose_recruit_cell(const State& st, int player, const Grid& threat) {
    const auto enemy_main = locate_main_general(st, 1 - player);
    double best = -1e100;
    int bx = -1;
    int by = -1;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner != player) continue;
            if (c.has_general) continue;
            if (blocked_by_super_weapon(st, player, x, y)) continue;

            int front = 0;
            for (int d = 0; d < kDirs; ++d) {
                const int nx = x + kDx[d];
                const int ny = y + kDy[d];
                if (!in_bounds(nx, ny)) continue;
                if (st.board[nx][ny].owner != player) ++front;
            }
            if (front == 0) continue;

            double score = front * 20.0 + static_cast<double>(c.army) * 0.4 - threat[x][y] * 0.3;
            if (enemy_main.first >= 0) {
                score += std::max(0, 24 - manhattan(x, y, enemy_main.first, enemy_main.second));
            }
            if (score > best) {
                best = score;
                bx = x;
                by = y;
            }
        }
    }
    if (best < 20.0) return {-1, -1};
    return {bx, by};
}

Candidate select_best_move(const State& st, int player, const Grid& threat, int main_safe_reserve) {
    Candidate best;
    const auto my_main = locate_main_general(st, player);
    const auto enemy_main = locate_main_general(st, 1 - player);

    for (int sx = 0; sx < kRow; ++sx) {
        for (int sy = 0; sy < kCol; ++sy) {
            const Cell& src = st.board[sx][sy];
            if (src.owner != player || src.army <= 1) continue;
            if (blocked_by_super_weapon(st, player, sx, sy)) continue;

            const bool src_is_main = (sx == my_main.first && sy == my_main.second);
            const bool src_is_my_general = src.has_general && src.general_player == player;

            for (int d = 0; d < kDirs; ++d) {
                const int nx = sx + kDx[d];
                const int ny = sy + kDy[d];
                if (!in_bounds(nx, ny)) continue;
                const Cell& dst = st.board[nx][ny];

                if (dst.type == 2 && st.tech[player][1] == 0) continue;  // mountain without climb

                const int max_send = src.army - 1;
                if (max_send <= 0) continue;

                if (dst.owner == player) {
                    if (max_send <= 1) continue;
                    int send = std::max(1, std::min(max_send, src.army / 2));
                    if (src_is_main && src.army - send < main_safe_reserve) continue;
                    if (src_is_my_general && src.army - send < 2) continue;

                    double score = (threat[sx][sy] - threat[nx][ny]) * 0.55 - 14.0;
                    if (dst.has_general && dst.general_player == player && dst.general_type == 1) score += 18.0;
                    if (adjacent_non_owned(st, nx, ny, player)) score += 8.0;
                    if (score > best.score) {
                        best = {true, sx, sy, d, send, score};
                    }
                    continue;
                }

                const double atk = attack_multiplier(st, sx, sy, player);
                const double def = defence_multiplier(st, nx, ny, dst.owner);
                const int need = std::max(1, static_cast<int>(std::floor((dst.army * def) / atk)) + 1);

                if (max_send >= need) {
                    int send = need;
                    if (src_is_main && src.army - send < main_safe_reserve && !(dst.has_general && dst.general_type == 1)) {
                        continue;
                    }
                    if (src_is_my_general && src.army - send < 2 && !(dst.has_general && dst.general_type == 1)) {
                        continue;
                    }

                    double score = 0.0;
                    score += (dst.owner == (1 - player)) ? 60.0 : 25.0;
                    if (dst.owner == -1 && dst.army == 0) score += 10.0;

                    if (dst.has_general) {
                        if (dst.general_type == 1 && dst.general_player == (1 - player)) {
                            score += 600.0;
                        } else if (dst.general_type == 2 && dst.general_player == (1 - player)) {
                            score += 170.0;
                        } else if (dst.general_type == 2 && dst.general_player == -1) {
                            score += 130.0;
                        } else if (dst.general_type == 3 && dst.general_player == -1) {
                            score += 90.0;
                        } else if (dst.general_type == 3 && dst.general_player == (1 - player)) {
                            score += 80.0;
                        }
                    }

                    if (enemy_main.first >= 0) {
                        score += std::max(0, 20 - manhattan(nx, ny, enemy_main.first, enemy_main.second));
                    }

                    if (dst.type == 1 && st.tech[player][2] == 0) score -= 4.0;
                    score += (threat[sx][sy] - threat[nx][ny]) * 0.4;
                    score -= send * 0.65;

                    if (score > best.score) {
                        best = {true, sx, sy, d, send, score};
                    }
                } else if (dst.owner == -1 && dst.army == 0) {
                    const int send = 1;
                    if (src_is_main && src.army - send < main_safe_reserve) continue;
                    double score = 8.0 + (threat[sx][sy] - threat[nx][ny]) * 0.25;
                    if (score > best.score) {
                        best = {true, sx, sy, d, send, score};
                    }
                } else if (dst.has_general && dst.general_type == 1 && dst.general_player == (1 - player) && max_send >= 1) {
                    int send = max_send;
                    if (src_is_main && src.army - send < main_safe_reserve) send = std::max(1, src.army - main_safe_reserve);
                    if (send <= 0) continue;
                    double score = 40.0 - std::max(0, need - send) * 0.5;
                    if (score > best.score) {
                        best = {true, sx, sy, d, send, score};
                    }
                }
            }
        }
    }

    return best;
}

void apply_move(State& st, int player, const Candidate& mv) {
    if (!mv.ok || mv.num <= 0) return;
    const int sx = mv.sx;
    const int sy = mv.sy;
    const int nx = sx + kDx[mv.dir];
    const int ny = sy + kDy[mv.dir];
    if (!in_bounds(nx, ny)) return;

    Cell& src = st.board[sx][sy];
    Cell& dst = st.board[nx][ny];

    if (src.owner != player || src.army <= 1) return;
    int send = std::min(mv.num, src.army - 1);
    if (send <= 0) return;

    src.army -= send;

    if (dst.owner == player) {
        dst.army += send;
        return;
    }

    const double atk = attack_multiplier(st, sx, sy, player);
    const double def = defence_multiplier(st, nx, ny, dst.owner);
    const double vs = send * atk - dst.army * def;

    if (vs > 1e-9) {
        dst.owner = player;
        dst.army = static_cast<int>(std::ceil(vs / std::max(0.25, atk)));
        if (dst.has_general && dst.general_idx >= 0 && dst.general_idx < static_cast<int>(st.generals.size())) {
            st.generals[dst.general_idx].player = player;
            dst.general_player = player;
        }
    } else if (vs < -1e-9) {
        dst.army = static_cast<int>(std::ceil((-vs) / std::max(0.25, def)));
    } else {
        dst.army = 0;
        if (!dst.has_general) dst.owner = -1;
    }
}

std::vector<Candidate> collect_top_moves(const State& st, int player, const Grid& threat, int main_safe_reserve, int top_k) {
    std::vector<Candidate> all;
    all.reserve(256);
    const auto my_main = locate_main_general(st, player);
    const auto enemy_main = locate_main_general(st, 1 - player);

    auto push_candidate = [&](int sx, int sy, int d, int send, double score) {
        if (send <= 0) return;
        Candidate c;
        c.ok = true;
        c.sx = sx;
        c.sy = sy;
        c.dir = d;
        c.num = send;
        c.score = score;
        all.push_back(c);
    };

    for (int sx = 0; sx < kRow; ++sx) {
        for (int sy = 0; sy < kCol; ++sy) {
            const Cell& src = st.board[sx][sy];
            if (src.owner != player || src.army <= 1) continue;
            if (blocked_by_super_weapon(st, player, sx, sy)) continue;

            const bool src_is_main = (sx == my_main.first && sy == my_main.second);
            const bool src_is_my_general = src.has_general && src.general_player == player;

            for (int d = 0; d < kDirs; ++d) {
                const int nx = sx + kDx[d];
                const int ny = sy + kDy[d];
                if (!in_bounds(nx, ny)) continue;
                const Cell& dst = st.board[nx][ny];
                if (dst.type == 2 && st.tech[player][1] == 0) continue;

                const int max_send = src.army - 1;
                if (max_send <= 0) continue;

                if (dst.owner == player) {
                    if (max_send <= 1) continue;
                    const int send = std::max(1, std::min(max_send, src.army / 2));
                    if (src_is_main && src.army - send < main_safe_reserve) continue;
                    if (src_is_my_general && src.army - send < 2) continue;
                    double score = (threat[sx][sy] - threat[nx][ny]) * 0.55 - 14.0;
                    if (dst.has_general && dst.general_player == player && dst.general_type == 1) score += 18.0;
                    if (adjacent_non_owned(st, nx, ny, player)) score += 8.0;
                    push_candidate(sx, sy, d, send, score);
                    continue;
                }

                const double atk = attack_multiplier(st, sx, sy, player);
                const double def = defence_multiplier(st, nx, ny, dst.owner);
                const int need = std::max(1, static_cast<int>(std::floor((dst.army * def) / atk)) + 1);

                if (max_send >= need) {
                    int send = need;
                    if (src_is_main && src.army - send < main_safe_reserve && !(dst.has_general && dst.general_type == 1)) {
                        continue;
                    }
                    if (src_is_my_general && src.army - send < 2 && !(dst.has_general && dst.general_type == 1)) {
                        continue;
                    }

                    double score = 0.0;
                    score += (dst.owner == (1 - player)) ? 60.0 : 25.0;
                    if (dst.owner == -1 && dst.army == 0) score += 10.0;

                    if (dst.has_general) {
                        if (dst.general_type == 1 && dst.general_player == (1 - player)) score += 600.0;
                        else if (dst.general_type == 2 && dst.general_player == (1 - player)) score += 170.0;
                        else if (dst.general_type == 2 && dst.general_player == -1) score += 130.0;
                        else if (dst.general_type == 3 && dst.general_player == -1) score += 90.0;
                        else if (dst.general_type == 3 && dst.general_player == (1 - player)) score += 80.0;
                    }
                    if (enemy_main.first >= 0) {
                        score += std::max(0, 20 - manhattan(nx, ny, enemy_main.first, enemy_main.second));
                    }
                    if (dst.type == 1 && st.tech[player][2] == 0) score -= 4.0;
                    score += (threat[sx][sy] - threat[nx][ny]) * 0.4;
                    score -= send * 0.65;
                    push_candidate(sx, sy, d, send, score);
                } else if (dst.owner == -1 && dst.army == 0) {
                    const int send = 1;
                    if (src_is_main && src.army - send < main_safe_reserve) continue;
                    const double score = 8.0 + (threat[sx][sy] - threat[nx][ny]) * 0.25;
                    push_candidate(sx, sy, d, send, score);
                } else if (dst.has_general && dst.general_type == 1 && dst.general_player == (1 - player) && max_send >= 1) {
                    int send = max_send;
                    if (src_is_main && src.army - send < main_safe_reserve) send = std::max(1, src.army - main_safe_reserve);
                    if (send <= 0) continue;
                    const double score = 40.0 - std::max(0, need - send) * 0.5;
                    push_candidate(sx, sy, d, send, score);
                }
            }
        }
    }

    std::sort(all.begin(), all.end(), [](const Candidate& lhs, const Candidate& rhs) {
        return lhs.score > rhs.score;
    });
    std::vector<Candidate> uniq;
    uniq.reserve(static_cast<size_t>(top_k));
    for (const auto& c : all) {
        bool dup = false;
        for (const auto& u : uniq) {
            if (u.sx == c.sx && u.sy == c.sy && u.dir == c.dir) {
                dup = true;
                break;
            }
        }
        if (!dup) uniq.push_back(c);
        if (static_cast<int>(uniq.size()) >= top_k) break;
    }
    return uniq;
}

double evaluate_state(const State& st, int player, int enemy_moves) {
    const int enemy = 1 - player;
    const auto my_main = locate_main_general(st, player);
    const auto enemy_main = locate_main_general(st, enemy);
    int army_my = 0;
    int army_enemy = 0;
    int cells_my = 0;
    int cells_enemy = 0;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner == player) {
                army_my += c.army;
                cells_my += 1;
            } else if (c.owner == enemy) {
                army_enemy += c.army;
                cells_enemy += 1;
            }
        }
    }

    int sub_my = 0, sub_enemy = 0, farmer_my = 0, farmer_enemy = 0;
    for (const auto& g : st.generals) {
        if (!g.alive) continue;
        if (g.player == player) {
            if (g.type == 2) sub_my++;
            if (g.type == 3) farmer_my++;
        } else if (g.player == enemy) {
            if (g.type == 2) sub_enemy++;
            if (g.type == 3) farmer_enemy++;
        }
    }

    double score = 0.0;
    score += (army_my - army_enemy) * 1.10;
    score += (cells_my - cells_enemy) * 8.0;
    score += (st.coins[player] - st.coins[enemy]) * 0.65;
    score += (sub_my - sub_enemy) * 18.0;
    score += (farmer_my - farmer_enemy) * 10.0;

    if (my_main.first >= 0) {
        const Grid threat = compute_threat(st, enemy, enemy_moves);
        const int mx = my_main.first;
        const int my = my_main.second;
        const int main_army = st.board[mx][my].army;
        const double main_threat = threat[mx][my];
        score -= main_threat * 1.2;
        score += main_army * 0.7;

        double ring_enemy = 0.0;
        double ring_friend = 0.0;
        int breaches = 0;
        for (int d = 0; d < kDirs; ++d) {
            const int nx = mx + kDx[d];
            const int ny = my + kDy[d];
            if (!in_bounds(nx, ny)) continue;
            const Cell& c = st.board[nx][ny];
            if (c.type == 2) {
                ring_friend += 2.5;  // mountain acts as a natural block.
                continue;
            }
            if (c.owner == player) {
                ring_friend += c.army * 0.9;
                if (c.has_general && c.general_player == player) ring_friend += 6.0;
            } else {
                breaches += 1;
                if (c.owner == enemy) {
                    ring_enemy += c.army;
                    if (c.has_general && c.general_player == enemy) ring_enemy += 8.0;
                } else {
                    ring_enemy += 2.0;
                }
            }
        }
        score -= std::max(0.0, ring_enemy - ring_friend) * 1.8;
        score -= breaches * 4.5;
        score -= std::max(0.0, main_threat - main_army * 0.85) * 1.1;

        const double outer_defense = compute_outer_ring_defense_score(st, player);
        const double chain_pressure = compute_enemy_chain_pressure_to_main(st, player);
        const double pressure_ratio = compute_main_pressure_ratio(st, player, enemy_moves);
        const double army_ratio = compute_army_ratio(st, player);
        const double attack_signal = compute_attack_window_signal(st, player);
        const double advance_density = compute_enemy_advance_density_to_main(st, player);
        const double beam_like_prob = estimate_beam_like_probability(
            chain_pressure,
            outer_defense,
            pressure_ratio,
            advance_density
        );
        const AntiBeamSignal anti = compute_anti_beam_signal(
            chain_pressure,
            outer_defense,
            pressure_ratio,
            army_ratio,
            attack_signal,
            beam_like_prob
        );
        score += outer_defense * (0.86 + 0.42 * anti.alert_effective);
        score -= chain_pressure * (1.00 + 0.90 * anti.alert_effective);
        score -= std::max(0.0, chain_pressure - std::max(0.0, outer_defense) * 0.72) *
                 (0.70 + 0.85 * anti.alert_effective);
    }

    if (enemy_main.first >= 0) {
        if (st.board[enemy_main.first][enemy_main.second].owner == player) {
            score += 5000.0;
        } else {
            int best_dist = 99;
            for (int x = 0; x < kRow; ++x) {
                for (int y = 0; y < kCol; ++y) {
                    const Cell& c = st.board[x][y];
                    if (c.owner == player && c.army > 0) {
                        best_dist = std::min(best_dist, manhattan(x, y, enemy_main.first, enemy_main.second));
                    }
                }
            }
            if (best_dist < 99) score += std::max(0, 24 - best_dist) * 2.2;
        }
    }
    return score;
}

double evaluate_after_enemy_response(const State& st_after_my, int player, int enemy_moves, int my_moves) {
    const int enemy = 1 - player;
    double worst_case = evaluate_state(st_after_my, player, enemy_moves);
    const Grid enemy_threat = compute_threat(st_after_my, player, my_moves);
    const int enemy_reserve = compute_main_safe_reserve(st_after_my, enemy, enemy_threat);
    int enemy_top_k = 3;
    const double pressure_ratio = compute_main_pressure_ratio(st_after_my, player, enemy_moves);
    if (pressure_ratio >= 0.95) enemy_top_k = 5;
    else if (pressure_ratio <= 0.20) enemy_top_k = 2;
    const auto enemy_cands = collect_top_moves(st_after_my, enemy, enemy_threat, enemy_reserve, enemy_top_k);

    for (const auto& c : enemy_cands) {
        if (!c.ok) continue;
        State st = st_after_my;
        apply_move(st, enemy, c);
        worst_case = std::min(worst_case, evaluate_state(st, player, enemy_moves));
    }
    return worst_case;
}

double score_state_robust(
    const State& st,
    int player,
    int enemy_moves,
    int my_moves,
    StrategyMode forced_mode = StrategyMode::kBalanced,
    bool use_forced_mode = false
) {
    ModeSignals sig = analyze_strategy_mode(st, player, enemy_moves);
    if (use_forced_mode) sig.mode = forced_mode;
    const double optimistic = evaluate_state(st, player, enemy_moves);
    const double pessimistic = evaluate_after_enemy_response(st, player, enemy_moves, my_moves);
    double w_opt = 0.35;
    double w_pes = 0.65;
    if (sig.mode == StrategyMode::kDefense) {
        w_opt = 0.22;
        w_pes = 0.78;
    } else if (sig.mode == StrategyMode::kOffense) {
        w_opt = 0.58;
        w_pes = 0.42;
    }

    double score = optimistic * w_opt + pessimistic * w_pes;
    if (sig.mode == StrategyMode::kDefense) {
        score -= std::max(0.0, optimistic - pessimistic) * 0.14;
        score -= std::max(0.0, sig.pressure_ratio - 0.80) * 10.0;
    } else if (sig.mode == StrategyMode::kOffense) {
        const double capped_attack = std::clamp(sig.attack_signal, -40.0, 40.0);
        const double pressure_gate = std::clamp((0.62 - sig.pressure_ratio) / 0.34, 0.0, 1.0);
        const double army_gate = std::clamp((sig.army_ratio - 0.92) / 0.25, 0.0, 1.0);
        const double ring_gate = std::clamp((sig.outer_defense - 5.0) / 12.0, 0.0, 1.0);
        const double chain_gate = std::clamp((16.0 - sig.chain_pressure) / 10.0, 0.0, 1.0);
        const AntiBeamSignal anti = compute_anti_beam_signal(
            sig.chain_pressure,
            sig.outer_defense,
            sig.pressure_ratio,
            sig.army_ratio,
            sig.attack_signal,
            sig.beam_like_prob
        );
        const double structure_gate =
            (0.54 - 0.22 * anti.alert_effective) + (0.46 + 0.22 * anti.alert_effective) * ring_gate * chain_gate;
        const double safety_gate = pressure_gate * (0.40 + 0.60 * army_gate) * structure_gate;
        score += std::max(0.0, capped_attack) * 0.35 * safety_gate;
        score += std::max(0.0, sig.army_ratio - 1.0) * 14.0 * std::max(0.4, safety_gate);
        const double safety_floor = std::clamp(
            0.29 + 0.20 * anti.alert_effective + 0.05 * anti.beam_like_prob - 0.03 * anti.initiative_gate,
            0.20,
            0.58
        );
        if (safety_gate < safety_floor) score -= (safety_floor - safety_gate) * (10.0 + 5.5 * anti.alert_effective);
    }
    return score;
}

double compute_main_next_turn_safety(const State& st, int player, int enemy_moves) {
    const auto my_main = locate_main_general(st, player);
    if (my_main.first < 0) return -1200.0;

    const Grid threat = compute_threat(st, 1 - player, enemy_moves);
    const int mx = my_main.first;
    const int my = my_main.second;
    const double main_army = static_cast<double>(st.board[mx][my].army);
    const double main_threat = threat[mx][my];
    const double outer_defense = compute_outer_ring_defense_score(st, player);
    const double chain_pressure = compute_enemy_chain_pressure_to_main(st, player);
    const double pressure_ratio = compute_main_pressure_ratio(st, player, enemy_moves);
    const double army_ratio = compute_army_ratio(st, player);
    const double attack_signal = compute_attack_window_signal(st, player);
    const double advance_density = compute_enemy_advance_density_to_main(st, player);
    const double beam_like_prob = estimate_beam_like_probability(
        chain_pressure,
        outer_defense,
        pressure_ratio,
        advance_density
    );
    const AntiBeamSignal anti = compute_anti_beam_signal(
        chain_pressure,
        outer_defense,
        pressure_ratio,
        army_ratio,
        attack_signal,
        beam_like_prob
    );

    const double shell_margin = outer_defense - 0.72 * chain_pressure;
    const double pressure_penalty = std::max(0.0, pressure_ratio - 0.80);
    return main_army * 0.58 -
           main_threat * (0.85 + 0.40 * anti.alert_effective) +
           shell_margin * (0.90 + 0.30 * anti.alert_effective) -
           pressure_penalty * (7.0 + 3.0 * anti.beam_like_prob) -
           anti.alert_effective * 4.5;
}

double estimate_first_step_safety_delta(
    const State& st,
    int player,
    int enemy_moves,
    const std::vector<Candidate>& seq
) {
    if (seq.empty() || !seq.front().ok) return 0.0;
    const double base_safety = compute_main_next_turn_safety(st, player, enemy_moves);
    State next = st;
    apply_move(next, player, seq.front());
    const double after_safety = compute_main_next_turn_safety(next, player, enemy_moves);
    return after_safety - base_safety;
}

std::vector<Candidate> plan_moves_beam(const State& init, int player, int enemy_moves, int move_budget) {
    struct BeamNode {
        State st;
        std::vector<Candidate> seq;
        double tactical = 0.0;
        double score = -1e100;
    };

    if (move_budget <= 0) return {};

    std::vector<BeamNode> beam;
    beam.push_back(BeamNode{init, {}, 0.0, evaluate_state(init, player, enemy_moves)});

    const int beam_width = (move_budget >= 5 ? 14 : 10);
    const int expand_topk = 6;

    for (int depth = 0; depth < move_budget; ++depth) {
        std::vector<BeamNode> next;
        for (const auto& node : beam) {
            Grid threat = compute_threat(node.st, 1 - player, enemy_moves);
            int main_safe_reserve = 3;
            const int my_moves = move_budget;
            if (node.st.my_main_x >= 0) {
                const double t = threat[node.st.my_main_x][node.st.my_main_y];
                main_safe_reserve = std::max(3, static_cast<int>(std::ceil(t * 0.55)));
                main_safe_reserve =
                    std::min(main_safe_reserve, std::max(3, node.st.board[node.st.my_main_x][node.st.my_main_y].army - 1));
            }

            auto cands = collect_top_moves(node.st, player, threat, main_safe_reserve, expand_topk);
            if (cands.empty()) {
                BeamNode stay = node;
                if (depth == 0) {
                    stay.score = score_state_robust(stay.st, player, enemy_moves, my_moves) + 0.12 * stay.tactical - 0.8 * depth;
                } else {
                    stay.score = evaluate_state(stay.st, player, enemy_moves) + 0.12 * stay.tactical - 0.8 * depth;
                }
                next.push_back(std::move(stay));
                continue;
            }

            for (const auto& c : cands) {
                BeamNode child = node;
                child.seq.push_back(c);
                child.tactical += c.score;
                apply_move(child.st, player, c);
                if (depth == 0) {
                    child.score =
                        score_state_robust(child.st, player, enemy_moves, my_moves) + 0.16 * child.tactical - 0.35 * depth;
                } else {
                    child.score = evaluate_state(child.st, player, enemy_moves) + 0.16 * child.tactical - 0.35 * depth;
                }
                next.push_back(std::move(child));
            }
        }

        if (next.empty()) break;
        std::sort(next.begin(), next.end(), [](const BeamNode& lhs, const BeamNode& rhs) {
            return lhs.score > rhs.score;
        });
        if (static_cast<int>(next.size()) > beam_width) next.resize(static_cast<size_t>(beam_width));
        beam = std::move(next);
    }

    if (beam.empty()) return {};
    const BeamNode* best = &beam[0];
    for (const auto& b : beam) {
        if (b.score > best->score) best = &b;
    }
    return best->seq;
}

std::vector<Candidate> plan_moves_greedy_sequence(const State& init, int player, int enemy_moves, int move_budget) {
    State st = init;
    std::vector<Candidate> seq;
    for (int step = 0; step < move_budget; ++step) {
        Grid threat = compute_threat(st, 1 - player, enemy_moves);
        int main_safe_reserve = 3;
        if (st.my_main_x >= 0) {
            const double t = threat[st.my_main_x][st.my_main_y];
            main_safe_reserve = std::max(3, static_cast<int>(std::ceil(t * 0.55)));
            main_safe_reserve =
                std::min(main_safe_reserve, std::max(3, st.board[st.my_main_x][st.my_main_y].army - 1));
        }
        Candidate cand = select_best_move(st, player, threat, main_safe_reserve);
        if (!cand.ok || cand.score < 1.0) break;
        seq.push_back(cand);
        apply_move(st, player, cand);
    }
    return seq;
}

double simulate_sequence_robust_score(
    const State& init,
    int player,
    int enemy_moves,
    int my_moves,
    const std::vector<Candidate>& seq,
    StrategyMode forced_mode = StrategyMode::kBalanced,
    bool use_forced_mode = false
) {
    State st = init;
    for (const auto& c : seq) {
        apply_move(st, player, c);
    }
    return score_state_robust(st, player, enemy_moves, my_moves, forced_mode, use_forced_mode);
}

double evaluate_two_step_counterfactual(
    const State& st,
    int player,
    int enemy_moves,
    int my_moves,
    const Candidate& first,
    int second_top_k
) {
    if (!first.ok) return -1e100;

    State after_first = st;
    apply_move(after_first, player, first);
    const double first_score = score_state_robust(after_first, player, enemy_moves, my_moves);

    const Grid second_threat = compute_threat(after_first, 1 - player, enemy_moves);
    const int second_reserve = compute_main_safe_reserve(after_first, player, second_threat);
    const auto second_cands = collect_top_moves(after_first, player, second_threat, second_reserve, second_top_k);

    double best_followup = first_score;
    for (const auto& c2 : second_cands) {
        if (!c2.ok) continue;
        State after_second = after_first;
        apply_move(after_second, player, c2);
        double s2 = score_state_robust(after_second, player, enemy_moves, my_moves);
        s2 += 0.06 * c2.score;
        if (s2 > best_followup) best_followup = s2;
    }

    return first_score * 0.45 + best_followup * 0.55;
}

Candidate select_best_move_counterfactual_2ply(
    const State& st,
    int player,
    int enemy_moves,
    int my_moves,
    int first_top_k,
    int second_top_k
) {
    const Grid threat = compute_threat(st, 1 - player, enemy_moves);
    const int main_safe_reserve = compute_main_safe_reserve(st, player, threat);
    const auto first_cands = collect_top_moves(st, player, threat, main_safe_reserve, first_top_k);

    Candidate best;
    double best_score = -1e100;
    for (const auto& c1 : first_cands) {
        if (!c1.ok) continue;
        double s = evaluate_two_step_counterfactual(st, player, enemy_moves, my_moves, c1, second_top_k);
        s += 0.10 * c1.score;
        if (s > best_score) {
            best_score = s;
            best = c1;
        }
    }
    return best;
}

std::vector<Candidate> plan_moves_counterfactual_2ply(const State& init, int player, int enemy_moves, int move_budget) {
    if (move_budget <= 0) return {};

    State st = init;
    std::vector<Candidate> seq;
    seq.reserve(static_cast<size_t>(move_budget));
    const int my_moves = move_budget;

    for (int step = 0; step < move_budget; ++step) {
        int first_top_k = (step == 0) ? 10 : 7;
        int second_top_k = (step <= 1) ? 5 : 4;

        const double pressure_ratio = compute_main_pressure_ratio(st, player, enemy_moves);
        int enemy_main_dist = 99;
        if (st.enemy_main_x >= 0 && st.my_main_x >= 0) {
            enemy_main_dist = manhattan(st.my_main_x, st.my_main_y, st.enemy_main_x, st.enemy_main_y);
        }
        const bool high_pressure = (pressure_ratio >= 0.80) || (enemy_main_dist <= 7);
        const bool low_pressure = (pressure_ratio <= 0.25) && (st.round >= 110) && (enemy_main_dist >= 11);
        if (high_pressure) {
            first_top_k += 2;
            second_top_k += 2;
        } else if (low_pressure) {
            first_top_k = std::max(5, first_top_k - 2);
            second_top_k = std::max(3, second_top_k - 1);
        }

        Candidate cand =
            select_best_move_counterfactual_2ply(st, player, enemy_moves, my_moves, first_top_k, second_top_k);
        if (!cand.ok) break;

        State next = st;
        apply_move(next, player, cand);
        const double hold_score = score_state_robust(st, player, enemy_moves, my_moves);
        const double next_score = score_state_robust(next, player, enemy_moves, my_moves);
        double stall_margin = 8.0;
        if (high_pressure) stall_margin = 12.0;
        else if (low_pressure) stall_margin = 6.0;
        if (next_score + stall_margin < hold_score) break;

        seq.push_back(cand);
        st = std::move(next);
    }

    return seq;
}

bool parse_state_from_rep(const json& rep, int seat, State& st) {
    st = State{};
    st.seat = seat;

    for (int i = 0; i < kRow; ++i) {
        for (int j = 0; j < kCol; ++j) {
            st.board[i][j] = Cell{};
        }
    }

    st.round = as_int(rep.value("Round", 1), 1);

    if (rep.contains("Coins") && rep["Coins"].is_array() && rep["Coins"].size() >= 2) {
        st.coins[0] = as_int(rep["Coins"][0], 0);
        st.coins[1] = as_int(rep["Coins"][1], 0);
    }
    if (rep.contains("Tech_level") && rep["Tech_level"].is_array() && rep["Tech_level"].size() >= 2) {
        for (int p = 0; p < 2; ++p) {
            if (!rep["Tech_level"][p].is_array()) continue;
            for (int k = 0; k < 4; ++k) {
                if (k < static_cast<int>(rep["Tech_level"][p].size())) {
                    st.tech[p][k] = as_int(rep["Tech_level"][p][k], st.tech[p][k]);
                }
            }
        }
    }

    if (rep.contains("Cell_type") && rep["Cell_type"].is_string()) {
        std::string cell_type = rep["Cell_type"].get<std::string>();
        if (cell_type.size() >= static_cast<size_t>(kRow * kCol)) {
            for (int i = 0; i < kRow; ++i) {
                for (int j = 0; j < kCol; ++j) {
                    const char c = cell_type[static_cast<size_t>(i * kCol + j)];
                    if (c >= '0' && c <= '9') st.board[i][j].type = c - '0';
                }
            }
        }
    }

    if (rep.contains("Cells") && rep["Cells"].is_array()) {
        for (const auto& item : rep["Cells"]) {
            if (!item.is_array() || item.size() < 3) continue;
            if (!item[0].is_array() || item[0].size() < 2) continue;
            const int x = as_int(item[0][0], -1);
            const int y = as_int(item[0][1], -1);
            if (!in_bounds(x, y)) continue;
            st.board[x][y].owner = as_int(item[1], -1);
            st.board[x][y].army = as_int(item[2], 0);
        }
    }

    if (rep.contains("Weapons") && rep["Weapons"].is_array()) {
        for (const auto& w : rep["Weapons"]) {
            if (!w.is_object()) continue;
            Weapon rec;
            rec.type = as_int(w.value("Type", 0), 0);
            rec.player = as_int(w.value("Player", -1), -1);
            rec.rest = as_int(w.value("Rest", 0), 0);
            if (w.contains("Position") && w["Position"].is_array() && w["Position"].size() >= 2) {
                rec.x = as_int(w["Position"][0], -1);
                rec.y = as_int(w["Position"][1], -1);
            }
            if (in_bounds(rec.x, rec.y)) st.weapons.push_back(rec);
        }
    }

    if (rep.contains("Generals") && rep["Generals"].is_array()) {
        for (const auto& g : rep["Generals"]) {
            if (!g.is_object()) continue;
            General rec;
            rec.id = as_int(g.value("Id", -1), -1);
            rec.player = as_int(g.value("Player", -1), -1);
            rec.type = as_int(g.value("Type", 0), 0);
            rec.alive = as_int(g.value("Alive", 1), 1) != 0;
            if (!rec.alive) continue;

            if (!g.contains("Position") || !g["Position"].is_array() || g["Position"].size() < 2) continue;
            rec.x = as_int(g["Position"][0], -1);
            rec.y = as_int(g["Position"][1], -1);
            if (!in_bounds(rec.x, rec.y)) continue;

            if (g.contains("Level") && g["Level"].is_array()) {
                if (g["Level"].size() >= 1) rec.level_prod = as_int(g["Level"][0], 1);
                if (g["Level"].size() >= 2) rec.level_def = as_int(g["Level"][1], 1);
                if (g["Level"].size() >= 3) rec.level_mob = as_int(g["Level"][2], 1);
            }
            if (g.contains("Skill_rest") && g["Skill_rest"].is_array()) {
                for (int i = 0; i < 3; ++i) {
                    if (i < static_cast<int>(g["Skill_rest"].size())) rec.skill_rest[i] = as_int(g["Skill_rest"][i], 0);
                }
            }

            const int idx = static_cast<int>(st.generals.size());
            st.generals.push_back(rec);
            Cell& c = st.board[rec.x][rec.y];
            c.has_general = true;
            c.general_idx = idx;
            c.general_player = rec.player;
            c.general_type = rec.type;
            c.general_def = decode_general_def(rec.type, rec.level_def);

            if (rec.type == 1 && rec.player == seat) {
                st.my_main_id = rec.id;
                st.my_main_x = rec.x;
                st.my_main_y = rec.y;
                st.my_main_prod = rec.level_prod;
                st.my_main_def = rec.level_def;
                st.my_main_mob = rec.level_mob;
            } else if (rec.type == 1 && rec.player == (1 - seat)) {
                st.enemy_main_x = rec.x;
                st.enemy_main_y = rec.y;
            }
        }
    }

    if (st.my_main_x == -1) {
        int best_army = -1;
        for (int i = 0; i < kRow; ++i) {
            for (int j = 0; j < kCol; ++j) {
                if (st.board[i][j].owner != seat) continue;
                if (st.board[i][j].army > best_army) {
                    best_army = st.board[i][j].army;
                    st.my_main_x = i;
                    st.my_main_y = j;
                }
            }
        }
    }

    return st.my_main_x != -1;
}

}  // namespace

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int seat = 0;
    int seed = 0;

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;

        int km_seat = seat;
        int km_seed = seed;
        if (parse_km(line, km_seat, km_seed)) {
            seat = km_seat;
            seed = km_seed;
            continue;
        }

        if (line.front() != '{' || line.back() != '}') continue;

        json rep;
        try {
            rep = json::parse(line);
        } catch (...) {
            continue;
        }
        if (!rep.is_object()) continue;

        if (rep.contains("Player")) seat = as_int(rep["Player"], seat);
        int turn = seat;
        if (rep.contains("Turn")) turn = as_int(rep["Turn"], seat);
        if (turn != seat) continue;

        State st;
        if (!parse_state_from_rep(rep, seat, st)) {
            send_payload("8\n");
            continue;
        }

        const int enemy = 1 - seat;
        int my_coin = st.coins[seat];
        int tech_mob_tier = st.tech[seat][0];
        const int enemy_moves = move_budget_from_tier(st.tech[enemy][0]);
        const int owned_cells = count_owned_cells(st, seat);

        std::vector<std::vector<int>> ops;
        ops.reserve(40);
        auto push_op = [&](std::vector<int> op) {
            if (ops.size() < 36) ops.push_back(std::move(op));
        };

        Grid threat = compute_threat(st, enemy, enemy_moves);
        const double main_threat = (st.my_main_x >= 0) ? threat[st.my_main_x][st.my_main_y] : 0.0;
        int main_safe_reserve = 3;
        if (st.my_main_x >= 0) {
            main_safe_reserve = std::max(3, static_cast<int>(std::ceil(main_threat * 0.55)));
            main_safe_reserve = std::min(main_safe_reserve, std::max(3, st.board[st.my_main_x][st.my_main_y].army - 1));
        }

        // 1) Defensive priority: main general defense when pressure is high.
        if (st.my_main_id >= 0 && my_coin >= 20 && st.my_main_x >= 0 &&
            !blocked_by_super_weapon(st, seat, st.my_main_x, st.my_main_y)) {
            const int main_army = st.board[st.my_main_x][st.my_main_y].army;
            if (st.my_main_def <= 1 && main_threat > main_army * 0.65) {
                push_op({3, st.my_main_id, 2});
                my_coin -= 20;
                st.my_main_def = 2;
            } else if (st.my_main_def == 2 && my_coin >= 50 && main_threat > main_army * 1.1) {
                push_op({3, st.my_main_id, 2});
                my_coin -= 50;
                st.my_main_def = 3;
            }
        }

        // 2) Mobility tech first (mirrors old AI's move-tempo preference).
        if (tech_mob_tier == 1 && my_coin >= 80 && st.round >= 35 && owned_cells >= 12) {
            push_op({5, 1});
            my_coin -= 80;
            tech_mob_tier = 2;
        } else if (tech_mob_tier == 2 && my_coin >= 150 && st.round >= 140 && owned_cells >= 25) {
            push_op({5, 1});
            my_coin -= 150;
            tech_mob_tier = 3;
        }

        // 3) Climb tech when mountain frontier is dense.
        if (st.tech[seat][1] == 0 && my_coin >= 100 && st.round >= 40 && count_adj_mountains(st, seat) >= 3) {
            push_op({5, 2});
            my_coin -= 100;
            st.tech[seat][1] = 1;
        }

        // 4) Main general growth.
        if (st.my_main_id >= 0 && st.my_main_x >= 0 &&
            !blocked_by_super_weapon(st, seat, st.my_main_x, st.my_main_y)) {
            if (st.my_main_prod <= 1 && my_coin >= 20 && st.round <= 180) {
                push_op({3, st.my_main_id, 1});
                my_coin -= 20;
                st.my_main_prod = 2;
            } else if (st.my_main_mob <= 1 && my_coin >= 10 && st.round <= 120) {
                push_op({3, st.my_main_id, 3});
                my_coin -= 10;
                st.my_main_mob = 2;
            } else if (st.my_main_prod == 2 && my_coin >= 40 && st.round >= 50 && st.round <= 260) {
                push_op({3, st.my_main_id, 1});
                my_coin -= 40;
                st.my_main_prod = 3;
            }
        }

        // 5) Recruit sub generals on active frontier.
        if (my_coin >= 50 && owned_cells >= 10) {
            const auto recruit = choose_recruit_cell(st, seat, threat);
            if (recruit.first != -1) {
                push_op({7, recruit.first, recruit.second});
                my_coin -= 50;
            }
        }

        // 6) Multi-step army actions:
        //    layered planner with mode-aware arbitration:
        //    selective 2-ply counterfactual + beam + greedy.
        const int move_budget = move_budget_from_tier(tech_mob_tier);
        const int my_moves = move_budget;
        const bool tactical_window =
            (st.round <= 100) ||
            (st.enemy_main_x >= 0 && st.my_main_x >= 0 &&
             manhattan(st.my_main_x, st.my_main_y, st.enemy_main_x, st.enemy_main_y) <= 10);
        auto greedy_seq = plan_moves_greedy_sequence(st, seat, enemy_moves, move_budget);
        auto counter_seq = plan_moves_counterfactual_2ply(st, seat, enemy_moves, move_budget);
        auto beam_seq = tactical_window ? plan_moves_beam(st, seat, enemy_moves, move_budget) : std::vector<Candidate>{};
        const ModeSignals raw_mode_sig = analyze_strategy_mode(st, seat, enemy_moves);
        static StrategyMode latched_mode = StrategyMode::kBalanced;
        static int mode_hold_until_round = 0;
        static int mode_last_round_seen = -1;
        static int mode_last_seed = -1;
        static double mode_last_pressure = 0.0;
        static double mode_last_chain_pressure = 0.0;
        static double mode_last_beam_like = 0.0;
        static double mode_last_advance_density = 0.0;
        static int mode_density_rise_streak = 0;
        static int mode_defense_release_streak = 0;
        static int mode_defense_reentry_cooldown = 0;
        static int mode_beam_family_state = -1;
        static int mode_beam_family_hold_until = 0;
        static double arb_prev_chain_pressure = 0.0;
        static double arb_prev_advance_density = 0.0;
        static int arb_prev_round_seen = -1;
        static int arb_prev_seed = -1;
        static int arb_low_jump_attack_streak = 0;
        const StrategyMode active_mode = apply_mode_hysteresis(
            raw_mode_sig,
            st.round,
            seed,
            latched_mode,
            mode_hold_until_round,
            mode_last_round_seen,
            mode_last_seed,
            mode_last_pressure,
            mode_last_chain_pressure,
            mode_last_beam_like,
            mode_last_advance_density,
            mode_density_rise_streak,
            mode_defense_release_streak,
            mode_defense_reentry_cooldown,
            mode_beam_family_state,
            mode_beam_family_hold_until
        );
        ModeSignals mode_sig = raw_mode_sig;
        mode_sig.mode = active_mode;
        const bool beam_family_latched = (mode_beam_family_state == 1);
        const bool rebound_window =
            (mode_defense_reentry_cooldown > 0) &&
            beam_family_latched &&
            mode_sig.mode != StrategyMode::kDefense;

        double greedy_bias = 0.0;
        double counter_bias = 0.0;
        double beam_bias = 0.0;
        if (mode_sig.mode == StrategyMode::kDefense) {
            greedy_bias = 1.2;
            counter_bias = 0.3;
            beam_bias = 0.2;
        } else if (mode_sig.mode == StrategyMode::kOffense) {
            greedy_bias = 0.1;
            counter_bias = 1.3;
            beam_bias = 0.8;
        }

        const AntiBeamSignal anti = compute_anti_beam_signal(
            raw_mode_sig.chain_pressure,
            raw_mode_sig.outer_defense,
            raw_mode_sig.pressure_ratio,
            raw_mode_sig.army_ratio,
            raw_mode_sig.attack_signal,
            raw_mode_sig.beam_like_prob
        );
        const bool rebound_suppressed =
            (anti.beam_like_prob <= 0.48 && raw_mode_sig.pressure_ratio >= 0.70) ||
            (anti.beam_like_prob <= 0.44 && raw_mode_sig.chain_pressure >= 12.8) ||
            (raw_mode_sig.pressure_ratio >= 0.84 && anti.alert_effective >= 0.42);
        const bool rebound_window_active = rebound_window && !rebound_suppressed;
        greedy_bias += 0.56 * anti.alert_effective + 0.08 * anti.beam_like_prob;
        counter_bias -= 0.36 * anti.alert_effective + 0.08 * anti.beam_like_prob;
        beam_bias -= 0.24 * anti.alert_effective + 0.10 * anti.beam_like_prob;
        const double chain_surge = std::clamp((raw_mode_sig.chain_pressure - 13.0) / 6.5, 0.0, 1.0) *
                                   std::clamp((raw_mode_sig.advance_density - 0.32) / 0.45, 0.0, 1.0);
        const bool arb_history_ready =
            seed == arb_prev_seed &&
            arb_prev_round_seen >= 0 &&
            st.round == arb_prev_round_seen + 1;
        if (!arb_history_ready) {
            arb_prev_chain_pressure = raw_mode_sig.chain_pressure;
            arb_prev_advance_density = raw_mode_sig.advance_density;
            arb_low_jump_attack_streak = 0;
        }
        const double chain_jump = std::max(0.0, raw_mode_sig.chain_pressure - arb_prev_chain_pressure);
        const double density_jump = std::max(0.0, raw_mode_sig.advance_density - arb_prev_advance_density);
        const double chain_jump_norm = std::clamp((chain_jump - 0.30) / 2.20, 0.0, 1.0);
        const double density_jump_norm = std::clamp((density_jump - 0.02) / 0.16, 0.0, 1.0);
        const double burst_fast_pressure = std::clamp(0.64 * chain_jump_norm + 0.36 * density_jump_norm, 0.0, 1.0);
        const double low_jump_mask = std::clamp((0.24 - chain_jump_norm) / 0.24, 0.0, 1.0);
        const double hardening_gate =
            std::clamp((anti.beam_like_prob - 0.52) / 0.28, 0.0, 1.0) *
            std::clamp((anti.alert_effective - 0.36) / 0.30, 0.0, 1.0);
        const double sustained_pressure_floor =
            std::clamp((raw_mode_sig.chain_pressure - 13.4) / 2.4, 0.0, 1.0) *
            std::clamp((anti.beam_like_prob - 0.56) / 0.26, 0.0, 1.0) *
            std::clamp((raw_mode_sig.advance_density - 0.50) / 0.18, 0.0, 1.0) *
            low_jump_mask;
        const double burst_hardening = (0.20 + 0.80 * burst_fast_pressure) * hardening_gate;
        const double sustained_loss_gate =
            std::clamp((0.68 - anti.initiative_gate) / 0.34, 0.0, 1.0) *
            std::clamp((raw_mode_sig.pressure_ratio - 0.62) / 0.24, 0.0, 1.0);
        const double sustained_hardening_add =
            0.22 * sustained_pressure_floor *
            std::clamp((anti.alert_effective - 0.30) / 0.34, 0.0, 1.0) *
            sustained_loss_gate;
        const double dual_jump_pulse =
            std::clamp((chain_jump_norm - 0.24) / 0.52, 0.0, 1.0) *
            std::clamp((density_jump_norm - 0.20) / 0.50, 0.0, 1.0);
        const double pulse_hardening_boost =
            0.12 *
            dual_jump_pulse *
            std::clamp((anti.beam_like_prob - 0.50) / 0.34, 0.0, 1.0) *
            std::clamp((anti.alert_effective - 0.30) / 0.34, 0.0, 1.0) *
            std::clamp((0.72 - anti.initiative_gate) / 0.30, 0.0, 1.0);
        const double hardening_intensity =
            std::clamp(burst_hardening + sustained_hardening_add + pulse_hardening_boost, 0.0, 1.0);
        const bool low_jump_high_attack =
            chain_jump_norm <= 0.22 &&
            density_jump_norm <= 0.28 &&
            raw_mode_sig.attack_signal >= 15.5 &&
            raw_mode_sig.pressure_ratio >= 0.64;
        if (low_jump_high_attack) {
            arb_low_jump_attack_streak = std::min(12, arb_low_jump_attack_streak + 1);
        } else {
            arb_low_jump_attack_streak = std::max(0, arb_low_jump_attack_streak - 2);
        }
        const double surge_guard = std::clamp((anti.beam_like_prob - 0.36) / 0.44, 0.0, 1.0);
        greedy_bias += 0.20 * chain_surge * surge_guard;
        counter_bias -= 0.10 * chain_surge * surge_guard;
        beam_bias -= 0.08 * chain_surge * surge_guard;
        if (beam_family_latched) {
            greedy_bias += 0.18;
            counter_bias -= 0.12;
            beam_bias -= 0.08;
        } else {
            greedy_bias -= 0.06;
            counter_bias += 0.10;
            beam_bias += 0.05;
        }
        if (anti.beam_like_prob >= 0.70 && raw_mode_sig.chain_pressure >= 14.0) {
            greedy_bias += 0.35;
            counter_bias -= 0.20;
            beam_bias -= 0.16;
        }
        greedy_bias += 0.18 * hardening_intensity;
        counter_bias -= 0.12 * hardening_intensity;
        beam_bias -= 0.09 * hardening_intensity;
        const bool mid_pressure_window = raw_mode_sig.pressure_ratio >= 0.44 && raw_mode_sig.pressure_ratio <= 0.80;
        const double recover_drive =
            std::clamp((raw_mode_sig.attack_signal - 11.0) / 26.0, 0.0, 1.0) *
            std::clamp((raw_mode_sig.army_ratio - 0.98) / 0.24, 0.0, 1.0);
        if (
            mid_pressure_window &&
            anti.beam_like_prob <= 0.50 &&
            chain_surge <= 0.42 &&
            anti.alert_effective <= 0.58 &&
            mode_sig.mode != StrategyMode::kDefense
        ) {
            greedy_bias -= 0.16 * (0.45 + 0.55 * recover_drive);
            counter_bias += 0.20 * (0.40 + 0.60 * recover_drive);
            beam_bias += 0.12 * (0.35 + 0.65 * recover_drive);
        }
        if (
            anti.alert_effective <= 0.22 &&
            anti.initiative_gate >= 0.58 &&
            anti.beam_like_prob <= 0.42 &&
            mode_sig.mode != StrategyMode::kDefense
        ) {
            counter_bias += 0.24;
            beam_bias += 0.14;
        }
        if (rebound_window_active) {
            const double rebound_scale = 0.55 + 0.25 * static_cast<double>(mode_defense_reentry_cooldown);
            greedy_bias -= 0.16 * rebound_scale;
            counter_bias += 0.22 * rebound_scale;
            beam_bias += 0.16 * rebound_scale;
        }
        const bool exchange_guard_window =
            st.round >= 70 &&
            st.round <= 260 &&
            mode_sig.mode != StrategyMode::kDefense &&
            anti.alert_effective >= 0.26 &&
            anti.alert_effective <= 0.76 &&
            anti.beam_like_prob >= 0.24 &&
            anti.beam_like_prob <= 0.84;
        double safety_delta_floor = -1.20;
        double guard_penalty_slope = 1.30;
        double guard_reject_deficit = 1.80;
        if (beam_family_latched) {
            safety_delta_floor = std::clamp(
                -0.48 + 0.58 * anti.initiative_gate - 0.50 * anti.alert_effective,
                -1.25,
                0.45
            );
            guard_penalty_slope = 2.50 + 1.10 * anti.alert_effective;
            guard_reject_deficit = 1.20;
            if (rebound_window_active) {
                safety_delta_floor -= 0.30;
                guard_penalty_slope *= 0.72;
                guard_reject_deficit += 0.45;
            }
        } else {
            safety_delta_floor = std::clamp(
                -1.38 + 0.92 * anti.initiative_gate - 0.30 * anti.alert_effective,
                -2.50,
                0.65
            );
            guard_penalty_slope = 1.05 + 0.55 * anti.alert_effective;
            guard_reject_deficit = 2.15;
        }
        if (hardening_intensity >= 0.08) {
            safety_delta_floor = std::min(0.65, safety_delta_floor + 0.06 + 0.14 * hardening_intensity);
            guard_penalty_slope += 0.16 + 0.44 * hardening_intensity;
            guard_reject_deficit = std::max(0.95, guard_reject_deficit - (0.08 + 0.22 * hardening_intensity));
        }
        const bool high_pressure_counterline_strong_guard =
            anti.beam_like_prob >= 0.58 &&
            raw_mode_sig.pressure_ratio >= 0.78 &&
            raw_mode_sig.chain_pressure >= 14.6 &&
            (chain_jump_norm >= 0.38 || density_jump_norm >= 0.36 || hardening_intensity >= 0.54);
        const bool high_pressure_counterline_weak_guard =
            !high_pressure_counterline_strong_guard &&
            anti.beam_like_prob >= 0.48 &&
            raw_mode_sig.pressure_ratio >= 0.70 &&
            raw_mode_sig.chain_pressure >= 13.6 &&
            (chain_jump_norm >= 0.28 || density_jump_norm >= 0.28 || hardening_intensity >= 0.40);
        const bool v2_narrow_burst_window =
            anti.beam_like_prob >= 0.66 &&
            raw_mode_sig.pressure_ratio >= 0.76 &&
            raw_mode_sig.chain_pressure >= 14.8 &&
            anti.initiative_gate <= 0.54 &&
            chain_jump_norm >= 0.30 &&
            density_jump_norm >= 0.26 &&
            hardening_intensity >= 0.44;
        const double counterline_relax_scale =
            high_pressure_counterline_strong_guard ? 0.0 : (high_pressure_counterline_weak_guard ? 0.50 : 1.0);
        const double counterline_transition_scale =
            high_pressure_counterline_strong_guard ? 0.0 : (high_pressure_counterline_weak_guard ? 0.66 : 1.0);
        const double v2_narrow_transition_scale = v2_narrow_burst_window ? 0.78 : 1.0;
        const double v2_narrow_midpressure_scale = v2_narrow_burst_window ? 0.76 : 1.0;
        const double v2_narrow_rebound_scale = v2_narrow_burst_window ? 0.84 : 1.0;
        const bool hardline_recovery_window =
            !v2_narrow_burst_window &&
            mode_sig.mode != StrategyMode::kDefense &&
            !beam_family_latched &&
            anti.beam_like_prob >= 0.50 &&
            anti.beam_like_prob <= 0.78 &&
            raw_mode_sig.pressure_ratio >= 0.70 &&
            raw_mode_sig.pressure_ratio <= 0.92 &&
            anti.alert_effective >= 0.34 &&
            anti.alert_effective <= 0.84 &&
            anti.initiative_gate >= 0.56 &&
            raw_mode_sig.chain_pressure >= 13.8 &&
            raw_mode_sig.chain_pressure <= 16.8 &&
            hardening_intensity >= 0.32 &&
            !high_pressure_counterline_strong_guard;
        const double hardline_transition_scale = hardline_recovery_window ? 1.12 : 1.0;
        const double hardline_midpressure_scale = hardline_recovery_window ? 1.14 : 1.0;
        const double hardline_v6_scale = hardline_recovery_window ? 1.08 : 1.0;
        const double hardline_rebound_scale = hardline_recovery_window ? 1.10 : 1.0;
        if (v2_narrow_burst_window) {
            safety_delta_floor = std::min(0.65, safety_delta_floor + 0.04);
            guard_penalty_slope += 0.10;
            guard_reject_deficit = std::max(0.90, guard_reject_deficit - 0.08);
        }
        if (hardline_recovery_window) {
            safety_delta_floor = std::clamp(safety_delta_floor - 0.05, -2.30, 0.65);
            guard_penalty_slope = std::max(0.80, guard_penalty_slope - 0.06);
            guard_reject_deficit = std::min(2.36, guard_reject_deficit + 0.08);
        }
        const bool non_beam_counter_relax_window =
            mode_sig.mode != StrategyMode::kDefense &&
            !beam_family_latched &&
            anti.beam_like_prob >= 0.30 &&
            anti.beam_like_prob <= 0.56 &&
            raw_mode_sig.pressure_ratio >= 0.60 &&
            raw_mode_sig.pressure_ratio <= 0.84 &&
            anti.initiative_gate >= 0.56 &&
            hardening_intensity <= 0.42 &&
            !high_pressure_counterline_strong_guard;
        if (non_beam_counter_relax_window) {
            if (high_pressure_counterline_weak_guard) {
                safety_delta_floor = std::clamp(safety_delta_floor - 0.07, -2.30, 0.65);
                guard_penalty_slope = std::max(0.86, guard_penalty_slope - 0.08);
                guard_reject_deficit = std::min(2.34, guard_reject_deficit + 0.10);
            } else {
                safety_delta_floor = std::clamp(safety_delta_floor - 0.14, -2.30, 0.65);
                guard_penalty_slope = std::max(0.78, guard_penalty_slope - 0.14);
                guard_reject_deficit = std::min(2.40, guard_reject_deficit + 0.16);
            }
        }
        const double base_main_safety = compute_main_next_turn_safety(st, seat, enemy_moves);
        double shell_safety_drop_cap = beam_family_latched ? 3.10 : 4.40;
        if (anti.beam_like_prob <= 0.50 && raw_mode_sig.pressure_ratio >= 0.66) {
            shell_safety_drop_cap = std::min(shell_safety_drop_cap, 2.20);
        }
        if (anti.beam_like_prob <= 0.40 && raw_mode_sig.pressure_ratio >= 0.74) {
            shell_safety_drop_cap = std::min(shell_safety_drop_cap, 1.80);
        }
        if (hardening_intensity >= 0.08) {
            const double hardening_drop_cap = std::clamp(3.05 - 0.70 * hardening_intensity, 2.35, 3.05);
            shell_safety_drop_cap = std::min(shell_safety_drop_cap, hardening_drop_cap);
        }
        const double shell_soft_floor = base_main_safety - shell_safety_drop_cap;
        double shell_hard_margin = beam_family_latched ? 0.95 : 1.25;
        if (anti.beam_like_prob <= 0.48 && raw_mode_sig.pressure_ratio >= 0.72) {
            shell_hard_margin = std::max(0.82, shell_hard_margin - 0.18);
        }
        if (hardening_intensity >= 0.08) {
            const double hardening_margin_cut = 0.10 + 0.20 * hardening_intensity;
            shell_hard_margin = std::max(0.58, shell_hard_margin - hardening_margin_cut);
        }
        const double shell_hard_floor = shell_soft_floor - shell_hard_margin;
        double shell_soft_penalty_slope = beam_family_latched ? 1.40 : 1.05;
        if (anti.beam_like_prob <= 0.52 && raw_mode_sig.pressure_ratio >= 0.68) {
            shell_soft_penalty_slope += 0.25;
        }
        shell_soft_penalty_slope += 0.10 * hardening_intensity + 0.16 * hardening_intensity * hardening_intensity;
        const bool counter_relief_window =
            mode_sig.mode != StrategyMode::kDefense &&
            raw_mode_sig.pressure_ratio >= 0.54 &&
            raw_mode_sig.pressure_ratio <= 0.86 &&
            anti.alert_effective >= 0.24 &&
            anti.alert_effective <= 0.72 &&
            anti.beam_like_prob >= 0.30 &&
            anti.beam_like_prob <= 0.82 &&
            raw_mode_sig.attack_signal >= 12.0 &&
            chain_surge <= 0.68;
        double counter_relief_bonus = 0.0;
        if (counter_relief_window &&
            !rebound_suppressed &&
            base_main_safety >= shell_soft_floor + 0.72) {
            const double safety_room = std::clamp((base_main_safety - shell_soft_floor - 0.72) / 2.2, 0.0, 1.0);
            const double initiative_room = std::clamp((anti.initiative_gate - 0.30) / 0.60, 0.0, 1.0);
            const double beam_relief_weight = std::clamp((0.82 - anti.beam_like_prob) / 0.52, 0.0, 1.0);
            const double alert_relief_weight = std::clamp((0.72 - anti.alert_effective) / 0.44, 0.0, 1.0);
            const double pressure_relief_weight = std::clamp((0.90 - raw_mode_sig.pressure_ratio) / 0.38, 0.0, 1.0);
            const double hardening_block = std::clamp(1.0 - 0.62 * hardening_intensity, 0.34, 1.0);
            const bool tempo_decay_whitelist =
                low_jump_high_attack &&
                raw_mode_sig.chain_pressure >= 13.4 &&
                raw_mode_sig.pressure_ratio >= 0.66 &&
                anti.alert_effective >= 0.34 &&
                anti.alert_effective <= 0.72 &&
                anti.beam_like_prob >= 0.52 &&
                anti.beam_like_prob <= 0.78 &&
                anti.initiative_gate <= 0.56;
            double anti_tempo_decay = 1.0;
            if (tempo_decay_whitelist) {
                const double streak_decay = std::clamp((static_cast<double>(arb_low_jump_attack_streak) - 2.0) / 6.0, 0.0, 1.0);
                anti_tempo_decay = std::clamp(
                    1.0 - 0.40 * streak_decay * std::clamp((anti.beam_like_prob - 0.50) / 0.28, 0.0, 1.0),
                    0.55,
                    1.0
                );
            }
            const double relief_weight =
                beam_relief_weight * alert_relief_weight * pressure_relief_weight * hardening_block * anti_tempo_decay;
            counter_relief_bonus = (0.08 + 0.12 * (0.55 * safety_room + 0.45 * initiative_room)) * relief_weight;
            if (beam_family_latched) counter_relief_bonus *= 0.78;
        }
        const bool counter_transition_protect_window =
            mode_sig.mode != StrategyMode::kDefense &&
            !beam_family_latched &&
            raw_mode_sig.pressure_ratio >= 0.58 &&
            raw_mode_sig.pressure_ratio <= 0.82 &&
            anti.beam_like_prob >= 0.34 &&
            anti.beam_like_prob <= 0.62 &&
            anti.alert_effective >= 0.20 &&
            anti.alert_effective <= 0.56 &&
            anti.initiative_gate >= 0.44 &&
            raw_mode_sig.chain_pressure <= 14.6 &&
            chain_jump_norm <= 0.52;
        double counter_transition_bonus_cap = 0.0;
        if (counter_transition_protect_window &&
            !rebound_suppressed) {
            const double initiative_headroom = std::clamp((anti.initiative_gate - 0.44) / 0.34, 0.0, 1.0);
            const double hardening_relax = std::clamp((0.70 - hardening_intensity) / 0.70, 0.0, 1.0);
            counter_transition_bonus_cap =
                (0.04 + 0.08 * initiative_headroom) * hardening_relax;
            counter_transition_bonus_cap *= v2_narrow_transition_scale;
            counter_transition_bonus_cap *= hardline_transition_scale;
        }
        const bool counter_midpressure_lane_window =
            mode_sig.mode != StrategyMode::kDefense &&
            !beam_family_latched &&
            anti.beam_like_prob >= 0.26 &&
            anti.beam_like_prob <= 0.54 &&
            raw_mode_sig.pressure_ratio >= 0.58 &&
            raw_mode_sig.pressure_ratio <= 0.84 &&
            anti.initiative_gate >= 0.54 &&
            raw_mode_sig.attack_signal >= 12.8 &&
            hardening_intensity <= 0.48 &&
            !high_pressure_counterline_strong_guard;
        double counter_midpressure_bonus_cap = 0.0;
        if (counter_midpressure_lane_window &&
            !rebound_suppressed) {
            const double initiative_lane = std::clamp((anti.initiative_gate - 0.54) / 0.30, 0.0, 1.0);
            const double attack_lane = std::clamp((raw_mode_sig.attack_signal - 12.8) / 8.0, 0.0, 1.0);
            const double beam_lane = std::clamp((0.58 - anti.beam_like_prob) / 0.32, 0.0, 1.0);
            const double hardening_lane = std::clamp((0.56 - hardening_intensity) / 0.56, 0.0, 1.0);
            counter_midpressure_bonus_cap =
                (0.03 + 0.07 * (0.45 * initiative_lane + 0.35 * attack_lane + 0.20 * beam_lane)) * hardening_lane;
            counter_midpressure_bonus_cap *= counterline_relax_scale;
            counter_midpressure_bonus_cap *= v2_narrow_midpressure_scale;
            counter_midpressure_bonus_cap *= hardline_midpressure_scale;
        }
        const bool counter_v6_2ply_window =
            mode_sig.mode != StrategyMode::kDefense &&
            !beam_family_latched &&
            anti.beam_like_prob >= 0.30 &&
            anti.beam_like_prob <= 0.60 &&
            raw_mode_sig.pressure_ratio >= 0.60 &&
            raw_mode_sig.pressure_ratio <= 0.86 &&
            anti.initiative_gate >= 0.62 &&
            raw_mode_sig.attack_signal >= 13.6 &&
            raw_mode_sig.chain_pressure >= 12.8 &&
            raw_mode_sig.chain_pressure <= 15.4 &&
            hardening_intensity <= 0.54 &&
            !high_pressure_counterline_strong_guard;
        double counter_v6_2ply_bonus_cap = 0.0;
        if (counter_v6_2ply_window &&
            !rebound_suppressed) {
            const double initiative_v6 = std::clamp((anti.initiative_gate - 0.62) / 0.22, 0.0, 1.0);
            const double attack_v6 = std::clamp((raw_mode_sig.attack_signal - 13.6) / 7.5, 0.0, 1.0);
            const double beam_v6 = std::clamp((0.62 - anti.beam_like_prob) / 0.32, 0.0, 1.0);
            const double hardening_v6 = std::clamp((0.62 - hardening_intensity) / 0.62, 0.0, 1.0);
            counter_v6_2ply_bonus_cap =
                (0.02 + 0.08 * (0.60 * initiative_v6 + 0.40 * attack_v6)) * beam_v6 * hardening_v6;
            if (high_pressure_counterline_weak_guard) {
                counter_v6_2ply_bonus_cap *= 0.76;
            }
            counter_v6_2ply_bonus_cap *= hardline_v6_scale;
        }
        const bool counter_v19_rebound_window =
            mode_sig.mode != StrategyMode::kDefense &&
            !beam_family_latched &&
            !high_pressure_counterline_strong_guard &&
            anti.beam_like_prob >= 0.44 &&
            anti.beam_like_prob <= 0.76 &&
            raw_mode_sig.pressure_ratio >= 0.66 &&
            raw_mode_sig.pressure_ratio <= 0.90 &&
            anti.alert_effective >= 0.24 &&
            anti.alert_effective <= 0.82 &&
            anti.initiative_gate >= 0.48 &&
            raw_mode_sig.chain_pressure >= 13.2 &&
            raw_mode_sig.chain_pressure <= 16.8 &&
            hardening_intensity <= 0.64;
        double counter_v19_rebound_bonus_cap = 0.0;
        if (counter_v19_rebound_window &&
            !rebound_suppressed) {
            const double safety_rebound = std::clamp((base_main_safety - shell_soft_floor - 0.30) / 1.90, 0.0, 1.0);
            const double pressure_rebound = std::clamp((raw_mode_sig.pressure_ratio - 0.66) / 0.24, 0.0, 1.0);
            const double beam_rebound = std::clamp((anti.beam_like_prob - 0.44) / 0.28, 0.0, 1.0);
            const double chain_stability = std::clamp((0.44 - chain_jump_norm) / 0.44, 0.0, 1.0);
            const double density_stability = std::clamp((0.42 - density_jump_norm) / 0.42, 0.0, 1.0);
            const double hardening_room = std::clamp((0.70 - hardening_intensity) / 0.70, 0.0, 1.0);
            const double stability = std::min(chain_stability, density_stability);
            counter_v19_rebound_bonus_cap =
                (0.015 + 0.070 * (0.45 * safety_rebound + 0.25 * pressure_rebound + 0.30 * beam_rebound)) *
                (0.55 + 0.45 * stability) * hardening_room;
            if (high_pressure_counterline_weak_guard) {
                counter_v19_rebound_bonus_cap *= 0.82;
            }
            counter_v19_rebound_bonus_cap *= v2_narrow_rebound_scale;
            counter_v19_rebound_bonus_cap *= hardline_rebound_scale;
        }
        arb_prev_chain_pressure = raw_mode_sig.chain_pressure;
        arb_prev_advance_density = raw_mode_sig.advance_density;
        arb_prev_round_seen = st.round;
        arb_prev_seed = seed;

        std::vector<Candidate> seq = greedy_seq;
        double best_score = simulate_sequence_robust_score(
            st, seat, enemy_moves, my_moves, greedy_seq, active_mode, true
        ) + greedy_bias;
        auto consider_seq = [&](const std::vector<Candidate>& cand_seq, double bias, bool apply_exchange_guard, double transition_bonus_cap) {
            if (cand_seq.empty()) return;
            double adjusted_bias = bias;
            double safety_delta = 0.0;
            double next_main_safety = base_main_safety;
            const bool need_safety_probe =
                (apply_exchange_guard && exchange_guard_window) ||
                (transition_bonus_cap > 0.0);
            if (need_safety_probe) {
                safety_delta = estimate_first_step_safety_delta(st, seat, enemy_moves, cand_seq);
                next_main_safety = base_main_safety + safety_delta;
            }
            if (apply_exchange_guard && exchange_guard_window) {
                if (next_main_safety < shell_hard_floor) return;
                if (next_main_safety < shell_soft_floor) {
                    adjusted_bias -= (shell_soft_floor - next_main_safety) * shell_soft_penalty_slope;
                }
                if (safety_delta < safety_delta_floor) {
                    const double deficit = safety_delta_floor - safety_delta;
                    adjusted_bias -= deficit * guard_penalty_slope;
                    if (deficit >= guard_reject_deficit) return;
                } else if (safety_delta > 0.60) {
                    adjusted_bias += 0.20 * std::min(1.5, safety_delta);
                }
            }
            const double transition_safety_floor = shell_soft_floor + (v2_narrow_burst_window ? 0.08 : 0.0);
            if (transition_bonus_cap > 0.0 && next_main_safety >= transition_safety_floor) {
                const double safety_headroom = std::clamp((next_main_safety - transition_safety_floor) / 1.8, 0.0, 1.0);
                const double delta_quality = std::clamp((safety_delta + 0.60) / 1.80, 0.0, 1.0);
                adjusted_bias += transition_bonus_cap * (0.60 * safety_headroom + 0.40 * delta_quality);
            }
            const double s = simulate_sequence_robust_score(
                st, seat, enemy_moves, my_moves, cand_seq, active_mode, true
            ) + adjusted_bias;
            if (s > best_score) {
                best_score = s;
                seq = cand_seq;
            }
        };
        consider_seq(
            counter_seq,
            counter_bias + counter_relief_bonus,
            true,
            (counter_transition_bonus_cap + counter_midpressure_bonus_cap + counter_v6_2ply_bonus_cap) *
                counterline_transition_scale +
                counter_v19_rebound_bonus_cap
        );
        consider_seq(beam_seq, beam_bias + 0.35 * counter_relief_bonus, true, 0.0);

        // Last-chance safety: if chosen first step has poor counterfactual value, fall back to greedy.
        if (!seq.empty()) {
            State next = st;
            apply_move(next, seat, seq.front());
            const double first_step_robust = score_state_robust(next, seat, enemy_moves, my_moves, active_mode, true);
            const double hold_robust = score_state_robust(st, seat, enemy_moves, my_moves, active_mode, true);
            if (first_step_robust + 4.0 < hold_robust && !greedy_seq.empty()) {
                seq = greedy_seq;
            }
        }

        for (const auto& cand : seq) {
            if (!cand.ok || cand.score < 1.0) continue;
            push_op({1, cand.sx, cand.sy, kDirCode[cand.dir], cand.num});
            apply_move(st, seat, cand);
            if (ops.size() >= 35) break;
        }

        push_op({8});
        send_payload(format_ops(ops));
    }

    return 0;
}
