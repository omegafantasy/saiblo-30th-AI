# Replay Analysis 模块说明

## 目标

为每轮评测保存 replay，并提供结构化复盘，避免仅按 Elo/胜率盲目迭代。

## 数据来源

- 对局 replay（每局一份）：
  - 生产：`/www/autolab/runtime/replays/<eval_tag>/`
  - iter：`/www/autolab/runtime/scopes/iter/replays/<eval_tag>/`
- 对局索引（match 行）：`eval_<tag>_matches.jsonl`，每行含 `replay_file`。

## 入口脚本

```bash
python3 /www/autolab_replay_analyze.py --scope iter --latest
```

常用参数：

- `--scope <name>`：分析对应 scope（空字符串为生产）。
- `--latest`：分析该 scope 的 `latest.json` 指向的 `matches`。
- `--matches <path>`：显式指定 `matches.jsonl`（会覆盖 latest）。
- `--max-matches N`：只分析最后 N 局（0 表示全部）。
- `--top-matches N`：报告保留的关键对局条数。

## 输出位置

默认输出到对应 runtime scope：

- `.../replay_analysis/<tag>_replay_analysis.json`
- `.../replay_analysis/<tag>_replay_analysis.md`
- `.../replay_analysis/latest.json`
- `.../replay_analysis/latest.md`

iter 实验脚本还会同步一份到 docs：

- `/www/docs/replay_analysis/iter_latest.json`
- `/www/docs/replay_analysis/iter_latest.md`

## 报告内容

- 版本聚合：`win_rate`、`score_rate`、平均回合、空操作率、终局地盘/兵力、动作分布。
- 对局级指标：回合数、兵力/地盘波动幅度、关键转折回合、replay 路径。
- 行为统计：动作类型计数（`army_move/general_upgrade/tech_upgrade/...`）、无效动作占比。

## 与 Codex 迭代对接

- `/www/scripts/autolab_eval_experiment_once.sh` 会在评测完成后自动调用 replay 分析。
- `docs/codex_objective_fixed.md` 和 `docs/codex_iteration_prompt.md` 已加入“必须使用 replay 分析”的约束。
- 建议在每轮迭代记录中写明：
  - 从 replay 观察到的关键行为；
  - 与代码改动是否一致；
  - 发现的逻辑偏差与下一步修正。
