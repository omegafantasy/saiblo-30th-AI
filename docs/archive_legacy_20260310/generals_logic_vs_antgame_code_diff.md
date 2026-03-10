# Generals-Logic 与 Ant-Game 代码实质差异（仅代码口径）

更新时间：2026-03-05（UTC）

对比范围：

- 旧逻辑：`/www/past_AIs/Generals-Logic`
- 当前逻辑：`/www/Ant-Game`

说明：

- 本文只信任代码，不引用任何规则文档。
- “实质差异”按是否影响对局行为优先排序。

## A. 直接影响对局行为的差异

### A1) 初始金币不同：`40` vs `50`

- 旧逻辑：
  - `init_coin()` 返回 `0`，随后 `main.py` 强制设为 `[40, 40]`。
  - 代码位置：`past_AIs/Generals-Logic/logic/gamedata.py:55-56`，`past_AIs/Generals-Logic/main.py:610`
- 当前逻辑：
  - `init_coin()` 直接返回 `50`（主流程还带 0->50 fallback）。
  - 代码位置：`Ant-Game/logic/gamedata.py:55-56`，`Ant-Game/main.py:286-289`

影响：开局经济节奏显著不同。

### A2) 每完整回合金币结算路径不同（当前存在额外加钱）

- 旧逻辑：
  - `update_round()` 不给双方固定 +1 coin。
  - 代码位置：`past_AIs/Generals-Logic/logic/gamestate.py:191-285`
- 当前逻辑：
  - `update_round()` 已给双方各 +1 coin。
  - `main.py` 在后手结束后又再给双方各 +1 coin。
  - 代码位置：`Ant-Game/logic/gamestate.py:431-432`，`Ant-Game/main.py:525-530`

影响：在 `main.py` 路径上是“双加钱”；与旧逻辑经济完全不同。

### A3) 地图生成机制差异很大

- 旧逻辑：
  - 初始地形参数：`bog=0.15, mountain=0.4`。
  - 先做 `update_map()` 两轮邻域重写（会改大量地形）。
  - 主将位置要求曼哈顿距离 `>18`，若不连通会强制打通路径。
  - 代码位置：
    - `past_AIs/Generals-Logic/logic/constant.py:33-37`
    - `past_AIs/Generals-Logic/main.py:576-594`（`update_map`）
    - `past_AIs/Generals-Logic/logic/gamestate.py:122-145`（主将距离与连通）
    - `past_AIs/Generals-Logic/main.py:608`（调用 `update_map`）
- 当前逻辑：
  - 地形参数：`bog=0.15, mountain=0.05`。
  - 无 `update_map` 邻域重写，无主将距离/连通修复。
  - 代码位置：`Ant-Game/logic/constant.py:33-37`，`Ant-Game/main.py`（无 `update_map` 调用）

影响：地图分布与地形连通性结构变化巨大。

### A4) 初始主将兵力：旧逻辑未设 50；当前显式设为 50

- 旧逻辑：
  - 主将初始化时仅设置位置与归属，未设置 `army=50`。
  - 代码位置：`past_AIs/Generals-Logic/logic/gamestate.py:131-142`
- 当前逻辑：
  - 主将初始化显式 `army = 50`。
  - 代码位置：`Ant-Game/logic/gamestate.py:326-337`

影响：开局战力基线完全不同。

### A5) 初始中立资源点构成不同

- 旧逻辑：
  - `farmer_num=10`，并且特意“3 个 farmer 从山地位置采样”。
  - 代码位置：`past_AIs/Generals-Logic/logic/constant.py:36`，`past_AIs/Generals-Logic/logic/gamestate.py:170-188`
- 当前逻辑：
  - `farmer_num=8`，全部从普通候选位采样。
  - 代码位置：`Ant-Game/logic/constant.py:36`，`Ant-Game/logic/gamestate.py:349-358`

影响：资源点数量与地形分布都变了。

### A6) `TIME_STOP` 生效范围：旧逻辑“对双方都禁用”；当前“仅禁对手”

- 旧逻辑（多个模块一致）：
  - 只要在时停区就禁止，不区分施法方。
  - 代码位置示例：
    - `past_AIs/Generals-Logic/logic/movement.py:70-76,183-189`
    - `past_AIs/Generals-Logic/logic/general_skills.py:117-122`
    - `past_AIs/Generals-Logic/logic/upgrade.py`（同类检查无 `sw.player!=player`）
- 当前逻辑：
  - 检查里增加 `sw.player != player`，即仅禁敌方行动/升级/技能。
  - 代码位置示例：
    - `Ant-Game/logic/movement.py:70-75,172-177`
    - `Ant-Game/logic/general_skills.py:116-121`
    - `Ant-Game/logic/upgrade.py:121-125`（同类处）

