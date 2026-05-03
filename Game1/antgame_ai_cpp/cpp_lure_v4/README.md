# cpp_lure_v4

`cpp_lure_v4` 是 2026-04-30 从阶段性最优 `cpp_lure_v3` 复制出的新实验分支。复制时 v4 与 v3 的策略逻辑、参数和评测口径保持一致；后续关键参数调节、行为分析和策略优化优先在 v4 上进行，目标是在压过 v3 的同时保持或提高对 `cpp_heavy_baseline` 的胜率与总血量差。

当前基准父版本：

- 源版本：`Game1/antgame_ai_cpp/cpp_lure_v3/`
- 复制时间：2026-04-30
- v3 阶段性最优评测：128 局 vs baseline，v3 `75-53-0`，总血量差 `+391`
- 结果目录：`eval_results/v3_vs_baseline_128_random_equal_newseeds_b{1..4}_{p0,p1}_20260430/`

## 入口

- `ai_cpp_lure_v4.cpp`
- 聚合策略入口：`include/antgame_ai/lure_strategy_v4.hpp`
- 参数入口：`include/antgame_ai/lure_strategy_v4_params.hpp`
- 参数类型与访问函数：`V4LureStrategyTuning` / `v4_lure_config()`

v4 保留 v3 的模块拆分：`session` / `core_format` / `core_ops` / `core_values` / `base_rules` / `base_swap` / `base_plans` / `lure_plans` / `lightning_plans` / `root_plans` / `reactive_targets` / `reactive` / `threat` / `rollout_sampling` / `terminal_eval` / `rollout_score` / `evaluation` / `offense` / `decision`。

## Build / Package

```bash
cd /root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp/cpp_lure_v4
make

cd /root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp
bash package_ai.sh cpp_lure_v4
```

## Eval

座位平衡评测应始终同时跑两个方向，并把结果写入仓库根目录 `eval_results/`：

```bash
cd /root/autodl-tmp/saiblo_iter
python3 Game1/antgame_ai_cpp/tools/eval_cpp_selfplay.py \
  --target0 cpp_lure_v4 \
  --target1 cpp_heavy_baseline \
  --seeds 1:16 \
  --jobs 16 \
  --output-dir eval_results/v4_vs_baseline_p0_16 \
  --force

python3 Game1/antgame_ai_cpp/tools/eval_cpp_selfplay.py \
  --target0 cpp_heavy_baseline \
  --target1 cpp_lure_v4 \
  --seeds 1:16 \
  --jobs 16 \
  --output-dir eval_results/v4_vs_baseline_p1_16 \
  --force
```

与 v3 直接比较时同样需要正反手各跑一遍，避免把座位侧效应误判为版本强弱。

## 当前状态说明

v4 初始状态完全继承 2026-04-30 的阶段性最优 v3；截至 2026-05-03，v4 仍是实验分支，尚未证明强于 v3。当前本地最优解仍按 v3 记录。

当前 v4 参数以 `include/antgame_ai/lure_strategy_v4_params.hpp` 为准，关键口径如下：

- rollout 使用纯随机等权移动采样，不再使用 forced move 概率加权。
- 闪电组先独立完整计算，再进入普通 action 搜索。
- 普通 action 使用实时测速卡时：先对每个 normal action 做 `action_probe_min_samples=5` 次可复用 probe，这些样本计入最终 UCB 统计；再按 `action_target_time_ms=3000` 估算本回合等效 base rollout 总数。target 总数为 base 的 `action_target_total_multiplier=1.25`，并继续受 `action_target_rollouts_per_action=125 * action_count` 截断。`action_time_budget_ms=4000` 是后续保底/补样阶段的硬预算停止条件。
- 普通 action UCB 为 `action_ucb_exploration=600`，单批最多 `100`。
- static-risk cache 默认开启：`rollout_static_risk_cache_enabled=true`，容量参数为 `1024`。
- 实验性 reverse-path cache 默认关闭：`rollout_reverse_path_cache_enabled=false`，容量参数为 `2048`。
- 单次决策 move-cache memo 默认开启：`rollout_move_cache_memo_enabled=true`，容量参数为 `2048`。
- 当前普通 rollout 为 `mid_eval_horizon=4`、`long_eval_horizon=8`，且 `mid_eval_weight=0`，即实际只采用第 8 回合终点评估。闪电 horizon 为 `10`，闪电 UCB 总预算为 `600`、batch 为 `2`、exploration 为 `300`。
- v4 rollout 在 `round_index >= 512` 时按官方最大回合口径截断，不再让 8/10 回合 horizon 跨过最大回合继续模拟。
- `c1_quick_transition_coin_threshold` 按行动前己方等效总金币判断。
- 己方经济估值使用 `400` 阈值阶梯权重：阈值内 `money_weight=10`，阈值以上 `money_weight_above_threshold=6`。
- `followup_plan_penalty` 当前为 `0.0`。历史上测试过 `50` 与 `20`，结果不如 v3 或结论不干净；当前归零后需要重新评测强度。
- `future_threat_eval_enabled=false`，`hold_followup_enabled=false`。对应代码和 SimViz 开关仍保留，便于单回合审计和后续重开试验。
- 进攻性 `EMP Blaster` / `Emergency Evasion` 仍作为 best action 之后的后处理。

