# Game1 Lure Strategy

这份文档记录当前 Game1 的高层策略方向，以及当前 baseline / v2 / v3 已经落实到代码里的部分。当前本地最优解是 `cpp_lure_v3`，`cpp_heavy_baseline` 只保留为冻结对照。

参考 replay：

- `Game1/good.json`

## 1. 策略目标

当前 Game1 的核心不是“尽量把普通蚂蚁全防住”，而是：

- 先建立并维护 `C1` 主锚点
- 把主要精力放在战斗蚂蚁控制上
- 用外圈廉价塔反复引诱战斗蚂蚁偏离基地
- 在战斗蚂蚁即将白拆 lure 塔前主动卖塔回收
- 在合适时机用 `Lightning Storm` 清理积累的战斗蚂蚁

也就是说，lure 塔首先是路线控制工具，不是输出塔。

## 2. 来自 `good.json` 的核心结论

`good.json` 对当前策略方向的启发是：

- `C1` 可以作为长期主锚点
- 外圈少量固定槽位可以反复承担 lure 作用
- “建 lure -> 引走战斗蚁 -> 卖 lure” 的净损耗通常很小
- 真正重要的是把战斗蚁控制在离基地更远的位置
- 普通蚂蚁前期允许漏，不应为此过度操作

因此当前更合理的大方向是：

- 少操作
- 重战斗蚁控制
- 重卖塔回收
- 闪电作为收束工具而不是常规输出工具

## 3. 当前代码已实现的部分

当前 baseline / v2 已经落实了以下几点：

- `base` 与 `lure` 分离建模
- lure 结构默认为“最多一个外部 lure”
- 若 lure 被战斗蚁贴近，会优先执行强制卖塔
- 当前 rollout 中对所有己方塔都保留“战斗蚁贴身则强制回收”的 reactive 逻辑
- 若需要同回合 `sell + build`，会保证“先拆后建”
- 若同回合需要拆多座塔，会优先拆当前血量更高的塔
- 闪电作为独立候选搜索
- 闪电候选当前只包含单次 `Lightning Storm`，不与 `base/lure` 或降级/拆塔组合
- 闪电中心使用棋盘中心半径 5 的 91 个合法中心生成候选
- future rollout 不再完整生成主动 `base × lure`，只保留贴身回收这类应急 reactive 动作

2026-04-27 已将当前 v2 完全覆盖到 `cpp_heavy_baseline`，因此 baseline 与 v2 当前是同一冻结点。清理后 `cpp_lure_v2` 源码目录和打包目标已删除；后续试验版本不直接改 baseline。

v3 已作为独立探索版本新开：

- 入口：`Game1/antgame_ai_cpp/cpp_lure_v3/`
- 策略：`Game1/antgame_ai_cpp/cpp_lure_v3/include/antgame_ai/lure_strategy_v3.hpp`
- 参数：`Game1/antgame_ai_cpp/cpp_lure_v3/include/antgame_ai/lure_strategy_v3_params.hpp`
- 实现拆分：`session` / `core_format` / `core_ops` / `core_values` / `base_rules` / `base_swap` / `base_plans` / `lure_plans` / `lightning_plans` / `root_plans` / `reactive_targets` / `reactive` / `threat` / `rollout_sampling` / `terminal_eval` / `rollout_score` / `evaluation` / `offense` / `decision`

v3 当前已独立于 baseline/v2 继续迭代：普通 root action 与闪电 root action 使用两套独立 UCB 分批 rollout；模拟中的贴塔回收会先做下一回合击杀检测；best action 算完后尝试追加进攻性超武后处理。终点评估中己方等效金币按阶梯权重计分：等效金币 `400` 以内按 `money_weight=10`，超过 `400` 的部分按 `money_weight_above_threshold=6`；该衰减只影响己方金币和己方塔可回收价值，不影响对敌方塔伤害使用的 `lightning_tower_value_ratio`。

`Emergency Evasion` 触发条件：

- 敌方 `Lightning Storm` 当前未生效
- 敌方 `Lightning Storm` CD 至少 `5`
- 模拟执行 best action 后，我方金币仍 `> 30`
- 模拟执行 best action 后，C1 仍是 `Sniper`
- 存在一个 `Emergency Evasion` 中心覆盖至少 `4` 只己方 `Worker`

选点只统计己方工蚁，不把战斗蚁计入覆盖数；平局优先更靠近敌方基地的位置。

`EMP Blaster` 触发条件：

