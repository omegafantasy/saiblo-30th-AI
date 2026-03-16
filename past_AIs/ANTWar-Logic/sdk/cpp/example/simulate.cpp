#include "../control.hpp"
#include "../simulate.hpp"

// construct a controller object
Controller c;
Simulator s(c);

// basic game process for player 0
void game_process0()
{
    Operation build_tower0(OperationType::BuildTower, 5, 9);
    Operation build_tower1(OperationType::BuildTower, 5, 3);
    Operation build_tower2(OperationType::BuildTower, 5, 15);
    Operation upgrade_tower0(OperationType::UpgradeTower, 0, TowerType::Heavy);
    Operation upgrade_tower1(OperationType::UpgradeTower, 1, TowerType::Quick);
    Operation upgrade_tower2(OperationType::UpgradeTower, 2, TowerType::Mortar);

    std::ofstream fout("replay0.out");

    while (true)
    {
        std::cerr << "add self operations" << std::endl;
        c.add_to_self_operations(build_tower0);
        c.add_to_self_operations(build_tower1);
        c.add_to_self_operations(build_tower2);
        c.add_to_self_operations(upgrade_tower0);
        c.add_to_self_operations(upgrade_tower1);
        c.add_to_self_operations(upgrade_tower2);
        for (auto& op: c.get_self_operations())
            if (s.get_info().is_operation_valid(0, op))
                s.add_operation_of_player(0, op);

        std::cerr << "send self operations" << std::endl;
        c.send_self_operations();

        std::cerr << "apply self operations" << std::endl;
        c.apply_self_operations();
        s.apply_operations_of_player(0);

        std::cerr << "read opponent operations" << std::endl;
        c.read_opponent_operations();
        for (auto& op: c.get_opponent_operations())
            if (s.get_info().is_operation_valid(1, op))
                s.add_operation_of_player(1, op);

        std::cerr << "apply opponent operations" << std::endl;
        c.apply_opponent_operations();
        s.apply_operations_of_player(1);
        
        std::cerr << "read round data" << std::endl;
        c.read_round_info();
        s.next_round();
        s.get_info().dump(fout);

        fout.flush();
    }

    fout.close();
}

// basic game process for player 1
void game_process1()
{
    Operation build_tower0(OperationType::BuildTower, 13, 9);
    Operation build_tower1(OperationType::BuildTower, 13, 3);
    Operation build_tower2(OperationType::BuildTower, 13, 15);

    while (true)
    {
        std::cerr << "read opponent operations" << std::endl;
        c.read_opponent_operations();

        std::cerr << "apply opponent operations" << std::endl;
        c.apply_opponent_operations();
        for (auto& op: c.get_opponent_operations())
            if (s.get_info().is_operation_valid(0, op))
                s.add_operation_of_player(0, op);

        std::cerr << "add operations" << std::endl;
        c.add_to_self_operations(build_tower0);
        c.add_to_self_operations(build_tower1);
        c.add_to_self_operations(build_tower2);
        for (auto& op: c.get_self_operations())
            if (s.get_info().is_operation_valid(1, op))
                s.add_operation_of_player(1, op);
        
        std::cerr << "send operations" << std::endl;
        c.send_self_operations();
        
        std::cerr << "apply self operations" << std::endl;
        c.apply_self_operations();
        s.apply_operations_of_player(1);

        std::cerr << "read round data" << std::endl;
        c.read_round_info();
        s.next_round();
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