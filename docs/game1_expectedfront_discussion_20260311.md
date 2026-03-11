# Game1 ExpectedFront Discussion Notes

本文记录 2026-03-11 这一轮关于 `Game1` 基础模拟、稀疏决策和旧 `ANTWar-AI` 迁移的讨论问题，并尽量只依据当前代码库做判断。

代码真值优先级：

1. `/www/Game1/Ant-Game/SDK/backend/engine.py`
2. `/www/Game1/Ant-Game/SDK/backend/model.py`
3. `/www/Game1/Ant-Game/SDK/utils/constants.py`
4. `/www/Game1/Ant-Game/game/src/*.cpp`

相关参考：

- 旧强 AI：`/www/past_AIs/ANTWar-AI/main.cpp`
- 当前 C++ 预测内核：`/www/Game1/antgame_ai_cpp/sim/exact_move_kernel.cpp`
- 当前随机性主分析：`/www/docs/game1_simulation_randomness_analysis.md`
- 当前性能/行为报告：`/www/docs/game1_simulation_perf_and_behavior_report.md`

## 先纠正一个关键前提

当前 `Game1` 里真正有 `hp` 的是基地 `camp`，不是塔。

- 塔对象没有 `hp` 字段，只有类型、位置、冷却等。
- 基地有 `hp=50`，蚂蚁到达敌方基地时会使基地 `hp -= 1`。

所以防守目标应表述为：

- 尽量不掉己方基地血

而不是：

- 尽量不掉己方塔血

这不只是措辞问题，因为它会直接影响防守评估函数写法。当前防守更接近“防漏怪”，不是“保塔耐久”。

## 本轮记录的讨论问题

用户提出的问题，按原意整理如下：

1. 现在有没有必要考虑自己的蚂蚁。当前阶段是否可以先不考虑。
2. 敌方蚂蚁出生于敌方基地，很多出生行为走几步就退化。等真正有威胁时，往往已经是 `DEFAULT`。基础策略里是否没必要考虑太多行为类型。
3. 一些行为类型依赖特定控制塔。是否可以直接不考虑这些塔，先把己方策略收窄到旧 AI 更常用的 `mortar` 基础和 `quick` 系列。
4. `ExpectedFront` 究竟是什么。它是否能支持旧版 AI 中非常重要的“稀疏决策”。
5. 由于新版本随机性更强，目标更像是“尽量不掉基地血，并考虑比较坏的情况”。在这种偏悲观、防守优先的问题里，`ExpectedFront` 是否合适。

## 对这些问题的当前判断

### 1. 是否可以先不考虑己方蚂蚁

如果当前目标是先做“基础防守模块”，可以。

理由：

- 敌方移动中的 crowding 只看同玩家蚂蚁，不看我方蚂蚁。
- 我方塔对敌方的伤害、控制，与我方蚂蚁是否存在没有直接耦合。
- 当前要解决的首要问题是“敌方未来几回合会不会漏到我方基地”。

因此，对一个防守型 risk evaluator，可以先只看：

- 敌方蚂蚁
- 我方塔
- 当前控制/超武效果

但这只是防守子模块的简化，不是完整 AI 的最终结论。完整 AI 后面仍要考虑己方蚂蚁，因为：

- 我方蚂蚁影响进攻节奏和金币
- 终局 tie-break 也看击杀和老死

结论：

- 防守模块里先不看己方蚂蚁：合理
- 全局策略里永久不看己方蚂蚁：不合理

### 2. 出生型特殊行为是否可以基本忽略

这个判断有一半对，一半不对。

对的部分：

- 敌方新出生蚂蚁确实从敌方基地出发。
- `CONSERVATIVE / BEWITCHED / CONTROL_FREE` 默认持续时间是 `5` 回合。
- 两基地间距离较大，正常走到我方半场需要明显超过 `5` 回合。
- 因此，很多“出生即带的特殊行为”在真正靠近我方基地之前，确实已经退化回 `DEFAULT`。

不对的部分：

- 特殊行为不只来自出生。
- 中途会被控制塔重新赋予行为：
  - `ICE`：冻结后转 `RANDOM`
  - `CANNON`：转 `BEWITCHED`
  - `PULSE`：转 `RANDOM`
