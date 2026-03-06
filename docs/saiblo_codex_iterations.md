# Saiblo Codex Iterations

该文档记录 Saiblo 专用定时 codex 会话的每轮动作与证据。

## 2026-03-04 初始化

- 建立独立定时脚本：`/www/scripts/codex_saiblo_iterate_once.sh`
- 建立独立提示词与固定目标：
  - `/www/docs/codex_saiblo_iteration_prompt.md`
  - `/www/docs/codex_saiblo_objective_fixed.md`
- 与主迭代脚本共享全局互斥锁：`/tmp/codex-automation-global.lock`
- 计划调度频率：每 15 分钟 1 次
- 原则：优先 replay 分析、谨慎迭代、最多 10 局 Saiblo 对战/轮

## 2026-03-04 定时心跳回合（analysis-round）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：当前环境无法解析 `api.saiblo.net`（`entities`/`ladders` 请求均 DNS 失败），不具备可靠在线对战条件。
- 下轮触发条件：网络恢复后，优先执行 `test-round`，沿用 `cpp_v1_current` 实体，选择分数接近/更强对手并开启 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按要求读取上下文：
   - 生产 Elo：`/www/autolab/runtime/latest.json`
   - 历史记录：`/www/docs/saiblo_codex_iterations.md`
   - 最新回放：`/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/`
2. 深入解析 `match_*.json` 的 `stdinRecords`，回灌复现 `cpp_v1_current` 行为。
3. 识别算法级缺陷并修复：
   - 棋盘维度从 `15x15` 改为 `19x19`
   - seat 绑定到 `km` 握手，不再由帧内 `Player` 覆盖
4. 修复文件：
   - `/www/ai_cpp/v66/ai_v66.cpp`
   - `/www/ai_cpp/saiblo_upload/cpp_v1_current.cpp`
5. 本地验证：编译 + 10 场回放双流回灌（旧版 vs 修复版）。

### 证据

- 最近 Saiblo 10 局：`seat=0 -> 4/5`，`seat=1 -> 0/5`。
- 输入协议证据（以 `match_7413436` 为例）：
  - `Cell_type` 长度 `361`，即 `19x19`
  - `Cells` 坐标范围 `0..18`
- 回灌统计（10 场 * 2 流）：
  - 旧版“全程无非结束操作”流：`7/20`
  - 修复后：`0/20`

### 结论

- 主要问题是状态空间维度错误（15x15 截断 19x19 输入），导致决策链在部分流上退化为空过。
- 修复后在同批输入流上已消除空过流，属于高置信结构性修复。
- 本轮新增回放分析文档：`/www/docs/replay_analysis/saiblo_board19_hotfix_20260304.md`

### 风险

- 仍为静态 `19x19`，未来若地图规格变动仍有风险；建议改为动态推导维度。
- 本轮未做在线 Saiblo 对战，真实胜率收益待网络恢复后验证。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（网络不可达）。
- 预算使用：`0/10`。

### 200ms 风险点

- 未新增搜索层级，仍保留 `200ms` 单步硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

## 2026-03-04 定时心跳回合（analysis-round，dynamic-bounds）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`api.saiblo.net` 仍 DNS 失败（`entities/ladders` 无法访问）。
- 下轮触发条件：网络恢复后立即执行 `test-round`，沿用 `cpp_v1_current`，按“接近或更强”对手策略，`--swap` 且总局数 `<=10`。

### 本轮动作

1. 重新读取固定目标、生产 Elo、历史迭代与 `saiblo_*` 回放分析。
2. 在线状态检查：
   - `python3 /www/saiblo_tools.py entities --game-id 48` 失败（DNS）
   - `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 失败（DNS）
3. 继续上轮改进，完成动态边界稳健化：
   - 运行时边界 `gActiveRows/gActiveCols`
   - `State.board_rows/board_cols`
   - `parse_state_from_rep` 按 `Cell_type/Cells/Generals/Weapons` 推断有效边界
   - 非活动区域隔离（`owner=-2`）
4. 修改文件：
   - `/www/ai_cpp/v66/ai_v66.cpp`
   - `/www/ai_cpp/saiblo_upload/cpp_v1_current.cpp`
5. 本地验证：编译 + Saiblo 历史回灌 + 15x15 合成边界检查。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`）当前前二：
  - `cpp_v66_generals_weapon_econ`：`1906.31`
  - `cpp_v64_generals_rebuild`：`1906.06`
- 回灌（10 场 * 2 输入流）对比旧版：
  - 旧版 `zero_non_end_streams=7`
  - 新版 `zero_non_end_streams=0`
- 15x15 合成输入：输出动作坐标均在 `0..14`，无越界。

### 结论

- 在上轮 19x19 修复基础上，本轮进一步移除“固定维度假设”风险。
- 当前版本对历史 Saiblo 输入更稳健，且未引入额外时限风险。
- 新增回放分析：`/www/docs/replay_analysis/saiblo_dynamic_bounds_guard_20260304.md`

### 风险

- 仍未完成在线实战验证，真实性能收益待网络恢复后确认。
- 若未来出现非方形地图，需要再扩展维度推断与索引映射逻辑。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（网络不可达，避免浪费预算）。
- 预算使用：`0/10`。

### 200ms 风险点

- 未引入新的搜索/前瞻层级。
- 保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

## 2026-03-04 定时心跳回合（analysis-round，turn-fastpath）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败，在线链路不可用。
- 下轮触发条件：网络恢复后立即转 `test-round`，沿用 `cpp_v1_current`，对手优先选分数接近/更强并启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程读取并核对：
   - 固定目标：`/www/docs/codex_saiblo_objective_fixed.md`
   - 生产 Elo：`/www/autolab/runtime/latest.json`
   - Saiblo 在线状态：`entities/ladders`（均 DNS 失败）
   - 历史记录与最新 `saiblo_*` 分析文档
   - 历史 AI：`Generals-AI`、`ANTWar-AI`
2. 识别算法级可改进点：非我方回合约占 50%，但此前仍先做完整 `json::parse` 后才丢弃，浪费 CPU 预算。
3. 在两个目标文件落地低风险优化：
   - `/www/ai_cpp/v66/ai_v66.cpp`
   - `/www/ai_cpp/saiblo_upload/cpp_v1_current.cpp`
   - 新增 `extract_turn_fast`，先做 `Turn` 快速提取；确定非我方回合时直接跳过重解析。
   - 保留原 `json::parse` + `turn != seat` 判定作为兜底，不改变决策语义。
4. 本地验证：编译 + 10 场 Saiblo 回放双流回灌 + 输出一致性抽检。
5. 产出回放分析：`/www/docs/replay_analysis/saiblo_turn_fastpath_guard_20260304.md`

### 证据

- 生产 Elo（`latest.json`）当前前二：
  - `cpp_v64_generals_rebuild`: `1881.12`
  - `cpp_v66_generals_weapon_econ`: `1862.96`
- 回放统计（10 场 * 2 流）：`json_lines=8312`，`Turn=0/1` 各 `4156`。
- 回灌对比（基线 vs turn-fastpath）：
  - `zero_non_end_streams`: `0 -> 0`
  - `total_non_end`: `14354 -> 14354`
  - `elapsed_sec`: `77.726 -> 65.526`（约 `+15.7%` 速度收益）
- 一致性抽检（2 场 4 流）：
  - `ai_v66_turnfast`、`cpp_v1_current_turnfast` 与 `ai_v66_dynfix` 输出哈希逐流一致。

### 结论

- 本轮改动属于结构性性能修复：减少非我方回合的无效解析，给 `<=200ms` 决策窗口释放预算。
- 在同批回放上行为指标保持一致，暂无策略回归迹象。

### 风险

