# 第二轮：本地版本管理、自动评测与算法迭代

## 0. Replay 持久化与复盘模块（2026-03-04）

- 评测器已改为默认保存所有对局 replay（生产与 iter 都生效）：
  - 生产：`/www/autolab/runtime/replays/<eval_tag>/`
  - iter：`/www/autolab/runtime/scopes/iter/replays/<eval_tag>/`
- `matches.jsonl` 每行新增 `replay_file` 字段，可直接追溯具体对局回放。
- 新增 replay 分析入口：`python3 /www/autolab_replay_analyze.py --scope iter --latest`
  - 输出 JSON：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
  - 输出 Markdown：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.md`
  - iter 实验脚本会自动同步到 docs：
    - `/www/docs/replay_analysis/iter_latest.json`
    - `/www/docs/replay_analysis/iter_latest.md`
- 迭代规范已升级为“必须结合 replay 复盘做结论”，不允许只看 Elo/胜率。

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

## 66. 本回合增量（2026-03-04，v66 in-place：threat-source reserve gate）

### 66.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_121021`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 以“各 challenger vs `cpp_v1_current` + anchors”构建（即按旧 champion=`v1` 构建）
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`
  - 回合起始可见 `eval_20260304_120951`（`matches=0`，因 challenger 不在当期 registry 池内导致空跑）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`/www/past_AIs/Generals-AI/main.cpp` 的 `threat_origin_cnt`（多来源威胁计数）
  - ANTWar：`/www/past_AIs/ANTWar-AI/main.cpp` 的 `danger/reserved`（危险态保留资源，抑制激进扩张）

本轮强制判读结论：

1. gauntlet 对手池受 champion 切换影响（高优先级风险）；当前轮次 Elo 绝对值不可跨 tag 外推。
2. 生产 Elo 是最终权威；iter Elo 仅用于候选筛选。

### 66.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place 小步改造）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 按最新固定目标“默认在现有版本上小步改造”，本次改动与 `v66` 结构兼容，无需新目录。
2. 当前目标是验证“简化风险门控是否有收益”，先做 in-place gate，再决定是否固化快照。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt`（同一目标格的多来源威胁计数）。
   - 映射：对我方主将计算“可在敌方机动半径内形成有效打击的来源数”，把单一 threat 强度扩展为“强度 + 来源数”。
   - 代码落点：新增 `count_threat_sources_to_cell(...)`，并在主循环中对主将格调用。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved`（危险时减少扩张，保留资源）。
   - 映射：当主将 threat 来源数高且 danger ratio 高时，提高 `main_safe_reserve` 并下调本回合可执行移动步数上限。
   - 代码落点：新增 `apply_reserved_main_floor(...)`、`choose_reserved_move_cap(...)`，接入主决策循环。

复杂度与硬截止约束：

1. 保留原搜索硬截止：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`。
2. 保留超时回退：`hard_cutoff_hit` 命中后立即停止后续搜索并使用当前最优候选。
3. 本轮新增逻辑为 O(board) 级 threat-source 计数，未引入无上限前瞻深度。

### 66.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck,cpp_v64_generals_rebuild --seed 20260320`

产物：

- 轮次：`eval_20260304_122143`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_122143_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_122143_matches.jsonl`
- 总局数：`400`（每关键对手 `100` 局）

`v66` 分对手结果（head-to-head）：

- vs `v1_current`：`78/100`（78.0%）
- vs `v2_beam`：`81/100`（81.0%）
- vs `v53_overlay_countercheck`：`55/100`（55.0%）
- vs `v64_generals_rebuild`：`48/100`（48.0%）

判读：

1. 本轮对比均达到 `>=100` 局门槛，可用于两两相对强度判断。
2. 对 `v1/v2` 维持强正向；对 `v53` 到达 55% 边界值；对 `v64` 仍负向（48%）。
3. 由于未满足“对每目标老版本 `>=200` 且 `>55%`”或大样本 Elo 稳定榜首，本轮不能宣称“明确优于多个老版本”。

借鉴点生效证据：

1. Generals 借鉴点（threat-source）有部分正向信号：对 `v53` 达到 `55/100`，较此前 overlay 分支常见的 40%~45% 区间明显改善。
2. ANTWar 借鉴点（danger/reserved）呈混合效果：在高压对局可能止损，但对 `v64` 仍 `48/100`，存在过度保守风险。

### 66.4 回到生产口径的结论

生产最新（`eval_20260304_121021`）显示：

- champion 发生 `v1 -> v2` 切换；
- `config.pairs` 按旧 champion=`v1` 构建；
- gauntlet 对手池口径已发生漂移风险。

结论：

1. 生产 Elo 仍是唯一权威；本轮结论以“生产口径风险提示 + iter 探索证据”组合给出。
2. 由于本次是 `v66` in-place 改造，生产轮次尚未对该新二进制做独立复验，暂不做生产晋升结论。
3. 当前状态标签：`neutral`（有正向信号但未通过关键替代门槛）。

### 66.5 风险与下一步

风险：

1. threat-source 计数在每步决策都会触发，CPU 预算压力增加。
2. reserved move-cap 可能在优势局面过早收缩行动，导致对 `v64` 这类进攻型对手失分。
3. 当前仍缺少 `>=200` 局 confirm，无法稳健声明关键替代结论。

下一步：

1. 做 confirm：`v66 vs v64` 至少 `200` 局，验证 48% 是否稳定。
2. 做单变量 ablation：
   - 仅保留 threat-source 提升 `main_safe_reserve`；
   - 关闭 `move_cap` 收缩；
   判断是否由“步数收缩”主导退化。
3. 若确认过保守，改为“仅当 main_threat_sources >= 5 且 danger_ratio >= 0.75”才触发 move-cap，其他场景只提高 reserve floor。

### 66.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物无逐步命中计数，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 搜索主路径仍受 `<=200ms` CPU 硬截止保护；
   - 新增风险点为每步 threat-source 计数引入的额外遍历成本。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 将 threat-source 计数限制为“仅主将周边高压态触发”；
   - 对 move-cap 使用更高触发阈值，减少正常局面分支干预；
   - 复用当步 threat 中间量，减少重复扫描。

## 67. 本回合增量（2026-03-04，v66 in-place：reserved gate 简化）

### 67.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_123130`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 主要为“各 challenger vs `cpp_v1_current` + anchors”，按旧 champion=`v1` 构建。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_122143`）
- 迭代日志：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（多来源威胁计数）
  - ANTWar：`danger/reserved`（危险态保留资源，避免过度扩张）

本轮强制判读结论：

1. gauntlet 对手池受 champion 切换影响（高优先级风险）；本轮生产 Elo 绝对值不可跨轮直接外推。
2. 生产 Elo 仍是唯一权威；iter Elo 仅用于候选筛选。

### 67.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place 小步改造）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 按固定目标“默认现有版本小步改造”，本次只做规则阈值与启停条件简化，和 `v66` 架构兼容。
2. 目标是验证“简化是否止损并维持强度”，无需创建新目录快照。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt`（同目标格的威胁来源数量）。
   - 映射：仅在主将高压态启用 threat-source 计数，作为 reserve floor 的附加依据。
   - 代码落点：`count_threat_sources_to_cell(...)` + `should_enable_reserved_gate(...)`。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved`（危险时保留资源、减少扩张）。
   - 映射：将 move-cap 简化为“仅极端危险触发一次减步”，不再中压频繁收缩。
   - 代码落点：`choose_reserved_move_cap(...)`（仅 `sources>=6 && danger_ratio>=0.90` 生效）。

本轮具体简化点：

1. `apply_reserved_main_floor` 从多阈值叠加改为三段轻量加成，降低过保守偏置。
2. `choose_reserved_move_cap` 从双阈值（`-2/-1`）改为单阈值（最多 `-1`）。
3. `count_threat_sources_to_cell` 仅在 `should_enable_reserved_gate` 为真时触发，减少每步 CPU 开销。

硬截止与回退约束：

1. 保持 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200`。
2. 保持 `hard_cutoff_hit` 回退路径。

### 67.3 可复现实验（已执行，隔离 scope）

执行命令（脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v53_overlay_countercheck,cpp_v1_current,cpp_v2_beam --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v53_overlay_countercheck,cpp_v64_generals_rebuild --seed 20260321`

产物：

- 轮次：`eval_20260304_124223`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_124223_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_124223_matches.jsonl`
- 总局数：`400`（每关键对手 `100` 局）

`v66` 分对手结果（head-to-head）：

- vs `v1_current`：`76/100`（76.0%）
- vs `v2_beam`：`80/100`（80.0%）
- vs `v53_overlay_countercheck`：`58/100`（58.0%）
- vs `v64_generals_rebuild`：`50/100`（50.0%）

判读：

1. 每个两两比较均达到 `>=100` 局，满足相对强度判断门槛。
2. 相较上轮同池 gate（`seed=20260320`）：`v66 vs v53` 从 `55% -> 58%`，`v66 vs v64` 从 `48% -> 50%`，简化方向有止损信号。
3. 但尚未满足“对每目标老版本 `>=200` 且 `>55%`”，不能宣称“明确优于多个老版本”。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source）生效信号：在保留该机制前提下，`v66 vs v53` 提升到 `58/100`。
2. ANTWar 借鉴（danger/reserved）生效信号：简化为极端态触发后，`v66 vs v64` 从负向 `48/100` 回升至 `50/100`（止损但未转优）。

### 67.4 回到生产口径的结论

生产最新（`eval_20260304_123130`）显示：

- champion 发生 `v1 -> v2` 切换；
- `config.pairs` 按旧 champion=`v1` 构建；
- gauntlet 口径存在 champion 依赖漂移风险。

结论：

1. 本轮最终结论仍以生产口径为权威前提，iter 仅作候选探索。
2. 当前 `v66`（简化版）在 iter 对 `v1/v2/v53` 为正向、对 `v64` 持平，标签可上调为 `promising` 候选，但尚未达到生产晋升证据线。
3. 若后续生产 gauntlet 排序与该趋势冲突，需补做 `v66 vs v64` `>=100`（建议 `200`）head-to-head 复验再定结论。

### 67.5 风险与下一步

风险：

1. threat-source 计数虽已条件化，但在高压对局仍有额外开销。
2. 对 `v64` 仅 `50/100`，说明“止损”不等于“建立优势”。

下一步：

1. 进入 confirm：`v66 vs v64` 至少 `200` 局（同脚本、隔离 scope）。
2. 若 confirm 仍接近 50%，尝试进一步简化：只保留 reserve floor，暂时禁用 move-cap（完全去掉减步）。
3. 若 confirm >55%，再扩大到固定池大样本（`>=1000`）验证 Elo 稳定性。

### 67.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID` 路径；
   - 评测产物无逐步命中统计，无法精确计数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 搜索主路径仍受 `<=200ms` CPU 硬截止保护；
   - 风险点主要在高压态触发的 threat-source 计数。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 仅在极端高压态计算 threat-source；
   - move-cap 继续保持单阈值，必要时完全移除；
   - 保持候选前置排序和早停，减少深评估候选数量。

## 68. 本回合增量（2026-03-04，v66 in-place：移除 move-cap，仅保留 reserve floor）

### 68.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_125156`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 仍按旧 champion=`v1` 构建（各 challenger 对 `v1` + anchors）。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_124223`）
- 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（多来源威胁）
  - ANTWar：`danger/reserved`（危险态保留资源）

本轮强制判读结论：

1. gauntlet 对手池受 champion 切换影响（高优先级风险）；生产 Elo 绝对值不应跨轮直接比较。
2. 生产 Elo 是最终口径；iter Elo 仅用于筛选候选。

### 68.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 本轮是“复杂度回收”而非结构重建，直接在 `v66` 上做小步回滚更可控。
2. 目标是先验证“去掉硬减步”是否修复 `v64` 对位，再决定是否固化快照。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt`。
   - 映射：保留 threat-source 计数，仅作为主将 reserve floor 的增强依据。
   - 代码落点：`count_threat_sources_to_cell(...)` + `apply_reserved_main_floor(...)`。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved` 的“危险时保留资源”而非强制截断动作。
   - 映射：删除 `move_cap` 硬减步逻辑，改为仅通过 reserve floor 软约束来体现 reserved。
   - 代码落点：删除 `choose_reserved_move_cap(...)` 与 `step >= step_move_cap` 分支；动作搜索恢复使用 `move_budget`。

简化收益（结构层面）：

1. 去除一条动作截断分支与相关状态变量，降低策略路径复杂度。
2. 保留高压态条件触发（`should_enable_reserved_gate`），减少无效 threat-source 计算。

硬截止约束：

1. 仍使用 `CLOCK_THREAD_CPUTIME_ID`。
2. 仍保持单步 `<=200ms`（`kSearchStepBudgetMs=200`）与 `hard_cutoff_hit` 回退。

### 68.3 可复现实验（已执行，隔离 scope）

执行命令（confirm，脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=100 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260323`

产物：

- 轮次：`eval_20260304_125633`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_125633_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_125633_matches.jsonl`
- 总局数：`200`（关键对手 confirm 门槛达成）

结果（head-to-head）：

- `v66 vs v64 = 106/200`（53.0%）

判读：

1. 本轮样本满足 confirm 最低建议（`>=200`），可用于关键对手稳定性判断。
2. 结果从此前 `48/100 -> 50/100 -> 53/200` 连续上行，说明“去掉 move-cap”方向在修复 `v64` 对位上有效。
3. 但 `53%` 仍未达到“`>55%`”判优阈值，不能宣称“v66 已明确优于 v64”。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source）仍有效：在移除硬减步后未丢失主将稳健性，`v66` 仍能保持对关键对手正向微优势。
2. ANTWar 借鉴（reserved 软约束化）有效：由“硬截断动作”改为“reserve floor”，`v66 vs v64` 从负/平转为 `53%`。

### 68.4 回到生产口径的结论

生产最新（`eval_20260304_125156`）显示：

- champion 切换 `v1 -> v2`；
- `pairs` 按旧 champion=`v1` 构建；
- gauntlet 口径存在 champion 依赖漂移。

结论：

1. 生产 Elo 仍为唯一权威；iter confirm 仅作为候选证据。
2. 当前生产与 iter 不再明显冲突：生产中 `v66` 位次高于 `v64`，iter confirm 也给出 `53%` 正向。
3. 但未达到 `>55%`，因此状态维持 `neutral`（接近可用，不足以宣称明确替代）。

### 68.5 风险与下一步

风险：

1. `v66 vs v64` 虽转正但优势窄，仍可能受 seed/对手池波动影响。
2. threat-source 在高压态仍有额外计算开销；虽受硬截止保护，仍应继续控复杂度。

下一步：

1. 做二次 confirm：`v66 vs v64` 再跑 `>=200` 局（新 seed）验证是否稳定高于 53%。
2. 若仍在 52~54% 区间，优先继续简化（减少 overlay 中低收益惩罚项）而非新增分支。
3. 若上到 `>55%` 且稳定，再扩展到 `v53/v1/v2` 的统一 `>=200` gate。

### 68.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物无逐步统计，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 搜索主路径受 `<=200ms` 硬截止保护；
   - 高压态 threat-source 计算仍是预算热点。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 进一步抬高 `should_enable_reserved_gate` 触发阈值；
   - 在不损伤对位收益前提下减少 overlay 低收益分支；
   - 保持“软约束优先、硬截断最少”的简化路线。

## 69. 本回合增量（2026-03-04，v66 in-place：reserved 软释放，confirm 复验）

### 69.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_130144`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v2_beam -> cpp_v1_current`
  - `config.pairs` 仍按旧 champion=`v2` 构建（各 challenger vs `v2` + anchors）。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（回合起始为 `eval_20260304_125633`）
- 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（多来源威胁）
  - ANTWar：`danger/reserved`（危险态保留、非危险态释放）

本轮强制判读结论：

1. gauntlet 对手池受 champion 切换影响（高优先级风险），生产 Elo 绝对值不能跨轮直接当作同池比较。
2. 生产 Elo 是唯一权威；iter Elo 仅用于候选筛选。

### 69.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 本轮目标是继续“简化优先”验证，属于现有 `v66` 的小步策略回收。
2. 改动与结构完全兼容，无需新目录快照。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt`。
   - 映射：保留主将 threat-source 计数，仅在高压态启用，作为 reserve floor 的增强依据。
   - 代码落点：`count_threat_sources_to_cell(...)` + `should_enable_reserved_gate(...)`。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved` 的“危险保留、非危险释放”。
   - 映射：新增 `apply_reserved_release_floor(...)`，在低 danger ratio 下释放 1 点 reserve，避免过保守。
   - 代码落点：主循环与每步循环中在 reserve 计算后调用该函数。

本轮简化变化：

1. 延续上轮已移除的 `move_cap` 硬减步路径，保持动作路径无硬截断分支。
2. 引入“软释放”替代“硬限制”，减少策略补丁层数。

硬截止与回退：

1. 保留 `CLOCK_THREAD_CPUTIME_ID`。
2. 保留 `kSearchStepBudgetMs=200` 与 `hard_cutoff_hit` 保底回退。

### 69.3 可复现实验（已执行，隔离 scope）

执行命令（confirm，脚本入口，14 并发）：

- `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=100 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260324`

产物：

- 轮次：`eval_20260304_130613`（`runtime_scope=iter`）
- 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_130613_summary.json`
- 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_130613_matches.jsonl`
- 总局数：`200`（关键对手 confirm 门槛达成）

结果（head-to-head）：

- `v66 vs v64 = 106/200`（53.0%）

判读：

1. 样本量达 `>=200`，可用于 confirm 级判断。
2. 与上一轮 confirm（`seed=20260323`）结果完全一致：`106/200`，说明当前胜率大约稳定在 53% 附近。
3. 仍未达到 `>55%` 阈值，因此不能宣称“v66 明确优于 v64”。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source）保持有效：在继续保留该机制下，`v66` 对 `v64` 维持稳定正向（53%）。
2. ANTWar 借鉴（reserved 软释放）有效性有限：未进一步提升超过 53%，但保持了“不过度保守且不回退到负向”的状态。

### 69.4 回到生产口径的结论

生产最新（`eval_20260304_130144`）显示：

- champion 从 `v2` 切回 `v1`；
- `pairs` 按旧 champion=`v2` 构建；
- 生产 gauntlet 口径存在 champion 依赖漂移。

结论：

1. 生产 Elo 仍是唯一权威，iter confirm 仅作为候选证据。
2. 生产与 iter 未出现方向冲突（均显示 `v66` 不弱于 `v64`），但也都不构成“显著领先”证据。
3. 本轮标签维持 `neutral`。

### 69.5 风险与下一步

风险：

1. `v66 vs v64` 长期停留在约 53%，说明当前策略已接近局部平台期。
2. threat-source 计算虽已条件化，仍是高压态 CPU 风险点。

下一步：

1. 不再增加新门控，优先做“减法式”ablation：尝试去掉 overlay 低收益惩罚项（保持硬截止不变）。
2. 若下轮仍在 53% 左右，转向固定池大样本 Elo（`>=1000`）判断整体稳定排名，避免在单对位上过拟合。
3. 如需晋升论断，必须先达成关键对手 `>55%` 且 `>=200` 的硬门槛。

### 69.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物无逐步命中计数，无法精确统计。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 搜索主路径仍受 `<=200ms` 硬截止保护；
   - 高压态 threat-source 计算仍可能抬升预算占用。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 进一步减少 overlay 低收益项，避免新增分支；
   - 如收益不降则提高 `should_enable_reserved_gate` 触发阈值；
   - 继续保持“软约束优先、硬截断最少”的简化路线。

## 70. 本回合增量（2026-03-04，v66 in-place：overlay 分支减法）

### 70.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_131255`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 仍按旧 champion=`v1` 构建（各 challenger vs `v1` + anchors）。
- 迭代口径（回合起始）：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_130613`）
- 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（多来源威胁）
  - ANTWar：`danger/reserved`（危险态保留、非危险态释放）

本轮强制判读结论：

1. 生产 gauntlet 对手池受 champion 切换影响（高优先级风险）：本轮生产池围绕旧 champion=`v1`，不可把跨轮 Elo 绝对值直接对比。
2. 生产 Elo 仍是唯一权威；iter Elo 仅用于候选筛选。

### 70.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 本轮目标是“减少分支与状态变量”的减法改造，与 `v66` 结构兼容。
2. 改动尚未通过关键对手 `>55%` 门槛，不满足固化新目录的必要性。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt`。
   - 映射：继续把 threat-source 计数作为主将 reserve floor 的高压增强信号。
   - 代码落点：`count_threat_sources_to_cell(...)` + `apply_reserved_main_floor(...)`。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved`（危险态保留，安全态释放）。
   - 映射：继续保留 `apply_reserved_main_floor(...)` + `apply_reserved_release_floor(...)` 软约束，不回到硬截断动作数。
   - 代码落点：主循环与逐步决策中的 reserve 计算链路。

本轮核心简化（算法级）：

1. 在 `select_best_move_overlay(...)` 中删除 pressure-loss 次级惩罚链路：
   - 删除 `base_enemy_main_pressure`、`pressure_loss/allowed_pressure_loss`；
   - 删除对应 veto 分支与 penalty 计分分支。
2. 保留主约束：
   - `base_reply_veto`（敌方回复上限）；
   - `dominance` 否决；
   - `hard_cutoff_hit` 回退。

硬截止约束：

1. 仍使用 `CLOCK_THREAD_CPUTIME_ID`。
2. 仍保持单步 `<=200ms`（`kSearchStepBudgetMs=200`）与保底回退路径。

### 70.3 可复现实验（已执行，隔离 scope）

中止说明（记录但不纳入结论）：

1. 试运行 gate（`games_per_pair=100`，`v66` vs `v64/v1/v2`，seed=20260325）耗时过长，中止。
2. 试运行 confirm（`games_per_pair=100`，`v66` vs `v64`，seed=20260326）同样耗时过长，中止。

本轮有效实验（用于结论）：

- 命令：
  - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260327`
- 产物：
  - 轮次：`eval_20260304_133531`
  - 汇总：`/www/autolab/runtime/scopes/iter/eval_20260304_133531_summary.json`
  - 明细：`/www/autolab/runtime/scopes/iter/eval_20260304_133531_matches.jsonl`
- 结果（head-to-head）：
  - `v66 vs v64 = 51/100`（51.0%）

判读：

1. 样本达到两 AI 最低可判读门槛（`>=100`），但仍低于 confirm 建议（`>=200`）。
2. 相比上一轮 `53.0%`（200 局），本轮简化后仅 `51.0%`，未体现增益。
3. 未达到 `>55%`，不能宣称“v66 明确优于 v64”。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source）仍有效但增益有限：在删分支后仍保持微弱正向（51%）。
2. ANTWar 借鉴（reserved 软约束）本轮未带来额外提升：结果回落到 51%。

### 70.4 回到生产口径的结论

生产最新（`eval_20260304_131255`）显示：

1. champion 切换为 `v2`，但对手池按旧 champion=`v1` 构建，gauntlet 漂移风险仍高。
2. 生产中 `v66` 位次高于 `v64`，iter 本轮 `51/100` 也保持同方向（无冲突）。
3. 但证据强度不足以给出“显著优于”结论，本轮标签维持 `neutral`（偏回落）。

### 70.5 风险与下一步

风险：

1. `v66 vs v64` 在 51%~53% 区间震荡，接近平台期。
2. 即使做了分支减法，单局总耗时仍偏高，导致 `>=200` confirm 成本高。

下一步：

1. 固定 `v66 vs v64` 先补一轮 `>=200` confirm（必要时拆分为两次 `games_per_pair=50` 同 seed 组）。
2. 若仍在 51%~53%，考虑回滚本轮 overlay 减法，或仅在高压态保留 pressure-loss（条件启用）。
3. 增加 `hard_cutoff_hit` 计数输出，定位真实 CPU 热点后再做剪枝。

### 70.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物无逐步命中统计，无法给出精确触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 单步搜索路径仍受 `<=200ms` 硬截止保护；
   - 风险主要在 overlay 中多次 `select_best_move_base(...)` 的累计计算量。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 继续收缩 overlay 候选池；
   - 将高成本分支仅在高 danger ratio 下启用；
   - 在不破坏强制回退路径前提下优先做分支删减。

## 71. 本回合增量（2026-03-04，v66 in-place：danger-only pressure-drop veto）

### 71.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_135243`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v1_current -> cpp_v2_beam`
  - `config.pairs` 按旧 champion=`v1` 构建（各 challenger vs `v1` + anchors）。
- 迭代口径（回合起始）：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_133531`）
- 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt` + `reserve_positions`
  - ANTWar：`danger/reserved` 状态驱动

本轮强制判读结论：

1. 本轮生产 gauntlet 对手池受 champion 切换影响（高优先级风险），生产 Elo 不能跨轮直接按绝对值比较。
2. 生产 Elo 是唯一权威；iter Elo 仅用于候选筛选。

### 71.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 仍是 `v66` 内的单分支修复，结构兼容且可回滚。
2. 本轮目标是验证“最小危险态补丁”而非形成新架构，不满足新目录必要性。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt` / `reserve_positions`（威胁来源与保留位）。
   - 映射：继续将 threat-source 作为主将 reserve floor 增强信号，避免在高压态过度外放。
   - 代码落点：`count_threat_sources_to_cell(...)` + `apply_reserved_main_floor(...)`。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved`（只在危险态启用更保守约束）。
   - 映射：在 overlay 中新增 `pressure_drop_veto`，仅高压态启用；非危险态不启用。
   - 代码落点：`OverlayTuning.pressure_drop_veto_enabled/slack` 与 `select_best_move_overlay(...)` 的单阈值 veto。

本轮改动要点（简化优先）：

1. 相比历史 pressure-loss 链路，仅恢复一个“高压态单阈值 veto”：
   - 只保留 `pressure_drop > slack` 时否决；
   - 不恢复 pressure-loss penalty 与多系数调参。
2. 继续保留上轮的分支减法主体（没有回滚整套旧链路）。

硬截止与回退：

1. 保留 `CLOCK_THREAD_CPUTIME_ID` 计时。
2. 保留 `kSearchStepBudgetMs=200` 和 `hard_cutoff_hit` 回退。

### 71.3 可复现实验（已执行，隔离 scope）

实验命令（两轮，累计 confirm 200 局）：

1. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260330`
2. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260331`

产物：

1. `eval_20260304_134431`：`v66 vs v64 = 50/100`
2. `eval_20260304_134710`：`v66 vs v64 = 51/100`

合并判读（关键对手 confirm）：

1. 累计 `v66 vs v64 = 101/200`（50.5%）。
2. 样本达到 `>=200`，可用于 confirm 结论。
3. 相比前次 `106/200`（53.0%）出现回落，且远低于 `>55%` 判优阈值。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source reserve）仍保证“不过度冒进”，但未带来对 `v64` 的强优势。
2. ANTWar 借鉴（danger-only veto）成功保持了低复杂度危险态约束，但胜率未提升（50.5%）。

### 71.4 回到生产口径的结论

生产最新（`eval_20260304_134253`）显示：

1. champion 从 `v2` 切到 `v1`，且 `pairs` 仍围绕旧 champion=`v2`，gauntlet 口径漂移风险持续存在。
2. 生产中 `v66` 仍略高于 `v64`，iter confirm（101/200）方向不冲突但强度很弱。
3. 本轮不支持“v66 明显优于 v64”结论，标签维持 `neutral`（本轮改动无增益）。

### 71.5 风险与下一步

风险：

1. `v66 vs v64` 在 50%~53% 区间震荡，已表现为平台期。
2. overlay 分支虽简化，但对强对位的收益不足，属于“复杂度下降但强度未升”。

下一步：

1. 回滚本轮 `pressure_drop_veto`，与当前版做同口径 A/B（各 100 局）验证是否纯噪声。
2. 若仍平台，转向固定池大样本 Elo（`>=1000`）评估整体稳定排序，不再在 `v64` 单对位过拟合。
3. 加入 `hard_cutoff_hit` 计数输出，量化 CPU 热点后再做下一步剪枝。

### 71.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码仍保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测结果文件没有逐步命中计数，无法精确统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 单步仍有 `<=200ms` 硬截止保护；
   - 风险点在 overlay 内多次 base move 求解的累计开销。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 继续减小 overlay 候选池；
   - 仅在高 danger ratio 保留高成本分支；
   - 优先删分支而非新增补丁。

## 72. 本回合增量（2026-03-04，v66 in-place：overlay 仅危险态启用）

### 72.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_134253`）
  - `mode=gauntlet`，`games_per_pair=6`
  - `champion.old/new = cpp_v2_beam -> cpp_v1_current`
  - `config.pairs` 按旧 champion=`v2` 构建（各 challenger vs `v2` + anchors）。
- 迭代口径（回合起始）：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_134710`）
- 旧 AI 参考：
  - Generals：`threat_origin_cnt` / `reserve_positions`
  - ANTWar：`danger/reserved` 状态驱动

本轮强制判读结论：

1. gauntlet 对手池受 champion 切换影响（高优先级风险），生产 Elo 不能跨轮按绝对值横比。
2. 生产 Elo 是唯一权威；iter Elo 仅用于候选筛选。

### 72.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 继续在 `v66` 上做小步可回滚改造，结构兼容。
2. 改造目标是进一步简化策略路径，不涉及新架构固化。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt` / `reserve_positions`。
   - 映射：继续保留 threat-source 驱动的 reserve floor，维持高压态防线。
   - 代码落点：`count_threat_sources_to_cell(...)` + `apply_reserved_main_floor(...)`。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved`（危险态才进入保守控制）。
   - 映射：overlay 策略改为“仅高风险启用”，非危险态直接回退 base move。
   - 代码落点：`choose_overlay_tuning(...)` 在 `!high_risk` 时 `tuning.enabled=false` 直接返回。

本轮核心简化：

1. 删除原“非高压态 conservative overlay”整段参数与分支。
2. 保留高压态 overlay（含单阈值 `pressure_drop_veto`）与 base 回退。
3. 有效减少非高压局面的状态变量与补丁层数。

硬截止与回退：

1. 保留 `CLOCK_THREAD_CPUTIME_ID`。
2. 保留 `kSearchStepBudgetMs=200` 与 `hard_cutoff_hit` 回退路径。

### 72.3 可复现实验（已执行，隔离 scope）

实验命令（两轮累计 confirm 200 局）：

1. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260332`
2. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260333`

产物与结果：

1. `eval_20260304_135424`：`v66 vs v64 = 55/100`
2. `eval_20260304_135654`：`v66 vs v64 = 56/100`
3. 合并：`v66 vs v64 = 111/200`（55.5%）

判读：

1. 累计样本 `>=200`，满足 confirm 门槛。
2. 对 `v64` 达到 `>55%`，满足“新版本优于该单一老版本（k=1）”的门槛条件。
3. 该结论仅对 `v64` 成立，尚不能外推到 `v1/v2/v53`。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source reserve）与 ANTWar 借鉴（danger-only 控制）组合在本轮恢复了对 `v64` 的有效优势（111/200）。
2. 证据为两次独立 seed 的稳定正向（55%、56%）。

### 72.4 回到生产口径的结论

生产最新（`eval_20260304_135243`）显示：

1. champion 切换与对手池漂移风险仍在（旧 champion=`v1` 池）。
2. 生产里 `v66` 略高于 `v64`，与本轮 iter confirm（55.5%）方向一致，无冲突。
3. 本轮可给出“`v66` 相对 `v64` 有效优势”的结论，但不宣称对多基线全面领先。

### 72.5 风险与下一步

风险：

1. 当前仅完成对 `v64` 的 `>=200` confirm，关键基线 `v1/v2` 仍缺同量级验证。
2. gauntlet champion 切换仍会造成生产 Elo 绝对值漂移。

下一步：

1. 按 gate 顺序补 `v66 vs v1`、`v66 vs v2` 各 `>=100`（建议继续两轮 `50+50`）。
2. 若两者都接近或超过 55%，再进入固定池大样本 Elo（`>=1000`）确认稳定排名。
3. 在代码中增加 `hard_cutoff_hit` 计数日志，量化 CPU 热点。

### 72.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 评测产物不含逐步命中计数，无法精确统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 单步仍受 `<=200ms` 硬截止保护；
   - 风险主要在高压态 overlay 的多次候选评估累计。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 继续压缩高压态候选池；
   - 仅在 threat-source 高阈值时启用最贵分支；
   - 保持“非危险态直接 base”的简化主线。

## 73. 本回合增量（2026-03-04，v66 in-place：非危险态直回 base + v1/v2 confirm）

### 73.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_141016`）
  - `mode=gauntlet`，`games_per_pair=1`，`rating_mode=cumulative`
  - `champion.old/new = cpp_v1_current -> cpp_v66_generals_weapon_econ`
  - `config.pairs` 仍按旧 champion=`v1` 构建（各 challenger vs `v1` + anchors）。
- 迭代口径（回合起始）：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_141535`）
- 旧 AI 参考：
  - Generals：`threat_origin_cnt` / `reserve_positions`
  - ANTWar：`danger/reserved` 状态驱动

本轮强制判读结论：

1. gauntlet 对手池受 champion 切换影响（高优先级风险）依旧成立。
2. 生产 Elo 为唯一权威；iter Elo 仅作候选筛选与直接对战验证。

### 73.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 本轮是“继续减分支”的小步修复，与现有 `v66` 完全兼容。
2. 属于可回滚调优，不需要新目录固化。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt` + `reserve_positions`（威胁来源与保留位）。
   - 映射：继续用 threat-source 强化主将 reserve floor。
   - 代码落点：`count_threat_sources_to_cell(...)` + `apply_reserved_main_floor(...)`。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved`（仅危险态进入保守控制）。
   - 映射：overlay 在非高压态直接禁用，回退 base chooser；危险态才启用 overlay/veto。
   - 代码落点：`choose_overlay_tuning(...)` 中 `!high_risk => tuning.enabled=false`。

本轮简化收益：

1. 删除非危险态整段 conservative overlay 分支，减少状态与参数耦合。
2. 仅保留高压态 overlay（含 `pressure_drop_veto`），保持关键防守控制。

硬截止与回退：

1. 保留 `CLOCK_THREAD_CPUTIME_ID`。
2. 保留 `kSearchStepBudgetMs=200` 与 `hard_cutoff_hit`。

### 73.3 可复现实验（已执行，隔离 scope）

实验命令（两轮，均脚本入口 + 14 并发）：

1. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam --seed 20260334`
2. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam --seed 20260335`

产物与分轮结果：

1. `eval_20260304_140823`：vs `v1` `79/100`，vs `v2` `77/100`
2. `eval_20260304_141535`：vs `v1` `80/100`，vs `v2` `77/100`

合并（confirm 级）：

1. `v66 vs v1 = 159/200`（79.5%）
2. `v66 vs v2 = 154/200`（77.0%）
3. 结合上一轮已完成的 `v66 vs v64 = 111/200`（55.5%）

判读：

1. 对 `v1/v2/v64` 三个关键老版本均满足 `>=200` 且 `>55%`。
2. 按当前门槛，可宣称 `v66` 对这 3 个目标老版本具备明确优势（直接对战口径）。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source reserve）与 ANTWar 借鉴（danger-only 控制）在本轮继续生效，且对 `v1/v2` 出现强优势。
2. 非危险态直回 base 的减法没有削弱关键对位，反而使 gate/confirm 结果更稳定。

### 73.4 回到生产口径的结论

生产最新（`eval_20260304_141016`）显示：

1. champion 已切到 `v66`，方向与本轮 iter 直接对战结论一致。
2. 但生产 gauntlet 仍受 champion 切换和对手池漂移影响，绝对 Elo 不做跨轮硬比较。
3. 本轮给出“`v66` 相对 `v1/v2/v64` 的直接对战优势成立”结论；更大范围排序仍需固定池大样本验证。

### 73.5 风险与下一步

风险：

1. 生产口径当前 `games_per_pair=1` 且 `rating_mode=cumulative`，短期波动和历史累计混合，需要谨慎解读绝对 Elo。
2. 虽然关键三对位已过门槛，但对更老版本全集的泛化仍待固定池验证。

下一步：

1. 进入固定池大样本 Elo（`>=1000`）验证 `v66` 排名稳定性（iter scope）。
2. 若稳定榜首，再考虑固化新快照或推广为默认候选。
3. 增加 `hard_cutoff_hit` 计数输出，量化 CPU 热点并进一步缩减高压态候选集。

### 73.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码保留 `hard_cutoff_hit` + `CLOCK_THREAD_CPUTIME_ID`；
   - 当前评测产物无逐步触发计数，无法精确统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 单步仍受 `<=200ms` 硬截止保护；
   - 风险集中在高压态 overlay 的累计评估开销。
3. 若有风险，下一轮降复杂度/剪枝计划：
   - 继续减少高压态候选池；
   - 提高高成本分支触发阈值；
   - 保持“非危险态直接 base”主路径不回退。

## 74. 本回合增量（2026-03-04，v66 in-place：threat-origin 驱动 overlay 启停简化）

### 74.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_144413`）
  - `mode=adaptive`，`games_per_pair=1`，`rating_mode=cumulative`
  - `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`（本轮未发生 champion 切换）
  - `config.pairs` 为 adaptive 抽样对阵池，不是固定 gauntlet 全量池。
