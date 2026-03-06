#ifndef __ANT_H__
#define __ANT_H__

#include <vector>
class Ant {
  private:
    int player;
    int id;
    int pos_x, pos_y;
    int level;
    int hp;
    int age;
    int hp_limit;

  public:
    // 暂时...?
    std::vector<int> path;
    static const int age_limit = 32;
    int shield=0;
    bool defend=false;
    bool is_frozen = false;
    bool all_frozen = false;
    bool is_chosen = false;
    bool invincible = false;
    enum Status {
        Alive,   // Still alive
        Success, // Reach the other camp
        Fail,    // No HP
        TooOld,  // Too old
        Frozen   // Forzen
    };

    Ant(int player, int id, int x, int y, int level);

    int get_player() const;
    int get_id() const;
    int get_x() const;
    int get_y() const;
    int get_hp() const;
    int get_hp_limit() const;
    int get_level() const;
    int get_path_len() const;

    void increase_age();

    Status get_status() const;

    void set_hp(int change);
    void set_hp_true(int change);
    void move(int direction);
};

#endif