#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <iostream>
#include <limits>
#include <queue>
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
constexpr int kSearchStepBudgetMs = 200;
constexpr int kOverlayMinPool = 6;
constexpr int kOverlayMaxPool = 14;
constexpr int kOverlayStableMaxPool = 8;

struct General {
    int id = -1;
    int player = -1;
    int type = 0;  // 1 main, 2 sub, 3 farmer
    int x = -1;
    int y = -1;
    int level_prod = 1;
    int level_def = 1;
    int level_mob = 1;
    std::array<int, 5> skill_cd{0, 0, 0, 0, 0};
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
    std::array<int, 2> weapon_cd{-1, -1};
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

struct OverlayTuning {
    bool enabled = true;
    bool conservative = false;
    int pool_limit = 8;
    int early_stop_gap = 26;
    int early_stop_min_evals = 4;
    double my_follow_weight = 0.32;
    double enemy_weight = 0.56;
    double switch_margin = 0.8;
    double switch_penalty = 0.0;
    double base_anchor_penalty = 0.0;
    double max_raw_drop = 1e9;
    double tactical_drop_relax = 0.0;
    double tactical_anchor_scale = 1.0;
    double tactical_reply_bonus = 0.0;
    double tactical_enemy_reply_ratio = 0.45;
    double dominance_veto_ratio = 1e9;
    double dominance_veto_margin = 1e9;
    double dominance_threat_gain_min = 0.0;
    bool base_reply_veto_enabled = true;
    double base_reply_veto_slack = 1e9;
    double base_reply_drop_scale = 0.0;
    double base_reply_threat_credit = 0.0;
    double base_reply_penalty = 0.0;
    bool pressure_anchor_enabled = true;
    double base_pressure_loss_slack = 1e9;
    double base_pressure_loss_drop_scale = 0.0;
    double base_pressure_loss_threat_credit = 0.0;
    double base_pressure_loss_penalty = 0.0;
};

struct Deadline {
    bool valid = false;
    int64_t cpu_target_ns = 0;
};

int64_t read_thread_cpu_ns() {
#if defined(CLOCK_THREAD_CPUTIME_ID)
    timespec ts{};
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts) == 0) {
        return static_cast<int64_t>(ts.tv_sec) * 1000000000LL + static_cast<int64_t>(ts.tv_nsec);
    }
#endif
    return -1;
}

Deadline make_deadline_ms(int ms) {
    Deadline d{};
    const int64_t now_cpu = read_thread_cpu_ns();
    if (now_cpu >= 0) {
        d.valid = true;
        d.cpu_target_ns = now_cpu + static_cast<int64_t>(ms) * 1000000LL;
    }
    return d;
}

bool deadline_reached(const Deadline& deadline) {
    // Hard requirement: cutoff must use thread CPU clock only.
    if (!deadline.valid) return true;
    const int64_t now_cpu = read_thread_cpu_ns();
    if (now_cpu < 0) return true;
    return now_cpu >= deadline.cpu_target_ns;
}

void apply_move(State& st, int player, const Candidate& mv);

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

int decode_general_mobility_from_replay_level(int level_mob) {
    if (level_mob <= 1) return 1;
    if (level_mob == 2) return 2;
    return 4;
}

bool has_main_general(const State& st, int player) {
    for (const auto& g : st.generals) {
        if (!g.alive) continue;
        if (g.player == player && g.type == 1) return true;
    }
    return false;
}

std::pair<int, int> locate_main_general(const State& st, int player) {
    for (const auto& g : st.generals) {
        if (!g.alive) continue;
        if (g.player == player && g.type == 1) return {g.x, g.y};
    }
    return {-1, -1};
}

