# Game1 cpp_v4 Rollout Status

本文记录当前 `Game1` 新版 `cpp_v4` 的设计、实现、对拍与本地评测结果。

相关代码：

- `/www/Game1/antgame_ai_cpp/v4/ai_v4.cpp`
- `/www/Game1/Ant-Game/AI/ai_cpp_v1.py`
- `/www/Game1/Ant-Game/tools/compare_cpp_v4_sampling.py`
- `/www/Game1/antgame_ai_cpp/sim/exact_move_kernel.cpp`

## 1. 设计目标

`cpp_v4` 直接落实了本轮讨论中的几条约束：

1. 先做防守优先的旧 `ANTWar-AI` 风格迁移，而不是追求复杂新机制全覆盖。
2. 当前 rollout 中明确忽略 `teleport`，接受这部分残余风险。
3. 候选动作保留 `build / upgrade / downgrade-or-destroy / base-upgrade` 四类，但动作数必须稀疏、保守。
4. 己方塔线只保留 `Quick` 与 `Mortar` 主线，不主动考虑 `Heavy`、`Sniper`、`Pulse`。
5. 候选评估以防守为先，用字典序比较，而不是普通加权和。
6. rollout 视野直接取 `16` 回合。
7. 使用共享场景和关键蚂蚁首步分层采样，降低候选排序噪声。

## 2. 已实现的模块

### 2.1 Snapshot bridge

`ai_cpp_v1.py` 现在会把下面这些状态送给 `cpp_v4`：

- 所有塔、基地、蚂蚁的当前状态
- `last_move`
- `behavior_turns`
- `behavior_expiry`
- `frozen`
- `bewitch_target_x / bewitch_target_y`
- `safe_coin_threshold`
- `nearest_enemy_distance / frontline_distance`
- `pheromone` 网格

这保证 `cpp_v4` 的 rollout 不是盲猜，而是基于当前 SDK 重建出的更接近代码真值的状态。

### 2.2 Threat precompute

`cpp_v4` 会先对敌方蚂蚁做轻量威胁预处理：

- 当前到我方基地的距离
- 未来主路径最短距离
- 假设沿途所有己方塔都能打到时的 `nominal_damage`
- 假设 `tower cooldown = 0` 的上界伤害 `upper_damage`
- 当前一步移动分布里的前两优方向与概率

预处理结果只保留最高威胁的少量敌蚁，用作后续分层采样对象。

### 2.3 Scenario generator

当前版本保留最多 `3` 只关键敌蚁。

- 每只蚂蚁只取前两优首步方向
- 组合成 `2^k` 个首步 strata
- 所有候选动作共享这批场景

这比纯随机 rollout 更稳，也更接近旧版 AI “抓关键对象再决策”的思路。

### 2.4 Fast rollout engine

当前 rollout 只模拟：

- 敌方蚂蚁
- 我方塔
- 我方基地血
- 金币与 `safe_coin_threshold`
- 蚂蚁出生与行为衰减

明确不模拟：

- `teleport`
- 己方蚂蚁的进攻收益
- 完整超武体系
- 全部控制塔分支

这不是“规则全覆盖模拟器”，而是一个服务于防守估值的快速 rollout。

### 2.5 Lexicographic defense evaluator

候选比较优先级不是普通加权和，而是防守优先的字典序：

1. `min_base_hp`
2. `damage_count`
3. `first_damage_round`
4. `tail_base_hp`（近似坏分位）
5. `mean_base_hp`
6. `min_safe_coin`
7. `mean_safe_coin`
8. `kill_reward`
9. `enemy_arrivals`
10. `action_penalty`

这符合“先别漏血，再谈别的”的目标。

## 3. 对拍与正确性

### 3.1 一步采样对拍

使用：

- `/www/Game1/Ant-Game/tools/compare_cpp_v4_sampling.py`
- `/www/Game1/antgame_ai_cpp/sim/exact_move_kernel`

正式对拍结果：

- 输出文件：`/www/docs/generated/sandbox/compare_cpp_v4_sampling_v4_20260312.json`
- `cases = 24`
- `ants = 150`
- `rows = 382`
- `loops_per_ant = 8000`
- `max_prob_diff = 0.03447`
- `mean_abs_diff = 0.00165`

解释：

- `cpp_v4` 的一步采样和精确分布核在平均误差上已经足够接近，可作为 rollout 的采样底座。
- 这里的目标不是逐帧精确还原全局概率，而是保证 rollout 场景生成没有明显偏离当前规则。

### 3.2 合法性与打包链路

已重新验证：

- `python3 -m pytest -q tests/test_packaging.py -k 'cpp_v4'`
- 结果：`1 passed`

快速本地对局中：

- `game_stderr = ""`
- `ai0_stderr = ""`
- `ai1_stderr = ""`

说明本轮 tightened 版本没有引入新的非法操作或桥接问题。

## 4. 两轮本地主评测

### 4.1 第一轮：较松的动作门槛

scope：`game1_v4_eval_core`

tag：`eval_20260312_170159`

