这是自动迭代心跳回合，请继续推进上一次工作。

必须先读取并严格遵守：
- /www/docs/codex_objective_fixed.md

本回合执行流程：
1) 读取最新状态：
   - 生产评测：`/www/autolab/runtime/latest.json`
   - 迭代评测（隔离）：`/www/autolab/runtime/scopes/iter/latest.json`（若存在）
   - 迭代记录：`/www/docs/round2_autolab_and_iterations.md`
2) 选择一项“算法级”改进并直接落到代码（优先 `ai_cpp/` 与 `autolab/`）。
3) 运行至少一轮可复现实验，必须使用：
   - `/www/scripts/autolab_eval_experiment_once.sh`
   - 禁止直接运行会写入生产 `latest/champion` 的评测命令。
   - 迭代优先：默认高并发（最多14核）；除非你在排查并发问题，不要降到 `--jobs 1`。
4) 将结果、风险、下一步写回 `/www/docs/round2_autolab_and_iterations.md`。

若你检测到当前会话已经在执行相同任务，则直接 `continue` 到下一步，不要重新开题。
