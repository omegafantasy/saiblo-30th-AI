# Game1 Simulation Randomness Analysis

本文只关注 `Game1/Ant-Game` 的真实移动与局面预测问题，代码真值优先级如下：

1. `/www/Game1/Ant-Game/SDK/backend/engine.py`
2. `/www/Game1/Ant-Game/game/src/game.cpp`
3. `/www/Game1/Ant-Game/SDK/utils/constants.py`

旧 `forecast.py` 仅能视为历史残留参考，不能再当作“真实模拟器”使用。它的移动逻辑仍接近旧版确定性信息素寻路，不符合当前 `softmax + crowding + behavior + teleport` 的代码真值。

## 真实随机模型

当前移动真值：

- `DEFAULT`
  - 候选邻居评分：`pheromone * weight - 1.25 * crowd`
  - `weight` 取值：
    - 更接近敌基地：`1.25`
    - 距离不变：`1.0`
    - 更远：`0.75`
  - 用 `temperature = 4.0` 做 softmax 采样
- `CONSERVATIVE`
  - 与 `DEFAULT` 使用同样的 `raw_score`
  - 但直接选 `raw_score` 最大的方向，不采样
- `CONTROL_FREE`
  - 与 `CONSERVATIVE` 相同，确定性移动
- `RANDOM`
  - 对所有合法邻居均匀采样
- `BEWITCHED`
  - 目标改为 `bewitch_target`
  - 评分：`(current_dist - next_dist) * 4.0 - 1.25 * crowd`
  - 用 `temperature = 1.5` 做 softmax 采样

其他关键点：

- `RANDOM` / `BEWITCHED` 允许回头，其他行为默认禁止原路折返。
- 每 `10` 回合会随机传送一部分非 `CONTROL_FREE` 蚂蚁。
- `RANDOM` 会在 `5` 回合后衰减回 `DEFAULT`。
- `BEWITCHED` / `CONTROL_FREE` 等特殊行为也会衰减。

这意味着多轮预测不能再使用“旧版确定性单线推进”假设。

## 统计工具

新增沙盒：

- `/www/Game1/Ant-Game/tools/ant_move_sandbox.py`

用途：

- `survey`
  - 枚举大量位置，计算单步精确转移分布
- `simulate`
  - 基于真实 `engine.GameState` 做多轮 Monte Carlo
- `benchmark`
  - 测当前 Python 真值引擎下的分布计算和整回合吞吐量

本轮输出保存在：

- `/www/docs/generated/sandbox/`

配套汇总报告：

- `/www/docs/game1_simulation_perf_and_behavior_report.md`

讨论补充：

- `/www/docs/game1_expectedfront_discussion_20260311.md`

## 在线版当前落地

截至当前版本，`/www/Game1/antgame_ai_cpp/v3/ai_v3.cpp` 已经不再是纯静态启发式。

它现在额外做了 3 件事：

- 从相邻公共回合重建 `last_move`
- 维护每只蚂蚁的 `trail`，并按可见消失事件近似重建 `pheromone`
- 在 `build_snapshot` 时一次性生成 `3` 回合 movement-only `ExpectedFront`

这张未来质量图当前的状态是：

- 在线版已经能稳定算出来
- 当前先保留为分析层和后续候选筛选层的基础设施
- 还没有保留到正式评分主链里

当前结论也很明确：

- `ExpectedFront` 适合作为分析层和候选筛选层
- 不适合直接线性塞进当前 `v3` 的 tower 评分

我已经做过一次直接接入测试，结果在多 seed 下明显退化，甚至会输给 `random`。所以当前仓库里保留的是：

- `pheromone / trail / last_move / behavior` 的在线重建
- `3` 回合未来质量图的计算基础设施

而不是“已经验证有效的 tower 打分公式”。

注意：

- 线上纯 `C++` 版仍然无法像 Python bridge 那样直接拿到引擎内部真值状态
- `bewitch_target`、teleport、控制连锁等仍是近似处理
- 所以 `v3` 现在是“已接入短视野分布预测”，但还不是完整真值模拟器

## 问题 1：softmax 下如何预测多轮状态

结论：不要把所有蚂蚁一刀切地做全局 Monte Carlo，也不要继续用旧版确定性 forecast。推荐三层模型。

### 层 1：单步精确分布

对每只蚂蚁，先算真实的一步分布：

- `DEFAULT` / `BEWITCHED`：精确算 softmax 概率
- `CONSERVATIVE` / `CONTROL_FREE`：直接 one-hot
- `RANDOM`：均匀分布

这一步必须做成“精确内核”，因为它既是统计分析基础，也是后续期望传播和采样的共同底座。

### 层 2：多步期望传播

