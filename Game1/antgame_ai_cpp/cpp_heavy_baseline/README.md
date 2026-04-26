# cpp_heavy_baseline

这是当前保留的 Game1 C++ AI 入口。

目录名沿用历史命名，但内部已经不是旧版 `heavy` 基线。

## 1. 当前入口

- `ai_cpp_heavy_baseline.cpp`
  - 比赛协议入口
  - 维护 `PublicState`
  - 维护 `NativeSimulator`
  - 调用 `antgame_sdk::decide_lure_strategy()`

## 2. 当前真实依赖

- `../../antgame_cpp_sdk/include/antgame_sdk/lure_strategy.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/lure_strategy_params.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/random_search_baseline.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/position_slots.hpp`

## 3. 当前策略口径

当前 baseline 的关键点：

- root 动作拆成 `base`、`lure`、`lightning`
- 常规候选是 `hold + base + lure + recycle_base*lure`
  - `base` 和 `lure` 不再乘算，同回合只选择其中一种主动策略
  - 只有纯回收类 `base` 动作可以与 `lure` 组合
  - 全 hold 只使用一个统一 `hold_bonus`
- 闪电是独立候选，目前只考虑单闪电
  - 遍历所有合法中心
  - 排除 `distance_to_boundary < lightning_min_boundary_distance` 的位置
  - 所有中心共享 UCB rollout 总预算
  - 不带前置降级/拆塔，也不与 `base/lure` 组合
- rollout 未来回合只保留 reactive 回收：
  - 若战斗蚁贴身己方塔，固定尝试降级/拆塔回收
  - 不再每个未来回合重新生成完整 `base/lure` 主动计划
- rollout 的防守模拟不生成未来基地蚂蚁
  - fast 使用 `ignore_enemy_spawns`
  - native 对拍使用 SDK 的 `advance_round_without_base_spawns()`
  - 实际对局同步仍以官方 `Ant-Game` 回合推进为准
- 首回合 rollout 只对威胁最高的最多 `5` 只蚂蚁做独立覆盖采样
  - 每只重点蚂蚁的所有正概率动作至少覆盖一次
  - 样本权重按这些重点蚂蚁真实动作概率乘积计算
- 终点评估只看：
  - 基地血
  - 塔可回收价值
  - 金币
  - worker threat
  - combat threat

当前还包含以下实现约束：

- 组合动作必须整组合法
- 当前 `base` 支持受限 swap，但不生成完整任意 op-list
- `lure` 的 relocate 仍允许“拆/卖 + 建”，并按先拆后建排序
- 若需要拆多塔，则优先拆当前血量更高的塔
- `base` 操作位置为旧版 `C / L / R / LL / RR` 系列槽位
- 非 lure 塔最多允许 `max_non_lure_towers = 2`
- `base` 的二级塔候选按 C1 状态区分：
  - C1 自身保留 `Heavy` 与 `Quick -> Sniper` 路线
  - C1 已是 `Sniper` 时，其他 base 槽位允许 `Heavy / Quick / Mortar`
  - C1 未成 `Sniper` 时，其他 base 槽位允许 `Heavy / Mortar`
  - 任意 base 槽位上的 `Quick` 后续都只允许继续升为 `Sniper`
  - `Sniper` 是当前唯一 3 级塔候选
- `base` 支持结构化多步 followup，最多覆盖 root 后 3 个未来回合：
  - `build slot -> upgrade allowed level-2 tower`
  - `upgrade Basic -> Quick -> Sniper`
  - `downgrade slot -> downgrade same slot`
  - `downgrade/sell source to bottom -> build another base slot`
  - `downgrade/sell source to bottom -> build another base slot -> upgrade allowed level-2 tower`
  - swap 源塔只允许 Basic 或一级塔，最多连续 2 次降级/出售，不处理顶级塔卖到底
  - 同回合多塔操作只允许多个 `downgrade/sell`
- `C1` 仍是唯一允许额外结构奖励/惩罚的 base 槽位
- 当前 lure 建塔位置不做额外启发式打分
  - 当前 lure 已开放除 `C / L / R / LL / RR` 系列之外的旧版位置槽位

2026-04-27 全 log 自战口径：

- 16 组 256 回合全部打满，P0/P1 平均终局血量 `26.5 / 28.125`
- 16 组 512 回合平均 `503.8125` 回合，胜负为 P0 `9`、P1 `6`、未归零到上限 `1`
- 32 个 fast/native 对拍 case 均执行成功，终点总评分平均绝对差约 `12.04`

## 4. Build

```bash
cd Game1/antgame_ai_cpp/cpp_heavy_baseline
make
```

## 5. Package

```bash
cd Game1/antgame_ai_cpp
bash package_ai.sh cpp_heavy_baseline
```

## 6. Debug / Eval

推荐工具：

- `../tools/eval_cpp_selfplay.py`
- `../tools/eval_cpp_partial_selfplay.py`
- `../tools/analyze_selfplay_batch.py`
- `../../antgame_cpp_sdk/build/sdk_lure_perf`
- `../../antgame_cpp_sdk/build/sdk_defense_parity`
- `../../antgame_cpp_sdk/build/sdk_lure_inspector`

典型流程：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target cpp_heavy_baseline \
  --seeds 1:8 \
  --debug-seeds 1 \
  --jobs 8 \
  --max-rounds 256 \
  --output-dir ./eval_current \
  --force

python tools/analyze_selfplay_batch.py ./eval_current
```

注意：

- 当前官方 `Game1/Ant-Game/game/output/main` 不会主动执行 init 里的 `config.max_rounds`
- 所以 `--max-rounds 256` 目前只能作为“期望测试窗口”的元数据，不保证 replay 真在 `256` 回合结束
- 若要分析严格前 `256` 回合，应对 replay 与 debug log 自行裁切

若要直接得到严格前 `256` 回合且保留全 plans log，建议改用：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_partial_selfplay.py \
  --target cpp_heavy_baseline \
  --seeds 1:8 \
  --debug-seeds 1:8 \
  --jobs 8 \
  --max-rounds 256 \
  --output-dir ./eval_partial_full_log_256 \
  --force
```

## 7. 边界说明

- 规则真值仍以 `../../Ant-Game/` 为准
- SDK 与 baseline 都不能把改动写回 `Ant-Game/`
- `eval_*`、`tmp_*`、位置图和临时 replay 分析目录都视为生成物，不进版本库
- 当前性能优化重点：
  - 搜索用 `DefenseSimulator` 热路径以固定数组为主
  - rollout clone 不复制派生 move cache
  - 内层主要剩余热点是增强移动的反向路径规划
