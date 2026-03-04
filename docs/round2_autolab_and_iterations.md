# 第二轮：本地版本管理、自动评测与算法迭代

## 1. 目标

- 建立可持续的本地版本管理与自动评测流水线。
- 面向 16 CPU 机器做并行批量评测与 Elo 评分（当前默认并发上限 14）。
- 在此框架下进行算法级迭代（不是只调参），并记录结果。

当前 Elo 治理约束（长期有效）：

- 生产 Elo（`/www/autolab/runtime/latest.json`）是唯一权威排名，用于 champion 决策与最终优劣判断。
- 迭代 Elo（`/www/autolab/runtime/scopes/iter/latest.json`）仅用于候选筛选与方向探索。
- 不同 scope / 不同对阵池下的 Elo 绝对值不可直接横向比较。

## 2. 新增系统（Autolab）

目录与入口：

- `/www/autolab/registry.json`：版本注册表（含 champion、anchors）。
- `/www/autolab_manage.py`：版本管理（注册、快照、设 champion）。
- `/www/autolab_eval.py`：批量评测 + Elo。
- `/www/autolab_schedule.py`：定时调度评测。
- `/www/autolab/runtime/`：轮次评测产物（json/jsonl）。
- `/www/autolab/versions/`：本地快照版本（源码+二进制）。

并行策略：

- 评测默认 `jobs=16`（实际取 `min(16, cpu_count)`）。
- 基于 `ProcessPoolExecutor` 并行运行单局对战任务。

评测模式：

- `round_robin`：全量两两对战。
- `gauntlet`：challenger 对 champion + anchors（默认 anchors：`greedy`、`random_safe`）。

Elo 机制：

- 标准 Elo 在线更新：`R' = R + K * (S - E)`。
- 每局结果映射：胜 `1`，负 `0`，平 `0.5`。
- 当前默认：`base_rating=1500`，`k_factor=20`。

## 3. 版本管理实践（本轮）

已注册版本（核心）：

- `cpp_v1_current`：当前主线 C++ AI
- `cpp_v1_r2_baseline`：第二轮起点快照
- `cpp_v2_beam`：算法迭代版（beam 序列搜索）
- `cpp_v3_hybrid`：算法迭代版（beam+greedy 仲裁）
- `cpp_v4_counterfactual`：算法迭代版（反事实首步 + 稳健仲裁）
- `cpp_v5_counterfactual_2ply`：算法迭代版（选择性 2-ply 反事实规划）
- `cpp_v6_adaptive_2ply`：算法迭代版（自适应 2-ply 宽度 + 主将邻域破口评估）
- `cpp_v7_mode_switch`：算法迭代版（攻防模式切换 + 模式感知仲裁）
- `cpp_v8_mode_hysteresis`：算法迭代版（模式滞回 + 进攻安全闸门）
- `cpp_v9_emergency_antibeam`：算法迭代版（紧急切防 + 反 beam 防守特征）
- `greedy` / `random_safe`：anchor 基线

## 4. 算法迭代记录

### 4.1 v2（`cpp_v2_beam`）

核心创新：

- 将“每步贪心”升级为“多步序列规划”：
  - 通过 `beam search` 在行动预算内搜索动作序列；
  - 使用局面估值函数（兵力、占格、经济、主将安全、敌主将距离）评估中间状态；
  - 结合 `past_AIs/Generals-AI` 的 threat/impact 思路改造为轻量可执行版本。

结果：

- 短回合 round_robin（140 回合）中曾领先；
- 长回合 gauntlet（160 回合）暴露退化，面对强对手（v1）表现不稳。

### 4.2 v3（`cpp_v3_hybrid`）

核心创新：

- 混合规划器（`beam + greedy`）：
  - 同时生成 beam 序列与 greedy 序列；
  - 用仿真评分做仲裁，仅在 beam 有显著预测优势时采用；
  - 目标是削弱 beam 的中后期误导风险。

结果：

- 相比 v2 稳定性略有改善，但仍未超过 `cpp_v1_current`。

### 4.3 v4（`cpp_v4_counterfactual`）

核心创新（算法级改动）：

- 将“对手响应近似”真正接入决策层，而不只是停留在辅助函数：
  - 新增 `score_state_robust = 0.35 * optimistic + 0.65 * pessimistic`，其中 pessimistic 来自 top-k 敌方应手的最差值近似。
  - `beam` 在根层（depth=0）用稳健评分扩展候选，降低单边高估导致的首步误判。
- 新增“反事实首步规划器”（`plan_moves_counterfactual_opening`）：
  - 首步从 top-8 候选中按“我方落子后 + 敌方近似反击”的稳健值选优；
  - 后续步骤再用 greedy 续推，形成“首步稳健、后续高效”的分层流程。
- 主流程从 `beam vs greedy` 二路仲裁升级为三路仲裁：
  - `counterfactual_opening`、`beam`、`greedy` 都用统一稳健评分比较；
  - 增加首步安全回退：若首步反事实值显著劣于“按兵不动”，回退到 greedy 序列。

## 5. 本轮评测结果摘要（2026-03-03）

关键轮次与文件：

- `docs/iteration_round2_eval_cycle1.md`
- `docs/iteration_round2_eval_cycle2.md`
- `docs/iteration_round2_eval_cycle3.md`
- `autolab/runtime/latest.json`（当前最新：`eval_20260303_152857`）
- `autolab/runtime/eval_20260303_152806_summary.json`（本轮 v4 验证）

### 5.1 最新基线（`eval_20260303_152857`，gauntlet）

`latest.json` 显示当时 champion 发生切换：`cpp_v1_current -> cpp_v2_beam`。

主要 Elo（同轮）：

- `cpp_v2_beam`: 1676.95（champion）
- `cpp_v1_r2_baseline`: 1643.75（落后 33.20）
- `cpp_v4_counterfactual`: 1588.12（落后 88.83）
- `cpp_v3_hybrid`: 1586.59（落后 90.37）
- `cpp_v1_current`: 1481.38（落后 195.57）

可见短板已从“能否超过 anchor”转为“面对 `v2` 的稳定对抗能力”。

### 5.2 本轮 v4 验证（`eval_20260303_152806`，gauntlet）

执行命令：`autolab_eval.py --mode gauntlet ... --challengers cpp_v4_counterfactual --opponents cpp_v2_beam,cpp_v1_current,cpp_v1_r2_baseline,greedy,random_safe`

结果（60 局）：

- 总体：`cpp_v4_counterfactual` 44/60，Elo 1668.83（本轮第一）
- 对 `cpp_v2_beam`：7/12
- 对 `cpp_v1_current`：7/12
- 对 `cpp_v1_r2_baseline`：6/12
- 对 `greedy` / `random_safe`：各 12/12
- 注：该轮是“定向 challenger-vs-opponents”验证；`latest.json` 可能被后台 idle loop 覆盖为其他轮次，需结合 `eval_20260303_152806_summary.json` 一并解读。

## 6. 风险与限制

- 本轮环境受沙箱信号量权限限制（`multiprocessing.SemLock`），无法使用 `jobs>1`；验证以 `jobs=1` 串行完成，吞吐和统计稳定性弱于标准 14 并发批测。
- 对手响应近似仍是轻量 top-k（k=3）单步反击，不是完整 minimax，多步战术交换仍可能被低估。
- `v4` 对 `cpp_v1_r2_baseline` 仅 6/12，且有先后手波动，说明中盘稳定性仍需继续加固。

## 7. 下一步（算法优先）

优先级从高到低：

1. 从 `Generals-AI` 迁移更完整的“威胁来源分解 + 局部战斗值”评估，而非单一启发式打分。
2. 将当前反事实评估扩展到“首步 + 关键二步”的选择（选择性 2-ply），提高中盘换子/压主将场景稳定性。
3. 把“征召/升级”与“战术动作”分离成显式策略模式（defense/expand/kill-window），减少同回合策略冲突。
4. 在具备并行权限的环境下复跑 `gauntlet --jobs 14 --cpu-policy idle_only`，并固定 seed 集做回归门禁。

## 8. 本回合增量（2026-03-03，v5）

### 8.1 算法级改动

新增版本：

- `cpp_v5_counterfactual_2ply`（`/www/ai_cpp/v5/ai_v5.cpp`，可执行 `/www/ai_cpp/v5/ai_v5`）

核心变更（相对 v4）：

- 将 `plan_moves_counterfactual_opening` 升级为“每步选择性 2-ply 反事实规划”：
  - 新增 `evaluate_two_step_counterfactual`：对每个首步，评估 `首步落子` 与 `次步最佳跟进` 的稳健值；
  - 新增 `select_best_move_counterfactual_2ply`：从 top-k 首步中按 2-ply 稳健值选优；
  - 新增 `plan_moves_counterfactual_2ply`：在行动预算内逐步重复该选择器，而不是“首步反事实 + 后续贪心”。
- 新增过度进攻刹车：
  - 若候选首步 `next_score + 8.0 < hold_score`（按 `score_state_robust`）则停止该序列扩展，避免明显负收益换子。
- 主流程仲裁保持三路，但将 counterfactual 分支替换为 2-ply 分支：
  - `counterfactual_2ply`、`beam`、`greedy` 统一用稳健分比较。

### 8.2 可复现实验（已执行）

注册命令：

- `python3 autolab_manage.py register-cpp --version-id cpp_v5_counterfactual_2ply --exe /www/ai_cpp/v5/ai_v5 --src /www/ai_cpp/v5/ai_v5.cpp --notes "selective 2-ply counterfactual planner"`

评测命令（固定 seed，可复现）：

- `python3 autolab_eval.py --mode gauntlet --versions cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v4_counterfactual,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v5_counterfactual_2ply --opponents cpp_v2_beam,cpp_v4_counterfactual,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --games-per-pair 2 --max-rounds 160 --jobs 1 --cpu-policy all --seed 20260303 --no-auto-promote`

结果：

- 轮次：`eval_20260303_154553`
- 汇总：`/www/autolab/runtime/eval_20260303_154553_summary.json`
- 明细：`/www/autolab/runtime/eval_20260303_154553_matches.jsonl`
- 总体：`cpp_v5_counterfactual_2ply` 15/24（62.5%），Elo 1554.62（该轮第一）
- 分对手：
  - vs `cpp_v2_beam`：1/4
  - vs `cpp_v1_current`：1/4
  - vs `cpp_v1_r2_baseline`：2/4
  - vs `cpp_v4_counterfactual`：3/4
  - vs `greedy`：4/4
  - vs `random_safe`：4/4

解读：

- 2-ply 规划在“压制 v4、稳定吃 anchor”上有效，但对 `v2` 与 `v1_current` 仍明显落后，说明当前改动更像“纠偏与稳健性增强”，尚未形成对强基线的稳定优势。

### 8.3 风险

- 样本量仍小（每个强对手仅 4 局），结论方差高，不能据此判定真实 Elo 排名。
- 当前环境只能 `jobs=1`，难以快速做多 seed 回归，迭代反馈周期偏长。
- 2-ply 评估增加单回合计算量，可能在高复杂局面带来决策时延风险（需后续做耗时剖析）。

### 8.4 下一步

1. 固定同一对手集，复跑 `games-per-pair=6` 或 `10`（同 seed 规则）验证 v5 对 `v2/v1_current` 的真实胜率。
2. 在 2-ply 里加入“威胁触发的自适应宽度”（高压局面增大 second_top_k，低压局面缩小）以提升性价比。
3. 在稳健评分中加入“主将邻域破口惩罚/封堵奖励”，优先修复 v5 对强对手的防线稳定性短板。

## 9. 本回合增量（2026-03-03，v6）

### 9.1 算法级改动

新增版本：

- `cpp_v6_adaptive_2ply`（`/www/ai_cpp/v6/ai_v6.cpp`，可执行 `/www/ai_cpp/v6/ai_v6`）

核心改动（相对 v5）：

1. 在估值函数中加入“主将邻域破口”结构特征：
   - 对主将四邻格统计友军护卫、敌军压迫、可通行破口数量；
   - 新增 `ring_enemy - ring_friend` 赤字惩罚与 `breaches` 惩罚，降低“主将周边空洞”局面的误判。
2. 在敌方反应近似中引入自适应分支宽度：
   - `evaluate_after_enemy_response` 中，敌方候选从固定 `top_k=3` 改为按主将压力比自适应（低压 `2`、常态 `3`、高压 `5`）。
3. 在 2-ply 规划中引入威胁触发宽度调度：
   - `plan_moves_counterfactual_2ply` 按 `main_pressure_ratio` 与主将间距动态调节 `first_top_k/second_top_k`；
   - 高压局面增宽搜索，低压中后期缩宽提速，并配套自适应停手阈值（`stall_margin`）。

### 9.2 可复现实验（已执行）

注册命令：

- `python3 autolab_manage.py register-cpp --version-id cpp_v6_adaptive_2ply --exe /www/ai_cpp/v6/ai_v6 --src /www/ai_cpp/v6/ai_v6.cpp --notes "adaptive 2-ply width + main-ring breach evaluation"`

评测命令（固定 seed，可复现）：

- `python3 autolab_eval.py --mode gauntlet --versions cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v4_counterfactual,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v6_adaptive_2ply --opponents cpp_v5_counterfactual_2ply,cpp_v4_counterfactual,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --games-per-pair 3 --max-rounds 170 --jobs 1 --cpu-policy all --seed 20260304 --no-auto-promote`

结果：

- 轮次：`eval_20260303_155453`
- 汇总：`/www/autolab/runtime/eval_20260303_155453_summary.json`
- 明细：`/www/autolab/runtime/eval_20260303_155453_matches.jsonl`
- 总体：`cpp_v6_adaptive_2ply` 28/42（66.7%），Elo 1606.01（该轮第一）
- 分对手：
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_current`：3/6
  - vs `cpp_v1_r2_baseline`：3/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v4_counterfactual`：4/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- v6 相对 v4 有清晰增益（4/6），且在 v2/v1_current 上从“明显劣势”提升到“基本持平（3/6）”。
- 这说明“自适应宽度 + 主将邻域防线评估”主要改善了中盘防守稳定性，但尚未建立对 v2 的稳定胜势。

### 9.3 风险

- 每个强对手样本仍只有 6 局，统计波动依然明显。
- 当前结果来自 `jobs=1` 串行评测，和标准并行长跑仍有分布差异风险。
- 新增评估项可能在个别局面过度保守，导致错失可行进攻窗口（需继续做攻击窗口识别）。

### 9.4 下一步

1. 对 `cpp_v6_adaptive_2ply` 做“防守态/进攻态”显式切换：高压用稳健权重，低压提高进攻奖励，减少过保守。
2. 在 v6 上做固定对手集 `games-per-pair=6` 的复现实验，重点观察 vs `cpp_v2_beam` 是否能稳定超过 50%。
3. 将 `latest.json` 的 champion 与 `autolab/registry.json` champion 进行一致性修复，避免后台轮次覆盖导致读数歧义。

## 10. 本回合增量（2026-03-03，v7，隔离评测）

### 10.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_160010`，后续被后台刷新为 `eval_20260303_160614`，属预期）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（起始为 `eval_20260303_155509`）
- 本回合严格使用隔离评测入口脚本，不直接调用会写生产 `latest/champion` 的命令。

### 10.2 算法级改动

新增版本：

- `cpp_v7_mode_switch`（`/www/ai_cpp/v7/ai_v7.cpp`，可执行 `/www/ai_cpp/v7/ai_v7`）

核心改动（相对 v6）：

1. 显式攻防模式识别（defense/balanced/offense）：
   - 新增 `ModeSignals` 与 `analyze_strategy_mode`，综合主将压力比、攻击窗口信号、兵力比进行模式判定。
2. 模式驱动的稳健评分权重：
   - `score_state_robust` 从固定 `0.35/0.65` 改为按模式动态加权：
     - 防守态：提高悲观项权重并惩罚“乐观-悲观落差”；
     - 进攻态：提高乐观项权重并加入攻击窗口奖励。
3. 模式感知的多规划器仲裁：
   - 在 `counterfactual_2ply / beam / greedy` 三路比较时加入模式偏置：
     - 防守态偏向 greedy；
     - 进攻态偏向 counterfactual 与 beam。

### 10.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 autolab_manage.py register-cpp --version-id cpp_v7_mode_switch --exe /www/ai_cpp/v7/ai_v7 --src /www/ai_cpp/v7/ai_v7.cpp --notes "mode-aware robust scoring and planner arbitration"`

评测命令（必须脚本入口）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=1 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v7_mode_switch --opponents cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260306`

结果：

- 轮次：`eval_20260303_160719`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_160719_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_160719_matches.jsonl`
- 总体：`cpp_v7_mode_switch` 28/42（66.7%），Elo 1594.47（该轮第一）
- 分对手：
  - vs `cpp_v6_adaptive_2ply`：4/6
  - vs `cpp_v5_counterfactual_2ply`：4/6
  - vs `cpp_v2_beam`：4/6
  - vs `cpp_v1_r2_baseline`：2/6
  - vs `cpp_v1_current`：2/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- v7 对 v6/v5/v2 均有优势（4/6），说明“模式切换 + 模式仲裁”确实提升了中盘主动性与稳定性。
- 但对 `v1_current` 与 `v1_r2_baseline` 退化为 2/6，表明当前进攻偏置在强防守对局中存在过冲问题。

### 10.4 风险

- 单轮每个强对手仅 6 局，仍存在显著方差。
- 进攻态奖励可能过强，导致对稳健型对手（`v1_current`、`v1_r2_baseline`）的交换质量下降。
- 单线程实验耗时较长，后续需要在隔离 scope 下恢复并行以提升迭代吞吐。

### 10.5 下一步

1. 在 `v7` 上增加“模式切换滞回”与“最短持有回合”，减少防守/进攻频繁抖动。
2. 对进攻态奖励加上“主将安全闸门”：当压力比超过阈值时自动衰减攻击窗口加成。
3. 继续使用 `autolab_eval_experiment_once.sh` 在 `iter` scope 复跑 `games-per-pair=6`，验证 v7 对 `v1_current` 能否回到至少 50%。

## 11. 本回合增量（2026-03-03，v8，隔离评测）

### 11.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_160927`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_160719`）
- 本回合继续严格使用实验脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 11.2 算法级改动

新增版本：

- `cpp_v8_mode_hysteresis`（`/www/ai_cpp/v8/ai_v8.cpp`，可执行 `/www/ai_cpp/v8/ai_v8`）

核心改动（相对 v7）：

1. 模式切换滞回 + 最短持有回合：
   - 新增 `mode_switch_confidence` 与 `apply_mode_hysteresis`；
   - 仅在切换置信度达阈值时切换模式，并设置最短持有回合（balanced 3 回合，defense/offense 5 回合）。
2. 进攻态安全闸门：
   - 在 `score_state_robust` 的进攻奖励中加入 `safety_gate`（由主将压力与兵力比共同决定）；
   - 高压力时自动衰减攻击窗口奖励，抑制“主将未稳先强攻”。
3. 锁定模式驱动序列仲裁：
   - 对 `greedy / counterfactual_2ply / beam` 的序列终点评分使用同一“锁定模式”进行比较，减少回合内模式抖动导致的仲裁噪声。

### 11.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 autolab_manage.py register-cpp --version-id cpp_v8_mode_hysteresis --exe /www/ai_cpp/v8/ai_v8 --src /www/ai_cpp/v8/ai_v8.cpp --notes "mode hysteresis + offense safety gate"`

评测命令（必须脚本入口）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=1 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v8_mode_hysteresis --opponents cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260307`

结果：

- 轮次：`eval_20260303_161706`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_161706_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_161706_matches.jsonl`
- 总体：`cpp_v8_mode_hysteresis` 34/48（70.8%），Elo 1628.70（该轮第一）
- 分对手：
  - vs `cpp_v7_mode_switch`：4/6
  - vs `cpp_v6_adaptive_2ply`：6/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：2/6
  - vs `cpp_v1_r2_baseline`：3/6
  - vs `cpp_v1_current`：4/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- v8 相比 v7 明显修复了“对 `v1_current` 退化”的问题（从 2/6 回升到 4/6）。
- 模式滞回与安全闸门有效抑制了过冲进攻，但对 `v2_beam` 仍 2/6，说明当前短板转为“对 beam 序列压制能力不足”。

### 11.4 风险

- 本轮仍是每强对手 6 局，小样本噪声仍在。
- 单线程实验耗时长，限制了同回合可验证假设数量。
- 模式持有回合可能在局势突变时响应偏慢，需要后续加入“紧急切换条件”。

### 11.5 下一步

1. 在 v8 增加“紧急切换”旁路：当主将压力比突然跃升时无视持有回合立即转 defense。
2. 针对 `v2_beam` 增加“反 beam 防守模板”特征（主将外圈二层防线完整度 + 敌方链式推进惩罚）。
3. 继续用 `autolab_eval_experiment_once.sh` 在 `iter` scope 复跑 `games-per-pair=6`，优先验证 v8 vs `v2_beam` 能否提升到至少 50%。

## 12. 本回合增量（2026-03-03，v9，隔离评测）

### 12.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_161949`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_161812`）
- 本回合继续严格使用 `autolab_eval_experiment_once.sh`，不触发生产 champion 晋升。

### 12.2 算法级改动

新增版本：

- `cpp_v9_emergency_antibeam`（`/www/ai_cpp/v9/ai_v9.cpp`，可执行 `/www/ai_cpp/v9/ai_v9`）

核心改动（相对 v8）：

1. 紧急切防旁路（模式滞回增强）：
   - `apply_mode_hysteresis` 新增“压力跃升/高压阈值”紧急分支；
   - 当主将压力比突增或反 beam 压力过高时，直接切到 `defense`，跳过持有回合限制。
2. 反 beam 防守模板特征：
   - 新增 `compute_outer_ring_defense_score`（主将二圈防线完整度）；
   - 新增 `compute_enemy_chain_pressure_to_main`（敌方链式推进压力）；
   - 将两者接入 `analyze_strategy_mode` 与 `evaluate_state`，强化对连续推进威胁的识别与惩罚。
3. 进攻安全闸门再收紧：
   - 在进攻态 `safety_gate` 里加入 `outer_defense / chain_pressure` 门控，避免“防线薄弱时的乐观高估”。
4. 仲裁偏置抗 beam：
   - 当 `chain_pressure` 高且 `outer_defense` 低时，额外提高 `greedy` 偏置，降低 `counter/beam` 偏置。

额外框架改动（为满足本回合“默认 16 并发”）：

- `autolab/evaluator.py`：
  - 并发上限从 14 提升到 16；
  - 当多进程受沙箱 `SemLock` 限制时报错时，自动回退到 `ThreadPoolExecutor(max_workers=jobs)`，保持高并发实验可执行；
  - 结果 `config` 新增 `backend` 字段（`multiprocessing` 或 `thread_fallback`）。

### 12.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 autolab_manage.py register-cpp --version-id cpp_v9_emergency_antibeam --exe /www/ai_cpp/v9/ai_v9 --src /www/ai_cpp/v9/ai_v9.cpp --notes "emergency defense switch + anti-beam ring-chain evaluation"`

评测命令（必须脚本入口，16 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=16 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v9_emergency_antibeam --opponents cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260308`

结果：

- 轮次：`eval_20260303_162506`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_162506_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_162506_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=16` 成功执行）
- 总体：`cpp_v9_emergency_antibeam` 29/54（53.7%），Elo 1555.33（该轮第一）
- 分对手：
  - vs `cpp_v8_mode_hysteresis`：1/6
  - vs `cpp_v7_mode_switch`：5/6
  - vs `cpp_v6_adaptive_2ply`：3/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：1/6
  - vs `cpp_v1_r2_baseline`：2/6
  - vs `cpp_v1_current`：2/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 本轮目标“修复对 beam 压制能力”未达成：`v9` 对 `v2_beam` 仍仅 1/6，且对 `v8` 本体退化到 1/6。
- 说明当前反 beam 特征与紧急切防存在过度防守副作用，抑制了本应保留的中盘反击机会。
- 仍有正向信号：`v9` 对 `v7` 提升明显（5/6），表明“紧急切防”在抑制激进抖动方面有效，但参数/触发阈值需要回调。

### 12.4 风险

- `thread_fallback` 与 `multiprocessing` 的执行时序不同，可能引入轻微分布差异；后续应在可用环境做一次进程池复核。
- 反 beam 特征当前惩罚偏重，导致对 `v8/v1/v2` 都出现保守退化。
- 隔离轮次依然是每强对手 6 局，统计波动仍不可忽略。

### 12.5 下一步

1. 下轮先做“反 beam 特征降权 + 自适应门控”：
   - 仅在 `pressure_jump` 或主将二圈缺口同时满足时启用强惩罚，常态降低惩罚系数。
2. 加入“防守转反击”释放条件：
   - 当 `outer_defense` 恢复且 `chain_pressure` 回落时，快速退回 balanced，避免防守模式滞留。
3. 继续用 `autolab_eval_experiment_once.sh`（`jobs=16`）复跑同对手集，优先看 `v9` 对 `v2_beam` 能否从 1/6 回升到至少 3/6。

## 13. 本回合增量（2026-03-03，v10，隔离评测）

### 13.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_163036`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_162506`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v9 失败分析）
- 本回合继续使用隔离入口脚本，不直接执行会写生产 `latest/champion` 的评测命令。

### 13.2 算法级改动

新增版本：

- `cpp_v10_antibeam_gate_release`（`/www/ai_cpp/v10/ai_v10.cpp`，可执行 `/www/ai_cpp/v10/ai_v10`）

核心改动（相对 v9）：

1. 反 beam 从硬阈值改为软门控告警（`anti_beam_alert`）：
   - 在模式识别、模式切换置信度、终局评估、仲裁偏置中统一引入 `chain_risk + ring_risk + pressure_risk` 组合告警；
   - 替换 `chain_pressure >= 16 && outer_defense <= 8` 这类硬触发，避免常态局面过早重防守。
2. 防守滞回增加“恢复释放”旁路：
   - 在 `apply_mode_hysteresis` 中新增 defense->balanced 释放条件；
   - 当 `outer_defense` 恢复且 `chain_pressure` 下降并伴随低压时，允许提前/快速回到 balanced，减少防守模式滞留。
3. 反 beam 评分降权并自适应：
   - `evaluate_state` 中 `outer_defense/chain_pressure` 的奖励惩罚由固定大权重改为随 `anti_beam_alert` 自适应；
   - 常态降低惩罚，只有高告警时才恢复强惩罚强度。
4. 进攻安全门改为“告警感知”：
   - `score_state_robust` 的 offense `safety_gate` 增加 `structure_gate` 与 `safety_floor` 动态项；
   - 低告警时放松进攻门槛，高告警时自动收紧，减少“一刀切保守”。

### 13.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v10_antibeam_gate_release --exe /www/ai_cpp/v10/ai_v10 --src /www/ai_cpp/v10/ai_v10.cpp --notes "adaptive anti-beam gating + defense release hysteresis"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v10_antibeam_gate_release --opponents cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260310`

结果：

- 轮次：`eval_20260303_163601`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_163601_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_163601_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v10_antibeam_gate_release` 30/60（50.0%），Elo 1548.70（该轮第一）
- 分对手：
  - vs `cpp_v9_emergency_antibeam`：2/6
  - vs `cpp_v8_mode_hysteresis`：2/6
  - vs `cpp_v7_mode_switch`：2/6
  - vs `cpp_v6_adaptive_2ply`：3/6
  - vs `cpp_v5_counterfactual_2ply`：2/6
  - vs `cpp_v2_beam`：4/6
  - vs `cpp_v1_r2_baseline`：1/6
  - vs `cpp_v1_current`：2/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 本轮核心目标“修复对 `v2_beam` 退化”达到阶段性结果：从 v9 的 1/6 回升到 v10 的 4/6。
- 但出现新的广谱退化：v10 对 `v8/v7/v5/v1` 多个对手回落到 2/6 或 1/6，说明当前释放逻辑和降权虽修复 anti-beam，但牺牲了中盘对抗稳定性。
- Elo 第一来自对手集中的相对关系（含 `greedy/random_safe` 与循环克制），不代表已形成稳健统治；仍应以关键对手分项战绩为主判据。

### 13.4 风险

- 关键强对手每组仍仅 6 局，方差较高。
- `thread_fallback` 并发后端可能与 `multiprocessing` 在调度序上存在微小分布差异。
- 当前 `anti_beam_alert` 在多个模块重复计算，后续若阈值继续迭代，存在一致性维护成本与漂移风险。

### 13.5 下一步

1. 做“对手分型双闸门”：
   - 将 `anti_beam_alert` 与“兵力领先/主将安全”联动，仅在满足压制条件时放大反beam惩罚，避免误伤非beam对局。
2. 为 defense release 增加短期稳定性约束：
   - 引入 2 回合恢复确认（或最小恢复积分），降低“刚释放又回防”的摆动。
3. 继续用 `autolab_eval_experiment_once.sh`（`iter`，`jobs=14`）复跑同对手集并固定 seed，对比 v10/v9 在 `v2_beam` 与 `v1_r2_baseline` 上能否同时达到至少 3/6。

## 14. 本回合增量（2026-03-03，v11，隔离评测）

### 14.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_163036`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_163601`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v10 结果）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 14.2 算法级改动

新增版本：

- `cpp_v11_dualgate_release_confirm`（`/www/ai_cpp/v11/ai_v11.cpp`，可执行 `/www/ai_cpp/v11/ai_v11`）

核心改动（相对 v10）：

1. 统一反 beam 信号计算（去重复 + 对手分型双闸门）：
   - 新增 `AntiBeamSignal` 与 `compute_anti_beam_signal`，统一输出 `alert_raw/initiative_gate/alert_effective`；
   - 将 `chain_pressure + outer_defense + pressure_ratio` 与“兵力领先 + 攻势窗口 + 低压安全”组合成 `initiative_gate`，用于在我方具备主动权时下调反 beam 告警强度，避免误伤非 beam 对局。
2. 模式切换与置信度改为使用统一 `alert_effective`：
   - `analyze_strategy_mode`、`mode_switch_confidence` 改为读取统一信号，减少阈值漂移。
3. 防守释放加入 2 回合确认：
   - `apply_mode_hysteresis` 新增 `defense_release_streak` 状态；
   - soft release 需要连续 2 回合满足恢复条件才允许 defense->balanced（hard release 保持快速释放），降低“刚恢复即反复切换”的抖动。
4. 评估与仲裁同步改为统一门控：
   - `evaluate_state` 与 `score_state_robust` 使用统一 `alert_effective`；
   - 主流程 `greedy/counter/beam` 偏置改为基于 `alert_effective + initiative_gate` 的连续调节。

### 14.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v11_dualgate_release_confirm --exe /www/ai_cpp/v11/ai_v11 --src /www/ai_cpp/v11/ai_v11.cpp --notes "dual-gate anti-beam signal + 2-round defense release confirmation"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v11_dualgate_release_confirm --opponents cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260311`