影响：时停机制从“区域冻结双方”变成“单向压制”。

### A7) 将军移动扣步规则不同（非常关键）

- 旧逻辑：
  - `check_general_movement()` 返回 BFS 实际步长；
  - `general_move()` 扣除该实际步长 `steps`。
  - 代码位置：`past_AIs/Generals-Logic/logic/movement.py:163`，`past_AIs/Generals-Logic/logic/movement.py:137-146`
- 当前逻辑：
  - `check_general_movement()` 只返回 bool；
  - `general_move()` 扣除曼哈顿距离 `abs(dx)+abs(dy)`。
  - 代码位置：`Ant-Game/logic/movement.py:151`，`Ant-Game/logic/movement.py:135`

影响：绕路场景下当前逻辑会“少扣步数”，直接改变将军机动上限。

### A8) 突袭与传送的山地限制被放宽

- 旧逻辑：
  - 突袭参数检查里禁止“无攀岩科技突袭到山地”。
  - 传送也禁止“无攀岩落到山地”。
  - 代码位置：`past_AIs/Generals-Logic/logic/general_skills.py:55-56`，`past_AIs/Generals-Logic/logic/super_weapons.py:139-140`
- 当前逻辑：
  - 上述两处限制都不存在。
  - 代码位置：`Ant-Game/logic/general_skills.py:41-63`，`Ant-Game/logic/super_weapons.py:133-139`

影响：山地跨越能力增强，改变战术可达域。

### A9) Farmer 是否可用将军技能：旧逻辑禁止，当前允许尝试

- 旧逻辑：
  - `skill_activate()` 显式拒绝 `Farmer`。
  - 代码位置：`past_AIs/Generals-Logic/logic/general_skills.py:106-107`
- 当前逻辑：
  - 仅检查 `general is None`，未排除 `Farmer`。
  - 代码位置：`Ant-Game/logic/general_skills.py:104-106`

影响：在 Farmer id 被调用技能时，行为语义与旧逻辑不同。

### A10) 非法操作处理策略不同

- 旧逻辑：
  - AI 非法操作通常直接判该方 `IA` 结束。
  - 代码位置：`past_AIs/Generals-Logic/main.py:463-466,505-507`
- 当前逻辑：
  - 对 AI/Web 非法操作默认 `continue` 忽略，不立即判负。
  - 代码位置：`Ant-Game/main.py:446-451`

影响：容错策略变化，影响对局终止条件与策略风险偏好。

### A11) AI 时间限制不同（主流程）

- 旧逻辑：AI 回合时间配置 `1` 秒。`past_AIs/Generals-Logic/main.py:646,684`
- 当前逻辑：AI 回合时间配置 `3.0` 秒。`Ant-Game/main.py:300-305`

影响：可用搜索预算显著变化。

## B. 主要为接口/回放层差异（不直接改战斗规则）

### B1) 回放结构重构

- 旧逻辑：逐行 JSONL，`get_single_round_replay` 只输出 `generals_ids` 指定将军，`Cell_type` 生成有缺陷。
- 当前逻辑：新增 AntWar 风格 replay writer（JSON 数组 + `op0/op1/round_state`），并修复 `Cell_type` 全图生成。
- 代码位置：
  - 旧：`past_AIs/Generals-Logic/logic/generate_round_replay.py:4-68`
  - 新：`Ant-Game/logic/generate_round_replay.py:5-73`，`Ant-Game/logic/gamestate.py:33-315`

### B2) 主循环协议扩展

- 当前 `main.py` 增加了 web action 映射、`255` surrender、中途 UI 刷新等；旧逻辑没有。
- 代码位置：`Ant-Game/main.py:124-185,203-230,503-552`

## C. 基本一致（或仅类型注解/日志差异）

- `computation.py` 核心战斗增益计算逻辑无实质变化。
- `call_generals.py`、`upgrade.py` 多数改动是 replay 参数/注释/类型注解，不改核心数值与判定主干。
- `tech_update` 数值与升级路径主干保持一致。

## D. 结论（只按代码）

从“实际可执行规则”看，当前 `Ant-Game` 与 `Generals-Logic` 并非小修：

1. 地图与开局（地形分布、主将初始兵、资源点数量与位置）已明显改写；
2. 经济结算（尤其 coin）节奏已变化，且当前主流程有额外加钱路径；
3. 关键技能/超武约束与时停作用对象发生变化；
4. 将军移动扣步从“实际路径步数”变成“曼哈顿步数”，这是高影响规则差异；
5. 非法操作判负策略与 AI 时限也与旧逻辑不同。

如果目标是“复刻旧逻辑强度”，必须先决定是否要把这些行为差异对齐，否则策略迁移会天然失真。

