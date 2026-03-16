#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace {
constexpr int kBuildTower = 11;
constexpr int kUpgradeTower = 12;

struct Tower {
    int id = -1;
    int player = -1;
    int x = -1;
    int y = -1;
    int type = -1;
    int cooldown = 0;
};

struct Ant {
    int id = -1;
    int player = -1;
    int x = -1;
    int y = -1;
    int hp = 0;
    int level = 0;
    int age = 0;
    int status = 0;
    int behavior = 0;
};

struct RoundState {
    int round = -1;
    std::vector<Tower> towers;
    std::vector<Ant> ants;
    int coins[2] = {50, 50};
    int camps_hp[2] = {50, 50};
};

using Pos = std::pair<int, int>;

const std::array<std::array<Pos, 12>, 2> kBuildOrder = {{
    {{{4, 9}, {5, 9}, {5, 7}, {6, 9}, {5, 11}, {5, 6}, {6, 7}, {6, 11}, {5, 12}, {4, 3}, {5, 3}, {7, 8}}},
    {{{14, 9}, {13, 9}, {13, 7}, {12, 9}, {13, 11}, {12, 6}, {12, 7}, {12, 11}, {12, 12}, {14, 3}, {13, 3}, {10, 8}}},
}};

const std::array<Pos, 2> kBases = {{{2, 9}, {16, 9}}};

int build_cost(int tower_count) {
    int cost = 15;
    for (int i = 0; i < tower_count; ++i) {
        cost *= 2;
    }
    return cost;
}

int hex_distance(int x0, int y0, int x1, int y1) {
    const int dy = std::abs(y0 - y1);
    int dx = 0;
    if (dy % 2) {
        if (x0 > x1) {
            dx = std::max(0, std::abs(x0 - x1) - dy / 2 - (y0 % 2));
        } else {
            dx = std::max(0, std::abs(x0 - x1) - dy / 2 - (1 - (y0 % 2)));
        }
    } else {
        dx = std::max(0, std::abs(x0 - x1) - dy / 2);
    }
    return dx + dy;
}

bool is_alive_status(int status) {
    return status == 0 || status == 4;
}

std::string send_packet_payload(const std::vector<std::array<int, 3>> &ops) {
    std::ostringstream out;
    out << ops.size() << '\n';
    for (const auto &op : ops) {
        if (op[0] == kBuildTower || op[0] == kUpgradeTower) {
            out << op[0] << ' ' << op[1] << ' ' << op[2] << '\n';
        }
    }
    return out.str();
}

void send_packet(const std::vector<std::array<int, 3>> &ops) {
    std::string payload = send_packet_payload(ops);
    uint32_t n = static_cast<uint32_t>(payload.size());
    unsigned char hdr[4];
    hdr[0] = static_cast<unsigned char>((n >> 24) & 0xFF);
    hdr[1] = static_cast<unsigned char>((n >> 16) & 0xFF);
    hdr[2] = static_cast<unsigned char>((n >> 8) & 0xFF);
    hdr[3] = static_cast<unsigned char>(n & 0xFF);
    std::cout.write(reinterpret_cast<const char *>(hdr), 4);
    std::cout << payload;
    std::cout.flush();
}

bool recv_line(std::string &line) {
    return static_cast<bool>(std::getline(std::cin, line));
}

void recv_operations_ignored() {
    std::string line;
    if (!recv_line(line)) {
        return;
    }
    int count = 0;
    try {
        count = std::stoi(line);
    } catch (...) {
        count = 0;
    }
    for (int i = 0; i < count; ++i) {
        if (!recv_line(line)) {
            return;
        }
    }
}

bool recv_round_state(RoundState &state) {
    std::string line;
    if (!recv_line(line)) {
        return false;
    }
    state.round = std::stoi(line);

    if (!recv_line(line)) {
        return false;
    }
    int tower_count = std::stoi(line);
    state.towers.clear();
    for (int i = 0; i < tower_count; ++i) {
        if (!recv_line(line)) {
            return false;
        }
        std::istringstream iss(line);
        Tower tower;
        iss >> tower.id >> tower.player >> tower.x >> tower.y >> tower.type >> tower.cooldown;
        state.towers.push_back(tower);
    }

    if (!recv_line(line)) {
        return false;
    }
    int ant_count = std::stoi(line);
    state.ants.clear();
    for (int i = 0; i < ant_count; ++i) {
        if (!recv_line(line)) {
            return false;
        }
        std::istringstream iss(line);
        Ant ant;
        iss >> ant.id >> ant.player >> ant.x >> ant.y >> ant.hp >> ant.level >> ant.age >> ant.status >> ant.behavior;
        state.ants.push_back(ant);
    }

    if (!recv_line(line)) {
        return false;
    }
    {
        std::istringstream iss(line);
        iss >> state.coins[0] >> state.coins[1];
    }
    if (!recv_line(line)) {
        return false;
    }
    {
        std::istringstream iss(line);
        iss >> state.camps_hp[0] >> state.camps_hp[1];
    }
    return true;
}

int own_tower_count(const RoundState &state, int player) {
    int count = 0;
    for (const auto &tower : state.towers) {
        if (tower.player == player && tower.type >= 0) {
            ++count;
        }
    }
    return count;
}

const Tower *first_basic_tower(const RoundState &state, int player) {
    for (const auto &tower : state.towers) {
        if (tower.player == player && tower.type == 0) {
            return &tower;
        }
    }
    return nullptr;
}

bool has_tower_at(const RoundState &state, int x, int y) {
    for (const auto &tower : state.towers) {
        if (tower.type >= 0 && tower.x == x && tower.y == y) {
            return true;
        }
    }
    return false;
}

int enemy_threat(const RoundState &state, int player) {
    const auto [bx, by] = kBases[player];
    int threat = 0;
    for (const auto &ant : state.ants) {
        if (ant.player == player || !is_alive_status(ant.status)) {
            continue;
        }
        int dist = hex_distance(ant.x, ant.y, bx, by);
        threat += std::max(0, 9 - dist) * (1 + ant.level);
    }
    return threat;
}

std::vector<std::array<int, 3>> decide(const RoundState &state, int player) {
    std::vector<std::array<int, 3>> ops;
    const int coins = state.coins[player];
    const int towers = own_tower_count(state, player);
    const int threat = enemy_threat(state, player);

    if (coins >= 60) {
        if (const Tower *tower = first_basic_tower(state, player)) {
            if (threat >= 10 || towers <= 2) {
                ops.push_back({kUpgradeTower, tower->id, 1});
                return ops;
            }
        }
    }

    const int cost = build_cost(towers);
    if (coins >= cost) {
        for (const auto &[x, y] : kBuildOrder[player]) {
            if (!has_tower_at(state, x, y)) {
                ops.push_back({kBuildTower, x, y});
                return ops;
            }
        }
    }
    return ops;
}

} // namespace

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string init;
    if (!std::getline(std::cin, init)) {
        return 0;
    }
    std::istringstream iss(init);
    int player = 0;
    int seed = 0;
    iss >> player >> seed;
    (void)seed;

    RoundState state;
    while (true) {
        if (player == 0) {
            send_packet(decide(state, player));
            recv_operations_ignored();
            if (!recv_round_state(state)) {
                break;
            }
        } else {
            recv_operations_ignored();
            send_packet(decide(state, player));
            if (!recv_round_state(state)) {
                break;
            }
        }
    }
    return 0;
}
