# cpp_lure_v3

这是 Game1 当前 v3 C++ AI。2026-04-27 之后，`cpp_heavy_baseline` 已被当前 v2 完全覆盖，因此 v2 与 baseline 当前是同一策略冻结点。`cpp_lure_v2` 源码目录和打包目标已经删除。后续实验应保持 v3 与 baseline 解耦，不直接改 baseline。

## 入口

- `ai_cpp_lure_v3.cpp`
  - 比赛协议入口
  - 维护 `PublicState`
  - 维护 `NativeSimulator`
  - 调用 `antgame_sdk::decide_lure_strategy()`

## 依赖

- `include/antgame_ai/lure_strategy_v3.hpp`
  - 对外聚合入口，保留旧 include 路径
- `include/antgame_ai/lure_strategy_v3_params.hpp`
  - v3 独立参数，类型/访问函数为 `V3LureStrategyTuning` / `v3_lure_config()`
- `include/antgame_ai/lure_strategy_v3_core.hpp`
  - core 聚合入口
- `include/antgame_ai/lure_strategy_v3_session.hpp`
  - 决策上下文与跨回合 last_move 推断
- `include/antgame_ai/lure_strategy_v3_core_format.hpp`
  - debug、随机种子、塔位名称、操作显示
- `include/antgame_ai/lure_strategy_v3_core_ops.hpp`
  - 操作排序、合法化和 plan key
- `include/antgame_ai/lure_strategy_v3_core_values.hpp`
  - 塔回收价值、降级惩罚和行为威胁倍率
- `include/antgame_ai/lure_strategy_v3_plan_types.hpp`
  - root plan、followup、rollout/eval 数据结构和显示工具
- `include/antgame_ai/lure_strategy_v3_base_rules.hpp`
  - base 槽位规则、C1 sniper 状态、可升级类型
- `include/antgame_ai/lure_strategy_v3_base_swap.hpp`
  - base 换塔候选的公共构造
- `include/antgame_ai/lure_strategy_v3_reactive_targets.hpp`
  - lure/非 lure 塔贴身回收目标选择
- `include/antgame_ai/lure_strategy_v3_base_plans.hpp`
  - base 候选生成主流程
- `include/antgame_ai/lure_strategy_v3_lure_plans.hpp`
  - 单 lure / forced relocate 候选
- `include/antgame_ai/lure_strategy_v3_lightning_plans.hpp`
  - 闪电中心和敌方塔伤害静态分
- `include/antgame_ai/lure_strategy_v3_root_plans.hpp`
  - root action 合成、去重和分类计数
- `include/antgame_ai/lure_strategy_v3_reactive.hpp`
  - rollout 中贴身回收与 followup 执行
- `include/antgame_ai/lure_strategy_v3_evaluation.hpp`
  - action-level UCB 汇总入口
- `include/antgame_ai/lure_strategy_v3_threat.hpp`
  - worker/combat threat 计算
- `include/antgame_ai/lure_strategy_v3_rollout_sampling.hpp`
  - first-step forced rollout 分配
- `include/antgame_ai/lure_strategy_v3_terminal_eval.hpp`
  - 终点评估、C1 root bonus 和两层估值合成
- `include/antgame_ai/lure_strategy_v3_rollout_score.hpp`
  - 单条 rollout 执行和闪电反事实 bonus
- `include/antgame_ai/lure_strategy_v3_offense.hpp`
  - 进攻性 `EMP Blaster` / `Emergency Evasion` 后处理
- `include/antgame_ai/lure_strategy_v3_decision.hpp`
  - `decide_lure_strategy()` 和 debug 输出
- `../../antgame_cpp_sdk/include/antgame_sdk/random_search_baseline.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/position_slots.hpp`

SDK 默认兼容入口 `lure_strategy.hpp` / `lure_strategy_params.hpp` 仍为 v2/baseline 口径；v3 的策略与参数只放在当前目录下。

## 当前 v3 口径

