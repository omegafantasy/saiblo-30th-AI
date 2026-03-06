#include "operation.h"
#include <fstream>
#include <iostream>

using json = nlohmann::json;

// Operation

Operation::Operation() : type(INVALID), id(INVALID), args(INVALID), pos() {}

Operation::Operation(int type, int id, int args, int pos_x, int pos_y)
    : type(type), id(id), args(args), pos({pos_x, pos_y}) {}

int Operation::get_id() const { return id; }

int Operation::get_args() const { return args; }

int Operation::get_pos_x() const { return pos.x; }

int Operation::get_pos_y() const { return pos.y; }

Operation::Type Operation::get_operation_type() const {
    // All the items must be checked, so a mask is used here to check all bits
    // at once. Compute the mask
    unsigned char mask = 0;
    if (id != INVALID)
        mask |= 0x1; // 001
    if (args != INVALID)
        mask |= 0x2; // 010
    if (pos.x != INVALID && pos.y != INVALID)
        mask |= 0x4; // 100

    // Check if valid and return the type of the operation
    switch(type) {
        case 11: {
            if (mask == 0x4)return (Type)type;
            break;
        }
        case 12: {
            if (mask == 0x3)return (Type)type;
            break;
        }
        case 13: {
            if (mask == 0x1)return (Type)type;
            break;
        }
        case 21: {
            if (mask == 0x4)return (Type)type;
            break;
        }
        case 22: {
            if (mask == 0x4)return (Type)type;
            break;
        }
        case 23: {
            if (mask == 0x4)return (Type)type;
            break;
        }
        case 24: {
            if (mask == 0x4)return (Type)type;
            break;
        }
        case 31: {
            if (mask == 0x0)return (Type)type;
            break;
        }
        case 32: {
            if (mask == 0x0)return (Type)type;
            break;
        }
        default: {
            return Type::Error;
        }
    }
            return Type::Error;
}

std::vector<Operation> read_operation(std::string name) {
    json j;
    std::ifstream fin(name);
    fin >> j;

    return j; // j is an Operation vector
}