结果：

- 轮次：`eval_20260303_164606`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_164606_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_164606_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v11_dualgate_release_confirm` 32/66（48.5%），Elo 1556.46（该轮第一）
- 分对手（按明细重算，v11视角）：
  - vs `cpp_v10_antibeam_gate_release`：1/6
  - vs `cpp_v9_emergency_antibeam`：1/6
  - vs `cpp_v8_mode_hysteresis`：3/6
  - vs `cpp_v7_mode_switch`：2/6
  - vs `cpp_v6_adaptive_2ply`：3/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：2/6
  - vs `cpp_v1_r2_baseline`：4/6
  - vs `cpp_v1_current`：1/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 本轮“对手分型双闸门 + 2回合释放确认”未达目标：
  - 对 `v1_current` 仍显著退化（1/6），且对 `v10/v9` 均 1/6；
  - 对 `v2_beam` 从 v10 的 4/6 回落到 2/6。
- 说明当前 dual-gate 与释放确认耦合后，策略在强对手上出现“防守与反击都不彻底”的折中失败：
  - 对稳健型对手时无法持续建立进攻效率；
  - 对 beam 型对手时又丢失了 v10 的针对性压制。
- Elo 仍位列第一主要受对手池内循环克制与弱基线影响，不能作为“算法有效”的充分证据；关键应看强对手分项。

### 14.4 风险

- 每个强对手仍仅 6 局，统计波动依然较大。
- `thread_fallback` 后端与 `multiprocessing` 在调度序上仍可能存在轻微差异。
- 本轮引入的 `initiative_gate` 对 `attack_signal` 较敏感，可能放大局面评估噪声，导致中盘模式决策不稳定。

### 14.5 下一步

1. 把 `initiative_gate` 从“连续值直连”改为“分段闸门”：
   - 仅在 `army_ratio` 和 `attack_signal` 同时超过高阈值时才放松反beam，其他区间回退到保守基线，减少噪声放大。
2. 在 `apply_mode_hysteresis` 增加“释放后冷却窗口”与“再入防守惩罚”：
   - 防止 release-confirm 后立刻被小波动拉回 defense。
3. 保持 `iter` 隔离与 `jobs=14`，用同一对手集复跑下一版（v12），优先目标：
   - `vs cpp_v2_beam >= 3/6`，`vs cpp_v1_current >= 3/6` 同时成立。

## 15. 本回合增量（2026-03-03，v12，隔离评测）

### 15.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_164938`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_164606`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v11 失败分析）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 15.2 算法级改动

新增版本：

- `cpp_v12_segmented_gate_cooldown`（`/www/ai_cpp/v12/ai_v12.cpp`，可执行 `/www/ai_cpp/v12/ai_v12`）

核心改动（相对 v11）：

1. `initiative_gate` 从连续值改为分段闸门：
   - 在 `compute_anti_beam_signal` 中改为 high/mid 两档触发（`1.0/0.5/0.0`），不再由连续乘积直接驱动。
   - 仅当兵力、攻击窗口、压力条件同时满足时才放松反 beam 告警，降低噪声放大。
2. 反 beam 告警放松幅度收敛：
   - `alert_effective` 改为“有限放松 + floor 兜底”，并叠加 `chain_risk` 抑制，避免在高链压局面下被过度放松。
3. defense 释放后加入再入冷却：
   - `apply_mode_hysteresis` 新增 `defense_reentry_cooldown`；
   - defense->balanced 后 2 回合内再入 defense 需要更高告警/压力阈值，降低“刚释放又回防”的震荡。
4. 评估一致性修正：
   - `evaluate_state` 的 anti-beam 信号改为使用真实 `attack_signal`（不再用 NaN 占位），与其他模块保持一致。
5. 进攻安全底线回调：
   - `score_state_robust` 的 `safety_floor` 提高并减弱对 `initiative_gate` 的下调幅度，抑制高估进攻收益。

### 15.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v12_segmented_gate_cooldown --exe /www/ai_cpp/v12/ai_v12 --src /www/ai_cpp/v12/ai_v12.cpp --notes "segmented anti-beam gate + defense reentry cooldown"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v12_segmented_gate_cooldown --opponents cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260312`

结果：

- 轮次：`eval_20260303_165456`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_165456_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_165456_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v12_segmented_gate_cooldown` 36/72（50.0%），Elo 1554.11（该轮第一）
- 分对手（按明细重算，v12 视角）：
  - vs `cpp_v11_dualgate_release_confirm`：2/6
  - vs `cpp_v10_antibeam_gate_release`：3/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：1/6
  - vs `cpp_v7_mode_switch`：4/6
  - vs `cpp_v6_adaptive_2ply`：3/6
  - vs `cpp_v5_counterfactual_2ply`：1/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：2/6
  - vs `cpp_v1_current`：2/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 与 v11 相比，`v12` 对 `v2_beam` 从 2/6 回升到 3/6，达到“至少不再劣势”的阶段性目标。
- 但关键目标“`v2` 与 `v1_current` 同时 >= 3/6”仍未达成（`v1_current` 仍 2/6）。
- 新问题：对 `v8` 与 `v5` 出现明显退化（均 1/6），说明分段闸门 + 冷却在某些中盘节奏下仍会错失反击窗口。
- 结论：本轮是“部分修复 + 仍失败”的可复现实验，不可推进为稳健候选。

### 15.4 风险

- 强对手样本仍是每组 6 局，统计波动仍较大。
- `thread_fallback` 与 `multiprocessing` 的时序差异仍在，建议后续在可用环境做一次进程池复核。
- 分段阈值对地图/节奏分布敏感，若阈值边界设定不稳，容易出现对部分策略族群（如 v5/v8）的系统性偏差。

### 15.5 下一步

1. 将 `initiative_gate` 改为“三段 + 连续过渡”：
   - 维持分段触发的稳健性，但在档位边界加入小范围线性过渡，减少阈值抖动。
2. 加入“对手族群自适应”轻量判别：
   - 用近几回合 `chain_pressure` 变化率与敌方推进密度估计 beam-like 概率，按族群调节 `alert_effective` 上限。
3. 保持 `iter` 隔离与 `jobs=14`，下一版（v13）继续同对手集复跑，硬目标仍为：
   - `vs cpp_v2_beam >= 3/6` 且 `vs cpp_v1_current >= 3/6`；
   - 同时避免 `vs cpp_v5_counterfactual_2ply` 低于 3/6。

## 16. 本回合增量（2026-03-03，v13，隔离评测）

### 16.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_165928`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_165456`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v12 结果）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 16.2 算法级改动

新增版本：

- `cpp_v13_beamlike_smoothgate`（`/www/ai_cpp/v13/ai_v13.cpp`，可执行 `/www/ai_cpp/v13/ai_v13`）

核心改动（相对 v12）：

1. `initiative_gate` 升级为“三段 + 连续过渡”：
   - 在 `compute_anti_beam_signal` 中由硬分段改为 `smoothstep` 过渡；
   - low/mid/high 三段通过连续混合映射到 `[0, 0.5, 1]`，降低阈值抖动。
2. 新增 `beam_like_prob` 估计并接入 anti-beam：
   - 新增 `compute_enemy_advance_density_to_main`（敌方向主将方向推进密度）；
   - 新增 `estimate_beam_like_probability`，融合 `chain_pressure/outer_defense/pressure_ratio/advance_density`；
   - `beam_like_prob` 进入 `compute_anti_beam_signal`，用于限制在 beam-like 对局中对反beam告警的放松幅度。
3. 滞回阈值改为 beam-like 自适应：
   - `apply_mode_hysteresis` 的紧急防守阈值随 `beam_like_prob` 与 `initiative_gate` 联动；
   - cooldown 强制回防增加 `beam_like_prob` 条件，避免被短期噪声触发。
4. 仲裁与进攻安全门同步 beam-like：
   - 规划器偏置（greedy/counter/beam）改为 `alert_effective + beam_like_prob + initiative_gate` 联动；
   - offense `safety_floor` 加入 `beam_like_prob`，降低对高风险局面的进攻高估。

### 16.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v13_beamlike_smoothgate --exe /www/ai_cpp/v13/ai_v13 --src /www/ai_cpp/v13/ai_v13.cpp --notes "smooth 3-stage initiative gate + beam-like adaptive alert"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v13_beamlike_smoothgate --opponents cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260313`

结果：

- 轮次：`eval_20260303_170719`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_170719_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_170719_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v13_beamlike_smoothgate` 40/78（51.3%），Elo 1579.20（该轮第一）
- 分对手（按明细重算，v13 视角）：
  - vs `cpp_v12_segmented_gate_cooldown`：2/6
  - vs `cpp_v11_dualgate_release_confirm`：3/6
  - vs `cpp_v10_antibeam_gate_release`：4/6
  - vs `cpp_v9_emergency_antibeam`：1/6
  - vs `cpp_v8_mode_hysteresis`：2/6
  - vs `cpp_v7_mode_switch`：2/6
  - vs `cpp_v6_adaptive_2ply`：2/6
  - vs `cpp_v5_counterfactual_2ply`：2/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：3/6
  - vs `cpp_v1_current`：4/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 关键目标出现改善：`v13` 同时达到 `vs cpp_v2_beam = 3/6` 与 `vs cpp_v1_current = 4/6`，较 v12 有实质提升。
- 但强对手覆盖仍不够稳健：对 `v9` 显著劣势（1/6），对 `v8/v7/v6/v5` 也低于 50%。
- 结论：本轮属于“关键指标达标但总体稳定性不足”的阶段性成功，仍不能作为收敛版本。

### 16.4 风险

- 每强对手仍为 6 局，小样本噪声仍然显著。
- `thread_fallback` 后端与进程池执行序可能存在轻微分布差异。
- 新增 `beam_like_prob` 可能对特定地图/节奏过拟合，出现“能打 v1/v2 但对 v5/v8/v9 回落”的结构性偏差。

### 16.5 下一步

1. 对 `beam_like_prob` 加“上限回撤”机制：
   - 当 `v5/v8` 型对手特征出现时，限制 alert 放松，防止过度进攻导致中盘交换亏损。
2. 增加 `v9` 定向对抗约束：
   - 在仲裁偏置中加入 `chain_pressure` 快速上升的惩罚项，优先修复 `vs v9` 的 1/6 问题。
3. 继续 `iter + jobs=14` 复跑 v14，同样对手集，下一轮硬目标：
   - 保持 `vs v2 >= 3/6`、`vs v1_current >= 3/6`；
   - 将 `vs v5/v8/v9` 至少提升到 `3/6`。

## 17. 本回合增量（2026-03-03，v14，隔离评测）

### 17.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_165928`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_170719`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v13 阶段性结果）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 17.2 算法级改动

新增版本：

- `cpp_v14_chainjump_reentry_guard`（`/www/ai_cpp/v14/ai_v14.cpp`，可执行 `/www/ai_cpp/v14/ai_v14`）

核心改动（相对 v13）：

1. 链压突增记忆接入滞回：
   - `apply_mode_hysteresis` 新增 `last_chain_pressure` / `last_beam_like_prob` 记忆；
   - 新增 `chain_jump` 与 `beam_like_jump` 紧急判据，当链压突增且 beam-like 概率上升时可快速切防。
2. 防守再入阈值自适应：
   - cooldown 期间的回防阈值按 `beam_like_prob`、`initiative_gate` 动态调整，减少误触发。
3. anti-beam 回撤保护：
   - 在 `compute_anti_beam_signal` 中增加“低 beam-like 限定回撤 + 保守下界”，避免过度放松造成中盘失稳。
4. 仲裁偏置加入突增惩罚：
   - 主流程在 `chain_pressure + advance_density` 上升时增加 `greedy` 偏置、降低 `counter/beam` 偏置，增强突发压力下的稳定性。

### 17.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v14_chainjump_reentry_guard --exe /www/ai_cpp/v14/ai_v14 --src /www/ai_cpp/v14/ai_v14.cpp --notes "chain-jump hysteresis memory + beam-like rollback guard"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v14_chainjump_reentry_guard --opponents cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260314`

结果：

- 轮次：`eval_20260303_171553`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_171553_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_171553_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v14_chainjump_reentry_guard` 50/84（59.5%），Elo 1608.13（该轮第一）
- 分对手（按明细重算，v14 视角）：
  - vs `cpp_v13_beamlike_smoothgate`：5/6
  - vs `cpp_v12_segmented_gate_cooldown`：5/6
  - vs `cpp_v11_dualgate_release_confirm`：3/6
  - vs `cpp_v10_antibeam_gate_release`：1/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：1/6
  - vs `cpp_v7_mode_switch`：5/6
  - vs `cpp_v6_adaptive_2ply`：0/6
  - vs `cpp_v5_counterfactual_2ply`：4/6
  - vs `cpp_v2_beam`：4/6
  - vs `cpp_v1_r2_baseline`：4/6
  - vs `cpp_v1_current`：3/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 正向结果：
  - 维持并强化了关键目标：`vs v2 = 4/6`，`vs v1_current = 3/6`；
  - `vs v9` 从 v13 的 1/6 回升到 3/6，说明链压突增记忆对该类对局有效；
  - `vs v5` 回升到 4/6。
- 负向结果（显著回归）：
  - `vs v6` 退化到 0/6；`vs v8` 与 `vs v10` 均 1/6。
- 结论：本轮属于“关键指标达标 + 局部大回归”的混合结果，不能直接作为收敛版本。

### 17.4 风险

- 强对手样本仍为每组 6 局，小样本方差显著。
- `thread_fallback` 与进程池在时序上仍可能有轻微差异。
- 当前链压突增逻辑可能对某些节奏（如 v6 的稳健推进）过度触发防守，导致主动权丢失。

### 17.5 下一步

1. 对 `chain_jump` 触发加入“节奏过滤”：
   - 仅当链压突增且 `advance_density` 连续两回合上行时才触发强切防，避免对稳态推进过拟合。
2. 增加 v6/v8 定向约束：
   - 在中压区间下调 `greedy` 额外偏置，恢复 `counter/beam` 的反击权重，优先修复 `vs v6/v8` 回归。
3. 继续 `iter + jobs=14` 复跑 v15，同对手集硬目标：
   - 保持 `vs v2 >= 3/6`、`vs v1_current >= 3/6`、`vs v9 >= 3/6`；
   - 将 `vs v6` 至少提升到 `3/6`。

## 18. 本回合增量（2026-03-03，v15，隔离评测）

### 18.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_171127`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_171553`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v14 混合结果）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 18.2 算法级改动

新增版本：

- `cpp_v15_tempo_filtered_chainjump`（`/www/ai_cpp/v15/ai_v15.cpp`，可执行 `/www/ai_cpp/v15/ai_v15`）

核心改动（相对 v14）：

1. `chain_jump` 触发加入节奏过滤：
   - 在 `apply_mode_hysteresis` 新增 `last_advance_density` 与 `density_rise_streak`；
   - 仅当推进密度连续上升（`density_rise_streak >= 2`）且链压突增时才触发 `chain_surge_emergency`，避免对稳态推进过拟合。
2. 非 beam-like 场景下的突增惩罚降权：
   - 对 `chain_surge` 偏置新增 `surge_guard`（由 `beam_like_prob` 控制）；
   - 低 beam-like 时不再强推 `greedy` 偏置，降低过度防守副作用。
3. 中压窗口反击恢复（定向修复 v6/v8）：
   - 在 `pressure_ratio` 中压区间且 `beam_like_prob` 不高时，按 `attack_signal + army_ratio` 提升 `counter/beam` 权重、下调 `greedy`，恢复中盘主动反击。

### 18.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v15_tempo_filtered_chainjump --exe /www/ai_cpp/v15/ai_v15 --src /www/ai_cpp/v15/ai_v15.cpp --notes "tempo-filtered chain-jump defense + mid-pressure counter recovery"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v15_tempo_filtered_chainjump --opponents cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260315`

结果：

- 轮次：`eval_20260303_172534`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_172534_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_172534_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v15_tempo_filtered_chainjump` 48/90（53.3%），Elo 1575.79（该轮第一）
- 分对手（按明细重算，v15 视角）：
  - vs `cpp_v14_chainjump_reentry_guard`：3/6
  - vs `cpp_v13_beamlike_smoothgate`：3/6
  - vs `cpp_v12_segmented_gate_cooldown`：3/6
  - vs `cpp_v11_dualgate_release_confirm`：3/6
  - vs `cpp_v10_antibeam_gate_release`：4/6
  - vs `cpp_v9_emergency_antibeam`：0/6
  - vs `cpp_v8_mode_hysteresis`：4/6
  - vs `cpp_v7_mode_switch`：1/6
  - vs `cpp_v6_adaptive_2ply`：4/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：2/6
  - vs `cpp_v1_current`：3/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 正向：
  - 本轮确实修复了 v14 的核心回归：`vs v6` 从 0/6 回升到 4/6，`vs v8` 从 1/6 回升到 4/6；
  - 保持关键底线：`vs v2 = 3/6`、`vs v1_current = 3/6`。
- 负向：
  - 出现新的严重退化：`vs v9 = 0/6`（从 v14 的 3/6 回落）；
  - 对 `v7` 也降到 1/6，且 `v1_r2` 仅 2/6。
- 结论：本轮为“修复 v6/v8 成功，但 v9 失守”的结构性失败，仍不可收敛。

### 18.4 风险

- 强对手每组仅 6 局，统计方差仍高。
- `thread_fallback` 与 `multiprocessing` 的时序差异仍可能影响边界对局分布。
- 新增的节奏过滤与中压恢复逻辑可能对 `v9` 型“高链压快攻”响应不足，导致延迟切防。

### 18.5 下一步

1. 做“v9 专用快切旁路”与“中压恢复互斥”：
   - 当 `chain_pressure` 和 `beam_like_prob` 同时高且短期跃升时，绕过中压恢复，直接强化 defense。
2. 引入双通道偏置：
   - 区分 `beam-like` 与 `non-beam` 两套偏置系数，避免一组参数同时服务 v6/v8/v9 导致此消彼长。
3. 继续 `iter + jobs=14` 复跑 v16，同对手集硬目标：
   - 保持 `vs v2 >= 3/6`、`vs v1_current >= 3/6`、`vs v6 >= 3/6`、`vs v8 >= 3/6`；
   - 把 `vs v9` 从 0/6 拉回至少 `3/6`。

## 19. 本回合增量（2026-03-03，v16，隔离评测）

### 19.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_172953`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_172534`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v15 结构性失败）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 19.2 算法级改动

新增版本：

- `cpp_v16_fastcut_dual_channel`（`/www/ai_cpp/v16/ai_v16.cpp`，可执行 `/www/ai_cpp/v16/ai_v16`）

核心改动（相对 v15）：

1. v9 快切旁路（fast-cut）：
   - 在 `apply_mode_hysteresis` 中新增 `v9_fast_cut` 条件；
   - 当 `beam_like_prob` 与 `chain_pressure` 同时较高且出现短期跃升时，绕过节奏过滤直接触发防守切换。
2. defense 置信度按 beam-like 放大：
   - `mode_switch_confidence` 的防守项从固定系数改为随 `beam_like_prob` 增强，提升高链压场景的防守响应速度。
3. release 条件收紧：
   - `soft_release_ready` 的 `beam_like_prob` 上限从 `0.52` 收紧到 `0.44`，减少高风险对局过早退防。
4. 双通道仲裁偏置：
   - 高 beam-like 场景增加额外防守偏置（提高 `greedy`、下调 `counter/beam`）；
   - 中压恢复仅允许在更低 beam-like 与更低告警区间触发，避免干扰对 v9 类对手的快切防。

### 19.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v16_fastcut_dual_channel --exe /www/ai_cpp/v16/ai_v16 --src /www/ai_cpp/v16/ai_v16.cpp --notes "v9 fast-cut bypass + dual-channel planner bias"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v16_fastcut_dual_channel --opponents cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260316`

结果：

- 轮次：`eval_20260303_173513`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_173513_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_173513_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v16_fastcut_dual_channel` 51/96（53.1%），Elo 1565.77（该轮第一）
- 分对手（按明细重算，v16 视角）：
  - vs `cpp_v15_tempo_filtered_chainjump`：4/6
  - vs `cpp_v14_chainjump_reentry_guard`：2/6
  - vs `cpp_v13_beamlike_smoothgate`：3/6
  - vs `cpp_v12_segmented_gate_cooldown`：4/6
  - vs `cpp_v11_dualgate_release_confirm`：6/6
  - vs `cpp_v10_antibeam_gate_release`：1/6
  - vs `cpp_v9_emergency_antibeam`：2/6
  - vs `cpp_v8_mode_hysteresis`：2/6
  - vs `cpp_v7_mode_switch`：3/6
  - vs `cpp_v6_adaptive_2ply`：2/6
  - vs `cpp_v5_counterfactual_2ply`：1/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：3/6
  - vs `cpp_v1_current`：3/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 与 v15 对比，`vs v9` 从 `0/6` 回升到 `2/6`，说明 fast-cut 方向有效但力度仍不足。
- 关键底线维持：`vs v2 = 3/6`、`vs v1_current = 3/6`。
- 新回归：`vs v5 = 1/6`、`vs v10 = 1/6`，且 `vs v6/v8` 回落到 `2/6`，表明双通道偏置仍存在耦合副作用。
- 结论：本轮是“局部修复但总体仍失败”的结果，尚不具备收敛性。

### 19.4 风险

- 强对手每组仅 6 局，小样本噪声仍高。
- `thread_fallback` 与进程池在时序上可能有轻微差异。
- v9 快切与中压恢复仍有参数冲突，可能在不同对手族群之间造成拉扯（修一端伤另一端）。

### 19.5 下一步

1. 引入“对手族群状态机”而非单阈值：
   - 对 `beam-like` 与 `non-beam` 维持独立短时状态（持续 2-3 回合）再切换，降低抖动。
2. 针对 `v5/v10` 增加中盘交换质量约束：
   - 在高 `counter` 候选中加入“次回合主将安全增量”门槛，避免冒进反击。
3. 继续 `iter + jobs=14` 跑 v17，同对手集硬目标：
   - 保持 `vs v2 >= 3/6`、`vs v1_current >= 3/6`；
   - 将 `vs v9` 提升到 `>=3/6`，并把 `vs v5/v10` 提升到 `>=3/6`。

## 20. 本回合增量（2026-03-03，v17，隔离评测）

### 20.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_174028`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_173513`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v16 局部修复但总体失败）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 20.2 算法级改动

新增版本：

- `cpp_v17_family_state_exchange_guard`（`/www/ai_cpp/v17/ai_v17.cpp`，可执行 `/www/ai_cpp/v17/ai_v17`）

核心改动（相对 v16）：

1. 对手族群短时状态机（beam-like / non-beam）接入滞回主流程：
   - 在 `apply_mode_hysteresis` 中新增 `beam_family_state` 与 `beam_family_hold_until`；
   - 族群切换需要满足进入条件并遵守 2-3 回合短持有，降低单回合阈值抖动。
2. 族群驱动的防守触发/释放阈值：
   - beam-like 族群降低 `emergency` 触发阈值并放宽 `v9_fast_cut` 入口；
   - defense release 在 beam-like 族群下使用更严格的 `alert/beam_like` 上限，减少过早退防。
3. 仲裁层双通道偏置改为“族群锁存”而非纯瞬时概率：
   - 在主仲裁段按 `beam_family_state` 对 `greedy/counter/beam` 增量修正，降低来回震荡。
4. 中盘交换质量门槛（首步主将安全增量）：
   - 新增 `compute_main_next_turn_safety` 与 `estimate_first_step_safety_delta`；
   - 对 `counter/beam` 候选在中盘窗口增加首步安全增量下限，不达标时施加惩罚或直接拒绝，抑制高风险换子/换地。

### 20.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v17_family_state_exchange_guard --exe /www/ai_cpp/v17/ai_v17 --src /www/ai_cpp/v17/ai_v17.cpp --notes "family-state hysteresis + first-step safety exchange guard"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v17_family_state_exchange_guard --opponents cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260317`

结果：

- 轮次：`eval_20260303_174729`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_174729_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_174729_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v17_family_state_exchange_guard` 52/102（51.0%），Elo 1570.02（该轮第一）
- 分对手（按 `matches` 重算，v17 视角）：
  - vs `cpp_v16_fastcut_dual_channel`：4/6
  - vs `cpp_v15_tempo_filtered_chainjump`：2/6
  - vs `cpp_v14_chainjump_reentry_guard`：2/6
  - vs `cpp_v13_beamlike_smoothgate`：4/6
  - vs `cpp_v12_segmented_gate_cooldown`：5/6
  - vs `cpp_v11_dualgate_release_confirm`：2/6
  - vs `cpp_v10_antibeam_gate_release`：2/6
  - vs `cpp_v9_emergency_antibeam`：2/6
  - vs `cpp_v8_mode_hysteresis`：2/6
  - vs `cpp_v7_mode_switch`：2/6
  - vs `cpp_v6_adaptive_2ply`：1/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：1/6
  - vs `cpp_v1_current`：5/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 正向：
  - 关键底线保持：`vs v2 = 3/6`，`vs v1_current = 5/6`；
  - `vs v5` 从 v16 的 `1/6` 修复到 `3/6`，说明“首步安全增量门槛”对中盘交换风险控制有效。
- 负向：
  - `vs v9` 与 `vs v10` 仍仅 `2/6`，未达上一轮目标 `>=3/6`；
  - 出现新退化：`vs v6 = 1/6`、`vs v1_r2 = 1/6`，说明当前门槛在部分稳健推进局里偏保守。
- 结论：本轮为“修复 v5 但未解决 v9/v10 且引入 v6/v1_r2 回归”的混合失败，仍不可收敛。

### 20.4 风险

- 强对手仍是每组 6 局，小样本波动较大。
- 本轮后端仍为 `thread_fallback`，与 `multiprocessing` 的时序差异可能影响边界局。
- 族群锁存 + 交换门槛存在叠加保守效应，可能在中压稳态对局（如 v6）抑制必要反击。

### 20.5 下一步

1. 将交换门槛改为“族群条件化阈值”而非统一阈值：
   - beam-like 族群保持严格门槛；non-beam 族群降低惩罚斜率，优先修复 `vs v6/v1_r2`。
2. 对 `v9/v10` 增加“快切后短时反打窗口”：
   - fast-cut 触发后 1-2 回合允许 `counter/beam` 小幅回升，避免长期锁死在过度防守。
3. 继续 `iter + jobs=14` 跑 v18，同对手集硬目标：
   - 保持 `vs v2 >= 3/6`、`vs v1_current >= 3/6`；
   - 将 `vs v9/v10` 提升到 `>=3/6`，并把 `vs v6` 拉回到 `>=3/6`。

## 21. 本回合增量（2026-03-03，v18，隔离评测）

### 21.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_174028`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_174729`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v17 混合失败）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 21.2 算法级改动

新增版本：

- `cpp_v18_conditional_exchange_rebound`（`/www/ai_cpp/v18/ai_v18.cpp`，可执行 `/www/ai_cpp/v18/ai_v18`）

核心改动（相对 v17）：

1. 交换质量门槛改为“族群条件化阈值”：
   - 在主仲裁中将 `exchange guard` 从单一阈值改为 beam-like / non-beam 两套 `safety_delta_floor`、惩罚斜率与拒绝阈值；
   - beam-like 维持严格风控，non-beam 放宽惩罚，降低对稳态推进局的过度抑制。
2. 引入“release 后短时反打窗口”（2 回合）：
   - 复用 `defense_reentry_cooldown` 作为反打窗口计数；
   - 当 defense 切回 balanced 且仍在 beam-like 族群时，短时上调 `counter/beam`、下调 `greedy`，避免 fast-cut 后长期锁死防守。
3. 反打窗口与交换门槛联动：
   - 在 rebound window 内，对 beam-like 族群适度下调门槛并减弱惩罚斜率，保留有限反击通道。
4. 释放路径稳定化：
   - defense release 时延长 `beam_family` 短持有，避免刚退防就发生族群抖动。

### 21.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v18_conditional_exchange_rebound --exe /www/ai_cpp/v18/ai_v18 --src /www/ai_cpp/v18/ai_v18.cpp --notes "family-conditional exchange guard + post-release rebound window"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v18_conditional_exchange_rebound --opponents cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260318`

结果：

