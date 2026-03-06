#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>

namespace {

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

bool parse_km(const std::string& line, int& seat) {
    std::istringstream iss(line);
    int k = -1;
    int seed = 0;
    std::string tail;
    if (!(iss >> k >> seed)) return false;
    if (iss >> tail) return false;
    if (k != 0 && k != 1) return false;
    seat = k;
    return true;
}

bool extract_turn(const std::string& json_line, int& turn_out) {
    const std::string key = "\"Turn\"";
    std::size_t pos = json_line.find(key);
    if (pos == std::string::npos) return false;

    pos = json_line.find(':', pos + key.size());
    if (pos == std::string::npos) return false;

    while (pos + 1 < json_line.size() &&
           (json_line[pos + 1] == ' ' || json_line[pos + 1] == '\t')) {
        ++pos;
    }

    std::size_t i = pos + 1;
    bool neg = false;
    if (i < json_line.size() && json_line[i] == '-') {
        neg = true;
        ++i;
    }

    if (i >= json_line.size() || json_line[i] < '0' || json_line[i] > '9') {
        return false;
    }

    int value = 0;
    while (i < json_line.size() && json_line[i] >= '0' && json_line[i] <= '9') {
        value = value * 10 + (json_line[i] - '0');
        ++i;
    }
    turn_out = neg ? -value : value;
    return true;
}

}  // namespace

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int seat = 0;
    std::string line;

    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;

        if (parse_km(line, seat)) {
            continue;
        }

        if (line.front() != '{' || line.back() != '}') {
            continue;
        }

        int turn = -1;
        const bool has_turn = extract_turn(line, turn);
        if (has_turn && turn != seat) {
            continue;
        }

        // Baseline legal noop: end this turn immediately.
        send_payload("8\n");
    }

    return 0;
}
