#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

#include "../past_AIs/Generals-AI/include/json.hpp"

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

Candidate select_best_move(const State& st, int player, const Grid& threat, int main_safe_reserve) {
    Candidate best;

    for (int sx = 0; sx < kRow; ++sx) {
        for (int sy = 0; sy < kCol; ++sy) {
            const Cell& src = st.board[sx][sy];
            if (src.owner != player || src.army <= 1) continue;
            if (blocked_by_super_weapon(st, player, sx, sy)) continue;

            const bool src_is_main = (sx == st.my_main_x && sy == st.my_main_y);
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

                    if (st.enemy_main_x >= 0) {
                        score += std::max(0, 20 - manhattan(nx, ny, st.enemy_main_x, st.enemy_main_y));
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

        // 6) Multi-step army actions (core from old Generals-AI style).
        const int move_budget = move_budget_from_tier(tech_mob_tier);
        for (int step = 0; step < move_budget; ++step) {
            threat = compute_threat(st, enemy, enemy_moves);
            if (st.my_main_x >= 0) {
                const double t = threat[st.my_main_x][st.my_main_y];
                main_safe_reserve = std::max(3, static_cast<int>(std::ceil(t * 0.55)));
                main_safe_reserve = std::min(main_safe_reserve, std::max(3, st.board[st.my_main_x][st.my_main_y].army - 1));
            }
            Candidate cand = select_best_move(st, seat, threat, main_safe_reserve);
            if (!cand.ok || cand.score < 1.0) break;
            push_op({1, cand.sx, cand.sy, kDirCode[cand.dir], cand.num});
            apply_move(st, seat, cand);
        }

        push_op({8});
        send_payload(format_ops(ops));
    }

    return 0;
}

