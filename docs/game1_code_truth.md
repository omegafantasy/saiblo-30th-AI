# Game1 Code Truth

这份文档只整理当前 Game1 里还能互相印证的代码真值。

## 1. 真值边界

- 规则、官方运行时与官方测试真值在 `Game1/Ant-Game/`
- 外置 C++ SDK 在 `Game1/antgame_cpp_sdk/`
- 当前保留的 C++ AI 源码在 `Game1/antgame_ai_cpp/`
- `Game1/Ant-Game/README.md` 只能当入口说明，不再单独充当规则真值

## 2. 推荐读取顺序

1. `Game1/Ant-Game/SDK/utils/constants.py`
2. `Game1/Ant-Game/SDK/backend/engine.py`
3. `Game1/Ant-Game/tests/test_engine.py`
4. native 交叉核对：
   `game/src/coin.cpp`
   `game/src/ant.cpp`
   `game/src/building.cpp`
   `game/src/game.cpp`
5. 协议与 C++ 侧公共状态：
   `Game1/antgame_cpp_sdk/include/antgame_sdk/sdk.hpp`
   `Game1/antgame_cpp_sdk/include/antgame_sdk/native_sim.hpp`
6. 若要审计某个具体回合的动作价值：
   `Game1/antgame_cpp_sdk/examples/sdk_lure_inspector.cpp`
   `Game1/antgame_cpp_sdk/examples/sdk_defense_parity.cpp`
   `Game1/antgame_cpp_sdk/examples/sdk_lure_perf.cpp`

## 3. 当前 Game1 代码结构

- `Game1/Ant-Game/`
  - 当前规则实现
  - Python SDK / engine / tests
- `Game1/antgame_cpp_sdk/`
  - 外置 C++ SDK
  - native rollout 封装
  - 对拍/bench 工具
  - 快速搜索模拟器 `DefenseSimulator`
- `Game1/antgame_ai_cpp/`
  - 当前保留的 Game1 C++ AI 入口
  - 现仅保留 `cpp_heavy_baseline/`

## 4. 核心常量

- 最大回合数：`512`
- 基地血量：`50`
- 初始金币：`50`
- 基础收入：每 `2` 回合 `+3`
  - 这是当前官方实现口径，不是“每回合 `+3`”
- 蚂蚁到达敌方基地奖励：`10`
- 击杀普通蚂蚁奖励：`6 / 10 / 14`
- 击杀战斗蚂蚁奖励：`18`

## 5. 基地升级

- 产兵周期：`4.5 / 4.0 / 3.5`
- 对应离散节奏由 `ANT_GENERATION_SCHEDULE = ((9, 2), (4, 1), (7, 2))` 实现
- 新生成普通蚂蚁最大生命：`20 / 25 / 25`
- 基地升级费用：`200 / 250`
- 一回合只能进行一种基地升级

## 6. 蚂蚁模型

### 6.1 行为

- `DEFAULT`
- `CONSERVATIVE`
- `RANDOM`
- `BEWITCHED`
- `CONTROL_FREE`

行为衰减：

- `RANDOM`：`5` 回合后退化为 `DEFAULT`
- `CONSERVATIVE`：`5` 回合后退化为 `DEFAULT`
- `BEWITCHED`：到达目标格或 `5` 回合后退化为 `DEFAULT`
- `CONTROL_FREE`：`5` 回合后退化为 `DEFAULT`

### 6.2 兵种

- `WORKER`
  - 寿命上限：`64`
  - 拆塔伤害：`1 / 2 / 4`
- `COMBAT`
  - 无寿命上限
  - 最大生命：`30`
  - 出生自带 `3` 层 `Emergency Evasion`
  - 拆塔伤害：`5`
  - 当前生命低于一半时，拆塔改为自爆
  - 自爆伤害：对目标塔及距离 `1` 内敌塔各造成 `10`

### 6.3 生成概率

基地与产蚁塔共享当前生成权重：

- 默认普通蚂蚁：`40%`
- 保守普通蚂蚁：`35%`
- 随机普通蚂蚁：`10%`
- 默认战斗蚂蚁：`15%`

## 7. 防御塔经济

- 建塔基础价：`15`
- 当前建塔价格序列：
  `15, 30, 45, 90, 135, 270, 405, ...`
- 通式：
  `15 * 3^(tower_count // 2) * (2 if tower_count is odd else 1)`
- 一级升二级费用：`60`
- 二级升三级费用：`200`
- 降级/拆除返还比例：`90% * 当前血量比例`，向下取整

## 8. 防御塔数据

当前结构化常量中的塔数据如下：