- 这些变化恰恰可能发生在中场甚至我方半场附近。

因此，正确结论不是“特殊行为都可以忽略”，而是：

- 可以弱化“出生型特殊行为”的重要性
- 不能忽略“中途由控制塔/效果触发的特殊行为”

### 3. 是否可以先不考虑某些控制塔

这个要分成两件事。

第一件事：己方动作空间

这里我同意可以收窄，而且我认为应该收窄。

旧强 AI 的优势从来不是“什么塔都用”，而是：

- 候选很稀疏
- 结构很稳定
- 升级分支有明显偏好
- 用少量高价值操作控制风险

所以当前己方策略空间，完全可以先缩到：

- `Basic -> Heavy / Quick / Mortar`
- `Quick -> QuickPlus / Double / Sniper`
- `Mortar -> MortarPlus / Missile`
- `Heavy -> HeavyPlus`

并且暂时不主动考虑：

- `Ice`
- `Cannon`
- `Pulse`

第二件事：敌方行为模型

这里不能删。

即使我们自己不建控制塔，敌方仍然可能建。只要敌方建了：

- 敌蚂蚁的行为分布就会改变
- 我方防守风险的统计特征也会变

结论：

- “己方建塔策略空间”可以先精简
- “敌方行为模拟”不能因此不管控制塔

### 4. `ExpectedFront` 是否适合稀疏决策

适合，但位置要摆对。

它不应该被理解为：

- 完整替代旧版 `Simulator`
- 或者完整替代旧版搜索树

更准确的定位是：

- 一个短视野、分布式的前线评估器

它最适合做的是：

- 给稀疏候选动作提供统一的前线风险地图
- 给“fail-round / danger / 近基地漏怪风险”提供更可信的输入
- 在真正进入更贵的模拟或采样前，先做筛选和排序

也就是说，它更像旧 AI 里的：

- 一个比 `nearest_ant_dis` 更细的 danger map

而不是旧 AI 里的：

- 整个搜索器本身

### 5. 在偏悲观、防守优先的问题里它是否合适

只用 `ExpectedFront` 本身，不够。

但作为第一层，非常合适。

原因：

- `ExpectedFront` 本质上是期望值模型
- 你想解决的是坏情况防守问题
- 坏情况问题不能只看期望

所以推荐的结构不是：

- 只有 `ExpectedFront`

而是：

- `ExpectedFront` 负责“平均前线和危险区域”
- 额外的 pessimistic layer 负责“坏情况兜底”

这和旧 AI 的思路其实并不冲突。旧 AI 里真正关键的也不是“平均收益最大”，而是：

- 尽量把 fail-round 推后
- 尽量避免突然漏血

## 我设想中的 ExpectedFront

下面写的是“推荐版 ExpectedFront 设计”，不是“当前已经完全实现的版本”。

### 目标

在给定当前公共局面和少量 tracker 恢复状态后，快速回答下面这些问题：

1. 敌方未来 `1-4` 回合在各格子的期望质量有多少
2. 哪些区域会成为高风险前线
3. 己方基地周围未来 `1-4` 回合的累计威胁有多少
4. 在不重跑完整搜索的情况下，一个稀疏候选操作能改善多少防守

### 输入

最小输入应包含：

- 当前所有可见蚂蚁
  - `x y hp level age status behavior`
- 当前所有塔
  - `player x y type cooldown`
- 当前基地血量与金币
- 当前活动效果
- tracker 恢复出的隐含状态
  - `last_move`
  - `behavior_turns`
  - `behavior_expiry`
  - `trail`
  - `approx pheromone`

其中，真正决定移动质量的关键隐藏项是：

- `last_move`
- `behavior` 还剩几回合
- `pheromone`

### 输出

不建议直接输出大而全的 JSON 回前端。

给 AI 真正有用的输出应收敛成几类：

1. `enemy_mass[t][cell]`
2. `enemy_pressure[t][region]`
3. `base_risk[t]`
4. `frontline_band[t]`
5. `teleport_risk_window`
6. 若干 query 槽位的局部覆盖收益

也就是说，真正在线上决策里使用时，`ExpectedFront` 更应该返回“标量和局部表”，而不是完整展示型结构。

### 时间范围

推荐拆成三段。

#### A. `t = 1..2`

