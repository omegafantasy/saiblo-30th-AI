#include "../control.hpp"

// construct a controller object
Controller c;

// basic game process for player 0
void game_process0()
{
    while (true)
    {
        std::cerr << "add operations" << std::endl;
        c.add_to_self_operations(BuildTower, 5, 9);
        c.add_to_self_operations(BuildTower, 5, 3);
        c.add_to_self_operations(BuildTower, 5, 15);
        std::cerr << "send operations" << std::endl;
        c.send_self_operations();
        std::cerr << "apply self operations" << std::endl;
        c.apply_self_operations();
        std::cerr << "read opponent operations" << std::endl;
        c.read_opponent_operations();
        std::cerr << "apply opponent operations" << std::endl;
        c.apply_opponent_operations();
        std::cerr << "read round data" << std::endl;
        c.read_round_info();
    }
}

// basic game process for player 1
void game_process1()
{
    while (true)
    {
        std::cerr << "read opponent operations" << std::endl;
        c.read_opponent_operations();
        std::cerr << "apply opponent operations" << std::endl;
        c.apply_opponent_operations();
        std::cerr << "add operations" << std::endl;
        c.add_to_self_operations(BuildTower, 13, 9);
        c.add_to_self_operations(BuildTower, 13, 3);
        c.add_to_self_operations(BuildTower, 13, 15);
        std::cerr << "send operations" << std::endl;
        c.send_self_operations();
        std::cerr << "apply self operations" << std::endl;
        c.apply_self_operations();
        std::cerr << "read round data" << std::endl;
        c.read_round_info();
    }
}

int main()
{
    if (c.self_player_id == 0)
    {
        std::cerr << "Player 0 initialized" << std::endl;
        game_process0();
    }
    else
    {
        std::cerr << "Player 1 initialized" << std::endl;
        game_process1();
    }
}