| Type | Damage | Cooldown | Range | Extra |
| ---- | ------ | -------- | ----- | ----- |
| `BASIC` | `5` | `2.0` | `1` | - |
| `HEAVY` | `12` | `2.0` | `1` | - |
| `HEAVY_PLUS` | `24` | `2.0` | `1` | - |
| `ICE` | `12` | `2.0` | `2` | 冻结，解冻后转 `RANDOM` |
| `BEWITCH` | `14` | `2.0` | `2` | 转 `BEWITCHED` |
| `QUICK` | `6` | `1.0` | `1` | - |
| `QUICK_PLUS` | `6` | `0.5` | `1` | 原生实现相当于一次结算可打两次 |
| `DOUBLE` | `6` | `2.0` | `3` | 最多打前二目标 |
| `SNIPER` | `10` | `2.0` | `4` | - |
| `MORTAR` | `12` | `4.0` | `2` | 以目标点为中心的 AOE |
| `MORTAR_PLUS` | `18` | `4.0` | `2` | 以目标点为中心的 AOE |
| `PULSE` | `14` | `4.0` | `2` | 同时打范围内所有敌蚁并转 `RANDOM` |
| `MISSILE` | `18` | `6.0` | `3` | 更大范围 AOE |
| `PRODUCER` | `0` | - | `0` | 每 `10` 回合产蚁 |
| `PRODUCER_FAST` | `0` | - | `0` | 每 `8` 回合产蚁 |
| `PRODUCER_SIEGE` | `0` | - | `0` | 每 `10` 回合产蚁，额外 `25%` 产战斗蚁 |
| `PRODUCER_MEDIC` | `0` | - | `0` | 每 `10` 回合产蚁，每 `4` 回合治疗前线目标并补 `1` 层回避 |

补充：

- `Basic` 最大血量 `10`
- `Basic` 从新建开始射程就是 `1`
- 其余塔最大血量 `15`
- 升级回满血
- 降级按血量比例继承

## 9. 超级武器

| Weapon | Cost | Cooldown | Duration | Range | Current effect |
| ------ | ---- | -------- | -------- | ----- | -------------- |
| `LIGHTNING_STORM` | `90` | `35` | `15` | `3` | 每回合对区域内敌蚁 `20` 伤害；第 `5/10/15` 生效回合对区域内敌塔 `3` 伤害 |
| `EMP_BLASTER` | `135` | `45` | `10` | `3` | 禁止区域内敌方建/升/降塔，并使区域内敌塔无法攻击 |
| `DEFLECTOR` | `60` | `25` | `10` | `3` | 区域内己方蚂蚁免疫小于半血阈值的单次伤害；离开或效果结束后转 `CONTROL_FREE` |
| `EMERGENCY_EVASION` | `60` | `25` | `1` | `3` | 立刻把区域内己蚁回避层补到至少 `2`；攻击前再补一次；回避耗尽后转 `CONTROL_FREE` |

当前实现中：

- 超级武器在玩家操作阶段部署后立即进入生效状态
- `Lightning Storm` 对蚂蚁走普通受伤流程，不是真实伤害
- `Lightning Storm` 部署当下就会先结算一次范围内敌蚁伤害，并用内部 `last_trigger_round` 防止同回合攻击阶段重复触发
- 因此 `Lightning Storm` 会先消耗 `Emergency Evasion` / 战斗蚁初始回避层
- `EMP Blaster` 部署当下即会影响后续操作，因此玩家 `0` 本回合放下的 `EMP` 可以直接让玩家 `1` 同回合在覆盖区内的建/升/降塔失败
- `Emergency Evasion` 部署当下会立刻把范围内己蚁回避层补到至少 `2`
- `Lightning Storm` 与 `EMP` 的中心都会在回合末随机漂移到当前格或相邻合法格
- `Deflector` 与 `Emergency Evasion` 还会写入寻路吸引场

## 10. 移动与随机移动

- 默认运行策略：`enhanced`
- 兼容旧策略：`legacy`
- 非 `RANDOM`、非 `BEWITCHED` 默认禁止回头
- 若没有非回头合法候选，则退化为允许回头
- 蚂蚁可以把相邻敌塔格当成目标；这会结算为攻击塔，而不是进入塔格

每 `10` 回合会触发一次随机移动阶段：

- 候选：所有非 `CONTROL_FREE`、未死亡、未老死蚂蚁
- 抽样比例：约 `10%`，至少 `1` 只
- 每只连续结算 `3` 步
- 每一步：
  - `2/3` 概率随机选合法方向
  - `1/3` 概率重新调用该蚂蚁当前移动算法

## 11. 回合顺序

native 当前整回合主流程：

0. 玩家操作阶段：先玩家 `0`，再玩家 `1`
   - 超武在这里部署并立即生效
   - 因此同回合后手操作会受到前手刚放下的 `EMP` 影响

