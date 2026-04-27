# cpp_lure_v3

这是 Game1 当前 v3 C++ AI。2026-04-27 之后，`cpp_heavy_baseline` 已被当前 v2 完全覆盖，因此 v2 与 baseline 当前是同一策略冻结点。后续进攻性探索应新开 v3，不应直接改 v2 或 baseline。

## 入口

- `ai_cpp_lure_v3.cpp`
  - 比赛协议入口
  - 维护 `PublicState`
  - 维护 `NativeSimulator`
  - 调用 `antgame_sdk::decide_lure_strategy()`

## 依赖

- `../../antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v3.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/lure_strategy_v3_params.hpp`
  - v3 独立参数，类型/访问函数为 `V3LureStrategyTuning` / `v3_lure_config()`
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

## v3 新增逻辑

v3 暂时不改变 v2 的搜索和估值，只在最优行动选出后做一个进攻性 `Emergency Evasion` 后处理。

若同时满足以下条件，则在本回合 best action 后追加一个紧急回避：

- 敌方 `Lightning Storm` 当前没有生效。
- 敌方 `Lightning Storm` 冷却至少还有 `10` 回合。
- 模拟执行 best action 后，我方金币仍然 `> 100`。
- 模拟执行 best action 后，`C1` 仍是 `Sniper`。
- 某个 `Emergency Evasion` 中心能覆盖至少 `5` 只我方工蚁。

选点规则：

- 只统计我方 `Worker`，不把战斗蚁计入覆盖数。
- 优先覆盖工蚁数最多的位置。
- 工蚁数相同时，优先更靠近敌方基地的位置。

debug summary 会额外输出 `v3_evasion_used`、`v3_evasion_reason`、`v3_evasion_worker_count`、`v3_evasion_x/y` 等字段，方便检查是否正确触发。

## 2026-04-27 v3 vs v2 结果

座位平衡 32 局完整官方对局：

- `tmp_v3_vs_v2_32_p0/`：v3 为 P0，v2 为 P1，v3 `7` 胜，v2 `9` 胜。
- `tmp_v3_vs_v2_32_p1/`：v2 为 P0，v3 为 P1，v2 `7` 胜，v3 `9` 胜。
- 合计：v3 `16` 胜，v2 `16` 胜。
- 平均终局血量：v3 `19.53125`，v2 `19.1875`。
- 平均终局金币：v3 `327.40625`，v2 `321.5`。
- 紧急回避实际触发 `1` 次。

触发样本：

- replay：`Game1/antgame_ai_cpp/tmp_v3_vs_v2_32_p0/matches/seed_0015/replay.json`
- 回合：`312`
- 操作：`Emergency Evasion` at `(4,10)`
- 覆盖：`5` 只己方工蚁，`0` 只己方战斗蚁
- best action 后金币：`490`
- 敌方闪电 CD：`19`
- 官方 replay 中金币从 `490` 扣到 `430`，符合回避费用 `60`

主要 gate 统计：

- v3(P0) run：`enemy_lightning_cd_too_low 5584`，`enemy_lightning_active 1450`，`post_action_coins_too_low 397`，`no_c1_sniper 378`，`insufficient_worker_coverage 320`，`use 1`。
- v3(P1) run：`enemy_lightning_cd_too_low 5875`，`enemy_lightning_active 1323`，`no_c1_sniper 317`，`post_action_coins_too_low 235`，`insufficient_worker_coverage 385`，`use 0`。

结论：当前后处理没有看到非法操作或误触发；触发率很低，主要因为敌方闪电窗口和 `>=5` 工蚁覆盖条件很难同时满足。

## Build / Package

```bash
cd Game1/antgame_ai_cpp/cpp_lure_v3
make

cd Game1/antgame_ai_cpp
bash package_ai.sh cpp_lure_v3
```

## Eval

自战：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target cpp_lure_v3 \
  --seeds 1:8 \
  --jobs 8 \
  --output-dir ./eval_current \
  --force
```

与 v2 / baseline 对战：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target0 cpp_lure_v2 \
  --target1 cpp_lure_v3 \
  --seeds 1:16 \
  --jobs 16 \
  --output-dir ./eval_v2_p0_v3_p1 \
  --force
```

座位平衡时应再反向运行 `--target0 cpp_lure_v3 --target1 cpp_lure_v2`。

## 2026-04-27 冻结说明

- 当前 v2 已完全覆盖到 `cpp_heavy_baseline`。
- v2 与 baseline 此后应作为同一冻结点理解。
- 后续主动超武探索从 `cpp_lure_v3` 开始。