- 敌方 `Lightning Storm` 当前未生效
- 敌方 `Lightning Storm` CD 至少 `5`
- 模拟执行 best action 后，我方金币仍 `> 30`，且实际金币足够支付 EMP
- best action 后存在己方战斗蚁距敌方任意顶级塔 `<= 2`

EMP 中心固定为该敌方顶级塔坐标。若多个塔满足，按距离、塔价值、到敌方基地距离和塔 ID 稳定选一个。官方会让 EMP active effect 每回合随机漂移，因此 replay 中 `activeEffects` 的坐标不一定等于释放时的 `op` 坐标。

2026-04-30 当前 v3 作为阶段性最优解冻结。最新 v3 vs baseline 座位平衡 128 局使用全新 seed `1001:1064`，分 4 批完成，结果为 v3 `75-53-0`，总血量差 `+391`，平均 `+3.0547`。分座位看，v3 先手 `35-29`、血量差 `-39`；v3 后手 `40-24`、血量差 `+430`。结果目录位于仓库根目录 `eval_results/v3_vs_baseline_128_random_equal_newseeds_b{1..4}_{p0,p1}_20260430/`。

该 128 局显示出明显 p1 侧效应：同一 seed 正反手互换后，v3 作为 p1 的血量比作为 p0 平均高 `+7.3281`。当前记录的可能来源包括：本地协议中 p1 决策前已接收并应用 p0 本回合操作，存在当前回合信息差；连续 seed `1001:1064` 的随机数也导致初始蚂蚁 profile 非完全镜像，p0 首只蚂蚁全为 `Worker + Conservative`，p1 首只蚂蚁为混合分布。v3 本身主要评估防守状态，理论上对敌方非超武操作不应高度敏感，因此后续评测应优先使用打散 seed，并用 v4 vs v3 / baseline-baseline / v3-v3 对照进一步拆分协议侧效应和策略侧效应。

2026-04-30 已复制 `cpp_lure_v3` 为 `cpp_lure_v4`。v4 初始逻辑、参数和评测口径与当前 v3 一致，后续关键参数调节、行为分析和策略优化优先在 v4 上进行，目标是在压过 v3 的同时维持或提高对 baseline 的胜率与总血量差。

2026-04-29 历史 v3 vs baseline 座位平衡 128 局结果为 v3 `72` 胜、baseline `56` 胜，总血量差 `+338`。分座位看，v3 先手 `37-27`、血量差 `+196`；v3 后手 `35-29`、血量差 `+142`。结果目录位于仓库根目录 `eval_results/v3_vs_baseline_128_c1_action_start_p0/` 与 `eval_results/v3_vs_baseline_128_c1_action_start_p1/`。

2026-04-29 增加 `cpp_lure_v3n` 性能探针，只计算 active lure 与 lightning 两类 root plan，永远不输出操作。该探针以原生 `cpp_zip` 上传 Saiblo，entity `v3n-perf-cppzip`，code id `cd02749306d642e3a409f2dd50d5d32f`。16 组自我对战中，本机平均 `317.978ms / player-round`，Saiblo stderr 平均 `515.530ms / player-round`，Saiblo/本机比例约 `1.621x`。Saiblo 页面用时统计图来自 match detail 的 `message.record[].time`，该图表平均 `512.608ms / call`，与 stderr 内部计时平均 `515.530ms / call` 的总量差约 `0.57%`，口径一致。详情见 `Game1/antgame_ai_cpp/cpp_lure_v3n/README.md`。

2026-04-29 另建 `cpp_lure_v3a` 作为激进抗性测试变体：其余操作沿用 v3，但己方当前金币 `>=200` 且基地蚂蚁等级 `<2` 时，优先尝试升级基地生成蚂蚁到 2 级。v3-a 用于测试当前 v3 对 25 血蚂蚁的抗性，不作为最优解。32 局 v3-a vs v3 中，v3-a `1-31`，总血量差 `-781`。

2026-04-28 的首批 v3(P0) vs baseline(P1) 32 局结果为 v3 `12` 胜、baseline `20` 胜。EMP 释放 `3` 次，回避释放 `9` 次；未发现非法操作或坐标反向。该轮来自更早参数，仅作为历史回归参考。

2026-04-27 的 32 局 v3 vs baseline 座位平衡测试来自 action-level UCB / reactive 击杀检测重构前的历史参数，当前仅作为回归参考。该轮 v3 与 baseline 总胜负为 `16:16`。v3 只实际释放了 `1` 次紧急回避：`seed_0015` 第 `312` 回合，位置 `(4,10)`，覆盖 `5` 只工蚁、`0` 只战斗蚁。

## 4. 当前代码刻意没有实现的部分