对大多数评估任务，不需要维护完整联合分布树。更稳的办法是做近似的 occupancy propagation：

- 用 `P_t(cell, behavior, level)` 表示某类蚂蚁在某格的期望占用
- 每回合按一步转移矩阵向前推
- crowding 不再按单只蚂蚁现状计算，而是按期望占用近似

适用场景：

- 比较建塔/升级前后的整体防线强弱
- 估算未来 `1-4` 回合前线压力
- 做 danger forecast / ruin forecast 的快速版本

优点：

- 复杂度接近“蚂蚁数 x 候选数 x 预测深度”
- 不会像全树分支那样指数爆炸

缺点：

- 忽略了同回合采样之间的相关性
- 遇到 teleport 回合时误差会突然放大

### 层 3：局部粒子 / 条件 Monte Carlo

真正需要采样的，只应是“高价值候选动作附近的少量关键敌蚂蚁”：

- 靠近己方基地的蚂蚁
- 被控制后的 `BEWITCHED` 蚂蚁
- `RANDOM` 蚂蚁
- 临近第 `10` 回合传送窗口的蚂蚁

建议做法：

- 先用层 2 筛候选动作
- 只对前若干候选做 `N=16/32/64` 条件采样
- 比较候选时使用同一批随机数种子

这样可以显著降低方差。比较两个候选动作时，用 common random numbers 比独立采样稳得多。

### 实战建议

- `1-2` 回合：优先精确或近精确
- `3-4` 回合：优先期望传播
- `5-9` 回合：只保留粗风险量，不追求格点级精度
- `10` 回合前后：把非 `CONTROL_FREE` 蚂蚁视为“分布重置风险”

也就是说，当前游戏更适合“短视野精确 + 中视野期望 + 少量重点采样”的混合方案，而不是单一大 Monte Carlo。

## 问题 2：不同类型蚂蚁如何分别处理

### `CONSERVATIVE` / `CONTROL_FREE`

最简单，也最适合走确定性模拟：

- 单步是 one-hot
- 多步就是确定路径
- 这两类蚂蚁应当作为 danger forecast 的主干输入

### `DEFAULT`

看起来是随机，实际上通常不算太随机：

- 单步常常只有 `2-4` 个候选
- 分布多数时候很尖锐
- 适合：
  - 一步精确分布
  - 多步期望传播
  - 对前线关键蚂蚁再补少量采样

### `BEWITCHED`

本质是“带目标的受控 softmax”：

- 温度更低，通常比 `DEFAULT` 更尖锐
- 目标明确，适合做短视野精确控制价值评估
- 需要单独跟踪：
  - 剩余行为时间
  - 目标点是否已到达

### `RANDOM`

是真正高熵的麻烦项：

- 不能指望路径级精确预测
- 更适合用 occupancy diffusion 或采样近似
- 只在关键区域保留粒子，其他地方直接转成期望占用

### 冻结、死亡、到达、老死

这些状态不该再进入移动分支：

- `FROZEN` 当前回合不动
- `FAIL/SUCCESS/TOO_OLD` 直接从移动系统移除

## 问题 3：softmax 常见概率与常见行为

本轮用沙盒做了几组代表性统计。

### 单步分布统计

1. `DEFAULT + uniform pheromone + no crowd`
   - 文件：`survey_default_uniform_none.json`
   - `top1 mean = 0.8547`
   - `top1 median = 1.0`
   - `P(top1 >= 0.85) = 0.7093`

含义：

- 即使在最朴素的均匀信息素下，`DEFAULT` 也经常是“几乎确定的”
- 只有在左右对称、且两边原始分数完全相同的格子上，才常出现 `50/50`

典型平局例子：

- `(2,5)` 位置，两条前进路 raw score 相同，形成 `0.5 / 0.5 / 0`

2. `DEFAULT + center_bias + pair crowd`
   - 文件：`survey_default_center_pair.json`
   - `top1 mean = 0.9926`

3. `DEFAULT + lane_bias + cluster crowd`
   - 文件：`survey_default_lane_cluster.json`
   - `top1 mean = 0.9515`

含义：

- 一旦信息素有明显结构，或者布局把路径偏好拉开，`DEFAULT` 的随机性会进一步塌缩
- 所以对实战 AI 而言，`DEFAULT` 的“随机性”往往更像局部岔路，而不是全局乱走

4. `BEWITCHED + uniform`
   - 文件：`survey_bewitched_uniform_none.json`
   - `top1 mean = 0.8049`
   - 最平的代表例子约 `0.482 / 0.482 / 0.033`

含义：

- `BEWITCHED` 常在两条都能接近目标的路上二选一
- 但由于温度更低、目标更明确，它通常仍是尖锐分布