- 仍缺在线实战验证，收益是否转化为 Elo/胜率需网络恢复后确认。
- fast-path 基于字符串模式提取 `Turn`，若协议键名/格式发生变化会自动退回原 JSON 路径，但性能收益会下降。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（在线 API 不可达），避免无效预算消耗。
- 预算使用：`0/10`。

### 200ms 风险点

- 未新增搜索深度或前瞻层级。
- 继续保持 `200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，优先验证 `turn-fastpath` 对高压对局的时限收益。
2. 在回放分析脚本中补充“fast-path 命中率/截止触发次数”自动指标。

## 2026-03-04 定时心跳回合（analysis-round，forced-kill-distance-gate）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败，在线对战链路不可用。
- 下轮触发条件：网络恢复后立即执行 `test-round`；候选实体维持 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按固定流程重读上下文：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - `entities/ladders`（在线检查）
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - `Generals-AI` 与 `ANTWar-AI` 历史代码
2. 识别算法级问题：`search_forced_main_kill_sequence` 在大量“步数必然不可达”的回合仍启动 beam 搜索。
3. 完成代码改进（两文件同步）：
   - `/www/ai_cpp/v66/ai_v66.cpp`
   - `/www/ai_cpp/saiblo_upload/cpp_v1_current.cpp`
   - 新增 `may_force_main_kill_in_budget`，在 forced-kill 搜索入口做不可达早退。
4. 本地验证：编译 + 10 场双流回灌 + 哈希一致性校验。
5. 产出分析文档：`/www/docs/replay_analysis/saiblo_forced_kill_distance_gate_20260304.md`

### 证据

- 生产 Elo（`eval_20260304_180902`）当前前二：
  - `cpp_v64_generals_rebuild`: `1861.58`
  - `cpp_v66_generals_weapon_econ`: `1824.98`
- 回放统计（10 场 * 2 流）：
  - 我方回合帧 `4156`
  - forced-kill 不可达帧 `3492`
  - 不可达占比 `84.02%`
- 回灌对比（基线 `/tmp/ai_v66_turnfast` vs 新版 `/tmp/ai_v66_killgate`）：
  - `zero_non_end_streams`: `0 -> 0`
  - `total_non_end`: `14354 -> 14354`
  - `total_frames`: `4156 -> 4156`
  - 输出哈希逐流一致：`True`
  - 耗时：`24.976s -> 15.242s`（`-38.97%`）
- 上传版一致性：`/tmp/cpp_v1_current_killgate` 与 `/tmp/ai_v66_killgate` 在抽检流哈希一致。

### 结论

- 本轮改动是“搜索触发条件收敛”的结构优化：在明确不可达时不进入 beam 搜索。
- 行为保持一致（哈希同构），并显著降低回灌耗时，预计可改善 200ms 预算可用性。

### 风险

- 仍缺线上实战验证，暂无法确认 Elo/胜率实际收益。
- 早退条件基于曼哈顿下界；若未来引入跨格位移机制，需要同步更新可达性判定。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（在线 API 不可达），避免无效预算消耗。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索层级，未引入新的前瞻深度。
- 保持单步 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，优先验证该 early-gate 对线上强对手局的时限收益与胜率变化。
2. 将 `forced_kill_gate_hit_rate` 与 `deadline_reached_count` 纳入自动回灌报告，形成上传前门槛。

## 2026-03-04 定时心跳回合（analysis-round，active-bounds-ablation）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`entities` 与 `ladders` API 仍因 `api.saiblo.net` DNS 失败不可达，无法执行可靠在线对战。
- 下轮触发条件：网络恢复后切换 `test-round`，沿用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - `python3 /www/saiblo_tools.py entities --game-id 48`
   - `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - `Generals-AI` 与 `ANTWar-AI` 历史代码
2. 进行一次算法结构 ablation：尝试将部分热点循环切换到 `board_rows/board_cols`（active-bounds loop）。
3. 实验验证发现行为偏移 + 性能退化后，立即回滚该改动，恢复稳定基线。
4. 编译并复验回滚版本（本地版与上传版）。
5. 新增分析文档：`/www/docs/replay_analysis/saiblo_active_bounds_loop_ablation_20260304.md`。

### 证据

- 生产 Elo（`eval_20260304_182936`）当前前二：
  - `cpp_v64_generals_rebuild`: `1923.83`
  - `cpp_v66_generals_weapon_econ`: `1908.87`
- ablation 首轮（`killgate` vs `activebounds`，10 场*2 流）：
  - `hash_equal_all=False`
  - `total_non_end: 14354 -> 14351`
  - `elapsed_sec: 33.015 -> 40.259`
- 回滚后复验（`killgate` vs `postrollback`，10 场*2 流）：
  - `hash_equal_all=True`
  - `zero_non_end_streams: 0 -> 0`
  - `total_non_end: 14354 -> 14354`
  - `total_frames: 4156 -> 4156`
- 上传版一致性抽检（2 场 4 流）：
  - `/tmp/ai_v66_postrollback` 与 `/tmp/cpp_v1_current_postrollback` 输出哈希一致。

### 结论

- active-bounds 循环改动在当前实现中不稳定，已拒绝并回滚。
- 本轮最终保留策略为“稳定优先”：维持已验证有效的 `turn-fastpath + forced-kill-distance-gate` 基线。

### 风险

- 在线链路未恢复，尚不能验证本地优化对真实 Elo 的增益。
- 当前实现在部分评估环节仍对固定遍历语义较敏感，后续重构需分阶段并配套更细粒度指标。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 本轮进行了性能 ablation，但未采纳退化改动。
- 保持 `<=200ms` 硬截止 + 回退路径；本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，优先对强/近分对手验证当前稳定基线收益。
2. 在本地回灌管线中补充 `deadline_reached_count`、候选池规模等指标，再重试边界循环类优化。

## 2026-03-04 定时心跳回合（analysis-round，skill-kill-secondpass-gate-ablation）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `ladders --game-id 48 --limit 30` 仍因 `api.saiblo.net` DNS 失败无法访问。
- 下轮触发条件：网络恢复后执行 `test-round`，沿用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 重新读取并核对：
   - 固定目标：`/www/docs/codex_saiblo_objective_fixed.md`
   - 生产 Elo：`/www/autolab/runtime/latest.json`
   - 在线状态：`entities/ladders`
   - 历史迭代：`/www/docs/saiblo_codex_iterations.md`
   - 最新回放分析：`/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`Generals-AI`、`ANTWar-AI`
2. 开展算法实验：对“技能后第二次斩首搜索”增加门控（仅进攻技能后触发）。
3. 完成本地编译与回灌 A/B（10 场*2 流）。
4. 发现行为漂移迹象后，回滚该实验改动，恢复稳定基线。
5. 补充回放分析：`/www/docs/replay_analysis/saiblo_skill_kill_secondpass_gate_ablation_20260304.md`。

### 证据

- 生产 Elo（`eval_20260304_182936`）当前前二：
  - `cpp_v64_generals_rebuild`: `1923.83`
  - `cpp_v66_generals_weapon_econ`: `1908.87`
- 单次 A/B 回灌（10 场*2 流）：
  - 基线：`zero_non_end_streams=0`，`total_non_end=14354`，`elapsed=21.636s`
  - 实验：`zero_non_end_streams=0`，`total_non_end=14354`，`elapsed=20.124s`
  - 输出哈希存在差异（行为漂移）。
- 非确定性确认（同一二进制重复回灌，5 场*2 流）：
  - `diff_cnt=1`，`non_end=7775/7777`
- 回滚后上传版一致性抽检（2 场 4 流）：
  - `/tmp/ai_v66_after_offskill_rollback` 与 `/tmp/cpp_v1_current_after_offskill_rollback` 输出哈希一致。

### 结论

- 该门控有潜在提速，但在当前 deadline 驱动路径下引入可观测行为漂移。
- 在无法在线实战验证收益时，按最小风险原则不采纳，已回滚。
- 当前保持稳定基线：`turn-fastpath + forced-kill-distance-gate`。

### 风险

- 在线链路不可用，无法进行强对手真实胜率验证。
- deadline 引入轻微运行间噪声，后续评估需采用多次统计而非单次哈希。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免浪费对战预算。
- 预算使用：`0/10`。

### 200ms 风险点

- 未引入新的搜索层级，仍保留 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点（实验改动已回滚）。

### 下一步

1. 网络恢复后执行 `test-round`，优先对近分/更强对手验证当前稳定基线。
2. 在本地回灌验证中加入多次重复统计（均值/方差）再评估小幅性能门控。

## 2026-03-04 定时心跳回合（analysis-round，stability-harness）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `ladders --game-id 48 --limit 30` 仍因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后执行 `test-round`，沿用 `cpp_v1_current`，优先分数接近/更强对手，开启 `--swap`，总局数 `<=10`。

### 本轮动作

1. 依流程重读并核对：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo 在线状态：`entities/ladders`
   - 历史记录：`/www/docs/saiblo_codex_iterations.md`
   - 最新分析：`/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`Generals-AI`、`ANTWar-AI`