当前 baseline / v2 仍然没有把 lure 策略做到最终形态。

暂未实现：

- 更复杂的同回合 op-list 模板
- `sell lure -> lightning -> build lure` 这种显式三段链
- `downgrade/sell -> lightning` 这种闪电前置回收链
- 主动 `Deflector`，后续再探索
- 主动 `EMP` 与 `Emergency Evasion` 已在 v3 中作为后处理试验项实现，但还未并入 baseline
- 更强的 lure 路径级控制
- 基于位置表的 lure 槽位偏好学习

另外，当前 lure 建塔位置已经不再做额外启发式打分：

- 不按离战斗蚁近远加分
- 不按离基地近远加分
- 不做前几名裁剪

这样做的目的，是让 lure 位置完全由 rollout 终点评估来决定。

## 5. 当前 `C1` 路线

当前 `C1` 路线仍是强结构化的：

- `C1` 为空时，考虑 `build C1` 与 `build C1 -> Heavy`
- `C1 Basic` 时：
  - 可升 `Heavy`
  - 钱较多时允许转 `Quick`
- `C1 Quick` 时允许转 `Sniper`
- `C1 Heavy` 在过渡期可通过 `downgrade -> Quick` 切线
- `C1 Sniper` 成型后，其他 base 槽位的二级塔候选放开到 `Heavy / Quick / Mortar`
- 当前还支持结构化 followup：
  - `build slot -> upgrade allowed level-2 tower`
  - `Basic -> Quick -> Sniper`
  - `Heavy(C1) -> downgrade -> Quick`
  - `downgrade/sell source to bottom -> build another base slot`
  - `downgrade/sell source to bottom -> build another base slot -> followup upgrade allowed level-2 tower`

这里仍保留一个显式金币阈值，用来控制 `Heavy` 与 `Quick / Sniper` 路线切换。v3 的阈值输入不是当前持有金币，
而是本回合行动前己方等效总金币：`当前金币 + 按最优顺序降级并卖完己方塔后的总回收价值`；达到阈值即进入转型阶段。

## 6. 当前 lure 结构

当前 lure 的动作模板只有三类：

- `hold`
- `sell`
- `sell + build`

以及在“没有 lure”时：

- `build`

这套结构的含义是：

- lure 是消耗品
- lure 不追求长期留场
- 只要预期价值不足，就可以直接卖

## 7. 当前闪电角色

当前闪电的定位是：

- 独立候选
- 偏战斗蚁应急
- 兼顾敌方塔伤害
- 不与 `base/lure` 相乘
- 不带前置 `downgrade / sell`
- baseline/v2 中每个合法闪电中心是一个 UCB arm
- v3 中闪电与 `recycle + lightning` 候选进入独立 lightning UCB 组，不与普通 action 抢普通 UCB 预算
- 默认合法中心为距棋盘中心 `(9,9)` 不超过 5 的 91 个格子

当前闪电启发主要看：

- rollout 后相对无闪电对照组减少的战斗蚁 threat
- 破盾收益
- 敌方超武窗口
- 对敌方塔造成的等效价值伤害

不再额外奖励普通蚂蚁数量。

## 8. 当前策略约束

当前 baseline / v2 还有几个明确约束：

- 当前只搜索单回合根动作，不再做旧版“两回合计划”
- 例外：base 主线保留少量显式 followup，用于表达建后升级、`Quick -> Sniper` 与 `Heavy(C1) -> Quick` 转线
- root 组合使用严格合法性判断
  - 组合里有一步非法，整组直接丢弃
- rollout 后续回合仅使用贴身强制回收，不再主动贪心生成完整 `base × lure`
- 所有直接影响评分的参数应统一暴露在 `lure_strategy_params.hpp`

当前根节点候选集合实际是：

- `hold`
- 单独 `base`
- 单独 `lure`
- `recycle-only base + lure`
- 单独 `lightning`

它不是完整的 `base × lure × lightning`。

## 9. 后续优化方向

当前值得继续推进的，不是再加更多零散 heuristic，而是：

- 继续强化战斗蚁控制
- 继续降低无意义操作
- 提高对 lure 卖塔时机的判断质量
- 提高闪电与 lure 联动质量
- 再决定是否逐步把主动超武和 `Medic` 纳入搜索

当前判断一个改动是否有价值，优先看：

- replay
- `ai*.stderr.log` 中的候选分解
- `sdk_lure_inspector` / simviz 的单回合候选与 sample trace
- `sdk_defense_parity` 的轻量模拟与 native 多 rollout 对拍
- 256 回合 self-play 的 HP / 经济 / 操作频率 / 时延统计