1. `attack_ants`
2. `move_ants`
3. `teleport_ants`
4. `update_pheromone`
5. `manage_ants`
6. `generate_ants`
7. `increase_ant_age`
8. `update_coin`
9. `update_items`
10. `round += 1`

## 12. 当前公开状态

当前公共回合状态至少包含：

- 防御塔：`id player x y type cd hp`
- 蚂蚁：`id player x y hp lv age state behavior kind`
- 基地等级
- 超武冷却
- 生效中的区域效果

补充：

- `active_effects` 公开的是 `type / player / x / y / remaining_turns`
- native / Python engine 内部还维护 `last_trigger_round` 一类非公开字段，用于保证“部署即生效”的效果不会在同回合重复结算

所有进一步判断都应从这些公开字段和当前代码结算逻辑出发，不再引用历史策略页。

## 13. 操作编号

补充：

- 每回合提交的是“有序操作列表”，不是单一操作
- engine 会按顺序逐条检查并应用合法操作
- 因此同回合允许出现：
  - `拆塔 -> 建塔`
  - `拆塔 -> 闪电 -> 建塔`
  - `双拆塔 -> 双建塔`
- 但同一回合内仍有顺序约束：
  - 同一座塔不能重复升级/降级
  - 同一种超武同回合最多使用一次
  - 基地两种升级同回合互斥
  - 整个操作列表在顺序应用后钱包不能为负
  - `EMP` 会立即生效，因此同回合后续塔操作可能被卡掉

- `11`：建塔
- `12`：升级塔
- `13`：降级/拆塔
- `21`：`Lightning Storm`
- `22`：`EMP Blaster`
- `23`：`Deflectors`
- `24`：`Emergency Evasion`
- `31`：升级产兵速度
- `32`：升级新生成蚂蚁生命

## 14. 当前保留 AI 入口

- C++ baseline 源码：`Game1/antgame_ai_cpp/cpp_heavy_baseline/ai_cpp_heavy_baseline.cpp`
- C++ baseline 构建：`Game1/antgame_ai_cpp/cpp_heavy_baseline/Makefile`
- baseline 主逻辑：`Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy.hpp`
- 快速模拟器：`Game1/antgame_cpp_sdk/include/antgame_sdk/random_search_baseline.hpp`
- 策略参数：`Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_params.hpp`
- 若要对可疑动作做单回合策略审计，应使用 `Game1/antgame_cpp_sdk/examples/sdk_lure_inspector.cpp`
- 若要对轻量模拟做 native 多 rollout 对拍，应使用 `Game1/antgame_cpp_sdk/examples/sdk_defense_parity.cpp`
- 当前基线策略重点：
  - `hold + base + lure + recycle_base*lure + lightning` 根节点搜索
  - 简化终点评估，默认偏向少操作
  - 搜索 `Build/Upgrade/Downgrade/Lightning` 及少量同回合 op-list
  - 当前不考虑基地升级
  - 主防守搜索忽略我方蚂蚁，也暂时禁用进攻补值
  - `C1` 主线当前以 `Heavy / Quick / Sniper` 为主
  - 闪电当前是单闪电候选，所有合法中心用 UCB 分配 rollout，不带前置降级/拆塔
  - future rollout 只保留战斗蚁贴身时的 reactive 回收，不再完整生成未来主动计划
  - 终点评估关注基地血量、塔剩余价值、敌蚂蚁威胁和钱

## 15. 当前快速模拟性能口径

- `NativeSimulator` 是官方 `Ant-Game/game` C++ 逻辑封装
- `DefenseSimulator` 是搜索用快速模拟，不是完整官方对象图
- 当前快速模拟默认忽略每 10 回合周期随机移动
- `DefenseSimulator` 内层状态以固定容量数组为主，减少 STL 热路径开销
- `DefenseSimulator::clone()` 不复制派生 move cache / lookup cache
- 当前最大内层热点仍是增强移动的反向路径规划
- 若做对拍，应优先选择不跨 10 回合随机移动窗口的起点和 horizon

2026-04-27 对拍记录：

- 32 个 512 回合 self-play replay 中后期 case
- 每个 case `1000` rollout、`6` 回合窗口
- 起点均避开跨 10 回合周期随机移动
- fast/native 终点评分平均绝对差约 `12.04`
- 基地血平均绝对差约 `0.049`
- 32 个 case 中包含 4 个 active effect 根状态，未发现结构性偏差

## 16. 胜负判定

基地被打空时立即结束。

若打满 `512` 回合，native 当前按以下顺序判定：

1. 基地剩余血量高者胜
2. 击杀敌方蚂蚁数多者胜
3. 使用超级武器次数少者胜
4. AI 总用时少者胜
5. 若仍相同，玩家 `0` 胜
