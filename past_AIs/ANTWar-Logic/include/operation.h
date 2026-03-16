#ifndef __OPERATION_H__
#define __OPERATION_H__

#include "json.hpp"
#include <string>
#include <vector>

class Operation {
  private:
    static constexpr int INVALID = -1;

    int type;
    int id;
    int args;

    // This could be a class for wider use.
    struct Point {
        int x = INVALID;
        int y = INVALID;
    };
    Point pos;

  public:
    // Constructor
    Operation(); // Set all with INVALID
    Operation(int type, int id, int args, int pos_x, int pos_y);

    // Getter
    int get_id() const;
    int get_args() const;
    int get_pos_x() const;
    int get_pos_y() const;

    // Operation type
    enum Type {
        TowerBuild = 11,
        TowerUpgrade = 12,
        TowerDestroy = 13,
        LightingStorm = 21,
        EMPBlaster = 22,
        Deflectors = 23,
        EmergencyEvasion = 24,
        BarrackUpgrade = 31,
        AntUpgrade = 32,
        // PutAnt = 91,
        // DeleteAnt = 92,
        // MaxCoin = 93,
        Error = -1,
    };

    Type get_operation_type() const;

    // Methods for serialization/deserialization
    NLOHMANN_DEFINE_TYPE_INTRUSIVE_WITH_DEFAULT(Point, x, y)
    NLOHMANN_DEFINE_TYPE_INTRUSIVE_WITH_DEFAULT(Operation, type, id, args, pos)
};

// Construct a vector of operationsfrom json.
std::vector<Operation> read_operation(std::string name);

#endif