2. 识别本轮算法级痛点：deadline 驱动下，单次回灌哈希易受运行噪声影响，实验结论不稳。
3. 完成代码改进（验证链路）：
   - 新增脚本：`/www/scripts/saiblo_replay_stability_check.py`
   - 能力：多次回灌稳定性统计 + 可选二进制对比（哈希差异、`non_end` 差异、耗时分布）。
4. 本地验证：
   - 5 场*2 流，3 次重复稳定性检查
   - 本地版与上传版单次对比检查
5. 产出分析文档：
   - `/www/docs/replay_analysis/saiblo_stability_harness_20260304.md`
   - JSON 结果：
     - `/www/docs/replay_analysis/saiblo_stability_harness_run_20260304.json`
     - `/www/docs/replay_analysis/saiblo_stability_harness_compare_20260304.json`

### 证据

- 生产 Elo（`eval_20260304_191239`）当前前二：
  - `cpp_v64_generals_rebuild`: `1819.70`
  - `cpp_v66_generals_weapon_econ`: `1814.21`
- 重复稳定性（5 场*2 流，3 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777,7777]`
  - `frame_totals=[2206,2206,2206]`
  - 耗时分布 `11.84s~16.14s`
- 二进制对比（本地版 vs 上传版，5 场*2 流）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`

### 结论

- 本轮有效提升了离线验证可靠性，避免“单次哈希噪声”导致误判推进。
- 当前建议将稳定性脚本作为上传前硬门槛之一。

### 风险

- 在线链路未恢复，仍无法将离线稳定性直接映射到线上胜率。
- 脚本只能降低误判风险，不能替代在线强对手实战证据。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮未改动搜索/前瞻策略。
- `<=200ms` 硬截止 + 回退保持不变。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，并将稳定性脚本结果与线上胜率联合判定是否上传。
2. 设定上传前阈值：`unstable_rate` 与 `non_end` 波动必须低于门槛。

## 2026-03-04 定时心跳回合（analysis-round，deterministic-tiebreak）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选沿用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/`
2. 算法级改进（低风险）：在候选与 beam 节点排序中加入确定性 tie-break，降低同分截断抖动。
   - `ai_cpp/v66/ai_v66.cpp`
   - `ai_cpp/saiblo_upload/cpp_v1_current.cpp`
3. 本地验证：
   - 编译新二进制：`/tmp/ai_v66_tiebreak`、`/tmp/cpp_v1_current_tiebreak`
   - 重复稳定性 + 基线对比 + 上传版一致性对比（脚本 `/www/scripts/saiblo_replay_stability_check.py`）
4. 新增分析文档：`/www/docs/replay_analysis/saiblo_deterministic_tiebreak_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_193618`）前二：
  - `cpp_v64_generals_rebuild`: `1959.28`
  - `cpp_v66_generals_weapon_econ`: `1915.10`
- 新版本稳定性（5 场*2 流，3 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777,7777]`
  - `frame_totals=[2206,2206,2206]`
- 基线 vs 新版本（单次 compare）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
- 本地版 vs 上传版（3 场*2 流）：
  - `hash_diff_streams=0/6`
  - `non_end_delta=0`
  - `frame_delta=0`

### 结论

- 本轮改动在当前样本上保持行为等价，验证链路稳定。
- 该改动属于“确定性降噪”与可复现性增强，风险低，可作为后续在线测试前的稳态基础。
- 因在线 API 不可达，暂不宣称 Elo/胜率收益。

### 与历史 AI 机制映射

- `Generals-AI`：借鉴其分阶段时间阈值与硬截止思想（`MAX_T*`），本轮在不改变截止逻辑前提下增加同分稳定决策。
- `ANTWar-AI`：借鉴其 `TIME1 + MAX_NODE_COUNT` 预算约束下的搜索治理，本轮针对预算截断边界引入稳定 tie-break，降低偶然分支漂移。

### 风险

- 未进行在线实战，仍缺“强/近分对手”胜率证据。
- 同分 tie-break 可能在极少数局改变边界分支选择，需线上小批量验证最终收益。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，优先选择榜单中分数接近或更强对手，`--swap`，总局数 `<=10`。
2. 若线上样本显示稳定且不降胜率，再将该稳定排序作为默认基线并继续推进更高收益策略改进。

## 2026-03-04 定时心跳回合（analysis-round，candidate-dedup）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 算法级改进：在候选汇总函数 `push_candidate` 引入“同动作去重 + 保留更高分”，降低 deadline 截断下重复动作挤占候选池的问题。
   - `/www/ai_cpp/v66/ai_v66.cpp`
   - `/www/ai_cpp/saiblo_upload/cpp_v1_current.cpp`
3. 本地验证：
   - 编译 `/tmp/ai_v66_dedup` 与 `/tmp/cpp_v1_current_dedup`
   - 重复稳定性、基线对比、本地版/上传版一致性复测
4. 产出分析文档：`/www/docs/replay_analysis/saiblo_candidate_dedup_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_195549`）前二：
  - `cpp_v64_generals_rebuild`: `1960.63`
  - `cpp_v66_generals_weapon_econ`: `1915.67`
- 新版本稳定性（5 场*2 流，3 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777,7777]`
  - `frame_totals=[2206,2206,2206]`
- 基线 `tiebreak` vs 新版本 `dedup`：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
- 本地版 vs 上传版：
  - 首次 3 场样本出现 `hash_diff_streams=1/6`、`non_end_delta=-2`
  - 追加 4 次复测（含 5 场样本）均为 `hash_diff_streams=0`、`non_end_delta=0`

### 结论

- 候选去重改动在当前样本下保持行为等价且稳定，属于低风险结构简化。
- 首次上传一致性对比的单点偏差经复测未复现，判断为 deadline 临界噪声。
- 在线链路不可用，暂不宣称 Elo/胜率收益。

### 与历史 AI 机制映射

- `Generals-AI`：借鉴其在 `best_dfs` 中用 `mindist` 抑制冗余扩展，本轮在候选层做去重以提升有效分支密度。
- `ANTWar-AI`：借鉴其 `TIME1 + MAX_NODE_COUNT` 预算化搜索治理，本轮通过减少重复候选提升预算利用率。

### 风险