- 常规 action rollout 从单一 6 回合终点评估改为 10 回合两层评估。
- 评估在第 6 回合和第 10 回合各算一次，最终按 `mid_eval_weight` 加权，默认第 6 回合权重 `0.5`。
- 允许 `basic -> quick -> sniper` 三连升候选，仅限 `C / L / R` 系列格子。
- C1 仍是唯一有额外结构奖励或转型惩罚的格子，其他 `C / L / R` 三连升不吃 C1 bonus。
- C1 `Heavy` 与 `Quick / Sniper` 路线切换阈值按 root/followup 后局面的己方等效总金币判断：`当前金币 + 全塔最优回收价值`。
- 闪电在敌方没有激活超武效果时额外施加 `lightning_no_enemy_super_penalty = -100`。
- `sniper -> quick` 降级额外施加 `sniper_downgrade_penalty = 500`，适用于所有位置。
- C1 出 Sniper 之前，非 C1 位置不生成 Quick 或 Sniper 路线；二级塔仅考虑 Heavy / Mortar。
- C1 出 Sniper 后，其他 base 槽位才放开 Quick 与 Sniper 路线。
- base+lure 组合只允许关联同一座 base 塔的回收，不再生成多座 base 塔同时降级组合。
- 新增 `sniper -> quick -> sniper` refresh 候选，用于利用升级回满血修复受损 Sniper。
- 闪电默认仍是单放；只有战斗蚁贴身己方塔时，才额外生成“该塔降级/拆 + 闪电”的候选。

- root 动作是 `hold + base + lure + recycle_base*lure + lightning`。
- `base` 与 `lure` 不乘算，只有纯回收类 `base` 可与 `lure` 组合。
- future rollout 仍不生成未来基地蚂蚁。
- future rollout 仍只保留战斗蚁贴塔时的 reactive 降级/拆塔；若下一回合塔攻击阶段能杀掉所有贴身威胁战斗蚁，则不执行 reactive 回收。
- 普通 root action 使用 action-level UCB：每次给一个普通 action 补 `action_ucb_batch_rollouts` 次，直到普通组总 rollout 数达到 `normal_action_count * rollout_count` 的平均目标。
- 闪电和 `recycle + lightning` 使用独立 UCB：每次补 `lightning_ucb_batch_rollouts=1` 次，整个闪电组总预算默认为 `lightning_ucb_total_rollouts=500`，不与普通 action 抢 UCB 预算。

## v3 新增逻辑

v3 已独立于 v2 继续迭代 root 搜索、reactive 模拟和估值参数；进攻性超武仍作为最优行动选出后的后处理。

### Offensive EMP

若同时满足以下条件，则在本回合 best action 后优先追加一个 `EMP Blaster`：

- `offensive_emp_enabled = true`。
- 敌方 `Lightning Storm` 当前没有生效。
- 敌方 `Lightning Storm` 冷却至少达到 `offensive_evasion_min_enemy_lightning_cd`。
- 模拟执行 best action 后，我方金币大于 `offensive_evasion_min_post_action_coins`，且实际金币足够支付 EMP 费用。
- best action 后存在一只己方 `Combat` ant，距离敌方任意顶级塔不超过 `offensive_emp_combat_to_top_tower_distance`。

选点规则：

- EMP 中心固定为满足条件的敌方顶级塔坐标。
- 多个候选塔同时满足时，优先选择最近战斗蚁距离更小的塔；再按塔回收价值、到敌方基地距离、塔 ID 稳定排序。
- 官方逻辑会对 `Lightning Storm` 和 `EMP Blaster` 的 active effect 执行 `drift_items()`，因此 replay 中 `activeEffects` 坐标可能在同回合末偏离实际释放操作坐标；真实释放坐标以 `op0/op1` 中的 operation 为准。

### Offensive Evasion

若同时满足以下条件，则在本回合 best action 和可能的 EMP 后追加一个紧急回避：