- 轮次：`eval_20260303_175605`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_175605_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_175605_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v18_conditional_exchange_rebound` 55/108（50.9%），Elo 1604.26（该轮第一）
- 分对手（按 `matches` 重算，v18 视角）：
  - vs `cpp_v17_family_state_exchange_guard`：4/6
  - vs `cpp_v16_fastcut_dual_channel`：2/6
  - vs `cpp_v15_tempo_filtered_chainjump`：1/6
  - vs `cpp_v14_chainjump_reentry_guard`：3/6
  - vs `cpp_v13_beamlike_smoothgate`：4/6
  - vs `cpp_v12_segmented_gate_cooldown`：2/6
  - vs `cpp_v11_dualgate_release_confirm`：2/6
  - vs `cpp_v10_antibeam_gate_release`：1/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：2/6
  - vs `cpp_v7_mode_switch`：2/6
  - vs `cpp_v6_adaptive_2ply`：3/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：1/6
  - vs `cpp_v1_r2_baseline`：4/6
  - vs `cpp_v1_current`：6/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 正向：
  - 按上轮目标，`vs v9` 从 2/6 提升到 `3/6`，`vs v6` 从 1/6 回升到 `3/6`；
  - `vs v5` 维持 `3/6`，`vs v1_current` 提升到 `6/6`。
- 负向：
  - `vs v10` 降到 `1/6`，仍未达到 `>=3/6`；
  - 出现关键回归：`vs v2` 从 3/6 下滑到 `1/6`；
  - 对 `v15` 也仅 `1/6`，说明新门槛/反打窗口组合在部分节奏下仍失衡。
- 结论：本轮实现“v9/v6 修复”，但引入 `v2/v10` 新回归，属于结构性此消彼长，仍不可收敛。

### 21.4 风险

- 每对手仍是 6 局，小样本波动显著。
- `thread_fallback` 与进程池仍可能有边界时序差异。
- 当前“反打窗口”触发条件较宽，在 `v2` 这类对局中可能过早释放反击导致主将壳层失衡。

### 21.5 下一步

1. 将 rebound window 增加 `v2/v10` 抑制门：
   - 当 `beam_like_prob` 低但 `pressure_ratio` 未脱离中高压时，不触发反打加成。
2. 对 `v2` 增加“主将壳层底线”硬约束：
   - 若首步导致 `main_next_turn_safety` 低于族群底线，则无条件回退到更保守候选。
3. 继续 `iter + jobs=14` 跑 v19，同对手集硬目标：
   - 恢复 `vs v2 >= 3/6`；
   - 保持 `vs v9 >= 3/6`、`vs v6 >= 3/6`，并把 `vs v10` 提升到 `>=3/6`。

## 22. 本回合增量（2026-03-03，v19，隔离评测）

### 22.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_175311`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_175605`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v18 结构性此消彼长）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 22.2 算法级改动

新增版本：

- `cpp_v19_rebound_shellfloor_guard`（`/www/ai_cpp/v19/ai_v19.cpp`，可执行 `/www/ai_cpp/v19/ai_v19`）

核心改动（相对 v18）：

1. rebound 抑制门（定向抑制 v2/v10 式误触发）：
   - 在主仲裁新增 `rebound_suppressed`，当 `beam_like_prob` 偏低且 `pressure_ratio/chain_pressure` 仍处中高压时，禁用 `rebound_window` 反打加成；
   - 仅在风险结构允许时才启用 `rebound_window_active`，避免过早由 defense 退回反打。
2. 主将壳层底线硬约束（首步硬拒绝）：
   - 在候选比较前计算 `base_main_safety` 与族群条件化 `shell_safety_drop_cap`；
   - 对 `counter/beam` 候选，若首步后 `next_main_safety < shell_safety_floor`，直接拒绝该候选，不再仅做软惩罚。
3. 保留既有 exchange guard，并与新硬约束叠加：
   - 先过壳层底线硬门，再执行 `safety_delta_floor` 的软惩罚/拒绝，提高中盘稳定性。

### 22.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v19_rebound_shellfloor_guard --exe /www/ai_cpp/v19/ai_v19 --src /www/ai_cpp/v19/ai_v19.cpp --notes "rebound suppression gate + shell safety floor hard reject"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v19_rebound_shellfloor_guard --opponents cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260319`

结果：

- 轮次：`eval_20260303_180530`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_180530_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_180530_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v19_rebound_shellfloor_guard` 62/114（54.4%），Elo 1597.56（该轮第一）
- 分对手（按 `matches` 重算，v19 视角）：
  - vs `cpp_v18_conditional_exchange_rebound`：4/6
  - vs `cpp_v17_family_state_exchange_guard`：4/6
  - vs `cpp_v16_fastcut_dual_channel`：1/6
  - vs `cpp_v15_tempo_filtered_chainjump`：2/6
  - vs `cpp_v14_chainjump_reentry_guard`：5/6
  - vs `cpp_v13_beamlike_smoothgate`：3/6
  - vs `cpp_v12_segmented_gate_cooldown`：3/6
  - vs `cpp_v11_dualgate_release_confirm`：1/6
  - vs `cpp_v10_antibeam_gate_release`：3/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：2/6
  - vs `cpp_v7_mode_switch`：3/6
  - vs `cpp_v6_adaptive_2ply`：4/6
  - vs `cpp_v5_counterfactual_2ply`：1/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：5/6
  - vs `cpp_v1_current`：3/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 达成目标（相对 21.5）：
  - `vs v2` 从 1/6 回升到 `3/6`；
  - `vs v10` 从 1/6 回升到 `3/6`；
  - `vs v9` 维持 `3/6`；
  - `vs v6` 提升到 `4/6`。
- 新回归：
  - `vs v5 = 1/6`、`vs v16 = 1/6`、`vs v11 = 1/6`，说明壳层硬约束与抑制门组合对部分反击型对手仍偏保守。
- 结论：本轮是“关键硬目标达成，但出现新族群回归”的部分成功版本，可作为下一轮定向修复基线。

### 22.4 风险

- 每对手 6 局，统计方差仍高。
- `thread_fallback` 与进程池时序差异可能影响边界对局。
- 壳层硬约束若阈值过紧，可能压制 `v5/v16` 所需的机会反击。

### 22.5 下一步

1. 对 `v5/v16` 增加“受限反击通道”：
   - 在满足壳层底线后，允许 `counter` 候选获得小幅 bonus，避免被 `greedy` 长期压制。
2. 将壳层硬约束改为“双层门”而非单层硬拒绝：
   - 轻微越界先重罚、深度越界再拒绝，降低过度保守副作用。
3. 继续 `iter + jobs=14` 跑 v20，硬目标：
   - 保持 `vs v2/v9/v10/v6 >= 3/6`；
   - 将 `vs v5` 与 `vs v16` 至少提升到 `>=3/6`。

## 23. 本回合增量（2026-03-03，v20，隔离评测）

### 23.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_180132`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_180530`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v19 部分成功）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 23.2 算法级改动

新增版本：

- `cpp_v20_duallayer_counterlane`（`/www/ai_cpp/v20/ai_v20.cpp`，可执行 `/www/ai_cpp/v20/ai_v20`）

核心改动（相对 v19）：

1. 受限反击通道（定向修复 v5/v16）：
   - 在主仲裁新增 `counter_relief_window` 与 `counter_relief_bonus`；
   - 仅当满足壳层安全余量（`base_main_safety` 高于软底线）且不触发 rebound 抑制时，为 `counter`（及少量 `beam`）提供增益，避免被 `greedy` 长期压制。
2. 壳层约束改为双层门：
   - 将单一 `shell_safety_floor` 硬拒绝改为 `shell_soft_floor + shell_hard_floor`；
   - 轻微越界走软惩罚，深度越界才拒绝，实现“可控放行 + 稳定兜底”。
3. 保留 v19 的风险抑制框架：
   - 继续使用 `rebound_suppressed` 与 exchange guard，避免 v2/v10 场景下反打误触发。

### 23.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v20_duallayer_counterlane --exe /www/ai_cpp/v20/ai_v20 --src /www/ai_cpp/v20/ai_v20.cpp --notes "dual-layer shell gate + conditional counter-relief lane"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v20_duallayer_counterlane --opponents cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260320`

结果：

- 轮次：`eval_20260303_181530`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_181530_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_181530_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v20_duallayer_counterlane` 67/120（55.8%），Elo 1598.86（该轮第一）
- 分对手（按 `matches` 重算，v20 视角）：
  - vs `cpp_v19_rebound_shellfloor_guard`：2/6
  - vs `cpp_v18_conditional_exchange_rebound`：5/6
  - vs `cpp_v17_family_state_exchange_guard`：2/6
  - vs `cpp_v16_fastcut_dual_channel`：3/6
  - vs `cpp_v15_tempo_filtered_chainjump`：4/6
  - vs `cpp_v14_chainjump_reentry_guard`：3/6
  - vs `cpp_v13_beamlike_smoothgate`：2/6
  - vs `cpp_v12_segmented_gate_cooldown`：2/6
  - vs `cpp_v11_dualgate_release_confirm`：3/6
  - vs `cpp_v10_antibeam_gate_release`：4/6
  - vs `cpp_v9_emergency_antibeam`：2/6
  - vs `cpp_v8_mode_hysteresis`：3/6
  - vs `cpp_v7_mode_switch`：5/6
  - vs `cpp_v6_adaptive_2ply`：4/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：3/6
  - vs `cpp_v1_current`：2/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 正向：
  - v19 的主要回归点得到修复：`vs v5` 从 1/6 提升到 `3/6`，`vs v16` 从 1/6 提升到 `3/6`；
  - 关键底线保持：`vs v2 = 3/6`、`vs v10 = 4/6`、`vs v6 = 4/6`。
- 负向：
  - `vs v9` 从 3/6 回落到 `2/6`；
  - `vs v1_current` 下降到 2/6，且对 `v19/v17` 仅 2/6，说明双层门放松后对部分 beam-like 节奏抗性下降。
- 结论：本轮实现了“修复 v5/v16 并维持 v2/v10/v6”，但牺牲了 `v9` 稳定性，仍是结构性权衡版本。

### 23.4 风险

- 强对手每组 6 局，小样本噪声仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 双层门若软罚斜率不足，可能放过 v9 型快压局的高风险反击。

### 23.5 下一步

1. 对 v9 场景引入“族群特异硬化”：
   - 当 `beam_like_prob` 高且链压跳升时，临时收紧 `shell_hard_floor` 与 exchange guard 拒绝阈值。
2. 将 counter relief 细化为“对手族群白名单”：
   - 仅在 non-beam 中压窗口开放 full bonus，beam-like 场景降级为半幅 bonus。
3. 继续 `iter + jobs=14` 跑 v21，硬目标：
   - 保持 `vs v2/v10/v6/v5/v16 >= 3/6`；
   - 将 `vs v9` 拉回 `>=3/6`，并恢复 `vs v1_current >=3/6`。

## 24. 本回合增量（2026-03-03，v21，隔离评测）

### 24.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_181109`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_181530`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v20 结构性权衡）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 24.2 算法级改动

新增版本：

- `cpp_v21_beamharden_whitelist`（`/www/ai_cpp/v21/ai_v21.cpp`，可执行 `/www/ai_cpp/v21/ai_v21`）

核心改动（相对 v20）：

1. v9 场景“族群特异硬化”：
   - 新增 `beam_hardening_window`（高 `beam_like_prob` + 高链压/推进密度/告警）；
   - 在该窗口内收紧 `shell_hard_floor`、提高 `shell_soft_penalty_slope`，并加强 exchange guard（提高罚率、降低拒绝阈值）。
2. `counter_relief` 白名单化：
   - 将反击通道拆成 `counter_relief_full`（non-beam 中压）与 `counter_relief_half`（受限 beam-like）；
   - beam-like 高风险段不再开放 full bonus，目标是抑制 v9 型快压下的冒进反击。
3. 保留 v20 双层壳层门：
   - 继续使用 `shell_soft_floor + shell_hard_floor` 机制，避免完全回退到单阈值硬拒绝。

### 24.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v21_beamharden_whitelist --exe /www/ai_cpp/v21/ai_v21 --src /www/ai_cpp/v21/ai_v21.cpp --notes "beam-hardening shell tighten + counter-relief whitelist"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v21_beamharden_whitelist --opponents cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260321`

结果：

- 轮次：`eval_20260303_182545`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_182545_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_182545_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v21_beamharden_whitelist` 68/126（54.0%），Elo 1572.98（该轮第一）
- 分对手（按 `matches` 重算，v21 视角）：
  - vs `cpp_v20_duallayer_counterlane`：3/6
  - vs `cpp_v19_rebound_shellfloor_guard`：5/6
  - vs `cpp_v18_conditional_exchange_rebound`：2/6
  - vs `cpp_v17_family_state_exchange_guard`：2/6
  - vs `cpp_v16_fastcut_dual_channel`：4/6
  - vs `cpp_v15_tempo_filtered_chainjump`：4/6
  - vs `cpp_v14_chainjump_reentry_guard`：4/6
  - vs `cpp_v13_beamlike_smoothgate`：3/6
  - vs `cpp_v12_segmented_gate_cooldown`：3/6
  - vs `cpp_v11_dualgate_release_confirm`：5/6
  - vs `cpp_v10_antibeam_gate_release`：1/6
  - vs `cpp_v9_emergency_antibeam`：2/6
  - vs `cpp_v8_mode_hysteresis`：3/6
  - vs `cpp_v7_mode_switch`：3/6
  - vs `cpp_v6_adaptive_2ply`：2/6
  - vs `cpp_v5_counterfactual_2ply`：2/6
  - vs `cpp_v2_beam`：2/6
  - vs `cpp_v1_r2_baseline`：3/6
  - vs `cpp_v1_current`：3/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 正向：
  - `vs v1_current` 从 2/6 回升到 `3/6`；
  - 对 `v16/v15/v14/v11` 提升明显（分别 4/6、4/6、4/6、5/6）。
- 负向：
  - 本轮硬目标未达成：`vs v2 = 2/6`、`vs v10 = 1/6`、`vs v9 = 2/6`、`vs v6 = 2/6`、`vs v5 = 2/6`；
  - 相比 v20，出现明显回撤，说明“硬化 + 白名单”组合过度收紧，压制了中压反击质量。
- 结论：v21 是一次失败迭代，虽然修复了 `vs v1_current`，但破坏了 v20 的关键平衡点，不可作为收敛版本。

### 24.4 风险

- 每对手仅 6 局，小样本噪声仍显著。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 当前 `beam_hardening_window` 触发域可能过宽，导致 non-beam 中压也被“连带硬化”。

### 24.5 下一步

1. 将 hardening 缩窄为“突发快压”而非“持续高压”：
   - 增加链压跳升/密度跳升条件，避免稳态中压局被误伤。
2. 将 counter_relief 白名单改为“动态比例”而非 hard full/half：
   - 基于 `beam_like_prob` 连续映射加权，避免阈值抖动造成策略跳变。
3. 继续 `iter + jobs=14` 跑 v22，硬目标：
   - 恢复并保持 `vs v2/v10/v9/v6/v5 >= 3/6`；
   - 同时保持 `vs v1_current >= 3/6`。

## 25. 本回合增量（2026-03-03，v22，隔离评测）

### 25.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_183708`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_182545`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v21 失败分析与 v22 假设）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 25.2 算法级改动

新增版本：

- `cpp_v22_burst_harden_dynamic_relief`（`/www/ai_cpp/v22/ai_v22.cpp`，可执行 `/www/ai_cpp/v22/ai_v22`）

核心改动（相对 v21）：

1. hardening 从“持续高压触发”改为“突发快压强度”驱动：
- 在主仲裁引入短时记忆 `arb_prev_chain_pressure/arb_prev_advance_density`；
- 新增 `chain_jump`、`density_jump`、`burst_fast_pressure` 与 `hardening_intensity`（连续值）；
- 原 `beam_hardening_window` 的离散收紧，改为按 `hardening_intensity` 连续调节 `bias`、`guard_penalty_slope`、`shell` 双层门参数，缩小对稳态中压局的误伤。

2. counter relief 从 full/half 白名单改为连续加权：
- 删除 `counter_relief_full` / `counter_relief_half` 双阈值；
- 使用 `beam_relief_weight * alert_relief_weight * pressure_relief_weight * hardening_block` 形成 `relief_weight`；
- `counter_relief_bonus` 按 `relief_weight` 连续缩放，减少阈值抖动带来的策略跳变。

3. 保留 v21 的双层壳层门与 exchange guard 主框架：
- 仍采用 `shell_soft_floor + shell_hard_floor`；
- 在突发快压下做“连续加严”，而不是固定硬切换。

### 25.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v22_burst_harden_dynamic_relief --exe /www/ai_cpp/v22/ai_v22 --src /www/ai_cpp/v22/ai_v22.cpp --notes "burst-triggered hardening + continuous counter-relief weighting"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v22_burst_harden_dynamic_relief --opponents cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260323`

结果：

- 轮次：`eval_20260303_184803`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_184803_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_184803_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v22_burst_harden_dynamic_relief` 69/132（52.3%），Elo 1607.07（该轮第一）
- 分对手（按 `matches` 重算，v22 视角）：
  - vs `cpp_v21_beamharden_whitelist`：4/6
  - vs `cpp_v20_duallayer_counterlane`：2/6
  - vs `cpp_v19_rebound_shellfloor_guard`：2/6
  - vs `cpp_v18_conditional_exchange_rebound`：0/6
  - vs `cpp_v17_family_state_exchange_guard`：4/6
  - vs `cpp_v16_fastcut_dual_channel`：3/6
  - vs `cpp_v15_tempo_filtered_chainjump`：5/6
  - vs `cpp_v14_chainjump_reentry_guard`：1/6
  - vs `cpp_v13_beamlike_smoothgate`：2/6
  - vs `cpp_v12_segmented_gate_cooldown`：4/6
  - vs `cpp_v11_dualgate_release_confirm`：2/6
  - vs `cpp_v10_antibeam_gate_release`：4/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：3/6
  - vs `cpp_v7_mode_switch`：1/6
  - vs `cpp_v6_adaptive_2ply`：3/6
  - vs `cpp_v5_counterfactual_2ply`：4/6
  - vs `cpp_v2_beam`：2/6
  - vs `cpp_v1_r2_baseline`：3/6
  - vs `cpp_v1_current`：5/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 相对 24.5 目标：
  - 达标：`vs v10=4/6`、`vs v9=3/6`、`vs v6=3/6`、`vs v5=4/6`、`vs v1_current=5/6`；
  - 未达标：`vs v2=2/6`（唯一硬目标缺口）。
- 结构性回归：
  - 对 `v18` 出现 0/6，`v14` 与 `v7` 仅 1/6，说明“突发快压优先”的硬化与连续 relief 组合在部分节奏型对手上存在被针对窗口。
- 结论：
  - v22 相比 v21 明显修复了大部分关键目标，但尚未满足“`v2` 同步回升”的完整目标；可作为 v23 的改进基线，而非收敛版本。

### 25.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异可能影响边界局。
- 新增“突发快压记忆”依赖回合连续性；虽已在断档时重置，但跨局统计仍可能引入轻微行为漂移。

### 25.5 下一步

1. 定向修复 `vs v2`：
- 在 `beam_like_prob` 高但 jump 低的“持续压制段”增加低幅 hardening 底座，避免只在 jump 出现时才硬化。
2. 针对 `v18/v14/v7` 的回归：
- 给 `relief_weight` 增加“反节奏衰减项”（对低 jump + 高攻势长度连续段降权），减少被拖入不利交换。
3. 继续 `iter + jobs=14` 跑 v23，硬目标：
- 保持 `vs v10/v9/v6/v5/v1_current >= 3/6`；
- 将 `vs v2` 拉回 `>=3/6`；
- 同时把 `vs v18` 从 0/6 提升到至少 `>=2/6`。

## 26. 本回合增量（2026-03-03，v23，隔离评测）

### 26.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_184154`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_184803`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v22 部分成功）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 26.2 算法级改动

新增版本：

- `cpp_v23_sustainfloor_tempo_decay`（`/www/ai_cpp/v23/ai_v23.cpp`，可执行 `/www/ai_cpp/v23/ai_v23`）

核心改动（相对 v22）：

1. 持续压制 hardening 底座（定向修复 `vs v2`）：
- 在既有 `burst_fast_pressure` 之外新增 `sustained_pressure_floor`；
- 当 `beam_like_prob` 高、链压/推进密度高但 `jump` 低时，提供低幅 `sustained_hardening`；
- `hardening_intensity = max(burst_hardening, sustained_hardening)`，避免仅靠 jump 触发硬化。

2. relief 的反节奏衰减（定向修复 `v18/v14/v7` 回归）：
- 引入 `arb_low_jump_attack_streak`（低 jump + 高攻势连续段计数）；
- 在 `relief_weight` 增加 `anti_tempo_decay`，连续段越长、beam-like 越高则 relief 递减；
- 目标是降低被拖入不利交换的概率。

3. 保留 v22 主框架：
- 双层壳层门（`shell_soft_floor + shell_hard_floor`）与 exchange guard 仍保留；
- 仅在 hardening 与 relief 的触发结构上做增量修正。

### 26.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v23_sustainfloor_tempo_decay --exe /www/ai_cpp/v23/ai_v23 --src /www/ai_cpp/v23/ai_v23.cpp --notes "sustained-pressure hardening floor + low-jump tempo-decay relief"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v23_sustainfloor_tempo_decay --opponents cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260324`

结果：

- 轮次：`eval_20260303_185726`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_185726_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_185726_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v23_sustainfloor_tempo_decay` 68/138（49.3%），Elo 1551.35（该轮第2）
- 分对手（按 `matches` 重算，v23 视角）：
  - vs `cpp_v22_burst_harden_dynamic_relief`：4/6
  - vs `cpp_v21_beamharden_whitelist`：2/6
  - vs `cpp_v20_duallayer_counterlane`：3/6
  - vs `cpp_v19_rebound_shellfloor_guard`：0/6
  - vs `cpp_v18_conditional_exchange_rebound`：5/6
  - vs `cpp_v17_family_state_exchange_guard`：3/6
  - vs `cpp_v16_fastcut_dual_channel`：3/6
  - vs `cpp_v15_tempo_filtered_chainjump`：2/6
  - vs `cpp_v14_chainjump_reentry_guard`：1/6
  - vs `cpp_v13_beamlike_smoothgate`：3/6
  - vs `cpp_v12_segmented_gate_cooldown`：3/6
  - vs `cpp_v11_dualgate_release_confirm`：4/6
  - vs `cpp_v10_antibeam_gate_release`：3/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：3/6
  - vs `cpp_v7_mode_switch`：3/6
  - vs `cpp_v6_adaptive_2ply`：2/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：2/6
  - vs `cpp_v1_r2_baseline`：4/6
  - vs `cpp_v1_current`：0/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 正向：
  - 25.5 的次目标里，`vs v18` 从 0/6 提升到 `5/6`，`vs v7` 从 1/6 提升到 `3/6`；
  - `vs v10/v9/v5` 保持在 `3/6` 或以上。
- 负向：
  - 主硬目标仍未达成：`vs v2` 继续 `2/6`；
  - 新增重大回归：`vs v1_current=0/6`、`vs v19=0/6`，且 `vs v6=2/6`、`vs v14=1/6`。
- 结论：
  - v23 的“持续压制 hardening + 反节奏衰减”过度偏向特定对手形态，导致泛化显著恶化；本轮为失败迭代，不可作为收敛版本。

### 26.4 风险

- 每对手 6 局，小样本噪声仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- `arb_low_jump_attack_streak` 为跨回合状态，参数过强时可能在非目标场景长期抑制 counter relief。

### 26.5 下一步

1. 对 `v1_current/v19` 回归做“保护上限”：
- 为 `anti_tempo_decay` 增加下限保护与触发白名单，避免全局过度削弱 relief。
2. 对 `v2` 继续定向：
- 将 `sustained_hardening` 从 `max` 改为“低幅叠加 + 安全门”，避免压制正常反打链路。
3. 继续 `iter + jobs=14` 跑 v24，硬目标：
- 保持 `vs v10/v9/v5 >=3/6`；
- 拉回 `vs v1_current/v19 >=3/6`；
- 同时将 `vs v2` 提升到 `>=3/6`。

## 27. 本回合增量（2026-03-03，v24，隔离评测）

### 27.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_185453`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_185726`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v23 失败分析）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 27.2 算法级改动

新增版本：

- `cpp_v24_guarded_additive_sustain`（`/www/ai_cpp/v24/ai_v24.cpp`，可执行 `/www/ai_cpp/v24/ai_v24`）

核心改动（相对 v23）：

1. `sustained_hardening` 改为低幅叠加 + 安全门：
- 将 `hardening_intensity = max(burst_hardening, sustained_hardening)` 改为 `burst_hardening + sustained_hardening_add`；
- `sustained_hardening_add` 由 `sustained_loss_gate` 约束（低 initiative 且高 pressure 才生效）；
- 避免 v23 中 sustained 分量过强导致全局压制反打链路。

2. `anti_tempo_decay` 增加触发白名单与下限保护：
- 仅在 `low_jump_high_attack + 高链压 + 高 pressure + beam-like 区间 + 低 initiative` 下触发衰减；
- 下限由 `0.28` 提升到 `0.55`，防止 relief 被长期过度削弱；
- 同时将 `hardening_block` 下限抬升（`0.34`），减少极端压制。

3. 保留 v23 的突发/持续信号框架与双层壳层门：
- 继续使用 jump 与 sustained 信号，但把“防守加严”控制在更窄、更可恢复的区间。

### 27.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v24_guarded_additive_sustain --exe /www/ai_cpp/v24/ai_v24 --src /www/ai_cpp/v24/ai_v24.cpp --notes "additive sustained hardening + whitelist tempo-decay with floor"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v24_guarded_additive_sustain --opponents cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260325`

结果：

- 轮次：`eval_20260303_190743`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_190743_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_190743_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v24_guarded_additive_sustain` 76/144（52.8%），Elo 1563.14（该轮第一）
- 分对手（按 `matches` 重算，v24 视角）：
  - vs `cpp_v23_sustainfloor_tempo_decay`：3/6
  - vs `cpp_v22_burst_harden_dynamic_relief`：2/6
  - vs `cpp_v21_beamharden_whitelist`：4/6
  - vs `cpp_v20_duallayer_counterlane`：1/6
  - vs `cpp_v19_rebound_shellfloor_guard`：5/6
  - vs `cpp_v18_conditional_exchange_rebound`：4/6
  - vs `cpp_v17_family_state_exchange_guard`：3/6
  - vs `cpp_v16_fastcut_dual_channel`：3/6
  - vs `cpp_v15_tempo_filtered_chainjump`：3/6
  - vs `cpp_v14_chainjump_reentry_guard`：4/6
  - vs `cpp_v13_beamlike_smoothgate`：3/6
  - vs `cpp_v12_segmented_gate_cooldown`：3/6
  - vs `cpp_v11_dualgate_release_confirm`：3/6
  - vs `cpp_v10_antibeam_gate_release`：2/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：3/6
  - vs `cpp_v7_mode_switch`：3/6
  - vs `cpp_v6_adaptive_2ply`：4/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v2_beam`：2/6
  - vs `cpp_v1_r2_baseline`：1/6
  - vs `cpp_v1_current`：2/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 相对 26.5 目标：
  - 达标：`vs v9=3/6`、`vs v5=3/6`、`vs v19=5/6`；
  - 未达标：`vs v10=2/6`、`vs v1_current=2/6`、`vs v2=2/6`。
- 对比 v23：
  - 明显修复了 `v19`（0/6 -> 5/6）与 `v18`（5/6 保持高位）；
  - 但 `v2` 依旧卡在 2/6，且 `v1_current` 仅部分回升（0/6 -> 2/6）。
- 结论：
  - v24 相比 v23 泛化更稳，但核心硬目标（`v2` 与 `v1_current`）仍未达线；属于“部分修复、未收敛”版本。

### 27.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 当前白名单虽然降低了过抑制，但在 `v10/v2` 场景可能仍存在“hardening 不足、反打释放偏早”的窗口。

### 27.5 下一步

1. 针对 `v2/v10` 增加“低幅常驻硬化底座”：
- 在 beam-like 高且 pressure 高时给 `hardening_intensity` 增加小常数底座，但保持 relief 通道不断流。
2. 为 `v1_current` 增加“反守转换保护”：
- 在 `v1_current` 风格的中压对抗段（非极端 beam-like）提高 counter 候选的安全补偿，避免过早保守。
3. 继续 `iter + jobs=14` 跑 v25，硬目标：
- `vs v2/v10/v1_current >= 3/6`；
- 保持 `vs v9/v5/v19 >= 3/6`。

## 28. 本回合增量（2026-03-03，v25，隔离评测）

### 28.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_190442`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_190743`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v24 部分修复）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 28.2 算法级改动

新增版本：

- `cpp_v25_floorplus_transition_guard`（`/www/ai_cpp/v25/ai_v25.cpp`，可执行 `/www/ai_cpp/v25/ai_v25`）

核心改动（相对 v24）：

1. `v2/v10` 低幅常驻硬化底座：
- 新增 `persistent_hardening_floor`，在高 beam-like + 高 pressure + 高链压且低 initiative 的持续压制段提供小幅 hardening；
- `hardening_intensity` 从 `burst + sustained_add` 改为 `burst + sustained_add + persistent_floor`。

2. `v1_current` 反守转换保护：
- 新增 `counter_transition_protect_window`（中压、非极端 beam-like、低 jump、非防守态）；
- 在该窗口下给 counter 增加 `counter_transition_bonus`，目标是减少过早保守。

3. 保留 v24 的白名单衰减框架：
- `anti_tempo_decay` 仍受触发白名单与下限保护约束，避免 v23 的全局过抑制。

### 28.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v25_floorplus_transition_guard --exe /www/ai_cpp/v25/ai_v25 --src /www/ai_cpp/v25/ai_v25.cpp --notes "persistent hardening floor + counter transition protection"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v25_floorplus_transition_guard --opponents cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260326`

结果：