int find_general_index_by_id(const State& st, int general_id) {
    for (int i = 0; i < static_cast<int>(st.generals.size()); ++i) {
        if (st.generals[i].id == general_id && st.generals[i].alive) return i;
    }
    return -1;
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

std::pair<int, int> choose_recruit_cell(const State& st, int player, const Grid& threat) {
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
            if (st.enemy_main_x >= 0) {
                score += std::max(0, 24 - manhattan(x, y, st.enemy_main_x, st.enemy_main_y));
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

int choose_overlay_pool_limit(const State& st, const Grid& enemy_threat, int my_moves) {
    int limit = 8;
    if (st.round >= 90) limit += 1;
    if (my_moves >= 4) limit += 1;

    if (st.my_main_x >= 0 && st.my_main_y >= 0) {
        const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
        const double danger_ratio = enemy_threat[st.my_main_x][st.my_main_y] / static_cast<double>(main_army);
        if (danger_ratio >= 0.55) limit += 2;
        if (danger_ratio >= 0.85) limit += 2;
    }

    if (st.my_main_x >= 0 && st.enemy_main_x >= 0) {
        const int d = manhattan(st.my_main_x, st.my_main_y, st.enemy_main_x, st.enemy_main_y);
        if (d <= 8) limit += 2;
    }

    if (limit < kOverlayMinPool) limit = kOverlayMinPool;
    if (limit > kOverlayMaxPool) limit = kOverlayMaxPool;
    return limit;
}

bool same_move(const Candidate& a, const Candidate& b) {
    return a.ok == b.ok && a.sx == b.sx && a.sy == b.sy && a.dir == b.dir && a.num == b.num;
}

bool is_tactical_escape_candidate(
    const State& st,
    const Candidate& cand,
    int player,
    int enemy,
    const Candidate& base
) {
    if (!cand.ok) return false;
    const int nx = cand.sx + kDx[cand.dir];
    const int ny = cand.sy + kDy[cand.dir];
    if (!in_bounds(nx, ny)) return false;
    if (cand.score >= 520.0) return true;

    const Cell& dst = st.board[nx][ny];
    if (dst.has_general && dst.general_player == enemy) return true;

    if (dst.owner == enemy) {
        if (dst.army >= 8) return true;
        if (st.enemy_main_x >= 0 && manhattan(nx, ny, st.enemy_main_x, st.enemy_main_y) <= 3) return true;
    }

    if (st.my_main_x >= 0 && st.my_main_y >= 0 && dst.owner != player &&
        manhattan(nx, ny, st.my_main_x, st.my_main_y) <= 2) {
        return true;
    }

    if (cand.score >= base.score - 8.0 && cand.score >= 120.0) return true;
    return false;
}

double estimate_overlay_priority(
    const State& st,
    const Candidate& cand,
    int player,
    int enemy,
    const Grid& enemy_threat,
    const Candidate& base
) {
    if (!cand.ok) return -1e100;
    const int nx = cand.sx + kDx[cand.dir];
    const int ny = cand.sy + kDy[cand.dir];
    if (!in_bounds(nx, ny)) return cand.score;

    const Cell& dst = st.board[nx][ny];
    double priority = cand.score;

    // Keep base candidate near the front so overlay keeps its fallback anchor.
    if (same_move(cand, base)) priority += 1200.0;

    if (dst.owner == enemy) priority += 22.0;
    if (dst.owner == -1 && dst.army == 0) priority += 8.0;
    if (dst.has_general) {
        if (dst.general_player == enemy) {
            if (dst.general_type == 1) priority += 340.0;
            else if (dst.general_type == 2) priority += 120.0;
            else priority += 80.0;
        } else if (dst.general_player == player && dst.general_type == 1) {
            priority -= 18.0;
        }
    }

    if (st.enemy_main_x >= 0 && st.enemy_main_y >= 0) {
        const int d_enemy_main = manhattan(nx, ny, st.enemy_main_x, st.enemy_main_y);
        priority += std::max(0, 8 - d_enemy_main) * 2.4;
    }

    if (st.my_main_x >= 0 && st.my_main_y >= 0) {
        const double local_relief = enemy_threat[st.my_main_x][st.my_main_y] - enemy_threat[nx][ny];
        if (local_relief > 0.0) priority += local_relief * 2.8;

        if (dst.owner != player) {
            const int d_my_main = manhattan(nx, ny, st.my_main_x, st.my_main_y);
            if (d_my_main <= 2) priority += (3 - d_my_main) * 6.0;
        }
    }

    if (!same_move(cand, base) && cand.score < base.score - 14.0) priority -= 9.0;
    return priority;
}

OverlayTuning choose_overlay_tuning(
    const State& st,
    const Grid& enemy_threat,
    int my_moves,
    const Candidate& base
) {
    OverlayTuning tuning;
    tuning.pool_limit = choose_overlay_pool_limit(st, enemy_threat, my_moves);

    double main_danger = 0.0;
    if (st.my_main_x >= 0 && st.my_main_y >= 0) {
        const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
        main_danger = enemy_threat[st.my_main_x][st.my_main_y] / static_cast<double>(main_army);
    }
    const bool duel_close = st.my_main_x >= 0 && st.enemy_main_x >= 0 &&
                            manhattan(st.my_main_x, st.my_main_y, st.enemy_main_x, st.enemy_main_y) <= 9;
    const bool high_risk = (main_danger >= 0.55) || duel_close;

    // Base already has decisive tactical value; avoid unnecessary overlay churn.
    if (base.score >= 540.0) {
        tuning.enabled = false;
        return tuning;
    }

    // Opening in low-risk state favors stable baseline decisions.
    if (st.round <= 18 && main_danger < 0.45 && base.score >= 80.0) {
        tuning.enabled = false;
        return tuning;
    }

    if (high_risk) {
        tuning.pressure_anchor_enabled = true;
        tuning.base_reply_veto_enabled = true;
        tuning.conservative = false;
        tuning.my_follow_weight = 0.34;
        tuning.enemy_weight = 0.62;
        tuning.switch_margin = 0.7;
        tuning.switch_penalty = 0.0;
        tuning.base_anchor_penalty = 0.18;
        tuning.max_raw_drop = 26.0;
        tuning.tactical_drop_relax = 14.0;
        tuning.tactical_anchor_scale = 0.38;
        tuning.tactical_reply_bonus = 1.0;
        tuning.tactical_enemy_reply_ratio = 0.52;
        tuning.dominance_veto_ratio = 1.55;
        tuning.dominance_veto_margin = 18.0;
        tuning.dominance_threat_gain_min = 4.0;
        tuning.base_reply_veto_slack = 16.0;
        tuning.base_reply_drop_scale = 0.40;
        tuning.base_reply_threat_credit = 1.60;
        tuning.base_reply_penalty = 0.06;
        tuning.base_pressure_loss_slack = 4.2;
        tuning.base_pressure_loss_drop_scale = 0.12;
        tuning.base_pressure_loss_threat_credit = 1.35;
        tuning.base_pressure_loss_penalty = 0.12;
        tuning.early_stop_gap = 20;
        tuning.early_stop_min_evals = 6;
        return tuning;
    }

    tuning.conservative = true;
    tuning.pressure_anchor_enabled = false;
    tuning.base_reply_veto_enabled = false;
    tuning.pool_limit = std::min(tuning.pool_limit, kOverlayStableMaxPool);
    tuning.my_follow_weight = 0.24;
    tuning.enemy_weight = 0.50;
    tuning.switch_margin = 1.6;
    tuning.switch_penalty = 3.5;
    tuning.base_anchor_penalty = 0.35;
    tuning.max_raw_drop = 14.0;
    tuning.tactical_drop_relax = 8.0;
    tuning.tactical_anchor_scale = 0.70;
    tuning.tactical_reply_bonus = 0.0;
    tuning.tactical_enemy_reply_ratio = 0.36;
    tuning.dominance_veto_ratio = 0.95;
    tuning.dominance_veto_margin = 10.0;
    tuning.dominance_threat_gain_min = 2.5;
    tuning.base_reply_veto_slack = 8.0;
    tuning.base_reply_drop_scale = 0.35;
    tuning.base_reply_threat_credit = 1.10;
    tuning.base_reply_penalty = 0.10;
    tuning.base_pressure_loss_slack = 1.6;
    tuning.base_pressure_loss_drop_scale = 0.06;
    tuning.base_pressure_loss_threat_credit = 0.95;
    tuning.base_pressure_loss_penalty = 0.24;
    tuning.early_stop_gap = 28;
    tuning.early_stop_min_evals = 5;
    if (base.score >= 180.0 && st.round < 160) {
        tuning.enabled = false;
    }
    return tuning;
}

Candidate select_best_move_base(
    const State& st,
    int player,
    const Grid& threat,
    int main_safe_reserve,
    const Deadline* deadline = nullptr
) {
    Candidate best;
    const auto main_pos = [&]() -> std::pair<int, int> {
        for (const auto& g : st.generals) {
            if (!g.alive) continue;
            if (g.player == player && g.type == 1) return {g.x, g.y};
        }
        int bx = -1;
        int by = -1;
        int best_army = -1;
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
    }();
    const auto enemy_main = [&]() -> std::pair<int, int> {
        for (const auto& g : st.generals) {
            if (!g.alive) continue;
            if (g.player == (1 - player) && g.type == 1) return {g.x, g.y};
        }
        return {-1, -1};
    }();

    for (int sx = 0; sx < kRow; ++sx) {
        for (int sy = 0; sy < kCol; ++sy) {
            if (deadline && deadline_reached(*deadline)) return best;
            const Cell& src = st.board[sx][sy];
            if (src.owner != player || src.army <= 1) continue;
            if (blocked_by_super_weapon(st, player, sx, sy)) continue;

            const bool src_is_main = (sx == main_pos.first && sy == main_pos.second);
            const bool src_is_my_general = src.has_general && src.general_player == player;

            for (int d = 0; d < kDirs; ++d) {
                if (deadline && deadline_reached(*deadline)) return best;
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

bool candidate_better(const Candidate& a, const Candidate& b) {
    return a.score > b.score;
}

void push_candidate(std::vector<Candidate>& out, const Candidate& cand, int limit) {
    if (!cand.ok) return;
    out.push_back(cand);
    if (static_cast<int>(out.size()) > limit * 3) {
        std::nth_element(out.begin(), out.begin() + limit, out.end(), candidate_better);
        out.resize(static_cast<size_t>(limit));
    }
}

std::vector<Candidate> collect_move_candidates_base(
    const State& st,
    int player,
    const Grid& threat,
    int main_safe_reserve,
    int limit,
    const Deadline* deadline = nullptr
) {
    std::vector<Candidate> pool;
    pool.reserve(static_cast<size_t>(limit * 2));
    const int enemy = 1 - player;
    const auto enemy_main = [&]() -> std::pair<int, int> {
        for (const auto& g : st.generals) {
            if (!g.alive) continue;
            if (g.player == enemy && g.type == 1) return {g.x, g.y};
        }
        return {-1, -1};
    }();
    const auto main_pos = [&]() -> std::pair<int, int> {
        for (const auto& g : st.generals) {
            if (!g.alive) continue;
            if (g.player == player && g.type == 1) return {g.x, g.y};
        }
        int bx = -1;
        int by = -1;
        int best_army = -1;
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
    }();

    bool timed_out = false;
    for (int sx = 0; sx < kRow && !timed_out; ++sx) {
        for (int sy = 0; sy < kCol; ++sy) {
            if (deadline && deadline_reached(*deadline)) {
                timed_out = true;
                break;
            }
            const Cell& src = st.board[sx][sy];
            if (src.owner != player || src.army <= 1) continue;
            if (blocked_by_super_weapon(st, player, sx, sy)) continue;

            const bool src_is_main = (sx == main_pos.first && sy == main_pos.second);
            const bool src_is_my_general = src.has_general && src.general_player == player;
            const int max_send = src.army - 1;
            if (max_send <= 0) continue;

            for (int d = 0; d < kDirs; ++d) {
                if (deadline && deadline_reached(*deadline)) {
                    timed_out = true;
                    break;
                }
                const int nx = sx + kDx[d];
                const int ny = sy + kDy[d];
                if (!in_bounds(nx, ny)) continue;
                const Cell& dst = st.board[nx][ny];
                if (dst.type == 2 && st.tech[player][1] == 0) continue;

                if (dst.owner == player) {
                    if (max_send <= 1) continue;
                    int send = std::max(1, std::min(max_send, src.army / 2));
                    if (src_is_main && src.army - send < main_safe_reserve) continue;
                    if (src_is_my_general && src.army - send < 2) continue;
                    double score = (threat[sx][sy] - threat[nx][ny]) * 0.55 - 14.0;
                    if (dst.has_general && dst.general_player == player && dst.general_type == 1) score += 18.0;
                    if (adjacent_non_owned(st, nx, ny, player)) score += 8.0;
                    push_candidate(pool, {true, sx, sy, d, send, score}, limit);
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
                    score += (dst.owner == enemy) ? 60.0 : 25.0;
                    if (dst.owner == -1 && dst.army == 0) score += 10.0;
                    if (dst.has_general) {
                        if (dst.general_type == 1 && dst.general_player == enemy) score += 600.0;
                        else if (dst.general_type == 2 && dst.general_player == enemy) score += 170.0;
                        else if (dst.general_type == 2 && dst.general_player == -1) score += 130.0;
                        else if (dst.general_type == 3 && dst.general_player == -1) score += 90.0;
                        else if (dst.general_type == 3 && dst.general_player == enemy) score += 80.0;
                    }
                    if (enemy_main.first >= 0) score += std::max(0, 20 - manhattan(nx, ny, enemy_main.first, enemy_main.second));
                    if (dst.type == 1 && st.tech[player][2] == 0) score -= 4.0;
                    score += (threat[sx][sy] - threat[nx][ny]) * 0.4;
                    score -= send * 0.65;
                    push_candidate(pool, {true, sx, sy, d, send, score}, limit);
                } else if (dst.owner == -1 && dst.army == 0) {
                    const int send = 1;
                    if (src_is_main && src.army - send < main_safe_reserve) continue;
                    double score = 8.0 + (threat[sx][sy] - threat[nx][ny]) * 0.25;
                    push_candidate(pool, {true, sx, sy, d, send, score}, limit);
                } else if (dst.has_general && dst.general_type == 1 && dst.general_player == enemy && max_send >= 1) {
                    int send = max_send;
                    if (src_is_main && src.army - send < main_safe_reserve) send = std::max(1, src.army - main_safe_reserve);
                    if (send <= 0) continue;
                    double score = 40.0 - std::max(0, need - send) * 0.5;
                    push_candidate(pool, {true, sx, sy, d, send, score}, limit);
                }
            }
            if (timed_out) break;
        }
    }

    std::sort(pool.begin(), pool.end(), candidate_better);
    if (static_cast<int>(pool.size()) > limit) pool.resize(static_cast<size_t>(limit));
    return pool;
}

double kill_state_heuristic(const State& st, int player, int enemy) {
    const auto enemy_main = locate_main_general(st, enemy);
    if (enemy_main.first < 0) return 1e9;

    double best = -1e9;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner != player || c.army <= 1) continue;
            const int d = manhattan(x, y, enemy_main.first, enemy_main.second);
            double h = static_cast<double>(c.army) - static_cast<double>(d) * 5.0;
            if (d == 1) {
                const double atk = attack_multiplier(st, x, y, player);
                const double def = defence_multiplier(st, enemy_main.first, enemy_main.second, st.board[enemy_main.first][enemy_main.second].owner);
                const int need =
                    std::max(1, static_cast<int>(std::floor((st.board[enemy_main.first][enemy_main.second].army * def) / atk)) + 1);
                if (c.army - 1 >= need) h += 380.0;
                else h += 120.0 - std::max(0, need - (c.army - 1)) * 2.0;
            }
            best = std::max(best, h);
        }
    }

    const auto my_main = locate_main_general(st, player);
    if (my_main.first >= 0) {
        best += static_cast<double>(st.board[my_main.first][my_main.second].army) * 0.18;
    }
    return best;
}

std::vector<Candidate> collect_kill_branch_candidates(
    const State& st,
    int player,
    int enemy,
    int enemy_moves,
    int limit,
    const Deadline* deadline = nullptr
) {
    Grid threat = compute_threat(st, enemy, enemy_moves);
    int reserve = 3;
    if (st.my_main_x >= 0 && st.my_main_y >= 0) {
        reserve = std::max(3, static_cast<int>(std::ceil(threat[st.my_main_x][st.my_main_y] * 0.55)));
        reserve = std::min(reserve, std::max(3, st.board[st.my_main_x][st.my_main_y].army - 1));
    }

    auto pool = collect_move_candidates_base(st, player, threat, reserve, std::max(limit, 8), deadline);
    const auto enemy_main = locate_main_general(st, enemy);
    if (enemy_main.first >= 0) {
        for (int d = 0; d < kDirs; ++d) {
            const int sx = enemy_main.first + kDx[d];
            const int sy = enemy_main.second + kDy[d];
            if (!in_bounds(sx, sy)) continue;
            const Cell& src = st.board[sx][sy];
            if (src.owner != player || src.army <= 1) continue;
            if (blocked_by_super_weapon(st, player, sx, sy)) continue;

            const int dir = (d == 0) ? 1 : (d == 1) ? 0 : (d == 2) ? 3 : 2;
            const int send = src.army - 1;
            if (send <= 0) continue;
            const double direct = 920.0 + static_cast<double>(src.army) * 0.7;
            push_candidate(pool, {true, sx, sy, dir, send, direct}, std::max(limit, 8));
        }
    }

    std::sort(pool.begin(), pool.end(), candidate_better);
    if (static_cast<int>(pool.size()) > limit) pool.resize(static_cast<size_t>(limit));
    return pool;
}

std::vector<Candidate> search_forced_main_kill_sequence(
    const State& root,
    int player,
    int enemy,
    int move_budget,
    int enemy_moves,
    const Deadline& deadline
) {
    if (!has_main_general(root, enemy)) return {};

    struct Node {
        State st;
        std::vector<Candidate> seq;
        double heuristic = -1e100;
    };

    std::vector<Node> frontier;
    frontier.push_back(Node{root, {}, kill_state_heuristic(root, player, enemy)});

    const int beam_width = 10;
    const int max_nodes = 260;
    int expanded = 0;

    for (int depth = 0; depth < move_budget && !frontier.empty(); ++depth) {
        if (deadline_reached(deadline)) return {};
        std::vector<Node> next;
        next.reserve(static_cast<size_t>(beam_width * 4));

        for (const auto& node : frontier) {
            if (deadline_reached(deadline)) return {};
            if (!has_main_general(node.st, enemy)) return node.seq;
            if (++expanded > max_nodes) break;

            auto cands = collect_kill_branch_candidates(node.st, player, enemy, enemy_moves, 8, &deadline);
            for (const auto& cand : cands) {
                if (deadline_reached(deadline)) return {};
                if (!cand.ok) continue;

                State ns = node.st;
                apply_move(ns, player, cand);

                std::vector<Candidate> seq = node.seq;
                seq.push_back(cand);
                if (!has_main_general(ns, enemy)) return seq;

                double h = kill_state_heuristic(ns, player, enemy) - static_cast<double>(seq.size()) * 2.3;
                next.push_back(Node{std::move(ns), std::move(seq), h});
                if (static_cast<int>(next.size()) > beam_width * 6) {
                    std::nth_element(
                        next.begin(),
                        next.begin() + beam_width * 3,
                        next.end(),
                        [](const Node& a, const Node& b) { return a.heuristic > b.heuristic; }
                    );
                    next.resize(static_cast<size_t>(beam_width * 3));
                }
            }
        }

        if (next.empty()) break;
        std::sort(next.begin(), next.end(), [](const Node& a, const Node& b) { return a.heuristic > b.heuristic; });
        if (static_cast<int>(next.size()) > beam_width) next.resize(static_cast<size_t>(beam_width));
        frontier = std::move(next);
    }
    return {};
}

int enemy_army_within(const State& st, int enemy, int cx, int cy, int radius) {
    int total = 0;
    for (int x = std::max(0, cx - radius); x <= std::min(kRow - 1, cx + radius); ++x) {
        for (int y = std::max(0, cy - radius); y <= std::min(kCol - 1, cy + radius); ++y) {
            if (st.board[x][y].owner == enemy) total += st.board[x][y].army;
        }
    }
    return total;
}

bool try_cast_defence_guard_skill(
    State& st,
    int player,
    int& my_coin,
    const Grid& enemy_threat,
    std::vector<std::vector<int>>& out_ops
) {
    if (st.my_main_x < 0 || st.my_main_y < 0) return false;
    if (my_coin < 30) return false;
    const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
    const double ratio = enemy_threat[st.my_main_x][st.my_main_y] / static_cast<double>(main_army);
    if (ratio < 0.78) return false;

    int best_idx = -1;
    int best_dist = 1e9;
    for (int i = 0; i < static_cast<int>(st.generals.size()); ++i) {
        const auto& g = st.generals[i];
        if (!g.alive || g.player != player) continue;
        if (g.type != 1 && g.type != 2) continue;
        if (g.skill_cd[3] > 0 || g.skill_rest[1] > 0) continue;
        if (blocked_by_super_weapon(st, player, g.x, g.y)) continue;
        const int d = manhattan(g.x, g.y, st.my_main_x, st.my_main_y);
        if (d > 2) continue;
        if (d < best_dist) {
            best_dist = d;
            best_idx = i;
        }
    }
    if (best_idx < 0) return false;

    out_ops.push_back({4, st.generals[best_idx].id, 4});
    st.generals[best_idx].skill_cd[3] = 10;
    st.generals[best_idx].skill_rest[1] = 10;
    my_coin -= 30;
    st.coins[player] = my_coin;
    return true;
}

bool try_cast_weaken_guard_skill(
    State& st,
    int player,
    int enemy,
    int& my_coin,
    const Grid& enemy_threat,
    std::vector<std::vector<int>>& out_ops
) {
    if (st.my_main_x < 0 || st.my_main_y < 0) return false;
    if (my_coin < 30) return false;
    const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
    const double ratio = enemy_threat[st.my_main_x][st.my_main_y] / static_cast<double>(main_army);
    if (ratio < 1.00) return false;
    if (enemy_army_within(st, enemy, st.my_main_x, st.my_main_y, 2) < 26) return false;

    int best_idx = -1;
    for (int i = 0; i < static_cast<int>(st.generals.size()); ++i) {
        const auto& g = st.generals[i];
        if (!g.alive || g.player != player) continue;
        if (g.type != 1 && g.type != 2) continue;
        if (g.skill_cd[4] > 0 || g.skill_rest[2] > 0) continue;
        if (blocked_by_super_weapon(st, player, g.x, g.y)) continue;
        if (manhattan(g.x, g.y, st.my_main_x, st.my_main_y) > 2) continue;
        best_idx = i;
        break;
    }
    if (best_idx < 0) return false;

    out_ops.push_back({4, st.generals[best_idx].id, 5});
    st.generals[best_idx].skill_cd[4] = 10;
    st.generals[best_idx].skill_rest[2] = 10;
    my_coin -= 30;
    st.coins[player] = my_coin;
    return true;
}

bool try_cast_rout_on_enemy_main(
    State& st,
    int player,
    int enemy,
    int& my_coin,
    std::vector<std::vector<int>>& out_ops
) {
    const auto enemy_main = locate_main_general(st, enemy);
    if (enemy_main.first < 0) return false;
    if (my_coin < 15) return false;
    if (st.board[enemy_main.first][enemy_main.second].army < 10) return false;

    int best_idx = -1;
    int best_score = -1e9;
    for (int i = 0; i < static_cast<int>(st.generals.size()); ++i) {
        const auto& g = st.generals[i];
        if (!g.alive || g.player != player) continue;
        if (g.type != 1 && g.type != 2) continue;
        if (g.skill_cd[1] > 0) continue;
        if (blocked_by_super_weapon(st, player, g.x, g.y)) continue;
        const int dx = std::abs(g.x - enemy_main.first);
        const int dy = std::abs(g.y - enemy_main.second);
        if (dx > 2 || dy > 2) continue;
        int score = 100 - (dx + dy) * 7 + (g.type == 1 ? 12 : 0);
        if (score > best_score) {
            best_score = score;
            best_idx = i;
        }
    }
    if (best_idx < 0) return false;

    out_ops.push_back({4, st.generals[best_idx].id, 2, enemy_main.first, enemy_main.second});
    st.generals[best_idx].skill_cd[1] = 10;
    st.board[enemy_main.first][enemy_main.second].army =
        std::max(0, st.board[enemy_main.first][enemy_main.second].army - 20);
    if (st.board[enemy_main.first][enemy_main.second].army == 0 &&
        !st.board[enemy_main.first][enemy_main.second].has_general) {
        st.board[enemy_main.first][enemy_main.second].owner = -1;
    }
    my_coin -= 15;
    st.coins[player] = my_coin;
    return true;
}

bool try_cast_command_for_attack(
    State& st,
    int player,
    int enemy,
    int& my_coin,
    std::vector<std::vector<int>>& out_ops
) {
    const auto enemy_main = locate_main_general(st, enemy);
    if (enemy_main.first < 0) return false;
    if (my_coin < 30) return false;

    bool nearby_pressure = false;
    for (int d = 0; d < kDirs; ++d) {
        const int x = enemy_main.first + kDx[d];
        const int y = enemy_main.second + kDy[d];
        if (!in_bounds(x, y)) continue;
        if (st.board[x][y].owner == player && st.board[x][y].army >= 12) {
            nearby_pressure = true;
            break;
        }
    }
    if (!nearby_pressure) return false;

    int best_idx = -1;
    int best_dist = 1e9;
    for (int i = 0; i < static_cast<int>(st.generals.size()); ++i) {
        const auto& g = st.generals[i];
        if (!g.alive || g.player != player) continue;
        if (g.type != 1 && g.type != 2) continue;
        if (g.skill_cd[2] > 0 || g.skill_rest[0] > 0) continue;
        if (blocked_by_super_weapon(st, player, g.x, g.y)) continue;
        const int d = manhattan(g.x, g.y, enemy_main.first, enemy_main.second);
        if (d > 3) continue;
        if (d < best_dist) {
            best_dist = d;
            best_idx = i;
        }
    }
    if (best_idx < 0) return false;

    out_ops.push_back({4, st.generals[best_idx].id, 3});
    st.generals[best_idx].skill_cd[2] = 10;
    st.generals[best_idx].skill_rest[0] = 10;
    my_coin -= 30;
    st.coins[player] = my_coin;
    return true;
}

bool try_move_main_general(
    State& st,
    int player,
    int enemy,
    const Grid& enemy_threat,
    std::vector<std::vector<int>>& out_ops
) {
    int main_idx = -1;
    for (int i = 0; i < static_cast<int>(st.generals.size()); ++i) {
        if (st.generals[i].alive && st.generals[i].player == player && st.generals[i].type == 1) {
            main_idx = i;
            break;
        }
    }
    if (main_idx < 0) return false;
    auto& mg = st.generals[main_idx];
    if (!in_bounds(mg.x, mg.y)) return false;
    if (blocked_by_super_weapon(st, player, mg.x, mg.y)) return false;

    const int max_step = decode_general_mobility_from_replay_level(mg.level_mob);
    if (max_step <= 0) return false;
    const int start_x = mg.x;
    const int start_y = mg.y;

    const int main_army = std::max(1, st.board[start_x][start_y].army);
    const double danger_ratio = enemy_threat[start_x][start_y] / static_cast<double>(main_army);
    const bool defensive = danger_ratio >= 0.80;
    const auto enemy_main = locate_main_general(st, enemy);

    std::array<std::array<int, kCol>, kRow> dist{};
    for (int i = 0; i < kRow; ++i) {
        for (int j = 0; j < kCol; ++j) dist[i][j] = -1;
    }
    std::queue<std::pair<int, int>> q;
    q.push({start_x, start_y});
    dist[start_x][start_y] = 0;

    double baseline = -1e100;
    double best = -1e100;
    int best_x = start_x;
    int best_y = start_y;

    while (!q.empty()) {
        auto [x, y] = q.front();
        q.pop();
        const int d0 = dist[x][y];

        int frontier = 0;
        for (int d = 0; d < kDirs; ++d) {
            const int nx = x + kDx[d];
            const int ny = y + kDy[d];
            if (!in_bounds(nx, ny)) continue;
            if (st.board[nx][ny].owner != player) ++frontier;
        }

        double score = 0.0;
        score -= enemy_threat[x][y] * (defensive ? 1.0 : 0.30);
        score += static_cast<double>(frontier) * (defensive ? 2.2 : 5.6);
        score += static_cast<double>(st.board[x][y].army) * 0.10;
        if (enemy_main.first >= 0) {
            const int cur_d = manhattan(x, y, enemy_main.first, enemy_main.second);
            score += static_cast<double>(std::max(0, 20 - cur_d)) * (defensive ? 0.3 : 0.9);
        }
        score -= static_cast<double>(d0) * (defensive ? 1.0 : 1.8);

        if (x == start_x && y == start_y) baseline = score;
        if (score > best) {
            best = score;
            best_x = x;
            best_y = y;
        }

        if (d0 >= max_step) continue;
        for (int d = 0; d < kDirs; ++d) {
            const int nx = x + kDx[d];
            const int ny = y + kDy[d];
            if (!in_bounds(nx, ny)) continue;
            if (dist[nx][ny] != -1) continue;
            if (st.board[nx][ny].owner != player) continue;
            if (st.board[nx][ny].has_general && !(nx == start_x && ny == start_y)) continue;
            if (st.board[nx][ny].type == 2 && st.tech[player][1] == 0) continue;
            dist[nx][ny] = d0 + 1;
            q.push({nx, ny});
        }
    }

    if (best_x == start_x && best_y == start_y) return false;
    if (best < baseline + 2.8) return false;

    out_ops.push_back({2, mg.id, best_x, best_y});

    Cell& src = st.board[start_x][start_y];
    Cell& dst = st.board[best_x][best_y];
    src.has_general = false;
    src.general_idx = -1;
    src.general_player = -1;
    src.general_type = 0;
    src.general_def = 1.0;

    mg.x = best_x;
    mg.y = best_y;

    dst.has_general = true;
    dst.general_idx = main_idx;
    dst.general_player = player;
    dst.general_type = 1;
    dst.general_def = decode_general_def(1, mg.level_def);

    if (st.my_main_id == mg.id) {
        st.my_main_x = best_x;
        st.my_main_y = best_y;
    }
    return true;
}

Candidate select_best_move_overlay(
    const State& st,
    int player,
    int enemy,
    int my_moves,
    int enemy_moves,
    const Grid& enemy_threat,
    int main_safe_reserve,
    const Deadline& deadline,
    bool* hard_cutoff_hit
) {
    if (hard_cutoff_hit) *hard_cutoff_hit = false;

    Candidate base = select_best_move_base(st, player, enemy_threat, main_safe_reserve, &deadline);
    if (!base.ok) return base;

    if (deadline_reached(deadline)) {
        if (hard_cutoff_hit) *hard_cutoff_hit = true;
        return base;
    }

    const OverlayTuning tuning = choose_overlay_tuning(st, enemy_threat, my_moves, base);
    if (!tuning.enabled) return base;

    auto pool = collect_move_candidates_base(st, player, enemy_threat, main_safe_reserve, tuning.pool_limit, &deadline);
    if (pool.empty()) return base;
    std::stable_sort(pool.begin(), pool.end(), [&](const Candidate& lhs, const Candidate& rhs) {
        const double lp = estimate_overlay_priority(st, lhs, player, enemy, enemy_threat, base);
        const double rp = estimate_overlay_priority(st, rhs, player, enemy, enemy_threat, base);
        if (lp != rp) return lp > rp;
        return lhs.score > rhs.score;
    });

    double base_enemy_reply_score = 0.0;
    double base_main_threat_gain = 0.0;
    double base_enemy_main_pressure = 0.0;
    {
        State base_after = st;
        apply_move(base_after, player, base);

        const Grid enemy_threat_base = compute_threat(base_after, enemy, enemy_moves);
        int my_reserve_base = main_safe_reserve;
        if (base_after.my_main_x >= 0) {
            my_reserve_base =
                std::max(3, static_cast<int>(std::ceil(enemy_threat_base[base_after.my_main_x][base_after.my_main_y] * 0.55)));
            my_reserve_base =
                std::min(my_reserve_base, std::max(3, base_after.board[base_after.my_main_x][base_after.my_main_y].army - 1));
        }

        const Grid my_threat_base = compute_threat(base_after, player, my_moves);
        const auto enemy_main_base = [&]() -> std::pair<int, int> {
            for (const auto& g : base_after.generals) {
                if (!g.alive) continue;
                if (g.player == enemy && g.type == 1) return {g.x, g.y};
            }
            return {-1, -1};
        }();
        int enemy_reserve_base = 3;
        if (in_bounds(enemy_main_base.first, enemy_main_base.second)) {
            enemy_reserve_base = std::max(
                3, static_cast<int>(std::ceil(my_threat_base[enemy_main_base.first][enemy_main_base.second] * 0.55))
            );
            enemy_reserve_base = std::min(
                enemy_reserve_base, std::max(3, base_after.board[enemy_main_base.first][enemy_main_base.second].army - 1)
            );
            base_enemy_main_pressure = my_threat_base[enemy_main_base.first][enemy_main_base.second];
        }

        const Candidate base_enemy_best =
            select_best_move_base(base_after, enemy, my_threat_base, enemy_reserve_base, &deadline);
        if (deadline_reached(deadline)) {
            if (hard_cutoff_hit) *hard_cutoff_hit = true;
            return base;
        }
        base_enemy_reply_score = std::max(0.0, base_enemy_best.score);
        if (st.my_main_x >= 0 && st.my_main_y >= 0) {
            base_main_threat_gain = enemy_threat[st.my_main_x][st.my_main_y] - enemy_threat_base[st.my_main_x][st.my_main_y];
        }
    }

    Candidate best = base;
    double best_overlay_score = base.score;
    double second_overlay_score = -1e100;
    int evaluated = 0;

    for (auto cand : pool) {
        if (deadline_reached(deadline)) {
            if (hard_cutoff_hit) *hard_cutoff_hit = true;
            break;
        }
        const bool cand_is_base = same_move(cand, base);
        const bool tactical_escape = !cand_is_base && is_tactical_escape_candidate(st, cand, player, enemy, base);
        const double raw_drop = std::max(0.0, base.score - cand.score);
        const double raw_drop_cap = tuning.max_raw_drop + (tactical_escape ? tuning.tactical_drop_relax : 0.0);
        if (!cand_is_base && raw_drop > raw_drop_cap) continue;
        State after = st;
        apply_move(after, player, cand);

        const Grid enemy_threat_after = compute_threat(after, enemy, enemy_moves);
        int my_reserve_after = main_safe_reserve;
        if (after.my_main_x >= 0) {
            my_reserve_after = std::max(3, static_cast<int>(std::ceil(enemy_threat_after[after.my_main_x][after.my_main_y] * 0.55)));
            my_reserve_after = std::min(my_reserve_after, std::max(3, after.board[after.my_main_x][after.my_main_y].army - 1));
        }

        const Grid my_threat_after = compute_threat(after, player, my_moves);
        const auto enemy_main = [&]() -> std::pair<int, int> {
            for (const auto& g : after.generals) {
                if (!g.alive) continue;
                if (g.player == enemy && g.type == 1) return {g.x, g.y};
            }
            return {-1, -1};
        }();
        int enemy_reserve = 3;
        if (in_bounds(enemy_main.first, enemy_main.second)) {
            enemy_reserve = std::max(3, static_cast<int>(std::ceil(my_threat_after[enemy_main.first][enemy_main.second] * 0.55)));
            enemy_reserve = std::min(enemy_reserve, std::max(3, after.board[enemy_main.first][enemy_main.second].army - 1));
        }

        const Candidate enemy_best = select_best_move_base(after, enemy, my_threat_after, enemy_reserve, &deadline);
        if (deadline_reached(deadline)) {
            if (hard_cutoff_hit) *hard_cutoff_hit = true;
            break;
        }
        const Candidate my_follow = select_best_move_base(after, player, enemy_threat_after, my_reserve_after, &deadline);
        if (deadline_reached(deadline)) {
            if (hard_cutoff_hit) *hard_cutoff_hit = true;
            break;
        }

        double main_threat_gain = 0.0;
        if (st.my_main_x >= 0 && st.my_main_y >= 0) {
            main_threat_gain = enemy_threat[st.my_main_x][st.my_main_y] - enemy_threat_after[st.my_main_x][st.my_main_y];
        }
        const double enemy_main_pressure =
            in_bounds(enemy_main.first, enemy_main.second) ? my_threat_after[enemy_main.first][enemy_main.second] : 0.0;

        const double enemy_reply = std::max(0.0, enemy_best.score);
        double allowed_enemy_reply = 1e100;
        double pressure_loss = 0.0;
        double allowed_pressure_loss = 1e100;
        if (!cand_is_base) {
            allowed_enemy_reply = base_enemy_reply_score + tuning.base_reply_veto_slack;
            allowed_enemy_reply += raw_drop * tuning.base_reply_drop_scale;
            allowed_enemy_reply +=
                std::max(0.0, main_threat_gain - base_main_threat_gain) * tuning.base_reply_threat_credit;

            if (tuning.pressure_anchor_enabled) {
                pressure_loss = std::max(0.0, base_enemy_main_pressure - enemy_main_pressure);
                allowed_pressure_loss = tuning.base_pressure_loss_slack + raw_drop * tuning.base_pressure_loss_drop_scale;
                allowed_pressure_loss +=
                    std::max(0.0, main_threat_gain - base_main_threat_gain) * tuning.base_pressure_loss_threat_credit;
            }
        }

        if (!cand_is_base) {
            const double cand_ref = std::max(1.0, std::max(0.0, cand.score));
            const bool dominated = enemy_reply > cand_ref * tuning.dominance_veto_ratio + tuning.dominance_veto_margin;
            if (dominated && main_threat_gain < tuning.dominance_threat_gain_min) {
                continue;
            }
            if (tuning.base_reply_veto_enabled && enemy_reply > allowed_enemy_reply &&
                main_threat_gain < tuning.dominance_threat_gain_min) {
                continue;
            }
            if (tuning.pressure_anchor_enabled && pressure_loss > allowed_pressure_loss &&
                main_threat_gain < tuning.dominance_threat_gain_min) {
                continue;
            }
        }

        double overlay_score = cand.score;
        overlay_score += tuning.my_follow_weight * std::max(0.0, my_follow.score);
        overlay_score -= tuning.enemy_weight * std::max(0.0, enemy_best.score);
        overlay_score += main_threat_gain * 0.42;
        if (!cand_is_base) {
            const double anchor_scale = tactical_escape ? tuning.tactical_anchor_scale : 1.0;
            overlay_score -= tuning.base_anchor_penalty * raw_drop * anchor_scale;
        }
        if (!cand_is_base) overlay_score -= tuning.switch_penalty;
        if (tactical_escape) {
            const double enemy_reply = std::max(0.0, enemy_best.score);
            const double tactical_ref = std::max(1.0, std::max(0.0, cand.score));
            if (enemy_reply <= tactical_ref * tuning.tactical_enemy_reply_ratio) {
                overlay_score += tuning.tactical_reply_bonus;
            }
        }
        if (!cand_is_base) {
            overlay_score -= tuning.base_reply_penalty * std::max(0.0, enemy_reply - allowed_enemy_reply);
            if (tuning.pressure_anchor_enabled) {
                overlay_score -=
                    tuning.base_pressure_loss_penalty * std::max(0.0, pressure_loss - allowed_pressure_loss);
            }
        }
        if (cand.score >= 550.0) overlay_score += 500.0;  // keep instant main-kill bias dominant

        ++evaluated;
        const double improve_margin = cand_is_base ? 0.0 : tuning.switch_margin;
        if (overlay_score > best_overlay_score + improve_margin) {
            second_overlay_score = best_overlay_score;
            cand.score = overlay_score;
            best_overlay_score = overlay_score;
            best = cand;
        } else if (overlay_score > second_overlay_score) {
            second_overlay_score = overlay_score;
        }

        // When top option is clearly dominant, stop deeper search early.
        if (evaluated >= tuning.early_stop_min_evals && second_overlay_score > -1e99 &&
            best_overlay_score - second_overlay_score >= tuning.early_stop_gap) {
            break;
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
    if (rep.contains("Weapon_cds") && rep["Weapon_cds"].is_array() && rep["Weapon_cds"].size() >= 2) {
        st.weapon_cd[0] = as_int(rep["Weapon_cds"][0], -1);
        st.weapon_cd[1] = as_int(rep["Weapon_cds"][1], -1);
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
            if (g.contains("Skill_cd") && g["Skill_cd"].is_array()) {
                for (int i = 0; i < 5; ++i) {
                    if (i < static_cast<int>(g["Skill_cd"].size())) rec.skill_cd[i] = as_int(g["Skill_cd"][i], 0);
                }
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

        const int early_move_budget = move_budget_from_tier(tech_mob_tier);
        const Deadline early_kill_deadline = make_deadline_ms(70);
        auto early_kill_seq =
            search_forced_main_kill_sequence(st, seat, enemy, early_move_budget, enemy_moves, early_kill_deadline);
        if (!early_kill_seq.empty()) {
            for (const auto& mv : early_kill_seq) {
                push_op({1, mv.sx, mv.sy, kDirCode[mv.dir], mv.num});
            }
            push_op({8});
            send_payload(format_ops(ops));
            continue;
        }

        Grid threat = compute_threat(st, enemy, enemy_moves);
        const double main_threat = (st.my_main_x >= 0) ? threat[st.my_main_x][st.my_main_y] : 0.0;
        int main_safe_reserve = 3;
        if (st.my_main_x >= 0) {
            main_safe_reserve = std::max(3, static_cast<int>(std::ceil(main_threat * 0.55)));
            main_safe_reserve = std::min(main_safe_reserve, std::max(3, st.board[st.my_main_x][st.my_main_y].army - 1));
        }

        // 1) Generals skills (ported from old Generals kill/escape mindset).
        bool used_skill = false;
        std::vector<std::vector<int>> tmp_skill_ops;
        if (try_cast_defence_guard_skill(st, seat, my_coin, threat, tmp_skill_ops)) used_skill = true;
        if (try_cast_weaken_guard_skill(st, seat, enemy, my_coin, threat, tmp_skill_ops)) used_skill = true;
        if (try_cast_rout_on_enemy_main(st, seat, enemy, my_coin, tmp_skill_ops)) used_skill = true;
        if (try_cast_command_for_attack(st, seat, enemy, my_coin, tmp_skill_ops)) used_skill = true;
        for (auto& op : tmp_skill_ops) push_op(op);

        if (used_skill) {
            threat = compute_threat(st, enemy, enemy_moves);
            const int skill_move_budget = move_budget_from_tier(tech_mob_tier);
            const Deadline skill_kill_deadline = make_deadline_ms(65);
            auto skill_kill_seq =
                search_forced_main_kill_sequence(st, seat, enemy, skill_move_budget, enemy_moves, skill_kill_deadline);
            if (!skill_kill_seq.empty()) {
                for (const auto& mv : skill_kill_seq) {
                    push_op({1, mv.sx, mv.sy, kDirCode[mv.dir], mv.num});
                }
                push_op({8});
                send_payload(format_ops(ops));
                continue;
            }
        }

        // 2) Defensive priority: main general defense when pressure is high.
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

        // 3) Mobility tech first (mirrors old AI's move-tempo preference).
        if (tech_mob_tier == 1 && my_coin >= 80 && st.round >= 35 && owned_cells >= 12) {
            push_op({5, 1});
            my_coin -= 80;
            tech_mob_tier = 2;
            st.tech[seat][0] = 2;
        } else if (tech_mob_tier == 2 && my_coin >= 150 && st.round >= 140 && owned_cells >= 25) {
            push_op({5, 1});
            my_coin -= 150;
            tech_mob_tier = 3;
            st.tech[seat][0] = 3;
        }

        // 4) Climb tech when mountain frontier is dense.
        if (st.tech[seat][1] == 0 && my_coin >= 100 && st.round >= 40 && count_adj_mountains(st, seat) >= 3) {
            push_op({5, 2});
            my_coin -= 100;
            st.tech[seat][1] = 1;
        }

        // 5) Main general growth.
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

        // 6) Main general reposition (Generals-like tempo action before army sweep).
        std::vector<std::vector<int>> gen_move_ops;
        if (try_move_main_general(st, seat, enemy, threat, gen_move_ops)) {
            for (auto& op : gen_move_ops) push_op(op);
            threat = compute_threat(st, enemy, enemy_moves);
        }

        // 7) Recruit sub generals on active frontier.
        if (my_coin >= 50 && owned_cells >= 10) {
            const auto recruit = choose_recruit_cell(st, seat, threat);
            if (recruit.first != -1) {
                push_op({7, recruit.first, recruit.second});
                my_coin -= 50;
            }
        }

        // 8) Multi-step army actions (core from old Generals-AI style).
        const int move_budget = move_budget_from_tier(tech_mob_tier);
        const Deadline decision_deadline = make_deadline_ms(kSearchStepBudgetMs);
        for (int step = 0; step < move_budget; ++step) {
            threat = compute_threat(st, enemy, enemy_moves);
            if (st.my_main_x >= 0) {
                const double t = threat[st.my_main_x][st.my_main_y];
                main_safe_reserve = std::max(3, static_cast<int>(std::ceil(t * 0.55)));
                main_safe_reserve = std::min(main_safe_reserve, std::max(3, st.board[st.my_main_x][st.my_main_y].army - 1));
            }
            bool hard_cutoff_hit = false;
            Candidate cand = select_best_move_overlay(
                st, seat, enemy, move_budget, enemy_moves, threat, main_safe_reserve, decision_deadline, &hard_cutoff_hit
            );
            if (!cand.ok || cand.score < 1.0) break;
            push_op({1, cand.sx, cand.sy, kDirCode[cand.dir], cand.num});
            apply_move(st, seat, cand);
            if (hard_cutoff_hit) break;
        }

        push_op({8});
        send_payload(format_ops(ops));
    }

    return 0;
}
