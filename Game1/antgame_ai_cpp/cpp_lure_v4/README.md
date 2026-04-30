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

## 初始状态说明

v4 初始状态完全继承当前 v3：

- rollout 使用纯随机等权移动采样，不再使用 forced move 概率加权。
- 闪电组先独立完整计算，再进入普通 action 搜索。
- 普通 action 使用 3s 卡时和 `min(action_target_total_rollouts, action_target_rollouts_per_action * action_count)` 的总预算截断。
- `c1_quick_transition_coin_threshold` 按行动前己方等效总金币判断。
- 己方经济估值使用 `400` 阈值阶梯权重：阈值内 `money_weight=10`，阈值以上 `money_weight_above_threshold=6`。
- 进攻性 `EMP Blaster` / `Emergency Evasion` 仍作为 best action 之后的后处理。

2026-04-30 的 v3 vs baseline 128 局显示，v3 相对 baseline 为正收益，但存在明显 p1 侧效应：v3 as p0 为 `35-29`、血量差 `-39`；v3 as p1 为 `40-24`、血量差 `+430`。当前判断可能来自本地协议当前回合信息差和连续 seed 的随机相关性；后续 v4 调参应优先使用打散 seed，并同时观察 v4 vs v3 与 v4 vs baseline。