- 迭代口径（回合起始并最终）：`/www/autolab/runtime/scopes/iter/latest.json`（先 `eval_20260304_142919`，后更新到 `eval_20260304_144359`）
- 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt` / `reserve_positions`
  - ANTWar：`global_state` / `danger` / `reserved`

本轮强制判读结论：

1. 生产 Elo 仍是唯一权威；iter Elo 仅用于候选筛选与对战验证。
2. 本轮 `champion.old == champion.new`，对手池未受到“champion 切换”扰动；但生产为 adaptive 抽样池，跨 tag Elo 绝对值仍不可直接横比。

### 74.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 仅在 `v66` 上做小步门控简化，和现有结构兼容。
2. 改动是“减少无效 overlay 分支”，属于可回滚微改，不需要新目录固化。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt`（威胁来源数量）。
   - 映射：把“主将威胁来源数量”作为 overlay 启停和候选池规模的一级信号，避免在低来源压力时展开额外分支。
   - 代码落点：`choose_overlay_tuning(...)` 中新增 `main_threat_sources = count_threat_sources_to_cell(...)`，并据此约束 `pool_limit` 与 `high_risk` 判定。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`global_state/danger/reserved`（危险态才进入保守控制）。
   - 映射：仅在“近身对抗 + 足够危险（danger 或 source_alert）”时启用 overlay；其余局面保持 base 路径。
   - 代码落点：`high_risk = main_danger>=0.55 || (duel_close && (main_danger>=0.40 || source_alert))`。

本轮简化收益（结构层面）：

1. 减少“仅因主将接近就开启 overlay”的误触发，降低状态分支数量。
2. 低威胁来源场景下收缩候选池，降低高成本评估路径触发概率。

硬截止与回退（保持不变）：

1. `CLOCK_THREAD_CPUTIME_ID` CPU 计时口径。
2. `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退路径。

### 74.3 可复现实验（已执行，隔离 scope）

实验命令（两轮 seed，均脚本入口 + 14 并发）：

1. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam --seed 20260336`
2. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam --seed 20260337`

产物与结果：

1. `eval_20260304_142919`：vs `v1` `83/100`，vs `v2` `72/100`
2. `eval_20260304_144359`：vs `v1` `82/100`，vs `v2` `71/100`

合并（confirm 级）：

1. `v66 vs v1 = 165/200`（82.5%）
2. `v66 vs v2 = 143/200`（71.5%）

判读：

1. 两个关键对手均满足 `>=200` 且 `>55%`。
2. 相比上一轮 `v66`（`v1=159/200`, `v2=154/200`），本轮对 `v1` 略升、对 `v2` 略降，属于“结构简化后的混合变化”，先记为稳定正优势而非显著提升。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-origin）生效证据：引入来源计数后，仍保持对 `v1/v2` 大样本正优势（`165/200`、`143/200`）。
2. ANTWar 借鉴（danger-only）生效证据：在减少 overlay 触发范围后，关键对位未崩塌，说明“危险态控制、平稳态简化”可行。

### 74.4 回到生产口径的结论

生产最新（`eval_20260304_144413`）显示：

1. 当前为 adaptive 对阵口径，`champion` 未切换（`v66 -> v66`），本轮不存在 champion 切换导致的对手池突变。
2. 因 production 非固定池、且 cumulative 累计，绝对 Elo 不用于跨 tag 直接强弱判定。
3. 本轮可确认的强结论仍来自 iter 直接对战：`v66` 对 `v1/v2` 均在 `>=200` 样本下显著领先。

### 74.5 风险与下一步

风险：

1. 本轮只复验了 `v1/v2`，尚未同步复验 `v64` 是否维持此前 `>55%` 的 confirm 水平。
2. 生产 adaptive 池会持续变动，不能把单轮 production 排名当作稳定排序结论。

下一步：

1. 补做 `v66 vs v64` 复验（建议 `200` 局）检查本轮简化是否影响该关键对位。
2. 进入固定池大样本 Elo（`>=1000`）验证 `v66` 的稳定榜首性。
3. 加入 `hard_cutoff_hit` 计数输出，量化真实触发频率，继续压缩高压态高成本分支。

### 74.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码仍含 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 当前评测产物无逐步计数，无法精确统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 单步有硬截止兜底；
   - 风险仍集中在高压态 overlay 的候选评估累计开销。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 在高压态继续按 `threat-source` 收缩候选池；
   - 仅对 threat/source 同时高的局面放宽分支；
   - 保持非危险态走 base 的简化路径。

## 75. 本回合增量（2026-03-04，v66 in-place：复用 step danger/source，补 v64 confirm）

### 75.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_145725`）
  - `mode=adaptive`，`games_per_pair=6`，`rating_mode=cumulative`
  - `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v64_generals_rebuild`（已发生晋升切换）
  - `config.pairs` 为 adaptive 抽样池（含 `cpp_v64_generals_rebuild vs cpp_v66_generals_weapon_econ` 等）。
- 迭代口径：`/www/autolab/runtime/scopes/iter/latest.json`（本轮结束为 `eval_20260304_145932`）
- 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt` / `reserve_positions`
  - ANTWar：`global_state` / `danger` / `reserved`

本轮强制判读结论：

1. 生产 Elo 仍是唯一权威；iter Elo 仅用于候选筛选。
2. 本轮已发生 `champion` 切换；由于生产是 adaptive 而非 gauntlet，风险形态不是“gauntlet 固定池切换高危”，但 production 排序口径已受对局抽样与晋升反馈影响，需以 head-to-head 复验校准。

### 75.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 本轮是“减少重复扫描/减少状态分支”的小步改造，与 `v66` 结构兼容。
2. 不涉及架构替换，属于可回滚优化，按规则保持 in-place。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt`（威胁来源数是决策主信号）。
   - 映射：把每步主将 `threat_sources` 当成主输入，复用到 overlay 调参，避免重复重新扫描。
   - 代码落点：`choose_overlay_tuning(...)` 改为直接接收 `main_danger/main_threat_sources`；主循环计算后复用。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`global_state/danger/reserved`（危险态才启用保守控制）。
   - 映射：仅在 `reserve_gate` 或 `duel_close` 时计算 threat-sources，其余平稳态不展开额外 threat-source 扫描。
   - 代码落点：主循环新增 `reserve_gate || duel_close_step` 触发条件。

本轮简化收益：

1. 去掉 `choose_overlay_tuning` 内部每步重复 `count_threat_sources_to_cell(...)`。
2. 减少一层“调参函数内再判态再扫描”的分支嵌套，主循环单点产出并复用。

硬截止与回退（保持）：

1. `CLOCK_THREAD_CPUTIME_ID` 计时口径。
2. `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。

### 75.3 可复现实验（已执行，隔离 scope）

实验命令（脚本入口，14 并发，两轮 confirm）：

1. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260338`
2. `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260339`

产物与结果：

1. `eval_20260304_145707`：`v66 vs v64 = 57/100`
2. `eval_20260304_145932`：`v66 vs v64 = 57/100`

合并（confirm 级）：

1. `v66 vs v64 = 114/200`（57.0%）

判读：

1. 满足 `>=200` 且 `>55%`，本轮确认 `v66` 对 `v64` 直接对战优势成立。
2. 结合前一轮已确认结果：`v66 vs v1 = 165/200`、`v66 vs v2 = 143/200`，当前 `v1/v2/v64` 三关键基线均满足门槛。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source 作为主信号）在本轮“减少重复扫描”后仍保持对 `v64` 稳定优势（两 seed 同为 `57/100`）。
2. ANTWar 借鉴（danger-only）在本轮依然成立：仅危险相关场景计算 threat-source，未导致关键对位退化。

### 75.4 回到生产口径的结论

生产最新（`eval_20260304_145725`）显示：

1. champion 从 `v66` 切到 `v64`，与本轮 iter 直接对战（`v66` 对 `v64` `114/200`）方向冲突。
2. 生产当前为 adaptive 抽样池，不能以单轮 Elo 绝对值替代固定池强度结论。
3. 按“生产口径冲突需做 head-to-head 复验”的规则，本轮已补做并满足 `>=100`（实际 `200`）复验样本；在直接对战口径下仍判定 `v66` 对 `v64` 为正优势。

### 75.5 风险与下一步

风险：

1. 本轮确认的是 `v64` 对位；尽管 `v1/v2` 已有 confirm，仍缺“固定池 >=1000 局 Elo”级别稳定排序证据。
2. 生产已出现 `v66 -> v64` 晋升，与近期 head-to-head 结论冲突，短窗排序波动风险上升。

下一步：

1. 执行固定对手池大样本 Elo（`>=1000` 局）验证 `v66` 稳定榜首性。
2. 若排序稳定，再考虑是否固化快照；否则继续优先做简化剪枝而不是叠补丁。
3. 可选补充：为 `hard_cutoff_hit` 增加计数输出，量化真实命中率。

### 75.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码仍有 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 评测产物无逐步计数，无法精确统计命中次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 单步存在硬截止兜底；
   - 风险主要来自高压态 overlay 候选累计评估。
3. 若有风险，下一轮降复杂度/改进剪枝：
   - 继续限定 threat-source 计算触发条件；
   - 优先复用 step 级中间量，避免函数内重复扫描；
   - 保持非危险态直接走 base 的主路径。

## 76. 本回合增量（2026-03-04，v66 in-place：duel_close 低危险态跳过 threat-source 扫描）

### 76.1 回合起始状态与必做判读

- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_151618`）
  - `mode=adaptive`，`games_per_pair=6`，`rating_mode=cumulative`
  - `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`
  - `config.pairs` 为 adaptive 抽样池（包含多组 `v66` 与历史基线对局）。
- 迭代口径（回合起始）：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_145932`）
- 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（多来源威胁计数）
  - ANTWar：`danger/reserved`（危险态才进入保守控制）

本轮强制判读结论：

1. 生产 Elo 仍是唯一权威；iter Elo 仅用于候选筛选。
2. 当前生产是 adaptive（非 gauntlet），且 `champion` 本轮未切换；不存在“gauntlet champion 切换导致对手池突变”的高优先级风险场景。

### 76.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 源码：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 本轮是“继续减分支/减重复扫描”的微改，结构与 `v66` 完全兼容。
2. 属于可回滚简化优化，不需要新目录固化。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt`。
   - 映射：保留 threat-source 作为高价值信号，但不在低信息量场景盲扫。
   - 代码落点：step 循环中 `overlay_source_gate` 控制 `count_threat_sources_to_cell(...)` 触发。
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved`。
   - 映射：`duel_close` 且 `danger<0.40` 时不进入来源扫描，只有显式危险才进入保守分支。
   - 代码落点：`overlay_source_gate = reserve_gate || (duel_close_step && step_main_danger >= 0.40)`。

本轮简化收益（预期）：

1. 减少近身但低危险局面的 threat-source 重复扫描。
2. 进一步压缩“低风险触发保守分支”的状态空间。

硬截止与回退（保持不变）：

1. `CLOCK_THREAD_CPUTIME_ID`。
2. `kSearchStepBudgetMs=200` + `hard_cutoff_hit`。

### 76.3 可复现实验（已执行，隔离 scope）

实验命令：

1. gate（关键三基线）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260340`
2. 冲突补复验（v64）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260341`

产物与结果：

1. `eval_20260304_152053`（gate）
   - `v66 vs v1 = 80/100`
   - `v66 vs v2 = 73/100`
   - `v66 vs v64 = 46/100`
2. `eval_20260304_152333`（v64 复验）
   - `v66 vs v64 = 59/100`

合并判读（当前代码）：

1. `v66 vs v64 = 105/200`（52.5%）
2. `v66 vs v1/v2` 仅有本轮 gate 的 `100` 局样本（正向，但尚未完成本轮代码版本的 `200` 局 confirm）。

结论：

1. 本轮简化在 `v64` 对位上未达到 `>55%` 门槛（`52.5%`），不能宣称当前代码“优于 v64”。
2. 相比上一轮（上一版代码）`v66 vs v64 = 114/200`，本轮 tweak 出现不稳定回落，按本轮改动标签更接近 `neutral/regression`。

借鉴点是否生效（证据）：

1. Generals 借鉴（threat-source）仍可提供判别，但“过度收紧触发”导致对 `v64` 稳定性下降（`46/100` 与 `59/100` 分化）。
2. ANTWar 借鉴（danger-only）方向成立，但阈值 `0.40` 可能过强，导致近身低危险阶段漏掉必要 threat-source 信息。

### 76.4 回到生产口径的结论

生产最新（`eval_20260304_151618`）显示：

1. `mode=adaptive`，`champion` 本轮未切换。
2. 生产抽样池不能替代固定池/直接对战判优。
3. 本轮关键判优仍以 iter head-to-head 为准：当前 tweak 下 `v66 vs v64` 仅 `52.5%`，不能作为“明显更强”结论。

### 76.5 风险与下一步

风险：

1. 本轮新增阈值使 `v64` 对位出现明显不稳定（两 seed 分化大）。
2. 若继续沿用该阈值，可能在近身低危险态漏判 threat-source，造成中盘决策偏差。

下一步：

1. 回调该阈值（例如恢复 `duel_close` 即可触发来源扫描，或降到 `>=0.30`）并做 `v64` `200` 局 confirm。
2. 对当前代码再补 `v1/v2` 各 `>=100`（建议补到 `200`）后再给版本级判优。
3. 推进固定池 `>=1000` 局 Elo，避免 adaptive 抽样噪声干扰版本结论。

### 76.6 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码路径仍有 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 当前评测产物无逐步触发计数，无法给出精确次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 单步有硬截止兜底；
   - 风险仍在高压态 overlay 多候选累计评估。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 优先调回“duel_close 来源扫描”阈值而非新增更多补丁；
   - 继续复用 step 中间量，避免函数内重复扫描；
   - 保持非危险态直接 base 主路径。

## 77. 本回合增量（2026-03-04，v66 in-place：threat-source 饱和计数 + 双层触发）

### 77.1 回合起始状态与必做判读

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_155621`）
  - `mode=adaptive`，`games_per_pair=6`
  - `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`
  - `config.pairs` 为 adaptive 抽样池（本轮包含多条与 `v66` 相关对局）
- 迭代口径（隔离）：`/www/autolab/runtime/scopes/iter/latest.json`
- 回放分析：
  - `runtime/scopes/iter/replay_analysis/latest.json`
  - `docs/replay_analysis/iter_latest.md`（已同步为本轮最新 replay 分析）
- 对局索引：iter `latest.json.paths.matches`
  - `/www/autolab/runtime/scopes/iter/eval_20260304_154813_matches.jsonl`
  - 每行含 `replay_file`，可直开原始回放逐帧核对
- 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`
  - ANTWar：`danger` / `reserved` / `global_state`

本轮强制判读结论：

1. 生产 Elo 仍是唯一权威；iter Elo 仅用于候选筛选。
2. 本轮生产为 `adaptive`（非 gauntlet），且 `champion` 未切换，因此不存在“gauntlet champion 切换导致对手池突变”的高优先级风险场景；但 adaptive 抽样池下 Elo 绝对值仍不可跨轮直接当强度结论。

### 77.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 改动是对 `v66` 现有 threat-source 流程的简化重构，和当前架构兼容；
2. 属于“小步可回滚”改造，不需要新目录固化。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt` 的“来源计数作为核心信号”
   - 映射：来源数在达到策略阈值后不需要继续累计，采用饱和计数减少无效扫描
   - 代码落点：`count_threat_sources_to_cell(..., cap)`，达到 `cap` 立即返回
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`danger/reserved` 的危险态分层控制
   - 映射：`reserve_gate` 用高精度探测（cap=4），`duel_close` 中风险用轻量探测（cap=2）
   - 代码落点：step 循环的双层触发
     - `reserve_gate -> cap=4`
     - `duel_close && step_main_danger>=0.28 -> cap=2`

本轮关键机制变化：

1. 新增常量：
   - `kThreatSourceProbeCap=4`
   - `kThreatSourceAlertCap=2`
   - `kDuelCloseSourceProbeDanger=0.28`
2. `count_threat_sources_to_cell` 改为带 `cap` 的饱和计数并早停；
3. 主循环把“是否扫描来源数”从单阈值改为双层触发，减少低价值重复扫描分支。

硬截止与回退（保持）：

1. CPU 计时口径仍是 `CLOCK_THREAD_CPUTIME_ID`
2. 搜索单步硬截止 `kSearchStepBudgetMs=200`
3. 截止后保底回退仍依赖 `hard_cutoff_hit` 路径

### 77.3 可复现实验（隔离 scope，脚本入口）

执行命令：

1. gate（关键三基线）  
   `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260342`
2. confirm（关键对手 v64）  
   `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260343`

结果：

1. `eval_20260304_154112`（gate）
   - `v66 vs v1 = 80/100`
   - `v66 vs v2 = 73/100`
   - `v66 vs v64 = 46/100`
2. `eval_20260304_154813`（confirm）
   - `v66 vs v64 = 59/100`
3. 合并关键对位（本轮代码）：
   - `v66 vs v64 = 105/200`（52.5%）

判读：

1. `v66 vs v64` 达到 `200` 样本，但未超过 `55%`，不能宣称当前改动后 `v66` 明显优于 `v64`。
2. `v66 vs v1/v2` 本轮仍为 gate 正向（各 `100` 局）。

### 77.4 Replay 分析与原始回放核对

回放分析文件（本轮已更新到最新 tag）：

1. `runtime/scopes/iter/replay_analysis/latest.json`（`tag=eval_20260304_154813`）
2. `docs/replay_analysis/iter_latest.md`（已同步）

聚合证据（`154813`）：

1. `v66`：`win_rate=0.59`，`no_effect_rate=0.0661`，`avg_actions=247.72`
2. `v64`：`win_rate=0.41`，`no_effect_rate=0.0658`，`avg_actions=254.18`
3. 动作结构：`v66` 较少 `general_skill/call_general`，较多 `general_upgrade`，说明本轮改动未把策略推向更重技能分支。

对局索引与逐帧核对（直接从 `paths.matches` 的 `replay_file` 打开）：

1. 索引文件：`/www/autolab/runtime/scopes/iter/eval_20260304_154813_matches.jsonl`
2. 负例核对（`seed=20260343`，`v66` 负，`max_round=66`）  
   回放：`.../20260304_154813_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260343_rounds-180.jsonl`  
   turning point（analysis）：`round 39`，`delta_army_lead_p0=-11`  
   帧动作核对：`round 38-40` 中 `v66` 出现升级/将军位移动作并行，`v64` 连续前线推进动作，负例显示中盘响应节奏仍可能偏慢。
3. 正例核对（`seed=20261254`，`v66` 胜，`max_round=180`）  
   回放：`.../20260304_154813_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261254_rounds-180.jsonl`  
   turning point（analysis）：`round 167`，`delta_army_lead_p0=-108`（对 p0 不利，即对 p1 的 v66 有利）  
   帧动作核对：`round 166-168` 中 `v66` 持续多路兵线动作并在后续回合叠加召将，形成后段兵力摆动放大。

回放结论（必须项）：

1. 本轮改动没有引入明显“无效动作率激增”问题（`no_effect_rate` 基本与 v64 持平）。
2. 但负例样本显示中盘压力交换仍不稳，和 `v66 vs v64 = 105/200` 未达判优门槛一致。

### 77.5 回到生产口径的结论

生产最新：`/www/autolab/runtime/latest.json`（`eval_20260304_153152`）

1. `mode=adaptive`，`champion.old/new = v66 -> v66`
2. 本轮生产未出现 champion 切换导致的对手池突变风险（gauntlet 高危场景不触发）
3. 最终判优仍以本轮 iter head-to-head 大样本为依据：当前改动下对 `v64` 为 `52.5%`，不满足“明显更强”标准。

### 77.6 风险与下一步

风险：

1. 双层触发虽降低了扫描成本，但对 `v64` 关键对位没有形成净增益（仍 `52.5%`）。
2. 中盘高压交换段仍有被 `v64` 反压样本（回放 seed `20260343`）。

下一步：

1. 在不增加分支复杂度前提下，优先回调 `duel_close` 轻量探测触发条件（例如仅调单阈值），并再做 `v64` `200` 局 confirm。
2. 若仍不稳定，考虑回退到上一版 `duel_close` 探测门控，保持“饱和计数早停”这项简化收益。
3. 补充固定池大样本 Elo（`>=1000` 局）验证，避免只看单轮 gauntlet/adaptive 信号。

### 77.7 回合末强制自检

1. 本轮是否触发搜索时间硬截止：
   - 代码仍包含 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 当前评测产物无逐步硬截止计数，无法给出次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 单步有硬截止兜底；
   - 风险主要在高压态 overlay 候选累计评估。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 保留饱和计数早停（`cap`）；
   - 继续减少中风险态不必要来源扫描；
   - 若收益不足，优先回退触发阈值而非叠加新分支。

## 78. 本回合增量（2026-03-04，v66 in-place：duel_close 危险态滞回门控）

### 78.1 回合起始状态与必做判读

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产口径：`/www/autolab/runtime/latest.json`（`eval_20260304_153152`）
  - `mode=adaptive`，`games_per_pair=6`
  - `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`
  - `config.pairs` 为 adaptive 抽样池（多组历史版本对战，含部分 `v66` 对位）
- 迭代口径（隔离）：`/www/autolab/runtime/scopes/iter/latest.json`
- 回放分析：
  - `runtime/scopes/iter/replay_analysis/latest.json`
  - `docs/replay_analysis/iter_latest.md`
- 对局索引（iter latest）：
  - `paths.matches = /www/autolab/runtime/scopes/iter/eval_20260304_161040_matches.jsonl`
  - 每行包含 `replay_file`，可直接逐帧核对
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（来源计数主信号）
  - ANTWar：`global_state/danger/reserved`（危险态带滞回的状态控制）

本轮强制判读结论：

1. 生产 Elo 仍是唯一权威，iter Elo 仅候选筛选。
2. 本轮生产不是 gauntlet，且 champion 未切换；不存在“gauntlet champion 切换导致对手池突变”的高优先级风险场景。

### 78.2 算法级改动（已落代码，未新建版本目录）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（in-place）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 仅在现有 `v66` 逻辑上做门控简化，不涉及架构不兼容改造。
2. 仍属可回滚的小步实验，先用 gate/confirm 决定是否保留。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`threat_origin_cnt` 作为风险输入
   - 映射：继续保留 threat-source 饱和计数（`cap` 早停）
   - 代码落点：`count_threat_sources_to_cell(..., cap)`
2. ANTWar 借鉴点 -> 本游戏映射 -> 代码落点
   - 借鉴点：`global_state/danger` 的状态滞回
   - 映射：`duel_close` 来源扫描由“单阈值”改为“on/off 双阈值滞回锁存”
   - 代码落点：新增 `update_duel_source_probe_latch(...)`，
     - `danger >= 0.28` 进入锁存
     - `danger <= 0.22` 释放锁存
     - `reserve_gate` 强制保持锁存

硬截止与回退（保持）：

1. `CLOCK_THREAD_CPUTIME_ID`
2. `kSearchStepBudgetMs=200`
3. `hard_cutoff_hit` 回退路径不变

### 78.3 可复现实验（隔离 scope，脚本入口）

执行命令：

1. gate（三基线）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260344`
2. confirm（v64）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260345`

产物与结果：

1. `eval_20260304_160144`（gate）
   - `v66 vs v1 = 80/100`
   - `v66 vs v2 = 73/100`
   - `v66 vs v64 = 45/100`
2. `eval_20260304_161040`（confirm）
   - `v66 vs v64 = 58/100`
3. 合并关键对手：
   - `v66 vs v64 = 103/200`（51.5%）

判读：

1. `v66 vs v64` 达到 `200` 局，但显著低于 `>55%` 判优线。
2. 与上一回合 `105/200` 相比，本轮滞回门控对 `v64` 对位进一步回落（`51.5%`）。

### 78.4 Replay 分析与原始回放核对

回放分析（脚本自动更新）：

1. `runtime/scopes/iter/replay_analysis/latest.json`：`tag=eval_20260304_161040`，`analyzed_matches=100`，`missing_replay=0`
2. `docs/replay_analysis/iter_latest.md`：已同步为同一 tag

聚合证据（`161040`）：

1. `v66`：`win_rate=0.58`，`no_effect_rate=0.06510`
2. `v64`：`win_rate=0.42`，`no_effect_rate=0.06476`
3. 动作结构：`v66` 仍偏“更多 general_upgrade、较少 general_skill/call_general”，本轮滞回门控未改变该宏观分布。

对局索引与逐帧核对（基于 `paths.matches` 的 `replay_file`）：

1. 负例（seed `20261256`，`v66` 负）
   - 回放：`.../20260304_161040_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261256_rounds-180.jsonl`
   - turning point：round95，`delta_army_lead_p0=-76`（对 p0 不利，p0 为 v64；对应 v66 未在该点完成反压）
   - 帧动作核对：round94-96 双方均连续兵线推进，v64 在 round95 出现技能动作 `Action=[4,17,2,6,12]` 后形成大摆动。
2. 正例（seed `20260345`，`v66` 胜）
   - 回放：`.../20260304_161040_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260345_rounds-180.jsonl`
   - turning point：round101，`delta_army_lead_p0=-39`（p0 即 v66 发生一次不利摆动但后续能收回）
   - 帧动作核对：round100-102 双方持续双线推进，说明该改动更多影响边界触发稳定性，而非改变主战术骨架。

回放结论：

1. 本轮没有出现“无效动作率恶化”证据。
2. 但关键对位胜率仍回落，说明滞回门控未解决 `v64` 中盘压制问题。

### 78.5 回到生产口径的结论

生产最新仍是 `eval_20260304_155621`（adaptive，champion 未切换）。

1. 本轮生产口径不存在 gauntlet champion 切换风险。
2. 版本优劣结论仍以本轮 iter head-to-head 为主：`v66 vs v64 = 103/200`，不能宣称“明显更强”。

### 78.6 风险与下一步

风险：

1. “滞回门控”降低了边界抖动，但对 `v64` 关键对位仍负向回落。
2. 若继续叠加门控状态，可能增加策略复杂度而收益不足。

下一步：

1. 保留 `cap` 早停，回退滞回门控（避免补丁层增厚），再做 `v64` `200` 局 confirm。
2. 若要继续简化路线，可改为单阈值+固定窗口（而非锁存状态）以减少状态变量。
3. 并行准备固定池大样本 Elo（`>=1000` 局）验证稳定排序，避免小样本波动误导。

### 78.7 回合末强制自检

1. 是否触发搜索硬截止：
   - 代码仍含 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 当前产物无逐步计数，无法给出命中次数。
2. 是否存在 `>200ms` 单步 CPU 风险：
   - 有硬截止兜底；
   - 风险点仍在高压态 overlay 候选累计评估。
3. 若有风险，下一轮降复杂度/剪枝：
   - 回退本轮锁存门控，减少状态分支；
   - 保留饱和计数早停；
   - 优先保证关键对位稳定性，再考虑进一步省算。

## 79. 自动迭代回合（v66：移除滞回锁存，改为无状态 danger 分级探测）

### 79.1 先读固定目标与最新状态（按要求）

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产评测：`/www/autolab/runtime/latest.json`（当前 `eval_20260304_161620`）
- 迭代评测：`/www/autolab/runtime/scopes/iter/latest.json`（当前 `eval_20260304_164010`）
- 回放分析：
  - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
  - `/www/docs/replay_analysis/iter_latest.md`
- 对局索引：iter latest `paths.matches=/www/autolab/runtime/scopes/iter/eval_20260304_164010_matches.jsonl`，逐行含 `replay_file`。
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（来源计数）
  - ANTWar：`global_state/danger` 分级切分（危险态切强分支，非危险态保持简单策略）

生产口径必做判读（`config.pairs` + `champion.old/new`）：

1. `mode=adaptive`，`games_per_pair=6`，`pairs_count=45`（抽样对手池）。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`，未发生 champion 切换。
3. 结论：本轮不存在 gauntlet + champion 切换导致对手池突变的高优先级风险；生产 Elo 仍是唯一权威，iter Elo 仅用于候选筛选。

### 79.2 算法级改动（in-place，小步简化）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（未新建目录）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 改动是对 `v66` 已有 threat-source 门控的“减状态”重构，与现结构兼容。
2. 属于可回滚的小步验证，先过 gate/confirm 再决定是否需要快照版本。

“旧 AI 借鉴点 -> 本游戏映射 -> 代码落点”链路：

1. Generals 借鉴点：`threat_origin_cnt`（威胁来源计数）
   - 映射：保留 `count_threat_sources_to_cell(..., cap)` 饱和计数与早停。
   - 代码落点：`count_threat_sources_to_cell` + step 内 `source_probe_cap`。
2. ANTWar 借鉴点：`global_state/danger` 分级切分（危险态走强分支）
   - 映射：移除滞回锁存状态，改为无状态 danger 分级：
     - `reserve_gate` -> `cap=4`
     - `duel_close && danger>=0.28` -> `cap=2`
     - `duel_close && danger>=0.48` -> `cap=4`（critical）
   - 代码落点：新增 `choose_threat_source_probe_cap(...)`，删除 `update_duel_source_probe_latch(...)` 与 `duel_source_probe_latched`。

CPU 硬截止（保持不变）：

1. `CLOCK_THREAD_CPUTIME_ID` 计时。
2. `kSearchStepBudgetMs=200`。
3. `hard_cutoff_hit` 保底回退路径仍在。

### 79.3 可复现实验（隔离 scope，规定脚本）

执行命令：

1. gate（关键三基线）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260346`
2. confirm（关键对手 v64）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260347`

产物与结果：

1. `eval_20260304_163017`（gate）
   - `v66 vs v1 = 80/100`
   - `v66 vs v2 = 73/100`
   - `v66 vs v64 = 47/100`
2. `eval_20260304_164010`（confirm）
   - `v66 vs v64 = 57/100`
3. 合并关键对手（满足 200 局口径）：
   - `v66 vs v64 = 104/200`（52.0%）

判读：

1. `v66` 对 `v1/v2` 仍稳定领先（100 局口径）。
2. 对关键对手 `v64` 虽较上一轮（`103/200`）小幅回升到 `104/200`，但仍显著低于 `>55%` 判优线，不能宣称优于 `v64`。

### 79.4 Replay 分析与原始回放核对

回放分析（脚本自动更新）：

1. `runtime/scopes/iter/replay_analysis/latest.json`：`tag=eval_20260304_164010`，`analyzed_matches=100`，`missing_replay=0`。
2. `docs/replay_analysis/iter_latest.md`：已同步到同一 tag。

聚合证据（`164010`）：

1. `v66`：`win_rate=0.570`，`no_effect_rate=0.063`，`avg_rounds=119.1`。
2. `v64`：`win_rate=0.430`，`no_effect_rate=0.065`，`avg_rounds=119.1`。
3. 动作结构：`v66` 仍偏更多 `general_upgrade`、较少 `general_skill/call_general`，宏观行为骨架未变。

基于 `paths.matches` 的原始回放逐帧核对（含 `replay_file`）：

1. 正例：seed `20260347`（`v66` 胜）
   - 回放：`.../20260304_164010_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260347_rounds-180.jsonl`
   - turning point：round166，`delta_territory_lead_p0=+2`，`delta_army_lead_p0=+44`。
   - 帧核对：round165-167 双方持续兵线推进，`v66` 在 round166 后两步推进保持压制。
2. 负例：seed `20261265`（`v66` 负，`v66` 在 p1）
   - 回放：`.../20260304_164017_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261265_rounds-180.jsonl`
   - turning point：round136，`delta_army_lead_p0=+353`（`v64` 侧大摆动）。
   - 帧核对：round135-137 出现 `v64` 连续推进后，`v66` 在同窗内防线被放大穿透。

回放结论：

1. 本轮改动未引入 no-effect 恶化。
2. 但 `v64` 对位仍存在中后盘大摆动失守样本，说明“去锁存后的分级探测”仅小幅止损，未达关键对位翻正。

### 79.5 本轮借鉴点是否生效（强制项）

1. Generals 借鉴点（来源计数）
   - 证据：`v1/v2` 仍分别 `80/100`、`73/100`，基础稳定性保持。
   - 判定：`部分生效`（稳定性有效，但非关键短板）。
2. ANTWar 借鉴点（danger 分级切分）
   - 证据：`v64` 从上一轮合并 `103/200` 回到 `104/200`（仅 +0.5pct）。
   - 判定：`弱生效/未达目标`（止损幅度不足以改变结论标签）。

### 79.6 回到生产口径的结论

生产最新：`eval_20260304_161620`（adaptive，champion 未切换）。

1. 本轮生产口径无 champion 切换导致的 gauntlet 池变风险。
2. 版本优劣结论仍以 head-to-head 样本为准：当前 `v66 vs v64 = 104/200`，不满足“明显更强”声明条件。

### 79.7 风险、下一步与回合末自检

风险：

1. 对 `v64` 关键对位仍低于判优线，存在中后盘 swing 被放大的风险。
2. overlay 在高压态仍可能因候选评估链路偏长而靠近 CPU 上限。

下一步：

1. 保持“无状态分级探测”不回退，优先在 high-risk overlay 内再做一次减支（减少 veto 叠层或收缩候选池上限）并复验 `v64` 200 局。
2. 若下一轮仍在 `52%` 附近，考虑固定池大样本（`>=1000` 局）确认真实排序，避免局部 seed 偏差。

回合末强制自检：

1. 是否触发搜索时间硬截止：
   - 代码保留 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 当前日志无逐步计数字段，无法量化触发次数。
2. 是否存在超过 `200ms` 单步 CPU 风险点：
   - 有硬截止兜底；
   - 风险点仍在高压态 overlay 候选评估（多次 threat 估计 + 应手评估）。
3. 若有风险，下一轮降复杂度/剪枝：
   - 继续减少 high-risk 分支层数（优先删次要 veto/penalty）；
   - 保持 threat-source 饱和早停与 base 回退路径，确保复杂度单调可控。

## 80. 自动迭代回合（v66：移除 pressure_drop_veto，继续简化 high-risk overlay）

### 80.1 固定目标与最新状态读取

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产评测：`/www/autolab/runtime/latest.json`（`eval_20260304_171815`）
- 迭代评测：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_172021`）
- 回放分析：
  - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
  - `/www/docs/replay_analysis/iter_latest.md`
- 对局索引：`paths.matches=/www/autolab/runtime/scopes/iter/eval_20260304_172021_matches.jsonl`（每行含 `replay_file`）
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（来源计数）
  - ANTWar：`global_state/danger + reserved`（危险态优先，分支选择保留主干）

生产口径必做判读（`config.pairs` + `champion.old/new`）：

1. 当前生产是 `adaptive`，`games_per_pair=6`，`pairs_count=45`。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`，本轮 latest 内未发生 champion 切换。
3. 结论：本轮不存在“gauntlet + champion 切换”导致对手池突变的高优先级风险；但生产 champion 已从早前 v66 变为 v64，跨 tag Elo 绝对值仍不可直接比较。

### 80.2 算法级改动（in-place，减分支）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（未新建目录）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 仅删除 high-risk overlay 的次级 veto 分支，不涉及架构不兼容。
2. 属于“减复杂度验证”，先做 gate/confirm 再决定是否固化快照。

“旧 AI 借鉴点 -> 映射 -> 代码落点”：

1. Generals 借鉴点：`threat_origin_cnt`
   - 映射：继续保留 threat-source 饱和计数（`cap` 早停）作为主风险输入。
   - 代码落点：`count_threat_sources_to_cell(..., cap)` 与 `choose_threat_source_probe_cap(...)`。
2. ANTWar 借鉴点：`danger/reserved` 下“保留主干、减少附加分支”
   - 映射：在已有 danger/reserve 主门控下，删除次级 `pressure_drop_veto`，避免叠补丁分支。
   - 代码落点：移除 `OverlayTuning` 中 `pressure_drop_veto_*` 字段及 `select_best_move_overlay(...)` 对应 veto 逻辑。

CPU 硬截止（保持）：

1. `CLOCK_THREAD_CPUTIME_ID`
2. `kSearchStepBudgetMs=200`
3. `hard_cutoff_hit` 回退路径

### 80.3 可复现实验（规定脚本）

执行命令：

1. gate（关键三基线）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260348`
2. confirm（关键对手 v64）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260349`

结果：

1. gate `eval_20260304_170145`
   - `v66 vs v1 = 81/100`
   - `v66 vs v2 = 73/100`
   - `v66 vs v64 = 47/100`
2. confirm `eval_20260304_172021`
   - `v66 vs v64 = 56/100`
3. 合并关键对位（200 局）：
   - `v66 vs v64 = 103/200`（51.5%）

判读：

1. `v66` 对 `v1/v2` 仍有明显优势信号。
2. 对 `v64` 关键对位从上一回合 `104/200` 回落到 `103/200`，仍低于 `>55%` 判优线。

### 80.4 Replay 分析与逐帧核对

回放分析（latest=`172021`）：

