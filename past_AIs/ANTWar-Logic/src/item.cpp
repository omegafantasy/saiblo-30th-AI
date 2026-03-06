#include "item.h"

// get cd of item
int get_item_cd(ItemType type) {
    int cd[4] = {100, 100, 50, 50};
    return cd[type];
}

// get duration of item
int get_item_time(ItemType type) {
    int time[4] = {20, 20, 10, 1};
    return time[type];
}