- 未进行在线实战，缺少强/近分对手真实胜率证据。
- 去重可能在极个别同分冲突局改变边界分支，仍需线上小样本确认。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，对近分/更强对手做 `<=10` 局 `--swap` 验证。
2. 若线上验证稳定，再将候选去重并入基线后继续推进更高收益策略改进。

## 2026-03-04 定时心跳回合（analysis-round，kill-arc-dedup）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 算法级改进：在 kill-only 候选收集末尾做“按攻击弧去重（`sx,sy,dir`）”，每弧仅保留最高分候选。
   - `/www/ai_cpp/v66/ai_v66.cpp`
   - `/www/ai_cpp/saiblo_upload/cpp_v1_current.cpp`
3. 本地验证：
   - 编译 `/tmp/ai_v66_arcdedup` 与 `/tmp/cpp_v1_current_arcdedup`
   - 进行重复稳定性、基线对比、本地版/上传版一致性验证
4. 新增分析文档：`/www/docs/replay_analysis/saiblo_kill_arc_dedup_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_195549`）前二：
  - `cpp_v64_generals_rebuild`: `1960.63`
  - `cpp_v66_generals_weapon_econ`: `1915.67`
- 新版本稳定性（5 场*2 流，3 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777,7777]`
  - `frame_totals=[2206,2206,2206]`
- 基线 `dedup` vs 新版本 `arcdedup`：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
- 本地版 vs 上传版（`arcdedup`）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`

### 结论

- kill-arc 去重在当前样本上保持行为等价且验证稳定。
- 该改动属于低风险结构简化，目标是减少斩首分支的候选冗余并提升预算利用率。
- 在线链路不可用，暂不宣称 Elo/胜率收益。

### 与历史 AI 机制映射

- `Generals-AI`：借鉴其 `best_dfs` 的分支去冗余（`mindist`）思想，本轮保留每条攻击弧的最优候选。
- `ANTWar-AI`：借鉴其 `TIME1 + MAX_NODE_COUNT` 预算化搜索治理，本轮通过去冗余提升预算内有效分支比例。

### 风险

- 未进行在线实战，缺少强/近分对手真实胜率证据。
- 弧级去重可能在个别局面削弱“同弧不同兵力”的精细调节能力，需线上样本验证。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，对近分/更强对手做 `<=10` 局 `--swap` 验证。
2. 若线上稳定，再继续 kill-search 侧的低风险去冗余改进。

## 2026-03-04 定时心跳回合（analysis-round，kill-arc-fastpath）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 算法级改进：将 kill-only 候选的弧去重实现从 `O(n^2)` 顺序查重替换为 `seen_arc[sx][sy][dir]` 标记（`O(n)`）。
   - `/www/ai_cpp/v66/ai_v66.cpp`
   - `/www/ai_cpp/saiblo_upload/cpp_v1_current.cpp`
3. 本地验证：
   - 编译 `/tmp/ai_v66_arcdedup_fast` 与 `/tmp/cpp_v1_current_arcdedup_fast`
   - 重复稳定性、与 `arcdedup` 基线对比、本地版/上传版一致性验证
4. 新增分析文档：`/www/docs/replay_analysis/saiblo_kill_arc_fastpath_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_203650`）前二：
  - `cpp_v66_generals_weapon_econ`: `1951.00`
  - `cpp_v64_generals_rebuild`: `1945.18`
- 新版本稳定性（5 场*2 流，3 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777,7777]`
  - `frame_totals=[2206,2206,2206]`
- 基线 `arcdedup` vs 新版本 `arcdedup_fast`：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
- 本地版 vs 上传版（`arcdedup_fast`）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`

### 结论

- 本轮改动在当前样本上保持行为等价且稳定。
- 该改动属于等价实现优化，降低 kill-arc 去重开销，风险低。
- 在线链路不可用，暂不宣称 Elo/胜率收益。

### 与历史 AI 机制映射

- `Generals-AI`：借鉴其在时限内优先保留有效分支的思想，本轮减少去重阶段冗余计算。
- `ANTWar-AI`：借鉴其 `TIME1 + MAX_NODE_COUNT` 预算化扩展治理，本轮将预算从重复查重转向有效节点扩展。

### 风险

- 未进行在线实战，缺少强/近分对手真实胜率证据。
- 该优化理论上等价，但仍需线上小样本确认无边缘回归。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，对近分/更强对手做 `<=10` 局 `--swap` 验证。
2. 若线上稳定，继续推进等价实现优化，避免策略语义漂移。

## 2026-03-04 定时心跳回合（analysis-round，kill-reach-prune-ablation）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 进行算法 ablation：在 `search_forced_main_kill_sequence` 尝试加入“剩余步数可达性剪枝”（节点级+落子后级）。
3. 完成本地验证（稳定性、与上轮基线对比、本地版/上传版一致性）。
4. 发现行为漂移后拒绝该实验，并将变更回滚到本轮实验前的函数形态。
5. 新增分析文档：`/www/docs/replay_analysis/saiblo_kill_reach_prune_ablation_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_205431`）前二：
  - `cpp_v64_generals_rebuild`: `1932.06`
  - `cpp_v66_generals_weapon_econ`: `1895.20`