- 轮次：`eval_20260303_191758`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_191758_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_191758_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v25_floorplus_transition_guard` 76/150（50.7%），Elo 1521.87（该轮第7）
- 分对手（按 `matches` 重算，v25 视角）：
  - vs `cpp_v24_guarded_additive_sustain`：3/6
  - vs `cpp_v23_sustainfloor_tempo_decay`：3/6
  - vs `cpp_v22_burst_harden_dynamic_relief`：4/6
  - vs `cpp_v21_beamharden_whitelist`：3/6
  - vs `cpp_v20_duallayer_counterlane`：3/6
  - vs `cpp_v19_rebound_shellfloor_guard`：5/6
  - vs `cpp_v18_conditional_exchange_rebound`：3/6
  - vs `cpp_v17_family_state_exchange_guard`：4/6
  - vs `cpp_v16_fastcut_dual_channel`：2/6
  - vs `cpp_v15_tempo_filtered_chainjump`：4/6
  - vs `cpp_v14_chainjump_reentry_guard`：3/6
  - vs `cpp_v13_beamlike_smoothgate`：2/6
  - vs `cpp_v12_segmented_gate_cooldown`：5/6
  - vs `cpp_v11_dualgate_release_confirm`：2/6
  - vs `cpp_v10_antibeam_gate_release`：3/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：3/6
  - vs `cpp_v7_mode_switch`：3/6
  - vs `cpp_v6_adaptive_2ply`：1/6
  - vs `cpp_v5_counterfactual_2ply`：0/6
  - vs `cpp_v2_beam`：0/6
  - vs `cpp_v1_r2_baseline`：4/6
  - vs `cpp_v1_current`：1/6
  - vs `greedy` / `random_safe`：各 6/6

解读（失败分析）：

- 正向：
  - `vs v19=5/6`、`vs v12=5/6`、`vs v15=4/6`，说明局部防守硬化在部分族群有效。
- 负向：
  - 核心目标失败：`vs v2=0/6`、`vs v1_current=1/6`，`vs v10` 仅 `3/6`（未提升到更稳）；
  - 新增回归：`vs v5=0/6`、`vs v6=1/6`，显示常驻硬化底座对中盘反打链路抑制过强。
- 结论：
  - v25 是明显失败迭代；“常驻硬化 + 转换补偿”组合出现方向性过拟合，损害主线对抗能力，不可作为后续基线。

### 28.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 当前 `persistent_hardening_floor` 触发域仍偏宽，可能在非目标局面持续抑制 counter 机会。

### 28.5 下一步

1. 回退常驻硬化为“脉冲硬化”而非连续底座：
- 仅在链压/推进密度双跳升时短时提升 hardening，避免长期压制中盘反打。
2. 将 `counter_transition_bonus` 从“固定加分”改为“安全差值驱动”：
- 只在 `next_main_safety` 不低于软底线时给 bonus，避免危险反打。
3. 继续 `iter + jobs=14` 跑 v26，硬目标：
- 恢复 `vs v2/v1_current/v6/v5 >= 3/6`；
- 保持 `vs v9/v10/v19 >= 3/6`。

## 29. 本回合增量（2026-03-03，v26，隔离评测）

### 29.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_192430`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_191758`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v25 失败迭代）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 29.2 算法级改动

新增版本：

- `cpp_v26_pulse_harden_safety_delta`（`/www/ai_cpp/v26/ai_v26.cpp`，可执行 `/www/ai_cpp/v26/ai_v26`）

核心改动（相对 v25）：

1. 回退“常驻硬化底座”为“脉冲硬化”：
- 删除 `persistent_hardening_floor` 持续加成；
- 新增 `dual_jump_pulse + pulse_hardening_boost`，仅在链压与推进密度双跳升时短时增强 hardening；
- 降低对中盘反打链路的持续压制。

2. `counter_transition_bonus` 改为安全差值驱动：
- 将固定加分改为 `counter_transition_bonus_cap`；
- 在候选评估中统一计算 `safety_delta/next_main_safety`，仅当 `next_main_safety >= shell_soft_floor` 时按 `safety_headroom + delta_quality` 释放 bonus；
- 对不满足软底线的候选不再给转换补偿。

3. 保留 v24/v25 其余稳定结构：
- 双层壳层门、exchange guard 与 relief 白名单仍保留；
- 仅对“硬化触发方式”和“转换补偿释放条件”做结构化修正。

### 29.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v26_pulse_harden_safety_delta --exe /www/ai_cpp/v26/ai_v26 --src /www/ai_cpp/v26/ai_v26.cpp --notes "dual-jump pulse hardening + safety-delta driven transition bonus"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v26_pulse_harden_safety_delta --opponents cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260327`

结果：

- 轮次：`eval_20260303_193648`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_193648_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_193648_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v26_pulse_harden_safety_delta` 88/156（56.4%），Elo 1598.31（该轮第一）
- 分对手（按 `matches` 重算，v26 视角）：
  - vs `cpp_v25_floorplus_transition_guard`：2/6
  - vs `cpp_v24_guarded_additive_sustain`：2/6
  - vs `cpp_v23_sustainfloor_tempo_decay`：3/6
  - vs `cpp_v22_burst_harden_dynamic_relief`：4/6
  - vs `cpp_v21_beamharden_whitelist`：2/6
  - vs `cpp_v20_duallayer_counterlane`：5/6
  - vs `cpp_v19_rebound_shellfloor_guard`：5/6
  - vs `cpp_v18_conditional_exchange_rebound`：3/6
  - vs `cpp_v17_family_state_exchange_guard`：3/6
  - vs `cpp_v16_fastcut_dual_channel`：4/6
  - vs `cpp_v15_tempo_filtered_chainjump`：4/6
  - vs `cpp_v14_chainjump_reentry_guard`：2/6
  - vs `cpp_v13_beamlike_smoothgate`：6/6
  - vs `cpp_v12_segmented_gate_cooldown`：3/6
  - vs `cpp_v11_dualgate_release_confirm`：1/6
  - vs `cpp_v10_antibeam_gate_release`：4/6
  - vs `cpp_v9_emergency_antibeam`：4/6
  - vs `cpp_v8_mode_hysteresis`：3/6
  - vs `cpp_v7_mode_switch`：2/6
  - vs `cpp_v6_adaptive_2ply`：2/6
  - vs `cpp_v5_counterfactual_2ply`：2/6
  - vs `cpp_v2_beam`：4/6
  - vs `cpp_v1_r2_baseline`：3/6
  - vs `cpp_v1_current`：3/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 相对 28.5 目标：
  - 达标：`vs v2=4/6`、`vs v1_current=3/6`，且 `vs v9=4/6`、`vs v10=4/6`、`vs v19=5/6` 保持在目标线以上；
  - 未达标：`vs v6=2/6`、`vs v5=2/6`。
- 对比 v25：
  - 主缺口显著修复：`vs v2` 从 0/6 回升到 4/6，`vs v1_current` 从 1/6 回升到 3/6；
  - 但 `v5/v6` 仍未恢复，说明“脉冲硬化 + 安全差值补偿”仍会在部分 2ply 强反打族群中压低 counter 质量。
- 结论：
  - v26 是明显优于 v25 的修复版本，但仍为“部分达标”；后续应定向修复 `v5/v6`。

### 29.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 当前 `counter_transition_bonus_cap` 在 `v5/v6` 场景可能被 safety gate 过早裁剪，导致中压反打不足。

### 29.5 下一步

1. 针对 `v5/v6` 增加“中压反打专用通道”：
- 在 `beam_like_prob` 中低区间且 `initiative_gate` 较高时，为 counter 提供小幅额外权重。
2. 对 `v11` 的 1/6 回归做门限修正：
- 缩小 `transition_bonus` 对低 `next_main_safety` 候选的贡献区间，减少被反制。
3. 继续 `iter + jobs=14` 跑 v27，硬目标：
- 保持 `vs v2/v1_current/v9/v10/v19 >= 3/6`；
- 将 `vs v5/v6` 拉回 `>=3/6`。

## 30. 本回合增量（2026-03-03，v27，隔离评测）

### 30.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_192430`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_193648`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v26 部分达标）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 30.2 算法级改动

新增版本：

- `cpp_v27_midpressure_counterlane`（`/www/ai_cpp/v27/ai_v27.cpp`，可执行 `/www/ai_cpp/v27/ai_v27`）

核心改动（相对 v26）：

1. non-beam 中压反打松弛（定向修复 `v5/v6`）：
- 新增 `non_beam_counter_relax_window`（中压、非 beam-like、高 initiative、低 hardening）；
- 在该窗口下放宽 guard：下调 `safety_delta_floor`、下调 `guard_penalty_slope`、上调 `guard_reject_deficit`，减少过度保守拒绝。

2. 中压反打专用 bonus 通道：
- 新增 `counter_midpressure_lane_window` 与 `counter_midpressure_bonus_cap`；
- 在非 beam-like 中压且 initiative/attack 足够时给 counter 增量 bonus。

3. 延续 v26 安全差值驱动机制：
- counter bonus 仍通过 `next_main_safety >= shell_soft_floor` 的条件释放，维持安全边界。

### 30.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v27_midpressure_counterlane --exe /www/ai_cpp/v27/ai_v27 --src /www/ai_cpp/v27/ai_v27.cpp --notes "non-beam counter relax + midpressure counter lane bonus"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v27_midpressure_counterlane --opponents cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260328`

结果：

- 轮次：`eval_20260303_194809`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_194809_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_194809_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v27_midpressure_counterlane` 93/162（57.4%），Elo 1627.11（该轮第一）
- 分对手（按 `matches` 重算，v27 视角）：
  - vs `cpp_v26_pulse_harden_safety_delta`：3/6
  - vs `cpp_v25_floorplus_transition_guard`：1/6
  - vs `cpp_v24_guarded_additive_sustain`：2/6
  - vs `cpp_v23_sustainfloor_tempo_decay`：5/6
  - vs `cpp_v22_burst_harden_dynamic_relief`：1/6
  - vs `cpp_v21_beamharden_whitelist`：4/6
  - vs `cpp_v20_duallayer_counterlane`：4/6
  - vs `cpp_v19_rebound_shellfloor_guard`：3/6
  - vs `cpp_v18_conditional_exchange_rebound`：2/6
  - vs `cpp_v17_family_state_exchange_guard`：4/6
  - vs `cpp_v16_fastcut_dual_channel`：5/6
  - vs `cpp_v15_tempo_filtered_chainjump`：4/6
  - vs `cpp_v14_chainjump_reentry_guard`：5/6
  - vs `cpp_v13_beamlike_smoothgate`：4/6
  - vs `cpp_v12_segmented_gate_cooldown`：2/6
  - vs `cpp_v11_dualgate_release_confirm`：2/6
  - vs `cpp_v10_antibeam_gate_release`：3/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v8_mode_hysteresis`：4/6
  - vs `cpp_v7_mode_switch`：3/6
  - vs `cpp_v6_adaptive_2ply`：2/6
  - vs `cpp_v5_counterfactual_2ply`：5/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：4/6
  - vs `cpp_v1_current`：3/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 相对 29.5 目标：
  - 达标：`vs v2=3/6`、`vs v1_current=3/6`、`vs v9=3/6`、`vs v10=3/6`、`vs v19=3/6`，`vs v5=5/6`；
  - 未达标：`vs v6=2/6`（唯一硬目标缺口）。
- 对比 v26：
  - `v5` 从 2/6 提升到 `5/6`，中压反打通道方向有效；
  - `v6` 仍 2/6，说明当前反打松弛对 v6 的 2ply 形态仍不足。
- 结论：
  - v27 达成“主要目标+关键修复”，但尚未完成 `v6` 收敛；属于可继续精修的强基线版本。

### 30.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 新增中压反打通道后，对 `v22/v25` 类风格出现回落（1/6），可能存在族群间 trade-off。

### 30.5 下一步

1. 定向修复 `v6`：
- 在 `v6` 风格高 initiative + 中压窗口下，增加“2ply 反制优先”权重，仅对 counter 序列有效。
2. 限制族群回落：
- 对 `v22/v25` 场景添加轻量回弹保护，避免中压通道在其高压段过度前压。
3. 继续 `iter + jobs=14` 跑 v28，硬目标：
- 保持 `vs v2/v1_current/v9/v10/v19/v5 >= 3/6`；
- 将 `vs v6` 拉回 `>=3/6`。

## 31. 本回合增量（2026-03-03，v28，隔离评测）

### 31.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_194427`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_194809`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v27 强基线）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 31.2 算法级改动

新增版本：

- `cpp_v28_v6lane_rebound_guard`（`/www/ai_cpp/v28/ai_v28.cpp`，可执行 `/www/ai_cpp/v28/ai_v28`）

核心改动（相对 v27）：

1. 高压回弹保护（限制族群回落）：
- 新增 `high_pressure_counterline_guard`（高 beam-like + 高 pressure + 高链压 + 跳升/硬化）；
- 在该 guard 下禁用 `non_beam_counter_relax_window` 与 `counter_midpressure_lane_window`，抑制中压通道在高压段过度前压。

2. v6 专用 2ply 反制通道：
- 新增 `counter_v6_2ply_window` 与 `counter_v6_2ply_bonus_cap`；
- 仅在高 initiative、中压、非极端 beam-like、适中链压窗口开放，定向提升对 v6 类 2ply 反制能力。

3. 保留 v27 的安全差值释放机制：
- counter bonus 仍需通过 `next_main_safety >= shell_soft_floor` 才释放，维持风控底线。

### 31.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v28_v6lane_rebound_guard --exe /www/ai_cpp/v28/ai_v28 --src /www/ai_cpp/v28/ai_v28.cpp --notes "v6 2ply lane bonus + high-pressure counterline guard"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v28_v6lane_rebound_guard --opponents cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260329`

结果：

- 轮次：`eval_20260303_195926`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_195926_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_195926_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v28_v6lane_rebound_guard` 94/168（56.0%），Elo 1645.50（该轮第一）
- 分对手（按 `matches` 重算，v28 视角）：
  - vs `cpp_v27_midpressure_counterlane`：1/6
  - vs `cpp_v26_pulse_harden_safety_delta`：0/6
  - vs `cpp_v25_floorplus_transition_guard`：2/6
  - vs `cpp_v24_guarded_additive_sustain`：4/6
  - vs `cpp_v23_sustainfloor_tempo_decay`：2/6
  - vs `cpp_v22_burst_harden_dynamic_relief`：4/6
  - vs `cpp_v21_beamharden_whitelist`：2/6
  - vs `cpp_v20_duallayer_counterlane`：3/6
  - vs `cpp_v19_rebound_shellfloor_guard`：2/6
  - vs `cpp_v18_conditional_exchange_rebound`：5/6
  - vs `cpp_v17_family_state_exchange_guard`：4/6
  - vs `cpp_v16_fastcut_dual_channel`：4/6
  - vs `cpp_v15_tempo_filtered_chainjump`：4/6
  - vs `cpp_v14_chainjump_reentry_guard`：4/6
  - vs `cpp_v13_beamlike_smoothgate`：1/6
  - vs `cpp_v12_segmented_gate_cooldown`：1/6
  - vs `cpp_v11_dualgate_release_confirm`：2/6
  - vs `cpp_v10_antibeam_gate_release`：5/6
  - vs `cpp_v9_emergency_antibeam`：5/6
  - vs `cpp_v8_mode_hysteresis`：5/6
  - vs `cpp_v7_mode_switch`：4/6
  - vs `cpp_v6_adaptive_2ply`：5/6
  - vs `cpp_v5_counterfactual_2ply`：4/6
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_r2_baseline`：2/6
  - vs `cpp_v1_current`：4/6
  - vs `greedy` / `random_safe`：各 6/6

解读：

- 相对 30.5 目标：
  - 达标：`vs v6=5/6`，并保持 `vs v2=3/6`、`vs v1_current=4/6`、`vs v5=4/6`、`vs v9=5/6`、`vs v10=5/6`；
  - 未达标：`vs v19=2/6`（回落到目标线下）。
- 结论：
  - v28 成功修复了 v6，但牺牲了 v19 稳定性；属于“单点修复成功、另一关键点回归”的权衡版本。

### 31.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- `high_pressure_counterline_guard` 可能在 v19 样式局中触发过早，压制必要反打导致 2/6 回落。

### 31.5 下一步

1. 对 v19 做“分层 guard”而非一刀切：
- 将 `high_pressure_counterline_guard` 拆为强/弱两层，弱层只削减 bonus，不完全关窗。
2. 对 v26/v27 回落对手加保底：
- 为关键旧强对手设置最小反打释放率，避免新窗全部关死。
3. 继续 `iter + jobs=14` 跑 v29，硬目标：
- 保持 `vs v2/v1_current/v5/v6/v9/v10 >= 3/6`；
- 将 `vs v19` 拉回 `>=3/6`。

## 32. 本回合增量（2026-03-03，v29，隔离评测）

### 32.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_200540`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_195926`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v28）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 32.2 算法级改动

新增版本：

- `cpp_v29_layered_counterline_rebound`（`/www/ai_cpp/v29/ai_v29.cpp`，可执行 `/www/ai_cpp/v29/ai_v29`）

核心改动（相对 v28）：

1. 高压 counterline guard 分层（从“一刀切”改为 strong/weak）：
- 新增 `high_pressure_counterline_strong_guard` 与 `high_pressure_counterline_weak_guard`；
- strong 层仍保守拦截（用于高 beam-like + 高 pressure + 高 jump/hardening 场景）；
- weak 层不再直接关窗，而是通过 `counterline_relax_scale`、`counterline_transition_scale` 对 bonus 做降权。

2. non-beam relax 改为“弱层降幅、强层拦截”：
- `non_beam_counter_relax_window` 仅在 strong guard 下禁用；
- weak guard 下保留窗口，但只做轻度放松（更小 `safety_delta_floor/guard_penalty_slope/guard_reject_deficit` 调整幅度）。

3. 新增 v19 回弹通道：
- 新增 `counter_v19_rebound_window` 与 `counter_v19_rebound_bonus_cap`；
- 在中高压、非防守、非 strong guard、且 jump 稳定时，给 counter 过渡 bonus 增量，目标是修复 v28 对 v19 的回落。

4. 保留 v6 专用 2ply 通道，但在 weak guard 下轻度降权：
- `counter_v6_2ply_bonus_cap` 在 weak guard 场景乘 `0.76`，降低过激反打。

### 32.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v29_layered_counterline_rebound --exe /www/ai_cpp/v29/ai_v29 --src /www/ai_cpp/v29/ai_v29.cpp --notes "layered counterline guard + v19 rebound lane"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v29_layered_counterline_rebound --opponents cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260330`

结果：

- 轮次：`eval_20260303_201559`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_201559_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_201559_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v29_layered_counterline_rebound` 96/174（55.2%），Elo 1658.40（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v29 视角）：
  - vs `cpp_v2_beam`：2/6
  - vs `cpp_v1_current`：5/6
  - vs `cpp_v5_counterfactual_2ply`：4/6
  - vs `cpp_v6_adaptive_2ply`：3/6
  - vs `cpp_v9_emergency_antibeam`：5/6
  - vs `cpp_v10_antibeam_gate_release`：4/6
  - vs `cpp_v19_rebound_shellfloor_guard`：4/6
  - vs `cpp_v28_v6lane_rebound_guard`：1/6
  - vs `cpp_v27_midpressure_counterlane`：1/6
  - vs `greedy/random_safe`：各 6/6

解读：

- 相对 31.5 目标：
  - 达标：`v1_current=5/6`、`v5=4/6`、`v6=3/6`、`v9=5/6`、`v10=4/6`、`v19=4/6`；
  - 未达标：`v2=2/6`。
- 对比 v28：
  - `v19` 从 2/6 修复到 4/6，分层 guard + v19 回弹通道方向有效；
  - `v6` 从 5/6 回落到 3/6（仍在目标线）；
  - `v2` 从 3/6 回落到 2/6，成为新的主缺口。
- 结论：
  - v29 完成了“修复 v19 且保持 v6>=3/6”，但引入了 `v2` 回落，属于目标迁移后的新 trade-off 版本。

### 32.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 弱层 guard 放松后，`v2` 场景可能出现“过度反打/过晚收敛”，导致 `v2=2/6`。

### 32.5 下一步

1. 定向修复 `v2`：
- 在高 beam-like 且 `pressure_ratio` 中高区间增加 `v2` 保护阈，限制 weak guard 下的 transition bonus 释放速度。
2. 保留 `v19` 收益：
- 仅在“链压稳定且 safety_headroom 足够”时保留 `counter_v19_rebound_bonus_cap`，其余区间回退到更保守系数。
3. 继续 `iter + jobs=14` 跑 v30，硬目标：
- 保持 `vs v1_current/v5/v6/v9/v10/v19 >= 3/6`；
- 将 `vs v2` 拉回 `>=3/6`。

## 33. 本回合增量（2026-03-03，v30，隔离评测）

### 33.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_202458`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_201559`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v29）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 33.2 算法级改动

新增版本：

- `cpp_v30_v2burst_guarded_transition`（`/www/ai_cpp/v30/ai_v30.cpp`，可执行 `/www/ai_cpp/v30/ai_v30`）

核心改动（相对 v29）：

1. 新增 v2 风格 beam-burst 抑制窗口：
- `v2_beam_burst_window`：高 `beam_like_prob` + 中高 `pressure_ratio` + 高链压，且存在 `jump/density/hardening` 突增；
- 在该窗口中上调安全门槛（提高 `safety_delta_floor`、提高 `guard_penalty_slope`、降低 `guard_reject_deficit`）。

2. transition 释放分层收紧：
- 新增 `v2_transition_release_scale` 与 `v2_rebound_release_scale`；
- 对 `counter_transition_bonus_cap` 与 `counter_v19_rebound_bonus_cap` 做额外衰减，限制高压 burst 下过快释放。

3. 新增 transition 安全地板：
- 在 `consider_seq` 中，transition bonus 触发阈从 `shell_soft_floor` 抬高为 `transition_safety_floor = shell_soft_floor + 0.24`（仅 v2 burst 窗口）。

4. 高压场景反打 relief 收敛：
- 在 v2 burst 窗口下对 `counter_relief_bonus` 进一步降权（乘 `0.74`）。

### 33.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v30_v2burst_guarded_transition --exe /www/ai_cpp/v30/ai_v30 --src /www/ai_cpp/v30/ai_v30.cpp --notes "v2 beam-burst suppression + guarded transition floor"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v30_v2burst_guarded_transition --opponents cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260331`

结果：

- 轮次：`eval_20260303_202852`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_202852_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_202852_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v30_v2burst_guarded_transition` 94/180（52.2%），Elo 1597.79（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v30 视角）：
  - vs `cpp_v2_beam`：5/6（主目标修复）
  - vs `cpp_v19_rebound_shellfloor_guard`：3/6（保住）
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v10_antibeam_gate_release`：5/6
  - vs `cpp_v1_current`：2/6（回落）
  - vs `cpp_v5_counterfactual_2ply`：1/6（显著回落）
  - vs `cpp_v6_adaptive_2ply`：2/6（回落）
  - vs `cpp_v29_layered_counterline_rebound`：1/6
  - vs `greedy/random_safe`：各 6/6

解读：

- 相对 32.5 目标：
  - 达标：`v2=5/6`、`v19=3/6`、`v9=3/6`、`v10=5/6`；
  - 未达标：`v1_current=2/6`、`v5=1/6`、`v6=2/6`。
- 结论：
  - v30 成功修复了 v2，但引入了对 `v1_current/v5/v6` 的明显退化；
  - 属于“过度收紧高压 transition 导致普适反打能力下降”的失败迭代。

### 33.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- v2 定向抑制窗口当前触发范围偏宽，连带压制了对 2ply 家族（v5/v6）和 current 基线的正常反打释放。

### 33.5 下一步

1. 收窄 v2 burst 抑制触发条件：
- 增加 `anti.initiative_gate` 上限与 `chain_jump_norm/density_jump_norm` 双条件，避免在“高 initiative 的可反打窗口”误触发。
2. 恢复 2ply 反打底线：
- 为 `v6` 通道增加最小 release floor（仅在 `next_main_safety >= shell_soft_floor + margin` 时生效），避免被统一缩放压死。
3. 做双层 release 机制：
- 将 transition bonus 切分为 `safe_core + risky_extra`，v2 burst 只裁剪 `risky_extra`，保留 `safe_core`。
4. 继续 `iter + jobs=14` 跑 v31，硬目标：
- 保持 `vs v2/v19/v9/v10 >= 3/6`；
- 将 `vs v1_current/v5/v6` 共同拉回 `>=3/6`。

## 34. 本回合增量（2026-03-03，v31，隔离评测）

### 34.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_203522`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_202852`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v30 失败回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 34.2 算法级改动

新增版本：

- `cpp_v31_dualcore_release_rebalance`（`/www/ai_cpp/v31/ai_v31.cpp`，可执行 `/www/ai_cpp/v31/ai_v31`）

核心改动（相对 v30）：

1. 收窄 v2 burst 抑制触发：
- `v2_beam_burst_window` 增加 `anti.initiative_gate <= 0.58`；
- 将 jump 条件改为“链压 jump + 密度 jump 双条件”或“更高链压 jump + 高 hardening”组合，降低误触发。

2. transition bonus 双层拆分：
- 拆为 `counter_transition_safe_core_cap` 与 `counter_transition_risky_extra_cap`；
- 仅对 `risky_extra` 施加 `v2_risky_extra_scale`，避免把所有 counter 过渡奖励一刀切压缩。

3. v6 最小释放地板：
- 新增 `counter_v6_min_release_floor`，仅在 `counter_v6_2ply_window` 且 `next_main_safety >= shell_soft_floor + margin` 时释放，避免 v6 通道被缩放后完全失活。

4. 缓和 v2 burst 场景惩罚强度：
- 相对 v30，下调 burst 场景的 guard 加压幅度，并将 transition safety floor 抬升从 `+0.24` 降到 `+0.10`。

### 34.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v31_dualcore_release_rebalance --exe /www/ai_cpp/v31/ai_v31 --src /www/ai_cpp/v31/ai_v31.cpp --notes "narrow v2 burst gate + dual-core transition + v6 min release floor"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v31_dualcore_release_rebalance,cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v31_dualcore_release_rebalance --opponents cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260401`

结果：

- 轮次：`eval_20260303_204748`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_204748_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_204748_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v31_dualcore_release_rebalance` 87/186（46.8%），Elo 1539.25（该轮第 2）
- 分对手（按 `matches` 基于 `score_a` 复算，v31 视角）：
  - vs `cpp_v2_beam`：1/6
  - vs `cpp_v1_current`：3/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v6_adaptive_2ply`：1/6
  - vs `cpp_v9_emergency_antibeam`：3/6
  - vs `cpp_v10_antibeam_gate_release`：1/6
  - vs `cpp_v19_rebound_shellfloor_guard`：4/6
  - vs `cpp_v30_v2burst_guarded_transition`：2/6
  - vs `cpp_v29_layered_counterline_rebound`：2/6
  - vs `greedy/random_safe`：各 6/6

解读：

- 相对 33.5 目标：
  - 达标：`v1_current=3/6`、`v5=3/6`、`v9=3/6`、`v19=4/6`；
  - 未达标：`v2=1/6`、`v6=1/6`、`v10=1/6`。
- 结论：
  - v31 虽在 `v1_current/v5` 有恢复，但 `v2/v6/v10` 出现严重回落，整体退化明显；
  - 当前“safe_core/risky_extra + v6 floor”与已有 guard/窗口组合存在非线性耦合，未形成稳定改进。

### 34.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 多通道叠加后（counterline guard + v2 burst + dual-core + v6 floor）参数耦合复杂，容易在不同族群间放大相反效应。

### 34.5 下一步

1. 回退到稳定基线再做单变量实验：
- 以 v29 为基线，仅引入“收窄后的 v2 burst 判定”，不叠加 dual-core/v6 floor，先验证 `v2` 是否可在不伤 `v6` 的前提下改善。
2. 将 v6 floor 独立成开关实验：
- 在固定基线下仅测试 `v6 min release floor`，避免与 v2 burst 缩放交叉干扰。
3. 增加局后特征日志（轻量）：
- 记录 `v2_beam_burst_window` 触发频次、transition bonus 实际释放量，定位是否“触发过频”或“释放过度裁剪”。
4. 继续 `iter + jobs=14` 跑 v32，硬目标：
- 保持 `vs v1_current/v5/v6/v9/v10/v19 >= 3/6`；
- 将 `vs v2` 拉回 `>=3/6`。

## 35. 本回合增量（2026-03-03，v32，隔离评测）

### 35.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（读取时为 `eval_20260303_205642`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（读取时为 `eval_20260303_204748`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v31 失败回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 35.2 算法级改动

新增版本：

- `cpp_v32_v29_narrow_v2burst`（`/www/ai_cpp/v32/ai_v32.cpp`，可执行 `/www/ai_cpp/v32/ai_v32`）

核心改动（相对 v29，单变量实验）：

1. 引入收窄版 v2 burst 判定窗口（单变量）：
- 新增 `v2_narrow_burst_window`，触发条件更严格（高 beam-like、高 pressure、高 chain、低 initiative，且 jump+density 同时抬升）。

2. 仅对高压过渡释放做温和裁剪：
- 新增 `v2_narrow_transition_scale`、`v2_narrow_midpressure_scale`、`v2_narrow_rebound_scale`；
- 只在 `v2_narrow_burst_window` 下生效，避免像 v30/v31 那样全局抑制反打通道。

3. 轻量安全收紧而非强抑制：
- burst 窗口仅轻微上调 `safety_delta_floor/guard_penalty_slope` 并下调 `guard_reject_deficit`；
- transition 触发地板仅抬升 `+0.08`（较 v30 的 `+0.24` 明显更温和）。

### 35.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v32_v29_narrow_v2burst --exe /www/ai_cpp/v32/ai_v32 --src /www/ai_cpp/v32/ai_v32.cpp --notes "v29 baseline + narrow v2 burst gating single-variable"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v32_v29_narrow_v2burst,cpp_v31_dualcore_release_rebalance,cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v32_v29_narrow_v2burst --opponents cpp_v31_dualcore_release_rebalance,cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260402`

结果：

- 轮次：`eval_20260303_205947`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_205947_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_205947_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v32_v29_narrow_v2burst` 105/192（54.7%），Elo 1618.64（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v32 视角）：
  - vs `cpp_v2_beam`：3/6
  - vs `cpp_v1_current`：3/6
  - vs `cpp_v5_counterfactual_2ply`：3/6
  - vs `cpp_v6_adaptive_2ply`：4/6
  - vs `cpp_v9_emergency_antibeam`：4/6
  - vs `cpp_v10_antibeam_gate_release`：3/6
  - vs `cpp_v19_rebound_shellfloor_guard`：3/6
  - vs `cpp_v29_layered_counterline_rebound`：4/6
  - vs `cpp_v30_v2burst_guarded_transition`：3/6
  - vs `greedy/random_safe`：各 6/6

解读：

- 相对 34.5 硬目标：
  - 达标：`v2=3/6`、`v1_current=3/6`、`v5=3/6`、`v6=4/6`、`v9=4/6`、`v10=3/6`、`v19=3/6`（核心目标全达标）。
- 对比 v30/v31：
  - 避免了 v30 的“v2修复但 v5/v6 崩塌”；
  - 也避免了 v31 的“多通道耦合导致整体退化”；
  - 说明“v29 基线 + 单变量收窄 v2 窗口”是当前更稳健方向。
- 结论：
  - v32 为本阶段首个同时满足关键对手硬约束的版本，可作为后续迭代新基线。

### 35.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 虽核心目标全达标，但存在族群回落点（如 `v22/v25/v26/v27` 对局分别出现 1/6 或接近下限），需后续稳健化。

### 35.5 下一步

1. 以 v32 为新基线做“稳健化”微结构：
- 仅针对 `v22/v25/v26/v27` 这些回落族群增加小幅保护项，不破坏核心目标线。
2. 加一轮重复种子验证：
- 保持同配置再跑 1-2 轮不同 seed，确认 `v2/v1_current/v5/v6/v9/v10/v19` 的达标稳定性。
3. 若稳定通过，再考虑引入轻量日志：
- 记录 `v2_narrow_burst_window` 触发频次与 transition 实际释放量，指导下一轮低风险改进。

## 36. 本回合增量（2026-03-03，v33，隔离评测）

### 36.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_210812`；执行中滚动到 `eval_20260303_211506`，本轮未使用生产评测）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_205947`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v32）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 36.2 算法级改动

新增版本：

- `cpp_v33_v32_hardline_recovery_lane`（`/www/ai_cpp/v33/ai_v33.cpp`，可执行 `/www/ai_cpp/v33/ai_v33`）

核心改动（相对 v32）：

1. 新增“hardline recovery window”：
- 仅在非 `v2_narrow_burst_window`、高压中高 beam-like、较高 initiative、且 hardening 强度达到阈值时触发；
- 用于把反打释放集中投向 `v22/v25/v26/v27` 这类高压硬化族群，而不在 v2 窄窗口内放大风险。

2. 新增分通道恢复缩放：
- `hardline_transition_scale`、`hardline_midpressure_scale`、`hardline_v6_scale`、`hardline_rebound_scale`；
- 分别作用于 transition/midpressure/v6/rebound 四类 counter bonus，形成结构化恢复而非单参数放大。

3. 窗口内轻量 guard 松绑：
- 在 `hardline_recovery_window` 下，对 `safety_delta_floor` 小幅下调、`guard_penalty_slope` 小幅减弱、`guard_reject_deficit` 小幅放宽；
- 目标是在可控安全边界内恢复被压制的 counter 通道。

### 36.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v33_v32_hardline_recovery_lane --exe /www/ai_cpp/v33/ai_v33 --src /www/ai_cpp/v33/ai_v33.cpp --notes "v32 + hardline recovery lane outside narrow v2 burst"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v31_dualcore_release_rebalance,cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v33_v32_hardline_recovery_lane --opponents cpp_v32_v29_narrow_v2burst,cpp_v31_dualcore_release_rebalance,cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260403`

