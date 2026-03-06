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

constexpr int kRow = 19;
constexpr int kCol = 19;
int gActiveRows = kRow;
int gActiveCols = kCol;

constexpr int kDirs = 4;
const int kDx[kDirs] = {-1, 1, 0, 0};   // up, down, left, right
const int kDy[kDirs] = {0, 0, -1, 1};
const int kDirCode[kDirs] = {1, 2, 3, 4};
constexpr int kSearchStepBudgetMs = 200;
constexpr int kOverlayMinPool = 6;
constexpr int kOverlayMaxPool = 14;
constexpr int kOverlayStableMaxPool = 8;
constexpr int kThreatSourceProbeCap = 4;
constexpr int kThreatSourceAlertCap = 2;
constexpr double kDuelCloseSourceProbeDanger = 0.28;
constexpr double kDuelCloseSourceProbeDangerCritical = 0.48;

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
    int board_rows = kRow;
    int board_cols = kCol;
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
    double dominance_veto_ratio = 1e9;
    double dominance_veto_margin = 1e9;
    double dominance_threat_gain_min = 0.0;
    bool base_reply_veto_enabled = true;
    double base_reply_veto_slack = 1e9;
    double base_reply_drop_scale = 0.0;
    double base_reply_threat_credit = 0.0;
    double base_reply_penalty = 0.0;
    double followup_raw_drop_cap = 1e9;
    double followup_skip_penalty = 0.0;
    double endgame_stable_signal = 0.0;
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