2026-04-30 的 v3 vs baseline 128 局显示，v3 相对 baseline 为正收益，但存在明显 p1 侧效应：v3 as p0 为 `35-29`、血量差 `-39`；v3 as p1 为 `40-24`、血量差 `+430`。当前判断可能来自本地协议当前回合信息差和连续 seed 的随机相关性；后续 v4 调参应优先使用打散 seed，并同时观察 v4 vs v3 与 v4 vs baseline。

2026-05-01 的当前 v4 vs v3 128 局完整评测使用 seed `711001:711064` 分 4 批完成，原始汇总为 v4 `66-62`、总血量差 `+219`、平均 `+1.7109`；v4 平均决策耗时 `2959.19ms`、p95 `3752.04ms`、最大 `4054.85ms`。但该批包含 3 局 IA：2 次 `TowerDestroy: EMPBlaster is active`、1 次 `TowerUpgrade: EMPBlaster is active`，结果目录为 `eval_results/v4_current_vs_v3_128_b{1..4}_{p0,p1}_full512_20260501_1636/`，聚合文件为 `eval_results/v4_current_vs_v3_128_full512_20260501_1636_aggregate.json`。该批应视为被 SDK 状态镜像 bug 污染，不能作为强度结论；修复后尚未重新跑 128 局。

2026-05-03 在 rollout 对齐修复和 `followup_plan_penalty=0.0` 后，用新 seed 重新跑了两组座位平衡 32 局，均为完整 512 回合上限、`--debug-mode none`、每座位批次 `--jobs 16` 并行，无 IA / failure：

- v4 vs v3：seed `734001:734032`，v4 `11-21-0`，总血量差 `+32`、平均 `+1.000`，总金币差 `+1462`、平均 `+45.688`，平均回合 `509.531`。v4 先手 `5-11`，血量差 `-20`，金币差 `+1653`，墙钟 `2552.554s`；v4 后手 `6-10`，血量差 `+52`，金币差 `-191`，墙钟 `2669.005s`。两批并行视角墙钟约 `2669.005s`，批次墙钟和 `5221.559s`。报告：`eval_results/v4_terminalfix_vs_v3_32_20260503_report.md`。
- v4 vs baseline：seed `735001:735032`，v4 `21-11-0`，总血量差 `+287`、平均 `+8.969`，总金币差 `+6062`、平均 `+189.438`，平均回合 `502.594`。v4 先手 `11-5`，血量差 `+168`，金币差 `+3787`，墙钟 `1917.063s`；v4 后手 `10-6`，血量差 `+119`，金币差 `+2275`，墙钟 `1997.371s`。两批并行视角墙钟约 `1997.371s`，批次墙钟和 `3914.434s`。报告：`eval_results/v4_terminalfix_vs_baseline_32_20260503_report.md`。

由于本轮使用 `--debug-mode none` 以减少测量扰动，markdown 中逐决策 `avg_s / p95_s / max_s` 为 `0`；效率对比应使用上述 bash `time` 墙钟日志，原始文件在 `eval_results/timing_logs/`。

同日又用基础 debug 口径重新跑 v4 vs v3 128 局：seed `736001:736128`，座位平衡，四批各 `32` 局，每批 `--jobs 32`，`--debug-mode summary`，无 IA / failure。总结果 v4 `65-63-0`，总血量差 `+38`、平均 `+0.296875`，总金币差 `+11077`、平均 `+86.5390625`，平均回合 `504.671875`。分批结果：v4 先手 `16-16`、血量差 `+20`、墙钟 `2665.628s`；v4 先手 `18-14`、血量差 `+39`、墙钟 `2568.543s`；v4 后手 `15-17`、血量差 `-25`、墙钟 `2644.592s`；v4 后手 `16-16`、血量差 `+4`、墙钟 `2647.011s`。基础 debug 下 v4 决策耗时平均 `2.365496s`，四批 mean p95 `3.522564s`，最大 `4.043358s`；v4 平均候选数 `154.457`，mean p95 候选数 `230`。批次墙钟和 `10525.774s`，原始聚合：`eval_results/v4_debugsummary_vs_v3_128_20260503_aggregate.json`，markdown 报告：`eval_results/v4_debugsummary_vs_v3_128_20260503_report.md`。