1. `analyzed_matches=100`，`missing_replay=0`。
2. 聚合：
   - `v66`：`win_rate=0.560`，`no_effect_rate=0.0642`
   - `v64`：`win_rate=0.440`，`no_effect_rate=0.0662`

原始回放逐帧证据（来自 `paths.matches` 的 `replay_file`）：

1. 正例：seed `20261260`（`v66` 胜，v66 在 p1）
   - 回放：`.../20260304_172021_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261260_rounds-180.jsonl`
   - turning point：round19，`delta_army_lead_p0=-17`（对 p0/v64 不利，v66 受益）
   - 帧核对：round19 v66 出现技能动作 `Action=[4,1,2,12,6]` 后继续双线推进。
2. 负例：seed `20260358`（`v66` 负，v66 在 p0）
   - 回放：`.../20260304_172126_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260358_rounds-180.jsonl`
   - turning point：round131，`delta_army_lead_p0=-29`
   - 帧核对：round131 敌方出现 `Action=[7,7,3]`（召将）后配合推进，v66 在该窗口出现兵力摆动下滑。

回放结论：

1. 简化未造成 no-effect 恶化。
2. 但对 `v64` 的中盘 swing 失守样本仍存在，关键短板未修复。

### 80.5 回到生产口径的结论

生产 latest：`eval_20260304_171815`（adaptive，champion 稳定为 `v64`）。

1. 本轮不存在 gauntlet champion 切换导致的池跳变风险。
2. 结论仍以关键 head-to-head 为准：`v66 vs v64 = 103/200`，不能宣称“新版本优于 v64”。

### 80.6 风险、下一步与回合末自检

风险：

1. 去掉 `pressure_drop_veto` 后，对 `v64` 对位未改善，出现小幅回落。
2. 虽已减分支，但高压态 overlay 仍有多次 threat/应手评估，CPU 预算风险仍在。

下一步：

1. 不恢复整条复杂 veto 链，只考虑“单条件、单阈值”的主将近域保护剪枝（继续简化路线）。
2. 继续按 `v64` 关键对位 200 局口径复验，避免小样本误判。

回合末自检：

1. 是否触发搜索硬截止：
   - 代码仍有 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 当前日志无命中计数，无法量化触发次数。
2. 是否存在超过 `200ms` 单步 CPU 风险点：
   - 有硬截止兜底；
   - 风险点在高压态 overlay 内部多次候选评估。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 仅保留单一关键剪枝，避免多层 veto 叠加；
   - 维持 threat-source 早停与 base 回退路径。

## 81. 自动迭代回合（v66：移除 tactical_escape 特例链，统一 high-risk 评分）

### 81.1 固定目标与最新状态

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产评测：`/www/autolab/runtime/latest.json`（`eval_20260304_175404`）
- 迭代评测：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_180039`）
- 回放分析：
  - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
  - `/www/docs/replay_analysis/iter_latest.md`
- 对局索引：`paths.matches=/www/autolab/runtime/scopes/iter/eval_20260304_180039_matches.jsonl`（每行包含 `replay_file`）
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`
  - ANTWar：`global_state/danger`（危险态主分支）+ `reserved`（少分支保守主干）

生产口径必做判读（`config.pairs` + `champion.old/new`）：

1. `mode=adaptive`，`games_per_pair=6`，`pairs_count=45`。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v64_generals_rebuild`，本轮发生 champion 切换。
3. 风险判断：
   - 在 gauntlet 口径下 champion 切换属于高优先级风险；
   - 但本轮生产是 adaptive 抽样，不是 gauntlet 固定挑战池，`config.pairs` 直接由抽样列表决定；
   - 因此“gauntlet champion 切换导致池突变”风险在本轮 production latest 不直接触发，但该切换会影响后续 gauntlet 解释，应持续警惕。

### 81.2 算法级改动（in-place，继续减复杂度）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（未新建版本目录）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 改动仅在 `v66` 内部删除 tactical 特例链，不涉及架构不兼容。
2. 属于“小步可回滚”验证，先通过 gate/confirm 再决定是否固化快照。

“旧 AI 借鉴点 -> 映射 -> 代码落点”链路：

1. Generals 借鉴点：`threat_origin_cnt`
   - 映射：继续以 threat-source 饱和计数作为主风险输入，不新增额外状态。
   - 代码落点：`count_threat_sources_to_cell(..., cap)` + `choose_threat_source_probe_cap(...)`。
2. ANTWar 借鉴点：`global_state/danger + reserved`
   - 映射：危险态保留主干规则，删除 tactical_escape 特例分支（少状态、少补丁）。
   - 代码落点：删除 `is_tactical_escape_candidate(...)` 与 `tactical_*` 评分链，high-risk 统一用 `base_reply_veto + dominance + base_anchor_penalty`。

CPU 硬截止（保持）：

1. `CLOCK_THREAD_CPUTIME_ID`
2. `kSearchStepBudgetMs=200`
3. `hard_cutoff_hit` 回退路径

### 81.3 可复现实验（规定脚本，隔离 scope）

执行命令：

1. gate（关键三基线）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260350`
2. confirm（关键对手 v64）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260351`

结果：

1. gate `eval_20260304_174158`
   - `v66 vs v1 = 82/100`
   - `v66 vs v2 = 73/100`
   - `v66 vs v64 = 48/100`
2. confirm `eval_20260304_180039`
   - `v66 vs v64 = 57/100`
3. 合并关键对位（200 局）：
   - `v66 vs v64 = 105/200`（52.5%）

判读：

1. `v66` 对 `v1/v2` 依旧稳健领先。
2. `v66 vs v64` 从上一回合 `103/200` 回升到 `105/200`，但仍显著低于 `>55%` 判优线，不能宣称优于 `v64`。

### 81.4 Replay 分析与逐帧核对

回放分析（latest=`180039`）：

1. `analyzed_matches=100`，`missing_replay=0`。
2. 聚合：
   - `v66`：`win_rate=0.57`，`no_effect_rate=0.0656`，`avg_rounds=114.95`
   - `v64`：`win_rate=0.43`，`no_effect_rate=0.0661`，`avg_rounds=114.95`

原始回放逐帧（由 `paths.matches` 中 `replay_file` 直接核对）：

1. 正例：seed `20260351`（`v66` 胜，p0）
   - 回放：`.../20260304_180039_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260351_rounds-180.jsonl`
   - turning point：round120，`delta_army_lead_p0=+78`
   - 帧核对：round119-121 双方连续兵线推进，v66 在 round120-121 形成连续增益。
2. 负例：seed `20260353`（`v66` 负，p0）
   - 回放：`.../20260304_180040_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260353_rounds-180.jsonl`
   - turning point：round39，`delta_territory_lead_p0=-1`，`delta_army_lead_p0=+57`（对 p0 不利）
   - 帧核对：round39 敌方出现技能动作 `Action=[4,1,2,7,9]` 后继续推进，v66 未完成同窗反制。

回放结论：

1. 删除 tactical 特例链未引入 no-effect 恶化。
2. 关键对位仍被 `v64` 技能窗口压制，短板仍在中盘技能交换与反压节奏。

### 81.5 本轮借鉴点是否生效

1. Generals 借鉴点（threat-origin 饱和计数）
   - 证据：对 `v1/v2` 维持 `82/100`、`73/100`。
   - 判定：`部分生效`（稳态有效）。
2. ANTWar 借鉴点（danger/reserved 主分支、减少特例）
   - 证据：关键对位从 `103/200` 回升到 `105/200`，仅 +1.0pct。
   - 判定：`弱生效/未达目标`（仍未翻过 `>55%`）。

### 81.6 回到生产口径结论

生产 latest：`eval_20260304_175404`（adaptive，champion 现为 `v64`）。

1. 本轮不属于 gauntlet 切池结论场景，但 champion 切换已发生，应继续避免跨 tag Elo 绝对值比较。
2. 最终结论仍由关键 head-to-head 给出：`v66 vs v64 = 105/200`，仍不足以宣称 `v66` 优于 `v64`。

### 81.7 风险、下一步与回合末自检

风险：

1. 对 `v64` 关键对位仍低于判优线。
2. 高压态 overlay 虽已减分支，但仍存在多次候选评估，CPU 上限风险依旧。

下一步：

1. 继续简化路线：只加一个“主将近域技能响应”单条件剪枝，避免恢复多层特例。
2. 在当前 champion=`v64` 背景下，优先做 `v66 vs v64` 直连 200 局复验作为 gate，减少噪声。

回合末自检：

1. 是否触发搜索硬截止：
   - 代码仍有 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 当前日志无命中计数，无法直接量化触发次数。
2. 是否存在 >200ms 单步 CPU 风险：
   - 有硬截止兜底；
   - 风险点在 high-risk overlay 的候选评估循环。
3. 若有风险，下一轮降复杂度/改进剪枝：
   - 继续维持单分支剪枝，不叠加 tactical 特例；
   - 优先保留 base fallback 与 threat-source 早停。

## 82. 自动迭代回合（v66：技能窗口风险剪枝，in-place）

### 82.1 固定目标与最新状态

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产评测：`/www/autolab/runtime/latest.json`（`eval_20260304_180902`）
- 迭代评测：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_182150`）
- 回放分析：
  - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（`eval_20260304_182150`）
  - `/www/docs/replay_analysis/iter_latest.md`（本轮已同步到最新 tag）
- 对局索引：`paths.matches=/www/autolab/runtime/scopes/iter/eval_20260304_182150_matches.jsonl`（每行含 `replay_file`）
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`
  - ANTWar：`global_state + attack_flag + enemy_emp + reserved`（时窗态切换）

生产口径必做判读（`config.pairs` + `champion.old/new`）：

1. 当前生产 `mode=adaptive`，`games_per_pair=6`，`pairs_count=45`；`config.pairs` 中包含 `v64-v66` 对局。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`，本轮 latest 内未发生 champion 切换。
3. 风险判断：
   - gauntlet 口径下，champion 切换会带来高优先级对手池变化风险；
   - 但当前生产 latest 是 adaptive 且本 tag 内无切换，因此本轮不触发“切换致池突变”风险；
   - 仍需避免跨 tag/跨池直接比较 Elo 绝对值。

### 82.2 算法级改动（in-place，小步）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（未新建目录）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 改动只是在现有 overlay 风险门控上加单状态剪枝，不涉及架构不兼容。
2. 属于“可回滚的小步验证”，先 gate 再决定是否继续扩展。

“旧 AI 借鉴点 -> 映射 -> 代码落点”：

1. Generals 借鉴点：`threat_origin_cnt`
   - 映射：继续保留 threat-source 饱和计数作为主风险输入，避免恢复全量扫描。
   - 代码落点：`count_threat_sources_to_cell(...)` + `choose_threat_source_probe_cap(...)`。
2. ANTWar 借鉴点：`global_state + enemy_emp/reserved` 的“时窗态收紧”
   - 映射：新增“敌方技能窗口（靠近我方主将）”检测，仅在该窗口对 high-risk overlay 收紧。
   - 代码落点：
     - `detect_enemy_skill_window_near_main(...)`
     - `choose_overlay_tuning(..., enemy_skill_window)` 内收紧 `pool_limit/max_raw_drop/base_reply_veto_slack/dominance_threat_gain_min`
     - step 循环传入 `step_enemy_skill_window` 给 `select_best_move_overlay(...)`

CPU 硬截止（保持）：

1. `CLOCK_THREAD_CPUTIME_ID`
2. `kSearchStepBudgetMs=200`
3. `hard_cutoff_hit` 回退路径

### 82.3 可复现实验（规定脚本）

执行命令：

1. gate（关键三基线）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260352`

结果（`eval_20260304_182150`，每对手 100 局）：

1. `v66 vs v1 = 81/100`
2. `v66 vs v2 = 74/100`
3. `v66 vs v64 = 49/100`

判读：

1. 对 `v1/v2` 仍明显领先。
2. 对 `v64` 回落到 49%，相对上一回合 `52.5%` 退化。
3. 本轮对位样本达到 `>=100`，可作为二者相对强度结论；但不能据此宣称“v66 优于 v64”。

### 82.4 Replay 分析与逐帧核对

回放分析（latest=`182150`）：

1. `analyzed_matches=300`，`missing_replay=0`，`replay_parse_errors=0`。
2. `v66-v64` pair_stats：`v66 49/100`，`v64 51/100`，`avg_rounds=102.14`。
3. `v66` 聚合：`win_rate=0.68`（三对手合并），`no_effect_rate=0.0610`。

原始回放逐帧（由 `paths.matches` 中 `replay_file` 直接核对）：

1. 正例（`v66` 胜）：seed `20263282`，`.../20260304_182712_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20263282_rounds-180.jsonl`
   - turning point：round169，`delta_army_lead_p0=-51`（对 p1/v66 有利）
   - 帧核对：round169 附近 `v66` 连续推进动作（如 `Action=[1,10,9,1,2]`），未见对手同窗技能反制。
2. 负例（`v66` 负）：seed `20262370`，`.../20260304_182708_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20262370_rounds-180.jsonl`
   - turning point：round174，`delta_army_lead_p0=-20`（对 p0/v66 不利）
   - 帧核对：round174 对手出现技能动作 `Action=[4,16,2,14,13]`，随后跟进推进动作，`v66` 未完成反压。

回放结论：

1. “技能窗口收紧”方向命中现象（失败样本确有技能窗口冲击）。
2. 但当前收紧强度不足以扭转 `v66-v64` 关键对位胜率。

### 82.5 借鉴点是否生效

1. Generals 借鉴点（threat-origin 饱和计数）
   - 证据：`v66` 对 `v1/v2` 仍为 `81/100`、`74/100`。
   - 判定：`生效（稳态对弱基线维持优势）`。
2. ANTWar 借鉴点（时窗态收紧）
   - 证据：`v66-v64` 本轮为 `49/100`，未改善关键对位。
   - 判定：`未生效（方向合理但参数/触发仍不足）`。

### 82.6 回到生产口径的结论

生产 latest：`eval_20260304_180902`（adaptive，champion 仍为 `v64`）。

1. 本轮 production latest 内无 champion 切换，且为 adaptive，不构成 gauntlet 切池结论场景。
2. iter gate 显示 `v66-v64=49/100`，与生产 champion=`v64` 方向一致，不存在“生产与近期结论冲突”而必须补做额外复验的情况。
3. 结论标签：本轮改动对关键对位为退化信号，不能用于晋升结论。

### 82.7 风险、下一步与回合末自检

风险：

1. 技能窗口剪枝引入后，`v66-v64` 仍未转正且回落至 49%。
2. overlay 仍需多次 `compute_threat + enemy/my follow`，复杂度较高。

下一步：

1. 保持简化路线，不再叠加新特例链；优先尝试“主将危险分数驱动的单阈值动态 `enemy_weight`”替代多参数收紧。
2. 关键对位先按 `v66 vs v64` 做 `>=200` 局 confirm 再判断是否继续该方向。

回合末自检：

1. 是否触发搜索时间硬截止：
   - 代码层面仍有 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 当前评测日志未记录命中次数，无法量化是否触发。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 有硬截止兜底；
   - 风险点集中在 `select_best_move_overlay` 内多次候选评估与 follow-up 计算。
3. 若有风险，下一轮降复杂度/剪枝方案：
   - 进一步压缩高风险候选池上限，优先减少重复 threat 评估调用；
   - 若收益不稳，回退到更短路径（更少参数的单阈值策略）。

## 83. 自动迭代回合（v66：技能窗口仅作用 reserved floor，撤销 overlay 收紧）

### 83.1 固定目标与最新状态

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产评测：`/www/autolab/runtime/latest.json`（`eval_20260304_191239`）
- 迭代评测：`/www/autolab/runtime/scopes/iter/latest.json`（gate `eval_20260304_190128`，confirm `eval_20260304_192127`）
- 回放分析：
  - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（`eval_20260304_192127`）
  - `/www/docs/replay_analysis/iter_latest.md`（已同步到 `192127`）
- 对局索引：
  - gate：`/www/autolab/runtime/scopes/iter/eval_20260304_190128_matches.jsonl`
  - confirm：`/www/autolab/runtime/scopes/iter/eval_20260304_192127_matches.jsonl`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`
  - ANTWar：`global_state + reserved`（危险时增保守，不在危险时扩分支）

生产口径必做判读（`config.pairs` + `champion.old/new`）：

1. 当前生产 latest 是 `adaptive`，`games_per_pair=6`，`pairs_count=45`。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`，本 tag 内未发生 champion 切换。
3. `config.pairs` 本轮不含 `v64-v66` 直接对局。
4. 判读：gauntlet 口径下“champion 切换引发对手池变化”的高优先级风险本轮不触发；但因 adaptive 抽样池不同，仍禁止跨 tag 直接比较 Elo 绝对值。

### 83.2 算法级改动（in-place，简化）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（未新建版本目录）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`

本轮未新建版本目录原因：

1. 改动是对补充12的简化回收，属于同一结构内可回滚小步。
2. 尚未通过 `v64` 关键对位的严格判优线，不满足固化新目录条件。

“旧 AI 借鉴点 -> 映射 -> 代码落点”：

1. Generals 借鉴点：`threat_origin_cnt`
   - 映射：继续使用 threat-source 饱和计数维持主将风险识别。
   - 代码落点：`count_threat_sources_to_cell(...)`、`choose_threat_source_probe_cap(...)`。
2. ANTWar 借鉴点：`global_state/reserved`（仅在危险态保守）
   - 映射：撤销“技能窗口收紧 overlay 参数”这条补丁链，改为技能窗口只抬升 `main_safe_reserve`。
   - 代码落点：
     - 保留 `detect_enemy_skill_window_near_main(...)`
     - 新增 `apply_skill_window_reserve_floor(...)`
     - 在 step 循环中 `apply_reserved_release_floor(...)` 之后调用该函数
     - 删除 `enemy_skill_window` 对 `choose_overlay_tuning(...)` 与 `select_best_move_overlay(...)` 的参数穿透

CPU 硬截止（保持）：

1. `CLOCK_THREAD_CPUTIME_ID`
2. `kSearchStepBudgetMs=200`
3. `hard_cutoff_hit` 回退路径

### 83.3 可复现实验（规定脚本）

执行命令：

1. gate（关键三基线）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260353`
2. confirm（关键对手补样本）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260354`

结果：

1. gate `eval_20260304_190128`（每对手 100 局）
   - `v66 vs v1 = 81/100`
   - `v66 vs v2 = 74/100`
   - `v66 vs v64 = 56/100`
2. confirm `eval_20260304_192127`
   - `v66 vs v64 = 54/100`
3. 合并关键对位（200 局）：
   - `v66 vs v64 = 110/200`（55.0%）

判读：

1. `v1/v2` 优势稳定。
2. 关键对位从上一轮 `49/100` 明显恢复到 `56/100`（gate），但在 confirm 回落到 `54/100`。
3. 合并为 `55.0%`，仍未满足“>55%”严格宣称线，不能宣称 `v66` 明确优于 `v64`。

### 83.4 Replay 分析与逐帧核对

回放分析（latest=`192127`）：

1. `analyzed_matches=100`，`missing_replay=0`。
2. `v66-v64`：`54/100`，`avg_rounds=116.84`。
3. no-effect：`v66=0.06293`，`v64=0.06674`。

原始回放逐帧（confirm tag）：

1. 正例（`v66` 胜）：seed `20260354`
   - 回放：`.../20260304_192127_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260354_rounds-180.jsonl`
   - turning point：round122，`delta_army_lead_p0=+94`
   - 帧核对：round122 出现对手技能动作 `Action=[4,18,2,9,9]`，v66 仍保持连续推进（前后回合 `Action=[1,11,5,2,1]` 等）。
2. 负例（`v66` 负）：seed `20261265`
   - 回放：`.../20260304_192127_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261265_rounds-180.jsonl`
   - turning point：round136，`delta_army_lead_p0=+353`（对 p0/v64 有利）
   - 帧核对：round136 出现技能动作 `Action=[4,21,2,8,9]` 后，v64 连续推进，v66 未能在相邻回合反压。

回放结论：

1. “技能窗口 -> reserved floor”比“技能窗口 -> overlay收紧”更稳（胜率恢复）。
2. 但技能窗口失守样本仍存在，尚未达到稳定压制 `v64`。

### 83.5 借鉴点是否生效

1. Generals 借鉴点（threat-source 饱和计数）
   - 证据：`v66` 对 `v1/v2` 维持 `81/100`、`74/100`。
   - 判定：`生效`。
2. ANTWar 借鉴点（危险态 reserved 主干）
   - 证据：`v66-v64` 从补充12的 `49/100` 恢复到 gate `56/100`，但 confirm `54/100`。
   - 判定：`部分生效（恢复但不稳定）`。

### 83.6 回到生产口径的结论

生产 latest：`eval_20260304_191239`（adaptive，champion 维持 `v66`）。

1. 本轮 production latest 内无 champion 切换，不触发 gauntlet 切池高风险判读。
2. 本轮迭代结论以 iter 关键对位样本为准：`v66 vs v64 = 110/200 (55.0%)`，未达到 `>55%` 声称线。
3. 最终标签：`neutral`（较上一轮回升，但仍不足以宣称明确优势）。

### 83.7 风险、下一步与回合末自检

风险：

1. `v66-v64` 仍在 54~56% 区间波动，稳定性不足。
2. overlay 计算链仍偏重，潜在 CPU 压力仍存在。

下一步：

1. 继续简化：尝试只用单阈值动态 `enemy_weight`（基于 `step_main_danger`），不再新增分支状态。
2. 优先做 `v66-v64` 直连 `>=200` 局确认（固定两批 seed），再考虑是否进行更大结构改动。

回合末自检：

1. 是否触发搜索硬截止：
   - 代码仍含 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`；
   - 评测日志未输出触发次数，无法量化。
2. 是否存在 >200ms 单步 CPU 风险：
   - 有硬截止兜底；
   - 风险点仍在 `select_best_move_overlay` 的多次候选评估与 follow-up 计算。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 保持“少状态 + 单阈值”策略，继续压缩 overlay 内重复评估路径；
   - 若收益继续波动，回退到更短路径版本做对照复验。

## 84. 自动迭代回合（v66：overlay 改为单一连续风险分数，补充14）

### 84.1 固定目标与最新状态

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产评测：`/www/autolab/runtime/latest.json`（`eval_20260304_195549`）
- 迭代评测：
  - smoke：`/www/autolab/runtime/scopes/iter/eval_20260304_194044_summary.json`
  - gate：`/www/autolab/runtime/scopes/iter/eval_20260304_194245_summary.json`
  - confirm：`/www/autolab/runtime/scopes/iter/eval_20260304_200105_summary.json`
  - latest：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_200105`）
- 回放分析：
  - `python3 /www/autolab_replay_analyze.py --scope iter --latest`（已执行）
  - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（tag=`eval_20260304_200105`）
  - `/www/docs/replay_analysis/iter_latest.md`（已同步到 `200105`）
- 对局索引：`/www/autolab/runtime/scopes/iter/eval_20260304_200105_matches.jsonl`
- 旧 AI 参考：
  - Generals：`threat_origin_cnt`（来源计数参与风险）
  - ANTWar：`global_state/reserved`（危险态统一收紧）

生产口径必做判读（`config.pairs` + `champion.old/new`）：

1. 当前生产 latest 为 `adaptive`，`pairs_count=45`，且 `config.pairs` 内含 `['cpp_v64_generals_rebuild','cpp_v66_generals_weapon_econ']` 直接对局。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`，本 tag 内未发生 champion 切换。
3. 判读：本轮“champion 切换导致对手池突变”的高优先级风险未触发；但生产池为 adaptive，仍禁止跨 tag 直接比较 Elo 绝对值。

### 84.2 算法级改动（in-place，简化分支）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（未新建版本目录）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`
- 函数：`choose_overlay_tuning(...)`（约 623-690 行）

本轮未新建版本目录原因：

1. 改动是 `v66` 内部调参逻辑重构（离散门控 -> 连续风险分数），与现有结构兼容。
2. 尚未通过关键对手 `v64` 的严格判优阈值（`>55%` 且足量稳定），不满足固化新目录条件。

“旧 AI 借鉴点 -> 映射 -> 代码落点”：

1. Generals 借鉴点：`threat_origin_cnt`
   - 映射：`main_threat_sources` 从离散开关改为连续 `source_pressure`（饱和上限），直接参与 `risk_score`。
   - 代码落点：`choose_overlay_tuning(...)` 内 `source_pressure` 计算。
2. ANTWar 借鉴点：`global_state/reserved`
   - 映射：用单一 `risk_score` 驱动 overlay 保守程度（`enemy_weight/base_anchor_penalty/max_raw_drop` 等），替代多段 `high_risk/source_alert` 分支。
   - 代码落点：`choose_overlay_tuning(...)` 内 `risk_score/risk_alpha` 与一组连续参数映射。

CPU 硬截止（保持）：

1. `CLOCK_THREAD_CPUTIME_ID`
2. `kSearchStepBudgetMs=200`
3. `hard_cutoff_hit` 回退路径

### 84.3 可复现实验（规定脚本）

执行命令：

1. smoke（方向筛选，每对手 20 局）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=10 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260355`
2. gate（关键三基线，每对手 100 局）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260356`
3. confirm（关键对手补样本 100 局）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260357`

结果：

1. smoke `eval_20260304_194044`（仅方向）：
   - `v66 vs v1 = 16/20`
   - `v66 vs v2 = 14/20`
   - `v66 vs v64 = 13/20`
2. gate `eval_20260304_194245`：
   - `v66 vs v1 = 80/100`
   - `v66 vs v2 = 72/100`
   - `v66 vs v64 = 57/100`
3. confirm `eval_20260304_200105`：
   - `v66 vs v64 = 52/100`
4. 合并关键对位（`194245 + 200105`）：
   - `v66 vs v64 = 109/200`（54.5%）

判读：

1. `v66` 对 `v1/v2` 维持明显优势（`>=100` 局有效）。
2. 关键对位 `v64` 在 gate 为正（57%），但 confirm 回落到 52%，合并 200 局为 54.5%。
3. 未达到“对目标老版本 `>55%` 且足量稳定”的严格宣称线，不能宣称 `v66` 明确优于 `v64`。

### 84.4 Replay 分析与逐帧核对

回放分析（latest=`200105`）：

1. `rows_in_matches_file=100`，`analyzed_matches=100`，`missing_replay=0`，`replay_parse_errors=0`。
2. `v66-v64` pair_stats：`v66 52/100`，`v64 48/100`，`avg_rounds=119.94`。
3. 聚合动作分布显示 `v64` 的 `general_skill/call_general` 仍明显更多（`513/379` vs `418/217`）。

原始回放逐帧（由 `paths.matches` 的 `replay_file` 直接核对）：

1. 正例（`v66` 胜）：seed `20260357`
   - 回放：`.../20260304_200105_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260357_rounds-180.jsonl`
   - turning point（replay 分析）：round52，`delta_army_lead_p0=+82`
   - 帧核对：round52 前后主要是双方军团推进交换（如 `p0 Action=[1,3,8,4,2]`），未见同回合技能压制。
2. 负例（`v66` 负）：seed `20260358`
   - 回放：`.../20260304_200105_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260358_rounds-180.jsonl`
   - turning point（replay 分析）：round131，`delta_army_lead_p0=-29`
   - 帧核对：round131 出现对手征召与推进（`p1 Action=[7,7,3]`，后接推进动作），随后局面继续向 `v64` 倾斜。

回放结论：

1. 连续风险分数改造后，`v66` 在部分中盘交换回合更稳定（gate 有所回升）。
2. 但关键局仍会被 `v64` 的技能/征召节奏拉开，confirm 未维持 gate 优势。

### 84.5 借鉴点是否生效

1. Generals 借鉴点（来源计数连续化）
   - 证据：gate 对 `v1/v2` 仍为 `80/100`、`72/100`，关键对位 gate 提升到 `57/100`。
   - 判定：`部分生效`（方向正确，但对 `v64` 稳定性不足）。
2. ANTWar 借鉴点（单状态危险收紧）
   - 证据：`risk_score` 路径减少了离散分支；但 `v64` confirm 为 `52/100`。
   - 判定：`部分生效`（结构更简，但收益未稳定固化）。

### 84.6 回到生产口径的结论

生产 latest：`eval_20260304_195549`（adaptive，champion 维持 `v64`）。

1. 本轮 production latest 内无 champion 切换，切池高优风险不触发。
2. 生产池已含 `v64-v66` 对局；iter 的 gate 与 confirm 显示该对位仅弱优势且不稳定（`109/200=54.5%`）。
3. 结论标签：`neutral`（结构简化成立，但关键对位未达严格判优线）。

### 84.7 风险、下一步与回合末自检

风险：

1. `v66-v64` 在 gate 与 confirm 间波动（57% -> 52%），存在样本间不稳定。
2. `select_best_move_overlay` 仍有多次 `compute_threat + enemy/my follow` 评估，CPU 压力点未根除。

下一步：

1. 延续简化路线：在不增分支的前提下，进一步压缩高风险态 `pool_limit` 与重复评估路径。
2. 若下一轮仍波动，回退到补充13并做固定双 seed A/B 复验，确认是否确有净增益。

回合末自检：

1. 是否触发搜索硬截止：
   - 代码层面仍是 `CLOCK_THREAD_CPUTIME_ID + 200ms + hard_cutoff_hit`；
   - 本轮评测日志无触发计数，无法量化命中率。
2. 是否存在 >200ms 单步 CPU 风险：
   - 有硬截止兜底；
   - 风险点仍在 overlay 候选多次前瞻评估。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 继续减少候选池与重复评估次数；
   - 必要时将 overlay 回退为更短路径（更少参数）并做对照复验。

## 85. 自动迭代回合（v66：危险态门控下的前线征召窗口，补充15）

### 85.1 固定目标与最新状态

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产评测：`/www/autolab/runtime/latest.json`（当前 `tag=eval_20260304_203650`）
- 迭代评测：
  - smoke：`eval_20260304_202203`
  - gate：`eval_20260304_202328`
  - confirm：`eval_20260304_204034`
  - latest：`/www/autolab/runtime/scopes/iter/latest.json`（`tag=eval_20260304_204034`）
- 回放分析：
  - `python3 /www/autolab_replay_analyze.py --scope iter --latest`（已执行）
  - `latest.json`：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（`tag=eval_20260304_204034`）
  - 报告：`/www/docs/replay_analysis/iter_latest.md`（已同步）
- 对局索引：`/www/autolab/runtime/scopes/iter/eval_20260304_204034_matches.jsonl`

生产口径必做判读（`config.pairs` + `champion.old/new`）：

1. `config.pairs` 仍为 gauntlet 大池（45 对），且包含多组 `v64/v66` 相关配对（含直接 `['cpp_v64_generals_rebuild','cpp_v66_generals_weapon_econ']`）。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`，本 tag 内无 champion 切换。
3. 判读：本轮“champion 切换导致对手池突变”的高优风险未触发；但 gauntlet 池本身是动态构成，仍禁止跨 tag 比较 Elo 绝对值。

### 85.2 算法级改动（in-place，小步简化）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（未新建版本目录）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`
- 关键改动点：
  - 新增 `count_sub_generals_alive(...)`
  - 扩展 `choose_recruit_cell(...)`，加入 `accept_threshold` 与 `attack_window`
  - 在主循环征召阶段增加 `recruit_attack_window`（`duel_close && !reserve_state && enemy_sub_count > my_sub_count`）
  - 攻击窗口下把征召门槛从 `owned_cells>=10 / score>=20` 放宽为 `owned_cells>=8 / score>=14`

本轮未新建版本目录原因：

1. 仅为 v66 现有征召策略的单点重构，结构兼容且可回滚。
2. 关键对位 `v64` 尚未稳定过 gate/confirm 判优阈值，不满足固化新目录条件。

“旧 AI 借鉴点 -> 本游戏映射 -> 代码落点”：

1. Generals 借鉴点：前线附近按局部兵力结构补充副将（`call_generals` 的近战区补位思路）。
   - 映射：当主将接触距离近且我方副将数落后时，打开“进攻征召窗口”，优先在前线/靠近敌主将区域征召。
   - 代码落点：`count_sub_generals_alive` + `recruit_attack_window` + `choose_recruit_cell(..., attack_window=true)`。
2. ANTWar 借鉴点：`global_state/reserved` 下危险态先保守，非危险态才放开进攻动作。
   - 映射：若 `should_enable_reserved_gate` 判定处于保守危险态，则禁止进入 aggressive recruit window。
   - 代码落点：征召阶段 `reserve_state` 门控。

CPU 硬截止（保持）：

1. `CLOCK_THREAD_CPUTIME_ID`
2. `kSearchStepBudgetMs=200`
3. `hard_cutoff_hit` 保底回退路径

### 85.3 可复现实验（规定脚本）

执行命令（均为 iter scope，14 并发）：