- 实验版稳定性（5 场*2 流，3 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7706,7706,7706]`
  - `frame_totals=[2206,2206,2206]`
- 基线 `arcdedup_fast` vs 实验版 `killreach`：
  - `hash_diff_streams=3/10`
  - `non_end_delta=-71`
  - `frame_delta=0`
- 实验版本地版 vs 上传版：
  - `hash_diff_streams=3/10`
  - `non_end_delta=+71`
  - `frame_delta=0`

### 结论

- 该剪枝不是纯等价优化，已引起可观测行为漂移。
- 在在线链路不可用且缺少强对手收益证据时，按最小风险原则不采纳。
- 本轮定位为“ablation 拒绝回合”，不上传、不替换线上候选。

### 与历史 AI 机制映射

- `Generals-AI`：借鉴其 `steps < dist` 的可达性剪枝思想进行实验。
- `ANTWar-AI`：借鉴其 `TIME1 + MAX_NODE_COUNT` 预算治理思想进行节点裁剪。

### 风险

- 在线链路不可达，无法验证行为改变是否带来真实胜率提升。
- 该类可达性剪枝在 kill-beam 上有策略语义风险，后续需更严格 A/B 门槛。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点（仅触发行为漂移风险）。

### 下一步

1. 网络恢复后执行 `test-round`，继续采用 `cpp_v1_current`，对近分/更强对手做 `<=10` 局 `--swap` 验证。
2. 下一轮优先做“严格等价”实现优化，避免策略语义级剪枝变更。

## 2026-03-04 定时心跳回合（analysis-round，drift-diagnostic-tooling）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 识别验证链路缺陷：仅有总量指标，无法定位具体漂移流，导致 ablation 排查成本高。
3. 代码改进（工具链）：增强 `/www/scripts/saiblo_replay_stability_check.py` 的 compare 输出，新增差异流索引和按流 delta 列表。
4. 本地验证：
   - `killreach_rollback` vs upload
   - `arcdedup_fast` vs `killreach_rollback`
   - 验证新增字段与总量指标一致。
5. 新增分析文档：`/www/docs/replay_analysis/saiblo_drift_diagnostic_tooling_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_213954`）前二：
  - `cpp_v64_generals_rebuild`: `1923.74`
  - `cpp_v66_generals_weapon_econ`: `1916.96`
- 漂移定位（`killreach_rollback` vs upload）：
  - `hash_diff_streams=3/10`
  - `hash_diff_indices=[0,4,6]`
  - `non_end_delta=+71`
  - 按流差异：`stream6(+35)`, `stream4(+32)`, `stream0(+4)`
- 基线对比（`arcdedup_fast` vs `killreach_rollback`）：
  - `hash_diff_streams=3/10`
  - `hash_diff_indices=[0,4,6]`
  - `non_end_delta=-71`

### 结论

- 本轮交付为“诊断能力增强”，不改 AI 行为，风险低。
- 新增按流差异指标后，后续 ablation 可更快定位问题来源。
- 在线链路不可用，暂不进行上传和对战。

### 与历史 AI 机制映射

- `Generals-AI`：映射其搜索分支可观测性（日志化）思想到回放验证链路。
- `ANTWar-AI`：映射其预算化搜索统计思想到按流差异统计。

### 风险

- 未进行在线实战，仍缺近分/强对手胜率证据。
- 工具增强不能替代策略正确性，需要继续与线上对局证据联合判定。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮未改动搜索或前瞻策略。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，优先近分/更强对手，`<=10` 局并启用 `--swap`。
2. 后续策略实验统一使用“按流漂移定位”作为采纳前门槛之一。

## 2026-03-04 定时心跳回合（analysis-round，drift-diagnostic-meta-tooling）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 识别验证链路缺陷：差异流只能定位到 stream index，无法直接映射到 replay 文件与 `stdinRecords` 序号。
3. 代码改进（工具链）：增强 `/www/scripts/saiblo_replay_stability_check.py`：
   - `decode_streams` 返回 `StreamMeta(match_file, match_id, stdin_index)`
   - compare 输出新增 `hash_diff_details`，并在按流 delta 中附带元信息。
4. 本地验证：
   - `killreach_rollback` vs `cpp_v1_current_killreach_rollback`
   - `arcdedup_fast` vs `killreach_rollback`
   - 验证元信息映射正确。
5. 新增分析文档：`/www/docs/replay_analysis/saiblo_drift_diagnostic_meta_tooling_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_213954`）前二：
  - `cpp_v64_generals_rebuild`: `1923.74`
  - `cpp_v66_generals_weapon_econ`: `1916.96`
- 漂移定位（`killreach_rollback` vs upload）：
  - `hash_diff_streams=3/10`
  - `hash_diff_indices=[0,4,6]`
  - `hash_diff_details` 映射为：
    - `match_7413435.json / stdin_index=0`
    - `match_7413437.json / stdin_index=0`
    - `match_7413438.json / stdin_index=0`
  - `non_end_delta=+71`
- 基线对比（`arcdedup_fast` vs `killreach_rollback`）：
  - `hash_diff_streams=3/10`
  - 同样映射为以上三路流
  - `non_end_delta=-71`

### 结论

- 本轮交付为“漂移定位能力增强”，不改 AI 行为，风险低。
- 新字段可将差异直接映射到 replay 级别，显著提升后续 ablation 调试效率。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：映射其搜索过程可观测性到“差异流-回放文件”结构化定位。
- `ANTWar-AI`：映射其预算化过程统计思想到按流元信息统计输出。

### 风险

- 未进行在线实战，仍缺近分/强对手胜率证据。
- 工具增强不能替代策略正确性，仍需线上证据闭环。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮未改动搜索或前瞻策略。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`，优先近分/更强对手，`<=10` 局并启用 `--swap`。
2. 后续策略实验统一以“差异流元信息定位 + 线上结果”双证据判定是否采纳。

## 2026-03-04 定时心跳回合（analysis-round，deterministic-trim）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 定位并修复潜在非确定性点：将 `cpp_v1_current` 中两处 `nth_element` 截断改为“排序后截断”（候选池 + kill-beam 中间层）。
3. 本地编译二进制：
   - 改动前：`/tmp/cpp_v1_current_pre_deterministic`
   - 改动后：`/tmp/cpp_v1_current_deterministic_trim`
4. 本地回放验证（5 场、10 流）：
   - 改动后 vs 改动前
   - 改动后 vs `cpp_v1_current_killreach_rollback`
   - 改动后 vs `ai_v66_killreach_rollback`
5. 新增分析文档：`/www/docs/replay_analysis/saiblo_deterministic_trim_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_215916`）前二：
  - `cpp_v66_generals_weapon_econ`: `1924.93`
  - `cpp_v64_generals_rebuild`: `1899.61`
- 稳定性（改动后，2 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777]`
  - `frame_totals=[2206,2206]`
- 行为等价（改动后 vs 改动前）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
- 与 `ai_v66_killreach_rollback` 对照：
  - `hash_diff_streams=3/10`
  - `hash_diff_indices=[0,4,6]`
  - 映射：`match_7413435/7413437/7413438` 的 `stdin_index=0`

### 结论

- 本轮改动属于“确定性收敛”而非策略变更：在当前样本上对基线行为等价、稳定性不下降。
- 在线链路不可用，无法直接验证该收敛是否提升线上一致性；但该改动风险低，可作为后续线上验证前的安全整理。

### 与历史 AI 机制映射

- `Generals-AI`：映射其并列候选固定优先级思想到“显式排序后截断”。
- `ANTWar-AI`：映射其预算化搜索思想到“保持既有 beam/node 预算，仅替换截断算子”。

### 风险

- 仍缺在线 head-to-head 证据。
- 与 `ai_v66_killreach_rollback` 的 3 路漂移仍在，说明历史分叉语义差异未完全消除。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未新增搜索深度或前瞻层。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。
2. 在现有 drift 元信息框架下，对 `[0,4,6]` 三路流继续做帧级定位，确认历史分叉来源。

## 2026-03-04 定时心跳回合（analysis-round，cutoff-fallback）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 识别并修复算法级问题：overlay 命中 deadline 时返回“部分评估 best”导致速度敏感。
3. 在 `cpp_v1_current` 中实现硬截止统一回退：`select_best_move_overlay` 若截止命中则返回 `base`。
4. 本地编译：`/tmp/cpp_v1_current_cutoff_fallback`。
5. 本地回放验证（5 场/10 流）：
   - `cutoff_fallback` vs `deterministic_trim`
   - `cutoff_fallback` vs `ai_v66_killreach_rollback`
6. 新增分析文档：`/www/docs/replay_analysis/saiblo_cutoff_fallback_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_221558`）前二：
  - `cpp_v64_generals_rebuild`: `1860.35`
  - `cpp_v66_generals_weapon_econ`: `1810.92`
- 稳定性（`cutoff_fallback`，2 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777]`
  - `frame_totals=[2206,2206]`
- 行为对照（`cutoff_fallback` vs `deterministic_trim`）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
- 与 `ai_v66_killreach_rollback` 对照：
  - `hash_diff_streams=3/10`
  - `hash_diff_indices=[0,4,6]`
  - 映射：`match_7413435/7413437/7413438` 的 `stdin_index=0`

### 结论

- 本轮改动为“超时路径确定性回退”，不改变主策略评分结构，风险低。
- 当前样本下与上轮版本行为等价，说明改动主要在硬截止语义层生效。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：映射其预算不足时回落稳定基线动作的守稳策略。
- `ANTWar-AI`：映射其 `TIME + NODE` 硬截止后固定回退思想。

### 风险

- 缺线上 head-to-head 证据，无法直接确认胜率收益。
- 历史 3 路流差异仍在，需继续做帧级定位。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。
2. 在 drift 元信息框架下继续定位 `[0,4,6]` 三路流的帧级分叉点。

## 2026-03-04 定时心跳回合（analysis-round，overlay-evalcap）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 定位算法缺陷：overlay 在高风险态会评估长尾候选，预算更多依赖 deadline 被动截断。
3. 代码改进（`cpp_v1_current`）：
   - `OverlayTuning` 增加 `eval_cap`；
   - 高风险分支按威胁源设置 `eval_cap`，并受 `pool_limit` 约束；
   - overlay 循环达到 `eval_cap` 立即停止。
