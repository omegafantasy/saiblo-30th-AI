#include "building.h"
#include <cmath>
#include <algorithm>


const int cd_list[3] = {4, 2, 1};
// judge whether ant can be generated
bool Headquarter::create_new_ant(int round) {
    if (!(round % cd_list[cd_level])) {
        return true;
    } else {
        return false;
    }
}
// current cd
int Headquarter::get_cd_level() const { return cd_level; }
// ants'hp_limit this round
int Headquarter::get_ant_level() const { return ant_level; }
// upgrade ant hp
bool Headquarter::ant_upgrade() {
    if (ant_level == 2) return false;
    ant_level ++;
    return true;
}
bool Headquarter::barrack_upgrade() {
    if (cd_level == 2) return false;
    cd_level ++;
    return true;
}

Ant *DefenseTower::find_attack_target(std::vector<Ant> &ants) {
    int m = 30;
    Ant *candidate = nullptr;
    for (auto &ant : ants) {
        if (tower_type == TowerType::Double && 
            std::find(attacked_ants.begin(), attacked_ants.end(), ant.get_id()) != attacked_ants.end()
        ) {
            continue;
        }
        if (get_player() != ant.get_player() && ant.get_hp() > 0) {
            int dist = distance(ant.get_x(), ant.get_y(), get_x(), get_y());
            if (dist <= get_range()) {
                if (dist < m) {
                    m = dist;
                    candidate = &ant;
                }
            }
        }
    }
    return candidate;
}

Ant *DefenseTower::attack1(std::vector<Ant> &ants, Ant first_attack_ant) {
    int m = 500;
    int flag = 0;

    Ant *attacked_ant = nullptr;
    if ((abs(get_x() - first_attack_ant.get_x()) *
             abs(get_x() - first_attack_ant.get_x()) +
         abs(get_y() - first_attack_ant.get_y()) *
             abs(get_y() - first_attack_ant.get_y())) <= range * range) {
        attacked_ant = &first_attack_ant;
        flag = 1;
    }
    if (flag == 0) {
        for (auto &ant : ants) {
            if (get_player() != ant.get_player() && ant.get_hp() > 0) {
                if (distance(ant.get_x(), ant.get_y(), get_x(), get_y()) <=
                    get_range()) {
                    if (abs(get_x() - ant.get_x()) +
                            abs(get_y() - ant.get_y()) <
                        m) {
                        m = abs(get_x() - ant.get_x()) +
                            abs(get_y() - ant.get_y());
                        attack_pos_x = ant.get_x();
                        attack_pos_y = ant.get_y();
                        attacked_ant = &ant;
                    } else if (abs(get_x() - ant.get_x()) +
                                   abs(get_y() - ant.get_y()) ==
                               m) {
                        if (ant.get_path_len() > attacked_ant->get_path_len()) {
                            attack_pos_x = ant.get_x();
                            attack_pos_y = ant.get_y();
                            attacked_ant = &ant;
                        }
                    }
                }
            }
        }
    }
    return attacked_ant;
}

Ant *DefenseTower::attack2(std::vector<Ant> &ants) {
    int m = 500;
    // int flag=0;

    Ant *attacked_ant = nullptr;
    for (auto &ant : ants) {
        if (get_player() != ant.get_player() && (ant.get_hp() > 0) &&
            (!ant.is_chosen)) {
            if (distance(ant.get_x(), ant.get_y(), get_x(), get_y()) <=
                get_range()) {
                if (abs(get_x() - ant.get_x()) + abs(get_y() - ant.get_y()) <
                    m) {
                    m = abs(get_x() - ant.get_x()) + abs(get_y() - ant.get_y());
                    attack_pos_x = ant.get_x();
                    attack_pos_y = ant.get_y();
                    attacked_ant = &ant;
                } else if (abs(get_x() - ant.get_x()) +
                               abs(get_y() - ant.get_y()) ==
                           m) {
                    if (ant.get_path_len() > attacked_ant->get_path_len()) {
                        attack_pos_x = ant.get_x();
                        attack_pos_y = ant.get_y();
                        attacked_ant = &ant;
                    }
                }
            }
        }
    }
    return attacked_ant;
}
// check the type of new tower
bool DefenseTower::upgrade_type_check(int new_type) const {
    try {
        auto t = TowerType(new_type);
        return TowerType(t / 10) == tower_type;
    } catch (const std::exception &e) {
        return false;
    }
}
// Get the downgrade type of tower
TowerType DefenseTower::tower_downgrade_type() const {
    return TowerType(tower_type / 10);
}
// upgrade the tower
bool DefenseTower::upgrade(TowerType tower_type_) {
    round = 0;
    level++;
    tower_type = tower_type_;
    switch (tower_type) {
    case 1:
        damage = 15;
        spd = 2;
        range = 2;
        break;
    case 2:
        damage = 6;
        spd = 1;
        range = 3;
        break;
    case 3:
        damage = 16;
        spd = 4;
        range = 3;
        break;
    case 11:
        damage = 35;
        spd = 2;
        range = 2;
        break;
    case 12:
        damage = 15;
        spd = 2;
        range = 2;
        break;
    case 13:
        damage = 50;
        spd = 4;
        range = 3;
        break;
    case 21:
        damage = 8;
        spd = 0.5;
        range = 3;
        break;
    case 22:
        damage = 10;
        spd = 1;
        range = 4;
        break;
    case 23:
        damage = 13;
        spd = 2;
        range = 6;
        break;
    case 31:
        damage = 35;
        spd = 4;
        range = 4;
        break;
    case 32:
        damage = 30;
        spd = 3;
        range = 2;
        break;
    case 33:
        damage = 45;
        spd = 6;
        range = 5;
        break;
    default:
        break;
    }
    return true;
}

// downgrade the tower
bool DefenseTower::downgrade(TowerType tower_type_) {
    round = 0;
    level--;
    tower_type = tower_type_;
    switch (tower_type) {
    case 0:
        damage = 5;
        spd = 2;
        range = 2;
        break;
 case 1:
        damage = 15;
        spd = 2;
        range = 2;
        break;
    case 2:
        damage = 6;
        spd = 1;
        range = 3;
        break;
    case 3:
        damage = 16;
        spd = 4;
        range = 3;
        break;
    default:
        break;
    }
    return true;
}

void DefenseTower::round_damage(std::vector<Ant> &ants, int x, int y,
                                int range) {
    for (auto &ant : ants) {
        if (get_player() != ant.get_player()) {
            if (distance(ant.get_x(), ant.get_y(), x, y) <= range) {
                ant.set_hp(-get_damage());
                add_attacked_ants(ant.get_id());
            }
        }
    }
}

int DefenseTower::distance(int x0, int y0, int x1, int y1) {
    int dy = abs(y0 - y1);
    int dx;
    if (abs(y0 - y1) % 2) {
        if (x0 > x1)
            dx = std::max(0, abs(x0 - x1) - abs(y0 - y1) / 2 - (y0 % 2));
        else
            dx = std::max(0, abs(x0 - x1) - abs(y0 - y1) / 2 - (1 - (y0 % 2)));
    } else
        dx = std::max(0, abs(x0 - x1) - abs(y0 - y1) / 2);

    return dx + dy;
}

void DefenseTower::set_changed_this_round() {
    changed = true;
}

void DefenseTower::set_unchanged_before_another_round() {
    changed = false;
    attacked_ants.clear();
}

void DefenseTower::add_attacked_ants(int id) {
    attacked_ants.push_back(id);
}