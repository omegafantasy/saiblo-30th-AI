# C++ SDK User Guide

## 0. 预备工作
请先前往Saiblo官网下载SDK包，确认内含`control.hpp`、`io.hpp`、`game_info.hpp`、`common.hpp`、`simulate.hpp`、`AI.cpp`。

`control.hpp`、`io.hpp`提供与Judger的通讯功能，包括读取初始化信息、读取回合信息、读取对手的操作、发送你的操作。

`game_info.hpp`、`common.hpp`提供游戏状态的维护功能，包括塔、兵营、蚂蚁、大本营、金币、道具、信息素等信息。

`simulate.hpp`提供逻辑维护代码，能模拟游戏逻辑的主要流程，包括塔攻击蚂蚁、蚂蚁移动、兵营生成蚂蚁、道具的获取和生效等。

`AI.cpp`为一个简易AI的代码，其中的框架可以沿用至你的AI程序中，或者你也可以直接在其上进行修改。

## 1. 开始！
首先，为了实现基本的通讯功能，需要先包含`control.hpp`头文件。
```cpp
#include "control.hpp"
```
然后创建一个全局的`Controller`对象，你可以将它理解为与Judger进行交互的控制器。  
Controller的构造函数中会直接调用游戏初始化信息的读取方法，包括你的选手id（先后手信息）和本局游戏的道具生成列表。
```cpp
Controller c;
```
再写一个main函数，根据游戏规则，先手和后手有不同的游戏流程。
```cpp
int main()
{
    if (c.self_player_id == 0)
        game_process0();    // 先手的游戏流程
    else
        game_process1();    // 后手的游戏流程
}
```
简易的先手的游戏流程如下：
```cpp
void game_process0() // 先手
{
    while (true)
    {
        c.read_round_data(); // 读取局面信息  
        c.add_to_self_operations(TargetPointSet, 27, 15); // 添加本回合自己的操作，例如设置蚂蚁目标点为对方的大本营
        // 添加本回合自己的其他操作……
        c.send_self_operations();   // 发送本回合自己的所有操作
        c.read_opponent_operations();   // 读取本回合对手的操作
    }
}
```
简易的后手的游戏流程如下：
```cpp
void game_process1()  // 后手
{
    while (true)
    {
        c.read_round_data();  // 读取局面信息
        c.read_opponent_operations();   // 读取本回合对手的操作
        c.apply_opponent_operations();  // 将本回合对手的操作应用到局面
        c.add_to_self_operations(TargetPointSet, 3, 15);  // 添加本回合自己的操作，例如设置蚂蚁目标点为对方的大本营
        // 添加本回合自己的其他操作……
        c.send_self_operations();   // 发送本回合自己的所有操作
    }
}
```
## Control Next Round 顺序
首先开始新回合
    1. round++
    2. read_round_info
然后需根据read得到的数据反推上回合结算流程，得到建筑、蚂蚁、经济在**本回合开始时**的信息。
    1. towers
    2. barracks
    3. ants
    4. global_pheromone_attenuation
    5. update_pheromone_for_ants
    6. clear_dead
    7. coin
    8. base
此时局面信息已是逻辑在**本回合开始时**的信息。特别地，蚂蚁也在本回合开始时的位置，故可以更新道具。
    1.  update_items_state
    2.  get_items

## 2. 样例AI的优化方向

## 3. API Reference