1. smoke：
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=10 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260358`
2. gate：
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260359`
3. confirm：
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260360`

结果：

1. smoke `eval_20260304_202203`（方向筛选，60 局）
   - `v66 vs v1 = 14/20`
   - `v66 vs v2 = 16/20`
   - `v66 vs v64 = 13/20`
2. gate `eval_20260304_202328`（每对手 100 局）
   - `v66 vs v1 = 82/100`
   - `v66 vs v2 = 74/100`
   - `v66 vs v64 = 55/100`
3. confirm `eval_20260304_204034`（`v66 vs v64` 100 局）
   - `v66 vs v64 = 52/100`
4. 关键合并（gate+confirm）：
   - `v66 vs v64 = 107/200 = 53.5%`

判读：

1. `v66` 对 `v1/v2` 仍稳定优势（`>=100` 局有效）。
2. 关键目标 `v64` 合并 200 局仅 `53.5%`，低于“`>55%`”严格判优阈值。
3. 本轮结论仅可记为未通过关键 gate/confirm，不得宣称 `v66` 明确优于 `v64`。

### 85.4 Replay 分析与逐帧核对

回放分析（latest=`204034`）：

1. `rows_in_matches_file=100`，`analyzed_matches=100`，`missing_replay=0`，`replay_parse_errors=0`。
2. `pair_stats`：`v66 52/100`，`v64 48/100`，`avg_rounds=114.82`。
3. 动作聚合：`v64` 仍明显更高频使用 `general_skill/call_general`（`475/347`），`v66` 为（`361/215`）。

原始回放逐帧核对（由 `notable_matches.longest[].replay_file` 直接打开）：

1. 正例：seed `20261272`，turning point round `171`
   - 回放：`.../20260304_204034_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261272_rounds-180.jsonl`
   - round170~172 关键动作：
     - p0: `[1,14,11,3,1]`, `[1,12,7,3,1]`, `[1,9,12,3,21]`
     - p1(v66): `[1,11,9,1,1]`, `[1,10,5,1,1]`, `[1,9,10,4,2]`
2. 正例：seed `20261273`，turning point round `123`
   - 回放：`.../20260304_204035_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261273_rounds-180.jsonl`
   - round122~124 关键动作：
     - p0: `[1,12,13,3,2]`, `[1,11,13,3,2]`, `[1,11,14,3,3]`
     - p1(v66): `[1,11,11,4,2]`, `[1,10,13,2,3]`, `[1,9,13,2,2]`

回放结论：

1. 新征召窗口未改变“v64 技能/征召频率更高”的总体事实。
2. 中后盘仍主要由军团推进交换主导，关键局没有稳定观察到 v66 通过征召节奏持续反压 v64。

### 85.5 借鉴点是否生效

1. Generals 借鉴点（前线副将补位）
   - 证据：`v1/v2` 仍高胜率（`82/100`,`74/100`）；但对 `v64` 仅 `107/200`。
   - 判定：`部分生效`（中低压对局有收益，关键对手稳定性不足）。
2. ANTWar 借鉴点（reserved 门控）
   - 证据：危险态下 aggressive recruit 被抑制，未出现明显大样本崩盘；但关键对位未转化为稳定提升。
   - 判定：`部分生效`（控制了风险扩散，但未带来关键对位净增益）。

### 85.6 回到生产口径的结论

生产 latest：`eval_20260304_203650`（gauntlet/adaptive 池，champion 维持 `v66`）。

1. 本 tag 内 champion 未切换，未触发“切换导致对手池突变”高优风险。
2. 但生产池是 gauntlet 动态对阵，不能把本 tag Elo 与其他 tag 绝对值横比。
3. 结合 iter 关键对位 `107/200=53.5%`，本轮改动结论标签：`regression`（相对补充14关键对位回撤）。

### 85.7 风险、下一步与回合末自检

风险：

1. 对 `v64` 的胜率仍在 52%~55% 区间波动，本轮未越过严格门槛。
2. 单步评估仍依赖 overlay 多候选前瞻，CPU 压力点仍在。

下一步：

1. 不再增加征召分支，改为减少 overlay 重复评估（优先裁剪候选与 follow-up 计算次数）。
2. 先做固定对手 `v64` 的最小结构改动 A/B 复验（保持 200 局口径）再决定是否回退本补丁。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍含 `CLOCK_THREAD_CPUTIME_ID + 200ms + hard_cutoff_hit`；
   - 现有评测日志无命中计数，无法直接统计触发次数。
2. 是否存在 >200ms 单步 CPU 风险点：
   - 有硬截止兜底；
   - 风险点仍在 `select_best_move_overlay` 的多候选前瞻评估链。
3. 若有风险，下一轮降复杂度/剪枝方案：
   - 继续压缩候选池与重复 `compute_threat/follow-up` 评估；
   - 优先做“同结构减分支”而非再叠加新状态逻辑。

## 86. 自动迭代回合（v66：征召金币缓冲 + 技能窗口收敛，补充16）

### 86.1 固定目标与最新状态

- 固定目标已重读：`/www/docs/codex_objective_fixed.md`
- 生产评测：`/www/autolab/runtime/latest.json`（当前 `tag=eval_20260304_211513`）
- 迭代评测（隔离）：
  - smoke：`eval_20260304_210144`
  - gate：`eval_20260304_210310`
  - confirm：`eval_20260304_212040`
  - latest：`/www/autolab/runtime/scopes/iter/latest.json`（`tag=eval_20260304_212040`）
- 回放分析：
  - 已执行：`python3 /www/autolab_replay_analyze.py --scope iter --latest`
  - `latest.json`：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（`tag=eval_20260304_212040`）
  - `iter_latest.md`：`/www/docs/replay_analysis/iter_latest.md`（已同步）
- 对局索引：`/www/autolab/runtime/scopes/iter/eval_20260304_212040_matches.jsonl`

生产口径必做判读（`config.pairs` + `champion.old/new`）：

1. 当前生产 latest：`champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`，本 tag 内无 champion 切换。
2. `config.pairs` 仍为 gauntlet/adaptive 池（45 对）；当前池内 `v64` 相关对局 9 组、`v66` 仅 1 组，且无直接 `v64-v66` 对局。
3. 判读：本 tag 内“由 champion 切换导致对手池突变”未触发；但由于 champion 已稳定在 `v64`，`v66` 在生产池曝光显著下降，gauntlet 绝对 Elo 更不可跨 tag 直比（高优先级风险仍在）。

### 86.2 算法级改动（in-place，小步简化）

版本与代码落点：

- 版本：`cpp_v66_generals_weapon_econ`（未新建版本目录）
- 文件：`/www/ai_cpp/v66/ai_v66.cpp`
- 关键改动：
  1. 新增 `compute_recruit_coin_buffer(...)`：按危险态/技能窗口/接敌态计算征召前金币缓冲。
  2. 征召窗口从“`duel_close && !reserve && sub_count落后`”收敛为：
     - `duel_close && !reserve && sub_count落后 && enemy_skill_window`。
  3. 征召阈值由补充15的激进配置回收：
     - `owned_need: 8 -> 9`，`accept_threshold: 14 -> 16`。
  4. 增加硬条件：`my_coin >= 50 + recruit_coin_buffer` 才允许征召。

本轮未新建版本目录原因：

1. 改动是对补充15征召逻辑的风险收敛，结构完全兼容当前 `v66` 主体。
2. 关键对位尚未通过 gate/confirm，不满足“固化新目录”条件。

旧 AI 借鉴链路（强制项）：

1. Generals 借鉴点：`reserve_positions`（按经济/局势保留资源，不把扩张打满）。
   - 本游戏映射：征召前预留 `coin buffer`，避免为副将补位透支技能预算。
   - 代码落点：`compute_recruit_coin_buffer(...)` 与征召前 `my_coin >= 50 + buffer`。
2. ANTWar 借鉴点：`global_state + reserved`（危险态优先保守）。
   - 本游戏映射：`reserve_state` 与 `enemy_skill_window` 同时参与征召窗口门控，在高压态收紧进攻征召。
   - 代码落点：征召段 `recruit_attack_window` 条件和 `reserve_state` 分支。

CPU 硬截止（保持）：

1. `CLOCK_THREAD_CPUTIME_ID`
2. `kSearchStepBudgetMs=200`
3. `hard_cutoff_hit` 保底回退路径

### 86.3 可复现实验（规定脚本）

执行命令（iter scope，14 并发）：

1. smoke（每对手20局）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=10 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260361`
2. gate（每对手100局）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v1_current,cpp_v2_beam,cpp_v64_generals_rebuild --seed 20260362`
3. confirm（关键对手补样本100局）
   - `EXPERIMENT_RUNTIME_SCOPE=iter EXPERIMENT_GAMES_PER_PAIR=50 EXPERIMENT_MAX_ROUNDS=180 EXPERIMENT_JOBS=14 EXPERIMENT_CPU_POLICY=all /www/scripts/autolab_eval_experiment_once.sh --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild --challengers cpp_v66_generals_weapon_econ --opponents cpp_v64_generals_rebuild --seed 20260363`

结果：

1. smoke `eval_20260304_210144`：
   - `v66 vs v1 = 17/20`
   - `v66 vs v2 = 15/20`
   - `v66 vs v64 = 11/20`（smoke 仅方向）
2. gate `eval_20260304_210310`：
   - `v66 vs v1 = 81/100`
   - `v66 vs v2 = 72/100`
   - `v66 vs v64 = 53/100`
3. confirm `eval_20260304_212040`：
   - `v66 vs v64 = 44/100`
4. 关键合并（gate+confirm）：
   - `v66 vs v64 = 97/200 = 48.5%`

判读：

1. 对 `v1/v2` 仍保持明显优势（`>=100` 局有效）。
2. 关键对位 `v64` 从 gate 的 `53%` 在 confirm 回落到 `44%`，200局合并仅 `48.5%`，明确回归。
3. 不能宣称 `v66` 优于 `v64`，且当前改动方向失败。

### 86.4 Replay 分析与逐帧核对

回放分析（latest=`212040`）：

1. `rows_in_matches_file=100`，`analyzed_matches=100`，`missing_replay=0`，`replay_parse_errors=0`。
2. `pair_stats`：`v66 44/100`，`v64 56/100`，`avg_rounds=118.09`。
3. 动作分布：`v64` 的 `general_skill/call_general` 仍显著高于 `v66`（`466/392` vs `351/146`）。

原始回放逐帧（直接打开 replay）：

1. 胜例（`v66` 胜）seed `20260363`，turning point round `166`
   - 回放：`.../20260304_212040_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260363_rounds-180.jsonl`
   - round165~167 片段含敌方技能动作：`p1 Action=[4,19,2,10,9]`，随后双方继续推进交换。
2. 负例（`v66` 负）seed `20260365`，turning point round `125`
   - 回放：`.../20260304_212040_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260365_rounds-180.jsonl`
   - round125 双方均放技能：`p0 Action=[4,0,2,11,8]`、`p1 Action=[4,1,2,12,10]`，但后续 `v64` 延续推进并守住优势。

回放结论：

1. 本轮“征召金币缓冲”确实降低了 `v66` 的征召频率（`call_general` 降至 146），但对关键对位形成反效果。
2. `v64` 在技能/征召节奏优势仍在，`v66` 中后盘反压能力进一步下降。

### 86.5 借鉴点是否生效

1. Generals 借鉴点（资源保留再扩张）
   - 证据：征召频率下降明显，但 `v66-v64` 合并降至 `48.5%`。
   - 判定：`未生效（对关键对位为负收益）`。
2. ANTWar 借鉴点（危险态保守门控）
   - 证据：高压态征召被抑制，未见无脑扩张；但关键样本中被 `v64` 节奏压制更明显。
   - 判定：`部分生效（控险生效，但收益端失败）`。

### 86.6 回到生产口径的结论

生产 latest：`eval_20260304_211513`（champion 维持 `v64`）。

1. 当前生产 tag 内 champion 未切换；但 gauntlet 池中 `v66` 曝光低，不能以生产 Elo 判定该改动优劣。
2. 关键判定以 iter 头对头样本为准：`v66 vs v64 = 97/200`，显著低于阈值。
3. 结论标签：`regression`。

### 86.7 风险、下一步与回合末自检

风险：

1. 征召收紧后，`v66` 对 `v64` 的技能/征召对抗进一步恶化。
2. `select_best_move_overlay` 仍是 CPU 热点（多候选 + 双侧 follow-up 评估）。

下一步：

1. 回退本轮征召收紧或做 A/B 双开关（仅保留一个门控项），优先恢复关键对位基线。
2. 在不增状态的前提下，继续减少 overlay 重复评估次数（先减复杂度，再看收益）。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍含 `CLOCK_THREAD_CPUTIME_ID + 200ms + hard_cutoff_hit`；
   - 评测汇总暂无触发计数。
2. 是否存在 >200ms 单步 CPU 风险点：
   - 有硬截止兜底；
   - 风险点仍在 overlay 候选前瞻链。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 缩减 overlay 候选与 follow-up 评估调用；
   - 避免再增加新的条件状态，优先回到更短路径策略。

### 87.1 固定目标与最新状态

已重新读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产评测（唯一权威口径）：

1. `latest.json` 当前为 `eval_20260304_221558`，`mode=adaptive`，`config.pairs` 共 `45` 组。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`（本 tag 内未发生 champion 切换）。
3. 必做判读（gauntlet 高优先级风险）：
   - 本轮对手池**未受 champion 切换直接影响**（old/new 未切换）；
   - 但 `adaptive` 采样导致跨 tag `config.pairs` 变化，生产 Elo 绝对值仍不可跨 tag 直接比较。

iter 评测（仅用于候选筛选）：

1. `iter/latest.json` 当前为 `eval_20260304_220641`（`v66 vs v64` 单对手，100局）。
2. `iter/replay_analysis/latest.json` 与 `docs/replay_analysis/iter_latest.md` 已同步到 `220641`：
   - `analyzed_matches=100`，`missing_replay=0`，`replay_parse_errors=0`。
3. 对局索引已核对：
   - `paths.matches=/www/autolab/runtime/scopes/iter/eval_20260304_220641_matches.jsonl`；
   - 每行包含 `replay_file`，可直接逐帧打开。

### 87.2 算法级改动（in-place，小步简化，continue）

本轮继续沿用并验证上一心跳已落地的 `v66` in-place 算法改造，不新建版本目录。

1. 代码落点：`/www/ai_cpp/v66/ai_v66.cpp`
2. 关键改动（已在代码中）：
   - `compute_recruit_coin_buffer(...)` 简化为 `reserve_state + duel_close + sub_gap` 的短路径逻辑（减少条件层数）；
   - `recruit_attack_window` 调整为 `duel_close && !reserve_state && sub_gap > 0`；
   - 窗口阈值采用更直接的 `owned_need=8`、`accept_threshold=15.0`。
3. 搜索硬截止（硬约束）：
   - 仍使用 `CLOCK_THREAD_CPUTIME_ID` + `200ms` CPU 截止，`hard_cutoff_hit` 保底回退路径未移除。
4. 本轮未新建版本原因：
   - 当前改动与 `v66` 结构兼容，属于可回滚的小步简化与门控重排，未达到“需新目录固化快照”的必要性。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_value/impact_value` 风险评估与门控思路（`past_AIs/Generals-AI/main.cpp`）
   - 映射：本游戏中用 `duel_close + threat/accept_threshold` 控制征召触发；
   - 落点：`choose_recruit_cell(...)` + `recruit_attack_window` 判定。
2. ANTWar 借鉴点：`safe_coin + danger/reserved` 资源保留机制（`past_AIs/ANTWar-AI/main.cpp`）
   - 映射：本游戏中引入 `reserve_state` 与 `recruit_coin_buffer`，危险态优先保留金币；
   - 落点：`compute_recruit_coin_buffer(...)` 与征召 coin guard。

### 87.3 可复现实验（规定脚本）

全部实验均使用：`/www/scripts/autolab_eval_experiment_once.sh`（iter 隔离、14核并发）。

1. smoke（方向筛选）`eval_20260304_214146`：
   - `v66 vs v1 = 17/20`
   - `v66 vs v2 = 15/20`
   - `v66 vs v64 = 10/20`（smoke，不用于最终判优）
2. gate（关键基线，>=100 局）`eval_20260304_214520`：
   - `v66 vs v1 = 82/100`
   - `v66 vs v2 = 75/100`
   - `v66 vs v64 = 58/100`
3. confirm-1 `eval_20260304_220042`：
   - `v66 vs v64 = 50/100`
4. confirm-2（本轮新增）`eval_20260304_220641`（seed=`20260390`）：
   - `v66 vs v64 = 58/100`

本轮新增实验命令（可复现）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260390
```

关键汇总：

1. `v66 vs v64`（gate + confirm-2）=`(58+58)/200 = 116/200 = 58.0%`。
2. `v66 vs v64`（gate + confirm-1 + confirm-2）=`166/300 = 55.3%`。
3. 对 `v1/v2` 目前仅各 `100` 局，尚不满足“宣称优于多个老版本（每个>=200局）”的严格条件。

### 87.4 Replay 分析与逐帧核对

latest replay 分析（tag=`220641`）：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：`v66 58/100`，`v64 42/100`，`avg_rounds=119.17`。
3. 动作分布：
   - `v66`: `general_skill=362`, `call_general=206`
   - `v64`: `general_skill=504`, `call_general=397`

原始回放索引核对（来自 `paths.matches`）：

1. 胜例：seed `20260390`
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260304_220641/20260304_220641_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260390_rounds-180.jsonl`
2. 负例：seed `20261302`
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260304_220641/20260304_220641_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261302_rounds-180.jsonl`

回放判读：

1. `v66` 在降低征召/技能动作频率后，仍能在本轮 confirm 达到 `58/100`，说明“保留金币+窗口征召”并非只带来保守副作用。
2. 负例中仍可见大地盘波动（`terr_swing` 高样本），说明关键风险仍在中后盘波动管理，而非单点征召触发本身。

### 87.5 借鉴点是否生效

1. Generals 借鉴点（威胁评估门控）
   - 证据：`v66 vs v64` 在新增 confirm（`220641`）达到 `58/100`，且 gate+confirm-2 为 `116/200`；
   - 判定：`部分生效`（关键对位回升，但仍有 seed 波动）。
2. ANTWar 借鉴点（safe_coin/danger reserve）
   - 证据：`v66` 的 `call_general` 低于 `v64`（`206` vs `397`）且本轮仍赢 `58%`；
   - 判定：`生效`（资源保留未阻断胜率，改善了过度征召风险）。

### 87.6 回到生产口径的结论

生产 latest：`eval_20260304_221558`，`champion v64 -> v64`。

1. 本 tag 内 champion 未切换，故“对手池受 champion 切换影响”风险本轮为否；
2. 但生产为 adaptive/gauntlet，跨 tag Elo 绝对值仍不可直接当成最终强弱结论；
3. 与 iter 最新 head-to-head 结果不冲突（iter 新增 confirm 显示 `v66` 对 `v64` 回升到 `58/100`）。

结论标签：`promising`（仅针对 `v66 vs v64` 的当前方向，非全池最终结论）。

### 87.7 风险、下一步与回合末自检

风险：

1. `v66-v64` 关键对位存在 seed 波动（`50/100` 到 `58/100`），稳定性尚不足。
2. 搜索 CPU 热点仍在 overlay 候选 + 双侧 follow-up 评估链。

下一步：

1. 继续补做 `v66 vs v64` confirm（再加 `>=100`，优先凑到 400+ 总样本）验证是否稳定维持 `>55%`；
2. 对 `v1/v2` 追加到各 `>=200` 才讨论“优于多个老版本”的严格宣称；
3. 若波动再次放大，优先减 overlay 评估调用次数，而不是叠新分支。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码中硬截止机制仍在（`CLOCK_THREAD_CPUTIME_ID` + `200ms` + 回退）；
   - 评测汇总未提供触发计数，无法从报告直接统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 有潜在风险点（overlay 多候选链），但有硬截止兜底。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 收紧 overlay 候选池与 follow-up 调用上限；
   - 保持 in-place 简化，不新增状态机分支。

### 88.1 固定目标与最新状态

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产评测（唯一权威口径）：

1. 当前 `latest.json` 为 `eval_20260304_223616`，`mode=adaptive`，`config.pairs` 共 `45` 组。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`。
3. 必做判读（gauntlet 高优先级风险）：
   - 本 tag 内无 champion 切换，因此“对手池受 champion 切换影响”= 否；
   - 但 `adaptive` 采样仍导致跨 tag 对手池变化，生产 Elo 绝对值不可跨 tag 直接比较。

迭代评测（隔离，仅候选筛选）：

1. `iter/latest.json` 更新为 `eval_20260304_224141`（`v66 vs v64`，100 局）。
2. replay latest 同步更新：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json` 与 `docs/replay_analysis/iter_latest.md` 均为 `224141`。
3. 对局索引核对：
   - `paths.matches=/www/autolab/runtime/scopes/iter/eval_20260304_224141_matches.jsonl`；
   - 每行均含 `replay_file`，可直接逐帧核对。

### 88.2 算法级改动（in-place，小步简化）

本轮继续在 `v66` 上做 in-place 小步改造，不新建版本目录。

改动目标：

1. 针对 replay 中高频“大地盘波动”样本，减少远端征召导致的扩张摆动。
2. 保持结构简化，不引入新状态机层。

代码落点：`/www/ai_cpp/v66/ai_v66.cpp`

1. `choose_recruit_cell(...)` 新增主将支持半径门控参数 `main_dist_cap`：
   - 若候选格距离我方主将超过上限，直接跳过；
   - 额外增加“靠近主将”支持分，降低远端孤立征召概率。
2. 征召阶段根据态势设置距离上限：
   - `reserve_state ? 9 : (recruit_attack_window ? 12 : 10)`。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_value/impact_value` 的“安全位置优先”思想。
   - 本游戏映射：征召位置必须受主将支持半径约束，避免远端高波动落点。
   - 代码落点：`choose_recruit_cell(...)` 的 `main_dist_cap` 和主将距离得分。
2. ANTWar 借鉴点：`danger/reserved` 下收紧扩张。
   - 本游戏映射：`reserve_state` 时把征召半径收得更紧（cap=9）。
   - 代码落点：征召前 `recruit_main_dist_cap` 计算与传参。

本轮未新建版本原因：

1. 改动与 `v66` 主体结构完全兼容，仅是征召候选筛选的局部简化。
2. 尚未通过更大样本 gate/confirm 稳定验证，不具备固化新目录的必要性。

### 88.3 可复现实验（规定脚本）

按要求使用：`/www/scripts/autolab_eval_experiment_once.sh`（iter 隔离、14核并发）。

命令：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260391
```

结果（`eval_20260304_224141`）：

1. `v66 vs v64 = 56/100`（满足两 AI 相对强度比较最小样本 `>=100`）。
2. 不足以据此做多 AI 排序结论，仅可作为关键对位 confirm 信号。

### 88.4 Replay 分析与逐帧核对

latest replay（`224141`）摘要：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：`v66 56/100`，`v64 44/100`，`avg_rounds=120.58`。
3. 动作分布：
   - `v66`: `general_skill=409`, `call_general=209`
   - `v64`: `general_skill=551`, `call_general=402`

原始回放核对（来自 `paths.matches`）：

1. 胜例：seed `20260391`
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260304_224141/20260304_224141_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260391_rounds-180.jsonl`
   - 关键 turning point：round `136`，`delta_army_lead_p0=+321`。
2. 负例：seed `20261302`
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260304_224141/20260304_224141_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261302_rounds-180.jsonl`
   - 关键 turning point：round `121`，`delta_territory_lead_p0=+2`，`delta_army_lead_p0=+46`。

回放结论：

1. 新门控未削弱关键对位基本胜率（仍 >55%）；
2. 但“最大地盘波动”样本仍高，说明仅靠征召半径收紧无法单独消除中后盘摆动。

### 88.5 借鉴点是否生效

1. Generals 借鉴点（安全位置优先）
   - 证据：征召逻辑已落地主将支持半径门控，关键对位 `56/100` 未退化到阈值下。
   - 判定：`部分生效`。
2. ANTWar 借鉴点（danger/reserved 收敛扩张）
   - 证据：`reserve_state` 对征召半径更严格；`v66` 征召动作数仍显著低于 `v64`（209 vs 402）。
   - 判定：`生效`（控险方向成立，收益幅度有限）。

### 88.6 回到生产口径的结论

生产 latest（本轮读取时）为 `eval_20260304_223616`，`champion` 仍 `v64 -> v64`。

1. 生产 gauntlet 无 champion 切换事件，不存在“由切换触发的池子突变”风险；
2. 生产 Elo 仅作候选信号，最终优劣仍以 iter 头对头样本为主；
3. 本轮新样本显示 `v66 vs v64 = 56/100`，方向正向但提升幅度有限。

结论标签：`neutral`。

### 88.7 风险、下一步与回合末自检

风险：

1. 关键对位虽 >55%，但波动仍大（replay 中高 `terr_swing` 样本持续存在）。
2. 搜索热点仍在 overlay 候选 + 双侧 follow-up，存在接近 200ms 风险。

下一步：

1. 继续做 `v66 vs v64` confirm（再加 `>=100`），优先把当前策略总样本拉高到 `>=200` 新增窗口；
2. 若波动不收敛，优先削减 overlay 候选/跟随评估调用而非新增分支。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍有 `CLOCK_THREAD_CPUTIME_ID` + `200ms` + 回退；
   - 当前评测输出未暴露触发计数。
2. 是否存在 >200ms 单步 CPU 风险点：
   - 风险点仍在 overlay 深评估；
   - 但存在 CPU 硬截止兜底。
3. 下一轮降复杂度/改进剪枝计划：
   - 在高 danger/低收益候选下进一步压缩 overlay pool 和 my-follow 调用次数。

### 89.1 固定目标与最新状态

已重新读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json` 为 `eval_20260304_225705`，`config.pairs` 共 `45` 组，且包含 `v64-v66` 直接对局。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`（本 tag 内未切换）。
3. 必做判读（gauntlet 高优先级风险）：
   - 本 tag 内“对手池受 champion 切换影响”= 否；
   - 但近期上一生产 tag `eval_20260304_225052` 发生过 `v64 -> v66` 切换，跨 tag 对手池与 Elo 绝对值仍不可直接比较。

iter 口径（仅候选筛选）：

1. 本轮新增 `iter/latest.json = eval_20260304_230146`。
2. replay latest 同步为 `eval_20260304_230146`，`rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`。

### 89.2 算法改动（沿用本轮 in-place 代码）

本轮不新建版本目录，继续验证已落地的 `v66` in-place 小步改动：

1. 在 `choose_recruit_cell(...)` 增加主将支持半径门控 `main_dist_cap`；超半径候选直接剔除。
2. 增加主将邻近支持分（更偏向可联动落点）。
3. 征召窗口半径：`reserve_state ? 9 : (recruit_attack_window ? 12 : 10)`。

代码位置：`/www/ai_cpp/v66/ai_v66.cpp`。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat/impact` 的“安全位置优先”。
   - 映射：征召必须受主将支持半径约束，减少远端孤立扩张。
   - 落点：`choose_recruit_cell(...)` 的距离门控与支持分。
2. ANTWar 借鉴点：`danger/reserved` 下收敛扩张。
   - 映射：`reserve_state` 时把征召半径收紧到 `9`。
   - 落点：`recruit_main_dist_cap` 的态势分支。

本轮未新建版本原因：

1. 本轮是对既有征召候选筛选的局部简化与验证，结构与 `v66` 完全兼容；
2. 关键对位尚未形成“稳定 >55%”的 confirm 证据，不满足固化快照必要性。

### 89.3 可复现实验（规定脚本）

执行命令（iter 隔离，14核并发）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260392
```

结果：`eval_20260304_230146`

1. `v66 vs v64 = 53/100`（满足两 AI 相对强度门槛 `>=100`）。
2. 与上一轮同代码 confirm（`56/100`）合并：`109/200 = 54.5%`，未达到 `>55%` 严格线。

### 89.4 Replay 分析与对局核对

replay 报告（`iter_latest.md` / `latest.json`）：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：`v66 53` vs `v64 47`，`avg_rounds=110.12`。
3. 动作分布：
   - `v66`: `general_skill=289`, `call_general=237`
   - `v64`: `general_skill=351`, `call_general=350`

从 `paths.matches` 与 replay 逐帧索引核对：

1. `v66` 胜例（seed=`20260392`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260304_230146/20260304_230146_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20260392_rounds-180.jsonl`
   - turning point：round `2`，`delta_army_lead_p0=+20`（对 p0=v64 有利，随后反转），全局 `army_lead_abs_max=15`，对局较短（`max_round=9`）。
2. `v66` 负例（seed=`20260393`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260304_230146/20260304_230146_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20260393_rounds-180.jsonl`
   - turning point：round `13`，`delta_army_lead_p0=+20`；`territory_lead_abs_max=24`，`army_lead_abs_max=53`。

replay 结论：

1. 主将支持半径门控并未造成明显崩盘（关键对位仍保持小幅正胜率）；
2. 但高波动样本仍存在（本批 `army_swing` 峰值可达 `814`），说明“远端征召收紧”尚不足以单独解决中后盘摆动。

### 89.5 本轮结论（回到生产口径）

1. 生产 latest（`225705`）本 tag 内 champion 未切换，单 tag 对手池切换风险为否；
2. 但近期已发生过 `v64->v66` 切换，gauntlet 跨 tag Elo 绝对值不可直接作为版本强弱结论；
3. 关键对位新证据：同代码两次 confirm 合并 `109/200=54.5%`，当前不支持“稳定优于 v64”的结论。

结论标签：`neutral`。

### 89.6 风险、下一步与回合末自检

风险：

1. `v66-v64` 仍处于窄优势/高波动区间（`54.5%`，未过 `>55%` 严格线）。
2. 复杂度热点仍在 overlay 候选 + follow-up 评估链。

下一步：

1. 再补 `v66 vs v64` `>=100` 局 confirm，优先把“当前代码窗口”扩大到 `>=300` 再判优；
2. 若仍 <55%，优先继续减法：收紧 `pool_limit` 与 follow-up 次数，而非加新状态分支。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码硬截止机制仍在（`CLOCK_THREAD_CPUTIME_ID` + `<=200ms` + 回退）；
   - 本轮评测输出未暴露触发计数，未观测到可证明的触发样本。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 仍有潜在风险点（overlay 深评估）；
   - 已有硬截止兜底，风险可控但未消失。
3. 若有风险，下轮降复杂度/剪枝方案：
   - 在高 danger 态进一步下调 overlay 候选上限；
   - 减少低收益 follow-up 评估调用，保留主约束链。

### 90.1 固定目标与最新状态

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260304_231915`。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`。
3. `config.pairs` 共 `45` 组，且包含 `v66-v64` 直接对局。
4. 必做判读（gauntlet 高优先级风险）：
   - 本 tag 内 champion 未切换，因此“本轮对手池受 champion 切换影响”= 否；
   - 但 gauntlet 口径跨 tag 对手池可能变化，生产 Elo 绝对值仍不可跨 tag 直接比较。

iter 口径（候选筛选）：

1. 两轮 confirm：`eval_20260304_232120` 与 `eval_20260304_232544`。
2. 最新 iter（`latest.json`）当前指向 `232544`，`paths.matches` 为：
   - `/www/autolab/runtime/scopes/iter/eval_20260304_232544_matches.jsonl`

### 90.2 算法级改动（in-place，小步）

文件：`/www/ai_cpp/v66/ai_v66.cpp`。

改动内容（征召阶段 danger 源门控）：

1. 新增低成本主将 threat-source 探测（cap=2）用于征召安全门控：
   - `recruit_main_threat_sources`、`recruit_source_alert`。
2. 仅在“非 reserve 且非 source_alert 且 sub_gap>0”时开启前压征召窗口：
   - `recruit_attack_window = duel_close && !reserve_state && !recruit_source_alert && sub_gap>0`。
3. source alert 下统一收紧征召策略：
   - 增加金币缓冲（`+10`）；
   - 收缩主将支持半径（`cap=8`）；
   - 抬高征召阈值（`accept_threshold=22`）。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin`（来源数）思想。
   - 映射：用主将受威胁来源数作为“是否允许前压征召”的门控；
   - 代码落点：征召段 `recruit_main_threat_sources/recruit_source_alert`。
2. ANTWar 借鉴点：`danger/reserved + safe_coin`。
   - 映射：source alert 视作 danger 子态，提升 `coin buffer` 并收紧扩张半径；
   - 代码落点：`recruit_coin_buffer += 10` 与 `recruit_main_dist_cap/accept_threshold` 收紧。

本轮未新建版本原因：

1. 改动与 `v66` 结构兼容，属于单段策略门控减法，不需拆新目录；
2. 尚未通过 `>=200` 局稳定优势 gate，不满足固化新版本的必要性。

### 90.3 可复现实验（规定脚本）

全部使用：`/www/scripts/autolab_eval_experiment_once.sh`（iter 隔离、14核）。

1. confirm-A（seed=`20260393`）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260393
```

结果：`eval_20260304_232120`，`v66 vs v64 = 58/100`。

2. confirm-B（seed=`20260450`）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260450
```

结果：`eval_20260304_232544`，`v66 vs v64 = 49/100`。

合并（本轮同代码）

1. `v66 vs v64 = (58+49)/200 = 107/200 = 53.5%`。
2. 达到 `>=100` 的两 AI 比较门槛，但未达到“稳定优于 v64（>55%）”线。

### 90.4 Replay 分析与原始回放核对

A. `eval_20260304_232120`（`58/100`）

1. replay：`rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. 动作分布：
   - `v66`: `general_skill=371`, `call_general=204`
   - `v64`: `general_skill=512`, `call_general=401`
3. 样本核对：
   - 胜例 seed `20260393`：
     `/www/autolab/runtime/scopes/iter/replays/eval_20260304_232120/20260304_232120_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260393_rounds-180.jsonl`
     turning point：round `61`，`delta_territory_lead_p0=-3`，`delta_army_lead_p0=-20`。
   - 负例 seed `20260394`：
     `/www/autolab/runtime/scopes/iter/replays/eval_20260304_232120/20260304_232120_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260394_rounds-180.jsonl`
     turning point：round `30`，`delta_territory_lead_p0=-1`，`delta_army_lead_p0=+13`（后续短局失稳）。

B. `eval_20260304_232544`（`49/100`，latest）

1. replay：`rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. 动作分布：
   - `v66`: `general_skill=327`, `call_general=180`
   - `v64`: `general_skill=379`, `call_general=322`
3. 样本核对：
   - 胜例 seed `20260450`：
     `/www/autolab/runtime/scopes/iter/replays/eval_20260304_232544/20260304_232544_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260450_rounds-180.jsonl`
     turning point：round `16`，`delta_territory_lead_p0=+2`，`delta_army_lead_p0=-6`。
   - 负例 seed `20261361`：
     `/www/autolab/runtime/scopes/iter/replays/eval_20260304_232544/20260304_232544_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261361_rounds-180.jsonl`
     turning point：round `24`，`delta_territory_lead_p0=-1`，`delta_army_lead_p0=+23`。

Replay 结论：

1. source alert 门控能显著压低征召/技能频次（相较旧样本），但对胜率提升不稳定；
2. 两次 confirm 呈现“58/100 与 49/100”强波动，说明当前门控对不同对局分布敏感。

### 90.5 回到生产口径的结论

1. 生产 latest `231915` 本 tag 内 champion 未切换，对手池切换风险为否；
2. 生产 gauntlet 与 iter 两轮 confirm 未出现“必须立即做生产冲突复验”的强冲突信号；
3. 本轮同代码 `200` 局仅 `53.5%`，不支持“稳定优于 v64”的结论。

结论标签：`regression`（相对补充18/19 的窗口表现未改善）。

### 90.6 风险、下一步与回合末自检

风险：

1. 关键对位高波动（`58/100` -> `49/100`），策略对 seed/对局形态敏感；
2. source alert 门控可能过早抑制前压，导致部分局势丢失反打窗口。

下一步：

1. 不新增目录，先做“减法回滚”：保留 threat-source 探测，但撤销 `accept_threshold=22` 的过强抬升，仅保留 coin buffer/半径收紧；
2. 再做 `v66-v64` `>=100` 局 confirm，观察波动是否收敛。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 搜索链硬截止仍在（`CLOCK_THREAD_CPUTIME_ID` + `200ms` + 回退）；
   - 评测产物未暴露触发计数，无法统计触发次数。
2. 是否存在超过 `200ms` 单步 CPU 风险点：
   - 潜在风险仍在 overlay 深评估链；
   - 已有硬截止兜底。
3. 若有风险，下轮如何降复杂度/改进剪枝：
   - 继续压缩低收益候选与 follow-up 调用；
   - 优先保留单一主约束链，避免叠加新状态补丁。

### 91.1 固定目标与最新状态

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260304_235453`。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`。
3. `config.pairs` 共 `45` 组，本 tag 不含 `v66-v64` 直接对局。
4. 必做判读（gauntlet 高优先级风险）：
   - 本 tag 内 champion 未切换，因此“本轮对手池受 champion 切换影响”= 否；
   - 但上一生产阶段发生过 `v64 -> v66` 切换，跨 tag 仍存在对手池变化风险，生产 Elo 绝对值不可直比。

iter 口径（仅候选筛选）：

1. 本轮新评测：`eval_20260305_000203`（`v66 vs v64`，100 局）。
2. replay latest 同步为 `eval_20260305_000203`，`rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`。

### 91.2 算法级改动（in-place，小步回滚）

文件：`/www/ai_cpp/v66/ai_v66.cpp`。

本轮执行“减法回滚”以降低过保守：

1. 保留 `recruit_source_alert` 的 threat-source 探测、保币（`+10`）与半径收紧（`cap=8`）；
2. 移除 source-alert 下额外阈值抬升分支：
   - `accept_threshold` 从 `recruit_attack_window ? 15 : (source_alert ? 22 : 20)`
   - 简化为 `recruit_attack_window ? 15 : 20`。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin` 来源计数。
   - 映射：继续以来源数触发 `source_alert` 门控。
2. ANTWar 借鉴点：`safe_coin / reserved`。
   - 映射：高压子态保留额外金币缓冲与扩张半径收缩，但不再叠加额外评分阈值分支。

本轮未新建版本原因：

1. 仅是补充20的局部回滚，结构完全兼容 `v66`；
2. 尚未形成稳定 gate 证据，不满足新目录固化条件。

### 91.3 可复现实验（规定脚本）

命令：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260460
```

结果：`eval_20260305_000203`

1. `v66 vs v64 = 53/100`（达到两 AI 相对强度结论门槛 `>=100`）。
2. 相比补充20的单批次低点（`49/100`）有回升，但仍未过 `>55%` 线。

### 91.4 Replay 分析与原始回放核对

replay 摘要（`eval_20260305_000203`）：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`；
2. `pair_wins`：`v66 53`，`v64 47`，`avg_rounds=108.08`；
3. 动作分布：
   - `v66`: `general_skill=317`, `call_general=203`
   - `v64`: `general_skill=498`, `call_general=377`

原始回放核对（来自 matches/replay_file）：

1. 负例 seed `20260460`：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_000203/20260305_000203_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20260460_rounds-180.jsonl`
   - turning point：round `5`，`delta_territory_lead_p0=-1`，`delta_army_lead_p0=-11`（短局失衡）。
2. 胜例 seed `20260461`：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_000203/20260305_000203_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20260461_rounds-180.jsonl`
   - turning point：round `29`，`delta_territory_lead_p0=-3`，`delta_army_lead_p0=-3`（中盘反超）。

Replay 判读：

1. “阈值回滚”后仍保留低频征召/技能特征（相较 v64 明显更少）；
2. 但短局波动仍在，说明本轮只部分修复了补充20的保守过度问题。

### 91.5 回到生产口径的结论

1. 生产 latest 本 tag 内 champion 未切换，对手池切换风险为否；
2. 因生产本 tag 不含 `v66-v64` 直接对局，而本轮 iter `53/100` 未形成强优势，当前不做“明显优于 v64”宣称；
3. 如需判优，仍需继续 head-to-head 补样本（建议再 `>=100`）。

结论标签：`neutral`。

### 91.6 风险、下一步与回合末自检

风险：

1. `v66-v64` 仍在 50% 附近摆动（`53/100`），稳定性不足；
2. 生产 gauntlet 本 tag 无直接 `v66-v64` 对局，难直接与迭代结论闭环。

下一步：

1. 在当前代码上继续补 `v66-v64` confirm（再 `>=100`），形成同代码 `>=200` 窗口；
2. 若仍低于 `55%`，优先继续减法（减少 source-alert 额外干预）而非新加分支。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 硬截止机制仍在：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + 回退；
   - 评测输出未提供触发计数，无法直接统计。
2. 是否存在超过 `200ms` 单步 CPU 风险点：
   - 风险点仍在 overlay 深评估链；
   - 有硬截止兜底。
3. 若有风险，下轮降复杂度/剪枝计划：
   - 继续压缩低收益候选评估，减少 follow-up 调用次数。

### 92.1 固定目标与最新状态

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260305_005347`（`mode=adaptive`）。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v64_generals_rebuild`（`promoted=true`）。
3. `config.pairs` 共 `45` 组；本 tag 内包含多组 `v64`/`v66` 相关对阵，但不含直接 `v64-v66` 对打。
4. 必做判读（gauntlet 高优先级风险）：本轮存在 champion 切换，因此“对手池受 champion 切换影响”= 是（高优先级风险，跨 tag Elo 绝对值不可直比）。