这两回合尽量做精确。

原因：

- 行为还没大规模退化
- teleport 还没把分布打散
- 对防守决策最关键

处理方式：

- `DEFAULT`：精确一步 softmax
- `CONSERVATIVE / CONTROL_FREE`：one-hot
- `RANDOM`：均匀
- `BEWITCHED`：target-conditioned softmax
- `FROZEN`：本回合停滞

#### B. `t = 3..4`

这两回合做 mean-field 期望传播。

处理方式：

- 保留 `(cell, last_move)` 状态
- 用 occupancy 近似 crowding
- 叠加塔伤近似
- 允许行为衰减

这里不再试图维护完整联合分布树，而是只维护每只蚂蚁的边缘分布。

#### C. `t >= 5`

不再做格点级严肃预测，只保留粗风险。

原因：

- 特殊行为开始普遍退化
- teleport 窗口会重置一部分蚂蚁分布
- 相关性误差积累明显变大

这里更适合输出：

- 某些区域未来仍可能有质量
- 基地附近风险上界
- 传送窗口后的风险增量

### 对各类蚂蚁的处理

#### `DEFAULT`

推荐做法：

- 单步精确 softmax
- 多步用期望传播

这是 `ExpectedFront` 的主力类型。

#### `CONSERVATIVE`

推荐做法：

- 直接按确定性路径传播

这类蚂蚁很便宜，没必要简化成 `DEFAULT`。

#### `CONTROL_FREE`

推荐做法：

- 也按确定性路径传播
- 并显式标记 teleport 免疫

这类同样便宜，而且如果把它误当 `DEFAULT`，会在 teleport 窗口严重预测错误。

#### `RANDOM`

推荐做法：

- 在 `ExpectedFront` 中先作为均匀扩散处理
- 但单独记录其质量占比
- 一旦它靠近基地或 teleport 窗口，就转交给 pessimistic layer

也就是说，不要把 `RANDOM` 当成普通 `DEFAULT`，但也没必要在主图里给它开大搜索树。

#### `BEWITCHED`

推荐做法：

- 保留明确目标
- 在 `t = 1..2` 尽量精确
- 到达目标或超时后再退化成 `DEFAULT`

这类也不该提前忽略，因为它可能在局部造成非常明显的逆向或回撤流。

#### `FROZEN`

推荐做法：

- 本回合停滞
- 下一回合转为其 pending behavior

当前一个容易偷懒的错误是：

- 只把它当作“停一回合后继续原行为”

这在 `ICE -> RANDOM` 链里会错。

### 行为之间是否有关联 / 耦合

有，但要区分“保留哪些耦合”和“放弃哪些耦合”。

#### 推荐保留的耦合

1. 同玩家 crowding
2. 塔伤和塔覆盖
3. 行为衰减
4. `BEWITCHED` 目标条件
5. teleport 免疫与非免疫差异

#### 推荐放弃的耦合

1. 完整联合分布
2. 多只蚂蚁路径竞争的精确相关性
3. teleport 被抽中的组合相关性
4. 多塔目标竞争的完全精确顺序

也就是说，`ExpectedFront` 应该是：

- 保留一阶局部耦合
- 放弃高阶联合相关

这正是它能快的原因。

### 它是否包含坏情况分析

单独的 `ExpectedFront` 不包含。

它是：

- 期望前线图

不是：

- 坏情况包络
- 概率上界证明
- adversarial rollout

如果目标是“尽量不掉基地血”，推荐在 `ExpectedFront` 外面再套一层 pessimistic analysis。

## 我设想中的 pessimistic layer

这是和 `ExpectedFront` 配套的一层，不应该混在一起。

### 目标

回答：

- 在比较坏的抽样结果下，这个候选动作是否仍可能漏怪

### 建议只对少量对象做

不要对所有蚂蚁都做。

只对：

- 距离我方基地最近的若干敌蚂蚁
- `RANDOM` 敌蚂蚁
- teleport 回合前后的非免控敌蚂蚁
- 被 `BEWITCHED` 后可能形成短时间反常流向的蚂蚁

### 建议的三种坏情况近似

#### A. Base-adversarial move choice

对靠近基地的关键蚂蚁，不按期望走，而是偏向：

