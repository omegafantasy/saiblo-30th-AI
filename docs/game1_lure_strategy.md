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

截至 2026-05-02，v4 仍是实验分支，尚未替代 v3。当前 v4 参数头的关键状态为：普通 rollout `4/8`、`mid_eval_weight=0`，普通 action 使用 `action_target_time_ms=3000` 的实时测速预算和 `action_time_budget_ms=4000` 的硬停止预算；闪电 UCB 为 `600` 总样本、batch `2`；`followup_plan_penalty=20`；`future_threat_eval_enabled=false`；`hold_followup_enabled=false`。

v4 当前记录的优化假设：

- 不对普通建塔、降级、升级、换 lure 乱加通用惩罚，因为这些动作很多时候正是搜索出的有效解。
- 已验证窄范围的 `followup_plan_penalty`：只对依赖后续回合 followup 才能成立的 root plan 扣分，用来降低 rollout 中多回合计划断层带来的乐观偏差。`50` 的结果不如 v3，不作为保留结论；当前参数头的 `20` 是较轻惩罚试验状态，尚无干净大样本结论。
- v4 已实现但当前关闭 rollout 后的轻量确定性 future resolver：历史测试为 rollout `6/10` 回合，terminal eval 之后追加 `future_threat_horizon=4`，当时总前瞻仍为 `14` 回合。future 阶段不允许未来新操作和 followup，不生成新敌蚂蚁，不把未来 income / kill reward 纳入经济估值；塔攻击、当前超武效果衰减、蚂蚁死亡与进基地扣血继续结算。蚂蚁移动按真实 `move_options_for` 分布，过滤会攻击塔的选项后选最高概率非攻击选项；无非攻击选项则原地不动。完整 512 回合测试显示退步，当前 `future_threat_eval_enabled=false`。由于当前 v4 普通 rollout 已为 `4/8`，未来若重新打开 `future_threat_horizon=4`，总前瞻口径会是 `12` 回合。
- v4 已实现但当前关闭 `hold + 后续回合操作` root plan：当前只允许延后一回合的单个 lure 类计划，生成 `hold_then_lure_*` 候选并继承 `hold_bonus`，不再为 base 建/升/降/换塔生成 hold-followup，避免候选空间过大抢占 rollout 资源。64 局完整测试显示旧版宽口径退步，当前 `hold_followup_enabled=false`。
- v4 的 `base+lure` 组合当前要求先完整回收一个 base 类塔再执行 lure：Basic base 塔可本回合卖塔+lure；高级 base 塔本回合只单降一级，后续 followup 继续降到 Basic，并在卖掉 base 塔的同一 future turn 执行 lure。旧版允许“高级 base 塔单降一级 + 同回合 lure”的组合已移除。
- `sdk_lure_inspector` / simviz 当前跟随 v4，并支持页面上的 `Future Threat` 与 `Hold Followup` 两个开关通过 `strategy_overrides` 临时覆盖上述两个布尔参数；正式 v4 参数头默认仍保持关闭。
- 当前 lure 的含义仍是把战斗蚁引开、优先处理其他蚂蚁；后续另一个方向是显式评估“主动放战斗蚁进基地”的 macro，让战斗蚁以 1 点血量代价退出场面，减少长期干扰。该方向应在 future resolver 之后再做，并限制剩余 followup 模板。

`followup_plan_penalty=50` 的首轮 v4 自战 32 局结果位于 `eval_results/v4_followup_penalty50_selfplay_32_20260430/`。同 seed 对照上一轮 v3 自战，v4 p0 `18` 胜、p1 `14` 胜，p1-p0 总血量差 `-28`；v3 对照为 p0 `15` 胜、p1 `17` 胜，p1-p0 总血量差 `+50`。该改动显著减少操作量：p0 非 hold 操作比 v3 少 `598`，p1 少 `428`，但自战不能直接说明强度提升。

随后进行 v4 vs v3 座位平衡 32 局，结果位于 `eval_results/v4_followup_penalty50_vs_v3_32_p0_20260430/` 与 `eval_results/v4_followup_penalty50_vs_v3_32_p1_20260430/`。v4 总计 `14-18`，总血量差 `-114`，平均血量差 `-3.5625`；其中 v4 先手 `6-10`、血量差 `-103`，v4 后手 `8-8`、血量差 `-11`。v4 非 hold 操作总数 `4836`，v3 为 `5210`，v4 少 `374` 次；其中 build 少 `74`、downgrade 少 `179`、upgrade 少 `109`。当前结论是：`followup_plan_penalty=50` 确实减少了无谓操作倾向，但强度不如 v3，暂不应作为 v4 保留优化。