iter 口径（仅候选筛选）：

1. 最新 iter：`eval_20260305_010140`。
2. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_010140_matches.jsonl`。
3. replay latest：`eval_20260305_010140`，`rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`。

### 92.2 算法级改动（in-place，小步简化）

文件：`/www/ai_cpp/v66/ai_v66.cpp`。

本轮改动（不新建版本目录）：

1. 新增 `RecruitPlan` 与 `choose_recruit_plan(...)`，用单一连续 `aggression` 分数统一驱动征召参数（`coin_buffer/main_dist_cap/owned_need/accept_threshold/attack_window`）。
2. 移除原征召段的离散组合分支（`recruit_source_alert + recruit_attack_window + 多重 ternary`），将决策收敛到一个策略函数输出，减少状态拼接与补丁层数。
3. 保持搜索链路不变，`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退仍生效。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin`（威胁来源数）思想。
   - 映射：`main_threat_sources` 直接进入 `aggression` 连续评分，不再单独拉出 `source_alert` 状态树。
   - 代码落点：`choose_recruit_plan(...)` 与征召调用点。
2. ANTWar 借鉴点：`reserved/safe_coin`。
   - 映射：`reserve_state` 直接压低 `aggression` 并抬升 `coin_buffer`、收紧 `main_dist_cap`，把保币与扩张收敛放在同一主干。
   - 代码落点：`choose_recruit_plan(...)`。

本轮未新建版本原因：

1. 改动与 `v66` 结构兼容，且属于“分支收敛”的 in-place 简化，不需要新目录固化。
2. 当前仅完成 100 局 gate 样本，尚未达到同代码 `>=200` confirm，不满足新版本固化条件。

### 92.3 可复现实验（规定脚本）

命令（iter 隔离，14 核）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260395
```

结果：`eval_20260305_010140`

1. `v66 vs v64 = 56/100`（满足两 AI 比较门槛 `>=100`）。
2. 本轮作为“生产 champion 切换后”的 head-to-head 复验，满足“冲突先复验”要求。

### 92.4 Replay 分析与原始回放核对

replay 摘要（`iter_latest.md` / `latest.json`）：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：`v66 56` vs `v64 44`，`avg_rounds=112.99`。
3. 动作分布：
   - `v66`: `general_skill=261`, `call_general=176`
   - `v64`: `general_skill=492`, `call_general=395`

原始回放逐帧核对（来自 `paths.matches`）：

1. 胜例（`v66` 胜，seed=`20261307`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_010140/20260305_010140_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261307_rounds-180.jsonl`
   - replay turning point：round `86`，`delta_army_lead_p0=-37`（对 p1 的 `v66` 有利）。
   - 帧动作抽样：`Round 44, Player 1, Action [7,8,8]`；`Round 104, Player 1, Action [7,11,8]`（`v66` 采用低频征召）。
2. 负例（`v66` 负，seed=`20260396`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_010140/20260305_010140_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260396_rounds-180.jsonl`
   - replay turning point：round `140`，`delta_army_lead_p0=-241`（`v66` 失衡）。
   - 帧动作抽样：对手 `v64` 在 `Round 24/49/81/96` 多次 `Action [7,...]`，而 `v66` 仅见 `Round 111, Player 0, Action [7,8,1]`（征召节奏偏慢）。

replay 结论：

1. 简化后的连续门控能维持较低技能/征召频次，同时本轮胜率回到 `56/100`。
2. 但极端波动仍明显（`army_swing` 峰值 `619`、`terr_swing` 峰值 `104`），中后盘稳定性仍未解决。

### 92.5 借鉴点是否生效

1. Generals 借鉴点（threat-origin 连续化）：
   - 证据：本轮 `v66-v64` 回到 `56/100`，且 `no_effect_rate` 优于 `v64`（`0.062` vs `0.065`）。
   - 判定：`部分生效`（方向为正，但样本仍偏少）。
2. ANTWar 借鉴点（reserved/safe_coin 收敛）：
   - 证据：`v66` 的 `call_general` 与 `general_skill` 持续显著低于 `v64`（`176/261` vs `395/492`），回放中 `v66` 征召触发更克制。
   - 判定：`生效`（控险目标达成）。

### 92.6 回到生产口径的结论

1. 生产 latest 已发生 `v66 -> v64` champion 切换，说明对手池存在切换影响风险。
2. 针对该冲突，本轮已补做 head-to-head 复验（`100` 局）并得到 `v66 56/100`。
3. 但同代码仅 `100` 局，尚未达到“稳定优于”所需的 `>=200` confirm；当前不宣称 `v66` 稳定强于 `v64`。

结论标签：`neutral`。

### 92.7 风险、下一步与回合末自检

风险：

1. 关键对位虽回升到 `56/100`，但样本仅 100，且高波动局依旧多。
2. 生产口径刚发生 champion 切换，跨 tag 排名波动可能继续放大解读偏差。

下一步：

1. 在当前同代码上补做 `v66-v64` 额外 `>=100` 局 confirm，使窗口达到 `>=200` 再判优。
2. 若 200 局仍无法稳定 `>55%`，优先再做减法：下调高风险态 overlay 候选上限，而非新增状态分支。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍具备 `CLOCK_THREAD_CPUTIME_ID` + `200ms` + 回退；
   - 评测产物无触发计数字段，未能从日志直接统计触发次数。
2. 是否存在超过 `200ms` 单步 CPU 风险点：
   - 风险点仍在 overlay 候选评估链；
   - 但有硬截止兜底，未出现“无保底”的路径。
3. 若有风险，下轮如何降复杂度/改进剪枝：
   - 按 `main_danger` 收缩 overlay pool 上限；
   - 提前终止低收益候选评估，减少 follow-up 调用。

### 93.1 固定目标与最新状态（continue）

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260305_011624`（`mode=adaptive`）。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`（`promoted=false`）。
3. `config.pairs` 共 `45` 组，且包含 `v64-v66` 直接对阵（1 组）。
4. 必做判读（gauntlet 高优先级风险）：
   - 就本 tag 而言，champion 未切换（old=new），因此“本轮对手池是否受 champion 切换影响”= 否；
   - 但跨 tag 仍存在高风险（上一生产 tag 出现过 `v66 -> v64`），禁止跨 scope/跨池直接比较 Elo 绝对值。

iter 口径（仅候选筛选）：

1. 最新 iter：`eval_20260305_012201`。
2. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_012201_matches.jsonl`。
3. replay latest：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（tag 同为 `eval_20260305_012201`），`rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`。

### 93.2 算法级改动（in-place，继续简化分支）

文件：`/www/ai_cpp/v66/ai_v66.cpp`。

本轮改动（不新建版本目录）：

1. 征召评分继续收敛：`choose_recruit_cell(...)` 从 `bool attack_window` 切换为连续 `aggression` 输入，移除离散开窗分支。
2. 新评分主干改为连续权重：
   - `front_weight = 20.0 + 2.0 * aggression`
   - `main_support_weight = 0.75 - 0.30 * aggression`
   - `enemy_main_weight = 1.0 + 0.8 * aggression`
3. 调用点直接传入 `RecruitPlan.aggression`，保持 `coin_buffer/main_dist_cap/accept_threshold` 与评分同源，减少补丁层。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin/threat_origin_cnt`（来源计数）。
   - 本游戏映射：`main_threat_sources` 进入 `choose_recruit_plan(...)` 的连续扣分，进一步驱动 `aggression` 而非离散 alert 开关。
   - 代码落点：`choose_recruit_plan(...)` + `choose_recruit_cell(...)`。
2. ANTWar 借鉴点：`reserved/safe_coin`（危险态资源保留）。
   - 本游戏映射：`reserve_state` 降低 `aggression`，并抬升 `coin_buffer`、收紧 `main_dist_cap`，同一主干完成“保币+收敛征召”。
   - 代码落点：`compute_recruit_coin_buffer(...)` + `choose_recruit_plan(...)`。

本轮未新建版本原因：

1. 仅为 `v66` 内部参数化重构（结构兼容），不需要目录级分叉；
2. 当前仅有一轮 `100` 局 gate 证据，未达到 `>=200` confirm 固化门槛。

### 93.3 可复现实验（规定脚本）

命令（iter 隔离，14 核）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260396
```

结果：`eval_20260305_012201`

1. `v66 vs v64 = 56/100`（满足两 AI 比较门槛 `>=100`，但仅为 gate 级样本）。
2. 本轮不宣称“稳定优于 v64”，仍需同代码补足到 `>=200` 局 confirm。

### 93.4 Replay 分析与原始回放核对

replay 摘要（`iter_latest.md` / `latest.json`）：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：`v66 56` vs `v64 44`，`avg_rounds=115.31`。
3. 动作分布：
   - `v66`: `general_skill=326`, `call_general=177`
   - `v64`: `general_skill=522`, `call_general=391`

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. 胜例（`v66` 胜，seed=`20261313`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_012201/20260305_012202_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261313_rounds-180.jsonl`
   - replay turning point：round `171`，`delta_army_lead_p0=-224`（对 p1 的 `v66` 有利）。
   - 附近动作抽样：`Round 176, Player 1, Action [7,2,4]`，`Round 177/178, Player 1, Action [4,3,2,4,6]/[4,18,2,4,6]`。
2. 负例（`v66` 负，seed=`20260439`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_012201/20260305_012341_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260439_rounds-180.jsonl`
   - replay turning point：round `138`，`delta_army_lead_p0=-177`（p0 侧 `v66` 失衡）。
   - 附近动作抽样：`Round 138, Player 0, Action [4,25,2,7,10]` 后，`Round 139, Player 1, Action [7,5,11]`。

replay 结论：

1. 结构简化后，`v66` 仍保持较低技能/征召频次（相对 `v64` 明显更克制）；
2. 高摆动局仍多（`army_swing` 峰值 `619`、`terr_swing` 峰值 `104`），关键转折仍集中在中后盘技能与征召链附近。

### 93.5 借鉴点是否生效

1. Generals 借鉴点（threat-origin 连续化）：
   - 证据：本轮保持 `56/100` 正胜率，且把来源压力映射到连续 `aggression` 后，征召评分分支继续减少。
   - 判定：`部分生效`（方向为正，但波动仍大）。
2. ANTWar 借鉴点（reserved/safe_coin 收敛）：
   - 证据：`v66` 的 `call_general/general_skill` 继续显著低于 `v64`（`177/326` vs `391/522`），说明保币与克制征召仍在起作用。
   - 判定：`生效`（控险有效，但需平衡终盘爆发）。

### 93.6 回到生产口径的结论

1. 生产 latest（`eval_20260305_011624`）本 tag 内 champion 未切换，因此本 tag 的对手池不受“本轮 champion 切换”影响。
2. 但 gauntlet/adaptive 口径仍受 champion 身份与配对集影响，跨 tag/跨 scope Elo 绝对值不可直接对比。
3. 本轮 iter `56/100` 仅作为候选信号；当前结论维持 `neutral`，不做“稳定优于 v64”宣称。

### 93.7 风险、下一步与回合末自检

风险：

1. `v66-v64` 仍只有单批次 `100` 局证据，统计稳定性不足；
2. replay 显示高波动局未收敛，终盘技能链仍可能放大摆动。

下一步：

1. 维持同代码补做 `v66-v64` 额外 `>=100` 局 confirm，形成 `>=200` 窗口后再判优；
2. 若 confirm 未稳定 `>55%`，优先继续减法：缩小高危险态 overlay 候选池与 follow-up 深评估次数。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物未记录触发计数，无法从现有日志直接统计次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 候选深评估链（`select_best_move_overlay`）；
   - 已有 deadline 检查与 base 回退，不存在“无保底”路径。
3. 若有风险，下轮如何降复杂度或改进剪枝：
   - 用 `main_threat_sources/main_danger` 进一步压缩 overlay pool；
   - 对低优先级候选更早退出，减少 follow-up 评估调用。

### 94.1 固定目标与最新状态（continue）

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260305_013618`（`mode=adaptive`）。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v66_generals_weapon_econ`（`promoted=true`）。
3. `config.pairs` 共 `45` 组，本 tag 内无直接 `v64-v66` 对打（`0` 组）。
4. 必做判读（gauntlet 高优先级风险）：
   - 本轮 production 发生 champion 切换，因此“本轮对手池是否受 champion 切换影响”= 是（高优先级风险）；
   - 在该前提下，跨 tag Elo 绝对值不可直比，iter Elo 仅用于候选筛选。

iter 口径（仅候选筛选）：

1. 最新 iter：`eval_20260305_014143`。
2. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_014143_matches.jsonl`。
3. replay latest：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（tag 同为 `eval_20260305_014143`），`rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`。

### 94.2 算法级改动（in-place，连续主干增补 lead 信号）

文件：`/www/ai_cpp/v66/ai_v66.cpp`。

本轮改动（不新建版本目录）：

1. 新增 `sum_owned_army(...)`，用于快速估计当前局面兵力领先度。
2. `choose_recruit_plan(...)` 新增 `territory_lead/army_lead` 入参，将“领先降攻、落后提攻”收敛到单一连续 `lead_signal`：
   - `lead_signal = 0.55 * terr_signal + 0.45 * army_signal`
   - `aggression -= 0.20 * max(0, lead_signal)`
   - `aggression += 0.10 * max(0, -lead_signal)`
3. 维持 `RecruitPlan` 单主干，不新增离散状态树；调用点在征召前直接计算领先度并传入。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`impact_value`（安全位置/优势局面不盲目冒进）。
   - 本游戏映射：优势局面（地盘/兵力领先）自动降低征召 aggression，减少无效扩张。
   - 代码落点：`choose_recruit_plan(...)` 的 `lead_signal` 抑制项。
2. ANTWar 借鉴点：`global_state + reserved/safe_coin`（顺逆风态差异化资源策略）。
   - 本游戏映射：落后时仅做受控增攻（`+0.10 * max(0,-lead_signal)`），避免直接切到离散攻击态。
   - 代码落点：`choose_recruit_plan(...)` 的 `lead_signal` 提升项。

本轮未新建版本原因：

1. 改动是 `v66` 内部连续策略补充，结构完全兼容，不需要新目录；
2. 仅完成 100 局 gate 样本，尚不足以触发版本固化。

### 94.3 可复现实验（规定脚本）

命令（iter 隔离，14 核）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260397
```

结果：`eval_20260305_014143`

1. `v66 vs v64 = 57/100`（满足两 AI 比较门槛 `>=100`）。
2. 仍属于 gate 级样本，未达同代码 `>=200` confirm。

### 94.4 Replay 分析与原始回放核对

replay 摘要（`iter_latest.md` / `latest.json`）：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：`v66 57` vs `v64 43`，`avg_rounds=114.56`。
3. 动作分布：
   - `v66`: `general_skill=332`, `call_general=173`
   - `v64`: `general_skill=513`, `call_general=390`

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. 胜例（`v66` 胜，seed=`20260446`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_014143/20260305_014401_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260446_rounds-180.jsonl`
   - replay turning point：round `133`，`delta_territory_lead_p0=-2`，`delta_army_lead_p0=332`。
   - 附近动作抽样：`Round 131/133/134` 出现连续技能动作 `[4,...]`（双方换技能后 p0 侧建立兵力优势）。
2. 负例（`v66` 负，seed=`20260439`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_014143/20260305_014343_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260439_rounds-180.jsonl`
   - replay turning point：round `138`，`delta_army_lead_p0=-177`。
   - 附近动作抽样：`Round 138, Player 0, Action [4,25,2,7,10]` 后，`Round 139, Player 1, Action [7,5,11]`。

replay 结论：

1. 新增 lead 信号后，`v66` 仍保持“低征召/低技能频次”相对特征；
2. 高波动局依旧存在（`army_swing` 峰值仍达 `619`，`terr_swing` 峰值 `106`），本轮更多体现为胜率小幅改善而非波动根治。

### 94.5 借鉴点是否生效

1. Generals 借鉴点（impact 优势抑攻）：
   - 证据：`v66-v64` 从上一轮 `56/100` 到本轮 `57/100`，且 `v66` 的 `no_effect_rate` 继续优于 `v64`（`0.0616` vs `0.0650`）。
   - 判定：`部分生效`（方向为正，但增益幅度小）。
2. ANTWar 借鉴点（顺逆风受控增攻）：
   - 证据：`v66` 的 `call_general/general_skill` 仍显著低于 `v64`（`173/332` vs `390/513`），说明“保币与克制”主干仍在。
   - 判定：`生效`（控险有效，待 confirm 验证稳定性）。

### 94.6 回到生产口径的结论

1. 生产 latest 已切换 champion（`v64 -> v66`），说明当前 gauntlet 对手池与 champion 身份已变化。
2. 但本 tag `config.pairs` 内无直接 `v64-v66` 对局，不能把该次切换直接视为 head-to-head 充分证据。
3. 本轮 iter `57/100` 仅作为候选信号；当前结论保持 `neutral`，不做“稳定优于 v64”宣称。

### 94.7 风险、下一步与回合末自检

风险：

1. 同代码仍只有 `100` 局，统计置信度不足；
2. replay 高波动样本仍多，终盘技能链导致的 swing 问题尚未收敛。

下一步：

1. 继续同代码补 `v66-v64` 至少 `>=100` 局 confirm，形成 `>=200` 窗口后再判优；
2. 若波动仍高，优先减法：进一步压缩高 danger 态下的 overlay pool/深评估次数。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 搜索链仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物未暴露触发计数字段，无法直接统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 主要风险仍在 overlay 候选深评估路径；
   - 现有 deadline 检查与 base 回退仍在，无“无兜底”路径。
3. 若有风险，下轮如何降复杂度或改进剪枝：
   - 在高 danger/source 态进一步收紧候选池规模；
   - 提前终止低收益候选的 follow-up 评估链。

### 95.1 固定目标与最新状态（continue）

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260305_015407`（`mode=adaptive`）。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`（`promoted=false`）。
3. `config.pairs` 共 `45` 组，本 tag 内无直接 `v64-v66` 对打（`0` 组）。
4. 必做判读（gauntlet 高优先级风险）：
   - 本 tag champion 未切换（old=new），因此“本轮对手池是否受 champion 切换影响”= 否；
   - 但 gauntlet 仍受 champion/对手池影响，跨 tag 与跨 scope Elo 绝对值仍不可直比。

iter 口径（仅候选筛选）：

1. 最新 iter：`eval_20260305_020147`。
2. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_020147_matches.jsonl`。
3. replay latest：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（tag 同为 `eval_20260305_020147`），`rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`。

### 95.2 算法级改动（in-place，连续 pressure 信号）

文件：`/www/ai_cpp/v66/ai_v66.cpp`。

本轮改动（不新建版本目录）：

1. `choose_recruit_plan(...)` 新增 `enemy_skill_window` 输入，把 threat-source 与技能窗口合并为连续 `pressure_signal`：
   - `pressure_signal = 0.65 * source_signal + 0.35 * skill_signal`
   - `aggression -= 0.32 * pressure_signal`
2. `coin_buffer` 与 `main_dist_cap` 同步连续化：
   - `coin_buffer += round(pressure_signal * 6.0)`；
   - `main_dist_cap -= round(pressure_signal)`，最终 `clamp(8,12)`。
3. 去掉 `owned_need` 的二值分支，改为连续公式：
   - `owned_need = clamp(10 - round(aggression*2), 8, 10)`。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin`/`impact_value` 连续威胁与安全度。
   - 本游戏映射：`main_threat_sources + enemy_skill_window` 收敛为同一个 `pressure_signal` 影响征召强度。
   - 代码落点：`choose_recruit_plan(...)`。
2. ANTWar 借鉴点：`global_state/reserved/safe_coin`。
   - 本游戏映射：危险窗口直接提高 `coin_buffer`、收缩 `main_dist_cap`，保持“危险态保币”主干。
   - 代码落点：`choose_recruit_plan(...)` 与征召调用点 `enemy_skill_window` 输入。

本轮未新建版本原因：

1. 改动是 `v66` 内部连续化重构，结构兼容；
2. 仅有 100 局 gate 样本，未达到版本固化门槛。

### 95.3 可复现实验（规定脚本）

命令（iter 隔离，14 核）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260398
```

结果：`eval_20260305_020147`

1. `v66 vs v64 = 46/100`（满足双 AI 比较门槛 `>=100`，但结果回归）。
2. 相比上一轮 `57/100` 明显下滑，本轮判定为 regression 信号。

### 95.4 Replay 分析与原始回放核对

replay 摘要（`iter_latest.md` / `latest.json`）：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：`v66 46` vs `v64 54`，`avg_rounds=107.94`。
3. 动作分布：
   - `v66`: `general_skill=303`, `call_general=174`
   - `v64`: `general_skill=366`, `call_general=369`

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. 胜例（`v66` 胜，seed=`20260420`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_020147/20260305_020228_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20260420_rounds-180.jsonl`
   - replay turning point：round `150`，`delta_territory_lead_p0=2`，`delta_army_lead_p0=-137`（对 p1 的 `v66` 有利）。
   - 附近动作抽样：`Round 147, Player 0, Action [7,9,12]`。
2. 负例（`v66` 负，seed=`20261310`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_020147/20260305_020147_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20261310_rounds-180.jsonl`
   - replay turning point：round `157`，`delta_territory_lead_p0=1`，`delta_army_lead_p0=472`（p0 侧 `v66` 失衡）。
   - 附近动作抽样：`Round 159, Player 1, Action [7,2,10]`。

replay 结论：

1. 本轮 `pressure_signal` 增强后，`v66` 仍保持低征召频次，但关键对位胜率下滑；
2. 波动进一步恶化：`army_swing` 峰值到 `726`，`terr_swing` 峰值到 `124`。

### 95.5 借鉴点是否生效

1. Generals 借鉴点（threat/impact 连续化）：
   - 证据：分支确实减少，但 `v66-v64` 从 `57/100` 回落至 `46/100`。
   - 判定：`本轮未生效`（方向错误）。
2. ANTWar 借鉴点（danger 保币）：
   - 证据：`v66` 的 `call_general` 继续显著低于 `v64`（`174` vs `369`），但胜率反而回落。
   - 判定：`过度生效`（保守过头，压制了中后盘对抗强度）。

### 95.6 回到生产口径的结论

1. 生产 latest（`eval_20260305_015407`）本 tag champion 未切换，切换风险在本 tag 内为否。
2. 但该 tag 无 `v64-v66` 直接对局，不能用 production adaptive 排名替代 head-to-head 证据。
3. 本轮 iter 明确回归（`46/100`），当前不宣称 `v66` 优于 `v64`。

结论标签：`regression`。

### 95.7 风险、下一步与回合末自检

风险：

1. 新 pressure 信号权重偏大，导致征召/进攻窗口过度收缩；
2. replay 显示极端 swing 上升，稳定性未改善反而恶化。

下一步：

1. 先做减法回退：下调 `pressure_signal` 影响系数（尤其 `aggression` 扣分与 `coin_buffer` 加成）；
2. 在同代码上补做 confirm（再 `>=100` 局）验证是否恢复到 `>=55%` 区间。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物未记录触发计数，无法直接统计次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 主要风险点仍在 overlay 候选深评估链；
   - 仍有 deadline 检查与 base 回退兜底。
3. 若有风险，下轮如何降复杂度或改进剪枝：
   - 继续收缩高 danger 态候选池；
   - 减少低收益 follow-up 评估并提前退出。

### 96.1 固定目标与最新状态（continue）

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260305_021316`（`mode=adaptive`）。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`（`promoted=false`）。
3. `config.pairs` 共 `45` 组，本 tag 无直接 `v64-v66` 对打（`0` 组）。
4. 必做判读（gauntlet 高优先级风险）：
   - 本 tag champion 未切换（old=new），因此“本轮对手池是否受 champion 切换影响”= 否；
   - 但 gauntlet 仍依赖 champion 与对手池，跨 tag/跨 scope Elo 绝对值不可直比。

iter 口径（仅候选筛选）：

1. 最新 iter：`eval_20260305_022119`。
2. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_022119_matches.jsonl`。
3. replay latest：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`（tag 同为 `eval_20260305_022119`），`rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`。

### 96.2 算法级改动（in-place，pressure 信号软化）

文件：`/www/ai_cpp/v66/ai_v66.cpp`。

本轮改动（不新建版本目录）：

1. 对补充25的 `pressure_signal` 做减法回退，降低过保守副作用：
   - `pressure_signal` 权重从 `0.65/0.35` 调整为 `0.78/0.22`（source/skill）。
2. 下调压力惩罚强度：
   - `aggression` 扣分从 `0.32` 降到 `0.14`；
   - `coin_buffer` 压力附加从 `+round(pressure*6)` 降到 `+round(pressure*2)`。
3. 去除 `main_dist_cap` 的压力二次扣减，减少同一信号在多维度重复惩罚（简化补丁叠加）。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`impact_value/threat_origin` 的“风险连续化而非硬开关”。
   - 本游戏映射：保留连续 `pressure_signal`，但弱化惩罚斜率，避免过度抑攻。
   - 代码落点：`choose_recruit_plan(...)` 的 `pressure_signal` 与 `aggression` 公式。
2. ANTWar 借鉴点：`reserved/safe_coin` 的“危险态保币但不过度锁死”。
   - 本游戏映射：保留轻量 `coin_buffer` 压力附加，移除过强半径惩罚。
   - 代码落点：`choose_recruit_plan(...)` 的 `coin_buffer/main_dist_cap` 计算。

本轮未新建版本原因：

1. 本轮是对补充25的 in-place 回退修正，结构兼容；
2. 结果仅 100 局 gate 样本，未满足版本固化条件。

### 96.3 可复现实验（规定脚本）

命令（iter 隔离，14 核）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260399
```

结果：`eval_20260305_022119`

1. `v66 vs v64 = 59/100`（满足双 AI 比较门槛 `>=100`）。
2. 相比补充25（`46/100`）明显恢复，但仍属 gate 样本，不能替代 `>=200` confirm。

### 96.4 Replay 分析与原始回放核对

replay 摘要（`iter_latest.md` / `latest.json`）：

1. `rows=100`，`analyzed=100`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：`v66 59` vs `v64 41`，`avg_rounds=113.51`。
3. 动作分布：
   - `v66`: `general_skill=310`, `call_general=170`
   - `v64`: `general_skill=496`, `call_general=390`

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. 胜例（`v66` 胜，seed=`20260446`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_022119/20260305_022704_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260446_rounds-180.jsonl`
   - replay turning point：round `133`，`delta_territory_lead_p0=-2`，`delta_army_lead_p0=332`。
   - 附近动作抽样：`Round 131/133/134` 连续技能动作 `[4,...]`（双方换技能后 p0 侧建立兵力优势）。
2. 负例（`v66` 负，seed=`20260439`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_022119/20260305_022634_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260439_rounds-180.jsonl`
   - replay turning point：round `138`，`delta_army_lead_p0=-177`。
   - 附近动作抽样：`Round 138, Player 0, Action [4,25,2,7,10]` 后，`Round 139, Player 1, Action [7,5,11]`。

replay 结论：

1. 软化后 `v66` 仍保持低技能/低征召频次特征，并恢复关键对位胜率；
2. 波动仍高（`army_swing` 峰值 `619`、`terr_swing` 峰值 `106`），稳定性问题尚未根治。

### 96.5 借鉴点是否生效

1. Generals 借鉴点（连续风险而非硬开关）：
   - 证据：在不引入新离散分支的前提下，关键对位从 `46/100` 回升到 `59/100`。
   - 判定：`生效`（方向为正，但需 confirm）。
2. ANTWar 借鉴点（危险态保币但不过度）：
   - 证据：`v66` 的 `call_general/general_skill` 继续显著低于 `v64`（`170/310` vs `390/496`），且胜率已恢复。
   - 判定：`部分生效`（控险与胜率暂时兼顾）。

### 96.6 回到生产口径的结论

1. 生产 latest（`eval_20260305_021316`）本 tag champion 未切换，切换风险在本 tag 内为否。
2. 但本 tag 无 `v64-v66` 直接对局，不能用 production adaptive 排名替代 head-to-head 判优。
3. 本轮 iter `59/100` 为正向候选信号；当前结论维持 `neutral`（未达 `>=200` confirm，不宣称稳定优于）。

### 96.7 风险、下一步与回合末自检

风险：

1. 本轮仍仅 100 局，统计置信度不足；
2. replay 高波动局仍较多，终盘 swing 问题未解决。

下一步：

1. 继续同代码补做 `v66-v64` 额外 `>=100` 局，形成 `>=200` confirm 后再判优；
2. 若 confirm 仍摆动，优先继续减法：限制高 danger 态下 overlay 候选规模与 follow-up 深评估次数。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物未提供触发计数，无法直接统计。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 候选深评估链；
   - 已有 deadline 与 base 回退兜底。
3. 若有风险，下轮如何降复杂度或改进剪枝：
   - 继续压缩高 danger/source 条件下的候选池；
   - 对低收益候选更早终止 follow-up 评估。

### 97.1 固定目标与最新状态（continue）

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260305_022924`（`mode=adaptive`）。
2. `champion.old/new = cpp_v64_generals_rebuild -> cpp_v66_generals_weapon_econ`（`promoted=true`）。
3. `config.pairs` 共 `45` 组，其中直接 `v64-v66` 对局 `1` 组（old/new 同对）。
4. 必做判读（gauntlet 高优先级风险）：
   - 本 tag 发生 champion 切换，因此“本轮对手池是否受 champion 切换影响”= 是（高优先级风险）；
   - 生产 Elo 仍是唯一权威，但该 tag 的对手池/采样随 champion 变化，跨 tag Elo 绝对值不可直比。

iter 口径（仅候选筛选）：

1. 最新 iter：`eval_20260305_024959`。
2. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_024959_matches.jsonl`。
3. replay latest：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json` 与 `/www/docs/replay_analysis/iter_latest.md`（`rows=200`、`analyzed=200`、`missing=0`、`parse_errors=0`）。

### 97.2 算法级改动（新版本 v68，overlay 风险池平滑限幅）

新增版本目录与版本 ID（不改写旧快照）：

1. 源码：`/www/ai_cpp/v68/ai_v68.cpp`
2. 可执行：`/www/ai_cpp/v68/ai_v68`
3. 注册 ID：`cpp_v68_overlay_smoothcap`

注册信息（可复现）：

```bash
python3 /www/autolab_manage.py register-cpp \
  --version-id cpp_v68_overlay_smoothcap \
  --exe /www/ai_cpp/v68/ai_v68 \
  --src /www/ai_cpp/v68/ai_v68.cpp \
  --notes "smooth overlay pool cap + danger-weighted early-stop"
```

本轮唯一策略改动（相对 `v67`）：

1. `choose_overlay_tuning(...)` 去掉分段阈值池规模切换（`risk<0.70` / `risk>=0.95`），改为连续平滑上限：
   - `smooth_pool_cap = kOverlayStableMaxPool + round(risk_alpha*2)`，将 overlay 候选池收敛到 `[8,10]`。
2. 提前停止条件改为随风险连续调节：
   - `early_stop_gap = 18 + round(risk_alpha*6)`；
   - `early_stop_min_evals = 4 + round((1-risk_alpha)*2)`。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin / impact_value`（连续威胁来源，不用硬阈值切段）。
   - 本游戏映射：用 `main_threat_sources + main_danger` 连续化 overlay 搜索预算，而非分段切换池大小。
   - 代码落点：`choose_overlay_tuning(...)` 的 `risk_alpha/smooth_pool_cap`。
2. ANTWar 借鉴点：`global_state + danger + reserved/safe_coin`（危险态收敛开销）。
   - 本游戏映射：高风险时减少搜索扩张并更早停止，优先稳定主线动作。
   - 代码落点：`choose_overlay_tuning(...)` 的 `early_stop_gap/early_stop_min_evals` 连续调节。

### 97.3 可复现实验（规定脚本，iter 隔离）

命令（14 核，禁止写生产 champion）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v68_overlay_smoothcap,cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --challengers cpp_v68_overlay_smoothcap \
  --opponents cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild \
  --seed 20260405
```

结果：`eval_20260305_024959`

1. `v68 vs v66 = 50/100`（达到两 AI 比较门槛 `>=100`，但无优势）。
2. `v68 vs v64 = 50/100`（达到两 AI 比较门槛 `>=100`，但无优势）。
3. 结论等级：`gate` 已达样本门槛，但当前仅 `neutral` 候选信号。

### 97.4 Replay 分析与原始回放核对

replay 摘要（`iter_latest.md` / `latest.json`）：

1. `rows=200`，`analyzed=200`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：
   - `v68-v66`: `50-50`（100 局）
   - `v68-v64`: `50-50`（100 局）
3. 动作分布（聚合）：
   - `v68`: `general_skill=570`, `call_general=311`
   - `v66`: `general_skill=281`, `call_general=182`
   - `v64`: `general_skill=379`, `call_general=298`

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. `v68 vs v64` 胜例（seed=`20261414`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_024959/20260305_025154_p0-cpp_v68_overlay_smoothcap_p1-cpp_v64_generals_rebuild_seed-20261414_rounds-180.jsonl`
   - turning point：round `26`（`delta_territory_lead_p0=+3`, `delta_army_lead_p0=+22`）。
   - 附近动作：`Round 26, P0 Action [4,0,2,5,10]`，随后连续推进动作保持领先。
2. `v68 vs v64` 负例（seed=`20261415`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_024959/20260305_025200_p0-cpp_v68_overlay_smoothcap_p1-cpp_v64_generals_rebuild_seed-20261415_rounds-180.jsonl`
   - turning point：round `18`（`delta_territory_lead_p0=-2`, `delta_army_lead_p0=-4`）。
   - 附近动作：`Round 17, P1 Action [7,1,5]` 后，`P0` 连续小步推进未扭转局面。
3. `v68 vs v66` 胜例（seed=`20260405`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_024959/20260305_024959_p0-cpp_v68_overlay_smoothcap_p1-cpp_v66_generals_weapon_econ_seed-20260405_rounds-180.jsonl`
   - turning point：round `66`（`delta_territory_lead_p0=+2`, `delta_army_lead_p0=+8`）。
   - 附近动作：`Round 66, P0 Action [4,3,2,6,13]` 后转入收官。
4. `v68 vs v66` 负例（seed=`20261316`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_024959/20260305_024959_p0-cpp_v66_generals_weapon_econ_p1-cpp_v68_overlay_smoothcap_seed-20261316_rounds-180.jsonl`
   - turning point：round `122`（`delta_army_lead_p0=-227`，对 p1=`v68` 不利）。
   - 附近动作：`Round 122, P1 Action [4,17,2,4,6]` 后仍被对手反压。

replay 结论：

1. `v68` 的 overlay 平滑限幅没有形成净胜率提升，两个关键对手都打成 `50/100`；
2. 高波动仍存在（`largest_army_swing` 峰值 `1047`，`largest_territory_swing` 峰值 `116`），说明“更稳搜索预算”尚未转化为波动收敛。

### 97.5 借鉴点是否生效

1. Generals 借鉴点（threat-origin 连续化）：
   - 证据：`choose_overlay_tuning` 已从分段切换改为连续 `risk_alpha` 平滑池上限，结构更简；
   - 结果：关键对位均 `50/100`，未体现强度增益。
   - 判定：`部分生效（结构简化生效，强度未提升）`。
2. ANTWar 借鉴点（danger/reserved 的危险态收敛）：
   - 证据：高风险下 overlay 候选池上限收敛到 `[8,10]`，并提前停止；
   - 结果：仍出现高 swing 长局（如 `army_swing=1047`）。
   - 判定：`未充分生效`。

### 97.6 回到生产口径的结论

1. 生产 latest（`eval_20260305_022924`）发生 champion 切换（`v64 -> v66`），对手池受影响风险为高。
2. 该生产 tag 虽含 `1` 组 `v64-v66` 直接对局，但整体仍为 adaptive 抽样池，不能单轮替代固定 head-to-head 复验结论。
3. 本轮 iter 结果仅用于候选筛选：`v68` 结论标签为 `neutral`，不宣称优于 `v64` 或 `v66`。

### 97.7 风险、下一步与回合末自检

风险：

1. `v68` 对关键基线无净增益（双 `50/100`），说明当前改动主要是结构简化而非强度突破；
2. replay 高波动样本仍多，终盘摆动问题未解。

下一步：

