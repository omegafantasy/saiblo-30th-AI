# Game1 Current Search Baseline

这份文档描述当前 `Game1/antgame_ai_cpp/cpp_heavy_baseline` 与 `cpp_lure_v2` 实际使用的搜索与估值逻辑。2026-04-27 起，baseline 已被当前 v2 完全覆盖，二者是同一冻结点。

说明：

- 文件名沿用历史命名
- 当前实现已经不是旧版 `random_search_baseline.hpp` 的两回合搜索
- baseline 入口是 `antgame_sdk/lure_strategy_baseline.hpp`
- 默认兼容入口 `antgame_sdk/lure_strategy.hpp` 当前仍指向 v2

## 1. 当前动作分解

每回合动作被拆成三部分：

- `base`
- `lure`
- `lightning`

根节点候选集合为：

- `hold`
- 单独 `base`
- 单独 `lure`
- `recycle-only base + lure`
- 单独 `lightning`

也就是：

- 常规防守操作通常只在 `base` 或 `lure` 中选一种
- 只有 `base` 动作是纯回收类时，才允许与 `lure` 组合
- 闪电是独立候选，不与 `base/lure` 相乘

## 2. 当前允许的 base 动作

`base` 只围绕靠近基地的固定槽位展开。

当前结构：

- 永远保留 `base_hold`
- `base` 位置使用旧版位置表里的 `C / L / R / LL / RR` 系列，但暂时禁用 `C2 / C3` 建塔
- 非 lure 塔最多保留 `max_non_lure_towers`
- 空槽位可生成 `build`，以及 `build -> allowed level-2 tower` followup
- 已有塔可生成 `downgrade/sell`
- 已有 Basic 可直接升允许的二级塔
- 已有 Quick 可升 `Sniper`
- 已有 Heavy 且位于 `C1` 时，可生成 `downgrade -> Quick`
- 可生成纯回收类双降级候选
- 可生成 base swap：
  - 先把 Basic 或一级塔卖到底
  - 再在其他 base 槽位建塔
  - 若源塔已卖到底且金币足够，可同回合建后升二级
  - 若源塔第一回合只是降级，则 followup 继续卖到底，并可再执行目标塔升级

二级候选规则：

- `C1`：`Heavy`，以及过渡到 `Quick -> Sniper`
- `C1` 已经是 `Sniper` 时，其他 base 槽位允许 `Heavy / Quick / Mortar`
- `C1` 未成 `Sniper` 时，其他 base 槽位允许 `Heavy / Mortar`
- `Sniper` 是当前唯一 3 级塔候选

当前 base 动作不再做复杂位置启发；除统一 `hold_bonus` 外，只保留以下 C1 结构项：

- `c1_build_bonus`：建 `C1` 的 root heuristic
- `c1_heavy_bonus` / `c1_heavy_side_trans_bonus`
- `c1_quick_trans_bonus` / `c1_sniper_trans_bonus`

这些 C1 状态项只作用于 `C1`，并以 root 后局面和起点金币阈值判定。

## 3. 当前允许的 lure 动作

当前只允许单 lure 结构。

具体规则：

- 永远保留 `lure_hold`
- 若存在 lure 塔且有战斗蚁贴近到给定距离内，直接只生成“强制卖塔”
- 若当前没有 lure 塔：
  - 所有合法 lure 槽位都生成 `build`
  - 不做额外位置打分
- 若当前已有 lure 塔：
  - 生成该 lure 的 `sell`
  - 对所有其他合法 lure 槽位生成 `sell + build`
  - 不做额外位置打分

当前不会再对 lure 建塔位置做：

- 距战斗蚁加分
- 距基地远近加分
- 候选前几名裁剪

也就是说，lure 的位置优劣完全交给 rollout 终点评估决定。

## 4. 当前闪电候选

闪电单独生成。

当前流程：

- 若冷却或金币不足，则不生成闪电候选
- 对以棋盘唯一中心 `(9,9)` 为中心、六边形距离 `<= lightning_center_radius` 的合法格子生成候选
- baseline / v2 默认半径为 `5`，候选中心数为 `91`
- 每个合法中心是一个 UCB arm
- UCB 总 rollout 数由 `lightning_ucb_total_rollouts` 控制
- 闪电候选当前不带前置 `downgrade/sell`

当前闪电启发只考虑：

- 对敌方塔的等效价值伤害
- 当前敌方超武窗口
- rollout 中相对无闪电对照组减少的战斗蚁 threat
- 破盾、伤害、击杀等 counterfactual bonus

不再给：

- 普通蚂蚁 presence 额外奖励
- 战斗蚁纯数量奖励

## 5. 合法性与操作顺序

当前所有组合操作都使用“严格合法”规则：

- 要么整组操作全部合法
- 要么整组候选直接丢弃

不会再出现：

- 一个组合里某一步非法
- 然后被静默裁成子集继续搜索

同回合操作顺序还做了统一优化：

- `DowngradeTower` 永远先于 `BuildTower`
- 若有多个 `DowngradeTower`，按当前塔血量从高到低执行

这样可以稳定利用：

- 先拆后建带来的金币与塔数优势
- 多拆时先拆高血塔带来的更高返还

## 6. Rollout

每个根节点候选都独立做 Monte Carlo rollout。

当前设置：