4. 本地编译：`/tmp/cpp_v1_current_overlay_evalcap`。
5. 本地回放验证（5 场/10 流）：
   - `overlay_evalcap` vs `cutoff_fallback`
   - `overlay_evalcap` vs `ai_v66_killreach_rollback`
6. 新增分析文档：`/www/docs/replay_analysis/saiblo_overlay_evalcap_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_221558`）前二：
  - `cpp_v64_generals_rebuild`: `1860.35`
  - `cpp_v66_generals_weapon_econ`: `1810.92`
- 稳定性（`overlay_evalcap`，2 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777]`
  - `frame_totals=[2206,2206]`
- 行为对照（`overlay_evalcap` vs `cutoff_fallback`）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
- 与 `ai_v66_killreach_rollback` 对照：
  - `hash_diff_streams=3/10`
  - `hash_diff_indices=[0,4,6]`
  - 映射：`match_7413435/7413437/7413438` 的 `stdin_index=0`

### 结论

- 本轮改动属于“预算治理收敛”，不改变样本内策略行为，采纳风险低。
- 该改动将 overlay 的候选评估从“deadline 被动截断”前移为“显式上限截断”，有助于稳定 200ms 预算边界。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：映射其优先高价值分支、压缩低价值长尾分支的思路。
- `ANTWar-AI`：映射其 `TIME + MAX_NODE_COUNT` 双预算治理到 `pool_limit + eval_cap`。

### 风险

- 缺线上 head-to-head 证据，无法直接确认胜率收益。
- 历史 `[0,4,6]` 三路差异仍在，需继续帧级定位。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。
2. 使用现有元信息文件对 `[0,4,6]` 三路流做帧级分叉定位，继续压缩语义差异来源。

## 2026-03-04 定时心跳回合（analysis-round，overlay-basecache）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 定位算法缺陷：overlay 循环对 base 候选进行重复评估，存在固定冗余开销。
3. 代码改进（`cpp_v1_current`）：
   - 预计算并缓存 base 的 overlay 相关量（`enemy_reply`/`my_follow`/`main_threat_gain`）；
   - 直接设定 `base_overlay_score` 为初始 best；
   - 循环内跳过 `cand_is_base` 的重复计算。
4. 本地编译：`/tmp/cpp_v1_current_overlay_basecache`。
5. 本地回放验证（5 场/10 流）：
   - `overlay_basecache` vs `overlay_evalcap`
   - `overlay_basecache` vs `ai_v66_killreach_rollback`
6. 新增分析文档：`/www/docs/replay_analysis/saiblo_overlay_basecache_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_225705`）前二：
  - `cpp_v64_generals_rebuild`: `1923.81`
  - `cpp_v66_generals_weapon_econ`: `1912.31`
- 稳定性（`overlay_basecache`，2 repeats）：
  - `unstable_streams=0/10`
  - `non_end_totals=[7777,7777]`
  - `frame_totals=[2206,2206]`
- 行为对照（`overlay_basecache` vs `overlay_evalcap`）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
- 与 `ai_v66_killreach_rollback` 对照：
  - `hash_diff_streams=3/10`
  - `hash_diff_indices=[0,4,6]`
  - 映射：`match_7413435/7413437/7413438` 的 `stdin_index=0`

### 结论

- 本轮改动属于“等价重排 + 冗余消除”，样本内行为保持一致，采纳风险低。
- 改动可降低 overlay 固定开销，进一步稳固 200ms 预算边界。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：映射其“主线先验 + 分支扩展”顺序化搜索思想。
- `ANTWar-AI`：映射其预算治理思想，先消除固定冗余成本后再扩展分支。

### 风险

- 缺线上 head-to-head 证据，无法直接确认胜率收益。
- 历史 `[0,4,6]` 三路差异仍在，需继续帧级定位。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 未增加搜索深度或前瞻层级。
- 仍保持 `<=200ms` 硬截止 + 回退。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。
2. 基于现有元信息继续对 `[0,4,6]` 三路流做帧级分叉定位，减少历史语义差异。

## 2026-03-04 定时心跳回合（analysis-round，first-diff-locator）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 继续上一轮“帧级分叉定位”任务，新增工具：`/www/scripts/saiblo_replay_first_diff.py`。
3. 用新工具执行两组本地验证（stream filter=`0,4,6`）：
   - `overlay_basecache` vs `ai_v66_killreach_rollback`
   - `overlay_basecache` vs `overlay_evalcap`
4. 新增分析文档：`/www/docs/replay_analysis/saiblo_first_diff_locator_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_231915`）前二：
  - `cpp_v64_generals_rebuild`: `1936.78`
  - `cpp_v66_generals_weapon_econ`: `1921.30`
- 首个分歧定位（`overlay_basecache` vs `ai_v66_killreach_rollback`）：
  - `diff_streams=3/3`
  - stream `0`：`match_7413435.json` / `stdin_index=0` / `frame=34` / `line=2`
  - stream `4`：`match_7413437.json` / `stdin_index=0` / `frame=9` / `line=1`
  - stream `6`：`match_7413438.json` / `stdin_index=0` / `frame=11` / `line=1`
- 对照组（`overlay_basecache` vs `overlay_evalcap`）：
  - `diff_streams=0/3`

### 结论

- 本轮交付为“首个分歧帧定位能力”，将 `[0,4,6]` 从流级差异推进到帧/行级差异。
- 三路流首个分歧均呈现 `opcode=7` 行的插入/缺失模式，后续应优先围绕该动作语义排查。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：映射其关键分支可观测思想到“首个分歧帧定位”。
- `ANTWar-AI`：映射其预算化诊断思想到“只抓首个分歧，避免全量比对开销”。

### 风险

- 仍缺线上 head-to-head 证据，无法直接确认胜率影响。
- 已定位到首个分歧帧，但尚未完成 opcode 语义归因。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮未改动搜索/前瞻策略，仅增强回放分析工具。
- 既有 `<=200ms` 硬截止 + 回退未变。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 结合 opcode 语义继续定位 `[0,4,6]` 首分歧对应的策略模块。
2. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。

## 2026-03-04 定时心跳回合（analysis-round，first-diff-opcode-tagging）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 继续上一轮首分歧定位任务，增强 `saiblo_replay_first_diff.py`：
   - 增加首分歧行 `opcode` 解析与动作标签输出；
   - 增加 `diff_kind` 字段用于差异类型判定。
3. 本地验证（stream filter=`0,4,6`）：
   - `overlay_basecache` vs `ai_v66_killreach_rollback`
   - `overlay_basecache` vs `overlay_evalcap`
4. 新增分析文档：`/www/docs/replay_analysis/saiblo_first_diff_opcode_tagging_20260304.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260304_231915`）前二：
  - `cpp_v64_generals_rebuild`: `1936.78`
  - `cpp_v66_generals_weapon_econ`: `1921.30`
- 首分歧语义归因（`overlay_basecache` vs `ai_v66_killreach_rollback`）：
  - `diff_streams=3/3`
  - 三路首分歧均为：`CALL_GENERAL(7)` vs `MOVE_ARMY(1)`
  - 位置：
    - stream `0`：`match_7413435` / `frame=34` / `line=2`
    - stream `4`：`match_7413437` / `frame=9` / `line=1`
    - stream `6`：`match_7413438` / `frame=11` / `line=1`
- 对照组（`overlay_basecache` vs `overlay_evalcap`）：
  - `diff_streams=0/3`

### 结论

- 本轮将历史漂移从“流级差异”推进到“动作类型差异”：核心分歧聚焦在 `CALL_GENERAL` 触发。
- 这为后续策略修复提供明确入口（招募模块而非全局 move 搜索）。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：映射其关键动作可观测思想到 opcode 语义定位。
- `ANTWar-AI`：映射其低成本诊断思想到“首个关键动作差异”优先定位。

### 风险

- 仍缺线上 head-to-head 证据，暂不能评估胜率影响。
- 已完成动作级定位，但尚未完成触发条件级归因。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮仅增强分析工具，未改动搜索/前瞻策略。
- 既有 `<=200ms` 硬截止 + 回退不变。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 直接围绕 `CALL_GENERAL`（`choose_recruit_cell` + 招募触发条件）做可逆小步实验。
2. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。

## 2026-03-05 定时心跳回合（analysis-round，recruit-postmove-rollback）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”（优先当前高分实体附近），启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 继续上一轮实验收尾：复核 `CALL_GENERAL(7)` 分歧实验（招募后置 + danger 门控）。
3. 代码处理：回滚 `/www/ai_cpp/saiblo_upload/cpp_v1_current.cpp` 中“招募后置 + `main_danger<0.58` 门控”改动，恢复“招募在 move sweep 前”的稳定顺序。
4. 本地验证：
   - 编译：`/tmp/cpp_v1_current_recruit_rollback`
   - 回放稳定性对比：`recruit_rollback` vs `overlay_basecache`（5 场/10 流，2 repeats）
5. 新增分析文档：`/www/docs/replay_analysis/saiblo_recruit_postmove_rollback_20260305.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260305_000532`）前二：
  - `cpp_v66_generals_weapon_econ`: `1886.14`
  - `cpp_v64_generals_rebuild`: `1884.91`
- 实验版本（`/tmp/cpp_v1_current_recruit_postmove`）相对基线（`overlay_basecache`）：
  - `hash_diff_streams=4/10`
  - `hash_diff_indices=[0,2,4,6]`
  - `non_end_delta=-3`
  - 结果文件：`/www/docs/replay_analysis/saiblo_recruit_postmove_compare_20260305.json`
- 回滚版本（`/tmp/cpp_v1_current_recruit_rollback`）相对基线（`overlay_basecache`）：
  - `hash_diff_streams=0/10`
  - `non_end_delta=0`
  - `frame_delta=0`
  - 结果文件：`/www/docs/replay_analysis/saiblo_recruit_postmove_rollback_compare_20260305.json`

### 结论

- 本轮确认“招募后置 + danger 门控”会扩大行为漂移，不符合最小风险策略，已拒绝并回滚。
- 回滚后恢复与当前稳定基线等价（样本内 0/10 差异），本轮交付为“高风险实验闭环 + 稳定性恢复”。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：维持经济动作在主战术 sweep 前的固定节奏，减少动作链重排。
- `ANTWar-AI`：采用风险优先的回退策略，出现显著语义漂移即撤回改动，保持可控演进。

### 风险

- 仍缺线上 head-to-head 证据，无法验证真实胜率收益。
- `[0,4,6]` 差异根因尚未完全消除，仅完成一次高风险分支回退。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费在不可执行链路。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮未引入新的搜索/前瞻分支，仅回滚动作时序实验。
- `<=200ms` 硬截止 + 回退机制保持不变。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 在原动作时序内做“轻量招募门控”可逆实验（不再调整招募相对时序）。
2. 继续以首分歧定位脚本约束实验采纳阈值（优先 `hash_diff_streams<=1/10`）。
3. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。

## 2026-03-05 定时心跳回合（analysis-round，recruit-reservegate-ablation-reject）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 沿上轮“原时序内轻量门控”假设做可逆实验：
   - 在招募阶段引入 `reserve_gate` coin buffer（+ threat source 轻探针），不改变招募时序。
3. 本地验证：
   - `recruit_reservegate` vs `overlay_basecache`（5 场/10 流 + 10 场/20 流）
   - `recruit_reservegate` vs `ai_v66_killreach_rollback`（10 场/20 流 first-diff）
   - `overlay_basecache` vs `ai_v66_killreach_rollback`（10 场/20 流 first-diff，对照）
4. 依据证据判定为 ablation reject，并回滚门控代码；回滚后再次验证与基线一致。
5. 新增分析文档：`/www/docs/replay_analysis/saiblo_recruit_reservegate_ablation_20260305.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260305_001813`）前二：
  - `cpp_v64_generals_rebuild`: `1902.39`
  - `cpp_v66_generals_weapon_econ`: `1866.28`
- 实验版（`recruit_reservegate`）对基线（`overlay_basecache`）：
  - 5 场/10 流：`hash_diff_streams=0/10`
  - 10 场/20 流：`hash_diff_streams=1/20`，`non_end_delta=-1`
  - 差异定位：`match_7413440` `stdin_index=1`，实验版少一次 `CALL_GENERAL`
- 对 `ai_v66` 的全样本 first-diff：
  - 实验版：`diff_streams=7/20`
  - 基线版：`diff_streams=7/20`
  - 首分歧覆盖与位置一致，未见收敛改善。
- 回滚后验证（`recruit_reservegate_rollback` vs `overlay_basecache`，10 场/20 流）：
  - `hash_diff_streams=0/20`
  - `non_end_delta=0`
  - `frame_delta=0`

### 结论

- 本轮轻量门控实验未降低与 `ai_v66` 的关键分歧覆盖，且引入了轻微新增漂移（1/20）。
- 依据“简化优先 + 最小风险”原则，本轮拒绝该实验并回滚，最终保持稳定基线逻辑。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：保持稳定动作节奏（招募仍在 move sweep 前），避免时序重排。
- `ANTWar-AI`：danger-state 小步门控 + 证据不足即回退，优先稳态演进。

### 风险

- 线上 head-to-head 证据仍缺，无法直接评估胜率收益。
- `CALL_GENERAL` 与局部 `MOVE_ARMY` 顺序差异仍在，根因尚未闭合。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费在不可执行链路。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮未新增搜索/前瞻深度；只做招募阶段的可逆门控实验并回滚。
- 既有 `<=200ms` 硬截止 + 回退机制不变。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 优先分析 stream `10/11` 的 `MOVE_ARMY` 顺序分歧，寻找比招募门控更直接的算法入口。
2. `CALL_GENERAL` 方向仅保留单条件、可解释、可回滚的小步实验。
3. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。

## 2026-03-05 定时心跳回合（analysis-round，first-diff-semantic-guard）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 围绕上轮提出的 stream `10/11` 分歧做深度诊断，增强 `saiblo_replay_first_diff.py`：
   - 新增 `--stability-runs` 复跑稳定性检查；
   - 新增语义字段（`semantic_diff_kind` / 行存在性 / `frame_jaccard`）。
3. 本地验证：
   - 同二进制自检（`overlay_basecache` vs `overlay_basecache`，10 场/20 流，`stability-runs=2`）；
   - 语义对比（`overlay_basecache` vs `ai_v66_killreach_rollback`，10 场/20 流，`stability-runs=2`）；
   - 脚本语法验证：`python3 -m py_compile /www/scripts/saiblo_replay_first_diff.py`。
4. 新增分析文档：`/www/docs/replay_analysis/saiblo_first_diff_semantic_guard_20260305.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260305_011624`）前二：
  - `cpp_v64_generals_rebuild`: `1865.80`
  - `cpp_v66_generals_weapon_econ`: `1854.78`
- 同二进制自检（stable2）：
  - `checked_streams=20`
  - `unstable_streams=0`
  - `diff_streams=0`
- `overlay_basecache` vs `ai_v66`（stable2）：
  - `checked_streams=20`
  - `unstable_streams=0`
  - `diff_streams=7`
  - 语义拆分：
    - `opcode_change=5`（核心仍是 `CALL_GENERAL(7)` vs `MOVE_ARMY(1)`）
    - `partial_intra_frame_shift=1`（stream `10`）
    - `intra_frame_reorder_move_army=1`（stream `11`，同帧重排）

### 结论

- 本轮确认 stream `11` 是“同帧 MOVE_ARMY 重排”而非核心策略分叉；主分歧仍由 `CALL_GENERAL` 触发。
- 新增稳定性复跑门控后，`first-diff` 结果可复验性更高，可减少误判驱动的无效改动。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：映射其关键动作可观测、分支可解释的调试思想到语义分类输出。
- `ANTWar-AI`：映射其预算化验证思想到 `stability-runs` 复跑门控（先稳再判）。

### 风险

- 缺线上 head-to-head 证据，无法直接转化为胜率结论。
- 仍有 `CALL_GENERAL` 相关分歧待进一步拆解（缺失/延后两类）。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费在不可执行链路。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮未改动 AI 搜索/前瞻策略，仅增强离线分析脚本。
- `<=200ms` 硬截止 + 回退机制不变。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 用语义分类结果继续拆解 `CALL_GENERAL` 分歧（先单流、再小样本）。
2. 将 stream `10` 的 `partial_intra_frame_shift` 做单流定向核验，确认是否资源占用引起。
3. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。

## 2026-03-05 定时心跳回合（analysis-round，call-general-delay-split）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 延续上轮语义诊断，增强 `saiblo_replay_first_diff.py`：
   - 新增 `--lookahead-frames`；
   - 将 `CALL_GENERAL` 差异细分为 delayed/missing。
3. 本地验证：
   - 脚本语法：`python3 -m py_compile /www/scripts/saiblo_replay_first_diff.py`
   - 自检：`overlay_basecache` vs `overlay_basecache`（10 场/20 流，`stability-runs=2`，`lookahead=2`）
   - 对照：`overlay_basecache` vs `ai_v66_killreach_rollback`（10 场/20 流，`stability-runs=2`，`lookahead=2`）
4. 新增分析文档：`/www/docs/replay_analysis/saiblo_call_general_delay_split_20260305.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260305_013618`）前二：
  - `cpp_v66_generals_weapon_econ`: `1909.39`
  - `cpp_v64_generals_rebuild`: `1848.83`
- 自检（同二进制）：
  - `checked_streams=20`
  - `unstable_streams=0`
  - `diff_streams=0`
- `overlay_basecache` vs `ai_v66`（lookahead split）：
  - `checked_streams=20`
  - `unstable_streams=1`（stream 7，候选侧不稳定）
  - `compared_streams=19`
  - `diff_streams=7`
  - 语义拆分：
    - `call_general_missing_in_cand=5`（stream `0/4/6/14/15`）
    - `partial_intra_frame_shift=1`（stream `10`）
    - `intra_frame_reorder_move_army=1`（stream `11`）

### 结论

- 本轮确认 `CALL_GENERAL` 主分歧是“missing”而非“delayed”。
- 这把后续实验范围收敛到“招募触发条件”本身，不需要再做动作时序重排。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：关键动作分歧做可解释拆解（missing vs delayed），减少盲目改动。
- `ANTWar-AI`：先做复跑稳定性门控，再解释差异并决定下一步实验。

### 风险

- 仍缺线上 head-to-head 证据，无法直接验证胜率收益。
- 候选侧存在单流不稳定现象（stream 7），可能污染对照结论，需要持续隔离处理。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费在不可执行链路。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮仅增强离线诊断脚本，未改动 AI 搜索/前瞻逻辑。
- `<=200ms` 硬截止 + 回退机制不变。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 对 `CALL_GENERAL` 做单条件触发实验（仅一处阈值/条件变化），验证 missing 是否下降。
2. 对候选不稳定流（stream 7）做复跑隔离，避免把候选抖动当成策略收益/退化。
3. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。

## 2026-03-05 定时心跳回合（analysis-round，recruit-subgap-ablation-reject）

- 本轮类型：`analysis-round`
- 是否上传：`否`
- 是否发起 Saiblo 对战：`否`
- 未对战原因：`python3 /www/saiblo_tools.py entities --game-id 48` 与 `python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30` 均因 `api.saiblo.net` DNS 失败不可达。
- 下轮触发条件：网络恢复后切换 `test-round`，候选继续使用 `cpp_v1_current`，对手优先“分数接近或更强”，启用 `--swap`，总局数 `<=10`。

### 本轮动作

1. 按流程重读：
   - `/www/docs/codex_saiblo_objective_fixed.md`
   - `/www/autolab/runtime/latest.json`
   - Saiblo `entities/ladders`
   - `/www/docs/saiblo_codex_iterations.md`
   - `/www/docs/replay_analysis/saiblo_*`
   - 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/main.cpp`