## 当前 v4 优化假设

2026-04-30 的回放分析显示，v4 的主要潜在提升点不是扩大普通建拆升降的手工奖惩，而是降低 rollout 对后续回合 followup 的过度乐观，并改善终局 threat 估值。

已验证但不保留的窄改动：

- `followup_plan_penalty = 50.0`：只对带有 future-turn followup 的 root plan 扣分，不惩罚普通 build / downgrade / upgrade / lure relocate 本身。该取值结果不如 v3，不作为保留结论。

初步自战结果：

- 目录：`eval_results/v4_followup_penalty50_selfplay_32_20260430/`
- 同 seed 对照上一轮 v3 自战，v4 p0 `18` 胜、p1 `14` 胜，p1-p0 总血量差 `-28`；v3 对照为 p0 `15` 胜、p1 `17` 胜，p1-p0 总血量差 `+50`。
- 操作量明显下降：p0 非 hold 操作比 v3 少 `598`，p1 少 `428`。build / downgrade / upgrade 都明显减少。

followup penalty 的 v4 vs v3 座位平衡 32 局结果：

- 目录：`eval_results/v4_followup_penalty50_vs_v3_32_p0_20260430/` 与 `eval_results/v4_followup_penalty50_vs_v3_32_p1_20260430/`
- v4 总计 `14-18`，总血量差 `-114`，平均血量差 `-3.5625`。
- 分座位看，v4 先手 `6-10`、血量差 `-103`；v4 后手 `8-8`、血量差 `-11`。
- v4 非 hold 操作总数 `4836`，v3 为 `5210`，v4 少 `374` 次；其中 build 少 `74`、downgrade 少 `179`、upgrade 少 `109`。
- 结论：`followup_plan_penalty=50` 确实降低了操作量，但当前强度不如 v3，暂不应作为 v4 的保留优化。

后续待验证方向：

- 评估“主动放战斗蚁进基地”的特殊 macro：在合适局面下卖光或卖到安全状态，让战斗蚁以 1 点基地血量代价退出场面，再执行受限 followup，例如 C1 重建链或单 lure。该方向应依赖 future resolver 后再试，避免旧 threat 估值误判。

## Future Threat Resolver

v4 曾试验 `6/10` 回合 rollout 加 `future_threat_horizon=4` 的确定性 future threat resolver，当时总前瞻仍为 `14` 回合。该 resolver 不允许未来新操作和 followup，不生成新敌蚂蚁，不把未来 income / kill reward 纳入经济估值；塔攻击、当前超武效果衰减、蚂蚁死亡与进基地扣血会继续结算。蚂蚁移动按真实 `move_options_for` 分布，过滤掉会攻击塔的选项后选最高概率非攻击选项；若无非攻击选项则原地不动。

该尝试当前已关闭：`future_threat_eval_enabled = false`。当前 v4 普通 rollout 已改为 `4/8`，若未来重新打开 `future_threat_horizon=4`，总前瞻口径将变为 `12` 回合，而不是历史测试时的 `14` 回合。

2026-04-30 的 32 局 v4 vs v3 partial 评测在第 256 回合主动截断，全部 `cutoff=True`、`rounds=256`：

- 目录：`eval_results/v4_future_threat_vs_v3_32_p0_partial256_20260430/` 与 `eval_results/v4_future_threat_vs_v3_32_p1_partial256_20260430/`
- 按第 256 回合血量领先统计，v4 `15-16-1`，总血量差 `-53`，平均血量差 `-1.65625`。
- 分座位看，v4 先手 `7-9-0`、血量差 `-31`；v4 后手 `8-7-1`、血量差 `-22`。
- v4 金币差总计 `-837`，平均 `-26.15625`。
- v4 非 hold 操作 `2468`，v3 为 `2708`，v4 少 `240` 次；其中 build 少 `129`、downgrade 少 `116`、lightning 少 `22`、upgrade 多 `22`、evasion 多 `5`。