2026-04-30 实现 future threat resolver 后，使用支持 `target0/target1` 的 partial wrapper 真正截断第 256 回合，进行 v4 vs v3 座位平衡 32 局。结果位于 `eval_results/v4_future_threat_vs_v3_32_p0_partial256_20260430/` 与 `eval_results/v4_future_threat_vs_v3_32_p1_partial256_20260430/`，全部 `cutoff=True`、`rounds=256`。按第 256 回合血量领先统计，v4 `15-16-1`，总血量差 `-53`，平均血量差 `-1.65625`；其中 v4 先手 `7-9-0`、血量差 `-31`，v4 后手 `8-7-1`、血量差 `-22`。v4 金币差总计 `-837`，平均 `-26.15625`；v4 非 hold 操作 `2468`，v3 为 `2708`，v4 少 `240` 次。

随后将 rollout 改回 `6/10`，future horizon 改为 `4`，进行完整 512 回合 v4 vs v3 座位平衡 32 局。结果位于 `eval_results/v4_future_threat_6_10_f4_vs_v3_32_p0_full512_20260430/` 与 `eval_results/v4_future_threat_6_10_f4_vs_v3_32_p1_full512_20260430/`。v4 总计 `13-19`，总血量差 `-196`，平均血量差 `-6.125`；其中 v4 先手 `8-8`、血量差 `-70`，v4 后手 `5-11`、血量差 `-126`。该尝试没有明显收益且完整局退步，因此当前关闭。

2026-04-30 补充 `hold + 后续回合操作` 尝试后，使用全新 seed `703001:703032` 做完整 512 回合 v4 vs v3 座位平衡 64 局。结果位于 `eval_results/v4_hold_followup_vs_v3_64_p0_full512_20260430/` 与 `eval_results/v4_hold_followup_vs_v3_64_p1_full512_20260430/`。v4 总计 `25-39`，总血量差 `-230`，平均血量差 `-3.59375`；其中 v4 先手 `13-19`、血量差 `-44`，v4 后手 `12-20`、血量差 `-186`。v4 金币差总计 `-3282`，平均 `-51.28125`；v4 非 hold 操作 `9733`，v3 为 `10348`，v4 少 `615` 次。操作量下降没有转化为强度收益，因此当前关闭。

2026-05-01 的当前 v4 vs v3 128 局完整评测使用 seed `711001:711064` 分 4 批完成，原始汇总为 v4 `66-62`、总血量差 `+219`、平均 `+1.7109`；v4 平均决策耗时 `2959.19ms`、p95 `3752.04ms`、最大 `4054.85ms`。该批包含 3 局 IA：2 次 `TowerDestroy: EMPBlaster is active`、1 次 `TowerUpgrade: EMPBlaster is active`，因此结果被 SDK 状态镜像 bug 污染，不能作为强度结论。结果目录为 `eval_results/v4_current_vs_v3_128_b{1..4}_{p0,p1}_full512_20260501_1636/`，聚合文件为 `eval_results/v4_current_vs_v3_128_full512_20260501_1636_aggregate.json`。

2026-05-02 已修复 SDK 对同回合操作列表的顺序应用语义。官方流程中 p0 操作会在 p1 读取前被裁剪并应用，p1 理应看到 p0 实际已释放的 EMP；此前 `PublicState::apply_operation_list()` 在修改状态后仍把已应用操作作为 `pending` 传给合法性判断，错误拒绝了“先降/卖塔筹钱，再建塔，再 EMP”的 salvage-funded EMP。典型污染样本为 seed `711058`，p0 降/卖 71、73，建 `(7,17)`，再对 `(14,9)` 释放 EMP。修复后 SDK 使用 `can_apply_operation_sequential()` 和同回合 tower/base 使用记录来验证操作列表，v2/v3/v4 的本地合法化路径也同步改为顺序检查；新增回归测试覆盖该场景。修复后尚未重新跑干净的 v4 vs v3 128 局。

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
