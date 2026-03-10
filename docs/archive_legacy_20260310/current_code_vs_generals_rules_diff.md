# 当前代码（Ant-Game）与 Generals（文档+past_AIs）规则差异对照

更新时间：2026-03-05（UTC）

## 1. 口径与证据来源

- 当前游戏规则：以 `Ant-Game/logic/*.py` 实际实现为准（不是规则文案）。
- Generals 规则：以 `docs/mhtml_parsed/generals_game35.md` + `past_AIs/Generals-AI` 的代码假设为准。

核心对照文件：

- 当前代码：
  - `Ant-Game/logic/gamedata.py`
  - `Ant-Game/logic/constant.py`
  - `Ant-Game/logic/gamestate.py`
  - `Ant-Game/logic/movement.py`
  - `Ant-Game/logic/upgrade.py`
  - `Ant-Game/logic/general_skills.py`
  - `Ant-Game/logic/super_weapons.py`
  - `Ant-Game/logic/game_rules.py`
  - `Ant-Game/main.py`
- Generals 文档：
  - `docs/mhtml_parsed/generals_game35.md`
- Generals 旧 AI 代码：
  - `past_AIs/Generals-AI/include/constant.hpp`
  - `past_AIs/Generals-AI/include/gamestate.hpp`
  - `past_AIs/Generals-AI/include/util.hpp`
  - `past_AIs/Generals-AI/main.cpp`

## 2. 结论先行

两者“框架同构”（将军/军队/科技/技能/超武/操作码都高度一致），但存在几处高影响差异：

1. **地形语义发生替换**：Generals 是“沼泽+流沙”，当前代码是“沼泽(BOG)+山地(MOUNTAIN)”。
2. **科技 1/2 的含义对调**：Generals 的 `IMMUNE_SWAMP / IMMUNE_SAND`，当前是 `CLIMB / IMMUNE(沼泽减兵免疫)`。
3. **地图生成与初始实体分布显著不同**：Generals 文档有复杂地形后处理与固定油田构成；当前代码是独立随机地形 + `8 farmer + 4 subgen`。
4. **运行主循环存在经济节奏分叉**：`update_round()` 已加 coin，`main.py` 在完整回合后又再加 coin（而 `runner.py` 不会再加），导致线上/离线节奏可能不同。
5. **非法操作处理不一致**：Generals 文档写“非法操作直接判负”；当前 `main.py` 对 AI/Web 非法操作是“忽略并继续”，不是立即判负。

这 5 点足以让“直接复刻 Generals AI 决策”出现系统性误判（尤其是地形/科技/经济节奏）。

## 3. 同构部分（可直接继承）

以下结构与 Generals/past_AIs 基本一致，可复用旧思路：

- 操作码主框架 `1..8` 一致（移动兵、移动将军、升将、技能、科技、超武、征召、回合结束）。
- 战斗公式框架一致：`num*attack - defender_army*defence`，占领后残兵取 `ceil`。
- 将军技能集合与费用/冷却主值一致（突袭、击破、统率、坚守、弱化）。
- 超武集合一致（核弹/强化/传送/时停）且都走“解锁+公共 CD”体系。
- 回合结算主干一致：将军产兵、油井(当前 Farmer)产币、10 回合全域 +1、地形持续效果、技能/超武剩余回合衰减。

## 4. 关键差异详解

### 4.1 地形与科技语义（最高优先级差异）

Generals 文档与 past_AIs：

- 地形：`PLAIN/SAND/SWAMP`。
- 文档语义：沼泽默认不可驻留/通过；流沙每回合减兵。
- 科技：`IMMUNE_SWAMP`（可过沼泽）和 `IMMUNE_SAND`（免流沙减兵）。
- 旧 AI 强依赖：
  - `CellType::SAND/SWAMP` 与 `TechType::IMMUNE_SWAMP/IMMUNE_SAND`；
  - 大量风险函数直接按 SAND/SWAMP 分支打分和剪枝。
  - 直接证据（`main.cpp`）：
    - 路径可达性把 `IMMUNE_SWAMP` 作为“是否可过 SWAMP”的硬约束；
    - 逃跑/进攻路径对 `SAND` 做惩罚、对 `SWAMP` 在特定科技态做偏置；
    - 科技顺序明确写成 `IMMUNE_SWAMP -> MOBILITY -> IMMUNE_SAND -> MOBILITY -> UNLOCK`。

当前代码：