随后将 rollout 改回 `6/10`，future horizon 改为 `4`，做完整 512 回合 v4 vs v3 座位平衡 32 局：

- 目录：`eval_results/v4_future_threat_6_10_f4_vs_v3_32_p0_full512_20260430/` 与 `eval_results/v4_future_threat_6_10_f4_vs_v3_32_p1_full512_20260430/`
- v4 总计 `13-19`，总血量差 `-196`，平均血量差 `-6.125`。
- 分座位看，v4 先手 `8-8`、血量差 `-70`；v4 后手 `5-11`、血量差 `-126`。
- v4 金币差总计 `-585`，非 hold 操作比 v3 多 `338` 次。
- 结论：future threat resolver 没有明显收益且完整局退步，当前不保留。

## Hold Followup

v4 还试验过 `hold + 后续回合操作` root plan：当前收窄为只允许延后一回合的单个 lure 类计划，生成 `hold_then_lure_*` 候选，并继承 `hold_bonus`。不再为 base 建/升/降/换塔计划生成 hold-followup，避免候选空间过大抢占 rollout 资源；该尝试不作用于闪电，也不合并复杂 base+lure 组合。

`base+lure` 组合也已收窄为“完整回收一个 base 类塔之后再执行 lure”：若 base 塔已经是 Basic，则本回合直接卖 base 塔并执行 lure；若 base 塔为高级塔，则本回合只先降一级，后续 followup 继续降到 Basic 并在卖掉 base 塔的同一 future turn 执行 lure。这样避免旧逻辑中“高级 base 塔单降一级 + 同回合 lure”的过宽组合。

该尝试当前已关闭：`hold_followup_enabled = false`。

SimViz 的 `sdk_lure_inspector` 当前跟随 v4，并在页面顶部提供 `Future Threat` / `Hold Followup` 两个调试开关。开关只通过 inspector 请求里的 `strategy_overrides` 临时覆盖运行时配置，便于单回合审计；不会修改 v4 参数头中的默认关闭状态。

2026-04-30 使用全新 seed `703001:703032` 做完整 512 回合 v4 vs v3 座位平衡 64 局：

- 目录：`eval_results/v4_hold_followup_vs_v3_64_p0_full512_20260430/` 与 `eval_results/v4_hold_followup_vs_v3_64_p1_full512_20260430/`
- v4 总计 `25-39`，总血量差 `-230`，平均血量差 `-3.59375`。
- 分座位看，v4 先手 `13-19`、血量差 `-44`；v4 后手 `12-20`、血量差 `-186`。
- v4 金币差总计 `-3282`，平均 `-51.28125`。
- v4 非 hold 操作 `9733`，v3 为 `10348`，v4 少 `615` 次；操作量下降没有转化为强度收益。

## 2026-05-02 SDK 状态镜像修复

官方 `Ant-Game` 中 p0 的操作会在 p1 读取前被裁剪并应用，因此 p1 理应看到 p0 同回合释放的 EMP。此前本地 SDK 的 `PublicState::apply_operation_list()` 在一边修改状态时，一边把已经应用过的操作继续作为 `pending` 传给 `can_apply_operation()`，导致“先降/卖塔筹钱，再建塔，再 EMP”的同回合操作在本地镜像中被错误拒绝。

典型污染样本为 seed `711058`：p0 同回合降/卖 71、73，建 `(7,17)`，再对 `(14,9)` 放 EMP；官方接受该操作序列，但旧 SDK 本地拒绝 EMP，导致 p1 后续认为顶级塔仍可被降/拆，从而输出会被官方 EMP 禁止的塔操作并 IA。

修复内容：

- `PublicState::apply_operation_list()` 改为顺序验证当前已变更状态，只额外记录同回合已经使用过的 tower id 与 base upgrade 状态。
- 新增 `can_apply_operation_sequential()` 与 `record_operation_turn_usage()`，避免把已经落地的操作再次作为 pending 参与金币和塔数计算。
- v2 / v3 / v4 的 `legalize_operations()` 与 downgrade penalty 计算同步使用顺序合法性检查。
- 移除了之前错误方向的“p0 等效金币可筹 EMP 时 p1 禁止塔操作”防守性补丁；正确语义是 p1 读取 p0 实际已接受操作，而不是预测 p0 可筹钱。
- 新增回归测试 `test_cpp_sdk_public_state_applies_salvage_funded_emp_before_p1_turn()`，覆盖 seed `711058` 这种 salvage-funded EMP 场景。