结果：

- 轮次：`eval_20260303_211955`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_211955_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_211955_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v33_v32_hardline_recovery_lane` 116/198（58.6%），Elo 1659.59（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v33 视角）：
  - 核心约束集：`v2=5/6`、`v1_current=2/6`、`v5=4/6`、`v6=3/6`、`v9=4/6`、`v10=5/6`、`v19=5/6`
  - 定向族群：`v22=3/6`、`v25=4/6`、`v26=2/6`、`v27=2/6`
  - 对基线：`vs v32=1/6`

解读：

- 相对 35.5 的“族群修复”目标：
  - 已改善：`v22` 从低位拉回到 3/6，`v25` 达到 4/6；
  - 未完成：`v26/v27` 仍为 2/6，未达 3/6 线。
- 相对核心硬约束：
  - 多数保持或提升（`v2/v5/v6/v9/v10/v19` 均 >=3/6）；
  - `v1_current` 回落到 2/6，出现新退化。
- 结论：
  - v33 属于“部分命中目标”的中间版本：高压族群修复有效但不完整，且引入了 `v1_current` 与 `vs v32` 的明显副作用。

### 36.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- `hardline_recovery_window` 当前覆盖面偏大，可能在非目标局（如 `v1_current`）过度放大 counter 通道，带来普适性回落。

### 36.5 下一步

1. 缩窄 `hardline_recovery_window`：
- 提高 beam-like 下限或增加“jump 形态”约束，只在更像 `v22/v25/v26/v27` 的对局触发，避免污染 `v1_current`。
2. 将恢复缩放分裂为“稳定态/脉冲态”：
- 对 `v26/v27` 重点加强脉冲链压通道（midpressure），同时下调对 transition 的统一增益，减少对基线对局副作用。
3. 继续 `iter + jobs=14` 复现实验：
- 下轮硬目标：保持 `v2/v5/v6/v9/v10/v19 >= 3/6`，把 `v1_current`、`v26`、`v27` 至少拉回 `3/6`。

## 37. 本回合增量（2026-03-03，v34，隔离评测）

### 37.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_212922`；执行中滚动到 `eval_20260303_213718`，本轮未使用生产评测）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_211955`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v33）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 37.2 算法级改动

新增版本：

- `cpp_v34_split_pulse_recovery`（`/www/ai_cpp/v34/ai_v34.cpp`，可执行 `/www/ai_cpp/v34/ai_v34`）

核心改动（相对 v33）：

1. 收窄 hardline 触发面：
- 将原 `hardline_recovery_window` 改为更严格的 `hardline_recovery_base_window`（更高 beam-like/pressure/initiative 下限，且限制区间上界）；
- 目标是减少在非目标对局（尤其 `v1_current`）的误触发。

2. 引入“脉冲态/稳定态”双态恢复：
- 基于 `chain_jump_norm` 与 `density_jump_norm` 拆分 `hardline_pulse_recovery_window` 与 `hardline_stable_recovery_window`；
- 对 transition/midpressure/v6/rebound 分别使用双态缩放，而不是 v33 的统一放大。

3. 新增独立脉冲 counter 通道：
- 新增 `counter_hardline_pulse_bonus_cap`，在脉冲高压但安全余量足够时提供额外释放；
- 用于定向补 `v26/v27` 这类脉冲链压局，而不依赖原有 midpressure/transition 窗口重叠。

4. guard 松绑降级为“仅稳定态轻量生效”：
- 仅在 `hardline_stable_recovery_window` 轻度放宽 `safety_delta_floor/guard_penalty_slope/guard_reject_deficit`；
- 避免 v33 中“全 hardline 窗口均松绑”带来的普适副作用。

### 37.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v34_split_pulse_recovery --exe /www/ai_cpp/v34/ai_v34 --src /www/ai_cpp/v34/ai_v34.cpp --notes "v33 narrowed hardline window + split pulse/stable recovery lane"`

评测命令（必须脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v31_dualcore_release_rebalance,cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --challengers cpp_v34_split_pulse_recovery --opponents cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v31_dualcore_release_rebalance,cpp_v30_v2burst_guarded_transition,cpp_v29_layered_counterline_rebound,cpp_v28_v6lane_rebound_guard,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v24_guarded_additive_sustain,cpp_v23_sustainfloor_tempo_decay,cpp_v22_burst_harden_dynamic_relief,cpp_v21_beamharden_whitelist,cpp_v20_duallayer_counterlane,cpp_v19_rebound_shellfloor_guard,cpp_v18_conditional_exchange_rebound,cpp_v17_family_state_exchange_guard,cpp_v16_fastcut_dual_channel,cpp_v15_tempo_filtered_chainjump,cpp_v14_chainjump_reentry_guard,cpp_v13_beamlike_smoothgate,cpp_v12_segmented_gate_cooldown,cpp_v11_dualgate_release_confirm,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v8_mode_hysteresis,cpp_v7_mode_switch,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_r2_baseline,cpp_v1_current,greedy,random_safe --seed 20260404`

结果：

- 轮次：`eval_20260303_214105`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_214105_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_214105_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v34_split_pulse_recovery` 122/204（59.8%），Elo 1625.19（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v34 视角）：
  - 核心约束集：`v2=4/6`、`v1_current=2/6`、`v5=4/6`、`v6=4/6`、`v9=3/6`、`v10=5/6`、`v19=4/6`
  - 定向族群：`v22=4/6`、`v25=3/6`、`v26=5/6`、`v27=2/6`
  - 对比近邻：`vs v33=1/6`、`vs v32=3/6`

解读：

- 相对 v33：
  - 明显改善：`v26` 从 2/6 拉升到 5/6，`v22/v25` 保持在达标线以上；
  - 仍未解决：`v27` 维持 2/6，`v1_current` 仍为 2/6。
- 相对硬约束：
  - `v2/v5/v6/v9/v10/v19` 均达到或超过 3/6；
  - 但 `v1_current` 未达 3/6，当前版本仍不能作为“核心约束全达标”候选。
- 结论：
  - v34 证明“脉冲通道独立化”对 `v26` 有效，但触发面与增益分配仍不足以同时修复 `v27` 与 `v1_current`。

### 37.4 风险

- 每对手 6 局，小样本方差仍高。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- `v27` 与 `v1_current` 的持续低位说明当前窗口分裂虽然降低了部分副作用，但仍存在“脉冲态收益与普适稳定性”冲突。

### 37.5 下一步

1. 针对 `v27` 做专门补偿：
- 在 `hardline_pulse_recovery_window` 内增加“中脉冲+中高 beam-like”专用 lane（区别于当前高脉冲 lane），避免只修复 `v26`。
2. 给 `v1_current` 增加反误触保护：
- 引入 `v1_guardrail`（例如低 chain_jump + 中低 beam-like 时抑制 pulse bonus），限制非目标对局的额外释放。
3. 继续 `iter + jobs=14` 复现实验：
- 下轮硬目标：保持 `v2/v5/v6/v9/v10/v19 >= 3/6`，并把 `v1_current`、`v27` 拉回 `>=3/6`。

## 38. 本回合增量（2026-03-03，v35，隔离评测）

### 38.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_214900`；执行中滚动到 `eval_20260303_215648`，本轮未使用生产评测）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_214105`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v34）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 38.2 算法级改动

新增版本：

- `cpp_v35_midpulse_guardrail`（`/www/ai_cpp/v35/ai_v35.cpp`，可执行 `/www/ai_cpp/v35/ai_v35`）

核心改动（相对 v34）：

1. 新增 `v1_guardrail_window`：
- 在中低 beam-like + 中高 initiative + 低 jump 区间触发；
- 对 hardline 通道缩放施加抑制（transition/midpressure/v6/rebound），减少非目标局误触发。

2. 保留高脉冲通道并加 guardrail 保护：
- `counter_hardline_pulse_bonus_cap` 仅在非 guardrail 场景下生效，避免对 `v1_current` 这类局额外放大。

3. 新增中脉冲专用通道：
- 新增 `counter_hardline_midpulse_bonus_cap`，覆盖“中脉冲 + 中高 beam-like + 足够安全余量”区间；
- 目标是专门补 `v27`，避免只能修复 `v26`。

4. 稳定态 guard 放松继续保守：
- `hardline_stable_recovery_window` 的 guard 松绑仅在非 guardrail 下生效，维持风险边界。

### 38.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v35_midpulse_guardrail --exe /www/ai_cpp/v35/ai_v35 --src /www/ai_cpp/v35/ai_v35.cpp --notes "v34 + v1 guardrail + hardline mid-pulse lane"`

评测执行说明：

- 首次尝试（全对手集，seed `20260405`）出现长时间挂起，未产生可用 `iter latest` 结果；
- 回合内改为精简对手集并保持 `jobs=14` 重新执行，确保本轮有可复现实验产出。

最终评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v35_midpulse_guardrail --opponents cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260406`

结果：

- 轮次：`eval_20260303_220318`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_220318_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_220318_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v35_midpulse_guardrail` 48/96（50.0%），Elo 1559.04（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v35 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=2/6`、`v5=2/6`、`v6=2/6`、`v9=6/6`、`v10=3/6`、`v19=3/6`
  - 定向族群：`v22=1/6`、`v25=2/6`、`v26=4/6`、`v27=3/6`
  - 对比近邻：`vs v34=1/6`、`vs v33=2/6`、`vs v32=3/6`

解读：

- 达成点：
  - `v27` 从 2/6 拉回到 3/6；
  - `v26` 保持较强（4/6）。
- 失败点：
  - `v2/v1/v5/v6` 同时回落到 2/6；
  - `v22` 降到 1/6，出现新的明显退化。
- 结论：
  - v35 的“guardrail + midpulse lane”产生了过度结构化副作用，虽修复了 `v27`，但破坏了核心基线稳定性；
  - 本轮属于失败迭代，需要回退并拆分验证。

### 38.4 风险

- 本轮先后两次评测（第一次挂起、第二次精简集完成）提示：大规模对手集在当前并发下存在偶发卡住风险。
- 精简对手集评测覆盖面小于全量，结论需在下一轮全量或半全量复核。
- 新增多通道（guardrail + pulse + midpulse）耦合较强，容易在不同对手族群之间引发反向退化。

### 38.5 下一步

1. 回退到 v34 稳定骨架再做单变量：
- 先只保留 `v1_guardrail_window`，不启用 midpulse 通道，验证是否能单独修复 `v1_current` 且不伤 `v2/v5/v6`。
2. midpulse 独立 A/B：
- 在固定基线上仅开启 `counter_hardline_midpulse_bonus_cap`，确认其对 `v27` 的纯增益与副作用边界。
3. 复跑全量或半全量对手集（仍 `jobs=14`）：
- 在修复挂起风险后，用更大覆盖面验证“核心集 + 定向族群”是否同时达标。

## 39. 本回合增量（2026-03-03，v36，隔离评测）

### 39.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_215648`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_220318`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v35 失败回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 39.2 算法级改动

新增版本：

- `cpp_v36_v34_guardrail_only`（`/www/ai_cpp/v36/ai_v36.cpp`，可执行 `/www/ai_cpp/v36/ai_v36`）

核心改动（相对 v34，单变量）：

1. 仅引入 `v1_guardrail_window`：
- 在中低 beam-like + 中高 initiative + 低 jump 区间触发；
- 对 hardline 通道缩放做轻度抑制（transition/midpressure/v6/rebound）。

2. 不引入 midpulse 新通道：
- 明确不启用 `counter_hardline_midpulse_bonus_cap` 类改动，仅验证 guardrail 的净效应。

3. 脉冲通道加 guardrail 保护：
- `counter_hardline_pulse_bonus_cap` 仅在非 guardrail 场景允许释放，减少误触发。

4. 稳定态 guard 放松受 guardrail 约束：
- `hardline_stable_recovery_window` 的 guard 放松仅在非 guardrail 下生效。

### 39.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v36_v34_guardrail_only --exe /www/ai_cpp/v36/ai_v36 --src /www/ai_cpp/v36/ai_v36.cpp --notes "v34 + v1 guardrail only (no midpulse lane)"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v36_v34_guardrail_only --opponents cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260407`

结果：

- 轮次：`eval_20260303_221351`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_221351_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_221351_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v36_v34_guardrail_only` 53/102（52.0%），Elo 1571.82（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v36 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=3/6`、`v5=2/6`、`v6=1/6`、`v9=3/6`、`v10=6/6`、`v19=3/6`
  - 定向族群：`v22=4/6`、`v25=1/6`、`v26=1/6`、`v27=4/6`
  - 对比近邻：`vs v35=2/6`、`vs v34=2/6`、`vs v33=3/6`、`vs v32=4/6`

解读：

- 成功点：
  - `v1_current` 回到 3/6；
  - `v27` 提升到 4/6；
  - `v22` 提升到 4/6，`v10` 强势（6/6）。
- 失败点：
  - `v6=1/6`、`v25=1/6`、`v26=1/6`，出现明显结构性退化；
  - `v2`、`v5` 也仅 2/6。
- 结论：
  - “guardrail only”单变量修复了 `v1/v27`，但显著破坏了 `v6/v25/v26`；
  - 说明 guardrail 阈值对脉冲族群压制过强，本轮仍为失败迭代。

### 39.4 风险

- 精简对手集覆盖面有限，仍需更大覆盖验证。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- guardrail 触发区间与脉冲对手群体重叠偏大，导致“修复一侧、破坏另一侧”的典型耦合问题。

### 39.5 下一步

1. 继续回到 v34 主体，做“guardrail 阈值再收窄”：
- 将 guardrail 限定到更低 jump 且更低 beam-like 区间，尽量不碰 `v26/v6` 的有效脉冲窗口。
2. 采用双开关实验矩阵：
- A: 仅 guardrail（更窄阈值）；B: 仅 midpulse（不加 guardrail）；分别验证后再考虑组合。
3. 维持 `iter + jobs=14`，先精简集快速筛选，再用半全量对手集复核：
- 目标是同时守住 `v2/v5/v6/v9/v10/v19` 并保持 `v1/v27 >= 3/6`。

## 40. 本回合增量（2026-03-03，v37，隔离评测）

### 40.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_221108`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_221351`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v36 失败回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 40.2 算法级改动

新增版本：

- `cpp_v37_v34_narrow_guardrail`（`/www/ai_cpp/v37/ai_v37.cpp`，可执行 `/www/ai_cpp/v37/ai_v37`）

核心改动（相对 v34，单变量收窄版 guardrail）：

1. 引入“更窄 guardrail 区间”：
- `v1_guardrail_window` 仅覆盖更低 jump、更低 hardening、且 beam-like/pressure 更窄区间；
- 目标是减少对 `v26/v6` 有效脉冲窗口的误伤。

2. guardrail 仅轻度抑制通道缩放：
- 对 transition/midpressure/v6/rebound 的缩放抑制幅度较 v36 更轻。

3. 不引入 midpulse 新结构：
- 仍保持单变量实验，避免多通道耦合。

4. pulse bonus 与 stable guard 放松均受 guardrail 约束：
- 在 guardrail 命中时不释放 pulse bonus，且不执行 stable guard 放松。

### 40.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v37_v34_narrow_guardrail --exe /www/ai_cpp/v37/ai_v37 --src /www/ai_cpp/v37/ai_v37.cpp --notes "v34 + narrow v1 guardrail only (low-jump low-hardening)"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v37_v34_narrow_guardrail --opponents cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260408`

结果：

- 轮次：`eval_20260303_222436`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_222436_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_222436_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v37_v34_narrow_guardrail` 56/108（51.9%），Elo 1587.09（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v37 视角）：
  - 核心约束集：`v2=3/6`、`v1_current=4/6`、`v5=1/6`、`v6=3/6`、`v9=2/6`、`v10=2/6`、`v19=6/6`
  - 定向族群：`v22=2/6`、`v25=3/6`、`v26=2/6`、`v27=2/6`
  - 对比近邻：`vs v36=2/6`、`vs v35=1/6`、`vs v34=3/6`、`vs v33=3/6`、`vs v32=5/6`

解读：

- 改善点：
  - `v1_current` 显著回升到 4/6；
  - `v2` 回到 3/6，`v6` 回到 3/6，`v19` 提升到 6/6。
- 退化点：
  - `v5=1/6`，`v9=2/6`，`v10=2/6`；
  - `v22/v26/v27` 也回落到 2/6 左右。
- 结论：
  - “更窄 guardrail”缓解了 v36 对 `v1/v2/v6` 的副作用，但把退化转移到 `v5/v9/v10` 与部分定向族群；
  - 本轮仍未达到核心集稳定达标，属于失败迭代。

### 40.4 风险

- 精简对手集覆盖面有限，结论需后续在半全量对手集复核。
- `thread_fallback` 与进程池时序差异仍可能影响边界局。
- 当前问题体现为“修复迁移”：同一 guardrail 在不同族群上引发相反效应，参数耦合仍偏强。

### 40.5 下一步

1. 改为“对手族群分段 guardrail”而非统一 guardrail：
- 对 `v1` 防误触与对 `v5/v9/v10` 保活分开建模，避免单阈值统管。
2. 做双分支 A/B：
- A 分支仅修 `v1`（不压 `v5/v9/v10`）；B 分支仅修 `v27/v26`；先分别达标再尝试合并。
3. 继续 `iter + jobs=14`：
- 先精简集快速筛，再用更大对手集验证是否能同时满足核心约束线。

## 41. 本回合增量（2026-03-03，v38，隔离评测）

### 41.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_222158`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_222436`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v37 失败回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 41.2 算法级改动

新增版本：

- `cpp_v38_v37_segmented_guardrail_release`（`/www/ai_cpp/v38/ai_v38.cpp`，可执行 `/www/ai_cpp/v38/ai_v38`）

核心改动（相对 v37，分段 guardrail）：

1. 新增“高压分段释放窗口”`v1_guardrail_release_window`：
- 在 `v1_guardrail_window` 命中基础上，只有当 beam-like/pressure/chain/attack 同时抬升（并伴随 density 或持续 low-jump 压力）才触发。
- 目标是把 `v1` 防误触与 `v5/v9/v10` 高压抗性拆开，避免统一 guardrail 一刀切。

2. guardrail 缩放改为“抑制/释放”双段：
- `hardline_transition_scale / midpressure_scale / v6_scale / rebound_scale` 在 release 窗口内改为轻度正向放大；
- 非 release 仍保留原有 guardrail 抑制。

3. 安全壳参数做小幅释放补偿：
- release 窗口内轻微放松 `safety_delta_floor / guard_penalty_slope / guard_reject_deficit`，减少高压对手下的过度保守。

4. pulse 通道从“guardrail 全禁”改为“guardrail 条件放行”：
- `counter_hardline_pulse_window` 在 release 窗口允许进入；
- 但增加 `0.72` 抑制系数，避免脉冲过冲。

### 41.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v38_v37_segmented_guardrail_release --exe /www/ai_cpp/v38/ai_v38 --src /www/ai_cpp/v38/ai_v38.cpp --notes "v37 + segmented v1 guardrail release lane for high-pressure anti-beam"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v38_v37_segmented_guardrail_release --opponents cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260409`

结果：

- 轮次：`eval_20260303_223650`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_223650_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_223650_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v38_v37_segmented_guardrail_release` 69/114（60.5%），Elo 1626.46（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v38 视角）：
  - 核心约束集：`v2=5/6`、`v1_current=4/6`、`v5=3/6`、`v6=1/6`、`v9=3/6`、`v10=3/6`、`v19=2/6`
  - 定向族群：`v22=5/6`、`v25=3/6`、`v26=4/6`、`v27=4/6`
  - 对比近邻：`vs v37=5/6`、`vs v36=1/6`、`vs v35=4/6`、`vs v34=3/6`、`vs v33=5/6`、`vs v32=2/6`

解读：

- 成功点：
  - 相比 v37，`v2/v5/v9/v10/v22/v26/v27` 明显回升；
  - `v1_current` 维持 4/6，说明 guardrail 主目标未丢。
- 失败点：
  - `v6=1/6`、`v19=2/6` 出现新的明显退化；
  - 对 `v36`、`v32` 也偏弱（1/6、2/6），存在策略对抗面缺口。
- 结论：
  - “分段 guardrail + release”有效修复了 v37 的 `v5/v9/v10` 误伤，但把主要短板迁移到 `v6/v19` 族群；
  - 本轮属于“有进展但未收敛”，仍需下一轮定向补洞。

### 41.4 风险

- 当前改动引入了条件释放分支，策略非线性增强，可能在未覆盖对手集上出现波动。
- 评测仍为精简对手集，覆盖面有限；需后续半全量/全量复核。
- `thread_fallback` 调度下时序差异仍可能影响边界局，需保持多 seed 复验。

### 41.5 下一步

1. 为 `v6/v19` 增加独立防线门：
- 在 release 窗口叠加 `v6/v19` 专属 shell-floor 与链压上限，避免过早释放导致主堡安全损失。
2. 做“release 仅 midpressure，不放 v6/rebound”对照分支：
- 保留 `v5/v9/v10` 修复能力，同时测试是否能回补 `v6/v19`。
3. 保持 `iter + jobs=14`，先双 seed 精简集，再半全量复核：
- 目标是同时满足 `v2/v1/v5/v6/v9/v10/v19` 的最低线，不再出现单侧修复迁移。

## 42. 本回合增量（2026-03-03，v39，隔离评测）

### 42.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_223402`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_223650`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v38 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 42.2 算法级改动

新增版本：

- `cpp_v39_v38_release_protect_v6v19`（`/www/ai_cpp/v39/ai_v39.cpp`，可执行 `/www/ai_cpp/v39/ai_v39`）

核心改动（相对 v38，release 保护层）：

1. 新增 `v6_v19_protect_window`：
- 在 `v1_guardrail_release_window` 命中后，进一步要求中高 pressure + 中高 chain + 更高 alert/hardening；
- 目标是在高压段专门收紧对 `v6/v19` 易受击穿的区域。

2. release 缩放改为“分层释放”：
- protect 窗口下仅保留轻微 `transition/midpressure` 放行；
- 同时将 `hardline_v6_scale`、`hardline_rebound_scale` 调低（保护态）。

3. protect 窗口内收紧安全壳：
- 提高 `safety_delta_floor`、`guard_penalty_slope`，降低 `guard_reject_deficit`；
- 额外收紧 `shell_safety_drop_cap`、`shell_hard_margin` 并提高 `shell_soft_penalty_slope`。

4. protect 窗口内禁用 hardline pulse 放行：
- `counter_hardline_pulse_window` 在 protect 场景下不再开启，避免脉冲过冲。

### 42.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v39_v38_release_protect_v6v19 --exe /www/ai_cpp/v39/ai_v39 --src /www/ai_cpp/v39/ai_v39.cpp --notes "v38 + release protect window for v6/v19 (tight shell, limit v6/rebound/pulse)"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v39_v38_release_protect_v6v19 --opponents cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260410`

结果：

- 轮次：`eval_20260303_224743`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_224743_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_224743_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v39_v38_release_protect_v6v19` 67/120（55.8%），Elo 1595.41（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v39 视角）：
  - 核心约束集：`v2=5/6`、`v1_current=2/6`、`v5=4/6`、`v6=1/6`、`v9=3/6`、`v10=2/6`、`v19=3/6`
  - 定向族群：`v22=2/6`、`v25=3/6`、`v26=2/6`、`v27=4/6`
  - 对比近邻：`vs v38=4/6`、`vs v37=1/6`、`vs v36=4/6`、`vs v35=3/6`、`vs v34=4/6`、`vs v33=4/6`、`vs v32=4/6`

解读：

- 改善点：
  - `v19` 从上一轮 2/6 回到 3/6；
  - `v5`、`v32~v36` 族群保持较强。
- 失败点：
  - `v6` 仍 1/6，核心问题未解；
  - `v1/v10/v22/v26` 回落到 2/6，且 `v37` 对抗显著偏弱（1/6）。
- 结论：
  - protect 窗口在局部补回了 `v19`，但整体收紧过度，造成新的全面回落；
  - 本轮属于失败迭代，需要回撤“全局 protect”强度，转向更细粒度补洞。

### 42.4 风险

- release + protect 双层门控增加了阈值耦合，策略边界更脆弱。
- 与背景生产评测并行时，资源竞争会拉长实验时间，可能放大边界局波动。
- 当前仍是精简对手集，需后续更大覆盖复核。

### 42.5 下一步

1. 回到 v38 主体，去掉“全局 protect 收紧”，改为仅对 `counter_v6_2ply_bonus_cap` / `counter_v19_rebound_bonus_cap` 做独立限幅。
2. 单独做 `v6` 反制通道（不触碰 v1/v5/v9/v10）：
- 仅在 `v6` 风险形态下提升安全壳，不影响 release 主通道。
3. 保持 `iter + jobs=14`，先双 seed 精简复验，再半全量验证：
- 目标是在不回落 `v1/v10/v22` 的前提下，把 `v6` 提升到至少 2/6~3/6。

## 43. 本回合增量（2026-03-03，v40，隔离评测）

### 43.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_224714`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_224743`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v39 失败回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 43.2 算法级改动

新增版本：

- `cpp_v40_v38_targeted_v6v19_cap`（`/www/ai_cpp/v40/ai_v40.cpp`，可执行 `/www/ai_cpp/v40/ai_v40`）

核心改动（相对 v38，定向限幅而非全局收紧）：

1. 新增 `v6_v19_cap_risk_window` 与连续风险强度 `v6_v19_cap_risk`：
- 仅在 release 场景下、且 pressure/chain/alert/hardening 达到高风险组合时生效。

2. 只限幅 v6/v19 通道：
- 对 `counter_v6_2ply_bonus_cap` 乘以 `v6_bonus_limit_scale`；
- 对 `counter_v19_rebound_bonus_cap` 乘以 `v19_bonus_limit_scale`。

3. pulse 做轻度联动限幅：
- 风险窗口中对 `counter_hardline_pulse_bonus_cap` 追加 `pulse_bonus_limit_scale`；
- 不再像 v39 那样全局收紧 shell/guard 主逻辑。

### 43.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v40_v38_targeted_v6v19_cap --exe /www/ai_cpp/v40/ai_v40 --src /www/ai_cpp/v40/ai_v40.cpp --notes "v38 + targeted cap risk window for v6/v19 bonus channels"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v40_v38_targeted_v6v19_cap --opponents cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260411`

结果：

- 轮次：`eval_20260303_225809`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_225809_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_225809_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v40_v38_targeted_v6v19_cap` 74/126（58.7%），Elo 1585.28（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v40 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=2/6`、`v5=4/6`、`v6=4/6`、`v9=2/6`、`v10=3/6`、`v19=2/6`
  - 定向族群：`v22=3/6`、`v25=3/6`、`v26=2/6`、`v27=3/6`
  - 对比近邻：`vs v39=4/6`、`vs v38=3/6`、`vs v37=4/6`、`vs v36=4/6`、`vs v35=4/6`、`vs v34=4/6`、`vs v33=4/6`、`vs v32=5/6`

解读：

- 改善点：
  - 相比 v39，`v6` 从 1/6 拉升到 4/6；
  - `v5` 保持较强（4/6），且对近邻版本整体压制更稳定。
- 退化点：
  - `v1/v2/v9/v19/v26` 回落到 2/6 左右，核心集不平衡仍明显；
  - 说明“定向限幅”在修复 v6 的同时削弱了反 beam 主线。
- 结论：
  - 本轮属于“局部成功（v6）但全局仍失败（核心集失衡）”；
  - 下一轮应继续做族群解耦，避免 v6 修复挤压 `v1/v2/v9`。

### 43.4 风险

- 目前 v6/v19 限幅仍与 release 主通道耦合，容易触发“修复迁移”。
- 与生产评测并行时资源竞争明显，评测耗时与边界局波动增大。
- 精简对手集结论仍需半全量复核。

### 43.5 下一步

1. 将 `v6` 限幅与 `v19` 限幅拆成独立门控：
- `v6` 只看 chain_jump/initiative 结构，`v19` 只看 shell 安全余量，避免同窗同罚。
2. 在 `v1/v2` 场景增加“反误伤白名单”：
- 当 beam-like 低且 initiative 高时，禁止触发 v6/v19 限幅，优先保证 `v1/v2` 基线。
3. 维持 `iter + jobs=14` 再做双 seed 精简实验：
- 目标：保住 `v6>=3/6` 的同时把 `v1/v2/v9` 拉回到至少 `3/6`。

## 44. 本回合增量（2026-03-03，v41，隔离评测）