5. `RANDOM + uniform`
   - 文件：`survey_random_uniform_none.json`
   - `top1 mean = 0.3527`
   - 中位数约 `1/3`

含义：

- `RANDOM` 才是真正的高熵扩散源
- 如果要节省算力，Monte Carlo 预算应优先给它

### 多轮代表性行为

`simulate --layout naive_control --pheromone center_bias`

1. `DEFAULT`
   - 文件：`sim_default_center_control_256.json`
   - 前 2 回合完全确定
   - 第 3 回合分成 `50/50`
   - 第 5 回合又汇合到单一路径

这说明：

- 多轮分布并不总是持续发散
- 很多岔路只是短期局部对称

2. `CONSERVATIVE`
   - 文件：`sim_conservative_center_control_256.json`
   - 全路径确定，只由 tie-break 决定选哪一支

3. `RANDOM`
   - 文件：`sim_random_center_control_256.json`
   - 第 1 回合后 top1 只有约 `20%`
   - 第 `3-7` 回合 top1 已跌到约 `6%-14%`

4. `BEWITCHED`
   - 文件：`sim_bewitched_center_control_256.json`
   - 第 3 回合 top1 仍有 `94%`
   - 第 4 回合在对称岔路上裂成约 `51% / 43%`

总体结论：

- `DEFAULT` 与 `BEWITCHED` 的单步随机性常常比直觉小
- 真正会让多轮模拟大爆炸的是：
  - `RANDOM`
  - crowding 相互作用
  - 第 10 回合传送

## 问题 4：如何从 C++ 角度全面优化模拟效率

### 先修正确性边界

在优化前，先固定一条原则：

- 生产模拟器必须跟 `engine.py/game.cpp` 对齐
- 旧 `forecast.py` 不能继续作为“优化目标”

### 最值得做的四个优化

1. 预计算地图与邻接

- 对每个合法格预存：
  - 是否路径
  - 是否高地
  - 6 个邻居 ID
  - 到双方基地距离
  - 是否在己方半场

这样每次移动决策都不再做重复几何判断。

2. 把 crowding 从 `O(ants^2)` 降到 `O(ants + cells)`

当前真值里，crowding 本质只依赖：

- 目标格同格友军数
- 目标格相邻 1 圈友军数

因此完全可以维护：

- `occ[player][cell]`
- `adj_occ[player][cell] = sum(occ[player][neighbor])`

则某格的 crowding 近似真值可在 `O(1)` 取到：

- `same_cell = occ[player][cell] - self_here`
- `adj = adj_occ[player][cell] - self_adj_contrib`
- `penalty = same_cell + 0.35 * adj`

这是最关键的速度突破点。

3. 用 SoA 和紧凑数组，而不是大量对象

推荐把移动相关核心状态改成：

- `x[]`
- `y[]`
- `hp[]`
- `level[]`
- `status[]`
- `behavior[]`
- `age[]`
- `last_move[]`

好处：

- cache 更友好
- 方便批量扫描
- 方便做 occupancy 更新与 apply/undo

4. 候选移动只走固定小数组

每只蚂蚁候选最多 `6` 个方向，实际常见只有 `2-4` 个。

因此不要为候选方向分配动态容器，直接用栈上小数组：

- `dir[6]`
- `nx[6]`
- `ny[6]`
- `score[6]`

softmax 也应做成专门的 2-6 项小核函数。

### 模拟器分层建议

建议未来 C++ 模拟模块拆成三层：

1. `ExactMoveKernel`
   - 输入单只蚂蚁与 occupancy
   - 输出精确一步分布
2. `ExpectedFrontSimulator`
   - 基于期望占用推进 `1-4` 回合
   - 产出 danger / pressure / frontline
3. `ParticleRefiner`
   - 只对关键蚂蚁和少量候选动作做采样

这样做的好处是：

- 大部分评估不需要复制完整状态
- 只把高成本采样花在关键候选上
- 更容易满足后续 `200ms` 单步预算

### 目前能看到的吞吐量下界

本轮是 Python 真值引擎下界，不是最终 C++ 上限。

1. `empty` 布局，20 只初始蚂蚁
   - 文件：`benchmark_16ants_empty.json`
   - 单步分布计算约 `23242 eval/s`
   - 整回合推进约 `6132 rounds/s`
   - 等价 `500` 回合对局约 `12.27 match/s`

2. `naive_control`，28 塔，20 只初始蚂蚁
   - 文件：`benchmark_16ants_14slots.json`
   - 单步分布计算约 `17766 eval/s`
   - 整回合推进约 `2487 rounds/s`

3. `naive_control`，36 塔，20 只初始蚂蚁
   - 文件：`benchmark_20ants_18slots.json`
   - 单步分布计算约 `19510 eval/s`
   - 整回合推进约 `2020 rounds/s`