bool extract_turn_fast(const std::string& line, int& turn) {
    const std::string key = "\"Turn\"";
    size_t pos = line.find(key);
    if (pos == std::string::npos) return false;
    pos += key.size();
    while (pos < line.size() && (line[pos] == ' ' || line[pos] == '\t' || line[pos] == '\n' || line[pos] == '\r')) {
        ++pos;
    }
    if (pos >= line.size() || line[pos] != ':') return false;
    ++pos;
    while (pos < line.size() && (line[pos] == ' ' || line[pos] == '\t' || line[pos] == '\n' || line[pos] == '\r')) {
        ++pos;
    }
    if (pos >= line.size()) return false;
    int sign = 1;
    if (line[pos] == '-') {
        sign = -1;
        ++pos;
    }
    if (pos >= line.size() || line[pos] < '0' || line[pos] > '9') return false;
    int64_t value = 0;
    while (pos < line.size() && line[pos] >= '0' && line[pos] <= '9') {
        value = value * 10 + static_cast<int64_t>(line[pos] - '0');
        if (value > static_cast<int64_t>(std::numeric_limits<int>::max())) {
            value = static_cast<int64_t>(std::numeric_limits<int>::max());
            break;
        }
        ++pos;
    }
    turn = sign * static_cast<int>(value);
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
    return x >= 0 && x < gActiveRows && y >= 0 && y < gActiveCols;
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

int count_threat_sources_to_cell(const State& st, int enemy, int enemy_moves, int tx, int ty, int cap = kThreatSourceProbeCap) {
    if (!in_bounds(tx, ty)) return 0;
    if (cap <= 0) return 0;
    const int target_owner = st.board[tx][ty].owner;
    const double target_def = defence_multiplier(st, tx, ty, target_owner);
    int sources = 0;
    for (int ex = 0; ex < kRow; ++ex) {
        for (int ey = 0; ey < kCol; ++ey) {
            const Cell& src = st.board[ex][ey];
            if (src.owner != enemy || src.army <= 1) continue;
            const int d = manhattan(ex, ey, tx, ty);
            if (d > enemy_moves) continue;
            const double atk = attack_multiplier(st, ex, ey, enemy);
            const double projected = static_cast<double>(src.army - 1) * atk;
            if (projected >= target_def * 0.60) {
                ++sources;
                if (sources >= cap) return cap;
            }
        }
    }
    return sources;
}

int apply_reserved_main_floor(
    const State& st,
    int current_floor,
    double main_threat,
    int main_threat_sources
) {
    if (st.my_main_x < 0 || st.my_main_y < 0) return current_floor;
    const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
    const double danger_ratio = main_threat / static_cast<double>(main_army);
    int bonus = 0;
    if (main_threat_sources >= 4) bonus += 1;
    if (danger_ratio >= 0.85) bonus += 1;
    if (danger_ratio >= 1.05) bonus += 1;
    const int capped = std::max(3, main_army - 1);
    return std::min(capped, current_floor + bonus);
}

bool should_enable_reserved_gate(double main_threat, int main_army) {
    if (main_army <= 0) return false;
    return main_threat / static_cast<double>(main_army) >= 0.62;
}

int apply_reserved_release_floor(const State& st, int current_floor, double main_threat) {
    if (st.my_main_x < 0 || st.my_main_y < 0) return current_floor;
    const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
    const double danger_ratio = main_threat / static_cast<double>(main_army);
    // ANTWAR mapping: reserved is for danger states; in safe states release one step conservatism.
    if (danger_ratio < 0.42) return std::max(3, current_floor - 1);
    return current_floor;
}

int apply_skill_window_reserve_floor(const State& st, int current_floor, bool enemy_skill_window, double main_danger) {
    if (!enemy_skill_window) return current_floor;
    if (st.my_main_x < 0 || st.my_main_y < 0) return current_floor;
    const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
    int bonus = 1;
    if (main_danger >= 0.78) bonus = 2;
    if (main_danger >= 1.05) bonus = 3;
    const int capped = std::max(3, main_army - 1);
    return std::min(capped, current_floor + bonus);
}

int choose_threat_source_probe_cap(double main_danger, bool reserve_gate, bool duel_close) {
    // ANTWar global_state mapping: danger enters a stronger branch directly, without extra latch state.
    if (reserve_gate) return kThreatSourceProbeCap;
    if (!duel_close) return 0;
    if (main_danger >= kDuelCloseSourceProbeDangerCritical) return kThreatSourceProbeCap;
    if (main_danger >= kDuelCloseSourceProbeDanger) return kThreatSourceAlertCap;
    return 0;
}

bool detect_enemy_skill_window_near_main(const State& st, int enemy) {
    if (st.my_main_x < 0 || st.my_main_y < 0) return false;
    for (const auto& g : st.generals) {
        if (!g.alive || g.player != enemy) continue;
        if (g.type != 1 && g.type != 2) continue;
        if (!in_bounds(g.x, g.y)) continue;

        const int dx = std::abs(g.x - st.my_main_x);
        const int dy = std::abs(g.y - st.my_main_y);
        const int dist = dx + dy;

        const bool rout_ready = g.skill_cd[1] <= 0 && dx <= 2 && dy <= 2;
        const bool command_ready = g.skill_cd[2] <= 0 && dist <= 3;
        const bool weaken_ready = g.skill_cd[4] <= 0 && dist <= 2;
        if (rout_ready || command_ready || weaken_ready) return true;
    }
    return false;
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

int sum_owned_army(const State& st, int player) {
    int total = 0;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            if (st.board[x][y].owner != player) continue;
            total += std::max(0, st.board[x][y].army);
        }
    }
    return total;
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

int count_sub_generals_alive(const State& st, int player) {
    int cnt = 0;
    for (const auto& g : st.generals) {
        if (!g.alive) continue;
        if (g.player != player) continue;
        if (g.type == 2) ++cnt;
    }
    return cnt;
}

int compute_recruit_coin_buffer(
    bool reserve_state,
    bool duel_close,
    int sub_gap
) {
    // Generals mapping: keep a small stable reserve before expansion spending.
    // ANTWar mapping: reserved danger state raises the reserve floor.
    int buffer = reserve_state ? 30 : 10;
    if (duel_close && sub_gap <= 0) buffer += 10;
    if (sub_gap > 0) buffer -= std::min(10, sub_gap * 5);
    if (buffer < 0) buffer = 0;
    if (buffer > 40) buffer = 40;
    return buffer;
}

struct RecruitPlan {
    double aggression = 0.0;
    int coin_buffer = 10;
    int main_dist_cap = 10;
    int owned_need = 10;
    double accept_threshold = 20.0;
};

RecruitPlan choose_recruit_plan(
    bool reserve_state,
    bool duel_close,
    int sub_gap,
    int main_threat_sources,
    bool enemy_skill_window,
    int territory_lead,
    int army_lead
) {
    RecruitPlan plan;
    plan.coin_buffer = compute_recruit_coin_buffer(reserve_state, duel_close, sub_gap);

    // Merge threat-origin and reserved-state control into one aggression score:
    // fewer branch combinations than source_alert + attack_window split logic.
    double aggression = duel_close ? 0.30 : 0.14;
    aggression += std::min(0.27, static_cast<double>(std::max(0, sub_gap)) * 0.09);
    aggression -= std::min(0.28, static_cast<double>(std::max(0, -sub_gap)) * 0.07);
    // Merge threat-origin and enemy-skill pressure into one continuous penalty.
    const double source_signal =
        std::clamp(static_cast<double>(std::max(0, main_threat_sources)) / static_cast<double>(kThreatSourceProbeCap), 0.0, 1.0);
    const double skill_signal = enemy_skill_window ? 1.0 : 0.0;
    const double pressure_signal = std::clamp(0.78 * source_signal + 0.22 * skill_signal, 0.0, 1.0);
    aggression -= 0.14 * pressure_signal;
    // Generals impact mapping: if board impact is already favorable, recruit less aggressively.
    // ANTWar mapping: behind-state allows controlled catch-up aggression.
    const double terr_signal = std::clamp(static_cast<double>(territory_lead) / 28.0, -1.0, 1.0);
    const double army_signal = std::clamp(static_cast<double>(army_lead) / 220.0, -1.0, 1.0);
    const double lead_signal = 0.55 * terr_signal + 0.45 * army_signal;
    aggression -= 0.20 * std::max(0.0, lead_signal);
    aggression += 0.10 * std::max(0.0, -lead_signal);
    if (reserve_state) aggression -= 0.38;
    plan.aggression = std::clamp(aggression, 0.0, 1.0);

    plan.coin_buffer += static_cast<int>(std::lround((1.0 - plan.aggression) * 10.0));
    plan.coin_buffer += static_cast<int>(std::lround(pressure_signal * 2.0));
    plan.coin_buffer = std::clamp(plan.coin_buffer, 0, 50);

    plan.main_dist_cap = 9 + static_cast<int>(std::lround(plan.aggression * 3.0));  // [9, 12]
    if (reserve_state) plan.main_dist_cap = std::min(plan.main_dist_cap, 9);
    plan.main_dist_cap = std::clamp(plan.main_dist_cap, 8, 12);

    plan.owned_need = std::clamp(10 - static_cast<int>(std::lround(plan.aggression * 2.0)), 8, 10);
    plan.accept_threshold = std::clamp(20.0 - plan.aggression * 4.5, 15.5, 20.0);
    return plan;
}

std::pair<int, int> choose_recruit_cell(
    const State& st,
    int player,
    const Grid& threat,
    double accept_threshold = 20.0,
    double aggression = 0.0,
    int main_dist_cap = -1
) {
    aggression = std::clamp(aggression, 0.0, 1.0);
    const double front_weight = 20.0 + 2.0 * aggression;
    const double main_support_weight = 0.75 - 0.30 * aggression;
    const double enemy_main_weight = 1.0 + 0.8 * aggression;
    double best = -1e100;
    int bx = -1;
    int by = -1;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner != player) continue;
            if (c.has_general) continue;
            if (blocked_by_super_weapon(st, player, x, y)) continue;

            int d_my_main = -1;
            if (st.my_main_x >= 0 && st.my_main_y >= 0) {
                d_my_main = manhattan(x, y, st.my_main_x, st.my_main_y);
                if (main_dist_cap >= 0 && d_my_main > main_dist_cap) continue;
            }

            int front = 0;
            for (int d = 0; d < kDirs; ++d) {
                const int nx = x + kDx[d];
                const int ny = y + kDy[d];
                if (!in_bounds(nx, ny)) continue;
                if (st.board[nx][ny].owner != player) ++front;
            }
            if (front == 0) continue;

            double score = front * front_weight + static_cast<double>(c.army) * 0.4 - threat[x][y] * 0.3;
            if (d_my_main >= 0) {
                score += std::max(0, 16 - d_my_main) * main_support_weight;
            }
            if (st.enemy_main_x >= 0) {
                const int d_enemy_main = manhattan(x, y, st.enemy_main_x, st.enemy_main_y);
                score += std::max(0, 24 - d_enemy_main) * enemy_main_weight;
            }
            if (score > best) {
                best = score;
                bx = x;
                by = y;
            }
        }
    }
    if (best < accept_threshold) return {-1, -1};
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
    double main_danger,
    int main_threat_sources,
    int my_moves,
    const Candidate& base
) {
    OverlayTuning tuning;
    tuning.pool_limit = choose_overlay_pool_limit(st, enemy_threat, my_moves);

    const bool duel_close = st.my_main_x >= 0 && st.enemy_main_x >= 0 &&
                            manhattan(st.my_main_x, st.my_main_y, st.enemy_main_x, st.enemy_main_y) <= 9;
    const int my_sub_count = count_sub_generals_alive(st, st.seat);
    const int enemy_sub_count = count_sub_generals_alive(st, 1 - st.seat);
    const double sub_gap_signal =
        std::clamp(static_cast<double>(std::max(0, enemy_sub_count - my_sub_count)) / 3.0, 0.0, 1.0);
    const double opening_signal = std::clamp((60.0 - static_cast<double>(st.round)) / 60.0, 0.0, 1.0);
    const double opening_sub_pressure = duel_close ? opening_signal * sub_gap_signal : 0.0;
    const int territory_lead = count_owned_cells(st, st.seat) - count_owned_cells(st, 1 - st.seat);
    const int army_lead = sum_owned_army(st, st.seat) - sum_owned_army(st, 1 - st.seat);
    const double terr_lead_signal = std::clamp(static_cast<double>(territory_lead) / 32.0, -1.0, 1.0);
    const double army_lead_signal = std::clamp(static_cast<double>(army_lead) / 260.0, -1.0, 1.0);
    const double lead_signal = 0.52 * terr_lead_signal + 0.48 * army_lead_signal;
    const double ahead_signal = std::max(0.0, lead_signal);
    const double endgame_signal = std::clamp((static_cast<double>(st.round) - 120.0) / 60.0, 0.0, 1.0);

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

    // Simplified risk model:
    // - Generals mapping: threat-origin count contributes continuously (no extra branch state).
    // - ANTWar mapping: danger-state caution is controlled by one scalar score.
    double source_pressure = 0.0;
    if (main_threat_sources > 0) {
        source_pressure = std::min(0.22, 0.05 * static_cast<double>(main_threat_sources));
    }
    if (duel_close && main_threat_sources > 0) {
        source_pressure = std::min(0.22, source_pressure + 0.03);
    }
    const double duel_pressure = duel_close ? 0.08 : 0.0;
    const double risk_score = main_danger + source_pressure + duel_pressure;
    if (risk_score < 0.42) {
        tuning.enabled = false;
        return tuning;
    }

    const double risk_alpha = std::max(0.0, std::min(1.0, (risk_score - 0.42) / 0.60));
    // Smooth cap avoids threshold jitter from piecewise pool switches.
    const int smooth_pool_cap = kOverlayStableMaxPool + static_cast<int>(std::lround(risk_alpha * 2.0));  // [8, 10]
    tuning.pool_limit = std::min(tuning.pool_limit, smooth_pool_cap);

    tuning.base_reply_veto_enabled = true;
    tuning.conservative = false;
    tuning.my_follow_weight = 0.34;
    tuning.enemy_weight = 0.58 + 0.10 * risk_alpha;
    tuning.switch_margin = 0.7;
    tuning.switch_penalty = 0.0;
    tuning.base_anchor_penalty = 0.14 + 0.10 * risk_alpha;
    tuning.max_raw_drop = 30.0 - 10.0 * risk_alpha;
    tuning.dominance_veto_ratio = 1.55;
    tuning.dominance_veto_margin = 18.0;
    tuning.dominance_threat_gain_min = 3.0 + 2.0 * risk_alpha;
    tuning.base_reply_veto_slack = 18.0 - 4.0 * risk_alpha;
    tuning.base_reply_drop_scale = 0.32 + 0.12 * risk_alpha;
    tuning.base_reply_threat_credit = 1.60;
    tuning.base_reply_penalty = 0.04 + 0.04 * risk_alpha;
    // ANTWar reserved mapping: under danger, keep search budget tighter.
    tuning.followup_raw_drop_cap = 16.0 - 8.0 * risk_alpha;  // [8, 16]
    tuning.followup_skip_penalty = 1.5 + 1.5 * risk_alpha;
    // Early duel with enemy sub advantage: evaluate more follow-up lines and tighten risky switches.
    // Generals mapping: threat-origin pressure extends tactical verification depth instead of adding states.
    tuning.base_anchor_penalty += 0.06 * opening_sub_pressure;
    tuning.max_raw_drop -= 6.0 * opening_sub_pressure;
    tuning.base_reply_veto_slack -= 3.0 * opening_sub_pressure;
    tuning.followup_raw_drop_cap += 6.0 * opening_sub_pressure;
    tuning.followup_skip_penalty -= 0.8 * opening_sub_pressure;
    // ANTWar global-state mapping: when already ahead, reserve margin and reduce risky switch budget.
    tuning.base_anchor_penalty += 0.10 * ahead_signal;
    tuning.max_raw_drop -= 4.0 * ahead_signal;
    tuning.base_reply_veto_slack -= 2.5 * ahead_signal;
    tuning.base_reply_drop_scale -= 0.08 * ahead_signal;
    // Simplified late-game lock: only apply in low-danger ahead states to avoid over-conservative regression.
    const double calm_signal = std::clamp((0.92 - risk_score) / 0.50, 0.0, 1.0);
    tuning.endgame_stable_signal = ahead_signal * endgame_signal * calm_signal;
    tuning.switch_margin += 0.30 * tuning.endgame_stable_signal;
    tuning.base_anchor_penalty += 0.05 * tuning.endgame_stable_signal;
    tuning.max_raw_drop = std::clamp(tuning.max_raw_drop, 10.0, 30.0);
    tuning.switch_margin = std::clamp(tuning.switch_margin, 0.6, 1.6);
    tuning.base_reply_veto_slack = std::clamp(tuning.base_reply_veto_slack, 10.0, 18.0);
    tuning.base_reply_drop_scale = std::clamp(tuning.base_reply_drop_scale, 0.18, 0.48);
    tuning.followup_raw_drop_cap = std::clamp(tuning.followup_raw_drop_cap, 8.0, 20.0);
    tuning.followup_skip_penalty = std::clamp(tuning.followup_skip_penalty, 0.6, 3.2);
    tuning.early_stop_gap = 18 + static_cast<int>(std::lround(risk_alpha * 6.0));
    tuning.early_stop_min_evals = 4 + static_cast<int>(std::lround((1.0 - risk_alpha) * 2.0));
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

bool candidate_key_less(const Candidate& a, const Candidate& b) {
    if (a.sx != b.sx) return a.sx < b.sx;
    if (a.sy != b.sy) return a.sy < b.sy;
    if (a.dir != b.dir) return a.dir < b.dir;
    if (a.num != b.num) return a.num < b.num;
    return false;
}

bool candidate_better(const Candidate& a, const Candidate& b) {
    constexpr double kScoreTieEps = 1e-9;
    if (a.score > b.score + kScoreTieEps) return true;
    if (b.score > a.score + kScoreTieEps) return false;
    return candidate_key_less(a, b);
}

bool candidate_seq_less(const std::vector<Candidate>& a, const std::vector<Candidate>& b) {
    const size_t n = std::min(a.size(), b.size());
    for (size_t i = 0; i < n; ++i) {
        if (candidate_key_less(a[i], b[i])) return true;
        if (candidate_key_less(b[i], a[i])) return false;
    }
    return a.size() < b.size();
}

void push_candidate(std::vector<Candidate>& out, const Candidate& cand, int limit) {
    if (!cand.ok) return;
    constexpr double kDedupScoreEps = 1e-9;
    for (auto& keep : out) {
        if (!same_move(keep, cand)) continue;
        if (cand.score > keep.score + kDedupScoreEps) keep.score = cand.score;
        return;
    }
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
    // Generals/ANTWar-style budget control: keep one best send plan per attack arc in kill-only branching.
    std::array<std::array<std::array<unsigned char, kDirs>, kCol>, kRow> seen_arc{};
    std::vector<Candidate> compact;
    compact.reserve(pool.size());
    for (const auto& cand : pool) {
        if (!in_bounds(cand.sx, cand.sy) || cand.dir < 0 || cand.dir >= kDirs) continue;
        if (seen_arc[cand.sx][cand.sy][cand.dir]) continue;
        seen_arc[cand.sx][cand.sy][cand.dir] = 1;
        compact.push_back(cand);
    }
    pool.swap(compact);
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

bool may_force_main_kill_in_budget(const State& st, int player, int enemy, int move_budget) {
    if (move_budget <= 0) return false;
    const auto enemy_main = locate_main_general(st, enemy);
    if (enemy_main.first < 0 || enemy_main.second < 0) return false;

    int min_dist = std::numeric_limits<int>::max();
    for (int x = 0; x < st.board_rows; ++x) {
        for (int y = 0; y < st.board_cols; ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner != player || c.army <= 1) continue;
            min_dist = std::min(min_dist, manhattan(x, y, enemy_main.first, enemy_main.second));
        }
    }
    if (min_dist == std::numeric_limits<int>::max()) return false;
    return min_dist <= move_budget;
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
    // Generals-like `steps < dist` infeasibility pruning before expensive beam search.
    if (!may_force_main_kill_in_budget(root, player, enemy, move_budget)) return {};

    struct Node {
        State st;
        std::vector<Candidate> seq;
        double heuristic = -1e100;
    };
    auto node_better = [](const Node& a, const Node& b) {
        constexpr double kHeuristicTieEps = 1e-9;
        if (a.heuristic > b.heuristic + kHeuristicTieEps) return true;
        if (b.heuristic > a.heuristic + kHeuristicTieEps) return false;
        return candidate_seq_less(a.seq, b.seq);
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
                        node_better
                    );
                    next.resize(static_cast<size_t>(beam_width * 3));
                }
            }
        }

        if (next.empty()) break;
        std::sort(next.begin(), next.end(), node_better);
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