### 44.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_225807`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_225809`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v40 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 44.2 算法级改动

新增版本：

- `cpp_v41_v40_split_cap_whitelist`（`/www/ai_cpp/v41/ai_v41.cpp`，可执行 `/www/ai_cpp/v41/ai_v41`）

核心改动（相对 v40，分拆限幅 + 白名单）：

1. 将 `v6/v19` 联合限幅拆分为独立风险门控：
- `v6_cap_risk_window` 与 `v19_cap_risk_window` 分别计算连续风险强度，避免同窗同罚。

2. 新增 `v1_v2_protect_whitelist`：
- 在低 beam-like + 高 initiative 的 `v1/v2` 场景下，对限幅强度做显著松绑，目标是减少误伤。

3. 通道级限幅继续保持轻量：
- `v6_bonus_limit_scale`、`v19_bonus_limit_scale`、`pulse_bonus_limit_scale` 仅作用于对应 bonus 通道，不改主壳层参数。

### 44.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v41_v40_split_cap_whitelist --exe /www/ai_cpp/v41/ai_v41 --src /www/ai_cpp/v41/ai_v41.cpp --notes "v40 + split v6/v19 cap gates with v1/v2 whitelist"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v41_v40_split_cap_whitelist --opponents cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260412`

结果：

- 轮次：`eval_20260303_230833`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_230833_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_230833_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v41_v40_split_cap_whitelist` 72/132（54.5%），Elo 1568.26（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v41 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=4/6`、`v5=1/6`、`v6=4/6`、`v9=2/6`、`v10=2/6`、`v19=3/6`
  - 定向族群：`v22=1/6`、`v25=2/6`、`v26=3/6`、`v27=1/6`
  - 对比近邻：`vs v40=3/6`、`vs v39=4/6`、`vs v38=5/6`、`vs v37=4/6`、`vs v36=5/6`、`vs v35=4/6`、`vs v34=3/6`、`vs v33=4/6`、`vs v32=3/6`

解读：

- 改善点：
  - `v1` 回升到 4/6，`v6` 维持 4/6；
  - 对 `v36/v38` 等近邻版本压制增强。
- 失败点：
  - `v5=1/6`、`v22=1/6`、`v27=1/6`，出现新的结构性崩塌；
  - `v2/v9/v10` 仍偏低（2/6 级别）。
- 结论：
  - “分拆限幅 + 白名单”实现了 `v1/v6` 双修复，但代价是 `v5/v22/v27` 大幅下滑；
  - 本轮仍为失败迭代，说明当前限幅逻辑仍与中压进攻族群存在强耦合。

### 44.4 风险

- 多门控组合带来的阈值交互复杂，容易在不同对手族群间产生迁移退化。
- 与生产评测并行时 CPU 竞争明显，实验耗时增加、边界局波动上升。
- 仍是精简对手集，需后续半全量复核。

### 44.5 下一步

1. 回到 `v40` 主体，取消对 `counter_midpressure_bonus_cap` 的隐式牵连：
- 仅保留 `v6` 专属限幅，不影响 `v5/v22/v27` 依赖的中压通道。
2. 增加 `v5/v22/v27` 保护下限：
- 对 `counter_midpressure_bonus_cap` 与 `counter_transition_bonus_cap` 设置最小保活阈值，防止被连带压穿。
3. 继续 `iter + jobs=14` 双 seed 快速复验：
- 目标是同时满足 `v1/v2/v5/v6/v9/v10/v22/v27` 至少 `3/6` 的基本线。

## 45. 本回合增量（2026-03-03，v42，隔离评测）

### 45.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_231745`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_230833`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v41 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 45.2 算法级改动

新增版本：

- `cpp_v42_v40_midpressure_floor`（`/www/ai_cpp/v42/ai_v42.cpp`，可执行 `/www/ai_cpp/v42/ai_v42`）

核心改动（相对 v40，中压通道保活）：

1. 新增 `counter_midpressure_floor_window`：
- 在中压进攻族群窗口中给 `counter_midpressure_bonus_cap` 设置动态下限，避免被连带压穿。

2. 新增 `counter_transition_floor_window`：
- 对 `counter_transition_bonus_cap` 设置动态下限，保持过渡通道最低保活能力。

3. 保持 v40 的 v6/v19 定向限幅主干：
- 仅在 transition/midpressure 两条通道上加 floor，不改其他主逻辑。

### 45.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v42_v40_midpressure_floor --exe /www/ai_cpp/v42/ai_v42 --src /www/ai_cpp/v42/ai_v42.cpp --notes "v40 + safeguard floors for transition/midpressure channels"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v42_v40_midpressure_floor --opponents cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260413`

结果：

- 轮次：`eval_20260303_232804`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_232804_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_232804_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v42_v40_midpressure_floor` 77/138（55.8%），Elo 1576.58（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v42 视角）：
  - 核心约束集：`v2=4/6`、`v1_current=3/6`、`v5=2/6`、`v6=0/6`、`v9=4/6`、`v10=3/6`、`v19=2/6`
  - 定向族群：`v22=2/6`、`v25=2/6`、`v26=2/6`、`v27=4/6`
  - 对比近邻：`vs v41=3/6`、`vs v40=3/6`、`vs v39=5/6`、`vs v38=4/6`、`vs v37=5/6`、`vs v36=3/6`、`vs v35=4/6`、`vs v34=2/6`、`vs v33=5/6`、`vs v32=3/6`

解读：

- 改善点：
  - `v2/v9/v27` 相比 v41 明显回升；
  - `v1` 回到 3/6 基线。
- 失败点：
  - `v6` 退化到 0/6（灾难性）；
  - `v5/v19/v22/v25/v26` 多线仍偏弱。
- 结论：
  - midpressure/transition floor 确实修复了部分中压族群，但严重挤压了 `v6` 相关能力；
  - 本轮仍为失败迭代，属于“修复迁移”再次发生。

### 45.4 风险

- 通道 floor 与 v6 限幅并存，导致策略偏向中压推进，牺牲了对 v6 形态的应对。
- 资源竞争持续存在，实验耗时较长，边界局波动增大。
- 当前依旧为精简对手集，需要半全量复核。

### 45.5 下一步

1. 增加 `v6_safety_priority_window`：
- 在 v6 风险形态中临时下调/关闭 midpressure floor，避免与 v6 通道抢权。
2. 对 `v5/v22/v27` 改为条件性保活：
- 只有当 `v6_safety_priority_window` 关闭时才启用较强 floor。
3. 继续 `iter + jobs=14` 双 seed 快速验证：
- 目标是在维持 `v2/v9/v27` 回升的同时，把 `v6` 拉回至少 `2/6~3/6`。

## 46. 本回合增量（2026-03-03，v43，隔离评测）

### 46.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_232712`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260303_232804`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v42 失败回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 46.2 算法级改动

新增版本：

- `cpp_v43_v42_v6_priority_floor_gate`（`/www/ai_cpp/v43/ai_v43.cpp`，可执行 `/www/ai_cpp/v43/ai_v43`）

核心改动（相对 v42，v6 优先门控）：

1. 新增 `v6_safety_priority_window`：
- 在 v6 风险形态（中高 pressure + 中高 chain + 低 jump）下触发优先保护。

2. 在优先窗口中下调 floor 影响：
- `counter_midpressure_bonus_cap` 与 `counter_transition_bonus_cap` 的 floor 乘以 `v6_floor_block`，降低抢权。

3. 在优先窗口中上调 v6 通道并下调 pulse：
- `counter_v6_2ply_bonus_cap` 额外上调；
- `counter_hardline_pulse_bonus_cap` 额外抑制，减少对 v6 防线的干扰。

### 46.3 可复现实验（已执行，隔离 scope）

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v43_v42_v6_priority_floor_gate --exe /www/ai_cpp/v43/ai_v43 --src /www/ai_cpp/v43/ai_v43.cpp --notes "v42 + v6 safety priority gate to downscale midpressure floors"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v43_v42_v6_priority_floor_gate --opponents cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260414`

结果：

- 轮次：`eval_20260303_233924`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260303_233924_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260303_233924_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v43_v42_v6_priority_floor_gate` 79/144（54.9%），Elo 1587.73（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v43 视角）：
  - 核心约束集：`v2=3/6`、`v1_current=3/6`、`v5=4/6`、`v6=3/6`、`v9=0/6`、`v10=5/6`、`v19=1/6`
  - 定向族群：`v22=2/6`、`v25=3/6`、`v26=2/6`、`v27=2/6`
  - 对比近邻：`vs v42=3/6`、`vs v41=2/6`、`vs v40=5/6`、`vs v39=3/6`、`vs v38=3/6`、`vs v37=3/6`、`vs v36=4/6`、`vs v35=3/6`、`vs v34=6/6`、`vs v33=4/6`、`vs v32=3/6`

解读：

- 改善点：
  - `v6` 从 0/6 回升到 3/6；
  - `v5` 也恢复到 4/6，`v10` 升到 5/6。
- 失败点：
  - `v9=0/6` 与 `v19=1/6` 出现严重退化；
  - `v22/v26/v27` 仍未达标。
- 结论：
  - v6 优先门控缓解了 v42 的灾难点，但退化迁移到 `v9/v19`，整体仍未收敛；
  - 本轮继续判定为失败迭代。

### 46.4 风险

- floor 与 v6 优先门控叠加后，反 beam 支线（特别是 v9 族）出现明显牺牲。
- 资源竞争持续存在，评测时间偏长、边界局波动较大。
- 精简集结论需后续半全量复核。

### 46.5 下一步

1. 新增 `v9_priority_restore_window`：
- 在低 beam-like + 高 attack 的反 beam 场景下，禁止 v6 优先门控继续压制关键通道。
2. 将 `v19` 保护从 bonus 限幅切换为安全壳底线：
- 避免通过通道缩放修复而引发新的迁移。
3. 继续 `iter + jobs=14` 双 seed 快速验证：
- 目标是守住 `v5/v6` 回升同时把 `v9/v19` 拉回到至少 `2/6~3/6`。

## 47. 本回合增量（2026-03-04，v44，隔离评测）

### 47.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_235907`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260304_000011`，由本回合实验落盘）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v43 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 47.2 算法级改动

新增版本：

- `cpp_v44_v43_v9restore_v19shellfloor`（`/www/ai_cpp/v44/ai_v44.cpp`，可执行 `/www/ai_cpp/v44/ai_v44`）

核心改动（相对 v43，反 beam 恢复 + v19 壳层保护解耦）：

1. 将 `v6/v19` 联合 bonus 限幅改为 `v6` 专属限幅：
- `v6_v19_cap_risk_window` 改为 `v6_cap_risk_window`；
- 保留 `v6_bonus_limit_scale`、`pulse_bonus_limit_scale`，移除 `v19_bonus_limit_scale` 对 rebound bonus 的直接缩放。

2. 新增 `v19_shellfloor_guard_window`：
- 在 v19 风险形态下，直接收紧 `shell_safety_drop_cap` 与 `shell_hard_margin`；
- 把 v19 保护从“通道 bonus 限幅”切换到“壳层安全底线”。

3. 新增 `v9_priority_restore_window` 并与 v6 优先门控联动：
- 在低 beam-like + 高 attack 的反 beam 场景触发恢复；
- 使用 `v6_priority_effective` 区分“v6 真优先”与“v9 恢复”路径，避免继续压制 floor/pulse 关键通道。

### 47.3 可复现实验（已执行，隔离 scope）

编译命令：

- `g++ -std=c++17 -O2 -pipe /www/ai_cpp/v44/ai_v44.cpp -o /www/ai_cpp/v44/ai_v44`

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v44_v43_v9restore_v19shellfloor --exe /www/ai_cpp/v44/ai_v44 --src /www/ai_cpp/v44/ai_v44.cpp --notes "v43 + v9 priority restore window + v19 shellfloor guard (de-couple from rebound cap)"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v44_v43_v9restore_v19shellfloor --opponents cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260415`

结果：

- 轮次：`eval_20260304_000011`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_000011_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_000011_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v44_v43_v9restore_v19shellfloor` 80/150（53.3%），Elo 1564.31（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v44 视角）：
  - 核心约束集：`v2=3/6`、`v1_current=2/6`、`v5=2/6`、`v6=4/6`、`v9=3/6`、`v10=0/6`、`v19=4/6`
  - 定向族群：`v22=2/6`、`v25=2/6`、`v26=1/6`、`v27=4/6`
  - 对比近邻：`vs v43=3/6`、`vs v42=3/6`、`vs v41=4/6`、`vs v40=3/6`

解读：

- 改善点：
  - `v9` 从 0/6 回升到 3/6；
  - `v19` 从 1/6 回升到 4/6；
  - `v6` 从 3/6 升到 4/6。
- 失败点：
  - `v10` 降到 0/6；
  - `v1/v5/v26` 同步走弱（2/6、2/6、1/6）。
- 结论：
  - “v9 恢复 + v19 壳层底线”解决了 v43 的两个灾难点，但退化迁移到 `v10` 与 `v1/v5`；
  - 本轮继续判定为失败迭代（尚未收敛到核心集稳态）。

### 47.4 风险

- `v9_priority_restore_window` 可能在高 attack 场景下过度放松，导致被 `v10` 族反制（本轮已出现 0/6）。
- `v19` 壳层收紧可能提高防守保守性，压低 `v1/v5` 需要的进攻转换效率。
- 当前仍为精简对手集；并发后端为 `thread_fallback`，边界局结果存在波动，需后续复核。

### 47.5 下一步

1. 增加 `v10_counter_restore_window`：
- 在 `v10` 典型高 initiative + 高 pressure 形态下，对 `v9_restore` 做反向约束，避免过度放开。
2. 给 `v19_shellfloor_guard_window` 加“转换效率护栏”：
- 当 `v1/v5` 进攻窗口满足时，降低壳层收紧强度，防止节奏被壳层策略压死。
3. 继续 `iter + jobs=14` 双 seed 快速验证：
- 目标：保持 `v6/v9/v19` 不低于 `3/6` 的同时，将 `v10` 拉回至少 `2/6`，并把 `v1/v5` 恢复到 `3/6`。

## 48. 本回合增量（2026-03-04，v45，隔离评测）

### 48.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260303_235907`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260304_000011`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v44 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 48.2 算法级改动

新增版本：

- `cpp_v45_v44_v10counter_transition_guard`（`/www/ai_cpp/v45/ai_v45.cpp`，可执行 `/www/ai_cpp/v45/ai_v45`）

核心改动（相对 v44，v10 反制 + v1/v5 转换护栏）：

1. 新增 `v10_counter_restore_window`：
- 当 `v9_priority_restore_window` 在高 pressure + 高 initiative + 高 attack 条件下可能“过放”时触发；
- 通过 `v9_priority_restore_effective` 抑制 restore 生效，避免被 `v10` 族反制。

2. 新增 `v1_v5_transition_guard_window`：
- 在 `v1/v5` 需要转换效率的进攻窗口，对 `v19_shellfloor_guard` 做动态放松；
- 目标是在保留 v19 壳层底线的同时减少对进攻节奏的压制。

3. 门控联动重构：
- `v6_priority_effective` 改为基于 `v9_priority_restore_effective`；
- `v6_floor_block`、`counter_v6_2ply_bonus_cap`、`counter_hardline_pulse_bonus_cap` 同步使用新联动，统一优先级。

### 48.3 可复现实验（已执行，隔离 scope）

编译命令：

- `g++ -std=c++17 -O2 -pipe /www/ai_cpp/v45/ai_v45.cpp -o /www/ai_cpp/v45/ai_v45`

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v45_v44_v10counter_transition_guard --exe /www/ai_cpp/v45/ai_v45 --src /www/ai_cpp/v45/ai_v45.cpp --notes "v44 + v10 counter-restore gate + v1/v5 transition guard for v19 shellfloor"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v45_v44_v10counter_transition_guard --opponents cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260416`

结果：

- 轮次：`eval_20260304_001625`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_001625_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_001625_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v45_v44_v10counter_transition_guard` 88/156（56.4%），Elo 1575.28（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v45 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=1/6`、`v5=2/6`、`v6=5/6`、`v9=4/6`、`v10=4/6`、`v19=2/6`
  - 定向族群：`v22=3/6`、`v25=2/6`、`v26=1/6`、`v27=2/6`
  - 对比近邻：`vs v44=1/6`、`vs v43=5/6`、`vs v42=4/6`、`vs v41=3/6`、`vs v40=2/6`

解读：

- 改善点：
  - `v10` 从 v44 的 0/6 回升到 4/6；
  - `v9` 从 3/6 升到 4/6；
  - `v6` 升到 5/6，说明反制窗口有效抑制了“过放”副作用。
- 失败点：
  - `v19` 从 4/6 回落到 2/6；
  - `v1/v5` 仍低（1/6、2/6）；
  - 与直接前代 `v44` 头对头仅 1/6，稳定性不足。
- 结论：
  - 本轮实现了 `v10` 灾难点修复，但退化再次迁移到 `v19/v1`，且对前代优势不稳；
  - 继续判定为失败迭代（未达到核心集均衡目标）。

### 48.4 风险

- `v10_counter_restore_window` 可能触发过频，导致 `v9_restore` 被过度抑制，间接伤害 `v19` 与 `v1` 转换。
- `v1_v5_transition_guard_window` 当前只做了 guard 强度缩放，可能不足以抵消壳层收紧的硬约束副作用。
- 当前仍是精简对手集，且 `thread_fallback` 下边界局波动存在，需多 seed 复核。

### 48.5 下一步

1. 给 `v10_counter_restore_window` 增加去抖（hysteresis）：
- 仅在连续回合满足条件时生效，降低一次性尖峰触发导致的误抑制。
2. 分离 `v19` 的 soft/hard 壳层收紧：
- 在 `v1/v5` 转换窗口只放松 hard margin，保留 soft floor，减少“全松/全紧”切换抖动。
3. 继续 `iter + jobs=14` 双 seed 快速验证：
- 目标：保持 `v9/v10/v6` 不低于 `4/6`，同时把 `v19` 拉回至少 `3/6`，`v1` 提升到 `2/6~3/6`。

## 49. 本回合增量（2026-03-04，v46，隔离评测）

### 49.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260304_002818`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260304_001625`）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v45 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 49.2 算法级改动

新增版本：

- `cpp_v46_v45_hysteresis_softhard_shell`（`/www/ai_cpp/v46/ai_v46.cpp`，可执行 `/www/ai_cpp/v46/ai_v46`）

核心改动（相对 v45，v10 去抖 + v19 软硬分离）：

1. 为 `v10_counter_restore_window` 增加连续触发去抖：
- 新增 `arb_v10_counter_streak` 连续计数；
- `v10_counter_restore_signal` 只有在 `streak>=2` 时才升级为有效窗口，降低单回合尖峰误触发。

2. 拆分 `v19` 壳层保护为 soft/hard 两路：
- 新增 `v19_shellfloor_soft_guard` 与 `v19_shellfloor_hard_guard`；
- `v1_v5` 转换窗口下只“轻放松 soft、重放松 hard”，避免此前一把梭式同步放松。

3. 壳层参数映射更新：
- `shell_safety_drop_cap` 使用 `soft_guard`；
- `shell_hard_margin` 使用 `hard_guard`；
- 使壳层收紧从单参数耦合改为双通道控制。

### 49.3 可复现实验（已执行，隔离 scope）

编译命令：

- `g++ -std=c++17 -O2 -pipe /www/ai_cpp/v46/ai_v46.cpp -o /www/ai_cpp/v46/ai_v46`

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v46_v45_hysteresis_softhard_shell --exe /www/ai_cpp/v46/ai_v46 --src /www/ai_cpp/v46/ai_v46.cpp --notes "v45 + v10 counter hysteresis + split v19 shellfloor soft/hard relaxation"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v46_v45_hysteresis_softhard_shell --opponents cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v39_v38_release_protect_v6v19,cpp_v38_v37_segmented_guardrail_release,cpp_v37_v34_narrow_guardrail,cpp_v36_v34_guardrail_only,cpp_v35_midpulse_guardrail,cpp_v34_split_pulse_recovery,cpp_v33_v32_hardline_recovery_lane,cpp_v32_v29_narrow_v2burst,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260417`

结果：

- 轮次：`eval_20260304_002928`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_002928_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_002928_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v46_v45_hysteresis_softhard_shell` 87/162（53.7%），Elo 1587.84（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v46 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=2/6`、`v5=2/6`、`v6=3/6`、`v9=5/6`、`v10=5/6`、`v19=5/6`
  - 定向族群：`v22=2/6`、`v25=2/6`、`v26=2/6`、`v27=0/6`
  - 对比近邻：`vs v45=0/6`、`vs v44=4/6`、`vs v43=3/6`、`vs v42=3/6`、`vs v41=3/6`、`vs v40=3/6`

解读：

- 改善点：
  - `v9/v10/v19` 全部拉升到 5/6；
  - 相比 v45，`v19` 从 2/6 修复到 5/6，说明 soft/hard 分离有效。
- 失败点：
  - `v27=0/6` 出现新灾难点；
  - `v6` 从 5/6 回落到 3/6；
  - 与直接前代 `v45` 头对头为 0/6，稳定性不足。
- 结论：
  - 去抖 + 壳层分离修复了 `v9/v10/v19`，但退化迁移到 `v27` 与 `v45` 对位；
  - 本轮继续判定为失败迭代（核心集仍不均衡）。

### 49.4 风险

- `v10` 去抖门控可能与中压族群门控耦合，导致 `v27` 分支在高压场景被意外压穿。
- soft/hard 分离后参数维度上升，跨对手迁移退化概率上升。
- 当前仍为精简对手集，且 `thread_fallback` 下边界局有波动，需多 seed 复核。

### 49.5 下一步

1. 新增 `v27_priority_safeguard_window`：
- 在 `v27` 典型中压形态下，为中压/transition 通道设最小保活，避免被 v10 去抖连带压制。
2. 对 `v10_counter_restore` 与 `v27` 门控做互斥白名单：
- 当 `v27` 保活窗口触发时，限制 v10 去抖门控继续收紧。
3. 继续 `iter + jobs=14` 双 seed 快速验证：
- 目标：保持 `v9/v10/v19>=4/6` 的同时把 `v27` 拉回至少 `2/6~3/6`，并维持 `v6>=3/6`。

## 50. 本回合增量（2026-03-04，v47，隔离评测）

### 50.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260304_005023`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260304_005050`，seed=20260418）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v46 回合）
- 本回合为 continue：沿用已落地的 v47 代码，补做第二个 seed 的隔离复现实验并回写结论。

### 50.2 算法级改动（已落地代码）

版本：

- `cpp_v47_v46_v27_safeguard_mutex`（`/www/ai_cpp/v47/ai_v47.cpp`，可执行 `/www/ai_cpp/v47/ai_v47`）

核心改动（相对 v46）：

1. 新增 `v27_priority_safeguard_window`：
- 在 `v27` 中压形态触发时，开启中压与 transition 通道的最小保活窗口。

2. 新增 `v27_v10_mutex_whitelist`：
- 当 `v27` 保活窗口触发时，对 `v10_counter_restore` 做互斥白名单，避免 v10 收紧链路继续压制 v27 通道。

3. 新增 v27 定向 floor 兜底：
- 引入 `v27_midpressure_floor` 与 `v27_transition_floor`；
- 在 `v10_counter_restore_window` 命中时分别额外放大 `1.06 / 1.04`，用于抵消 v10 收紧副作用。

### 50.3 可复现实验（已执行，隔离 scope）

编译命令：

- `g++ -std=c++17 -O2 -pipe /www/ai_cpp/v47/ai_v47.cpp -o /www/ai_cpp/v47/ai_v47`

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v47_v46_v27_safeguard_mutex --exe /www/ai_cpp/v47/ai_v47 --src /www/ai_cpp/v47/ai_v47.cpp --notes "v46 + v27 safeguard floors + v10 counter mutex whitelist"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v47_v46_v27_safeguard_mutex,cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v47_v46_v27_safeguard_mutex --opponents cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260419`

结果：

- 轮次：`eval_20260304_005422`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_005422_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_005422_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v47_v46_v27_safeguard_mutex` 55/120（45.8%），Elo 1535.97（该轮第 2）
- 分对手（按 `matches` 基于 `score_a` 复算，v47 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=2/6`、`v5=0/6`、`v6=2/6`、`v9=3/6`、`v10=5/6`、`v19=4/6`
  - 定向族群：`v22=2/6`、`v25=3/6`、`v26=2/6`、`v27=2/6`
  - 对比近邻：`vs v46=1/6`、`vs v45=3/6`、`vs v44=2/6`、`vs v43=3/6`、`vs v42=3/6`、`vs v41=2/6`、`vs v40=2/6`

解读：

- 改善点：
  - `v10` 拉升到 `5/6`；
  - `v19` 回到 `4/6`；
  - `v27` 从 v46 回合的 `0/6` 修复到 `2/6`，保活窗口方向有效。
- 失败点：
  - `v5` 退化到 `0/6`；
  - `v6/v2/v1` 均停在 `2/6`；
  - 对直接前代 `v46` 仅 `1/6`，稳定性不足。
- 结论：
  - v27 定向保活解决了“完全崩塌”，但引入了对 `v5/v6` 与近邻对位的系统性副作用；
  - 本轮继续判定为失败迭代（未达到核心集均衡目标）。

### 50.4 风险

- `v27` 保活 floor 当前为静态抬升，可能在非 v27 对手上导致“过保守 + 节奏丢失”，拖累 `v5/v6`。
- `v27_v10_mutex_whitelist` 让 v10 收紧链路失效的时机可能过宽，出现对近邻版本（尤其 v46）对位退化。
- 本轮对手集较窄（20 对手），且后端为 `thread_fallback`，仍需后续多 seed/扩对手集确认泛化。

### 50.5 下一步

1. 将 `v27_midpressure_floor / transition_floor` 改为连续值（按 `pressure/initiative` 分段插值）：
- 避免当前二值开关导致的“开了太猛、关了太弱”。
2. 给 `v27_v10_mutex_whitelist` 加时序阈值（最小持续回合 + 冷却）：
- 只在 v27 形态稳定出现时屏蔽 v10 收紧，减少误触发。
3. 下一轮继续 `iter + jobs=14`（脚本入口）做双 seed 复验：
- 目标：保持 `v10>=4/6`、`v19>=3/6`、`v27>=3/6`，并把 `v5/v6` 至少拉回 `2/6~3/6`。

## 51. 本回合增量（2026-03-04，v48，隔离评测）

### 51.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260304_005023`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260304_005422`，seed=20260419）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v47 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 51.2 算法级改动

新增版本：

- `cpp_v48_v47_v27continuous_mutexhyst`（`/www/ai_cpp/v48/ai_v48.cpp`，可执行 `/www/ai_cpp/v48/ai_v48`）

核心改动（相对 v47，连续 floor + 互斥时序阈值）：

1. 将 `v27` 保活从二值窗口改为连续强度：
- 新增 `v27_priority_safeguard_strength`，由 `beam/pressure/initiative/attack/chain/jump/hardening` 多信号连续插值计算；
- `v27_priority_safeguard_window` 改为基于强度阈值触发（不再只靠硬条件拼接）。

2. 给 `v27_v10` 互斥增加时序门控：
- 新增 `arb_v27_mutex_streak`、`arb_v27_mutex_cooldown`、`arb_v27_mutex_active_prev`；
- 互斥白名单改为 `signal + 最小持续回合(streak>=2) + 冷却(cooldown==0)` 联合判定，减少误触发。

3. `v27` 中压/transition floor 改为连续缩放：
- `v27_midpressure_floor` 与 `v27_transition_floor` 由 `v27_priority_safeguard_strength` 连续调节；
- 对 `v10_counter_restore_window` 的补偿也改为随强度缩放（避免固定倍率过冲）。

### 51.3 可复现实验（已执行，隔离 scope）

编译命令：

- `g++ -std=c++17 -O2 -pipe /www/ai_cpp/v48/ai_v48.cpp -o /www/ai_cpp/v48/ai_v48`

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v48_v47_v27continuous_mutexhyst --exe /www/ai_cpp/v48/ai_v48 --src /www/ai_cpp/v48/ai_v48.cpp --notes "v47 + continuous v27 safeguard strength + mutex sustain/cooldown hysteresis"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v48_v47_v27continuous_mutexhyst,cpp_v47_v46_v27_safeguard_mutex,cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v48_v47_v27continuous_mutexhyst --opponents cpp_v47_v46_v27_safeguard_mutex,cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260420`

结果：

- 轮次：`eval_20260304_010806`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_010806_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_010806_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v48_v47_v27continuous_mutexhyst` 68/126（54.0%），Elo 1585.70（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v48 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=4/6`、`v5=1/6`、`v6=3/6`、`v9=4/6`、`v10=3/6`、`v19=5/6`
  - 定向族群：`v22=2/6`、`v25=3/6`、`v26=3/6`、`v27=2/6`
  - 对比近邻：`vs v47=3/6`、`vs v46=3/6`、`vs v45=3/6`、`vs v44=3/6`、`vs v43=4/6`、`vs v42=4/6`、`vs v41=2/6`、`vs v40=2/6`

解读：

- 改善点：
  - `v1_current` 从 `2/6` 提升到 `4/6`；
  - `v6` 从 `2/6` 回升到 `3/6`；
  - `v19` 从 `4/6` 提升到 `5/6`；
  - 对 `v46` 对位从 `1/6` 回升到 `3/6`。
- 失败点：
  - `v10` 从 `5/6` 回落到 `3/6`；
  - `v27` 仍为 `2/6`（未达到回合目标）；
  - `v5` 仅 `1/6`，核心短板仍在。
- 结论：
  - 连续 floor + 互斥时序阈值提升了稳态与部分近邻对位，但未达成核心集均衡目标；
  - 本轮判定为“部分改善但未收敛”，需继续迭代。

### 51.4 风险

- `v27` 连续 floor 当前增益仍偏弱，未能把 `v27` 从 `2/6` 拉升到目标区间。
- 互斥冷却机制可能在部分局面抑制了 `v10` 反制强度，导致 `v10` 对位回落。
- 当前对手集仍是精简子集，且 `thread_fallback` 后端存在边界局波动，泛化结论仍需扩集验证。

### 51.5 下一步

1. 将 `v27` floor 增益分成“保活底线 + 压力增益”双通道：
- 保活底线维持稳定，压力增益仅在 `v27` 高置信窗口抬升，避免全局过度保守。
2. 将 `v27_v10` 互斥改为“部分抑制”而非完全屏蔽：
- 引入 `mutex_blend`（例如只削减 `v10_counter_restore` 的一部分强度），争取 `v10` 与 `v27` 同时不崩。
3. 保持 `iter + jobs=14` 继续双 seed 复验：
- 目标：`v10>=4/6`、`v27>=3/6`、`v19>=4/6`，并把 `v5` 提升到至少 `2/6`。

## 52. 本回合增量（2026-03-04，v49，隔离评测）

### 52.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260304_011943`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260304_010806`，seed=20260420）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v48 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 52.2 算法级改动

新增版本：

- `cpp_v49_v48_v27dualfloor_mutexblend`（`/www/ai_cpp/v49/ai_v49.cpp`，可执行 `/www/ai_cpp/v49/ai_v49`）

核心改动（相对 v48，v27 双通道 floor + v10 部分抑制）：

1. `v27_v10` 从完全互斥改为部分抑制：
- 新增 `v10_counter_restore_blend` 与 `v10_counter_restore_pressure`；
- `v27` 互斥命中时不再完全屏蔽 `v10_counter_restore`，而是按强度做连续削减。

2. `v27` midpressure floor 拆分为双通道：
- `base floor` 负责最低保活；
- `pressure boost` 仅在高压窗口叠加增益，减少全局过保守副作用。

3. `v27` transition floor 拆分为双通道：
- `base floor` + `initiative boost`；
- 使 transition 保护只在高主动权窗口进一步抬升。

### 52.3 可复现实验（已执行，隔离 scope）

编译命令：

- `g++ -std=c++17 -O2 -pipe /www/ai_cpp/v49/ai_v49.cpp -o /www/ai_cpp/v49/ai_v49`

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v49_v48_v27dualfloor_mutexblend --exe /www/ai_cpp/v49/ai_v49 --src /www/ai_cpp/v49/ai_v49.cpp --notes "v48 + v27 dual-channel floor + v10 mutex blend (partial suppression)"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v49_v48_v27dualfloor_mutexblend,cpp_v48_v47_v27continuous_mutexhyst,cpp_v47_v46_v27_safeguard_mutex,cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v49_v48_v27dualfloor_mutexblend --opponents cpp_v48_v47_v27continuous_mutexhyst,cpp_v47_v46_v27_safeguard_mutex,cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260421`

