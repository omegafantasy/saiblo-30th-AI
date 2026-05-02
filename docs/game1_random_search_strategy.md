# Game1 Current Search Baseline

这份文档描述当前 `Game1/antgame_ai_cpp/cpp_heavy_baseline` 实际使用的搜索与估值逻辑。2026-04-27 起，baseline 已被当前 v2 完全覆盖；清理后 `cpp_lure_v2` 源码目录和打包目标已删除。`cpp_lure_v3` 在此冻结点之外独立迭代，并且是当前本地最优解。

说明：

- 文件名沿用历史命名
- 当前实现已经不是旧版 `random_search_baseline.hpp` 的两回合搜索
- baseline/v2 的唯一策略实现是 `antgame_sdk/lure_strategy_v2.hpp`
- `antgame_sdk/lure_strategy.hpp` 是默认兼容转发入口；旧 `lure_strategy_baseline*.hpp` 已删除

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
  - 目标塔升级总是作为后续回合 followup 执行，不在同一回合使用刚建出的塔
  - 若源塔第一回合只是降级，则 followup 会先继续卖到底，再按需要执行目标塔升级

二级候选规则：

- `C1`：`Heavy`，以及过渡到 `Quick -> Sniper`
- `C1` 已经是 `Sniper` 时，其他 base 槽位允许 `Heavy / Quick / Mortar`
- `C1` 未成 `Sniper` 时，其他 base 槽位允许 `Heavy / Mortar`
- `Sniper` 是当前唯一 3 级塔候选

当前 base 动作不再做复杂位置启发；除统一 `hold_bonus` 外，只保留以下 C1 结构项：

- `c1_build_bonus`：建 `C1` 的 root heuristic
- `c1_heavy_bonus` / `c1_heavy_side_trans_bonus`
- `c1_quick_trans_bonus` / `c1_sniper_trans_bonus`

这些 C1 状态项只作用于 `C1`。v3 中路线切换阈值以本回合行动前己方等效总金币判定：
`当前金币 + full_tower_salvage_coin`，其中 `full_tower_salvage_coin` 是按最优顺序降级并卖完己方塔后的总回收价值。

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
- baseline / v2 中每个合法中心是一个 UCB arm
- v3 中闪电与 `recycle + lightning` 候选进入独立 lightning UCB 组，并在普通 action 前先完整计算
- 当前 v3/v4 lightning 组默认总预算 `lightning_ucb_total_rollouts=600`，每次补 `lightning_ucb_batch_rollouts=2`

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

2026-05-02 修复了 SDK 状态镜像里的同回合操作列表应用：`PublicState::apply_operation_list()` 现在在已经变更的当前状态上顺序验证操作，只额外记录本回合已使用的 tower id 和 base upgrade 状态。此前旧实现会错误拒绝“先降/卖塔筹钱，再建塔，再 EMP”的合法操作，进而污染 v4 vs v3 的 IA 评测样本。

## 6. Rollout

每个根节点候选都独立做 Monte Carlo rollout。

当前设置：

- 普通候选 horizon: `long_eval_horizon`，并在 `mid_eval_horizon` 做一次中点评估
- 闪电候选 horizon: `lightning_horizon`
- v3 普通候选仍使用固定总预算：`action_base_total_rollouts=8000`、`action_target_total_rollouts=10000`、`action_time_budget_ms=3000`，horizon 为 `6/10` 且 `mid_eval_weight=0.5`。
- v4 普通候选使用实时测速预算：先对 normal action 做可复用 probe，按实测 `us/sample` 和 `action_target_time_ms=3000` 估算本回合等效 base rollout 总数；target 总数为 base 的 `action_target_total_multiplier=1.25`，并受 `action_target_rollouts_per_action=125 * 普通action数` 截断。保底/补样阶段按 `action_max_rollouts_per_batch=100` 分批，并以 `action_time_budget_ms=4000` 作为预算停止条件。截至 2026-05-02，v4 horizon 为 `4/8` 且 `mid_eval_weight=0`。
- 闪电候选 rollout 次数：独立 lightning UCB，总预算 `lightning_ucb_total_rollouts`，每批 `lightning_ucb_batch_rollouts`，并在普通候选前完整跑完
- 快速模拟默认忽略每 `10` 回合的周期随机移动机制

