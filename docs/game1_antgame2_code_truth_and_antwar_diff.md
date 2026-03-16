# Game1 / 蚁洋陷役2 代码真值与旧 ANTWar 差异

## 1. 结论先行

`Game1/Ant-Game` 不是全新游戏，而是以旧 `past_AIs/ANTWar-Logic` 为底座的大幅增强版。

可以直接复用的底层骨架：

- 地图与坐标体系仍然是 19x19 六边形 offset 坐标。
- 基地、塔、防守升级树、金币经济、信息素主框架都保留了旧血统。
- 旧 `ANTWar-AI` 的固定战略槽位、留钱防 EMP、塔位分组思路仍然有价值。

不能继续照搬的部分：

- 蚂蚁新增了行为类型与独立衰减计时。
- 默认寻路从确定性变成了带 softmax 的随机采样，并新增拥塞惩罚。
- 新增随机传送、超级武器区域漂移、控制免疫、蛊惑目标等机制。
- 协议、回放、公共局面字段都发生了变化。

## 2. 代码真值入口

本次分析以这些文件为绝对基准：

- `Game1/Ant-Game/game/src/game.cpp`
- `Game1/Ant-Game/game/src/ant.cpp`
- `Game1/Ant-Game/game/src/building.cpp`
- `Game1/Ant-Game/game/src/comm_judger.cpp`
- `Game1/Ant-Game/game/src/output.cpp`
- `Game1/Ant-Game/SDK/backend/engine.py`
- `Game1/Ant-Game/SDK/backend/model.py`
- `Game1/Ant-Game/SDK/utils/constants.py`

旧逻辑对照基准：

- `past_AIs/ANTWar-Logic/src/game.cpp`
- `past_AIs/ANTWar-Logic/src/ant.cpp`
- `past_AIs/ANTWar-Logic/src/building.cpp`
- `past_AIs/ANTWar-Logic/src/comm_judger.cpp`
- `past_AIs/ANTWar-Logic/src/output.cpp`

## 3. 新代码下的真实规则骨架

### 3.1 回合顺序

按代码，`Game::next_round()` / `GameState.advance_round()` 的核心顺序是：

1. 结算闪电风暴与防御塔攻击。
2. 蚂蚁移动。
3. 每 10 回合传送一次非免控型蚂蚁。
4. 更新信息素。
5. 结算到达基地、击杀、老死并移除蚂蚁。
6. 基地生成新蚂蚁。
7. 蚂蚁年龄与行为计时 +1。
8. 双方金币 +1。
9. 超级武器漂移、持续时间 -1、冷却 -1。
10. 回合数 +1；若到 512 再按血量/击杀/超级武器次数/AI 总用时/先手顺序判胜负。

这和规则页文字有几个重要不一致：

- 代码里是“先攻击，再在回合末漂移超级武器区域”，不是“先漂移再攻击”。
- 传送发生在蚂蚁移动之后、信息素之后，而不是文字描述中那种更早的阶段。
- 超级武器冷却和剩余持续时间都是在回合末结算。

### 3.2 蚂蚁新增行为系统

相较旧 ANTWar，新版 `Ant` 多了：

- `behavior`: `DEFAULT / CONSERVATIVE / RANDOM / BEWITCHED / CONTROL_FREE`
- `behavior_rounds`
- `behavior_expiry`
- `target_x / target_y`
- `pending_behavior`
- `last_move` 和 `trail_cells`

对应效果：

- `DEFAULT`: 依据信息素、吸引度、拥塞惩罚，softmax 采样前进方向。
- `CONSERVATIVE`: 不做采样，直接取最好方向。
- `RANDOM`: 在合法方向中均匀随机。
- `BEWITCHED`: 朝目标格推进。
- `CONTROL_FREE`: 免疫控制，移动规则和 `CONSERVATIVE` 一样。

行为衰减：

- `RANDOM` 5 回合后退化为 `DEFAULT`。
- `CONSERVATIVE / BEWITCHED / CONTROL_FREE` 也有独立 5 回合衰减。
- `BEWITCHED` 提前到达目标也会退化。

### 3.3 新增拥塞与随机传送

旧 ANTWar 主要是确定性信息素寻路；新版新增：

- 默认型移动会给“己方蚂蚁过多”的方向扣分。
- 每 10 回合随机选取约 20% 的非免控蚂蚁传送。
- 传送后 `last_move` 会重置，因此回头路限制也会被刷新。

这意味着：

- 旧版那种假定前线稳定、可长时间靠信息素渐进逼近的判断会明显失真。
- 任何依赖“上一回合位置推导下一步唯一方向”的旧推理都需要改写。

## 4. 塔与超级武器：代码真值和旧版差异

### 4.1 防御塔数值变化

与旧 `ANTWar-Logic/src/building.cpp` 相比，新版代码真值有这些关键变化：

| 塔 | 旧值 | 新值 | 说明 |
| --- | --- | --- | --- |
| Heavy | 15/2/2 | 20/2/2 | 一级重炮伤害提高 |
| Heavy+ | 35/2/2 | 35/2/3 | 射程提高 |
| Cannon(13) | 50/4/3 | 10/3/3 | 数值大改，且语义改成蛊惑塔 |
| Double | 10/1/4 | 7/1/4 | 伤害下降 |
| Sniper | 13/2/6 | 15/2/6 | 伤害提高 |
| Pulse | 30/3/2 | 12/3/2 | 伤害大降，但仍带控制效果 |

