# 第二轮：本地版本管理、自动评测与算法迭代

## 1. 目标

- 建立可持续的本地版本管理与自动评测流水线。
- 支持 16 CPU 并行批量评测与 Elo 评分。
- 在此框架下进行算法级迭代（不是只调参），并记录结果。

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