2. 基于上一轮 `CALL_GENERAL missing` 结论做单条件实验：
   - 仅在“我方副将数 `<=` 对手副将数 + 1”时允许招募。
   - 不改招募时序，不改搜索深度。
3. 本地验证：
   - `recruit_subgap` vs `overlay_basecache`（10 场/20 流，2 repeats）
   - `recruit_subgap` vs `ai_v66_killreach_rollback`（10 场/20 流，stable2+lookahead2）
4. 实验判定失败后，回滚改动并验证回滚版本与基线一致。
5. 新增分析文档：`/www/docs/replay_analysis/saiblo_recruit_subgap_ablation_20260305.md`。

### 证据

- 生产 Elo（`/www/autolab/runtime/latest.json`，tag=`eval_20260305_015407`）前二：
  - `cpp_v64_generals_rebuild`: `1885.75`
  - `cpp_v66_generals_weapon_econ`: `1854.68`
- 实验版（`recruit_subgap`）对基线（`overlay_basecache`）：
  - `hash_diff_streams=7/20`
  - `non_end_delta=+189`
  - 漂移显著放大。
- 实验版对 `ai_v66`（stable2+lookahead2）：
  - `diff_streams=9/20`（基线为 `7/20`）
  - 新增 `call_general_missing_in_base`，语义偏差扩大。