- 选择更接近我方基地的高概率分支

不是选绝对最坏的非法分支，而是选：

- “概率不太低、但更危险”的分支

#### B. Teleport risk envelope

在 `round % 10 == 9` 的窗口，对所有非 `CONTROL_FREE` 敌蚁额外记录：

- 传送后落入危险半径的概率上界

这里没必要知道它精确落在哪，只要知道：

- 会不会被重置到更坏区域

#### C. Random ant particle refinement

对靠近基地的 `RANDOM` 蚂蚁，单独跑很小样本粒子：

- `8 / 16 / 32` 条就够

目标不是精确估计均值，而是看：

- 是否存在稳定漏怪路径

### 输出形式

推荐只输出几个偏防守标量：

1. `leak_risk_1`
2. `leak_risk_2`
3. `teleport_leak_risk`
4. `worst_front_mass_near_base`
5. `critical_ant_count`

这层不应该直接取代主评分，而应该作为：

- 剪枝条件
- hard constraint
- 或强惩罚项

## 和旧版稀疏操作的兼容性

我认为是兼容的，而且兼容得比全局 Monte Carlo 更自然。

旧 `ANTWar-AI` 的稀疏性主要来自两点：

1. 候选动作生成很稀疏
   - 固定槽位
   - 固定分组
   - 少量 build / upgrade / sell 组合
2. 评估重点是 fail-round / danger / 近基风险

这在旧 AI 代码里很清楚：

- 候选动作生成：`series_action(...)`
- 危险回合与 fail-round：`Node::evaluate()`

`ExpectedFront` 很适合放在这个结构里当评估器，而不是替掉整个结构。

### 推荐的接法

#### 第 1 层：稀疏候选生成

沿用旧思路：

- 固定槽位
- 少量 build
- 少量 upgrade
- 少量 sell + build / sell + upgrade

#### 第 2 层：静态合法性和经济筛

包括：

- coin
- EMP 风险
- group 互斥
- 槽位稀疏约束

#### 第 3 层：一次性生成当前 `ExpectedFront`

这一步只和“当前局面”有关。

#### 第 4 层：对每个候选只做局部重评分

这里是稀疏兼容性的关键：

- 不必为每个候选完整重跑全局 forecast
- 只要重新计算“这个候选新增/改变的塔”对当前前线图的局部覆盖收益

也就是说，可以把评估拆成：

- 敌方未来分布：主要由当前局面决定
- 己方候选操作的收益：主要由少数局部塔位决定

这比“每个候选都做完整 forward simulation”更适合稀疏操作。

#### 第 5 层：只对极少数候选再做 pessimistic refinement

比如：

- 先留下 top `3-5`
- 再跑坏情况检查

### 兼容性的结论

`ExpectedFront` 和稀疏决策不是冲突关系，而是：

- 稀疏生成器
- 配合一个分布式前线评估器
- 再配一个小规模悲观修正器

这是我认为最接近“旧 AI 思路迁移”的结构。

## 当前我最认可的迁移路线

如果我们现在就做一个旧版 AI 迁移版，我更倾向于：

1. 先做纯防守 evaluator
   - 只看敌蚂蚁 + 我方塔
   - 目标只看己方基地血
2. 行为空间上先弱化出生型特殊行为
   - 但保留控制塔诱发行为
3. 己方动作空间先收窄
   - 主打 `quick / mortar / heavy`
   - 先不主动建 `ICE / CANNON / PULSE`
4. `ExpectedFront` 只做 `1-4` 回合
5. `ExpectedFront` 不直接给总分
   - 先做 danger map / fail-round proxy / candidate pruning
6. 对最危险区域再做 pessimistic refinement

## 目前最值得继续讨论的点

如果后续按你的“朴素模拟 + 稀疏操作”路线推进，我认为最关键的讨论点只有 4 个：

1. 稀疏候选动作到底保留哪些塔和哪些组合
2. fail-round / ruin-round 现在用什么指标替代旧版精确模拟
3. teleport 窗口的坏情况约束怎么写
4. `ExpectedFront` 在每回合里是只算一次，还是允许对 top 候选重算少量局部版本

我认为第 4 点的合理答案大概率是：

- 绝大多数候选共享同一张前线图
- 只有少数候选需要局部重算
