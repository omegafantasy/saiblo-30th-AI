# cpp_lure_v2

这是 Game1 当前 v2 C++ AI。2026-04-27 之后，`cpp_heavy_baseline` 已被当前 v2 完全覆盖，因此 v2 与 baseline 当前是同一策略冻结点。后续进攻性探索应新开 v3，不应直接改 v2 或 baseline。

## 入口

- `ai_cpp_lure_v2.cpp`
  - 比赛协议入口
  - 维护 `PublicState`
  - 维护 `NativeSimulator`
  - 调用 `antgame_sdk::decide_lure_strategy()`

## 依赖

- `../../antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v2.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v2_params.hpp`
  - v2 独立参数，类型/访问函数为 `V2LureStrategyTuning` / `v2_lure_config()`
- `../../antgame_cpp_sdk/include/antgame_sdk/random_search_baseline.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/position_slots.hpp`

默认兼容入口 `lure_strategy.hpp` / `lure_strategy_params.hpp` 也已同步为 v2 口径；冻结 baseline 使用独立的 `lure_strategy_baseline.hpp` / `lure_strategy_baseline_params.hpp`，但内容已与当前 v2 对齐。

## 当前 v2 / baseline 共同口径

- 常规 action rollout 从单一 6 回合终点评估改为 10 回合两层评估。
- 评估在第 6 回合和第 10 回合各算一次，最终按 `mid_eval_weight` 加权，默认第 6 回合权重 `0.5`。
- 允许 `basic -> quick -> sniper` 三连升候选，仅限 `C / L / R` 系列格子。
- C1 仍是唯一有额外结构奖励或转型惩罚的格子，其他 `C / L / R` 三连升不吃 C1 bonus。
- 闪电在敌方没有激活超武效果时额外施加 `lightning_no_enemy_super_penalty = -100`。
- `sniper -> quick` 降级额外施加 `sniper_downgrade_penalty = 200`，适用于所有位置。
- C1 出 Sniper 之前，非 C1 位置不生成 Quick 或 Sniper 路线；二级塔仅考虑 Heavy / Mortar。
- C1 出 Sniper 后，其他 base 槽位才放开 Quick 与 Sniper 路线。
- base+lure 组合只允许关联同一座 base 塔的回收，不再生成多座 base 塔同时降级组合。
- 新增 `sniper -> quick -> sniper` refresh 候选，用于利用升级回满血修复受损 Sniper。
- 闪电默认仍是单放；只有战斗蚁贴身己方塔时，才额外生成“该塔降级/拆 + 闪电”的候选。

- root 动作是 `hold + base + lure + recycle_base*lure + lightning`。
- `base` 与 `lure` 不乘算，只有纯回收类 `base` 可与 `lure` 组合。
- future rollout 仍不生成未来基地蚂蚁。
- future rollout 仍只保留战斗蚁贴塔时的 reactive 降级/拆塔。
- 闪电使用棋盘中心半径 5 的 91 个中心做 UCB 分配 rollout。

## Build / Package

```bash
cd Game1/antgame_ai_cpp/cpp_lure_v2
make

cd Game1/antgame_ai_cpp
bash package_ai.sh cpp_lure_v2
```

## Eval

自战：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target cpp_lure_v2 \
  --seeds 1:8 \
  --jobs 8 \
  --output-dir ./eval_current \
  --force
```

与冻结 baseline 对战：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target0 cpp_heavy_baseline \
  --target1 cpp_lure_v2 \
  --seeds 1:16 \
  --jobs 16 \
  --output-dir ./eval_baseline_p0_v2_p1 \
  --force
```

座位平衡时应再反向运行 `--target0 cpp_lure_v2 --target1 cpp_heavy_baseline`。

## 2026-04-27 冻结说明

- 当前 v2 已完全覆盖到 `cpp_heavy_baseline`。
- v2 与 baseline 此后应作为同一冻结点理解。
- 后续主动超武探索从 `cpp_lure_v3` 开始。