v4 runtime 另有两层运行兜底：自方操作先经 public mirror 过滤，再交给 native mirror；若 native mirror 仍拒绝其中某条操作，实际发送给 judger 的列表会退回到首个 native 非法操作之前的前缀，保持发送内容与 native 已应用状态一致。对手操作则先由 native mirror 应用；若 native mirror 拒绝但操作前 public fallback 能完整重放该对手操作，v4 会把 native simulator 重新同步到 public fallback，避免后手在前手操作被本地错拒后的状态上决策。

## 2026-05-03 rollout 对齐修复

后期回合 12 回合 rollout 的标准逻辑对齐检查统一采用“不考虑每 10 回合随机传送、标准逻辑也不做基地产兵”的口径。偏移排查中确认，主要误差来自终局存活统计和 base death 后的回合结算语义：

- `DefenseSimulator::manage_ants()` 调整为先处理 `Success` / `Fail`；若基地血量降到 `0`，立即终局并跳过后续 spawn / age / income / effects；只有继续游戏时才处理 `TooOld`。
- rollout 终点评估与统计不再把 `too_old()` 的蚂蚁、以及已经站在己方基地格但尚未被终局清理的蚂蚁算作仍活跃威胁。
- 新增 `NativeSimulator::advance_round_without_base_spawns_no_teleport()` 作为 validation 专用标准逻辑入口，避免标准侧混入周期随机传送或基地产兵。
- native tower id/index 同步、确定性移动 RNG 消耗、蚂蚁可走格 effect drift 等早先发现的差异已一并修正；v4 native mirror 发送兜底改为使用 public 已接受操作前缀，避免 native 拒绝后误截断。

最终验证目录：`eval_results/v4_rollout_alignment_late_h12_s5000_no_teleport_after_terminal_alive_20260503/summary.json`。16 个后期局面、每个局面 5000 次、horizon 12 的 `sim - standard` 聚合偏差为：`base_hp` 均值 `-0.003162`、最差 `+0.034400`；`coins` 均值 `-0.025838`、最差 `+0.280800`；`worker_count` 均值 `-0.003488`、最差 `-0.039000`；`ant_hp` 均值 `-0.002975`、最差 `-0.775800`；`total_threat` 均值 `-0.537846`、最差 `-7.587876`；`total_score` 均值 `+0.975096`、最差 `-11.285465`。在 5000 次随机抽样尺度下，该结果可视为当前模拟与客观模拟几乎无系统偏差。

## 2026-05-02 模拟性能分析检查点

本轮分析目标是提高 v4 大量 action / 大量 rollout 下的模拟吞吐，暂不考虑每 10 回合随机传送；`RandomSearchParams::ignore_periodic_random_move` 默认已经为 true。`sdk_lure_inspector` 的单回合 profiling 显示，普通 action UCB 的核心瓶颈集中在 `DefenseSimulator::simulate_round()` 内部的 `move_phase()`，其中 `move_cache_ns` 长期占据 `move_ns` 和总模拟时间的大头，很多样本达到 80% 以上。因此优先优化方向应是减少重复构建移动准备数据，而不是先微调终局估值权重。

已落地的低风险优化：

- 普通 action rollout 从已经应用 root plan 的 `DefenseSimulator` 状态开始，避免每个样本重复 clone 根状态并再次应用同一个 plan。
- 终点评估中复用 `terminal_evaluate_state()` 已经算出的塔全额回收价值，避免重复遍历塔。
- SDK 的风险字段失效从移动缓存失效中拆开，仅在超武效果实际漂移或过期时重新计算静态风险。
- `resolve_ant_step()` 去掉一次重复的 `tower_at()` 查询。
- `prepare_move_cache()` 的 traffic / occupied / adjacent 动态场合并为一次清零和一次蚂蚁遍历，减少每次移动准备的固定开销。
- `prepare_move_cache()` profiling 已拆分为 static / dynamic / weight / worker path / tower path / annotation；`sdk_lure_inspector` 的 `simulator_profile` 会输出这些字段。
- 单次决策共享 static-risk cache 默认开启，只缓存 walkable / neighbors / damage risk / control risk / effect pull 这些不依赖蚂蚁分布的静态场。seed `707010` round `101` 动态预算样本中，该缓存命中约 `38,896 / 40,834` 次，`move_cache_static_ns` 从约 `85ms` 降到约 `20ms`，总样本数约从 `12,875` 增至 `13,075`。
- `ReverseHeap` 去掉每次 Dijkstra 前对 `kMaxReverseHeapEntries` 大数组的无用零初始化。该改动不改变路径算法语义，但在 seed `707010` round `101` 固定预算样本中把总耗时从约 `560ms` 降到约 `341ms`；动态预算样本中约 `14,157` samples、`action_estimated_us_per_sample` 约 `256.9us`。
- `move_phase()` 内的反向路径搜索现在只算本次移动打分会读取的目标格：worker 包含当前格与合法非塔候选格，combat 包含合法非塔候选格。Dijkstra 在这些目标格全部 finalized 后提前停止；`move_phase()` 结束后会把 move cache 标脏，防止部分路径被外部完整 `move_options_for()` 查询复用。该优化只改变准备阶段算到哪里，不改变任一被读取格子的最短路结果。

