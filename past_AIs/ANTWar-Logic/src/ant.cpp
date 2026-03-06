#include "ant.h"
#include "map.h"

#include <cassert>
// Create an ant.

const int hp_list[3] = {10, 25, 50};
Ant::Ant(int player, int id, int x, int y, int level)
    : player(player),
      id(id),             // Set player and id (may be generated automatically?)
      pos_x(x), pos_y(y), // Set initial position
      level(level),       // Set level
      hp(hp_list[level]), hp_limit(hp_list[level]), // Set HP and its limit
      path(),                                        // Init path
      age(0)
{}

// Get the player to which the ant belong.
int Ant::get_player() const { return player; }

// Get the ant's id.
int Ant::get_id() const { return id; }

// Get the x coordinate of the ant's current position.
int Ant::get_x() const { return pos_x; }

// Get the y coordinate of the ant's current position.
int Ant::get_y() const { return pos_y; }

// Get the ant's HP.
int Ant::get_hp() const { return hp; }

// Get the ant's level.
int Ant::get_level() const { return level; }
// Get the HP limit of the ant.
int Ant::get_hp_limit() const { return hp_limit; }

// Get the length of path
int Ant::get_path_len() const { return path.size(); }

void Ant::increase_age() { age++; }

// Get the status of the ant.
Ant::Status Ant::get_status() const {
    if (hp <= 0)
        return Status::Fail;
    if (player && pos_x == PLAYER_0_BASE_CAMP_X &&
        pos_y == PLAYER_0_BASE_CAMP_Y)
        return Status::Success;
    if (!player && pos_x == PLAYER_1_BASE_CAMP_X &&
        pos_y == PLAYER_1_BASE_CAMP_Y)
        return Status::Success;
    if (age > age_limit)
        return Status::TooOld;
    if (is_frozen || all_frozen)
        return Status::Frozen;
    return Status::Alive;
}

void Ant::set_hp_true(int change) { hp += change; }
// Change HP
void Ant::set_hp(int change) {
    if (shield > 0) {
        change = 0;
        shield--;
    } else if (defend && change < 0 && (-change) * 2 < hp_limit) {
        change = 0;
    }
    hp += change;
    if (hp > hp_limit)
        hp = hp_limit;
}

// Move the ant in specified direction.
// Note that the given direction should be valid (possible to reach),
// so it will NOT be checked.
void Ant::move(int direction) {
    const int d[2][6][2] = {
        {{0, 1}, {-1, 0}, {0, -1}, {1, -1}, {1, 0}, {1, 1}},
        {{-1, 1}, {-1, 0}, {-1, -1}, {0, -1}, {1, 0}, {0, 1}}};
    // path may be used elsewhere
    //  Change (Unfinished)
    if (direction == -1)
        return;

    pos_x += d[pos_y % 2][direction][0];
    pos_y += d[pos_y % 2][direction][1];
}