- 敌方 `Lightning Storm` 当前没有生效。
- 敌方 `Lightning Storm` 冷却至少达到 `offensive_evasion_min_enemy_lightning_cd`。
- 模拟执行 best action 后，我方金币大于 `offensive_evasion_min_post_action_coins`。
- 模拟执行 best action 后，`C1` 仍是 `Sniper`。
- 某个 `Emergency Evasion` 中心覆盖的我方工蚁数达到 `offensive_evasion_min_worker_count`。

选点规则：

- 只统计我方 `Worker`，不把战斗蚁计入覆盖数。
- 优先覆盖工蚁数最多的位置。
- 工蚁数相同时，优先更靠近敌方基地的位置。

debug summary 会额外输出 `v3_evasion_used`、`v3_evasion_reason`、`v3_evasion_worker_count`、`v3_evasion_x/y` 等字段，方便检查是否正确触发。
EMP 对应输出 `v3_emp_used`、`v3_emp_reason`、`v3_emp_x/y`、`v3_emp_tower_id`、`v3_emp_combat_ant_id`、`v3_emp_distance` 等字段。

当前参数默认值为：敌方闪电 CD 至少 `5`，best action 后金币大于 `30`，回避中心覆盖至少 `4` 只己方工蚁。
EMP 默认开启，战斗蚁到敌方顶级塔触发距离为 `2`。

## 2026-04-28 EMP 测试

当前实验口径为：

- 进攻超武门槛：`5/30/4`。
- 关键估值参数：`sniper_downgrade_penalty=500`、`base_hp_weight=300`、`worker_threat_unit=300`。

该口径下先执行首批 32 局：

- 目录：`Game1/antgame_ai_cpp/tmp_v3_emp_vs_baseline_batch1_32/`
- 对阵：P0=`cpp_lure_v3`，P1=`cpp_heavy_baseline`
- 并发：`--jobs 32`
- 结果：v3 `12` 胜，baseline `20` 胜，未继续后续三批。
- 平均终局血量：v3 `17.625`，baseline `21.9375`。
- 平均终局金币：v3 `187.9375`，baseline `432.21875`。
- EMP 实际释放 `3` 次，触发距离均为 `2`。
- Emergency Evasion 实际释放 `9` 次，覆盖工蚁数均达到当前门槛。

检查结论：

- EMP 操作坐标均为敌方顶级塔坐标；replay 中 active effect 可能漂移，这是官方 `drift_items()` 行为，不是坐标反向或前端显示错误。
- EMP / 回避触发均满足当前 `5/30/4` 门槛，未发现非法操作或坐标错误。
- v3 作为 P0 对 baseline 偏弱；后续应优先继续分析基础搜索/估值、经济和座位/seed 分布。

## 2026-04-27 历史 v3 vs baseline 结果

以下结果来自当前 action-level UCB / reactive 击杀检测重构之前的历史参数，仅作为回归参考。结果目录沿用当时的历史命名：

- `tmp_v3_vs_v2_32_p0/`：v3 为 P0，baseline 为 P1，v3 `7` 胜，baseline `9` 胜。
- `tmp_v3_vs_v2_32_p1/`：baseline 为 P0，v3 为 P1，baseline `7` 胜，v3 `9` 胜。
- 合计：v3 `16` 胜，baseline `16` 胜。
- 平均终局血量：v3 `19.53125`，baseline `19.1875`。
- 平均终局金币：v3 `327.40625`，baseline `321.5`。
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

与 baseline 对战：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target0 cpp_heavy_baseline \
  --target1 cpp_lure_v3 \
  --seeds 1:16 \
  --jobs 16 \
  --output-dir ./eval_baseline_p0_v3_p1 \
  --force
```

座位平衡时应再反向运行 `--target0 cpp_lure_v3 --target1 cpp_heavy_baseline`。

## 2026-04-27 冻结说明

- 当前 v2 已完全覆盖到 `cpp_heavy_baseline`。
- `cpp_lure_v2` 源码目录和打包目标已删除。
- 后续主动超武探索从 `cpp_lure_v3` 开始。