单次决策 move-cache memo 当前默认开启：`rollout_move_cache_memo_enabled=true`，容量参数为 `rollout_move_cache_memo_entries=2048`。当前实现只缓存准备阶段的核心字段，命中后仍重新执行当轮 reservation / attack annotation，不缓存最终 `move_options_for()` 结果，也不缓存 `reservations` / `tower_claims`。memo key 使用 hash index 查找，缓存的 tower plans 改为紧凑存储，只保存实际有效 plan，避免每个 entry 携带 64 个完整 `ReversePathPlan` slot。move-phase 部分路径模式下，memo key 额外记录参与路径的蚂蚁 role(worker/combat) 与 `last_move`，使部分路径只在同一候选目标集合语义下命中；外部完整路径查询不带该 key 后缀。seed `707010` round `101` 固定预算样本中，部分路径 + memo 的代表性 run 可把 `move_cache_ns` 从此前约 `271ms` 降到约 `167ms`，`action_estimated_us_per_sample` 从约 `240us` 降到约 `158us`；动态预算样本中仍能达到约 `16,100` samples，`action_estimated_us_per_sample` 约 `208us`。同一 replay 的 round `80` / `140` 抽样中，2048 entries 相对 512 entries 对 samples 也更有利。

`sdk_lure_inspector` 新增 `alignment_check` 模式，用于抽样对比 replay 标准状态与 DefenseSimulator 投影状态，并把当前 best rollout 均值和 replay 未来 `long_eval_horizon` 回合的实际标准状态估值放在同一输出中。seed `707010` 的 round `80/101/140/180`、player `0`、horizon `8` 检查中，起点状态和未来标准状态投影到 DefenseSimulator 的 `base_hp / coins / tower_count / tower_hp / worker_count / combat_count / ant_hp / enemy level` 差异均为 `0`；预测均值和实际未来估值的差异主要来自当前 best action 与 replay 实际 action 不一致，不是状态镜像硬偏差。

实验性 reverse-path cache 也默认关闭：`rollout_reverse_path_cache_enabled=false`。它以 walkable / step_total / step_damage / sources 为 key 缓存单次 Dijkstra 的 `ReversePathPlan`，语义上精确；但 seed `707010` round `101` 固定预算中命中率偏低，hash 与 lookup 成本超过节省的 Dijkstra 时间。当前只保留为 inspector 调试开关。

当前 full move memo key 覆盖当前移动玩家、存活塔的 id / 位置 / 类型、存活蚂蚁的位置序列、是否需要 worker/combat 路径的全局 mask、超武效果的位置 / 类型 / 剩余回合。它不再逐个记录与准备字段无关的蚂蚁 HP / level / frozen / too_old 细节；这些只通过“是否实际需要某类路径”的 mask 影响准备字段。static-risk cache key 只覆盖当前移动玩家、存活塔的位置 / 类型、会影响静态场的己方 LightningStorm 与敌方 Deflector / EmergencyEvasion。塔 HP 和 cooldown 当前不参与准备字段，只在后续移动打分或攻击阶段使用，因此不放进 static-risk cache key；若未来 `prepare_move_cache()` 使用这些字段，必须同步更新 key。当前反向路径不依赖信息素，但最终移动打分会依赖信息素，因此信息素不应作为“准备核心缓存”命中后可跳过的最终决策输入。

分段 profile 当前显示，static-risk 已不是主要瓶颈；seed `707010` round `101` 中 `worker_path` 与 `tower_path` 仍合计占据绝大多数 `move_cache_ns`。下一轮主要方向应转向反向路径算法本身或精确 lazy combat tower path；当前连通分量裁剪在该样本中 `tower_path_skipped=0`，不作为默认优化。