double evaluate_nuclear_boom_value(const State& st, int player, int cx, int cy) {
    const int enemy = 1 - player;
    double score = 0.0;
    for (int x = std::max(0, cx - 1); x <= std::min(kRow - 1, cx + 1); ++x) {
        for (int y = std::max(0, cy - 1); y <= std::min(kCol - 1, cy + 1); ++y) {
            const Cell& c = st.board[x][y];
            if (c.owner == enemy) score += static_cast<double>(c.army) * 11.0;
            if (c.owner == player) score -= static_cast<double>(c.army) * 18.0;

            if (!c.has_general || c.general_idx < 0 || c.general_idx >= static_cast<int>(st.generals.size())) continue;
            const General& g = st.generals[c.general_idx];
            if (!g.alive) continue;
            if (g.type == 1) {
                if (g.player == enemy) score += static_cast<double>(c.army) * 8.0 + 120.0;
                if (g.player == player) score -= static_cast<double>(c.army) * 16.0 + 260.0;
            } else if (g.type == 2) {
                if (g.player == enemy) score += 380.0;
                else if (g.player == player) score -= 520.0;
                else score += 260.0;
            } else if (g.type == 3) {
                if (g.player == enemy) score += 260.0;
                else if (g.player == player) score -= 320.0;
                else score += 180.0;
            }
        }
    }

    const auto enemy_main = locate_main_general(st, enemy);
    if (in_bounds(enemy_main.first, enemy_main.second)) {
        const int d = manhattan(cx, cy, enemy_main.first, enemy_main.second);
        if (d <= 1) score += 180.0;
    }
    return score;
}