- 回滚后验证（`recruit_subgap_rollback` vs `overlay_basecache`）：
  - `hash_diff_streams=0/20`
  - `non_end_delta=0`
  - `frame_delta=0`

### 结论

- 该单条件实验未收敛 `CALL_GENERAL` 主分歧，且明显增加行为漂移，风险不可接受。
- 依据“最小风险 + 简化优先”原则，本轮拒绝并回滚，保持稳定基线。
- 在线链路不可用，暂不上传、不对战。

### 与历史 AI 机制映射

- `Generals-AI`：保持经济动作时序稳定（未改招募相对时序）。
- `ANTWar-AI`：将劣势分支思想映射为副将差门控做小步验证；证据不成立即回退。

### 风险

- 线上 head-to-head 证据仍缺，无法确认离线差异对胜率的实际影响。
- `CALL_GENERAL` missing 主分歧仍在，需要继续做更局部、更低漂移的条件实验。

### 对手选择与预算说明

- 对手选择理由：本轮未对战（API 不可达），避免预算浪费在不可执行链路。
- 预算使用：`0/10`。

### 200ms 风险点

- 本轮未增加搜索/前瞻深度，仅做招募触发单条件实验并回滚。
- `<=200ms` 硬截止 + 回退机制保持不变。
- 本轮未触发新的 200ms 风险点。

### 下一步

1. 继续单条件、可回滚实验，但从“招募位置/score 阈值”入手，避免结构性副将差门控。
2. 针对 `call_general_missing_in_cand` 的 5 条主流分歧做定向小样本验证（先 stream 0/4/6）。
3. 网络恢复后执行 `test-round`：`cpp_v1_current` 对近分/更强对手，`--swap`，`<=10` 局。