注：表中格式为 `伤害/间隔/范围`。

### 4.2 13 号塔的“命名未改、语义已改”

代码枚举名仍然是 `CANNON`，但实际行为已经不是旧版炮塔：

- `game/src/game.cpp` 中，13 号塔命中后会把蚂蚁变成 `Bewitched`。
- 若蚂蚁仍在自己半场，目标会被设为敌方基地。
- 若蚂蚁已经在对方半场，目标会被设为己方半场随机合法点。

因此：

- 规则页把它写成 `Bewitch`，在语义上是对的。
- 代码里沿用了旧枚举名 `CANNON`，这是历史命名残留。

### 4.3 控制类塔的新行为

旧版控制主要是冰冻/护盾；新版还有：

- `Ice`: 冻结 1 回合，解冻后转 `RANDOM`。
- `Cannon(13)`: 施加 `BEWITCHED`。
- `Pulse(32)`: 把命中的蚂蚁转成 `RANDOM`。
- `CONTROL_FREE` 蚂蚁对这些控制都免疫。

### 4.4 超级武器与旧版差异

新旧都保留了 4 类超级武器，但代码真值上有两个必须注意的点：

1. `LightningStorm` / `EMPBlaster` 会在回合末随机漂移一格。
2. `EmergencyEvasion` 在代码里不是“永久保存 2 层直到用光”。

代码真实语义更接近：

- 释放 `EmergencyEvasion` 当回合，区域内蚂蚁得到 `shield = 2`。
- 但该效果本身的 `duration = 1`，回合末就会被移除。
- 下一次 `prepare_ants_for_attack()` 时，如果区域效果已经不在，蚂蚁会转为 `CONTROL_FREE`。

也就是说，当前实现是“短时 2 层盾 + 结束后转免控”，不是规则页文字描述的“盾层永久存在直到耗尽”。

## 5. 协议和公共局面变化

### 5.1 输入输出协议

新版平台通信仍然是：

- `stdin` 读文本协议
- `stdout` 返回“4 字节大端长度 + 文本内容”

但 AI 内部的推荐实现已经改成：

- `AI/protocol.py` 读初始化、对手操作、公共局面。
- `AI/main.py` 负责 session 循环。
- `SDK/backend/runtime.py` + `SDK/backend/engine.py` 在本地重建完整状态。

### 5.2 公共局面里的蚂蚁字段

规则页/README 在“每行 8 个整数”这句上有笔误。

代码真实输出是 9 个字段：

- `id player x y hp level age status behavior`

也就是说：

- 新版公共局面已经显式给出了 `behavior`。
- 这一点比此前很多旧文档更强，不需要再完全靠行为反推蚂蚁类型。

### 5.3 回放格式变化

新版本地/新 Judger 回放主格式是 JSON 数组，每轮形如：

- `op0`
- `op1`
- `round_state`
- `seed`

并且 `round_state` 默认不再保留 `pheromone`。

这和之前本地老脚本里大量使用的 `jsonl` 回放完全不是一回事，旧回放分析脚本不能直接套用。

## 6. 与旧 ANTWar 逻辑的逐项差异总结

### 6.1 可以视为“同宗增强”的部分

- 地图尺寸、基地位置、塔升级树、基地升级体系都延续旧版。
- 基础经济和信息素更新思想仍在。
- 旧 AI 的战略槽位表在新版常量里被直接保留为 `STRATEGIC_BUILD_ORDER`。

### 6.2 需要明确视为“已经断代”的部分

- 旧版 `Simulator::fast_next_round()` 的很多假设已经失效。
- 旧版不会处理行为状态、区域漂移、传送、拥塞、免控衰减。
- 旧版把 13 号塔当强力输出炮塔；新版它实际上是低伤害控制塔。
- 旧版对超级武器的判定不包含漂移与控制免疫。
- 旧版公共状态和 replay 都没有 `behavior` 字段。

## 7. 对 AI 迁移的直接含义

从旧 `ANTWar-AI` 迁移时，建议只保留这些“稳定资产”：

- 固定战略槽位顺序。
- 留钱防 EMP 的经济观念。
- 攻守模式切换。
- 建塔/升级/基地升级的高层节奏控制。

需要重写的部分：

- 所有基于旧模拟器的精细评估。
- 13 号塔、Pulse、EmergencyEvasion 的价值判断。
- 对前线稳定性的假设。
- 任何依赖旧 replay / 旧协议 / 旧字段数的脚本。

## 8. 当前迁移策略

本轮 `Game1/antgame_ai_cpp/v1` 采用的是：

- 旧 AI 的“槽位 + 分支 + 经济留钱 + 攻守切换”思想；
- 但不再直接复刻旧 C++ 模拟器；
- 改为由 `Game1/Ant-Game/AI/ai_cpp_v1.py` 用当前 SDK 提供精确状态快照，再交给 C++ 决策。

这样做的原因很直接：

- 旧模拟器对新规则缺失过多；
- 但新版 SDK 已经能提供精确状态、冷却、效果和合法性判断；
- 用桥接保住 C++ 决策核心，比重新手写一套完整新模拟器更稳妥。