void apply_nuclear_boom_estimate(State& st, int player, int cx, int cy) {
    for (int x = std::max(0, cx - 1); x <= std::min(kRow - 1, cx + 1); ++x) {
        for (int y = std::max(0, cy - 1); y <= std::min(kCol - 1, cy + 1); ++y) {
            Cell& c = st.board[x][y];
            if (c.has_general && c.general_idx >= 0 && c.general_idx < static_cast<int>(st.generals.size())) {
                General& g = st.generals[c.general_idx];
                if (g.alive && g.type == 1) {
                    c.army = c.army / 2;
                } else {
                    g.alive = false;
                    c.army = 0;
                    c.owner = -1;
                    c.has_general = false;
                    c.general_idx = -1;
                    c.general_player = -1;
                    c.general_type = 0;
                    c.general_def = 1.0;
                }
            } else {
                c.army = 0;
                c.owner = -1;
            }
        }
    }

    Weapon w{};
    w.type = 1;
    w.player = player;
    w.x = cx;
    w.y = cy;
    w.rest = 5;
    st.weapons.push_back(w);
    st.weapon_cd[player] = 50;
}

bool try_use_nuclear_boom(
    State& st,
    int player,
    std::vector<std::vector<int>>& out_ops
) {
    if (st.tech[player][3] <= 0) return false;
    if (st.weapon_cd[player] != 0) return false;

    double best_score = -1e100;
    int best_x = -1;
    int best_y = -1;
    for (int x = 0; x < kRow; ++x) {
        for (int y = 0; y < kCol; ++y) {
            double score = evaluate_nuclear_boom_value(st, player, x, y);
            if (score > best_score) {
                best_score = score;
                best_x = x;
                best_y = y;
            }
        }
    }
    if (best_x < 0 || best_score < 520.0) return false;

    out_ops.push_back({6, 1, best_x, best_y});
    apply_nuclear_boom_estimate(st, player, best_x, best_y);
    return true;
}