当前平均每次 move eval 的候选数约为 `3.7`。

### 对 C++ 的保守估计

如果把移动预测内核单独重写成上面的数组式结构，并把 crowding 改成 occupancy 取数，保守预期：

- 单步移动分布内核：至少应比当前 Python 真值实现快一个数量级
- 更现实的目标区间：
  - `2e5 - 8e5` 次 move eval / 秒
  - 轻量前线预测 `1e4 - 5e4` ant-step / `200ms`

这不是实测上限，而是当前代码结构下一个合理的工程目标。

## 本轮实现进展

已经新增一个独立的 C++ 一步分布内核：

- `/www/Game1/antgame_ai_cpp/sim/exact_move_kernel.cpp`
- `/www/Game1/antgame_ai_cpp/sim/README.md`

并新增 Python 对拍脚本：

- `/www/Game1/Ant-Game/tools/verify_exact_move_kernel.py`

对拍结果：

- 文件：`verify_exact_move_kernel.json`
- `24` 个状态
- `308` 只蚂蚁
- `812` 条 move row
- `max_prob_diff = 2.22e-16`
- `max_raw_diff = 0`
- `max_score_diff = 0`

说明当前 `ExactMoveKernel` 已经和 Python 真值一步分布对齐，可以作为后续 `ExpectedFrontSimulator` 的可信底座。

当前 C++ benchmark：

- 文件：`exact_move_kernel_benchmark_cpp.json`
- 在当前 `32` 蚂蚁的合成负载下，约 `2.7e6 move eval/s`

关键原因：

- 第一版走了 `vector + json` 热路径，只有 `4e4` 量级
- 改成固定 `6` 路小数组后，速度直接提升两个数量级以上

这说明当前问题的主要性能损耗来自：

- 动态分配
- 通用容器
- JSON 包装路径

而不是 softmax 本身。

按 `2.7e6 eval/s` 粗算：

- `200ms` 内大约可做 `5.4e5` 次一步分布评估

这已经足够支持：

- 少量候选动作
- 数回合 occupancy propagation
- 再叠加一层小样本重点采样

## 短视野 ExpectedFront 原型

当前 `exact_move_kernel` 里已经补了一个 `--expected-front` 原型，额外跟踪了：

- `last_move`
- 期望 occupancy
- 期望 crowding
- 近似 tower damage
- `RANDOM / SPECIAL` 的简单回合衰减
- `FROZEN` 的一回合停滞

并新增对比脚本：

- `/www/Game1/Ant-Game/tools/compare_expected_front.py`

当前对比结果：

1. 单只 `DEFAULT`，空场，`center_bias`
   - 文件：`compare_expected_front_default_single.json`
   - `0-4` 回合 `query_tv_distance_topk = 0`
   - own pressure 与 Monte Carlo 完全一致

2. 两只 `DEFAULT`，带 crowding，空场
   - 文件：`compare_expected_front_default_pair.json`
   - 第 `3-4` 回合 `query_tv_distance_topk ≈ 0.0059`
   - 说明 mean-field 在低随机、低攻击场景下已经很接近真值

3. 单只 `RANDOM`，空场
   - 文件：`compare_expected_front_random_single.json`
   - 第 `2-4` 回合 `query_tv_distance_topk` 上升到约 `0.10 - 0.28`
   - 说明 `RANDOM` 确实不适合只靠期望传播，需要粒子或 Monte Carlo 补充

4. 单只 `DEFAULT`，`naive_core` 塔布局
   - 文件：`compare_expected_front_default_single_naive_core.json`
   - 第 `0-4` 回合 `query_tv_distance_topk = 0`
   - 表明在基础塔伤场景下，当前 `ExpectedFront` 已经能正确反映“进入塔程即被击杀”的情况

这个结果和前面的判断是一致的：

- `DEFAULT / CONSERVATIVE / CONTROL_FREE` 可以优先走 ExpectedFront
- `RANDOM` 需要单独保留采样预算
- `BEWITCHED` 更适合走短视野精确控制评估

当前仍未进入 `ExpectedFront` 的机制：

- `ICE / CANNON / PULSE` 的控制效果
- `Deflector / EmergencyEvasion`
- teleport

## 当前建议

下一步不要先写“大而全”的新模拟器。正确顺序应当是：

1. 用当前沙盒继续做更多位置与行为统计
2. 先实现 C++ `ExactMoveKernel`
3. 再实现基于 occupancy 的 `ExpectedFrontSimulator`
4. 最后只对关键候选接 `ParticleRefiner`

如果先上完整 Monte Carlo，很大概率会在 `RANDOM + teleport + crowding` 三个因素上把算力烧光，但评估质量仍不稳定。