- 地形：`PLAIN/BOG/MOUNTAIN`。
- 行为：
  - `MOUNTAIN` 不可过，直到 `tech_level[*][1]`（CLIMB）解锁；
  - `BOG` 可占领，但会每回合减兵，直到 `tech_level[*][2]`（IMMUNE）解锁。
- 成本：
  - `mountaineering=100`，`swamp_immunity=75`。

影响：

- 直接套用旧 AI 中“IMMUNE_SWAMP 优先级”和“避 SAND/偏 SWAMP”逻辑，会把科技和地形决策做反。
- 迁移时必须先做语义映射：
  - `old SWAMP blocked` -> `new MOUNTAIN blocked`
  - `old SAND attrition` -> `new BOG attrition`
  - `old IMMUNE_SWAMP` -> `new CLIMB`
  - `old IMMUNE_SAND` -> `new IMMUNE`

### 4.2 初始地图与实体分布

Generals 文档：

- 初始有 10 油田（7 平地 + 3 沼泽）、4 中立副将、双方主将。
- 还有一套随机后处理（40% 沼泽 + 15% 流沙，再做邻域修正、主将距离与连通性修复）。

当前代码：

- 地形独立采样：`bog_percent=0.15`、`mountain_percent=0.05`。
- 实体初始化：
  - 双方主将各 50 兵；
  - 4 中立副将（10~20 兵）；
  - 8 中立 farmer（3~5 兵，等价“油井角色”）。
- 无文档描述的复杂地形后处理、主将距离下限、连通性修复。

影响：

- 旧 AI 若隐含“开局固定 10 油井结构/路径可达性分布”先验，会在当前地图上系统失准。
- 开局扩张与抢点策略要按新分布重建，不可按 Generals 固定密度照搬。

### 4.3 经济节奏与回合结算路径差异

当前代码内部：

- `update_round()` 末尾会给双方各 `+1 coin`。
- 但 `Ant-Game/main.py` 在完整回合后又再给双方各 `+1 coin`。
- `logic/runner.py` 路径只有 `update_round()` 这一次加 coin。

影响：

- 同一 AI 在“本地 runner”与“主逻辑进程”可能处于不同经济节奏，导致离线优劣与线上优劣偏移。
- 如果用 Generals 节奏设计科技/超武时机，容易在某条执行路径上失配。

### 4.4 非法操作与胜负判定细节

Generals 文档写法：

- 非法操作直接判负。
- 500 回合后 tie-break：兵力 > 格子 > 石油 > 总用时 > 先手。

当前代码：

- `main.py` 对 AI/Web 的非法操作默认“忽略继续”（并非立即 IA）。
- `game_rules.py` tie-break：兵力 > 格子 > coin，若仍相同直接判 0 号玩家胜（没有“总用时”层）。

影响：

- 旧 AI 的“严格合法性防守”价值在当前实现下被削弱。
- 极长局和均势局的末端偏好会变化（0 号先手偏置更强）。

### 4.5 技能/超武细粒度差异

核心技能集合一致，但有几个实现细节需注意：

- 当前 `check_rush_param` 要求突袭目标格无将军，且若打敌方必须可占领（`vs>0`）。
- 传送与时停的禁行动判定在当前实现中会同时约束兵和将。
- 核弹是“立即 3x3 清场/半伤主将”+“后续 5 回合每回合 -3”的双阶段效果，和旧 util/gamestate 逻辑一致。

整体上，这一层与 Generals 差异小于地形/科技与经济节奏差异。

## 5. 对 Generals-AI 复刻的直接指导

必须先做的“语义层改造”：

1. 地形枚举和科技枚举的统一映射层（禁止在策略层直接用旧枚举语义）。
2. 所有地形代价函数改为基于“新语义”计算（blocked=mountain, attrition=bog）。
3. 开局价值函数重训：将“10 油井先验”改成“8 farmer + 4 subgen + 随机地形”。
4. 经济时机策略必须区分运行路径（`runner` vs `main`），否则会出现离线在线错配。
5. 长局 tie-break 评估函数按当前代码重写（去掉“时间层”）。

不建议继续沿用的旧假设：

- “IMMUNE_SWAMP 优先级=先过障碍”这一逻辑在当前是错位的。
- “流沙区高惩罚、沼泽可通行”在当前应完全反过来映射。
- “非法操作高风险导致必须过度保守”在当前主逻辑下不是同等强约束。

## 6. 一句话版本

当前游戏不是“Generals 原样复刻”，而是“Generals 骨架 + 地形/科技语义重映射 + 初始化分布与经济节奏改写”；如果不先做这一层校正，后续任何策略迭代都会在错误规则模型上优化。