bool try_upgrade_subgeneral_production(
    State& st,
    int player,
    int& my_coin,
    const Grid& enemy_threat,
    std::vector<std::vector<int>>& out_ops
) {
    int best_idx = -1;
    double best_score = -1e100;
    for (int i = 0; i < static_cast<int>(st.generals.size()); ++i) {
        const auto& g = st.generals[i];
        if (!g.alive || g.player != player || g.type != 2) continue;
        if (!in_bounds(g.x, g.y)) continue;
        if (blocked_by_super_weapon(st, player, g.x, g.y)) continue;

        int cost = 0;
        if (g.level_prod <= 1) cost = 40;
        else if (g.level_prod == 2) cost = 80;
        else continue;
        if (my_coin < cost) continue;

        const Cell& c = st.board[g.x][g.y];
        const double safety = static_cast<double>(c.army) * c.general_def - enemy_threat[g.x][g.y];
        if (safety < 8.0) continue;

        int frontier = 0;
        for (int d = 0; d < kDirs; ++d) {
            const int nx = g.x + kDx[d];
            const int ny = g.y + kDy[d];
            if (!in_bounds(nx, ny)) continue;
            if (st.board[nx][ny].owner != player) ++frontier;
        }

        double score = 0.0;
        score += (g.level_prod <= 1) ? 100.0 : 56.0;
        score += safety * 1.2;
        score += static_cast<double>(frontier) * 12.0;
        score -= static_cast<double>(cost) * 0.4;
        if (score > best_score) {
            best_score = score;
            best_idx = i;
        }
    }
    if (best_idx < 0 || best_score < 35.0) return false;

    out_ops.push_back({3, st.generals[best_idx].id, 1});
    if (st.generals[best_idx].level_prod <= 1) my_coin -= 40;
    else my_coin -= 80;
    st.generals[best_idx].level_prod = std::min(3, st.generals[best_idx].level_prod + 1);
    st.coins[player] = my_coin;
    return true;
}