1. 在 `v68` 上做“低收益候选跳过 my_follow”剪枝（继续减法，不加新状态机），优先压波动；
2. 对 `v68 vs v66` 与 `v68 vs v64` 分别补到 `>=200` 局 confirm，再决定是否保留该分支。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍使用 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物未记录触发计数，无法直接统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best + my_follow` 双评估链；
   - 本轮已通过池上限与提前停止降低风险，但未做计数可观测性。
3. 若有风险，下轮如何降复杂度或改进剪枝：
   - 增加 `hard_cutoff_hit` 计数日志并写入评测摘要；
   - 在高风险态优先跳过 `raw_drop` 偏大的候选 follow-up 评估。

### 98.1 固定目标与最新状态（continue）

已重新读取并严格遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. 当前 `latest.json`：`eval_20260305_025927`（`mode=adaptive`）。
2. `champion.old/new = cpp_v66_generals_weapon_econ -> cpp_v64_generals_rebuild`（`promoted=true`）。
3. `config.pairs` 共 `45` 组，本 tag 内 `old/new` 直接对局 `0` 组。
4. 必做判读（gauntlet 高优先级风险）：
   - 本 tag 发生 champion 切换，因此“本轮对手池是否受 champion 切换影响”= 是（高优先级风险）；
   - 且该 tag 无 old/new 直接对打，不能用单轮 production adaptive Elo 替代 head-to-head 复验。

iter 口径（仅候选筛选）：

1. 最新 iter：`eval_20260305_030348`。
2. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_030348_matches.jsonl`。
3. replay latest：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json` 与 `/www/docs/replay_analysis/iter_latest.md`（`rows=400`、`analyzed=400`、`missing=0`、`parse_errors=0`）。

### 98.2 算法级改动（新版本 v69，overlay follow-up 连续剪枝）

新增版本目录与版本 ID（旧快照不改写）：

1. 源码：`/www/ai_cpp/v69/ai_v69.cpp`
2. 可执行：`/www/ai_cpp/v69/ai_v69`
3. 注册 ID：`cpp_v69_overlay_followup_prune`

注册信息（可复现）：

```bash
python3 /www/autolab_manage.py register-cpp \
  --version-id cpp_v69_overlay_followup_prune \
  --exe /www/ai_cpp/v69/ai_v69 \
  --src /www/ai_cpp/v69/ai_v69.cpp \
  --notes "overlay follow-up pruning by raw-drop risk"
```

本轮策略改动（相对 `v68`，简化优先）：

1. `OverlayTuning` 新增两个连续参数：
   - `followup_raw_drop_cap`（决定是否评估 `my_follow`）
   - `followup_skip_penalty`（跳过 follow-up 的轻惩罚）
2. 在 `choose_overlay_tuning(...)` 中按 `risk_alpha` 连续设置：
   - `followup_raw_drop_cap = 16 - 8*risk_alpha`（`[8,16]`）
   - `followup_skip_penalty = 1.5 + 1.5*risk_alpha`
3. 在 `select_best_move_overlay(...)` 中：
   - 非 base 且 `raw_drop` 超过 cap 的候选，跳过 `my_follow` 深评估；
   - 仍保留 enemy reply veto 与 base 回退链，防止无兜底路径。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin` 连续威胁来源 -> 本游戏映射为“低优先级分支不做二次跟进评估”。
   - 代码落点：`select_best_move_overlay` 的 `should_eval_follow` 分支。
2. ANTWar 借鉴点：`danger/reserved` 危险态收敛预算 -> 本游戏映射为“风险越高，follow-up 预算越紧”。
   - 代码落点：`choose_overlay_tuning` 的 `followup_raw_drop_cap/followup_skip_penalty`。

### 98.3 可复现实验（规定脚本，iter gate）

命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v69_overlay_followup_prune,cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v69_overlay_followup_prune \
  --opponents cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260406
```

结果：`eval_20260305_030348`

1. `v69 vs v66 = 51/100`（`>=100`，轻微正向）。
2. `v69 vs v64 = 48/100`（`>=100`，对当前生产 champion 仍劣势）。
3. `v69 vs v1 = 84/100`（`>=100`，gate 正向）。
4. `v69 vs v2 = 76/100`（`>=100`，gate 正向）。

判读：本轮属于 gate 结果，尚无任一关键结论达到 `>=200` confirm；不能宣称“稳定优于多个老版本”。

### 98.4 Replay 分析与原始回放核对

replay 摘要（`iter_latest.md` / `latest.json`）：

1. `rows=400`，`analyzed=400`，`missing=0`，`parse_errors=0`。
2. `pair_stats`：
   - `v69-v66`: `51-49`
   - `v69-v64`: `48-52`
   - `v69-v1`: `84-16`
   - `v69-v2`: `76-24`
3. `v69` 聚合：`win_rate=0.647`，`no_effect_rate=0.0567`，`avg_rounds=132.03`。

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. `v69 vs v66` 胜例（seed=`20261317`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_030348/20260305_030348_p0-cpp_v66_generals_weapon_econ_p1-cpp_v69_overlay_followup_prune_seed-20261317_rounds-180.jsonl`
   - turning point：round `92`（`delta_army_lead_p0=+206`，对 p1=`v69` 有利）。
   - 附近动作：`Round 92, P1 Action [4,16,2,9,11]` 后转入优势交换。
2. `v69 vs v66` 负例（seed=`20260406`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_030348/20260305_030348_p0-cpp_v69_overlay_followup_prune_p1-cpp_v66_generals_weapon_econ_seed-20260406_rounds-180.jsonl`
   - turning point：round `90`（`delta_army_lead_p0=-39`）。
   - 附近动作：`Round 90, P0 Action [4,14,2,9,5]` 后未扭转下行。
3. `v69 vs v64` 胜例（seed=`20262326`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_030348/20260305_030558_p0-cpp_v64_generals_rebuild_p1-cpp_v69_overlay_followup_prune_seed-20262326_rounds-180.jsonl`
   - turning point：round `104`（`delta_army_lead_p0=-198`，对 p1=`v69` 有利）。
   - 附近动作：`Round 104, P1 Action [4,16,2,11,3]`。
4. `v69 vs v64` 负例（seed=`20261415`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_030348/20260305_030554_p0-cpp_v69_overlay_followup_prune_p1-cpp_v64_generals_rebuild_seed-20261415_rounds-180.jsonl`
   - turning point：round `18`（`delta_territory_lead_p0=-2`, `delta_army_lead_p0=-4`），早盘丢节奏。

replay 结论：

1. `v69` 在非 champion 对手池（`v1/v2`）上增益明显，但对当前 champion `v64` 仍未过 50%；
2. 高波动长局仍存在（`largest_army_swing` 峰值 `1232`，`largest_territory_swing` 峰值 `151`），说明剪枝降低了分支复杂度，但尚未显著收敛终盘 swing。

### 98.5 借鉴点是否生效

1. Generals 借鉴点（threat-origin 连续化）：
   - 证据：`my_follow` 评估已从“全候选”改为“连续 raw_drop 门控”，结构更简；
   - 结果：`v69-v66` 提升到 `51/100`，对 `v64` 仍 `48/100`。
   - 判定：`部分生效`。
2. ANTWar 借鉴点（danger/reserved 收敛预算）：
   - 证据：高风险时 follow-up cap 更紧，避免低价值候选深评估；
   - 结果：`v69` 的 `no_effect_rate=0.0567` 低于 `v64=0.0736`，但高波动仍在。
   - 判定：`部分生效`（复杂度下降，稳定性收益不足）。

### 98.6 回到生产口径的结论

1. 生产 latest（`eval_20260305_025927`）发生 `v66 -> v64` champion 切换，且本 tag 无 old/new 直接对局，gauntlet 口径风险高。
2. 本轮 iter 仅用于候选筛选：`v69` 对 `v1/v2` 强，但对当前 champion `v64` 仍不足；
3. 结论标签：`neutral`（不宣称优于当前 champion 或稳定优于多个老版本）。

### 98.7 风险、下一步与回合末自检

风险：

1. 对冠军关键对位 `v69-v64` 仍未达 50%+（`48/100`）；
2. replay 仍有极端 swing（`army_swing` 到 `1232`），稳定性短板未解。

下一步：

1. 在 `v69` 上继续减法：对 `enemy_reply` 高且 `raw_drop` 大的候选提前终止，不再进入 overlay 打分；
2. 先做 `v69 vs v64` 追加 `>=100` 局 confirm（形成 `>=200`），再做对 `v66` 的 confirm。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物未记录触发计数，无法直接统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best/my_follow` 评估链；
   - 本轮通过 `followup_raw_drop_cap` 降低该风险，但不是可观测闭环。
3. 若有风险，下轮如何降复杂度或改进剪枝：
   - 在评测摘要中增加 `hard_cutoff_hit` 计数导出；
   - 对高风险候选加更早的 veto，减少深评估调用次数。

### 99.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_032841`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`（`promoted=false`）。
3. `config.pairs` 共 `45` 对，其中包含 champion 的对局 `7` 对。
4. 必做判读（champion 切换影响）：本 tag **未发生** champion 切换，因此本轮对手池不受“切换事件”直接影响；但 adaptive/gauntlet 的对手组成仍与 champion 身份耦合，跨 tag Elo 绝对值不可比较。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_033232`，mode=`gauntlet`，`matches=500`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_033232_matches.jsonl`（已用于逐局索引）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 99.2 算法级改动落地（新版本 `v70`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v70/ai_v70.cpp`（未改写旧版本快照）。
2. 新版本 ID：`cpp_v70_overlay_opening_subpressure`。
3. 注册项：`/www/autolab/registry.json`（`exe=/www/ai_cpp/v70/ai_v70`，`src=/www/ai_cpp/v70/ai_v70.cpp`，`notes=opening sub-gap pressure in overlay tuning`）。

改动点（简化优先，未新增状态机）：

1. 在 `choose_overlay_tuning(...)` 增加开局子将压力连续信号：
   - `my_sub_count/enemy_sub_count -> sub_gap_signal`；
   - `opening_signal = clamp((60-round)/60)`；
   - `opening_sub_pressure = duel_close * opening_signal * sub_gap_signal`。
2. 用同一连续信号联动 overlay 预算：
   - `base_anchor_penalty`、`max_raw_drop`、`base_reply_veto_slack`；
   - `followup_raw_drop_cap`、`followup_skip_penalty`；
   - 并做 clamp，避免离散阈值补丁扩散。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin` 连续威胁来源。
   - 本游戏映射：开局且子将劣势时，提高对候选后续验证强度，而不是新增离散状态分支。
   - 代码落点：`choose_overlay_tuning(...)` 的 `opening_sub_pressure` 与后续连续调参。
2. ANTWar 借鉴点：`danger/reserved` 的预算收敛。
   - 本游戏映射：在危险态动态收紧/放宽 overlay 搜索预算（而非固定门槛）。
   - 代码落点：`max_raw_drop/base_reply_veto_slack/followup_*` 的统一预算联动。

### 99.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope，禁止生产晋升）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v70_overlay_opening_subpressure,cpp_v69_overlay_followup_prune,cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v70_overlay_opening_subpressure \
  --opponents cpp_v69_overlay_followup_prune,cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260407
```

结果（tag=`eval_20260305_033232`，每对手 `100` 局，满足两 AI 比较 `>=100` 门槛）：

1. `v70 vs v69 = 52/100`
2. `v70 vs v66 = 46/100`
3. `v70 vs v64(champion) = 51/100`
4. `v70 vs v1 = 74/100`
5. `v70 vs v2 = 70/100`

口径判读：

1. 这是 gate 结果，不是 confirm；当前关键对位均未达到 `>=200`。
2. 不能宣称“新版本优于多个老版本”：`v70` 对 `v66` 仍为负。
3. 与上一轮 `v69` 的同量级 gate 对比（仅作方向信号，不作跨实验严格判优）：`vs v64` 从 `48/100` 升到 `51/100`，但 `vs v66` 从 `51/100` 降到 `46/100`。

### 99.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=500`，`analyzed=500`，`missing=0`，`parse_errors=0`。
2. pair 统计：
   - `v70-v69: 52-48`
   - `v70-v66: 46-54`
   - `v70-v64: 51-49`
   - `v70-v1: 74-26`
   - `v70-v2: 70-30`
3. 波动仍高：`largest_army_swing=1047`，`largest_territory_swing=152`。

原始回放逐帧核对（均来自 `paths.matches` 的 `replay_file`）：

1. `v70 vs v66` 胜例（seed=`20262369`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_033232/20260305_033624_p0-cpp_v66_generals_weapon_econ_p1-cpp_v70_overlay_opening_subpressure_seed-20262369_rounds-180.jsonl`
   - turning point：round `149`（`delta_army_lead_p0=-211`，p1=`v70` 受益）。
   - 附近动作：`R149 P1 Action [1,11,1,3,1]`、`[1,11,1,4,1]`；对应回合 p0 兵力领先回撤。
2. `v70 vs v66` 负例（seed=`20261426`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_033232/20260305_033527_p0-cpp_v70_overlay_opening_subpressure_p1-cpp_v66_generals_weapon_econ_seed-20261426_rounds-180.jsonl`
   - turning point：round `130`（`delta_army_lead_p0=-290`，p0=`v70` 失衡）。
   - 附近动作：`R130 P0 Action [4,17,2,7,5]` 后未能扭转下行。
3. `v70 vs v64` 胜例（seed=`20262473`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_033232/20260305_033826_p0-cpp_v70_overlay_opening_subpressure_p1-cpp_v64_generals_rebuild_seed-20262473_rounds-180.jsonl`
   - turning point：round `145`（`delta_army_lead_p0=+327`，p0=`v70` 放大优势）。
   - 附近动作：`R145 P0 Action [1,9,13,2,1]` 后，p0 维持扩张节奏。
4. `v70 vs v64` 负例（seed=`20262458`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_033232/20260305_033754_p0-cpp_v70_overlay_opening_subpressure_p1-cpp_v64_generals_rebuild_seed-20262458_rounds-180.jsonl`
   - turning point：round `176`（`delta_army_lead_p0=-402`，p0=`v70` 终盘被反打）。
   - 附近动作：`R176 P0 Action [4,23,2,4,8]` 与 `R176 P1 Action [4,5,2,7,2]` 同窗出现，随后兵力差急剧逆转。

replay 结论：

1. `v70` 对当前 champion `v64` 略有改善（`51/100`），但仍接近五五开；
2. 对 `v66` 出现回退（`46/100`），且终盘高 swing 仍常见，稳定性问题未解。

### 99.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（threat-origin 连续化）：
   - 证据：开局子将压力被压缩为单一连续信号并直连 overlay 调参；
   - 结果：对 champion 对位从上一轮 `48/100` 到本轮 `51/100`（仅 gate 信号）。
   - 判定：`部分生效`。
2. ANTWar 借鉴点（danger/reserved 预算收敛）：
   - 证据：危险态预算联动（`max_raw_drop/base_reply_veto_slack/followup_*`）已落地；
   - 结果：`v70` 仍在 `v66` 对位回退到 `46/100`，且大 swing 未收敛。
   - 判定：`部分生效但收益不稳定`。

### 99.6 回到生产口径的结论

1. 生产权威 tag=`eval_20260305_032841`，`champion` 仍为 `cpp_v64_generals_rebuild`（本 tag 无切换）。
2. 本轮结论仅可用作 iter 候选筛选；生产 Elo/晋升结论不应由本轮 iter Elo 直接推出。
3. 当前标签：`neutral`（非晋升结论）。
   - 原因：`v70` 对 champion 仅 `51/100`，对 `v66` 为 `46/100`，尚不满足 confirm 或“优于多个老版本”的判优门槛。

### 99.7 风险、下一步与回合末自检

风险：

1. 关键对位未形成稳定优势：`v70-v64=51/100`、`v70-v66=46/100`；
2. replay 波动上限仍高（`army_swing=1047`，`territory_swing=152`）。

下一步：

1. 做 `v70 vs v64` 与 `v70 vs v66` 的 confirm 复验（各再补 `>=100`，形成 `>=200`）；
2. 若 `v66` 仍劣势，下轮优先减法：对“高 `enemy_reply` 且高 `raw_drop`”候选提前 veto，避免进入 follow-up；
3. 评测产物增加 `hard_cutoff_hit` 计数导出，建立复杂度风险可观测闭环。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍使用 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 现有评测产物未导出触发计数，无法在结果文件中直接确认触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best + my_follow` 评估链。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 增加更早 veto（先验拦截高风险低收益候选）；
   - 将 `hard_cutoff_hit` 暴露到评测摘要，按对手对位定位超时热点。

### 100.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_035840`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v68_overlay_smoothcap -> cpp_v68_overlay_smoothcap`（`promoted=false`）。
3. `config.pairs` 共 `45` 对，其中包含 champion 的对局 `8` 对。
4. 必做判读（champion 切换影响）：
   - 本 tag 内 **无** champion 切换（`old==new`），因此本轮对手池不受“本次切换事件”直接影响；
   - 但生产在上一 tag（`eval_20260305_035138`）发生过 `v64 -> v68` 切换，gauntlet 对手池口径已变化，跨 tag Elo 绝对值比较属于高风险。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_040307`，mode=`gauntlet`，`matches=600`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_040307_matches.jsonl`（已用于索引原始回放）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 100.2 算法级改动落地（新版本 `v71`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v71/ai_v71.cpp`（旧版本源码未改写）。
2. 新版本 ID：`cpp_v71_overlay_replyrisk_gate`。
3. 注册项：`/www/autolab/registry.json`（`exe=/www/ai_cpp/v71/ai_v71`，`src=/www/ai_cpp/v71/ai_v71.cpp`，`notes=unified reply-risk gate + ahead-state budget tightening`）。

本轮改动（简化优先）：

1. 在 `choose_overlay_tuning(...)` 增加领先态连续信号：
   - `territory_lead/army_lead -> lead_signal -> ahead_signal`；
   - `ahead_signal` 连续作用于 `base_anchor_penalty/max_raw_drop/base_reply_veto_slack/base_reply_drop_scale`。
2. 在 `select_best_move_overlay(...)` 合并两条离散 veto：
   - 原先 `dominated veto + base_reply veto` 两个硬分支；
   - 改为单一连续 `reply_risk` 闸门（`reply_surplus + 0.45*dominance_surplus - 1.25*threat_credit`），仅保留一条 veto 判定。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin/impact_value` 连续威胁来源。
   - 本游戏映射：把 reply 风险从双阈值离散分支压成一个连续风险量 `reply_risk`。
   - 代码落点：`/www/ai_cpp/v71/ai_v71.cpp` 中 `reply_risk` 计算与单闸门判定。
2. ANTWar 借鉴点：`global_state + reserved`（领先态保守预算）。
   - 本游戏映射：领先时自动收紧切换预算，减少高波动非必要切换。
   - 代码落点：`ahead_signal` 对 `max_raw_drop/base_reply_*` 的连续收紧。

### 100.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v71_overlay_replyrisk_gate,cpp_v70_overlay_opening_subpressure,cpp_v68_overlay_smoothcap,cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v71_overlay_replyrisk_gate \
  --opponents cpp_v70_overlay_opening_subpressure,cpp_v68_overlay_smoothcap,cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260408
```

结果：`eval_20260305_040307`（每对手 `100` 局，达到两 AI 比较门槛 `>=100`）：

1. `v71 vs v70 = 52/100`
2. `v71 vs v68(champion) = 48/100`
3. `v71 vs v66 = 54/100`
4. `v71 vs v64 = 51/100`
5. `v71 vs v1 = 79/100`
6. `v71 vs v2 = 83/100`

口径判读：

1. 当前是 gate，不是 confirm（关键对位尚未达到 `>=200`）；
2. 不满足“新版本优于多个老版本”的宣称条件；
3. 仅可作为候选方向信号：`v71` 修复了 `v70-v66` 的劣势（`46/100 -> 54/100`），但对当前生产 champion `v68` 仍 `48/100`。

### 100.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=600`，`analyzed=600`，`missing=0`，`parse_errors=0`。
2. 关键 pair：
   - `v71-v70: 52-48`
   - `v71-v68: 48-52`
   - `v71-v66: 54-46`
3. `v71` 聚合：`win_rate=0.6117`，`avg_rounds=125.88`，`no_effect_rate=0.0591`。
4. 波动上限仍高：`largest_army_swing=1047`（未见明显收敛）。

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. `v71 vs v68` 胜例（seed=`20262340`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_040307/20260305_040523_p0-cpp_v68_overlay_smoothcap_p1-cpp_v71_overlay_replyrisk_gate_seed-20262340_rounds-180.jsonl`
   - turning point：round `139`（`delta_army_lead_p0=379`，`impact_score=383`）。
   - 附近动作：`R139 P1 Action [1,7,6,2,1]`、`[1,8,5,2,1]`、`[1,9,8,4,1]`。
2. `v71 vs v68` 负例（seed=`20261450`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_040307/20260305_040604_p0-cpp_v71_overlay_replyrisk_gate_p1-cpp_v68_overlay_smoothcap_seed-20261450_rounds-180.jsonl`
   - turning point：round `179`（`delta_army_lead_p0=340`，`impact_score=344`）。
   - 附近动作：`R179 P0 Action [1,8,14,3,1]`、`R179 P1 Action [1,2,5,3,1]`。
3. `v71 vs v66` 胜例（seed=`20262442`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_040307/20260305_040701_p0-cpp_v71_overlay_replyrisk_gate_p1-cpp_v66_generals_weapon_econ_seed-20262442_rounds-180.jsonl`
   - turning point：round `179`（`delta_army_lead_p0=541`，`impact_score=541`）。
   - 附近动作：`R179 P0 Action [1,2,2,1,1]`、`[1,4,5,2,1]`、`[1,5,6,4,1]`。
4. `v71 vs v66` 负例（seed=`20262467`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_040307/20260305_040801_p0-cpp_v71_overlay_replyrisk_gate_p1-cpp_v66_generals_weapon_econ_seed-20262467_rounds-180.jsonl`
   - turning point：round `127`（`delta_army_lead_p0=442`，`impact_score=446`）。
   - 附近动作：`R127 P0 Action [1,10,1,2,1]`、`[1,11,2,4,1]`，对应 `R127 P1 Action [1,11,7,3,2]`。

replay 结论：

1. 单闸门风险过滤对 `v66` 对位有正向修复（`54/100`）；
2. 但在当前 champion `v68` 对位仍偏弱（`48/100`），且极端 swing 未收敛，稳定性问题仍在。

### 100.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat-origin）：
   - 证据：v71 将双阈值 veto 合并为连续 `reply_risk` 单闸门；
   - 结果：对 `v70`、`v66` 均出现正向（`52/100`、`54/100`）。
   - 判定：`部分生效`。
2. ANTWar 借鉴点（领先态 reserved）：
   - 证据：`ahead_signal` 驱动预算收紧已落地；
   - 结果：对 `v66` 修复，但对 champion `v68` 仍 `48/100`。
   - 判定：`部分生效但未达晋级要求`。

### 100.6 回到生产口径的结论

1. 生产权威当前为 `eval_20260305_035840`，champion 为 `cpp_v68_overlay_smoothcap`；
2. 本轮 iter Elo 仅做筛选，不参与生产绝对结论；
3. 本轮结论标签：`neutral`。
   - 原因：虽修复 `v66` 对位，但对当前生产 champion `v68` 仍 `48/100`，且关键对位仍未进入 confirm 样本。

### 100.7 风险、下一步与回合末自检

风险：

1. 当前 champion 对位仍劣：`v71-v68 = 48/100`；
2. replay 极端波动仍高（`army_swing=1047`）。

下一步：

1. 先做 confirm 复验：`v71 vs v68` 追加 `>=100`（形成 `>=200`）；
2. 并行补 `v71 vs v66` 追加 `>=100`（确认修复是否稳定）；
3. 若 `v68` 仍劣，下轮优先继续减法：在 `reply_risk` 前增加更早的低价值候选预筛，减少终盘高 swing 切换。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物未导出 `hard_cutoff_hit` 计数，无法直接统计触发次数。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 中 `enemy_best/my_follow` 的多次 base 评估链。
3. 若有风险，下轮如何降复杂度或改进剪枝：
   - 增加 `reply_risk` 前置轻筛（先剔除明显低价值候选）；
   - 补充评测导出 `hard_cutoff_hit`，形成 CPU 风险可观测闭环。

### 101.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_042619`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v69_overlay_followup_prune -> cpp_v69_overlay_followup_prune`（`promoted=false`）。
3. `config.pairs` 共 `45` 对。
4. 必做判读（champion 切换影响）：
   - 本 tag 内 `old==new`，本轮对手池不受“本次切换事件”直接影响；
   - 但生产在近邻 tag（`eval_20260305_041953`）发生过 `v68 -> v69` 切换，gauntlet 对手池口径已变化，属于高优先级风险，不能跨 tag 直接比较 Elo 绝对值。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_043217`，mode=`gauntlet`，`matches=700`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_043217_matches.jsonl`（已用于原始回放索引）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 101.2 算法级改动落地（新版本 `v72`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v72/ai_v72.cpp`（未改写旧版本源码）。
2. 新版本 ID：`cpp_v72_overlay_endgame_lock`。
3. 注册项：`/www/autolab/registry.json`（`exe=/www/ai_cpp/v72/ai_v72`，`src=/www/ai_cpp/v72/ai_v72.cpp`，`notes=endgame ahead-lock signal + reply-risk lock penalty`）。

改动内容（简化优先）：

1. 在 `choose_overlay_tuning(...)` 新增单一连续信号：
   - `endgame_lock = ahead_signal * clamp((round-120)/60)`；
   - 领先且终盘时，统一收紧 `switch_margin/base_anchor_penalty/followup_raw_drop_cap/base_reply_*`。
2. 在 `select_best_move_overlay(...)` 的单闸门 `reply_risk` 上追加：
   - `+ 0.60 * lock_penalty`（`lock_penalty=endgame_lock_signal*max(0,raw_drop-2)`）；
   - 不新增分支状态，只在原连续风险量上叠加终盘领先惩罚。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin/impact_value` 连续威胁建模。
   - 映射：继续沿用单一连续 `reply_risk` 作为唯一高风险切换闸门。
   - 代码落点：`select_best_move_overlay(...)` 的 `reply_risk` 公式。
2. ANTWar 借鉴点：`global_state + reserved` 的领先保守预算。
   - 映射：领先终盘时自动“锁仓”，降低高波动切换概率。
   - 代码落点：`choose_overlay_tuning(...)` 的 `endgame_lock_signal` 与预算联动。

### 101.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v72_overlay_endgame_lock,cpp_v71_overlay_replyrisk_gate,cpp_v69_overlay_followup_prune,cpp_v68_overlay_smoothcap,cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v72_overlay_endgame_lock \
  --opponents cpp_v71_overlay_replyrisk_gate,cpp_v69_overlay_followup_prune,cpp_v68_overlay_smoothcap,cpp_v66_generals_weapon_econ,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260409
```

结果：`eval_20260305_043217`（每对手 `100` 局，满足两 AI 比较门槛 `>=100`）：

1. `v72 vs v71 = 53/100`
2. `v72 vs v69(champion) = 49/100`
3. `v72 vs v68 = 53/100`
4. `v72 vs v66 = 53/100`
5. `v72 vs v64 = 45/100`
6. `v72 vs v1 = 80/100`
7. `v72 vs v2 = 82/100`

口径判读：

1. 当前是 gate，不是 confirm（关键对位仍未达 `>=200`）。
2. 对当前生产 champion `v69` 未过线（`49/100`），不能给出晋升结论。
3. 结构改动对 `v71/v68/v66` 为正向，但对 `v64` 出现明显退化。

### 101.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=700`，`analyzed=700`，`missing=0`，`parse_errors=0`。
2. `v72` 聚合：`win_rate=0.5929`，`avg_rounds=122.79`，`no_effect_rate=0.0589`。
3. pair 摘要：
   - `v72-v71: 53-47`
   - `v72-v69: 49-51`
   - `v72-v64: 45-55`
4. 极端波动仍高：`largest_army_swing=1047`（未见显著收敛）。

原始回放逐帧核对（均来自 `paths.matches` 的 `replay_file`）：

1. `v72 vs v69` 胜例（seed=`20262339`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_043217/20260305_043404_p0-cpp_v69_overlay_followup_prune_p1-cpp_v72_overlay_endgame_lock_seed-20262339_rounds-180.jsonl`
   - turning point：round `137`（`delta_army_lead_p0=383`，`impact_score=383`）。
   - 附近动作：`R137 P1 Action [1,11,9,1,1]`、`[1,12,8,3,1]`、`[1,12,11,1,1]`。
2. `v72 vs v69` 负例（seed=`20261426`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_043217/20260305_043400_p0-cpp_v72_overlay_endgame_lock_p1-cpp_v69_overlay_followup_prune_seed-20261426_rounds-180.jsonl`
   - turning point：round `130`（`delta_army_lead_p0=-290`，`impact_score=290`）。
   - 附近动作：`R130 P0 Action [4,17,2,7,5]` 后未止损。
3. `v72 vs v71` 胜例（seed=`20261343`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_043217/20260305_043248_p0-cpp_v71_overlay_replyrisk_gate_p1-cpp_v72_overlay_endgame_lock_seed-20261343_rounds-180.jsonl`
   - turning point：round `148`（`delta_army_lead_p0=421`，`impact_score=421`）。
   - 附近动作：`R148 P1 Action [4,18,2,8,2]` 与连续推进动作同窗出现。
4. `v72 vs v64` 负例（seed=`20264483`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_043217/20260305_043959_p0-cpp_v72_overlay_endgame_lock_p1-cpp_v64_generals_rebuild_seed-20264483_rounds-180.jsonl`
   - turning point：round `161`（`delta_army_lead_p0=184`，`impact_score=192`）。
   - 附近动作：`R161 P0 Action [1,6,12,4,1]`、`[1,8,10,2,1]` 后仍被反压。

replay 结论：

1. 终盘锁定信号在 `v71` 对位上有小幅收益（`53/100`）；
2. 但对当前 champion `v69` 未形成优势（`49/100`），且对 `v64` 出现回退，说明“锁定强度”可能过度抑制中后盘反击窗口。

### 101.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat-origin）：
   - 证据：`reply_risk` 单闸门保持，且仅叠加连续 `lock_penalty`；
   - 结果：`v72-v71=53/100`，正向但幅度有限。
   - 判定：`部分生效`。
2. ANTWar 借鉴点（领先态 reserved）：
   - 证据：`endgame_lock_signal` 已统一作用于多项预算；
   - 结果：对 `v69` 未过线（`49/100`），并诱发 `v64` 对位退化（`45/100`）。
   - 判定：`部分生效但存在副作用`。

### 101.6 回到生产口径的结论

1. 生产权威当前是 `eval_20260305_042619`，champion 为 `cpp_v69_overlay_followup_prune`；
2. iter Elo 仅用于候选筛选，不能直接作为生产结论；
3. 本轮结论标签：`neutral`。
   - 原因：对当前 champion `v69` 仅 `49/100`，未达晋升标准，且关键对位未完成 confirm。

### 101.7 风险、下一步与回合末自检

风险：

1. `v72-v69` 未达 50%（`49/100`），当前冠军对位仍不足；
2. `v72-v64=45/100` 出现明显回退；
3. replay 极端波动仍高（`largest_army_swing=1047`）。

下一步：

1. 按 confirm 路线补做 `v72 vs v69` 追加 `>=100`（形成 `>=200`）；
2. 并行做 `v72 vs v64` 追加 `>=100`，确认退化是否稳定；
3. 若退化确认，下轮减法回调：下调 `endgame_lock_signal` 对 `followup_raw_drop_cap/base_reply_drop_scale` 的抑制斜率。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物仍未导出 `hard_cutoff_hit` 计数，无法直接统计触发频次。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best/my_follow` 多次 base 评估链。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 增加 `reply_risk` 前置轻筛，减少进入深评估的候选；
   - 在评测摘要中导出 `hard_cutoff_hit`，建立 CPU 风险观测闭环。

### 102.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_045540`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v64_generals_rebuild -> cpp_v64_generals_rebuild`（`promoted=false`）。
3. `config.pairs` 共 `45` 对，当前 champion 在其中出现 `4` 对。
4. 必做判读（champion 切换影响）：
   - 本 tag 内 `old==new`，本轮对手池不受“本次 champion 切换事件”直接影响；
   - 但生产排名仍以该 tag 的对阵池为准，iter 与生产 Elo 不可跨 scope 比较绝对值。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_050157`，mode=`gauntlet`，`matches=600`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_050157_matches.jsonl`（逐行含 `replay_file`）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 102.2 算法级改动落地（新版本 `v73`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v73/ai_v73.cpp`（未改写旧版本源码快照）。
2. 新版本 ID：`cpp_v73_overlay_calm_endgame_lock`。
3. 注册项：`/www/autolab/registry.json`（`exe=/www/ai_cpp/v73/ai_v73`，`src=/www/ai_cpp/v73/ai_v73.cpp`）。

改动内容（简化优先）：

1. 将 `v72` 的终盘锁定信号改为更窄的稳定信号：`endgame_stable_signal = ahead_signal * endgame_signal * calm_signal`，其中 `calm_signal=clamp((0.92-risk_score)/0.50)`；
2. 仅保留较轻联动：`switch_margin += 0.30*endgame_stable_signal` 与 `base_anchor_penalty += 0.05*endgame_stable_signal`；
3. `reply_risk` 的终盘附加惩罚降斜率：
   - `lock_penalty=endgame_stable_signal*max(0,raw_drop-4.0)`；
   - `reply_risk += 0.35*lock_penalty`（由 `v72` 的 `0.60` 下调）。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin/impact_value` 的连续威胁表达。
   - 映射：继续使用单一连续 `reply_risk` 闸门，不恢复多分支 veto。
   - 代码落点：`select_best_move_overlay(...)` 的 `reply_risk` 公式与 `lock_penalty` 融合。
2. ANTWar 借鉴点：`global_state + reserved` 的危险态保守预算。
   - 映射：仅在“领先 + 终盘 + 低危险”时触发稳定化预算。
   - 代码落点：`choose_overlay_tuning(...)` 的 `calm_signal/endgame_stable_signal` 与预算联动。

### 102.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v73_overlay_calm_endgame_lock,cpp_v72_overlay_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v71_overlay_replyrisk_gate,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v73_overlay_calm_endgame_lock \
  --opponents cpp_v72_overlay_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v71_overlay_replyrisk_gate,cpp_v1_current,cpp_v2_beam \
  --seed 20260410
```

结果：`eval_20260305_050157`（每对手 `100` 局，达到两 AI 比较门槛 `>=100`）：

1. `v73 vs v72 = 48/100`
2. `v73 vs v69 = 48/100`
3. `v73 vs v64(champion) = 51/100`
4. `v73 vs v71 = 53/100`
5. `v73 vs v1 = 78/100`
6. `v73 vs v2 = 82/100`

口径判读：

1. 该轮是 gate，不是 confirm（关键对位仍未达 `>=200`）；
2. 无任一关键老版本达到“`>=200` 且 `>55%`”宣称门槛，不能给出“明确优于 k 个老版本”结论；
3. 相比上一轮 `v72-v64=45/100`，`v73-v64=51/100` 出现回修信号，但对 `v72/v69` 均 `48/100`。

### 102.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=600`，`analyzed=600`，`missing=0`，`parse_errors=0`；
2. `v73` 聚合：`win_rate=0.6000`，`avg_rounds=124.80`，`no_effect_rate=0.0584`；
3. pair 摘要（关键对位）：
   - `v73-v64: 51-49`
   - `v73-v72: 48-52`
   - `v73-v69: 48-52`
4. 极端波动仍高：`largest_army_swing=1047`（未见收敛）。

原始回放逐帧核对（均来自 `paths.matches` 的 `replay_file`）：

1. `v73 vs v64` 胜例（seed=`20263386`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_050157/20260305_050639_p0-cpp_v64_generals_rebuild_p1-cpp_v73_overlay_calm_endgame_lock_seed-20263386_rounds-180.jsonl`
   - turning point：round `175`（`delta_army_lead_p0=472`，`impact_score=480`）。
   - 附近动作：`R175 P1 Action [1,4,6,2,2]`、`[1,7,9,3,1]`、`[1,7,11,3,1]`。
2. `v73 vs v64` 负例（seed=`20262467`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_050157/20260305_050614_p0-cpp_v73_overlay_calm_endgame_lock_p1-cpp_v64_generals_rebuild_seed-20262467_rounds-180.jsonl`
   - turning point：round `149`（`delta_army_lead_p0=425`，`impact_score=425`）。
   - 附近动作：`R149 P1 Action [4,24,2,10,1]`、`[1,13,7,3,2]`。
3. `v73 vs v72` 负例（seed=`20261329`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_050157/20260305_050159_p0-cpp_v72_overlay_endgame_lock_p1-cpp_v73_overlay_calm_endgame_lock_seed-20261329_rounds-180.jsonl`
   - turning point：round `158`（`delta_army_lead_p0=-662`，`impact_score=662`）。
   - 附近动作：`R158 P1 Action [1,10,2,3,122]`、`[1,10,2,3,61]`。
4. `v73 vs v71` 胜例（seed=`20264362`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_050157/20260305_050723_p0-cpp_v71_overlay_replyrisk_gate_p1-cpp_v73_overlay_calm_endgame_lock_seed-20264362_rounds-180.jsonl`
   - turning point：round `168`（`delta_army_lead_p0=366`，`impact_score=370`）。
   - 附近动作：`R168 P1 Action [4,21,2,6,6]`、`[1,11,6,2,1]`、`[1,2,1,3,1]`。

replay 结论：

1. `calm_signal` 软化后，对 `v64` 对位从 `45/100` 修复到 `51/100`（方向正确但幅度有限）；
2. 对 `v72/v69` 仍 `48/100`，说明终盘稳定化仍存在副作用；
3. 高波动指标未收敛（`largest_army_swing=1047`），结构仍需继续减法。