- 普通候选 horizon: `long_eval_horizon`，并在 `mid_eval_horizon` 做一次中点评估
- 闪电候选 horizon: `lightning_horizon`
- 普通候选 rollout 次数: `rollout_count`
- 闪电候选 rollout 次数：全体闪电 arm 共享 `lightning_ucb_total_rollouts`
- 快速模拟默认忽略每 `10` 回合的周期随机移动机制

rollout 中未来回合不再主动生成完整 `base × lure` 计划，只保留轻量 reactive 回收：

- 若有战斗蚁贴身己方塔，固定尝试降级/拆塔回收
- 否则不做未来回合主动操作
- 这样能保留 lure 策略里最关键的“贴身不白送塔”
- 同时避免 rollout 中每回合重复生成大量 STL plan

因此当前 rollout 是：

- 根节点用“搜索 + 终点评估”
- 后续回合用“贴身回收”反应式规则

## 7. 终点评估

终点评估只看以下几项：

- 基地血量
- 己方塔全部拆完后的可回收价值
- 当前金币
- 普通蚂蚁 threat
- 战斗蚂蚁 threat

其中：

- 普通蚂蚁 threat 只看离基地距离与血量比例
- 战斗蚂蚁 threat 取“对基地威胁”和“对己方塔钱的威胁”的较大者
- 战斗蚂蚁的威胁缩放还会受到 `Random` / `Bewitched` 行为影响

当前 `combat threat` 的塔威胁项只看旧版位置表里的核心建塔位，避免外圈 lure 塔本身把终点评估拖得过重。

## 8. 参数入口

当前所有直接影响策略打分的参数，按版本独立放在：

- baseline：`Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_baseline_params.hpp`
- v2：`Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v2_params.hpp`

当前实现里，策略 header 不应再包含未暴露到参数文件的隐藏评分常数。

## 9. 代码入口

关键文件：

- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_baseline.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_baseline_params.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v2.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v2_params.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_params.hpp`
- `Game1/antgame_ai_cpp/cpp_heavy_baseline/ai_cpp_heavy_baseline.cpp`

辅助工具：

- `Game1/antgame_ai_cpp/tools/eval_cpp_selfplay.py`
- `Game1/antgame_ai_cpp/tools/analyze_selfplay_batch.py`
- `Game1/antgame_cpp_sdk/examples/sdk_lure_perf.cpp`
- `Game1/antgame_cpp_sdk/examples/sdk_defense_parity.cpp`
- `Game1/antgame_cpp_sdk/examples/sdk_lure_inspector.cpp`

## 10. 当前局限

当前实现仍然是简化 baseline，不代表最终策略。

主要局限：

- `base` 和 `lure` 仍是模板化候选，不是完整同回合 op-list 生成
- 主动 `EMP/Deflector/Evasion` 还没纳入搜索
- lure 的自适应性主要来自“贴近即卖”和未来回合贴身强制回收，尚未发展成更强的路径级控制
- `C1` 路线切换仍保留一个显式金币阈值
- 对普通蚂蚁和战斗蚂蚁的估值比例仍需要继续校准

## 11. 当前性能口径

2026-04-27 已确认：

- `DefenseSimulator` 内层状态以固定容量数组为主
- `DefenseSimulator::clone()` 不复制派生 move cache / lookup cache
- 当前 `MoveCache` 约 `208KB`
- 16 组 256 回合全 log self-play：
  - P0/P1 平均决策耗时约 `1.32s / 1.13s`
  - P0/P1 p95 决策耗时约 `2.72s / 2.41s`
  - P0/P1 平均候选数约 `143 / 123`
- 16 组 512 回合全 log self-play：
  - P0/P1 平均决策耗时约 `1.38s / 1.18s`
  - P0/P1 p95 决策耗时约 `2.80s / 2.52s`
  - P0/P1 平均候选数约 `153 / 130`
- 单回合模拟最大热点仍是 `move_cache` 反向路径规划
- 当前性能已足够用于离线调参；后续暂不以 `200ms` 为硬目标

## 12. 最新强度与对拍记录

2026-04-27 测试：

- `Game1/antgame_ai_cpp/eval_lure_ucb_full_256_16_20260427`
  - `16/16` 局严格跑到 `256` 回合
  - P0/P1 平均终局血量 `26.5 / 28.125`
  - P0/P1 平均终局金币 `273.25 / 225.375`
  - 决策分布：`hold 6398`，`base 863`，`lure 839`，`lightning 108`
- `Game1/antgame_ai_cpp/eval_lure_ucb_full_512_16_20260427`
  - 平均回合 `503.8125`
  - 胜负：P0 胜 `9`，P1 胜 `6`，未归零到上限 `1`
  - P0/P1 平均终局血量 `16.0 / 15.125`
  - P0/P1 平均终局金币 `485.4375 / 319.1875`
  - 决策分布：`hold 12492`，`base 1762`，`lure 1660`，`lightning 244`

同日 fast/native 对拍：

- 文件：`Game1/antgame_ai_cpp/eval_lure_ucb_full_512_16_20260427/parity_32_round252_432_rollout1000.json`
- 32 个 case，`1000` rollout，`6` 回合窗口，全部成功执行
- 特意避开跨 10 回合随机移动窗口
- 终点 fast-native 平均绝对差：
  - 基地血 `0.049`
  - 金币 `0.080`
  - 塔可回收价值 `0.398`
  - 总评分 `12.04`
- 32 个 case 中包含 4 个 active effect 根状态，未发现结构性偏差
