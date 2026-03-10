这是自动迭代心跳回合，请继续推进上一次工作。

必须先读取并严格遵守：
- /www/docs/codex_objective_fixed.md

本回合执行流程：
1) 读取最新状态：
   - 生产评测：`/www/autolab/runtime/latest.json`
   - 迭代评测（隔离）：`/www/autolab/runtime/scopes/iter/latest.json`（若存在）
   - 回放分析：`/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`、`/www/docs/replay_analysis/iter_latest.md`（若不存在则先生成）
   - 对局索引：iter `latest.json` 里的 `paths.matches`；每行包含 `replay_file`，可直接打开原始回放逐帧核对
   - 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
   - 旧 AI 参考：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI`（至少提取各 1 个机制）
   - Elo 治理：生产 Elo 是唯一权威；iter Elo 仅用于候选筛选，禁止跨 scope 直接比较 Elo 绝对值。
   - 必做判读：读取生产 `latest.json` 的 `config.pairs` 与 `champion.old/new`，写明本轮对手池是否受 champion 切换影响（gauntlet 口径下这是高优先级风险）。
2) 选择一项“算法级”改进并直接落到代码（优先 `ai_cpp/` 与 `autolab/`）。
   - 若涉及 AI 策略代码改动，必须新建版本目录与新版本 ID；禁止改写已有版本源码（旧版本视为不可变快照）。
   - 若本轮仅做分析或评测基础设施改进，可不新建 AI 版本，但要在文档中明确“无策略代码改动”。
   - 必须给出“旧 AI 借鉴点 -> 本游戏映射 -> 代码落点”的可验证链路。
   - 优先简化策略结构（减少分支、状态和补丁层数）；若复杂化与收益冲突，优先选简化路线。
   - 若改动涉及搜索/前瞻（beam/minimax/rollout 等），必须在代码中加入“单步 CPU `<=200ms`”硬截止与保底回退路径。
   - CPU 时间口径必须使用 CPU 计时接口（如 `CLOCK_THREAD_CPUTIME_ID`），不能只用 wall-clock 近似。
3) 运行至少一轮可复现实验，必须使用：
   - `/www/scripts/autolab_eval_experiment_once.sh`
   - 该脚本会自动生成 iter 回放分析；若你用其他命令评测，必须手动执行：`python3 /www/autolab_replay_analyze.py --scope iter --latest`
   - 禁止直接运行会写入生产 `latest/champion` 的评测命令。
   - 迭代优先：默认高并发（最多14核）；除非你在排查并发问题，不要降到 `--jobs 1`。
   - 最终结论必须回到生产评测口径（`/www/autolab/runtime/latest.json`），iter 结果仅作探索依据。
   - 判优口径：
     - 两个 AI 相对强度比较：`>=100` 局才可用于结论；否则仅标记 smoke。
     - 多 AI 排序比较：需要更大样本，不可用小样本结论替代。
     - 若要宣称“新版本优于 k 个老版本”，需满足：
       1) 对每个目标老版本 `>=200` 局且胜率都 `>55%`；或
       2) 在大样本 Elo（如 `>=1000` 局）中稳定榜首。
   - 若生产 gauntlet 与近期结论冲突，必须补做 head-to-head 复验（至少 `100` 局；建议 `200` 局）后再给判优结论。
   - 推荐稳健验证顺序：
     1) smoke：每对手 20 局（仅筛选方向）；
     2) gate：候选 vs 关键基线（`v1/v2/当前champion`）每对手 `>=100` 局；
     3) confirm：关键对手每对手 `>=200` 局，或固定池大样本 Elo `>=1000` 局。
4) 将结果、风险、下一步写回 `/www/docs/round2_autolab_and_iterations.md`。
   - 必须同步引用 replay 分析结论，不能只写胜率/Elo。
   - 必须同步写“新版本命名与注册信息”；若本轮无新 AI 版本，必须证明本轮确实未改策略代码。
   - 必须写“Generals 借鉴点”和“ANTWar 借鉴点”各一条，并给出本轮是否生效的证据。
5) 同步思路文档（强制）：
   - 更新 `/www/docs/version_strategy_deep_dive_v1_v53.md` 对应版本条目；
   - 至少写清：设计假设、关键机制、评测证据、结论标签（`promising/neutral/regression/placeholder`）；
   - 若出现“新目录/新版本但无代码差异”，必须标记为 `placeholder`，不得当作有效迭代。
6) 每回合末尾必须自检并记录：
   - 本轮是否触发了搜索时间硬截止；
   - 是否存在超过 `200ms` 的单步 CPU 风险点；
   - 若有风险，下一轮如何降复杂度或改进剪枝。

若你检测到当前会话已经在执行相同任务，则直接 `continue` 到下一步，不要重新开题。