### 102.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat-origin）：
   - 证据：维持单一连续 `reply_risk` 闸门，仅调整连续惩罚斜率；
   - 结果：`v73-v71=53/100`，但 `v73-v72=48/100`、`v73-v69=48/100`。
   - 判定：`部分生效`（简化保持但强度未稳）。
2. ANTWar 借鉴点（领先态 reserved）：
   - 证据：`endgame_stable_signal` 仅在低危险领先终盘触发；
   - 结果：`v73-v64` 从上一轮 `45/100` 修复到 `51/100`；
   - 判定：`部分生效但仍有副作用`（关键对位未全面转正）。

### 102.6 回到生产口径的结论

1. 生产权威当前是 `eval_20260305_045540`，champion 为 `cpp_v64_generals_rebuild`；
2. 本 tag `champion.old==new`，且 mode=`adaptive`，对手池不受“本 tag champion 切换”直接影响；
3. iter Elo 仅用于候选筛选，不能直接用于生产强度结论；
4. 本轮结论标签：`neutral`。
   - 原因：对当前生产 champion `v64` 仅 `51/100`，同时对 `v72/v69` 为 `48/100`，未达判优门槛。

### 102.7 风险、下一步与回合末自检

风险：

1. `v73-v72=48/100`、`v73-v69=48/100`，对近邻强基线仍偏弱；
2. replay 极端波动仍高（`largest_army_swing=1047`）；
3. 关键对位仍只有 gate 样本（`100` 局），没有 confirm 稳定性。

下一步：

1. 补 confirm：`v73 vs v64/v69/v72` 各追加 `>=100`（形成每对手 `>=200`）；
2. 若 `v69/v72` 继续低于 `50%`，继续减法：优先去掉 `reply_risk` 中 `lock_penalty` 项，仅保留 `switch_margin/base_anchor_penalty` 的轻量稳定化；
3. 补充评测导出 `hard_cutoff_hit` 计数，闭环 CPU 风险观测。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 保底回退；
   - 当前评测产物未导出 `hard_cutoff_hit` 计数，无法直接统计触发频次。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 中 `enemy_best/my_follow` 的多次 base 评估链。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 减少进入 `my_follow` 深评估的候选规模；
   - 继续简化终盘稳定化项，避免在 `reply_risk` 叠加过多惩罚分量。

### 103.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_052402`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v70_overlay_opening_subpressure -> cpp_v72_overlay_endgame_lock`（`promoted=true`）。
3. `config.pairs` 共 `45` 对，当前 champion 在其中出现 `5` 对。
4. 必做判读（champion 切换影响）：
   - 本轮生产 tag 发生了 champion 切换（`v70 -> v72`），对手池构成受影响，属于高优先级风险；
   - 因此不同 tag 的 Elo 绝对值不可直比，结论必须依赖同池 head-to-head 样本。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_053212`，mode=`gauntlet`，`matches=700`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_053212_matches.jsonl`（逐行含 `replay_file`）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 103.2 算法级改动落地（新版本 `v74`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v74/ai_v74.cpp`（未改写旧版本源码快照）。
2. 新版本 ID：`cpp_v74_overlay_calm_margin_only`。
3. 注册项：`/www/autolab/registry.json`（`exe=/www/ai_cpp/v74/ai_v74`，`src=/www/ai_cpp/v74/ai_v74.cpp`）。

改动内容（简化优先）：

1. 直接删除 `reply_risk` 中的 `lock_penalty` 分量，保留单一连续风险门：
   - `reply_risk = reply_surplus + 0.45*dominance_surplus - 1.25*threat_credit`；
2. 保留 `endgame_stable_signal` 对 `switch_margin/base_anchor_penalty` 的轻量联动，不再在风险闸门重复叠加终盘惩罚；
3. 未引入新状态机与新搜索层，属于“减法”结构收敛。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin/impact_value` 连续威胁评分。
   - 映射：维持单一连续 `reply_risk` 门控，去掉额外终盘惩罚分支。
   - 代码落点：`select_best_move_overlay(...)` 风险闸门公式。
2. ANTWar 借鉴点：`global_state + reserved` 危险态资源收敛。
   - 映射：保留“领先+终盘+低风险”的预算收紧，但不再在闸门二次加罚。
   - 代码落点：`choose_overlay_tuning(...)` 的 `endgame_stable_signal` 预算联动。

### 103.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v72_overlay_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v71_overlay_replyrisk_gate,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v74_overlay_calm_margin_only \
  --opponents cpp_v73_overlay_calm_endgame_lock,cpp_v72_overlay_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v71_overlay_replyrisk_gate,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260411
```

结果：`eval_20260305_053212`（每对手 `100` 局，达到两 AI 比较门槛 `>=100`）：

1. `v74 vs v73 = 50/100`
2. `v74 vs v72(champion) = 49/100`
3. `v74 vs v69 = 49/100`
4. `v74 vs v71 = 51/100`
5. `v74 vs v64 = 44/100`
6. `v74 vs v1 = 79/100`
7. `v74 vs v2 = 82/100`

口径判读：

1. 本轮是 gate，不是 confirm（关键对位未达 `>=200`）；
2. 对当前生产 champion `v72` 仍未过线（`49/100`）；
3. 相比 `v73`，`v74` 未提升关键对位，且 `v64` 回退到 `44/100`。

### 103.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=700`，`analyzed=700`，`missing=0`，`parse_errors=0`；
2. `v74` 聚合：`win_rate=0.5771`，`avg_rounds=120.72`，`no_effect_rate=0.0595`；
3. pair 摘要（关键对位）：
   - `v74-v72: 49-51`
   - `v74-v69: 49-51`
   - `v74-v64: 44-56`
4. 极端波动仍高：`largest_army_swing=1047`（未见收敛）。

原始回放逐帧核对（均来自 `paths.matches` 的 `replay_file`）：

1. `v74 vs v72` 胜例（seed=`20262340`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_053212/20260305_053357_p0-cpp_v72_overlay_endgame_lock_p1-cpp_v74_overlay_calm_margin_only_seed-20262340_rounds-180.jsonl`
   - turning point：round `139`（`delta_army_lead_p0=379`，`impact_score=383`）。
   - 附近动作：`R139 P1 Action [1,7,6,2,1]`、`[1,8,5,2,1]`、`[1,9,8,4,1]`。
2. `v74 vs v72` 负例（seed=`20261426`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_053212/20260305_053353_p0-cpp_v74_overlay_calm_margin_only_p1-cpp_v72_overlay_endgame_lock_seed-20261426_rounds-180.jsonl`
   - turning point：round `130`（`delta_army_lead_p0=-290`，`impact_score=290`）。
   - 附近动作：`R130 P0 Action [4,17,2,7,5]` 后仍被反制。
3. `v74 vs v64` 负例（seed=`20264483`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_053212/20260305_053939_p0-cpp_v74_overlay_calm_margin_only_p1-cpp_v64_generals_rebuild_seed-20264483_rounds-180.jsonl`
   - turning point：round `161`（`delta_army_lead_p0=184`，`impact_score=192`）。
   - 附近动作：`R161 P0 Action [1,8,10,2,1]`、`[1,6,12,4,1]` 后被 `P1` 反压。
4. `v74 vs v71` 胜例（seed=`20264362`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_053212/20260305_053718_p0-cpp_v71_overlay_replyrisk_gate_p1-cpp_v74_overlay_calm_margin_only_seed-20264362_rounds-180.jsonl`
   - turning point：round `168`（`delta_army_lead_p0=366`，`impact_score=370`）。
   - 附近动作：`R168 P1 Action [4,21,2,6,6]`、`[1,11,6,2,1]`、`[1,2,1,3,1]`。

replay 结论：

1. 去掉 `lock_penalty` 后，`v72/v69` 关键对位仍仅 `49/100`；
2. `v64` 对位明显退化（`44/100`），说明仅删除终盘二次惩罚会放大中后盘风险切换；
3. 极端波动未下降（`largest_army_swing=1047`）。

### 103.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat-origin）：
   - 证据：风险闸门维持为单一连续 `reply_risk`，无额外分支；
   - 结果：结构更简，但对 `v72/v69` 仍 `49/100`。
   - 判定：`结构生效、强度未生效`。
2. ANTWar 借鉴点（领先态 reserved）：
   - 证据：保留低危险领先终盘预算收紧，但去掉闸门二次加罚；
   - 结果：`v64` 回退到 `44/100`。
   - 判定：`本轮未生效（回归）`。

### 103.6 回到生产口径的结论

1. 生产权威当前是 `eval_20260305_052402`，champion 已切到 `cpp_v72_overlay_endgame_lock`；
2. 本轮 iter 仅用于候选筛选，不用于生产 Elo 绝对结论；
3. 本轮结论标签：`regression`。
   - 原因：对当前 champion `v72` 未过线（`49/100`），对 `v64` 明显回退（`44/100`）。

### 103.7 风险、下一步与回合末自检

风险：

1. 关键对位 `v74-v72=49/100`、`v74-v69=49/100` 持续未过线；
2. `v74-v64=44/100` 显著退化；
3. replay 波动指标未收敛（`largest_army_swing=1047`）。

下一步：

1. 回到“最小回滚”路线：基于 `v73` 新开版本，仅恢复很小权重的 `lock_penalty`（例如 `0.10~0.15`），避免像 `v74` 这样完全移除；
2. 按 confirm 路线优先补 `vs v72/v69` 各 `>=200`，再决定是否保留终盘锁定项；
3. 继续推动导出 `hard_cutoff_hit` 计数，建立 CPU 风险观测闭环。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物仍未暴露 `hard_cutoff_hit` 计数，无法直接统计触发频次。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best/my_follow` 多次 base 评估链。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 先减少进入 `my_follow` 的候选规模，再调终盘惩罚斜率；
   - 优先小幅回调，不再引入新分支或新状态层。

### 104.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_055542`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v72_overlay_endgame_lock -> cpp_v73_overlay_calm_endgame_lock`（`promoted=true`）。
3. `config.pairs` 共 `45` 对，当前 champion 在其中出现 `6` 对。
4. 必做判读（champion 切换影响）：
   - 本 tag 发生 champion 切换（`v72 -> v73`），gauntlet 对手池受影响，属于高优先级风险；
   - 本轮结论仅在同池 head-to-head 内有效，不能跨 tag 直接比较 Elo 绝对值。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_060150`，mode=`gauntlet`，`matches=700`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_060150_matches.jsonl`（逐行含 `replay_file`）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 104.2 算法级改动落地（新版本 `v75`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v75/ai_v75.cpp`（未改写旧版本源码快照）。
2. 新版本 ID：`cpp_v75_overlay_calm_micro_lock`。
3. 注册项：`/www/autolab/registry.json`（`exe=/www/ai_cpp/v75/ai_v75`，`src=/www/ai_cpp/v75/ai_v75.cpp`）。

改动内容（简化优先）：

1. 基于 `v73` 做“最小回滚”：
   - `lock_penalty` 阈值由 `raw_drop-4.0` 调整为 `raw_drop-5.0`；
   - 权重由 `0.35` 下调到 `0.15`（微量终盘锁定）。
2. 保持单一连续 `reply_risk` 闸门结构，不新增分支状态与搜索层；
3. 保持 `endgame_stable_signal` 的轻量预算联动（`switch_margin/base_anchor_penalty`）。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin/impact_value` 连续威胁评分。
   - 映射：`reply_risk` 仍为单一连续闸门，只做微量斜率回调。
   - 代码落点：`select_best_move_overlay(...)` 的 `lock_penalty/reply_risk` 公式。
2. ANTWar 借鉴点：`global_state + reserved` 危险态保守预算。
   - 映射：保留“领先+终盘+低风险”预算收紧，并以 micro-lock 方式避免 `v74` 的完全放开。
   - 代码落点：`choose_overlay_tuning(...)` 的 `endgame_stable_signal` 与风险闸门中的小权重 lock 项。

### 104.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v72_overlay_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v75_overlay_calm_micro_lock \
  --opponents cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v72_overlay_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260412
```

结果：`eval_20260305_060150`（每对手 `100` 局，达到两 AI 比较门槛 `>=100`）：

1. `v75 vs v74 = 52/100`
2. `v75 vs v73(champion) = 49/100`
3. `v75 vs v72 = 55/100`
4. `v75 vs v69 = 51/100`
5. `v75 vs v64 = 45/100`
6. `v75 vs v1 = 80/100`
7. `v75 vs v2 = 82/100`

口径判读：

1. 本轮是 gate，不是 confirm（关键对位仍未达 `>=200`）；
2. 对当前生产 champion `v73` 仍未过线（`49/100`）；
3. 相比 `v74`，micro-lock 回滚修复了对 `v72/v69` 对位，但 `v64` 仍偏弱（`45/100`）。

### 104.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=700`，`analyzed=700`，`missing=0`，`parse_errors=0`；
2. `v75` 聚合：`win_rate=0.5914`，`avg_rounds=121.05`，`no_effect_rate=0.0598`；
3. pair 摘要（关键对位）：
   - `v75-v73: 49-51`
   - `v75-v72: 55-45`
   - `v75-v64: 45-55`
4. 极端波动仍高：`largest_army_swing=1047`（未见收敛）。

原始回放逐帧核对（均来自 `paths.matches` 的 `replay_file`）：

1. `v75 vs v72` 胜例（seed=`20262442`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_060150/20260305_060503_p0-cpp_v75_overlay_calm_micro_lock_p1-cpp_v72_overlay_endgame_lock_seed-20262442_rounds-180.jsonl`
   - turning point：round `179`（`delta_army_lead_p0=541`，`impact_score=541`）。
   - 附近动作：`R179 P0 Action [1,5,6,4,1]`、`[1,2,2,1,1]`、`[1,4,5,2,1]`。
2. `v75 vs v73` 负例（seed=`20261426`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_060150/20260305_060331_p0-cpp_v75_overlay_calm_micro_lock_p1-cpp_v73_overlay_calm_endgame_lock_seed-20261426_rounds-180.jsonl`
   - turning point：round `130`（`delta_army_lead_p0=-290`，`impact_score=290`）。
   - 附近动作：`R130 P0 Action [4,17,2,7,5]` 后仍被反制。
3. `v75 vs v64` 负例（seed=`20264483`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_060150/20260305_060919_p0-cpp_v75_overlay_calm_micro_lock_p1-cpp_v64_generals_rebuild_seed-20264483_rounds-180.jsonl`
   - turning point：round `161`（`delta_army_lead_p0=184`，`impact_score=192`）。
   - 附近动作：`R161 P0 Action [1,8,10,2,1]`、`[1,6,12,4,1]` 后被反压。
4. `v75 vs v69` 胜例（seed=`20264362`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_060150/20260305_060659_p0-cpp_v69_overlay_followup_prune_p1-cpp_v75_overlay_calm_micro_lock_seed-20264362_rounds-180.jsonl`
   - turning point：round `168`（`delta_army_lead_p0=366`，`impact_score=370`）。
   - 附近动作：`R168 P1 Action [4,21,2,6,6]`、`[1,11,6,2,1]`、`[1,2,1,3,1]`。

replay 结论：

1. micro-lock 相比 `v74` 恢复了对 `v72` 的稳定收益（`55/100`）；
2. 但对当前 champion `v73` 仍 `49/100`，关键对位未过线；
3. `v64` 对位仍弱（`45/100`），且极端波动未下降。

### 104.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat-origin）：
   - 证据：保持单一 `reply_risk` 连续闸门，仅做 lock 斜率微调；
   - 结果：对 `v72/v69` 有修复（`55/100`,`51/100`）。
   - 判定：`部分生效`。
2. ANTWar 借鉴点（领先态 reserved）：
   - 证据：恢复小权重 lock 后，终盘保守预算不再完全失效；
   - 结果：`v74 -> v75` 对 `v72` 从 `49/100` 提升到 `55/100`，但 `v64` 仍仅 `45/100`。
   - 判定：`部分生效但仍不稳定`。

### 104.6 回到生产口径的结论

1. 生产权威当前是 `eval_20260305_055542`，champion 为 `cpp_v73_overlay_calm_endgame_lock`；
2. 本 tag 发生 champion 切换（`v72 -> v73`），对手池口径风险高；
3. iter Elo 仅用于候选筛选，不能直接作为生产强度结论；
4. 本轮结论标签：`neutral`。
   - 原因：`v75` 修复了对 `v72/v69` 的退化，但对当前 champion `v73` 仍 `49/100` 未过线。

### 104.7 风险、下一步与回合末自检

风险：

1. 当前生产 champion 对位仍不足：`v75-v73=49/100`；
2. `v64` 对位持续弱势：`45/100`；
3. replay 波动指标未收敛（`largest_army_swing=1047`）。

下一步：

1. 按 confirm 路线补 `v75 vs v73` 追加 `>=100`（形成 `>=200`）；
2. 并行补 `v75 vs v64` 追加 `>=100`，确认弱势是否稳定；
3. 若 `v75-v73` 仍<50%，下一轮优先做“前置轻筛”减法（先裁掉高 `raw_drop` 低收益候选，再进入 `my_follow`）。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物仍未导出 `hard_cutoff_hit` 计数，无法统计触发频次。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best/my_follow` 多次 base 评估链。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 对进入 `my_follow` 的候选增加前置轻筛；
   - 维持“微量回调”策略，不新增状态层与分支链。

### 105.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_062938`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v74_overlay_calm_margin_only -> cpp_v74_overlay_calm_margin_only`（`promoted=false`）。
3. `config.pairs` 共 `45` 对，当前 champion 在其中出现 `3` 对。
4. 必做判读（champion 切换影响）：
   - 本 tag 内 `old==new`，本轮对手池不受“本次 champion 切换事件”直接影响；
   - 但近期生产 tag 发生过 champion 切换（例如 `v72->v73`），gauntlet 口径仍需谨慎，不能跨 tag 直接比较 Elo 绝对值。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_063214`，mode=`gauntlet`，`matches=700`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_063214_matches.jsonl`（逐行含 `replay_file`）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 105.2 算法级改动落地（新版本 `v76`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v76/ai_v76.cpp`（未改写旧版本源码快照）。
2. 新版本 ID：`cpp_v76_overlay_prefilter_prune`。
3. 注册项：`/www/autolab/registry.json`（`exe=/www/ai_cpp/v76/ai_v76`，`src=/www/ai_cpp/v76/ai_v76.cpp`）。

改动内容（简化优先）：

1. 在候选循环新增前置轻筛，提前剪掉高 `raw_drop` 分支，避免其进入 `enemy_best` 深评估链：
   - `precheck_raw_drop_cap = tuning.followup_raw_drop_cap + 3.0 - 2.0 * tuning.endgame_stable_signal`；
   - `if (!cand_is_base && raw_drop > precheck_raw_drop_cap) continue;`
2. 保持 `reply_risk` 单闸门与原有搜索结构，不新增状态机与搜索层级；
3. 硬截止路径保持不变（`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + 回退）。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin/impact_value` 连续威胁排序。
   - 映射：在进入深评估前先按连续风险量做候选剪枝。
   - 代码落点：`select_best_move_overlay(...)` 的 `precheck_raw_drop_cap` 轻筛。
2. ANTWar 借鉴点：`global_state + reserved` 的预算收敛。
   - 映射：在低危险终盘（`endgame_stable_signal` 高）自动收紧分支预算，减少高波动切换。
   - 代码落点：`precheck_raw_drop_cap` 与 `endgame_stable_signal` 联动。

### 105.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v76_overlay_prefilter_prune \
  --opponents cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260413
```

结果：`eval_20260305_063214`（每对手 `100` 局，达到两 AI 比较门槛 `>=100`）：

1. `v76 vs v75 = 53/100`
2. `v76 vs v74(champion) = 50/100`
3. `v76 vs v73 = 55/100`
4. `v76 vs v69 = 50/100`
5. `v76 vs v64 = 43/100`
6. `v76 vs v1 = 80/100`
7. `v76 vs v2 = 82/100`

口径判读：

1. 本轮仍是 gate，不是 confirm（关键对位未达 `>=200`）；
2. 对当前生产 champion `v74` 仅 `50/100`，未形成优势；
3. 对 `v64` 退化到 `43/100`，弱点仍明显。

### 105.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=700`，`analyzed=700`，`missing=0`，`parse_errors=0`；
2. `v76` 聚合：`win_rate=0.5900`，`avg_rounds=122.86`，`no_effect_rate=0.0590`；
3. pair 摘要（关键对位）：
   - `v76-v74: 50-50`
   - `v76-v73: 55-45`
   - `v76-v64: 43-57`
4. 极端波动仍高：`largest_army_swing=1047`（未见收敛）。

原始回放逐帧核对（均来自 `paths.matches` 的 `replay_file`）：

1. `v76 vs v74` 胜例（seed=`20262340`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_063214/20260305_063537_p0-cpp_v74_overlay_calm_margin_only_p1-cpp_v76_overlay_prefilter_prune_seed-20262340_rounds-180.jsonl`
   - turning point：round `139`（`delta_army_lead_p0=379`，`impact_score=383`）。
   - 附近动作：`R139 P1 Action [1,7,6,2,1]`、`[1,8,5,2,1]`、`[1,9,8,4,1]`。
2. `v76 vs v74` 负例（seed=`20261426`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_063214/20260305_063533_p0-cpp_v76_overlay_prefilter_prune_p1-cpp_v74_overlay_calm_margin_only_seed-20261426_rounds-180.jsonl`
   - turning point：round `130`（`delta_army_lead_p0=-290`，`impact_score=290`）。
   - 附近动作：`R130 P0 Action [4,17,2,7,5]` 后被反制。
3. `v76 vs v73` 胜例（seed=`20262442`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_063214/20260305_063715_p0-cpp_v76_overlay_prefilter_prune_p1-cpp_v73_overlay_calm_endgame_lock_seed-20262442_rounds-180.jsonl`
   - turning point：round `179`（`delta_army_lead_p0=541`，`impact_score=541`）。
   - 附近动作：`R179 P0 Action [1,5,6,4,1]`、`[1,2,2,1,1]`、`[1,4,5,2,1]`。
4. `v76 vs v64` 负例（seed=`20264483`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_063214/20260305_064151_p0-cpp_v76_overlay_prefilter_prune_p1-cpp_v64_generals_rebuild_seed-20264483_rounds-180.jsonl`
   - turning point：round `161`（`delta_army_lead_p0=184`，`impact_score=192`）。
   - 附近动作：`R161 P0 Action [1,8,10,2,1]`、`[1,6,12,4,1]` 后被反压。

replay 结论：

1. 前置轻筛在 `v73` 对位上有效（`55/100`），并保持 `v74` 不掉分（`50/100`）；
2. 但无法修复 `v64` 弱点（`43/100`）；
3. 波动指标仍未下降（`largest_army_swing=1047`）。

### 105.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat-origin）：
   - 证据：新增前置连续轻筛，减少高 drop 分支进入深评估；
   - 结果：`v76-v73=55/100`、`v76-v75=53/100`；
   - 判定：`部分生效`。
2. ANTWar 借鉴点（领先态 reserved）：
   - 证据：轻筛 cap 与 `endgame_stable_signal` 联动，终盘低风险场景更保守；
   - 结果：对 `v74` 至少不回退（`50/100`），但 `v64` 仍 `43/100`。
   - 判定：`部分生效但关键短板未修复`。

### 105.6 回到生产口径的结论

1. 生产权威当前是 `eval_20260305_062938`，champion 为 `cpp_v74_overlay_calm_margin_only`；
2. 本轮 iter 仅用于候选筛选，不能直接作为生产 Elo 结论；
3. 本轮结论标签：`regression`。
   - 原因：对当前 champion 仅 `50/100` 无优势，同时对关键基线 `v64` 退化到 `43/100`。

### 105.7 风险、下一步与回合末自检

风险：

1. 关键对位 `v76-v74` 仅 `50/100`，无晋级证据；
2. `v76-v64=43/100` 仍显著偏弱；
3. replay 波动指标未收敛（`largest_army_swing=1047`）。

下一步：

1. 按 confirm 路线补 `v76 vs v74` 与 `v76 vs v64` 各 `>=100`（形成 `>=200`）；
2. 若 `v64` 仍弱，下轮优先针对 `allowed_enemy_reply` 做小幅斜率回调（增 `base_reply_drop_scale` 的保守度），避免新增状态机；
3. 推进导出 `hard_cutoff_hit` 计数，形成 CPU 风险观测闭环。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码保持 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 当前评测产物仍未导出 `hard_cutoff_hit` 计数，无法直接统计触发频次。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best/my_follow` 多次 base 评估链，虽有前置轻筛但未完全消除。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 继续加大前置轻筛覆盖（优先不增加新分支状态）；
   - 保持“单闸门 + 小幅斜率回调”路线，避免补丁层增厚。

### 106.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_065755`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v74_overlay_calm_margin_only -> cpp_v71_overlay_replyrisk_gate`（`promoted=true`）。
3. `config.pairs` 共 `45` 对，当前 champion 在其中出现 `3` 对。
4. 必做判读（champion 切换影响）：
   - 本 tag 发生 champion 切换（`v74 -> v71`），gauntlet 对手池受影响，属于高优先级风险；
   - 本轮 iter gate 未包含 `v71`，因此对生产当前关键对位缺口明显，不能直接给出晋升结论。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_070231`，mode=`gauntlet`，`matches=800`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_070231_matches.jsonl`（逐行含 `replay_file`）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 106.2 算法级改动落地（新版本 `v77`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v77/ai_v77.cpp`（未改写旧版本源码快照）。
2. 新版本 ID：`cpp_v77_overlay_source_tighten`。
3. 注册项：`/www/autolab/registry.json`（`exe=/www/ai_cpp/v77/ai_v77`，`src=/www/ai_cpp/v77/ai_v77.cpp`）。

改动内容（简化优先）：

1. 基于 `v75` 做单点斜率回调（不继承 `v76` 前置轻筛分支）：
   - `tuning.base_reply_veto_slack -= 2.5 * source_pressure`；
   - `tuning.base_reply_drop_scale -= 0.10 * source_pressure`。
2. 保持 `reply_risk` 单闸门结构，不新增状态机；
3. 保持 CPU 硬截止与回退路径不变（`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit`）。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin/impact_value` 连续威胁源。
   - 映射：威胁源越多（`source_pressure` 越高），越收紧 `allowed_enemy_reply` 预算。
   - 代码落点：`choose_overlay_tuning(...)` 内 `base_reply_veto_slack` 的 source-pressure 回调。
2. ANTWar 借鉴点：`global_state + reserved` 危险态保守预算。
   - 映射：在 danger 态（高 `source_pressure`）缩小 `base_reply_drop_scale`，降低高 drop 切换放行。
   - 代码落点：`choose_overlay_tuning(...)` 内 `base_reply_drop_scale` 的 source-pressure 回调。

### 106.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v77_overlay_source_tighten,cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v77_overlay_source_tighten \
  --opponents cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260414
```

结果：`eval_20260305_070231`（每对手 `100` 局，达到两 AI 比较门槛 `>=100`）：

1. `v77 vs v76 = 53/100`
2. `v77 vs v75 = 51/100`
3. `v77 vs v74 = 53/100`
4. `v77 vs v73 = 51/100`
5. `v77 vs v69 = 41/100`
6. `v77 vs v64 = 51/100`
7. `v77 vs v1 = 82/100`
8. `v77 vs v2 = 79/100`

口径判读：

1. 本轮是 gate，不是 confirm（关键对位未达 `>=200`）；
2. 对 `v74/v64` 有修复信号，但对 `v69` 出现显著回归（`41/100`）；
3. 且生产 champion 已切到 `v71`，本轮缺少 `v77-v71` 对位，无法用于生产判优。

### 106.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=800`，`analyzed=800`，`missing=0`，`parse_errors=0`；
2. `v77` 聚合：`win_rate=0.5763`，`avg_rounds=117.01`，`no_effect_rate=0.0595`；
3. pair 摘要（关键对位）：
   - `v77-v74: 53-47`
   - `v77-v64: 51-49`
   - `v77-v69: 41-59`
4. 极端波动仍高：`largest_army_swing=1047`（未见收敛）。

原始回放逐帧核对（均来自 `paths.matches` 的 `replay_file`）：

1. `v77 vs v74` 胜例（seed=`20262442`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_070231/20260305_070643_p0-cpp_v77_overlay_source_tighten_p1-cpp_v74_overlay_calm_margin_only_seed-20262442_rounds-180.jsonl`
   - turning point：round `179`（`delta_army_lead_p0=541`，`impact_score=541`）。
   - 附近动作：`R179 P0 Action [1,5,6,4,1]`、`[1,2,2,1,1]`、`[1,4,5,2,1]`。
2. `v77 vs v74` 负例（seed=`20262467`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_070231/20260305_070745_p0-cpp_v77_overlay_source_tighten_p1-cpp_v74_overlay_calm_margin_only_seed-20262467_rounds-180.jsonl`
   - turning point：round `127`（`delta_army_lead_p0=442`，`impact_score=446`）。
   - 附近动作：`R127 P0 Action [1,12,6,1,1]`、`[1,11,2,4,1]` 后被 `P1` 反制。
3. `v77 vs v69` 负例（seed=`20264455`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_070231/20260305_071022_p0-cpp_v77_overlay_source_tighten_p1-cpp_v69_overlay_followup_prune_seed-20264455_rounds-180.jsonl`
   - turning point：round `156`（`delta_army_lead_p0=-469`，`impact_score=473`）。
   - 附近动作：`R156 P1 Action [7,6,8]`、`[1,6,10,1,1]`。
4. `v77 vs v64` 胜例（seed=`20266406`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_070231/20260305_071310_p0-cpp_v64_generals_rebuild_p1-cpp_v77_overlay_source_tighten_seed-20266406_rounds-180.jsonl`
   - turning point：round `166`（`delta_army_lead_p0=-507`，`impact_score=507`）。
   - 附近动作：`R166 P1 Action [1,9,5,4,3]`、`[1,1,6,1,1]`、`[1,1,7,2,1]`。

replay 结论：

1. source-pressure 收紧确实修复了 `v64` 对位（`43/100 -> 51/100`）并提升 `v74` 对位（`50/100 -> 53/100`）；
2. 但对 `v69` 出现明显回归（`50/100 -> 41/100`）；
3. 总体仍不稳定，且未覆盖当前生产 champion `v71`。

### 106.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat-origin）：
   - 证据：按 `source_pressure` 连续收紧 reply slack；
   - 结果：`v77-v74=53/100`、`v77-v64=51/100`。
   - 判定：`部分生效`。
2. ANTWar 借鉴点（danger/reserved）：
   - 证据：danger 态下收紧 `base_reply_drop_scale`；
   - 结果：修复 `v64`，但导致 `v69` 回归到 `41/100`。
   - 判定：`部分生效但副作用显著`。

### 106.6 回到生产口径的结论

1. 生产权威当前是 `eval_20260305_065755`，champion 为 `cpp_v71_overlay_replyrisk_gate`；
2. 本 tag 发生 champion 切换（`v74 -> v71`），对手池口径风险高；
3. 本轮 iter 未包含 `v71` 对位，不能用于生产判优；
4. 本轮结论标签：`neutral`。
   - 原因：虽修复 `v74/v64`，但 `v69` 回归显著且缺少对现 champion 的直接证据。

### 106.7 风险、下一步与回合末自检

风险：

1. `v77-v69=41/100` 明显回归；
2. 当前生产 champion `v71` 缺少 head-to-head 样本；
3. replay 波动指标未收敛（`largest_army_swing=1047`）。

下一步：

1. 优先补 gate/confirm：`v77 vs v71` 至少 `100`，建议直接补到 `200`；
2. 并行补 `v77 vs v69` 追加 `>=100`，确认回归稳定性；
3. 若 `v69` 回归稳定，下轮回调 source-pressure 斜率（先减 `drop_scale` 回调幅度），保持单闸门结构不加新状态。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍为 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退；
   - 评测产物仍未导出 `hard_cutoff_hit` 计数，无法统计触发频次。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best/my_follow` 多次 base 评估链。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 继续压缩进入深评估的候选数量，但只做斜率回调，不新增状态机；
   - 推动 `hard_cutoff_hit` 指标落盘，避免 CPU 风险不可观测。

### 107.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_072341`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v71_overlay_replyrisk_gate -> cpp_v73_overlay_calm_endgame_lock`（`promoted=true`）。
3. `config.pairs` 共 `45` 对；旧 champion `v71` 在 pairs 中出现 `5` 次，新 champion `v73` 出现 `1` 次。
4. 必做判读（champion 切换影响）：
   - 本 tag 发生 champion 切换，且 `pairs` 中 old/new 暴露频次差异明显（`5 -> 1`）；
   - 在 gauntlet 口径下属于高优先级池变化风险，不能把跨 tag Elo 绝对值直接当作可比强度。

迭代口径（仅用于候选筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_073355`，mode=`gauntlet`，`matches=1000`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_073355_matches.jsonl`（逐行含 `replay_file`）。
3. replay 分析已自动生成并同步：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 107.2 算法级改动落地（新版本 `v78`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v78/ai_v78.cpp`（未改写旧版本快照）。
2. 新版本 ID：`cpp_v78_overlay_source_reserve_release`。
3. 可执行文件：`/www/ai_cpp/v78/ai_v78`。
4. 注册项：`/www/autolab/registry.json`（notes: `source reserve_signal ... behind-state releases reserve`）。

改动内容（简化优先）：

1. 基于 `v77`，把 `source_pressure` 的收紧汇总为单一连续量 `reserve_signal`：
   - `reserve_signal = source_pressure * (0.30 + 0.70 * ahead_signal)`；
   - `reserve_signal *= (1.0 - 0.85 * behind_signal)`。
2. 将收紧仅作用于 `base_reply_veto_slack`：
   - `tuning.base_reply_veto_slack -= 2.2 * reserve_signal`。
3. 删除 `v77` 中“source 直接收紧 `base_reply_drop_scale`”这条强约束，减少对反打分支的过抑制。
4. 继续保持单闸门 `reply_risk` 结构，不新增状态机/补丁分支。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin_cnt / threat_value / impact_value` 连续威胁源。
   - 映射：`source_pressure -> reserve_signal` 连续收紧敌方回复预算。
   - 代码落点：`choose_overlay_tuning(...)` 的 `reserve_signal` 与 `base_reply_veto_slack`。
2. ANTWar 借鉴点：`global_state + reserved + safe_coin`。
   - 映射：领先态保留预算；落后态释放 reserved 以保留反打。
   - 代码落点：`behind_signal` 对 `reserve_signal` 的释放因子。

CPU 硬约束：

1. 搜索硬截止与回退路径保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` fallback。

### 107.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v78_overlay_source_reserve_release,cpp_v77_overlay_source_tighten,cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v71_overlay_replyrisk_gate,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v78_overlay_source_reserve_release \
  --opponents cpp_v77_overlay_source_tighten,cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v71_overlay_replyrisk_gate,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260415
```

结果：`eval_20260305_073355`（每对手 `100` 局，满足两版本比较门槛 `>=100`）：

1. `v78 vs v77 = 52/100`
2. `v78 vs v76 = 50/100`
3. `v78 vs v75 = 54/100`
4. `v78 vs v74 = 50/100`
5. `v78 vs v73 = 40/100`
6. `v78 vs v71 = 52/100`
7. `v78 vs v69 = 53/100`
8. `v78 vs v64 = 52/100`
9. `v78 vs v1 = 80/100`
10. `v78 vs v2 = 81/100`

口径判读：

1. 本轮为 gate（对每关键对手达到 `100`，但未达 confirm 的 `200`）；
2. `v69` 对位从上轮 `v77` 的 `41/100` 修复到 `53/100`；
3. 但当前生产 champion `v73` 对位退化到 `40/100`，为主阻断项。

### 107.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=1000`，`analyzed=1000`，`missing=0`，`parse_errors=0`；
2. `v78` 聚合：`win_rate=0.5640`，`avg_rounds=113.32`，`no_effect_rate=0.0607`；
3. pair 摘要：`v78-v69=53-47`，`v78-v71=52-48`，`v78-v73=40-60`；
4. 极端波动仍高：`largest_army_swing=1062`（未收敛）。

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. `v78 vs v69` 负例（seed=`20266518`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_073355/20260305_074508_p0-cpp_v78_overlay_source_reserve_release_p1-cpp_v69_overlay_followup_prune_seed-20266518_rounds-180.jsonl`
   - turning point：round `139`，`impact_score=320`（`delta_army_lead_p0=-320`）。
   - 该回合动作：`P0 [1,1,4,2,1]`、`[1,0,5,3,1]`；`P1 [1,5,3,4,1]`、`[1,6,6,2,1]`、`[1,7,2,3,1]`。
2. `v78 vs v69` 胜例（seed=`20267422`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_073355/20260305_074458_p0-cpp_v69_overlay_followup_prune_p1-cpp_v78_overlay_source_reserve_release_seed-20267422_rounds-180.jsonl`
   - turning point：round `95`，`impact_score=215`（`delta_army_lead_p0=215`）。
   - 该回合动作：`P0 [4,14,2,4,7]`、`[1,2,5,1,1]`；`P1 [1,6,9,3,1]`、`[1,0,11,4,1]`。