结果：

- 轮次：`eval_20260304_012528`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_012528_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_012528_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v49_v48_v27dualfloor_mutexblend` 68/132（51.5%），Elo 1564.56（该轮第一）
- 分对手（按 `matches` 基于 `score_a` 复算，v49 视角）：
  - 核心约束集：`v2=2/6`、`v1_current=4/6`、`v5=1/6`、`v6=2/6`、`v9=2/6`、`v10=2/6`、`v19=2/6`
  - 定向族群：`v22=5/6`、`v25=3/6`、`v26=4/6`、`v27=4/6`
  - 对比近邻：`vs v48=2/6`、`vs v47=4/6`、`vs v46=4/6`、`vs v45=2/6`、`vs v44=3/6`、`vs v43=3/6`、`vs v42=3/6`、`vs v41=2/6`、`vs v40=2/6`

解读：

- 改善点：
  - `v27` 从 `2/6` 提升到 `4/6`，达到本轮重点修复方向；
  - `v22` 从 `2/6` 提升到 `5/6`；
  - 相比 v48，`vs v47` 与 `vs v46` 都提升到 `4/6`。
- 失败点：
  - `v10` 从 `3/6` 回落到 `2/6`；
  - `v19` 从 `5/6` 回落到 `2/6`；
  - `v6` 回落到 `2/6`，`v5` 仍 `1/6`。
- 结论：
  - v27 双通道 floor 有效修复了 v27 族群，但回退迁移到 `v10/v19/v6`；
  - 本轮继续判定为失败迭代（核心集仍未均衡）。

### 52.4 风险

- `v10_counter_restore_blend` 当前削减幅度可能过大，导致 `v10` 相关对位失守。
- v27 增益分配偏向中压族群，可能挤压了 `v19` 的壳层反制空间。
- 对手集虽包含近邻与核心基线，但仍属于精简评测，结论需继续多 seed 复核。

### 52.5 下一步

1. 引入 `v19_protect_backstop`（当 `v27` boost 生效时给 v19 单独保底）：
- 避免修复 v27 时再次压穿 v19。
2. 将 `v10_counter_restore_blend` 改为分段函数：
- 在中等 `v27_strength` 仅轻度削减，在高置信 `v27` 才强削减，争取把 `v10` 拉回 `3/6~4/6`。
3. 继续 `iter + jobs=14` 双 seed 复验：
- 目标：保持 `v27>=3/6` 的前提下，把 `v10/v19` 至少恢复到 `3/6`，并将 `v5` 提升到 `2/6`。

## 53. 本回合增量（2026-03-04，v50，隔离评测）

### 53.1 回合起始状态

- 生产评测最新：`/www/autolab/runtime/latest.json`（启动读取为 `eval_20260304_013922`）
- 迭代评测最新：`/www/autolab/runtime/scopes/iter/latest.json`（启动读取为 `eval_20260304_012528`，seed=20260421）
- 迭代记录基线：`/www/docs/round2_autolab_and_iterations.md`（上一节为 v49 回合）
- 本回合继续严格使用隔离脚本入口，不直接执行会写生产 `latest/champion` 的评测命令。

### 53.2 算法级改动

新增版本：

- `cpp_v50_v49_v19backstop_pieceblend`（`/www/ai_cpp/v50/ai_v50.cpp`，可执行 `/www/ai_cpp/v50/ai_v50`）

核心改动（相对 v49，分段 blend + v19 backstop）：

1. `v10_counter_restore_blend` 改为分段函数：
- 在中低 `v27_strength` 区间只轻度削减 `v10`；
- 在高 `v27_strength` 才进入较强削减，避免过早把 `v10` 压穿。

2. 新增 `v19_protect_backstop`：
- 当 `v27` boost 生效（`v27_backstop_signal` 达阈值）时，给 `counter_v19_rebound_bonus_cap` 设置保底；
- 目标是在修复 `v27` 的同时减少对 `v19` 的连带伤害。

3. 保留 v27 双通道 floor：
- 继续使用 `base floor + pressure/initiative boost` 结构，验证与上述两项联动后的稳定性。

### 53.3 可复现实验（已执行，隔离 scope）

编译命令：

- `g++ -std=c++17 -O2 -pipe /www/ai_cpp/v50/ai_v50.cpp -o /www/ai_cpp/v50/ai_v50`

注册命令：

- `python3 /www/autolab_manage.py register-cpp --version-id cpp_v50_v49_v19backstop_pieceblend --exe /www/ai_cpp/v50/ai_v50 --src /www/ai_cpp/v50/ai_v50.cpp --notes "v49 + piecewise v10 mutex blend + v19 protect backstop under v27 boost"`

评测命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=3 EXPERIMENT_MAX_ROUNDS=170 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v50_v49_v19backstop_pieceblend,cpp_v49_v48_v27dualfloor_mutexblend,cpp_v48_v47_v27continuous_mutexhyst,cpp_v47_v46_v27_safeguard_mutex,cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --challengers cpp_v50_v49_v19backstop_pieceblend --opponents cpp_v49_v48_v27dualfloor_mutexblend,cpp_v48_v47_v27continuous_mutexhyst,cpp_v47_v46_v27_safeguard_mutex,cpp_v46_v45_hysteresis_softhard_shell,cpp_v45_v44_v10counter_transition_guard,cpp_v44_v43_v9restore_v19shellfloor,cpp_v43_v42_v6_priority_floor_gate,cpp_v42_v40_midpressure_floor,cpp_v41_v40_split_cap_whitelist,cpp_v40_v38_targeted_v6v19_cap,cpp_v27_midpressure_counterlane,cpp_v26_pulse_harden_safety_delta,cpp_v25_floorplus_transition_guard,cpp_v22_burst_harden_dynamic_relief,cpp_v19_rebound_shellfloor_guard,cpp_v10_antibeam_gate_release,cpp_v9_emergency_antibeam,cpp_v6_adaptive_2ply,cpp_v5_counterfactual_2ply,cpp_v2_beam,cpp_v1_current,greedy,random_safe --seed 20260422`

结果：

- 轮次：`eval_20260304_013924`（`runtime_scope=iter`）
- iter latest：`/www/autolab/runtime/scopes/iter/latest.json`
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_013924_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_013924_matches.jsonl`
- 并发后端：`backend=thread_fallback`（`jobs=14`）
- 总体：`cpp_v50_v49_v19backstop_pieceblend` 81/138（58.7%），Elo 1601.57（该轮第一）
- 样本说明：本轮总局数 `138`（`>=100`），可用于“相对强度”稳定比较（非 smoke）。
- 分对手（按 `matches` 基于 `score_a` 复算，v50 视角）：
  - 核心约束集：`v2=4/6`、`v1_current=3/6`、`v5=2/6`、`v6=3/6`、`v9=3/6`、`v10=3/6`、`v19=2/6`
  - 定向族群：`v22=2/6`、`v25=4/6`、`v26=3/6`、`v27=4/6`
  - 对比近邻：`vs v49=4/6`、`vs v48=4/6`、`vs v47=5/6`、`vs v46=3/6`、`vs v45=2/6`、`vs v44=4/6`、`vs v43=4/6`、`vs v42=4/6`、`vs v41=4/6`、`vs v40=2/6`

解读：

- 改善点：
  - 在保持 `v27=4/6` 的同时，`v10` 从 `2/6` 回升到 `3/6`；
  - `v6` 从 `2/6` 回升到 `3/6`；
  - `v5` 从 `1/6` 回升到 `2/6`；
  - `v2` 从 `2/6` 提升到 `4/6`。
- 失败点：
  - `v19` 仍停留在 `2/6`，`v19_protect_backstop` 未达预期修复目标；
  - `v22` 从 `5/6` 回落到 `2/6`。
- 结论：
  - v50 相比 v49 在整体稳态与多组核心约束上明显改善，但 `v19` 仍是主短板；
  - 本轮结论为“有效改进但未完全收敛”。

### 53.4 风险

- `v19_protect_backstop` 触发条件可能仍偏保守，导致实际命中不足。
- 分段 blend 目前对 `v10` 的恢复有效，但在 `v45/v40` 对位上仍有边界退化（均 `2/6`）。
- 仍是单 seed 结果，虽然局数达标，但建议再做第二 seed 复核稳定性。

### 53.5 下一步

1. 提升 `v19_protect_backstop` 覆盖率：
- 将 `v27_backstop_signal` 触发阈值做轻度下调，并增加对 `chain_pressure` 的联合门控。
2. 对 `v10` blend 再做“对手态分流”：
- 在 `v45/v40` 形态下降低削减幅度，避免边界对位继续回落。
3. 继续 `iter + jobs=14` 双 seed 验证：
- 目标：保持 `v27>=3/6`、`v10>=3/6`、`v5>=2/6` 的同时，把 `v19` 提升到 `3/6`。

## 54. 定向复核（2026-03-04，v45-v50 单独对战 v1，隔离评测）

### 54.1 目的

- 验证“后续叠代版本是否整体不如 v1”这一核心质疑；
- 使用大于 smoke 的样本量，避免 6 局级别对局导致误判。

### 54.2 可复现实验

执行命令（iter scope，不写生产 champion）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=60 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v45_v44_v10counter_transition_guard,cpp_v46_v45_hysteresis_softhard_shell,cpp_v47_v46_v27_safeguard_mutex,cpp_v48_v47_v27continuous_mutexhyst,cpp_v49_v48_v27dualfloor_mutexblend,cpp_v50_v49_v19backstop_pieceblend,cpp_v1_current --challengers cpp_v45_v44_v10counter_transition_guard,cpp_v46_v45_hysteresis_softhard_shell,cpp_v47_v46_v27_safeguard_mutex,cpp_v48_v47_v27continuous_mutexhyst,cpp_v49_v48_v27dualfloor_mutexblend,cpp_v50_v49_v19backstop_pieceblend --opponents cpp_v1_current --seed 20260304`

产物：

- 轮次：`eval_20260304_052738`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_052738_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_052738_matches.jsonl`
- 总局数：`720`（每个新版本对 `v1` 为 `120` 局）

### 54.3 结果与统计判读

按版本对 `v1` 胜率（`wins/120`）：

- `v45`：`42/120`（35.0%）  
  - 95% CI `[27.1%, 43.9%]`，显著低于 50%
- `v46`：`53/120`（44.2%）  
  - 95% CI `[35.6%, 53.1%]`，不显著低于 50%
- `v47`：`58/120`（48.3%）  
  - 95% CI `[39.6%, 57.2%]`，与 50% 无显著差异
- `v48`：`46/120`（38.3%）  
  - 95% CI `[30.1%, 47.3%]`，显著低于 50%
- `v49`：`48/120`（40.0%）  
  - 95% CI `[31.7%, 48.9%]`，显著低于 50%
- `v50`：`60/120`（50.0%）  
  - 95% CI `[41.2%, 58.8%]`，与 50% 持平

### 54.4 结论

1. “后续叠代版本普遍优于 v1”不成立；本次 `v45-v50` 无一版本显著强于 `v1`。
2. 其中 `v45/v48/v49` 在本轮样本下可判为“显著弱于 v1”；`v46/v47/v50` 只能判为“与 v1 接近”。
3. 因此该分支存在明显“高迭代密度但真实提升不足”的问题，不能继续按原方向无约束叠版。

### 54.5 后续动作建议

1. 对 `v45-v50` 分支设置“硬门禁”：若对 `v1` 在 `>=120` 局下未达 `>55%`，禁止晋升为主分支候选。
2. 研发优先回到“v1/v5/v6 主干”并做结构级创新（搜索/估值/动作层解耦），而非继续微调 v10/v19/v27 互斥参数。
3. 继续保留 `v50` 作为“局部对位修复参考”，但不作为生产 champion 候选。

## 55. 本回合增量（2026-03-04，v52/v53 深度重构与复验）

### 55.1 背景与目标

- 问题：后续高版本大量叠加后，生产表现整体仍落后 `v1`，疑似“结构上过拟合 + 评估器漂移”。
- 目标：做一次根本性策略重构，验证“是否能在大样本 head-to-head 中稳定超过 v1”。

### 55.2 v52：宏观稳健搜索（失败版）

新增版本：

- `cpp_v52_robust_minimax_lane`（`/www/ai_cpp/v52/ai_v52.cpp`，可执行 `/www/ai_cpp/v52/ai_v52`）

核心改动：

1. 从单步贪心改为“候选动作池 + 敌方近似应手 + 稳健评分”的轻量 minimax 选步。
2. 新增宏观局面估值（兵力、占格、前线、中心、主将安全、敌主将压力）驱动动作仲裁。

评测（iter，100 局，对手仅 `v1`）：

- 轮次：`eval_20260304_054223`
- 命令：`games_per_pair=50`（含换先共 100 局）
- 结果：`v52` 26/100（26.0%），显著弱于 `v1`

失败结论：

- 宏观估值函数与实际战术收益不一致，导致动作选择系统性偏离；
- 虽有“对手应手”结构，但估值偏差放大后反而比 `v1` 更差。

### 55.3 v53：回归 v1 内核 + 轻量对手惩罚（成功版）

新增版本：

- `cpp_v53_overlay_countercheck`（`/www/ai_cpp/v53/ai_v53.cpp`，可执行 `/www/ai_cpp/v53/ai_v53`）

核心改动（相对 v1）：

1. 保留 `v1` 原始动作打分/经济节奏（稳健内核不动）。
2. 在选步层增加“overlay counter-check”：
   - 先生成 top 候选动作池；
   - 对每个候选做一步敌方应手近似惩罚；
   - 只在 overlay 分显著优于基线时替换，否则回退 `v1` 贪心动作。
3. 这样做的本质是：把 `v1` 当保底策略，只在“确定更优”时出手。

评测（iter，`v53` 单独对 `v1`，双 seed）：

- 轮次 A：`eval_20260304_054626`（seed=20260306）  
  - `v53` 64/100（64.0%）
- 轮次 B：`eval_20260304_054848`（seed=20260307）  
  - `v53` 63/100（63.0%）

合并样本（A+B）：

- `127/200`（63.5%）
- 95% CI：`[56.63%, 69.86%]`
- 双侧二项检验（对 50%）：`p=0.000164`

结论：

- 在当前 head-to-head 口径下，`v53` 已显著强于 `v1`；
- 与 `v52` 对比可见：结构创新不是问题，关键是“创新层必须依附稳定内核并可回退”。

### 55.4 多对手 smoke（方向性验证）

评测：

- 轮次：`eval_20260304_055621`（iter，seed=20260308）
- 配置：`games_per_pair=10`（每个对手 20 局，含换先）
- 对手集：`v1/v2/v5/v6/v40/v47/v50`

`v53` 分项结果（v53 视角）：

- vs `v1_current`：`13/20`（65.0%）
- vs `v2_beam`：`14/20`（70.0%）
- vs `v5_counterfactual_2ply`：`14/20`（70.0%）
- vs `v6_adaptive_2ply`：`13/20`（65.0%）
- vs `v40_v38_targeted_v6v19_cap`：`17/20`（85.0%）
- vs `v47_v46_v27_safeguard_mutex`：`17/20`（85.0%）
- vs `v50_v49_v19backstop_pieceblend`：`12/20`（60.0%）

结论：

- 方向上，`v53` 不仅克 `v1`，对当前抽样强对手集也呈正胜率；
- 但每对手仅 20 局，仍属于 smoke，不能替代正式判优门槛。

### 55.5 下一步

1. 把 `v53` 纳入“多对手验证池”（`v1/v2/v5/v6/v40/v45/v47/v50`）做每对手 `>=100` 局验证。
2. 若 `v53` 对关键对手均 `>55%`，再进入生产候选流程（避免单对手最优）。
3. 继续迭代时坚持：先保底回退，再放开创新分支，禁止直接替换核心打分。

## 56. 生产 Elo（精简后）复盘与判读修正（2026-03-04）

### 56.1 新一轮生产评测事实

- 轮次：`eval_20260304_064305`
- 路径：`/www/autolab/runtime/eval_20260304_064305_summary.json`
- 配置：`mode=gauntlet`，`games_per_pair=6`，`matches=720`
- champion：`cpp_v2_beam -> cpp_v1_current`（本轮发生晋升）
- 关键排名：
  - `#1 cpp_v1_current 1669.39`
  - `#10 cpp_v53_overlay_countercheck 1550.74`
  - `#21 cpp_v2_beam 1406.83`

### 56.2 为什么本轮与上一轮看起来“反转”

本项目当前生产评测是 gauntlet 模式，默认对手集依赖当轮 `champion`：

1. 当 `champion=v1`（如 `eval_20260304_061650`），challenger 主要对 `v1 + anchors` 打。
2. 当 `champion=v2`（如 `eval_20260304_064305`），challenger 主要对 `v2 + anchors` 打。

因此不同 tag 的 Elo 绝对值并不处于同一“参照系”。
这会导致“上一轮 v2 高、下一轮 v1 高”的表观跳变，不应直接解读为算法强弱瞬时翻转。

### 56.3 小样本不稳定性的直接证据

`v1` vs `v2` 在两轮生产数据中的直接对战（都只有 12 局）：

- `eval_20260304_061650`：`v1` 为 `4/12`（33.3%，95% CI `[13.8%, 60.9%]`）
- `eval_20260304_064305`：`v1` 为 `7/12`（58.3%，95% CI `[32.0%, 80.7%]`）

两轮结论方向相反，且置信区间很宽，说明 `games_per_pair=6` 下关键 pair 的统计稳定性不足。

### 56.4 对当前 Elo 的正确使用方式

1. 生产 Elo 仍是“唯一权威榜单”，但单轮 gauntlet 更适合做“候选信号”，不适合做最终判优。
2. 版本优劣结论必须落到大样本 head-to-head 或固定对手池复验：
   - 两版本比较至少 `>=100` 局（建议 `>=200` 局）。
   - 多版本排序优先用更大样本（如固定池 `>=1000` 局）再定论。
3. 生产晋升若与近期结论冲突，应先复验再解读，避免 champion 在小样本下来回摆动。

### 56.5 对 codex 自动迭代的动作修正（已同步到目标文档）

1. 新增硬要求：搜索/前瞻方法必须实现“单步 CPU `<=200ms`”强制截止与回退（按 CPU 计时口径，不可仅用 wall-clock 近似）。
2. 每回合必须在文档写明：
   - 本轮生产 gauntlet 的对手池结构（是否受 champion 切换影响）；
   - 判优是否达到 `>=100/200` 局门槛；
   - 是否存在超时风险与缓解方案。
3. 默认流程改为：smoke（20局）-> gate（100局）-> confirm（200局或1000+局大池）。

### 56.6 硬约束落地（v54 搜索计时口径）

1. 自动迭代产出的 `v54` 初版使用 `steady_clock`（wall-clock）做截止，不满足“CPU 时间口径”硬要求。
2. 已修正为线程 CPU 计时口径：
   - 使用 `CLOCK_THREAD_CPUTIME_ID` 读取线程 CPU 时间；
   - 以 `kSearchStepBudgetMs=200` 生成 CPU deadline；
   - 超时立即中断后续搜索分支并回退当前最佳候选。
3. 修正后重新编译 `v54`；为避免“前后两个二进制混样本”，已终止旧的进行中 `v54` 实验，后续需以新二进制重跑。

## 57. 本回合增量（2026-03-04，v54 CPU 计时硬截止 + gate 复验）

### 57.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_072325`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 里 challenger 主要对 `cpp_v1_current + anchors(greedy/random_safe)`，说明本轮对手池仍按旧 champion（`v1`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（本轮更新后为 `eval_20260304_072425`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. 在 gauntlet 下，本轮生产对手池明显受 champion 切换影响（高优先级风险）。
2. 生产 Elo 仍是唯一权威；iter Elo 仅用于候选筛选，禁止跨 scope 比较 Elo 绝对值。

### 57.2 算法级改动（已落代码）

版本：

- `cpp_v54_overlay_adaptive_timeout`
- 源码：`/www/ai_cpp/v54/ai_v54.cpp`

关键机制（相对 v53）：

1. 搜索硬截止改为 CPU 计时口径（满足硬约束）：
   - 使用 `CLOCK_THREAD_CPUTIME_ID` 读取线程 CPU 时间；
   - 单回合共享 `kSearchStepBudgetMs=200` 的 CPU deadline；
   - 截止触发后立即终止后续搜索分支并回退当前最佳候选（保底可退回 base 候选）。
2. overlay 搜索做自适应扩展：
   - 候选池宽度按局势动态调节（主将危险度、回合阶段、接敌距离、机动层级）。
3. 增加置信提前停止：
   - 当当前最佳候选与次优候选分差足够大时提前停止搜索，避免无效扩展。
4. 修正一手应手评估的主将定位：
   - `select_best_move_base` 改为按 `player` 动态定位己方/敌方主将，避免敌方应手模拟误用我方主将坐标。

### 57.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发，不写生产 champion）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=60 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v54_overlay_adaptive_timeout,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v54_overlay_adaptive_timeout --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck --seed 20260309`

产物：

- 轮次：`eval_20260304_072425`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_072425_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_072425_matches.jsonl`
- 总局数：`360`（每个关键对手 `120` 局，达到 `>=100` gate 门槛）

`v54` 分对手结果（head-to-head）：

- vs `v1_current`：`75/120`（62.5%，95% CI 约 `[53.6%, 70.7%]`）
- vs `v2_beam`：`75/120`（62.5%，95% CI 约 `[53.6%, 70.7%]`）
- vs `v53_overlay_countercheck`：`55/120`（45.8%，95% CI 约 `[37.2%, 54.7%]`）

判读：

1. 对双关键基线（`v1/v2`）均达到 gate 级正优势（样本 `>=100` 且胜率 `>55%`）。
2. `v54` 仍弱于 `v53`，因此“v54 全面优于上一代”不成立。
3. 本轮尚不满足“明确优于 k 个老版本”的严格宣称门槛（未达每对手 `>=200` 局，且未有 `>=1000` 局固定池稳定榜首）。

### 57.4 回到生产口径的结论

生产最新（`eval_20260304_072325`）：

- `champion`: `v1 -> v2`（发生切换）
- `v53` Elo：`1570.73`
- `v54` Elo：`1545.17`（低于 `v53`）
- `v54` 在本轮 gauntlet 的直接统计为 `34/36`，但该统计建立在“对手池含旧 champion=v1”的单轮口径上。

结论：

1. 生产口径与 iter gate 联合看，`v54` 目前应作为“对 v1/v2 改善但未超过 v53”的候选分支。
2. 由于本轮 gauntlet 对手池受 champion 切换影响，不能把本轮生产 Elo 绝对值直接外推为稳定强弱排序。

### 57.5 风险与下一步

风险：

1. 虽有 200ms CPU 硬截止，但 `v54` 评测耗时明显增加，说明搜索仍偏重，吞吐风险存在。
2. 对 `v53` 的劣势说明“自适应扩展 + 提前停止”尚未在强对手上找到合适平衡点。

下一步：

1. confirm：补做 `v54 vs v1/v2/v53` 每对手 `>=200` 局（或固定池 `>=1000` 局）以完成最终判优。
2. 剪枝优化：下调高压场景下候选扩展上限，优先保留“高价值高置信”分支，降低平均搜索开销。
3. 若生产 gauntlet 与后续 confirm 冲突，按规则先做 head-to-head 复验（`>=100`，建议 `200`）再下结论。

### 57.6 回合末强制自检

1. 是否触发搜索时间硬截止：
   - 代码路径已实现并生效（`hard_cutoff_hit` 分支 + CPU deadline 中断）。
   - 评测框架当前不直接暴露逐步命中计数；本轮无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 主要风险点在 overlay 候选展开与双侧应手评估；
   - 现有实现通过单回合共享 CPU deadline 做硬截断，理论上可防止超过预算。
3. 若仍有风险，下一轮降复杂度方案：
   - 收紧候选池上限（尤其高压态）；
   - 提前停止阈值前置（减少低收益分支评估）；
   - 在不影响主将安全约束前提下减少重复 threat 计算次数。

## 58. 本回合增量（2026-03-04，v55 dual-mode overlay 剪枝）

### 58.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_073256`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v2_beam -> cpp_v1_current`
  - `config.pairs` 里 challenger 主要对 `cpp_v2_beam + anchors(greedy/random_safe)`，说明本轮对手池按旧 champion（`v2`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. gauntlet 口径下，本轮生产对手池受 champion 切换影响，属于高优先级风险。
2. 生产 Elo 仍为唯一权威；iter Elo 仅做候选筛选，不跨 scope 比较绝对值。

### 58.2 算法级改动（已落代码）

版本：

- `cpp_v55_overlay_dualmode_prune`
- 源码：`/www/ai_cpp/v55/ai_v55.cpp`

核心机制（相对 v54）：

1. 保持 CPU 硬截止与回退（硬约束保持）：
   - `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`；
   - 超时后经 `hard_cutoff_hit` 中断剩余搜索并回退当前最优动作。
2. 新增 dual-mode overlay（算法级策略分流）：
   - 高压模式：放宽 overlay 参与、提高敌方应手惩罚权重；
   - 平稳模式：限制候选池上限，增加换招惩罚与更高切换门槛。
3. 新增 overlay 启用门：
   - 对“高置信 base 决策”（例如开局低风险、显著战术高分）直接跳过 overlay，减少无效搜索。
4. 候选生成中的敌主将定位泛化：
   - `collect_move_candidates_base` 内按 `player` 动态推导 `enemy_main`，避免固定座位视角偏差。

### 58.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v55_overlay_dualmode_prune,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v55_overlay_dualmode_prune --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck --seed 20260310`

产物：

- 轮次：`eval_20260304_074045`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_074045_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_074045_matches.jsonl`
- 总局数：`300`（每个对手 `100` 局，达到两版本结论门槛）

`v55` 分对手结果（head-to-head）：

- vs `v1_current`：`56/100`（56.0%，95% CI 约 `[46.2%, 65.3%]`）
- vs `v2_beam`：`61/100`（61.0%，95% CI 约 `[51.2%, 70.0%]`）
- vs `v53_overlay_countercheck`：`43/100`（43.0%，95% CI 约 `[33.7%, 52.8%]`）

判读：

1. `v55` 对 `v2` 有正向信号；对 `v1` 仅弱正、置信区间跨 50%，不能判显著优势。
2. `v55` 对 `v53` 为明确负向（43/100），未达候选替代目标。
3. 因此本轮 `v55` 不能作为“优于 v53 的新主线”结论。

### 58.4 回到生产口径的结论

生产最新（`eval_20260304_073256`）显示：

- 本轮 champion 从 `v2` 切到 `v1`；
- 但 pair 池仍以 `v2 + anchors` 为挑战对手口径。

结论：

1. 该轮生产 Elo 仍受对手池切换影响，不能与其他轮次做 Elo 绝对值直比。
2. 结合 iter gate，本轮对 `v55` 的稳健结论为：`regression`（相对 `v53`）。

### 58.5 风险与下一步

风险：

1. dual-mode overlay 虽降低部分无效切换，但在对 `v53` 的关键对位仍未收敛。
2. `v1` 对位表现不稳定（置信区间跨 50%），需要更大样本确认。

下一步：

1. 针对 `v53` 失败样本做定向 ablation：分别关闭“平稳态跳过”“switch penalty”“early-stop gap”以定位主退化源。
2. 若继续验证 `v55`，优先做 `v55 vs v53` `>=200` 局 confirm，再决定是否保留该分支。
3. 若生产 gauntlet 与直接对战冲突，继续按规则先做 `>=100`（建议 `>=200`）head-to-head 复验。

### 58.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径可触达（`hard_cutoff_hit` + CPU deadline）；
   - 当前评测框架未输出逐步触发计数，无法给出精确次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 候选展开与敌我应手评估；
   - 通过 `CLOCK_THREAD_CPUTIME_ID` 的强制截止与回退路径控制上限。
3. 若有风险，下轮降复杂度方案：
   - 在高压模式继续收窄 pool 上限；
   - 提前停止阈值前移，减少低增益分支；
   - 对 repeated threat 计算做缓存或复用，减少重复 CPU 消耗。

## 59. 本回合增量（2026-03-04，v56 base-anchor 正则 + raw-drop 硬剪枝）

### 59.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_075323`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v2_beam -> cpp_v1_current`
  - `config.pairs` 显示挑战集合主要是“各版本 vs `cpp_v2_beam` + anchors(`greedy/random_safe`)”，说明该轮对手池按旧 champion（`v2`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（本轮先 gate=`eval_20260304_080032`，后 confirm=`eval_20260304_080942`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. gauntlet 口径下，对手池受 champion 切换影响，属于高优先级风险，不能把不同轮次 Elo 绝对值直接当稳定强弱结论。
2. 生产 Elo 仍是唯一权威；iter Elo 仅用于候选筛选，不跨 scope 比较绝对值。

### 59.2 算法级改动（已落代码）

版本：

- `cpp_v56_overlay_baseanchor_prune`
- 源码：`/www/ai_cpp/v56/ai_v56.cpp`

关键机制（相对 v55）：

1. 保留 CPU 时间硬截止与保底回退（硬约束继续满足）：
   - 使用 `CLOCK_THREAD_CPUTIME_ID`；
   - `kSearchStepBudgetMs=200`；
   - 达到 deadline 时通过 `hard_cutoff_hit` 中断后续搜索并回退当前最优候选。
2. 新增 base-anchor 正则（抑制过激换招）：
   - overlay 评分新增 `base_anchor_penalty * raw_drop` 惩罚；
   - 在平稳态提高 anchor 惩罚、在高压态降低惩罚，减少对基线高价值动作的无效偏离。
3. 新增 raw-drop 硬剪枝（搜索空间裁剪）：
   - 对相对 base 分数跌幅过大的候选直接丢弃（`max_raw_drop`）；
   - 平稳态阈值更紧、高压态阈值更宽，优先把计算预算用于高价值候选。

### 59.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v56_overlay_baseanchor_prune,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v56_overlay_baseanchor_prune --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck --seed 20260311`

