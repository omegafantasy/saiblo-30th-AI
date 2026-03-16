#include "../control.hpp"
#include "../simulate.hpp"

int main()
{    
    Controller c;
    Simulator s(c);

    // clear "replay.out"
    std::ofstream fout("replay.out");

    Operation build_tower0(OperationType::BuildTower, 5, 9);
    Operation upgrade_tower0(OperationType::UpgradeTower, 0, TowerType::Heavy);
    
    for (int i = 0; i < 300; ++i)
    {
        // Dump or show
        // s.get_info().show();
        s.get_info().dump(fout);
        // Add player0's operation
        s.add_operation_of_player(0, build_tower0);
        s.add_operation_of_player(0, upgrade_tower0);
        // Apply player0's operation
        s.apply_operations_of_player(0);
        // Add player1's operation
        
        // Apply player1's operation
        s.apply_operations_of_player(1);
        // Next round
        if (s.next_round() != GameState::Running)
            break;
    }
    
    return 0;
}