3. `v78 vs v73` 负例（seed=`20264455`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_073355/20260305_074044_p0-cpp_v78_overlay_source_reserve_release_p1-cpp_v73_overlay_calm_endgame_lock_seed-20264455_rounds-180.jsonl`
   - turning point：round `156`，`impact_score=473`（`delta_army_lead_p0=-469`）。
   - 该回合动作：`P1 [7,6,8]`、`[1,6,10,1,1]`、`[1,1,11,4,1]`。
4. `v78 vs v71` 胜例（seed=`20265476`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_073355/20260305_074236_p0-cpp_v78_overlay_source_reserve_release_p1-cpp_v71_overlay_replyrisk_gate_seed-20265476_rounds-180.jsonl`
   - turning point：round `149`，`impact_score=188`。
   - 该回合动作：`P0 [4,18,2,2,10]`、`[1,5,12,1,1]`、`[1,7,11,1,1]`。
5. `v78 vs v64` 胜例（seed=`20268419`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_073355/20260305_074624_p0-cpp_v64_generals_rebuild_p1-cpp_v78_overlay_source_reserve_release_seed-20268419_rounds-180.jsonl`
   - turning point：round `161`，`impact_score=455`。
   - 该回合动作：`P1 [4,24,2,8,8]`、`[1,9,7,2,1]`、`[1,8,6,3,2]`。

replay 结论：

1. `v69` 对位已从 `v77` 的明显回归（`41/100`）修复到 `53/100`；
2. 但对当前生产 champion `v73` 出现稳定负差（`40/100`），且高冲击回合仍频繁；
3. 波动指标 `largest_army_swing=1062` 说明结构稳定性未收敛。

### 107.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（threat-origin 连续压力）：
   - 证据：`reserve_signal` 将 source 压力连续注入 reply slack；
   - 结果：`v78-v69=53/100`（对 `v77` 的 `41/100` 明显修复）。
   - 判定：`生效`。
2. ANTWar 借鉴点（global_state/reserved，落后释放）：
   - 证据：`behind_signal` 释放 reserve，降低落后时过保守；
   - 结果：`v78-v71=52/100`、`v78-v64=52/100`，但 `v78-v73=40/100`。
   - 判定：`部分生效，且对现 champion 出现副作用`。

### 107.6 回到生产口径的结论

1. 生产唯一权威仍是 `/www/autolab/runtime/latest.json`（`eval_20260305_072341`，champion=`v73`）；
2. iter Elo 仅用于筛选，不能与生产 Elo 跨 scope 直接比较绝对值；
3. 本轮虽然修复 `v69`，但对当前生产 champion `v73` 为 `40/100`（`>=100` 样本）；
4. 本轮结论标签：`regression`（相对生产关键对手口径不满足晋级条件）。

### 107.7 风险、下一步与回合末自检

风险：

1. 当前主阻断是 `v78-v73=40/100`；
2. replay 显示高冲击波动仍未收敛（`largest_army_swing=1062`）；
3. champion 切换导致 gauntlet 池口径变化，不能用单轮名次替代 head-to-head 结论。

下一步：

1. 下轮优先对 `v73` 定向修复并保持 `v69` 不回退，继续走“单闸门 + 连续信号”减法路线；
2. gate/confirm 路径建议：`v79 vs v73/v69/v71` 各补到 `>=200`；
3. 若 `v73` 仍弱，优先减少 `ahead/endgame` 侧额外惩罚耦合，避免再叠新分支。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍具备 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + fallback；
   - 评测产物未导出 `hard_cutoff_hit` 计数，无法统计触发频次。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 中 `enemy_best/my_follow` 的重复 base 评估链。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 继续压缩深评估触发面（优先调连续系数，不加状态机）；
   - 推进导出 `hard_cutoff_hit` 指标，形成 CPU 风险可观测闭环。

### 108.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_075833`，mode=`adaptive`。
2. `champion.old/new`=`cpp_v73_overlay_calm_endgame_lock -> cpp_v75_overlay_calm_micro_lock`（`promoted=true`）。
3. `config.pairs` 共 `45` 对；old/new 在 pairs 中出现次数分别为 `7/4`。
4. 必做判读（champion 切换影响）：
   - 本回合生产口径发生 champion 切换（`v73 -> v75`），gauntlet 对手池已变化；
   - 在该口径下 Elo 绝对值不可与旧 tag 或 iter 直接横比，属于高优先级风险。

迭代口径（仅用于筛选）：

1. `iter/latest.json`=`/www/autolab/runtime/scopes/iter/latest.json`，tag=`eval_20260305_080229`，mode=`gauntlet`，`matches=1100`。
2. `paths.matches`=`/www/autolab/runtime/scopes/iter/eval_20260305_080229_matches.jsonl`（逐行含 `replay_file`）。
3. replay 分析已自动生成：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`

### 108.2 算法级改动落地（新版本 `v79`）

新版本与注册信息：

1. 新目录：`/www/ai_cpp/v79/ai_v79.cpp`（未改写既有版本快照）。
2. 新版本 ID：`cpp_v79_overlay_risk_weighted_release`。
3. 可执行文件：`/www/ai_cpp/v79/ai_v79`。
4. 注册项：`/www/autolab/registry.json`（notes: `behind release is risk-weighted...`）。

改动内容（简化优先）：

1. 基于 `v78`，保留单一 `reserve_signal` 主线，不新增离散状态；
2. 将“落后态释放 reserve”改为风险加权释放（高风险少释放）：
   - `release_signal = 0.85 * behind_signal * (0.35 + 0.65 * (1.0 - risk_alpha))`；
   - `reserve_signal *= (1.0 - clamp(release_signal, 0.0, 0.90))`。
3. 保持 `reply_risk` 单闸门与原搜索框架，不新增状态机分支。

旧 AI 借鉴链路（可验证）：

1. Generals 借鉴点：`threat_origin_cnt/impact_value` 连续威胁压力。
   - 映射：`source_pressure -> reserve_signal` 连续调节敌方回复预算。
   - 代码落点：`choose_overlay_tuning(...)` 中 `reserve_signal`。
2. ANTWar 借鉴点：`global_state + reserved + danger`。
   - 映射：落后可释放 reserve，但 danger 高时保留预算（风险加权释放）。
   - 代码落点：`release_signal` 对 `reserve_signal` 的衰减。

CPU 硬约束：

1. 继续保留 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退路径。

### 108.3 可复现实验（规定脚本，iter gate）

执行命令（14 核，隔离 scope）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v79_overlay_risk_weighted_release,cpp_v78_overlay_source_reserve_release,cpp_v77_overlay_source_tighten,cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v71_overlay_replyrisk_gate,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v79_overlay_risk_weighted_release \
  --opponents cpp_v78_overlay_source_reserve_release,cpp_v77_overlay_source_tighten,cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v71_overlay_replyrisk_gate,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260416
```

结果：`eval_20260305_080229`（每对手 `100` 局，达到两版本比较门槛 `>=100`）：

1. `v79 vs v78 = 54/100`
2. `v79 vs v77 = 51/100`
3. `v79 vs v76 = 54/100`
4. `v79 vs v75 = 50/100`
5. `v79 vs v74 = 40/100`
6. `v79 vs v73 = 53/100`
7. `v79 vs v71 = 54/100`
8. `v79 vs v69 = 56/100`
9. `v79 vs v64 = 56/100`
10. `v79 vs v1 = 83/100`
11. `v79 vs v2 = 77/100`

口径判读：

1. 本轮为 gate（`>=100`），不是 confirm（关键对位尚未 `>=200`）；
2. 相对 `v78`，`v73` 对位从 `40/100` 修复到 `53/100`，`v69` 从 `53/100` 提升到 `56/100`；
3. 但 `v74` 对位明显退化到 `40/100`，结构稳定性仍有 trade-off。

### 108.4 Replay 分析与原始回放核对

replay 汇总（`iter_latest.md` / `latest.json`）：

1. `rows=1100`，`analyzed=1100`，`missing=0`，`parse_errors=0`；
2. `v79` 聚合：`win_rate=0.5709`，`avg_rounds=113.57`，`no_effect_rate=0.0615`；
3. 关键 pair：`v79-v73=53-47`、`v79-v69=56-44`、`v79-v71=54-46`、`v79-v75=50-50`；
4. 极端波动仍高：`largest_army_swing=1062`。

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. `v79 vs v73` 胜例（seed=`20265501`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_080229/20260305_081253_p0-cpp_v79_overlay_risk_weighted_release_p1-cpp_v73_overlay_calm_endgame_lock_seed-20265501_rounds-180.jsonl`
   - turning point：round `95`，`impact_score=171`（`delta_army_lead_p0=167`）。
   - 该回合动作：`P0 [1,11,9,2,1]`、`[1,11,9,4,1]`；`P1 [4,16,2,10,3]`。
2. `v79 vs v73` 负例（seed=`20266392`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_080229/20260305_081224_p0-cpp_v73_overlay_calm_endgame_lock_p1-cpp_v79_overlay_risk_weighted_release_seed-20266392_rounds-180.jsonl`
   - turning point：round `148`，`impact_score=354`（`delta_army_lead_p0=-354`）。
   - 该回合动作：`P0 [4,18,2,2,12]`、`[1,5,10,3,1]`；`P1 [1,4,12,4,2]`。
3. `v79 vs v69` 胜例（seed=`20268419`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_080229/20260305_081553_p0-cpp_v69_overlay_followup_prune_p1-cpp_v79_overlay_risk_weighted_release_seed-20268419_rounds-180.jsonl`
   - turning point：round `157`，`impact_score=603`（`delta_army_lead_p0=603`）。
   - 该回合动作：`P0 [1,7,8,2,90]`、`[1,7,8,2,45]`；`P1 [1,11,7,2,1]`。
4. `v79 vs v69` 负例（seed=`20267520`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_080229/20260305_081624_p0-cpp_v79_overlay_risk_weighted_release_p1-cpp_v69_overlay_followup_prune_seed-20267520_rounds-180.jsonl`
   - turning point：round `177`，`impact_score=428`（`delta_army_lead_p0=-424`）。
   - 该回合动作：`P0 [4,17,2,1,5]`、`[1,3,6,4,1]`；`P1 [1,4,5,3,1]`。
5. `v79 vs v71` 胜例（seed=`20267422`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_080229/20260305_081436_p0-cpp_v71_overlay_replyrisk_gate_p1-cpp_v79_overlay_risk_weighted_release_seed-20267422_rounds-180.jsonl`
   - turning point：round `95`，`impact_score=215`。
   - 该回合动作：`P0 [4,14,2,4,7]`；`P1 [1,6,9,3,1]`、`[1,0,11,4,1]`。

replay 结论：

1. 风险加权释放修复了 `v78` 的主阻断（对 `v73` 从 `40/100` 回到 `53/100`）；
2. 对 `v69/v71/v64` 同时保持正差（`56/54/56`）；
3. 但 `v74` 对位回退到 `40/100`，且高波动仍未收敛（`largest_army_swing=1062`）。

### 108.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（threat-origin 连续压力）：
   - 证据：`reserve_signal` 仍为单连续量，并通过 `risk_alpha` 加权释放；
   - 结果：`v79-v73=53/100`、`v79-v69=56/100`。
   - 判定：`生效`。
2. ANTWar 借鉴点（global_state/reserved/danger）：
   - 证据：behind 释放在高 danger 下被抑制（保留 reserve）；
   - 结果：修复了 `v73` 回归，但 `v74` 出现 `40/100` 副作用。
   - 判定：`部分生效（有副作用）`。

### 108.6 回到生产口径的结论

1. 生产权威当前为 `eval_20260305_075833`，champion=`cpp_v75_overlay_calm_micro_lock`；
2. 本轮迭代结果仅作筛选，不可与生产 Elo 绝对值跨 scope 比较；
3. `v79` 对当前生产 champion `v75` 仅 `50/100`（`>=100` 样本），暂无优势结论；
4. 本轮结论标签：`neutral`。
   - 原因：修复了 `v73` 并提升 `v69/v71/v64`，但对 `v75` 无增益、对 `v74` 明显退化。

### 108.7 风险、下一步与回合末自检

风险：

1. `v79-v74=40/100` 显示 trade-off 明显；
2. replay 的极端波动仍高（`largest_army_swing=1062`）；
3. 生产 champion 切换（`v73->v75`）导致 gauntlet 口径变化，结论必须以 head-to-head 补样确认。

下一步：

1. 进入 confirm：优先补 `v79 vs v75/v73/v69` 各 `+100`（累计到 `>=200`）；
2. 若 `v74` 回退持续，优先回调 `release_signal` 的上限（连续系数微调）而不新增新状态；
3. 同步推进 `hard_cutoff_hit` 计数落盘，建立 CPU 风险可观测闭环。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码保持 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + fallback；
   - 评测产物仍无 `hard_cutoff_hit` 计数，触发频次不可观测。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best/my_follow` 重复评估链。
3. 若有风险，下一轮如何降复杂度或改进剪枝：
   - 优先压缩深评估触发面（调连续系数），保持单闸门结构；
   - 导出截止触发统计，避免 CPU 风险盲区。

### 109.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，当前 tag=`eval_20260305_082908`。
2. `champion.old/new`=`cpp_v75_overlay_calm_micro_lock -> cpp_v70_overlay_opening_subpressure`（`promoted=true`）。
3. `config.pairs` 共 `45` 对；old/new 在 pairs 中出现次数分别为 `6/3`。
4. 必做判读（champion 切换影响）：
   - 本轮生产口径发生 champion 切换（`v75 -> v70`），gauntlet 对手池已变化；
   - 该变化会直接影响单轮 Elo 与名次解释，属于高优先级风险；
   - 生产 Elo 仍是唯一权威，iter Elo 仅用于候选筛选，禁止跨 scope 比较 Elo 绝对值。

迭代口径（隔离，仅筛选）：

1. 第一轮 gate：`eval_20260305_083630`（`1200` 局，12 对手 x 100）。
2. 因生产 champion 在本轮切换，补做 head-to-head gate：`eval_20260305_090453`（`400` 局，4 对手 x 100）。
3. 当前 iter latest：`/www/autolab/runtime/scopes/iter/latest.json` -> tag=`eval_20260305_090453`。
4. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_090453_matches.jsonl`（逐行含 `replay_file`）。
5. replay 分析：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`
   - latest 汇总：`rows_in_matches_file=400`、`analyzed_matches=400`、`missing_replay=0`、`replay_parse_errors=0`。

旧 AI 参考（本轮显式提取）：

1. Generals-AI：`threat_origin_cnt/impact_value` 连续威胁建模（`/www/past_AIs/Generals-AI/main.cpp`，如 `185-189`, `983-985`）。
2. ANTWar-AI：`global_state + reserved + safe_coin` 的全局态保留/释放机制（`/www/past_AIs/ANTWar-AI/main.cpp`，如 `31`, `38`, `165`, `1530-1538`, `1656`）。

### 109.2 算法级改动落地（新版本 `v80`）

新版本与注册信息（未改写旧快照）：

1. 新目录：`/www/ai_cpp/v80/ai_v80.cpp`。
2. 新版本 ID：`cpp_v80_overlay_release_time_decay`。
3. 可执行文件：`/www/ai_cpp/v80/ai_v80`。
4. 注册位置：`/www/autolab/registry.json`（notes: `behind reserve release decays by round...`）。

本轮策略改动（相对 `v79`，简化优先）：

1. 保留单主线 `reserve_signal`，不新增离散状态机；
2. 将 behind 释放加入回合衰减窗：
   - 新增 `release_window = 0.20 + 0.80 * (1.0 - endgame_signal)`；
   - `release_signal = 0.85 * behind_signal * (0.35 + 0.65 * (1.0 - risk_alpha)) * release_window`；
   - 仍通过 `reserve_signal *= (1.0 - clamp(release_signal, 0.0, 0.90))` 生效。

可验证链路（旧 AI 借鉴点 -> 本游戏映射 -> 代码落点）：

1. Generals 借鉴点（threat-origin 连续压力）
   - 映射：把 threat-source 压力折叠成单连续 `reserve_signal`，不引入额外分支；
   - 代码落点：`choose_overlay_tuning(...)` 中 `reserve_signal` 构造与 `base_reply_veto_slack` 调节。
2. ANTWar 借鉴点（global_state/reserved + late policy）
   - 映射：落后可释放 reserve，但进入后期逐步收紧释放窗口，避免后期过激反打；
   - 代码落点：`release_window` 与 `release_signal`。

CPU 硬约束：

1. 版本继续保留 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + fallback（`hard_cutoff_hit` 早停回退）。

### 109.3 可复现实验（规定脚本，iter 隔离）

实验 A（广谱 gate，12 对手）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v80_overlay_release_time_decay,cpp_v79_overlay_risk_weighted_release,cpp_v78_overlay_source_reserve_release,cpp_v77_overlay_source_tighten,cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v71_overlay_replyrisk_gate,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v80_overlay_release_time_decay \
  --opponents cpp_v79_overlay_risk_weighted_release,cpp_v78_overlay_source_reserve_release,cpp_v77_overlay_source_tighten,cpp_v76_overlay_prefilter_prune,cpp_v75_overlay_calm_micro_lock,cpp_v74_overlay_calm_margin_only,cpp_v73_overlay_calm_endgame_lock,cpp_v71_overlay_replyrisk_gate,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260417
```

结果（`eval_20260305_083630`，每对手 `100` 局）：

1. `v80 vs v79 = 54/100`
2. `v80 vs v78 = 51/100`
3. `v80 vs v77 = 53/100`
4. `v80 vs v76 = 50/100`
5. `v80 vs v75 = 39/100`
6. `v80 vs v74 = 53/100`
7. `v80 vs v73 = 55/100`
8. `v80 vs v71 = 56/100`
9. `v80 vs v69 = 51/100`
10. `v80 vs v64 = 50/100`
11. `v80 vs v1 = 78/100`
12. `v80 vs v2 = 76/100`

实验 B（生产切换后补做 h2h gate）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v80_overlay_release_time_decay,cpp_v70_overlay_opening_subpressure,cpp_v75_overlay_calm_micro_lock,cpp_v73_overlay_calm_endgame_lock,cpp_v79_overlay_risk_weighted_release,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v80_overlay_release_time_decay \
  --opponents cpp_v70_overlay_opening_subpressure,cpp_v75_overlay_calm_micro_lock,cpp_v73_overlay_calm_endgame_lock,cpp_v79_overlay_risk_weighted_release \
  --seed 20260418
```

结果（`eval_20260305_090453`，每对手 `100` 局）：

1. `v80 vs v70(当前生产 champion) = 54/100`
2. `v80 vs v75 = 53/100`
3. `v80 vs v73 = 55/100`
4. `v80 vs v79 = 52/100`

门槛判读：

1. 上述均为 pairwise `>=100`，可用于 gate 级方向判断；
2. 仍未达到 confirm（关键对位 `>=200`）门槛；
3. 不能据此宣称“明确优于多个老版本”（尚未满足 `>=200` 且全部 `>55%`）。

### 109.4 Replay 分析与原始回放核对

最新 replay 汇总（`eval_20260305_090453`）：

1. `rows_in_matches_file=400`，`analyzed_matches=400`，`missing_replay=0`，`replay_parse_errors=0`；
2. `v80` 聚合：`win_rate=0.535`，`avg_rounds=106.28`，`no_effect_rate=0.0616`；
3. 关键 pair：`v80-v70=54-46`、`v80-v75=53-47`、`v80-v73=55-45`、`v80-v79=52-48`；
4. 极端波动仍高：`largest_army_swing=1047`（`v80-v70`）。

原始回放逐帧核对（来自 `paths.matches` 的 `replay_file`）：

1. `v80 vs v70` 胜例（seed=`20261340`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_090453/20260305_090511_p0-cpp_v70_overlay_opening_subpressure_p1-cpp_v80_overlay_release_time_decay_seed-20261340_rounds-180.jsonl`
   - turning point：round `116`，`impact_score=115`（`delta_army_lead_p0=-107`）。
   - 该回合动作：`P0 [1,10,12,3,3]`、`[1,12,11,1,1]`；`P1 [1,13,8,4,1]`、`[1,6,11,4,1]`。
2. `v80 vs v70` 负例（seed=`20260464`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_090453/20260305_090624_p0-cpp_v80_overlay_release_time_decay_p1-cpp_v70_overlay_opening_subpressure_seed-20260464_rounds-180.jsonl`
   - turning point：round `150`，`impact_score=61`（`delta_army_lead_p0=61`）。
   - 该回合动作：`P0 [1,1,4,1,2]`、`[1,0,0,2,1]`；`P1 [1,1,11,3,1]`、`[1,3,10,3,1]`。
3. `v80 vs v75` 胜例（seed=`20261471`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_090453/20260305_090756_p0-cpp_v80_overlay_release_time_decay_p1-cpp_v75_overlay_calm_micro_lock_seed-20261471_rounds-180.jsonl`
   - turning point：round `143`，`impact_score=253`（`delta_army_lead_p0=249`）。
   - 该回合动作：`P0 [3,5,1]`、`[1,3,10,3,1]`；`P1 [1,4,6,1,1]`、`[1,1,7,3,1]`。
4. `v80 vs v75` 负例（seed=`20261457`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_090453/20260305_090727_p0-cpp_v80_overlay_release_time_decay_p1-cpp_v75_overlay_calm_micro_lock_seed-20261457_rounds-180.jsonl`
   - turning point：round `130`，`impact_score=133`（`delta_army_lead_p0=-129`）。
   - 该回合动作：`P0 [1,8,2,1,1]`、`[1,11,1,1,1]`；`P1 [1,9,5,3,1]`、`[1,9,9,4,1]`。
5. `v80 vs v73` 胜例（seed=`20263388`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_090453/20260305_090938_p0-cpp_v73_overlay_calm_endgame_lock_p1-cpp_v80_overlay_release_time_decay_seed-20263388_rounds-180.jsonl`
   - turning point：round `129`，`impact_score=91`（`delta_army_lead_p0=-75`）。
   - 该回合动作：`P0 [1,10,0,1,2]`、`[1,10,0,2,2]`；`P1 [1,10,3,1,1]`、`[1,10,2,3,1]`。
6. `v80 vs v79` 负例（seed=`20263452`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_090453/20260305_091016_p0-cpp_v80_overlay_release_time_decay_p1-cpp_v79_overlay_risk_weighted_release_seed-20263452_rounds-180.jsonl`
   - turning point：round `59`，`impact_score=47`（`delta_army_lead_p0=-47`）。
   - 该回合动作：`P1 [1,10,5,4,1]`、`[1,10,7,1,1]`（该回合 `P0` 无非终局动作）。

replay 结论：

1. `v80` 在 `v70/v75/v73` 对位均能打出长局后期翻转样本（多局 `max_round=180`）；
2. 但大波动仍突出（`largest_army_swing=1047`），说明“后期释放衰减”未根治震荡；
3. 与实验 A（`083630`）相比，`v75` 对位从 `39/100` 到补测 `53/100`，样本方差/种子敏感性明显。

### 109.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat-origin 压力）
   - 证据：`reserve_signal` 仍作为单连续量主导预算调节，无新增状态机；
   - 结果：在补测 `090453` 中，对 `v70/v73/v79` 为 `54/55/52`；
   - 判定：`生效`。
2. ANTWar 借鉴点（global_state/reserved + late-round policy）
   - 证据：`release_window` 将落后释放随 `endgame_signal` 衰减；
   - 结果：`v74` 回退在实验 A 修复（`53/100`），补测里 `v75` 从负差（A）回到正差（B）；
   - 判定：`部分生效，但稳定性不足`。

### 109.6 回到生产口径的结论

1. 生产唯一权威为 `eval_20260305_082908`，当前 champion=`cpp_v70_overlay_opening_subpressure`；
2. 本轮已按要求在 champion 切换后补做 h2h gate（`v80 vs v70`，`100` 局）；
3. `v80` 对当前生产 champion `v70` 为 `54/100`（gate 正向但未达 `>55%`）；
4. 结合实验 A/B 的冲突（尤其 `v75` 对位 `39 -> 53`），本轮只可给出筛选级信号，不能下“明确更强”结论；
5. 本轮结论标签：`neutral`。

### 109.7 风险、下一步与回合末自检

风险：

1. 跨 seed 波动较大（`v80-v75` 在两轮 gate 出现 `39/100` 与 `53/100` 分歧）；
2. replay 显示极端兵力波动仍高（`largest_army_swing=1047`）；
3. gauntlet 口径受生产 champion 切换影响显著，单轮名次不可替代大样本 h2h。

下一步：

1. 进入 confirm：对 `v80 vs v70/v75/v73/v79` 各补 `+100`（累计到 `>=200`），优先固定对手池+多 seed；
2. 若波动仍高，优先继续“减法”：限制高风险高回合的 follow-up 扩张，不新增新状态层；
3. 推进把 `hard_cutoff_hit` 计数写入评测产物，形成 CPU 截止可观测闭环。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码路径保持 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + fallback；
   - 当前评测报告仍未导出 `hard_cutoff_hit`，触发频次不可直接统计。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 仍存在于 overlay 的 `enemy_best/my_follow` 重复评估链（长局高波动对局更敏感）。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 保持单闸门结构，优先收紧深评估触发面与候选池；
   - 补齐截止计数落盘后，再按热点回放定向减枝。

### 110.1 最新状态读取（强制项）

已读取并遵守：`/www/docs/codex_objective_fixed.md`。

生产口径（唯一权威）：

1. `latest.json`=`/www/autolab/runtime/latest.json`，tag=`eval_20260305_092145`。
2. `champion.old/new`=`cpp_v72_overlay_endgame_lock -> cpp_v69_overlay_followup_prune`（`promoted=true`）。
3. `config.pairs` 共 `45` 对；old/new 在 pairs 中出现次数分别为 `3/4`。
4. 必做判读（champion 切换影响）：
   - 本轮生产口径发生 champion 切换（`v72 -> v69`），gauntlet 对手池受影响，属高优先级风险；
   - 单轮 gauntlet Elo 绝对值不可跨 tag 或跨 scope 直接比较。

迭代口径（隔离，仅筛选）：

1. `iter/latest.json` 当前为 `eval_20260305_093220`（`matches=1000`）。
2. `paths.matches`：`/www/autolab/runtime/scopes/iter/eval_20260305_093220_matches.jsonl`。
3. replay 分析：
   - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
   - `/www/docs/replay_analysis/iter_latest.md`
   - 汇总：`rows_in_matches_file=1000`、`analyzed_matches=1000`、`missing_replay=0`、`replay_parse_errors=0`。

旧 AI 借鉴点（本轮显式提取）：

1. Generals-AI：`threat_origin_cnt/impact_value`（连续威胁与影响值，`/www/past_AIs/Generals-AI/main.cpp`）。
2. ANTWar-AI：`global_state + reserved + safe_coin`（全局态预算保留/释放，`/www/past_AIs/ANTWar-AI/main.cpp`）。

### 110.2 算法级改动（新版本 `v81`）

新版本与注册信息（未改写旧快照）：

1. 新目录：`/www/ai_cpp/v81/ai_v81.cpp`。
2. 新版本 ID：`cpp_v81_overlay_deficit_late_release`。
3. 可执行：`/www/ai_cpp/v81/ai_v81`。
4. 注册：`/www/autolab/registry.json`（notes: `from v80: ... behind-state release floor ...`）。

改动（相对 `v80`，减法 + 连续信号）：

1. 保留 `v80` 的后期释放衰减主线；
2. 新增“落后态后期释放底线”（无新状态机）：
   - `late_release_floor = 0.20 + 0.45 * behind_signal`
   - `release_window = max(0.20 + 0.80*(1-endgame_signal), late_release_floor)`
3. 保持 `release_signal` 单式：
   - `release_signal = 0.85 * behind_signal * (0.35 + 0.65*(1-risk_alpha)) * release_window`。

可验证链路（旧 AI 借鉴点 -> 映射 -> 代码落点）：

1. Generals 借鉴点（连续 threat/impact）：
   - 映射：继续用单连续 `reserve_signal` 承载 threat-source 压力；
   - 代码落点：`choose_overlay_tuning(...)` 中 `reserve_signal` 与 `base_reply_veto_slack`。
2. ANTWar 借鉴点（global_state/reserved）：
   - 映射：后期默认收紧释放，但在落后态保留最小释放预算，避免彻底“锁死”反打；
   - 代码落点：`late_release_floor` 与 `release_window`。

CPU 硬约束：

1. 维持 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + fallback 回退路径。

### 110.3 可复现实验（规定脚本，iter gate）

执行命令（14 核、iter 隔离）：

```bash
EXPERIMENT_RUNTIME_SCOPE=iter \
EXPERIMENT_GAMES_PER_PAIR=50 \
EXPERIMENT_MAX_ROUNDS=180 \
EXPERIMENT_JOBS=14 \
EXPERIMENT_CPU_POLICY=all \
/www/scripts/autolab_eval_experiment_once.sh \
  --versions cpp_v81_overlay_deficit_late_release,cpp_v80_overlay_release_time_decay,cpp_v79_overlay_risk_weighted_release,cpp_v75_overlay_calm_micro_lock,cpp_v73_overlay_calm_endgame_lock,cpp_v72_overlay_endgame_lock,cpp_v70_overlay_opening_subpressure,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --challengers cpp_v81_overlay_deficit_late_release \
  --opponents cpp_v80_overlay_release_time_decay,cpp_v79_overlay_risk_weighted_release,cpp_v75_overlay_calm_micro_lock,cpp_v73_overlay_calm_endgame_lock,cpp_v72_overlay_endgame_lock,cpp_v70_overlay_opening_subpressure,cpp_v69_overlay_followup_prune,cpp_v64_generals_rebuild,cpp_v1_current,cpp_v2_beam \
  --seed 20260419
```

结果：`eval_20260305_093220`（每对手 `100` 局，gate 门槛达标）：

1. `v81 vs v80 = 56/100`
2. `v81 vs v79 = 54/100`
3. `v81 vs v75 = 53/100`
4. `v81 vs v73 = 52/100`
5. `v81 vs v72 = 39/100`
6. `v81 vs v70 = 54/100`
7. `v81 vs v69(当前生产 champion) = 55/100`
8. `v81 vs v64 = 53/100`
9. `v81 vs v1 = 79/100`
10. `v81 vs v2 = 81/100`

门槛判读：

1. pairwise 均 `>=100`，可做 gate 判断；
2. 尚未到 confirm（关键对位 `>=200`）阶段；
3. 不能宣称“新版本已明确优于多个老版本”。

### 110.4 Replay 分析与原始回放核对

replay 汇总（`eval_20260305_093220`）：

1. `rows=1000`、`analyzed=1000`、`missing=0`、`parse_errors=0`；
2. `v81` 聚合：`win_rate=0.576`、`avg_rounds=115.71`、`no_effect_rate=0.0602`；
3. 关键 pair：`v81-v69=55-45`、`v81-v70=54-46`、`v81-v72=39-61`、`v81-v80=56-44`；
4. 极端波动仍高：`largest_army_swing=1062`。

原始回放逐帧核对（来自 `paths.matches`）：

1. `v81 vs v69` 胜例（seed=`20267422`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_093220/20260305_094502_p0-cpp_v69_overlay_followup_prune_p1-cpp_v81_overlay_deficit_late_release_seed-20267422_rounds-180.jsonl`
   - turning point：round `95`，`impact_score=215`（`delta_army_lead_p0=215`）。
   - 该回合动作：`P0 [4,14,2,4,7]`；`P1 [1,6,9,3,1]`、`[1,0,11,4,1]`。
2. `v81 vs v69` 负例（seed=`20267433`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_093220/20260305_094527_p0-cpp_v69_overlay_followup_prune_p1-cpp_v81_overlay_deficit_late_release_seed-20267433_rounds-180.jsonl`
   - turning point：round `130`，`impact_score=331`（`delta_army_lead_p0=327`）。
   - 该回合动作：`P0 [1,1,9,2,3]`、`[1,7,9,1,1]`；`P1 [1,2,10,3,2]`。
3. `v81 vs v70` 胜例（seed=`20266423`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_093220/20260305_094345_p0-cpp_v70_overlay_opening_subpressure_p1-cpp_v81_overlay_deficit_late_release_seed-20266423_rounds-180.jsonl`
   - turning point：round `143`，`impact_score=192`（`delta_army_lead_p0=-192`）。
   - 该回合动作：`P0 [4,18,2,13,10]`；`P1 [1,1,3,3,1]`、`[1,4,0,1,1]`。
4. `v81 vs v72` 负例（seed=`20264455`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_093220/20260305_094043_p0-cpp_v81_overlay_deficit_late_release_p1-cpp_v72_overlay_endgame_lock_seed-20264455_rounds-180.jsonl`
   - turning point：round `156`，`impact_score=473`（`delta_army_lead_p0=-469`）。
   - 该回合动作：`P0 [1,6,6,1,1]`；`P1 [7,6,8]`、`[1,6,10,1,1]`。
5. `v81 vs v80` 胜例（seed=`20261343`）：
   - `/www/autolab/runtime/scopes/iter/replays/eval_20260305_093220/20260305_093323_p0-cpp_v80_overlay_release_time_decay_p1-cpp_v81_overlay_deficit_late_release_seed-20261343_rounds-180.jsonl`
   - turning point：round `148`，`impact_score=421`（`delta_army_lead_p0=421`）。
   - 该回合动作：`P0 [1,5,2,3,1]`；`P1 [4,18,2,8,2]`、`[1,10,7,1,1]`。

replay 结论：

1. `v81` 对当前 champion `v69` 提升到 `55/100`，目标对位方向生效；
2. 但 `v72` 对位显著回退（`39/100`），说明“落后态底线释放”对旧终盘锁定型对手副作用明显；
3. 波动上界仍高（`1062`），稳定性问题仍未收敛。

### 110.5 借鉴点是否生效（本轮证据）

1. Generals 借鉴点（连续 threat/impact 主干）：
   - 证据：仍使用单连续 `reserve_signal`，不新增状态机；
   - 结果：`v81-v80=56/100`，对 `v69/v70` 为 `55/54`；
   - 判定：`生效`。
2. ANTWar 借鉴点（global_state/reserved）：
   - 证据：后期衰减 + 落后底线释放（`release_window`）直接作用预算；
   - 结果：修复了 `v69` 对位（相较 `v80` 的 `51/100` 到 `55/100`），但 `v72` 出现 `39/100`；
   - 判定：`部分生效（有明显副作用）`。

### 110.6 回到生产口径的结论

1. 生产唯一权威在回合末为 `eval_20260305_092917`，champion=`cpp_v79_overlay_risk_weighted_release`（由 `v69 -> v79` 切换）；
2. 本轮已覆盖对当前 champion 的 `>=100` h2h gate：`v81-v79=54/100`；
3. 同轮也覆盖了上一任 champion `v69`（`v81-v69=55/100`）与 `v72`（`v81-v72=39/100`）；
4. 由于对 `v72` 明显负差且关键对位尚未 `>=200` confirm，本轮仅可作为候选筛选信号；
5. 本轮结论标签维持：`neutral`。

### 110.7 风险、下一步与回合末自检

风险：

1. `v81-v72=39/100` 为当前主要阻断；
2. replay `largest_army_swing=1062`，高波动问题仍在；
3. 本轮内生产 champion 连续切换（`v72 -> v69 -> v79`），gauntlet 口径存在高敏感风险。

下一步：

1. 按 confirm 路径补样：`v81 vs v69/v70/v72/v80` 各 `+100`（累计 `>=200`）；
2. 若 `v72` 持续弱势，优先减法修正：仅对“ahead+late”场景压低 `late_release_floor`，避免全面回滚；
3. 推进将 `hard_cutoff_hit` 计数写入评测产物，完成 CPU 截止可观测闭环。

回合末自检：

1. 本轮是否触发搜索时间硬截止：
   - 代码仍具备 `CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + fallback；
   - 评测产物未导出 `hard_cutoff_hit` 次数，触发频率暂不可观测。
2. 是否存在超过 `200ms` 的单步 CPU 风险点：
   - 风险点仍在 overlay 的 `enemy_best/my_follow` 重复评估链。
3. 若有风险，下一轮如何降复杂度/改进剪枝：
   - 继续收紧 follow-up 触发面并保持单闸门结构；
   - 优先补齐截止计数，再按热点回放定向减枝。

### 110.8 回合末口径刷新（生产 latest 复读）

1. 回合收尾复读生产 `latest.json`：tag 已推进到 `eval_20260305_092917`；
2. `champion.old/new` 进一步切换为 `cpp_v69_overlay_followup_prune -> cpp_v79_overlay_risk_weighted_release`（`promoted=true`）；
3. `config.pairs=45`，old/new 在 pairs 中暴露 `5/6`，再次确认 gauntlet 对手池受 champion 切换影响（高优先级风险）；
4. 针对“当前最新 champion=`v79`”的本轮 h2h gate 结果：`v81-v79=54/100`（`>=100`，但未达 `>55%`）；
5. 因本轮内生产口径发生连续切换（`v72->v69->v79`），本回合结论维持 `neutral`，并继续按 confirm 样本推进。