产物：

- 轮次：`eval_20260304_080032`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_080032_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_080032_matches.jsonl`
- 总局数：`300`（每个关键对手 `100` 局，达到两版本比较 `>=100` 门槛）

`v56` 分对手结果（head-to-head）：

- vs `v1_current`：`57/100`（57.0%）
- vs `v2_beam`：`63/100`（63.0%）
- vs `v53_overlay_countercheck`：`45/100`（45.0%）

判读：

1. `v56` 对 `v1/v2` 延续正向信号（样本满足 `>=100`）。
2. `v56` 对 `v53` 仍为负向（45/100），关键替代目标未达成。
3. 本轮仅达到 gate 级，不满足“明确优于 k 个老版本”的 `>=200`/对手或大样本 Elo 条件。

补充 confirm 复验（关键对手 `v53`，`>=200` 局）：

- 执行命令：
  - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=100 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v56_overlay_baseanchor_prune,cpp_v53_overlay_countercheck --challengers cpp_v56_overlay_baseanchor_prune --opponents cpp_v53_overlay_countercheck --seed 20260312`
- 产物：
  - 轮次：`eval_20260304_080942`（`runtime_scope=iter`）
  - 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_080942_summary.json`
  - 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_080942_matches.jsonl`
  - 总局数：`200`
- 结果：
  - vs `v53_overlay_countercheck`：`74/200`（37.0%）

confirm 判读：

1. `v56` 相对 `v53` 的退化在 `>=200` 样本下稳定存在，不是小样本抖动。
2. 因此 `v56` 不能作为 `v53` 的候选替代版本。

### 59.4 回到生产口径的结论

生产最新（`eval_20260304_075323`）显示：

- champion 发生 `v2 -> v1` 切换；
- 该轮 `config.pairs` 仍以旧 champion=`v2` 为挑战对手池核心；
- 生产列表尚未纳入 `v56`，因此当前不能给出 `v56` 的生产 Elo 结论，也不能宣称可替代现有 champion。

结论：

1. 从生产治理口径看，`v56` 目前仅是 iter 候选，状态为“对 `v1/v2` 有提升，但相对 `v53` 在 gate（45/100）与 confirm（74/200）均退化”。
2. 在 gauntlet 对手池随 champion 切换的前提下，需继续使用固定关键对手 head-to-head 做判优，不以单轮生产 Elo 排名做外推。

### 59.5 风险与下一步

风险：

1. `v56` 仍未修复对 `v53` 的关键对位退化，说明当前 overlay 惩罚/剪枝仍可能误杀高价值反制分支。
2. 200ms 硬截止约束主要覆盖 overlay 搜索路径；多步循环中的 threat 重算虽规模较小，但仍是额外 CPU 消耗点。

下一步：

1. 做定向 ablation：分别关闭 `base_anchor_penalty` 与 `max_raw_drop`，定位 `v53` 对位退化主因。
2. 若确认剪枝过硬，下一版按局面风险自适应放宽 `max_raw_drop`，并对“高战术价值候选”增加白名单。
3. 新版先做 smoke（20/对手）筛选，再做 gate（`v1/v2/v53` 各 `>=100`）后决定是否进入 confirm。

### 59.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码实现了 `hard_cutoff_hit` 与 CPU deadline 的强制中断路径；
   - 当前评测产物未输出逐步命中计数，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - overlay 搜索分支受 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` 硬截止控制；
   - 风险点主要在候选展开与双侧应手评估，另有 threat 重算开销（规模小但应继续关注）。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 先做失败样本回放，识别被 `max_raw_drop` 误剪的关键分支；
   - 对平稳态进一步压缩候选池，仅保留高战术分段；
   - 对重复 threat 计算做局部缓存，降低同回合重复 CPU 消耗。

## 60. 本回合增量（2026-03-04，v57 tactical-escape overlay）

### 60.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_082422`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 显示挑战集合主要为“各版本 vs `cpp_v1_current` + anchors(`greedy/random_safe`)”，说明该轮对手池按旧 champion（`v1`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_080942`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. gauntlet 口径下，对手池受 champion 切换影响（高优先级风险），单轮 Elo 绝对值不应跨轮直接外推。
2. 生产 Elo 是唯一权威；iter Elo 仅用于候选筛选，不做跨 scope 绝对值比较。

### 60.2 算法级改动（已落代码）

版本：

- `cpp_v57_overlay_tactical_escape`
- 源码：`/www/ai_cpp/v57/ai_v57.cpp`

关键机制（相对 v56）：

1. 保留 CPU 硬截止与回退（硬约束保持）：
   - `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`；
   - 通过 `hard_cutoff_hit` 中断后续搜索并回退当前最优候选。
2. 新增“战术逃逸候选”机制（算法级结构改动）：
   - 新增 `is_tactical_escape_candidate`，识别“高价值战术候选”（敌将点、重兵关键点、主将近域防守点等）；
   - 对该类候选放宽 raw-drop 剪枝上限（`max_raw_drop + tactical_drop_relax`），降低误剪关键反制分支概率。
3. 新增战术候选的差异化正则：
   - 对战术候选使用更轻的 base-anchor 惩罚（`tactical_anchor_scale`）；
   - 当敌方应手强度受限时追加 `tactical_reply_bonus`，鼓励“高价值且可压制敌应手”的分支。

### 60.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v57_overlay_tactical_escape,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v57_overlay_tactical_escape --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck --seed 20260313`

产物：

- 轮次：`eval_20260304_083140`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_083140_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_083140_matches.jsonl`
- 总局数：`300`（每关键对手 `100` 局，达到两版本比较门槛）

`v57` 分对手结果（head-to-head）：

- vs `v1_current`：`58/100`（58.0%）
- vs `v2_beam`：`63/100`（63.0%）
- vs `v53_overlay_countercheck`：`43/100`（43.0%）

判读：

1. `v57` 对 `v1/v2` 仍是正向，但相对 `v56` 仅小幅波动。
2. `v57` 对 `v53` 仍显著负向（43/100），与 `v56` gate（45/100）同向，说明“战术逃逸候选”尚未修复关键退化。
3. 本轮为 gate 级证据，不满足“优于多个老版本”的 `>=200`/对手或大样本 Elo 门槛。

### 60.4 回到生产口径的结论

生产最新（`eval_20260304_082422`）显示：

- champion 发生 `v1 -> v2` 切换；
- `config.pairs` 按旧 champion=`v1` 构建；
- 生产池当前尚未纳入 `v57`，因此没有 `v57` 的生产 Elo 可用于晋升判断。

结论：

1. 从生产治理口径看，`v57` 目前仅是 iter 候选；结合 gate 结果，当前结论为 `regression`（相对 `v53`）。
2. 在 champion 高频切换下，继续优先采信固定关键对手 head-to-head，而非单轮 gauntlet 排名。

### 60.5 风险与下一步

风险：

1. 战术候选逃逸机制虽然放宽了部分分支，但对 `v53` 关键对位仍无改善，可能仍存在“分支选择目标错位”而非单纯剪枝过硬问题。
2. 200ms 硬截止下，overlay 仍可能把预算消耗在价值接近但对位无效的候选上。

下一步：

1. 做单变量 confirm：`v57 vs v53` `>=200` 局，确认退化是否继续稳定。
2. 做结构 ablation：分别关闭 `tactical_reply_bonus`、`tactical_drop_relax`，定位是“放宽剪枝无效”还是“奖励项引入噪声”。
3. 若 confirm 仍负向，下一版改为“对 `v53` 失败局面定向特征触发”的窄门控，而非全局放宽。

### 60.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID` 截止路径；
   - 评测产物仍无逐步触发计数，无法给出精确命中次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - overlay 搜索路径有 CPU 硬截止保护；
   - 风险点仍在候选扩展与双侧应手评估，存在预算利用效率问题。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 收紧“非战术候选”池宽并前置 early-stop；
   - 对 threat 评估做轻量缓存，减少同步重复计算；
   - 将战术逃逸触发改为更窄条件，避免无效候选占用预算。

## 61. 本回合增量（2026-03-04，v58 dominance-veto overlay）

### 61.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_084115`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v2_beam -> cpp_v1_current`
  - `config.pairs` 显示挑战集合主要是“各版本 vs `cpp_v2_beam` + anchors(`greedy/random_safe`)”，说明该轮对手池按旧 champion（`v2`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_083140`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. gauntlet 口径下，对手池受 champion 切换影响（高优先级风险），不能把跨轮 Elo 绝对值直接当稳定强弱结论。
2. 生产 Elo 为唯一权威；iter Elo 仅用于候选筛选，不跨 scope 做绝对值比较。

### 61.2 算法级改动（已落代码）

版本：

- `cpp_v58_overlay_dominance_veto`
- 源码：`/www/ai_cpp/v58/ai_v58.cpp`

关键机制（相对 v57）：

1. 保留 CPU 计时硬截止与回退（硬约束保持）：
   - `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`；
   - `hard_cutoff_hit` 命中后中断后续搜索并回退当前最优候选。
2. 新增“敌方应手主导 veto”：
   - 在 overlay 评估中，若候选的敌方最佳应手明显主导（`enemy_reply` 超过阈值）且未显著改善主将威胁，则直接过滤该候选；
   - 目标是减少对高反击风险分支的误选，降低对 `v53` 对位中的反制暴露。
3. 收紧战术逃逸放宽：
   - 缩小 `tactical_drop_relax`，降低“全局放宽剪枝”带来的噪声；
   - 平稳态下将 `tactical_reply_bonus` 置零，避免额外奖励放大误判。

### 61.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v58_overlay_dominance_veto,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v58_overlay_dominance_veto --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck --seed 20260314`

产物：

- 轮次：`eval_20260304_085221`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_085221_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_085221_matches.jsonl`
- 总局数：`300`（每关键对手 `100` 局）

`v58` 分对手结果（head-to-head）：

- vs `v1_current`：`58/100`（58.0%）
- vs `v2_beam`：`62/100`（62.0%）
- vs `v53_overlay_countercheck`：`42/100`（42.0%）

判读：

1. `v58` 对 `v1/v2` 仍为正向（达到 `>=100` 样本门槛）。
2. `v58` 对 `v53` 仍显著负向（42/100），较 `v57`（43/100）无改善。
3. 因此 `v58` 仍不能作为 `v53` 替代候选，标签维持 `regression`。

### 61.4 回到生产口径的结论

生产最新（`eval_20260304_084115`）显示：

- champion 发生 `v2 -> v1` 切换；
- `config.pairs` 按旧 champion=`v2` 构建；
- 当前生产池尚未纳入 `v58`，无生产 Elo 可用于其晋升判断。

结论：

1. 从生产治理口径看，`v58` 仅为 iter 候选，且 gate 对关键对手 `v53` 仍退化。
2. 在 champion 高频切换背景下，继续以固定关键对手 head-to-head 作为主判据，不以单轮 gauntlet 排名外推。

### 61.5 风险与下一步

风险：

1. dominance-veto 过滤了部分高反击分支，但未提升 `v53` 对位，说明当前问题可能不是单一“敌应手过强候选”导致。
2. 多条门控叠加后，搜索预算可能更多回退到基线动作，限制了对强对手的有效反制探索。

下一步：

1. 做 `v58 vs v53` `>=200` confirm，确认负向是否稳定。
2. 做双 ablation：分别关闭 `dominance-veto` 与 `tactical_escape`，验证退化主因是“过滤过严”还是“特征触发偏差”。
3. 若 confirm 仍负向，下一版改为“失败局面模板触发”的局部策略，而非全局门控叠加。

### 61.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物不含逐步命中计数，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - overlay 搜索分支受 `<=200ms` CPU 硬截止保护；
   - 风险点仍在候选展开、敌我应手评估与 threat 重算。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 对低价值候选提前剪枝并前置 dominance-veto；
   - 降低同回合重复 threat 计算；
   - 将战术逃逸触发进一步收窄到高置信失败模板。

## 62. 本回合增量（2026-03-04，v59 base-reply guard overlay）

### 62.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_090104`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 显示挑战集合主要是“各版本 vs `cpp_v1_current` + anchors(`greedy/random_safe`)”，说明该轮对手池按旧 champion（`v1`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_085221`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. gauntlet 口径下，对手池受 champion 切换影响（高优先级风险）；跨 tag 的 Elo 绝对值不可直接外推为稳定强弱。
2. 生产 Elo 是唯一权威；iter Elo 仅用于候选筛选，不跨 scope 做绝对值比较。

### 62.2 算法级改动（已落代码）

版本：

- `cpp_v59_overlay_base_reply_guard`
- 源码：`/www/ai_cpp/v59/ai_v59.cpp`

关键机制（相对 v58）：

1. 保留 CPU 计时硬截止与回退（硬约束保持）：
   - `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`；
   - `hard_cutoff_hit` 命中后中断搜索并回退当前最优候选。
2. 新增“相对 base 敌方应手增量”门控：
   - 先对 base 动作计算 `base_enemy_reply_score`；
   - 对每个非 base 候选，若敌方最佳应手显著高于“base 应手 + 允许增量（含 raw_drop/威胁改善补偿）”，则 veto。
3. 新增“相对 base 敌方应手超额”软惩罚：
   - 对未触发 veto 的候选，按超额部分扣分，减少高反击风险换招被误选概率。

### 62.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v59_overlay_base_reply_guard,cpp_v58_overlay_dominance_veto,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v59_overlay_base_reply_guard --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck --seed 20260315`

产物：

- 轮次：`eval_20260304_091146`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_091146_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_091146_matches.jsonl`
- 总局数：`300`（每关键对手 `100` 局）

`v59` 分对手结果（head-to-head）：

- vs `v1_current`：`59/100`（59.0%）
- vs `v2_beam`：`62/100`（62.0%）
- vs `v53_overlay_countercheck`：`43/100`（43.0%）

判读：

1. `v59` 对 `v1/v2` 仍为正向（均达到 `>=100` 样本门槛）。
2. `v59` 对 `v53` 仍显著负向（43/100）；相对 `v58` 的 42/100 仅是 +1 局级波动，未形成方向性修复证据。
3. 本轮为 gate 级证据，`v59` 仍不能作为 `v53` 替代候选，标签维持 `regression`。

### 62.4 回到生产口径的结论

生产最新（`eval_20260304_090104`）显示：

- champion 发生 `v1 -> v2` 切换；
- `config.pairs` 按旧 champion=`v1` 构建；
- 当前生产池尚未纳入 `v59`，无生产 Elo 可用于其晋升判断。

结论：

1. 从生产治理口径看，`v59` 仅是 iter 候选，且 gate 对关键对手 `v53` 仍退化。
2. 本轮结果与生产 gauntlet 的“`v53` 位次高于 `v58`”方向不冲突，因此无需额外触发冲突型 head-to-head 复验。

### 62.5 风险与下一步

风险：

1. base-reply 相对门控降低了部分高反击换招，但对 `v53` 关键对位仍无实质修复，说明退化主因可能不只在“敌方应手超额”。
2. 新增 base 参考评估增加了每步 threat/应手计算次数，虽受 200ms 硬截止保护，但预算利用率风险上升。

下一步：

1. 做 confirm：`v59 vs v53` `>=200` 局，确认负向是否稳定。
2. 做单变量 ablation：分别关闭“base-reply veto”和“base-reply penalty”，定位是“门控过严”还是“惩罚权重无效”。
3. 若 confirm 仍负向，下一版优先做“失败局面模板触发 + 候选重排”，而不是继续叠加全局门控。

### 62.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物不含逐步命中计数，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 搜索主路径仍受 `<=200ms` CPU 硬截止保护；
   - 风险点在于新增 base 参考评估引入额外 threat/应手计算，可能推高预算压力。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 缓存候选回合内可复用的 threat/reserve 结果，减少重复计算；
   - 对低 raw-drop 且低 threat-gain 候选前置快速淘汰；
   - 将 base-reply 规则限制到高风险局面，降低稳态开销。

## 63. 本回合增量（2026-03-04，v60 pressure-anchor overlay）

### 63.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_091945`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v2_beam -> cpp_v1_current`
  - `config.pairs` 显示挑战集合主要是“各版本 vs `cpp_v2_beam` + anchors(`greedy/random_safe`)”，说明该轮对手池按旧 champion（`v2`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_091146`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. gauntlet 口径下，对手池受 champion 切换影响（高优先级风险）；跨 tag Elo 绝对值不可直接外推。
2. 生产 Elo 是唯一权威；iter Elo 仅用于候选筛选，不跨 scope 比较 Elo 绝对值。

### 63.2 算法级改动（已落代码）

版本：

- `cpp_v60_overlay_pressure_anchor`
- 源码：`/www/ai_cpp/v60/ai_v60.cpp`

关键机制（相对 v59）：

1. 保留 CPU 计时硬截止与回退（硬约束保持）：
   - `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`；
   - `hard_cutoff_hit` 命中后中断搜索并回退当前最优候选。
2. 新增“相对 base 的敌主将压力保持”门控：
   - 先计算 base 动作下的 `base_enemy_main_pressure`；
   - 对非 base 候选，若相对 base 的敌主将压力损失超过允许区间（含 raw_drop/主将威胁改善补偿），则 veto。
3. 新增“压力损失超额”软惩罚：
   - 对未触发 veto 的候选，按超额压力损失扣分，抑制“保住防线但丢失进攻节奏”的换招。

### 63.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v60_overlay_pressure_anchor,cpp_v59_overlay_base_reply_guard,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v60_overlay_pressure_anchor --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck,cpp_v59_overlay_base_reply_guard --seed 20260316`

产物：

- 轮次：`eval_20260304_093304`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_093304_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_093304_matches.jsonl`
- 总局数：`400`（每关键对手 `100` 局）

`v60` 分对手结果（head-to-head）：

- vs `v1_current`：`59/100`（59.0%）
- vs `v2_beam`：`60/100`（60.0%）
- vs `v53_overlay_countercheck`：`44/100`（44.0%）
- vs `v59_overlay_base_reply_guard`：`38/100`（38.0%）

判读：

1. `v60` 对 `v1/v2` 仍为正向（均达到 `>=100` 样本门槛）。
2. `v60` 对 `v53` 仍负向（44/100），仅较 `v59` 的 43/100 小幅回升，未达替代门槛。
3. `v60` 对直接前代 `v59` 为 `38/100`，显示本次 pressure-anchor 门控总体引入退化。
4. 结论标签：`regression`。

### 63.4 回到生产口径的结论

生产最新（`eval_20260304_091945`）显示：

- champion 发生 `v2 -> v1` 切换；
- `config.pairs` 按旧 champion=`v2` 构建；
- 当前生产池未纳入 `v60`，无生产 Elo 可用于 `v60` 晋升判断。

结论：

1. 从生产治理口径看，`v60` 仅是 iter 候选，且 gate 对关键对手 `v53` 仍未转正。
2. 生产 gauntlet 与本轮 iter 方向不构成“冲突型跳变”（均不支持 overlay 新分支替代 `v53`），因此本轮不额外触发冲突复验。

### 63.5 风险与下一步

风险：

1. pressure-anchor 规则对节奏保护有一定作用（`v53` 44% 略高于 `v59` 43%），但同时显著伤害了与 `v59` 的直接对位（38%），说明门控可能过严。
2. 新增 base 相对压力约束叠加在 base-reply 门控上，存在“防守与压制双约束”导致可行动作被过度过滤的风险。

下一步：

1. 做 `v60 vs v59` `>=200` confirm，确认退化是否稳定。
2. 做单变量 ablation：分别关闭 `base_pressure_loss_veto` 与 `base_pressure_loss_penalty`，定位退化源。
3. 若退化稳定，下一版改为“仅在高风险局面启用 pressure-anchor”，平稳态回退到 `v59` 规则。

### 63.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物不含逐步命中计数，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 搜索主路径受 `<=200ms` CPU 硬截止保护；
   - 风险点在于 base 相对指标增加了候选评分分支的额外计算，预算压力上升。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 将 pressure-anchor 仅在高风险态启用，稳定态直接跳过；
   - 合并/复用候选内重复的 base 相对计算，降低分支开销；
   - 对低潜力候选在进入压力评估前做早停筛除。

## 64. 本回合增量（2026-03-04，v61 pressure-riskgate overlay）

### 64.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_093957`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 显示挑战集合主要是“各版本 vs `cpp_v1_current` + anchors(`greedy/random_safe`)”，说明该轮对手池按旧 champion（`v1`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_093304`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. gauntlet 口径下，对手池受 champion 切换影响（高优先级风险）；跨 tag Elo 绝对值不可直接外推。
2. 生产 Elo 是唯一权威；iter Elo 仅用于候选筛选，不跨 scope 比较绝对值。

### 64.2 算法级改动（已落代码）

版本：

- `cpp_v61_overlay_pressure_riskgate`
- 源码：`/www/ai_cpp/v61/ai_v61.cpp`

关键机制（相对 v60）：

1. 保留 CPU 计时硬截止与回退（硬约束保持）：
   - `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`；
   - `hard_cutoff_hit` 命中后中断搜索并回退当前最优候选。
2. 新增 pressure-anchor 风险门控：
   - 在 `choose_overlay_tuning` 中引入 `pressure_anchor_enabled`；
   - 高风险态启用 pressure-loss veto/penalty，平稳态关闭该分支并回退到 `v59` 风格规则。
3. 候选评估阶段按门控条件执行：
   - 仅当 `pressure_anchor_enabled=true` 才计算并应用 `pressure_loss` 相关 veto 与 penalty，避免稳定局面过度过滤。

### 64.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v61_overlay_pressure_riskgate,cpp_v60_overlay_pressure_anchor,cpp_v59_overlay_base_reply_guard,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v61_overlay_pressure_riskgate --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck,cpp_v59_overlay_base_reply_guard,cpp_v60_overlay_pressure_anchor --seed 20260317`

产物：

- 轮次：`eval_20260304_095530`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_095530_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_095530_matches.jsonl`
- 总局数：`500`（每关键对手 `100` 局）

`v61` 分对手结果（head-to-head）：

- vs `v1_current`：`59/100`（59.0%）
- vs `v2_beam`：`59/100`（59.0%）
- vs `v53_overlay_countercheck`：`44/100`（44.0%）
- vs `v59_overlay_base_reply_guard`：`39/100`（39.0%）
- vs `v60_overlay_pressure_anchor`：`51/100`（51.0%）

判读：

1. `v61` 对 `v1/v2` 仍为正向（均达到 `>=100` 样本门槛）。
2. `v61` 对 `v53` 仍负向（44/100），未达到替代阈值。
3. 相对 `v60` 已明显止损（51/100），但相对关键上代 `v59` 仍显著退化（39/100）。
4. 结论标签：`regression`。

### 64.4 回到生产口径的结论

生产最新（`eval_20260304_093957`）显示：

- champion 发生 `v1 -> v2` 切换；
- `config.pairs` 按旧 champion=`v1` 构建；
- 当前生产池未纳入 `v61`，无生产 Elo 可用于 `v61` 晋升判断。

结论：

1. 从生产治理口径看，`v61` 仅是 iter 候选，且对关键对手 `v53`/`v59` 仍未过关。
2. 生产 gauntlet 与本轮 iter 不构成“冲突型排序跳变”；本轮不额外触发冲突复验。

### 64.5 风险与下一步

风险：

1. risk-gate 限制后虽修复了 `v60` 的过严过滤副作用（对 `v60` 51/100），但仍无法修复对 `v59` 与 `v53` 的关键退化。
2. 当前 overlay 门控层数仍较多（base-reply + dominance + pressure-gate），可能导致可行动作空间被结构性压窄。

下一步：

1. 做 confirm：`v61 vs v59` `>=200` 局，确认退化是否稳定。
2. 做双 ablation：分别关闭 `base_reply_veto` 与 `base_reply_penalty`，判断是否由 base-reply 约束主导退化。
3. 若 confirm 仍负向，下一版尝试“候选重排优先级重构”（先按进攻压力/战术收益排序，再套门控）而不是继续叠加 veto。

### 64.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物不含逐步命中计数，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 搜索主路径受 `<=200ms` CPU 硬截止保护；
   - 风险点仍在候选分支上的多路应手评估，门控层增加导致预算利用率风险持续存在。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 减少稳定态 overlay 分支数，优先保留高信息增益门控；
   - 对候选池做更激进的前置筛选，减少进入双侧评估的候选数；
   - 将 threat 相关中间量在同步内缓存复用，降低重复计算。

## 65. 本回合增量（2026-03-04，v62 base-veto-riskonly overlay）

### 65.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_100237`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v2_beam -> cpp_v1_current`
  - `config.pairs` 显示挑战集合主要是“各版本 vs `cpp_v2_beam` + anchors(`greedy/random_safe`)”，说明该轮对手池按旧 champion（`v2`）构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_095530`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`

本轮强制判读结论：

1. gauntlet 口径下，对手池受 champion 切换影响（高优先级风险）；跨 tag Elo 绝对值不可直接外推。
2. 生产 Elo 是唯一权威；iter Elo 仅用于候选筛选，不跨 scope 比较绝对值。

### 65.2 算法级改动（已落代码）

版本：

- `cpp_v62_overlay_baseveto_riskonly`
- 源码：`/www/ai_cpp/v62/ai_v62.cpp`

关键机制（相对 v61）：

1. 保留 CPU 计时硬截止与回退（硬约束保持）：
   - `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`；
   - `hard_cutoff_hit` 命中后中断搜索并回退当前最优候选。
2. 新增 base-reply 风险门控：
   - 增加 `base_reply_veto_enabled`；
   - 高风险态启用 `base-reply veto`，平稳态关闭硬 veto（保留软惩罚）。
3. 候选评估中调整 base-reply 约束方式：
   - 稳定局面从“硬过滤 + 软惩罚”改为“仅软惩罚”，降低过严门控对候选空间的压缩。

### 65.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v62_overlay_baseveto_riskonly,cpp_v61_overlay_pressure_riskgate,cpp_v59_overlay_base_reply_guard,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v62_overlay_baseveto_riskonly --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck,cpp_v59_overlay_base_reply_guard,cpp_v61_overlay_pressure_riskgate --seed 20260318`

产物：

- 轮次：`eval_20260304_101631`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_101631_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_101631_matches.jsonl`
- 总局数：`500`（每关键对手 `100` 局）

`v62` 分对手结果（head-to-head）：

- vs `v1_current`：`58/100`（58.0%）
- vs `v2_beam`：`59/100`（59.0%）
- vs `v53_overlay_countercheck`：`44/100`（44.0%）
- vs `v59_overlay_base_reply_guard`：`38/100`（38.0%）
- vs `v61_overlay_pressure_riskgate`：`47/100`（47.0%）

判读：

1. `v62` 对 `v1/v2` 仍为正向（`>=100` 样本门槛已满足）。
2. `v62` 对关键对手 `v53/v59` 仍显著负向，且对 `v61` 也为负向（47/100）。
3. 该改动未实现预期止损，结论标签维持 `regression`。

### 65.4 回到生产口径的结论

生产最新（`eval_20260304_100237`）显示：

- champion 发生 `v2 -> v1` 切换；
- `config.pairs` 按旧 champion=`v2` 构建；
- 当前生产池未纳入 `v62`，无生产 Elo 可用于 `v62` 晋升判断。

结论：

1. 从生产治理口径看，`v62` 仅是 iter 候选，且关键对位未过关。
2. 生产 gauntlet 与本轮 iter 不构成“冲突型排序跳变”；本轮不额外触发冲突复验。

### 65.5 风险与下一步

风险：

1. 仅关闭稳定态 base-reply 硬 veto 仍不足以修复关键退化，说明问题不止在“硬过滤过严”。
2. 当前多门控耦合（dominance/base-reply/pressure）仍可能导致动作排序与真实战术价值错位。

下一步：

1. 做 confirm：`v62 vs v59` `>=200` 局，确认负向是否稳定。
2. 做结构性 ablation：先暂时关闭 `base_reply_penalty`，验证是否是软惩罚项本身导致排序偏移。
3. 若 confirm 仍负向，下一版改为“候选重排优先 + 轻门控”，减少串联 veto 对搜索空间的压缩。

### 65.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物不含逐步命中计数，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 搜索主路径受 `<=200ms` CPU 硬截止保护；
   - 风险点仍在候选双侧应手评估与多门控叠加带来的预算消耗。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 将低信息增益门控做条件化启停，减少稳定态分支；
   - 先做候选重排再进入复杂评估，降低深评估候选数量；
   - 对可复用 threat/reserve 中间量做缓存，缩短单步 CPU 消耗。