结果：

- 总战绩：`5-3`
- Elo：
  - `cpp_v4_rollout_defense 1518.92`
  - `example 1501.02`
  - `cpp_v1_current 1480.06`
- 分对手：
  - 对 `cpp_v1_current`：`3-1`
  - 对 `example`：`2-2`

但 replay 汇总暴露了明显问题：

- `cpp_v4` 在 8 局里累计动作数：
  - `build_tower = 75`
  - `downgrade_tower = 69`
  - `upgrade_tower = 53`
  - `lightning_storm = 12`
- 对 `random` 的定向补测里也出现了 `1-1` 的不稳定结果。

这说明第一轮虽然小样本分数领先，但过于依赖拆塔与结构重排，不符合“保守少操作”的迁移目标。

### 4.2 第二轮：tightened 门槛

对 `cpp_v4` 做了三类调整：

1. `downgrade` 只在更明确的应急条件下开放
2. `combo(downgrade + build/upgrade)` 只在低金币或前线压近时开放
3. 基地升级显著后置

scope：`game1_v4_eval_core_tight`

tag：`eval_20260312_170803`

结果：

- 总战绩：`4-4`
- Elo：
  - `cpp_v4_rollout_defense 1501.14`
  - `cpp_v1_current 1499.94`
  - `example 1498.92`
- 分对手：
  - 对 `cpp_v1_current`：`2-2`
  - 对 `example`：`2-2`

动作数显著下降：

- `cpp_v4` 在 8 局里累计动作数：
  - `build_tower = 30`
  - `upgrade_tower = 30`
  - `lightning_storm = 10`
  - `downgrade_tower = 0`

这说明 tightened 版明显更接近目标风格：

- 不再依赖高频拆塔
- 对局更稳定
- 主评测强度维持在 `cpp_v1_current` 和 `example` 同量级

代价是：

- 小样本 Elo 不再像第一轮那样明显领先
- 当前更像“稳住风格、避免过拟合动作”的版本，而不是已经验证的更强版本

## 5. 单局验证

tightened 版单局验证：

- `cpp_v4` vs `example`, seed `42`
  - 胜
  - `477` 回合结束
  - 动作数：`build=4, upgrade=4, lightning=2`
- `cpp_v4` vs `random`, seed `41`
  - 胜
  - `512` 回合结束
  - 动作数：`build=4, upgrade=5`

对手动作数对比非常明显：

- `example` 在这局里：`build=59, downgrade=56`
- `random` 在这局里：`build=131, downgrade=133`

这说明 tightened `cpp_v4` 已经明显体现出“少操作、保守结构”的差异。

## 6. 回放分析结论

replay analysis 输出：

- 第一轮：`/www/autolab/runtime/scopes/game1_v4_eval_core/replay_analysis/eval_20260312_170159_replay_analysis.md`
- 第二轮：`/www/autolab/runtime/scopes/game1_v4_eval_core_tight/replay_analysis/eval_20260312_170803_replay_analysis.md`

当前可以确认的现象：

1. 绝大多数局都打到很深回合，当前版本仍是“防守拉锯型”
2. `example` 的高频建拆塔风格会制造很多波动，但 tightened `cpp_v4` 已经不再跟着一起高频重构
3. 第一轮的主要问题是过多 `downgrade`，第二轮已明显修正
4. 当前 rollout 仍然偏重保基地血和安全金币，对主动终结能力仍偏弱

## 7. 当前限制

当前 `cpp_v4` 仍然不是终版，主要限制有：

1. 仍然显式忽略 `teleport`
2. 仍然基本不模拟己方蚂蚁进攻收益
3. 仍然没有把旧 `ANTWar-AI` 的卖塔应急链完整迁完，只保留了更保守的残余版本
4. 当前 tower 选择仍只覆盖 `Quick / Mortar` 主线
5. `greedy` 相关对局会明显拉长，适合作为压力测试，不适合作为当前主 Elo 样本
6. 当前主评测样本仍偏小，不能把 `4-4` 或 `5-3` 这种结果当作稳定强弱结论

## 8. 当前判断

截至这轮，本地最可信的判断是：

1. `cpp_v4` 的 rollout 主线已经跑通
2. 一步采样对拍已经到可用精度
3. 本地打包、桥接、回放、评测链都已经通
4. tightened `cpp_v4` 的风格比第一轮更对，更接近旧 AI 想要的“克制、防守优先、少操作”
5. 但强度仍只能说与 `cpp_v1_current` / `example` 同量级，尚未证明显著更强

## 9. 下一步建议

后续最值得继续做的不是重新放开动作空间，而是：

1. 继续把 `downgrade/destroy` 限制为更纯粹的应急动作
2. 把旧 AI 的 `safe_coin` 与 `fail-round` 逻辑再更直接地迁到 rollout 候选剪枝里
3. 对 `greedy` 做专门的长局 replay 分析，而不是把它混进主 Elo
4. 在不放开复杂塔线的前提下，补更强的 `Quick/Mortar` 槽位模板