rollout 中未来回合不再主动生成完整 `base × lure` 计划，只保留轻量 reactive 回收：

- 若有战斗蚁贴身己方塔，固定尝试降级/拆塔回收
- v3 会先模拟下一次塔攻击阶段；若能杀掉所有贴身威胁战斗蚁，则跳过这次 reactive 回收
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
- v3 的己方金币与己方塔可回收价值先合并为等效总金币，再按阶梯权重计分：`400` 以内按 `money_weight=10`，超过 `400` 的部分按 `money_weight_above_threshold=6`
- 该金币衰减只作用于己方经济项，不作用于 `lightning_tower_value_ratio` 这类对敌方塔伤害的估值

当前 `combat threat` 的塔威胁项只看旧版位置表里的核心建塔位，避免外圈 lure 塔本身把终点评估拖得过重。

## 8. 参数入口

当前所有直接影响策略打分的参数，按版本独立放在：

- baseline/v2：`Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v2_params.hpp`
- v3：`Game1/antgame_ai_cpp/cpp_lure_v3/include/antgame_ai/lure_strategy_v3_params.hpp`
- v4：`Game1/antgame_ai_cpp/cpp_lure_v4/include/antgame_ai/lure_strategy_v4_params.hpp`

旧 `lure_strategy_baseline_params.hpp` 已删除，不再维护第二套参数。当前实现里，策略 header 不应再包含未暴露到参数文件的隐藏评分常数。

## 9. v3 进攻性超武试验

v3 已独立于 v2 继续迭代 root 搜索与模拟；进攻性 EMP 和回避仍作为最优 root action 之后的后处理：

- 先在本地复制局面并执行 best action
- 若 best action 本身非法，则不追加回避
- 若敌方闪电正在生效，则不追加回避
- 若敌方闪电 CD 小于 `offensive_evasion_min_enemy_lightning_cd`，则不追加回避
- 若 best action 后金币不大于 `offensive_evasion_min_post_action_coins`，则不追加回避
- 若 best action 后 C1 不是 `Sniper`，则不追加回避
- 若己方 `Emergency Evasion` 在 CD，则不追加回避
- 遍历所有合法 `Emergency Evasion` 中心，统计范围内己方 `Worker`
- 覆盖工蚁数达到 `offensive_evasion_min_worker_count` 时追加回避

选点 tie-break：

- 覆盖工蚁数更多优先
- 工蚁数相同，更靠近敌方基地优先
- 仍相同，覆盖战斗蚁更少优先
- 最后按坐标稳定排序

debug summary 会输出 `v3_evasion_used`、`v3_evasion_reason`、`v3_evasion_worker_count`、`v3_evasion_x/y`、`v3_emp_used`、`v3_emp_reason`、`v3_emp_x/y`、`final_first`、`final_pretty` 等字段，用于确认是否真实生效。

2026-04-28 已补充进攻性 `EMP Blaster` 后处理：在与紧急回避相同的敌方闪电空挡和 best action 后金币 gating 下，若己方战斗蚁距敌方顶级塔 `<= 2`，则以该敌方顶级塔为中心释放 EMP。当前实验口径下，首批 v3(P0) vs baseline(P1) 32 局结果为 v3 `12` 胜、baseline `20` 胜；EMP 释放 `3` 次，回避释放 `9` 次；未发现非法操作或坐标反向，replay 中 EMP active effect 坐标漂移来自官方 `drift_items()`。

## 10. 代码入口

关键文件：

- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v2.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v2_params.hpp`
- `Game1/antgame_ai_cpp/cpp_lure_v3/include/antgame_ai/lure_strategy_v3.hpp`
  - v3 对外聚合入口
  - v3 主体实现已拆为 `session`、`core_format/core_ops/core_values`、`plan_types`、`base_rules/base_swap/base_plans`、`lure/lightning/root_plans`、`reactive_targets/reactive`、`threat/rollout_sampling/terminal_eval/rollout_score/evaluation`、`offense`、`decision`
- `Game1/antgame_ai_cpp/cpp_lure_v3/include/antgame_ai/lure_strategy_v3_params.hpp`
- `Game1/antgame_ai_cpp/cpp_lure_v4/include/antgame_ai/lure_strategy_v4.hpp`
  - 2026-04-30 从阶段性最优 v3 复制出的后续实验分支；初始策略、参数和评测口径与当前 v3 一致
- `Game1/antgame_ai_cpp/cpp_lure_v4/include/antgame_ai/lure_strategy_v4_params.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_params.hpp`
- `Game1/antgame_ai_cpp/cpp_heavy_baseline/ai_cpp_heavy_baseline.cpp`
- `Game1/antgame_ai_cpp/cpp_lure_v3/ai_cpp_lure_v3.cpp`
- `Game1/antgame_ai_cpp/cpp_lure_v4/ai_cpp_lure_v4.cpp`
- `Game1/antgame_ai_cpp/cpp_lure_v3a/ai_cpp_lure_v3a.cpp`
  - 激进抗性测试变体：金币 `>=200` 时优先尝试把基地生成蚂蚁升到 2 级，其余操作沿用 v3；不作为当前最优解

辅助工具：

- `Game1/antgame_ai_cpp/tools/eval_cpp_selfplay.py`
- `Game1/antgame_ai_cpp/tools/analyze_selfplay_batch.py`
- `Game1/antgame_cpp_sdk/examples/sdk_lure_perf.cpp`
- `Game1/antgame_cpp_sdk/examples/sdk_defense_parity.cpp`
- `Game1/antgame_cpp_sdk/examples/sdk_lure_inspector.cpp`

## 11. 当前局限

当前搜索仍然是简化模板化实现，不代表最终策略形态。

主要局限：

- `base` 和 `lure` 仍是模板化候选，不是完整同回合 op-list 生成
- 主动 `EMP` 和 `Emergency Evasion` 当前只作为 v3 后处理，不在 rollout 内评估长期收益
- 主动 `Deflector` 还没纳入搜索
- lure 的自适应性主要来自“贴近即卖”和未来回合贴身强制回收，尚未发展成更强的路径级控制
- `C1` 路线切换仍保留一个显式阈值；v3 的阈值输入已改为行动前己方等效总金币，而不是当前持有金币
- 对普通蚂蚁和战斗蚂蚁的估值比例仍需要继续校准

## 12. 当前性能口径

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

## 13. 最新强度与对拍记录

2026-04-30 阶段性最优 v3 测试：

- 结果目录统一位于仓库根目录 `eval_results/`
- 当前 v3 vs baseline 座位平衡 128 局，使用全新 seed `1001:1064`，分 4 批完成：
  - `eval_results/v3_vs_baseline_128_random_equal_newseeds_b1_p0_20260430`
  - `eval_results/v3_vs_baseline_128_random_equal_newseeds_b1_p1_20260430`
  - `eval_results/v3_vs_baseline_128_random_equal_newseeds_b2_p0_20260430`
  - `eval_results/v3_vs_baseline_128_random_equal_newseeds_b2_p1_20260430`
  - `eval_results/v3_vs_baseline_128_random_equal_newseeds_b3_p0_20260430`
  - `eval_results/v3_vs_baseline_128_random_equal_newseeds_b3_p1_20260430`
  - `eval_results/v3_vs_baseline_128_random_equal_newseeds_b4_p0_20260430`
  - `eval_results/v3_vs_baseline_128_random_equal_newseeds_b4_p1_20260430`
  - 总胜负：v3 `75`，baseline `53`
  - 总血量差：v3 `+391`，平均每局 `+3.0547`
  - v3 先手 64 局：`35-29`，血量差 `-39`
  - v3 后手 64 局：`40-24`，血量差 `+430`
  - 平均回合数：`497.6641`，达到 512 回合的局数 `98/128`
- 座位侧效应记录：
  - 同 seed 正反手配对后，v3 as p1 的血量比 v3 as p0 平均高 `+7.3281`
  - 全 128 局按纯座位看，p1 侧血量差为 `+469`，平均 `+3.6641`
  - 当前可能原因包括：p1 决策前已接收并应用 p0 本回合操作，存在当前回合信息差；连续 seed `1001:1064` 的首轮随机抽样不完全镜像，p0 首只蚂蚁全为 `Worker + Conservative`，p1 首只蚂蚁为混合 profile
  - 由于 v3 理论上主要做防守评估，敌方非超武操作不应显著影响己方防守，后续应使用打散 seed，并通过 v4 vs v3、v3-v3、baseline-baseline 对照拆分协议侧效应和策略侧效应
- 2026-04-30 已复制当前 v3 为 `cpp_lure_v4`，作为后续参数调节、行为分析和策略优化分支；当前阶段性最优仍记录为 `cpp_lure_v3`

2026-04-29 历史最优 v3 测试：

- v3 vs baseline 座位平衡 128 局：
  - `eval_results/v3_vs_baseline_128_c1_action_start_p0`
  - `eval_results/v3_vs_baseline_128_c1_action_start_p1`
  - 总胜负：v3 `72`，baseline `56`
  - 总血量差：v3 `+338`
  - v3 先手 64 局：`37-27`，血量差 `+196`
  - v3 后手 64 局：`35-29`，血量差 `+142`
- v3-a vs v3 座位平衡 32 局：
  - `eval_results/v3a_vs_v3_32_p0`
  - `eval_results/v3a_vs_v3_32_p1`
  - 总胜负：v3-a `1`，v3 `31`
  - 总血量差：v3-a `-781`
- Saiblo 性能探针：
  - 版本：`cpp_lure_v3n`
  - 口径：每回合只计算 active lure 与 lightning 两类 root plan，永远不输出操作
  - 原生 Saiblo 包：`eval_results/ai_cpp_lure_v3n_cppzip.zip`
  - Saiblo entity/code：`v3n-perf-cppzip` / `cd02749306d642e3a409f2dd50d5d32f`
  - 本机 16 组自我对战：`317.978ms / player-round`
  - Saiblo 16 组自我对战：`515.530ms / player-round`
  - Saiblo/本机比例：`1.621x`
  - Saiblo 页面用时图来自 match detail 的 `message.record[].time`，平均 `512.608ms / call`；stderr 计时平均 `515.530ms / call`，总量差约 `0.57%`
  - 详细打包方式与统计见 `Game1/antgame_ai_cpp/cpp_lure_v3n/README.md`

结论：当前阶段性最优解为 `cpp_lure_v3`。v3-a 的过早 2 级基地蚂蚁策略明显牺牲防守经济，只保留为抗性测试变体；后续优化从 `cpp_lure_v4` 开始。

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

同日 v3 vs baseline 进攻性回避测试来自 action-level UCB / reactive 击杀检测重构前的历史参数，仅作为回归参考。结果目录沿用当时的历史命名：

- 目录：
  - `Game1/antgame_ai_cpp/tmp_v3_vs_v2_32_p0`
  - `Game1/antgame_ai_cpp/tmp_v3_vs_v2_32_p1`
- 座位平衡 32 局完整官方对局
- v3 `16` 胜，baseline `16` 胜
- 平均终局血量：v3 `19.53125`，baseline `19.1875`
- 平均终局金币：v3 `327.40625`，baseline `321.5`
- v3 实际释放 `Emergency Evasion` 共 `1` 次
- 触发样本：`tmp_v3_vs_v2_32_p0/matches/seed_0015/replay.json` 第 `312` 回合，位置 `(4,10)`，覆盖 `5` 工蚁、`0` 战斗蚁，best action 后金币 `490`，敌方闪电 CD `19`
- 主要未触发原因：敌方闪电 CD 不足、敌方闪电仍在生效、金币不足、无 C1 Sniper、工蚁覆盖不足

结论：v3 后处理逻辑能正确进入 replay，未发现非法操作或误触发；当前触发率极低，强度上暂未优于 v2。