Candidate select_best_move_overlay(
    const State& st,
    int player,
    int enemy,
    int my_moves,
    int enemy_moves,
    const Grid& enemy_threat,
    double main_danger,
    int main_threat_sources,
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

    const OverlayTuning tuning = choose_overlay_tuning(
        st, enemy_threat, main_danger, main_threat_sources, my_moves, base
    );
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
        const double raw_drop = std::max(0.0, base.score - cand.score);
        if (!cand_is_base && raw_drop > tuning.max_raw_drop) continue;
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
        double main_threat_gain = 0.0;
        if (st.my_main_x >= 0 && st.my_main_y >= 0) {
            main_threat_gain = enemy_threat[st.my_main_x][st.my_main_y] - enemy_threat_after[st.my_main_x][st.my_main_y];
        }
        const double enemy_reply = std::max(0.0, enemy_best.score);
        double allowed_enemy_reply = 1e100;
        if (!cand_is_base) {
            allowed_enemy_reply = base_enemy_reply_score + tuning.base_reply_veto_slack;
            allowed_enemy_reply += raw_drop * tuning.base_reply_drop_scale;
            allowed_enemy_reply +=
                std::max(0.0, main_threat_gain - base_main_threat_gain) * tuning.base_reply_threat_credit;
        }

        if (!cand_is_base && tuning.base_reply_veto_enabled) {
            const double cand_ref = std::max(1.0, std::max(0.0, cand.score));
            const double dominated_cap = cand_ref * tuning.dominance_veto_ratio + tuning.dominance_veto_margin;
            const double reply_surplus = std::max(0.0, enemy_reply - allowed_enemy_reply);
            const double dominance_surplus = std::max(0.0, enemy_reply - dominated_cap);
            const double threat_credit = std::max(0.0, main_threat_gain - tuning.dominance_threat_gain_min);
            const double lock_penalty = tuning.endgame_stable_signal * std::max(0.0, raw_drop - 5.0);
            // Generals threat-origin mapping: keep one continuous risk gate with a micro endgame lock term.
            const double reply_risk = reply_surplus + 0.45 * dominance_surplus - 1.25 * threat_credit +
                                      0.15 * lock_penalty;
            if (reply_risk > 0.0) continue;
        }

        double my_follow_score = 0.0;
        const bool should_eval_follow = cand_is_base || raw_drop <= tuning.followup_raw_drop_cap;
        // Generals threat-origin mapping: low-priority branches skip deeper follow-up eval.
        if (should_eval_follow) {
            const Candidate my_follow =
                select_best_move_base(after, player, enemy_threat_after, my_reserve_after, &deadline);
            if (deadline_reached(deadline)) {
                if (hard_cutoff_hit) *hard_cutoff_hit = true;
                break;
            }
            my_follow_score = std::max(0.0, my_follow.score);
        }

        double overlay_score = cand.score;
        overlay_score += tuning.my_follow_weight * my_follow_score;
        overlay_score -= tuning.enemy_weight * std::max(0.0, enemy_best.score);
        overlay_score += main_threat_gain * 0.42;
        if (!cand_is_base) {
            overlay_score -= tuning.base_anchor_penalty * raw_drop;
        }
        if (!cand_is_base) overlay_score -= tuning.switch_penalty;
        if (!cand_is_base && !should_eval_follow) overlay_score -= tuning.followup_skip_penalty;
        if (!cand_is_base) {
            overlay_score -= tuning.base_reply_penalty * std::max(0.0, enemy_reply - allowed_enemy_reply);
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
    st.board_rows = kRow;
    st.board_cols = kCol;

    for (int i = 0; i < kRow; ++i) {
        for (int j = 0; j < kCol; ++j) {
            st.board[i][j] = Cell{};
            st.board[i][j].owner = -2;
            st.board[i][j].type = 2;
        }
    }

    int inferred_rows = 0;
    int inferred_cols = 0;
    bool has_shape_from_cell_type = false;
    if (rep.contains("Cell_type") && rep["Cell_type"].is_string()) {
        const std::string ct = rep["Cell_type"].get<std::string>();
        const int n = static_cast<int>(ct.size());
        const int root = static_cast<int>(std::llround(std::sqrt(static_cast<double>(n))));
        if (root > 0 && root * root == n && root <= kRow && root <= kCol) {
            inferred_rows = root;
            inferred_cols = root;
            has_shape_from_cell_type = true;
        }
    }

    int max_seen_x = -1;
    int max_seen_y = -1;
    auto scan_pos = [&](const json& arr) {
        if (!arr.is_array() || arr.size() < 2) return;
        const int x = as_int(arr[0], -1);
        const int y = as_int(arr[1], -1);
        if (x >= 0) max_seen_x = std::max(max_seen_x, x);
        if (y >= 0) max_seen_y = std::max(max_seen_y, y);
    };
    if (rep.contains("Cells") && rep["Cells"].is_array()) {
        for (const auto& item : rep["Cells"]) {
            if (!item.is_array() || item.size() < 1) continue;
            scan_pos(item[0]);
        }
    }
    if (rep.contains("Generals") && rep["Generals"].is_array()) {
        for (const auto& g : rep["Generals"]) {
            if (!g.is_object() || !g.contains("Position")) continue;
            scan_pos(g["Position"]);
        }
    }
    if (rep.contains("Weapons") && rep["Weapons"].is_array()) {
        for (const auto& w : rep["Weapons"]) {
            if (!w.is_object() || !w.contains("Position")) continue;
            scan_pos(w["Position"]);
        }
    }

    if (!has_shape_from_cell_type) {
        if (max_seen_x >= 0 && max_seen_y >= 0) {
            inferred_rows = max_seen_x + 1;
            inferred_cols = max_seen_y + 1;
        } else {
            inferred_rows = kRow;
            inferred_cols = kCol;
        }
    } else {
        if (max_seen_x >= 0) inferred_rows = std::max(inferred_rows, max_seen_x + 1);
        if (max_seen_y >= 0) inferred_cols = std::max(inferred_cols, max_seen_y + 1);
    }

    inferred_rows = std::max(1, std::min(kRow, inferred_rows));
    inferred_cols = std::max(1, std::min(kCol, inferred_cols));
    st.board_rows = inferred_rows;
    st.board_cols = inferred_cols;

    for (int i = 0; i < st.board_rows; ++i) {
        for (int j = 0; j < st.board_cols; ++j) {
            st.board[i][j].owner = -1;
            st.board[i][j].type = 0;
        }
    }
    const auto in_active_bounds = [&](int x, int y) {
        return x >= 0 && x < st.board_rows && y >= 0 && y < st.board_cols;
    };

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
        const size_t need = static_cast<size_t>(st.board_rows * st.board_cols);
        if (cell_type.size() >= need) {
            for (int i = 0; i < st.board_rows; ++i) {
                for (int j = 0; j < st.board_cols; ++j) {
                    const char c = cell_type[static_cast<size_t>(i * st.board_cols + j)];
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
            if (!in_active_bounds(x, y)) continue;
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
            if (in_active_bounds(rec.x, rec.y)) st.weapons.push_back(rec);
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
            if (!in_active_bounds(rec.x, rec.y)) continue;

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
        for (int i = 0; i < st.board_rows; ++i) {
            for (int j = 0; j < st.board_cols; ++j) {
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
        int fast_turn = seat;
        if (extract_turn_fast(line, fast_turn) && fast_turn != seat) continue;

        json rep;
        try {
            rep = json::parse(line);
        } catch (...) {
            continue;
        }
        if (!rep.is_object()) continue;

        // Keep seat pinned to km handshake.
        // Saiblo streams may set Player to frame owner (can differ from our side).
        int turn = seat;
        if (rep.contains("Turn")) turn = as_int(rep["Turn"], seat);
        if (turn != seat) continue;

        State st;
        if (!parse_state_from_rep(rep, seat, st)) {
            send_payload("8\n");
            continue;
        }
        gActiveRows = st.board_rows;
        gActiveCols = st.board_cols;

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
        int main_threat_sources = 0;
        if (st.my_main_x >= 0) {
            const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
            main_safe_reserve = std::max(3, static_cast<int>(std::ceil(main_threat * 0.55)));
            main_safe_reserve = std::min(main_safe_reserve, std::max(3, main_army - 1));
            // Generals threat-origin count + ANTWAR reserved mapping (only in high-pressure state).
            if (should_enable_reserved_gate(main_threat, main_army)) {
                main_threat_sources = count_threat_sources_to_cell(
                    st, enemy, enemy_moves, st.my_main_x, st.my_main_y, kThreatSourceProbeCap
                );
                main_safe_reserve = apply_reserved_main_floor(st, main_safe_reserve, main_threat, main_threat_sources);
            }
            main_safe_reserve = apply_reserved_release_floor(st, main_safe_reserve, main_threat);
        }

        // 1) Super-weapon usage (Generals old `use_weapon` style).
        std::vector<std::vector<int>> weapon_ops;
        if (try_use_nuclear_boom(st, seat, weapon_ops)) {
            for (auto& op : weapon_ops) push_op(op);
            threat = compute_threat(st, enemy, enemy_moves);
        }

        // 2) Generals skills (ported from old Generals kill/escape mindset).
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

        // 3) Defensive priority: main general defense when pressure is high.
        if (st.my_main_id >= 0 && my_coin >= 20 && st.my_main_x >= 0 &&
            !blocked_by_super_weapon(st, seat, st.my_main_x, st.my_main_y)) {
            const int main_army = st.board[st.my_main_x][st.my_main_y].army;
            const double cur_main_threat = threat[st.my_main_x][st.my_main_y];
            if (st.my_main_def <= 1 && cur_main_threat > main_army * 0.65) {
                push_op({3, st.my_main_id, 2});
                my_coin -= 20;
                st.my_main_def = 2;
            } else if (st.my_main_def == 2 && my_coin >= 50 && cur_main_threat > main_army * 1.1) {
                push_op({3, st.my_main_id, 2});
                my_coin -= 50;
                st.my_main_def = 3;
            }
        }

        // 4) Mobility tech first (mirrors old AI's move-tempo preference).
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

        // 5) Climb tech when mountain frontier is dense.
        if (st.tech[seat][1] == 0 && my_coin >= 100 && st.round >= 40 && count_adj_mountains(st, seat) >= 3) {
            push_op({5, 2});
            my_coin -= 100;
            st.tech[seat][1] = 1;
        }

        // 6) Main general growth.
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

        // 7) Sub-general economy upgrade when safe (old upgrade module parity).
        std::vector<std::vector<int>> sub_up_ops;
        if (my_coin >= 40 && try_upgrade_subgeneral_production(st, seat, my_coin, threat, sub_up_ops)) {
            for (auto& op : sub_up_ops) push_op(op);
        }

        // 8) Main general reposition (Generals-like tempo action before army sweep).
        std::vector<std::vector<int>> gen_move_ops;
        if (try_move_main_general(st, seat, enemy, threat, gen_move_ops)) {
            for (auto& op : gen_move_ops) push_op(op);
            threat = compute_threat(st, enemy, enemy_moves);
        }

        // 9) Recruit sub generals on active frontier.
        // ANTWar mapping: only enter aggressive recruiting window when not in reserved danger state.
        if (my_coin >= 50) {
            bool reserve_state = false;
            if (st.my_main_x >= 0 && st.my_main_y >= 0) {
                const int main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
                const double main_threat_now = threat[st.my_main_x][st.my_main_y];
                reserve_state = should_enable_reserved_gate(main_threat_now, main_army);
            }

            const bool duel_close_recruit = st.my_main_x >= 0 && st.my_main_y >= 0 && st.enemy_main_x >= 0 &&
                                            st.enemy_main_y >= 0 &&
                                            manhattan(st.my_main_x, st.my_main_y, st.enemy_main_x, st.enemy_main_y) <= 10;
            const int my_sub_count = count_sub_generals_alive(st, seat);
            const int enemy_sub_count = count_sub_generals_alive(st, enemy);
            const int sub_gap = enemy_sub_count - my_sub_count;
            const bool enemy_skill_window = detect_enemy_skill_window_near_main(st, enemy);
            const int enemy_owned_cells = count_owned_cells(st, enemy);
            const int territory_lead = owned_cells - enemy_owned_cells;
            const int army_lead = sum_owned_army(st, seat) - sum_owned_army(st, enemy);
            int recruit_main_threat_sources = 0;
            if (duel_close_recruit && st.my_main_x >= 0 && st.my_main_y >= 0) {
                // Generals threat-origin mapping: cheap source probe for recruit safety gate.
                recruit_main_threat_sources =
                    count_threat_sources_to_cell(st, enemy, enemy_moves, st.my_main_x, st.my_main_y, 2);
            }
            const RecruitPlan recruit_plan =
                choose_recruit_plan(
                    reserve_state,
                    duel_close_recruit,
                    sub_gap,
                    recruit_main_threat_sources,
                    enemy_skill_window,
                    territory_lead,
                    army_lead
                );
            if (owned_cells >= recruit_plan.owned_need && my_coin >= 50 + recruit_plan.coin_buffer) {
                const auto recruit = choose_recruit_cell(
                    st, seat, threat, recruit_plan.accept_threshold, recruit_plan.aggression, recruit_plan.main_dist_cap
                );
                if (recruit.first != -1) {
                    push_op({7, recruit.first, recruit.second});
                    my_coin -= 50;
                }
            }
        }

        // 10) Multi-step army actions (core from old Generals-AI style).
        const int move_budget = move_budget_from_tier(tech_mob_tier);
        const Deadline decision_deadline = make_deadline_ms(kSearchStepBudgetMs);
        for (int step = 0; step < move_budget; ++step) {
            threat = compute_threat(st, enemy, enemy_moves);
            double step_main_threat = 0.0;
            double step_main_danger = 0.0;
            int step_main_army = 1;
            int step_main_threat_sources = 0;
            const bool step_enemy_skill_window = detect_enemy_skill_window_near_main(st, enemy);
            if (st.my_main_x >= 0) {
                step_main_threat = threat[st.my_main_x][st.my_main_y];
                step_main_army = std::max(1, st.board[st.my_main_x][st.my_main_y].army);
                step_main_danger = step_main_threat / static_cast<double>(step_main_army);
                main_safe_reserve = std::max(3, static_cast<int>(std::ceil(step_main_threat * 0.55)));
                main_safe_reserve = std::min(main_safe_reserve, std::max(3, st.board[st.my_main_x][st.my_main_y].army - 1));

                const bool reserve_gate = should_enable_reserved_gate(step_main_threat, step_main_army);
                const bool duel_close_step = st.enemy_main_x >= 0 && st.enemy_main_y >= 0 &&
                                             manhattan(st.my_main_x, st.my_main_y, st.enemy_main_x, st.enemy_main_y) <= 9;
                const int source_probe_cap = choose_threat_source_probe_cap(step_main_danger, reserve_gate, duel_close_step);
                // Generals+ANTWar mapping: saturating threat-origin probe with danger-state branching.
                if (source_probe_cap > 0) {
                    step_main_threat_sources = count_threat_sources_to_cell(
                        st, enemy, enemy_moves, st.my_main_x, st.my_main_y, source_probe_cap
                    );
                }

                if (reserve_gate) {
                    main_safe_reserve =
                        apply_reserved_main_floor(st, main_safe_reserve, step_main_threat, step_main_threat_sources);
                }
                main_safe_reserve = apply_reserved_release_floor(st, main_safe_reserve, step_main_threat);
                main_safe_reserve =
                    apply_skill_window_reserve_floor(st, main_safe_reserve, step_enemy_skill_window, step_main_danger);
            }
            bool hard_cutoff_hit = false;
            Candidate cand = select_best_move_overlay(
                st,
                seat,
                enemy,
                move_budget,
                enemy_moves,
                threat,
                step_main_danger,
                step_main_threat_sources,
                main_safe_reserve,
                decision_deadline,
                &hard_cutoff_hit
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
