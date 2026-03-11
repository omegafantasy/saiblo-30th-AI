# Docs Layout

当前 `docs/` 的主线已经分成 `Game1` 与 `Game2` 两部分，另保留少量基础参考文档。

## 1. Game2 当前最重要入口

如果现在只看 `Game2`，优先读这些：

- `game2_deepclue_rules_and_sdk_analysis.md`
  - 游戏机制、SDK 协议、线上开发约束
- `game2_saiblo_status.md`
  - 当前 Saiblo 联通、主线版本、受控复测状态
- `game2_batch_and_result_analysis.md`
  - batch 语义、结果解释、回放分析链、当前关键发现
- `game2_iteration_notes_20260311.md`
  - 当天迭代记录、实验矩阵、当前结论

当前最重要的生成报告：

- `generated/game2_run_comparison.md`
  - `v2 / v7 / admin` 的并排对比
- `generated/game2_version_summary.md`
  - 各上传版本当前已知最好成绩
- `generated/game2_latest_batch.md`
  - 最新 batch 状态
- `generated/game2_latest_submission.md`
  - 最新上传状态

## 2. Game1 文档

Game1 仍保留以下主文档：

- `game1_antgame2_code_truth_and_antwar_diff.md`
- `game1_antwar_ai_migration_and_cpp_v1.md`
- `game1_antwar_ai_coverage_check.md`
- `game1_simulation_randomness_analysis.md`
- `game1_simulation_perf_and_behavior_report.md`
- `game1_expectedfront_discussion_20260311.md`
- `game1_cpp_v3_unified_status.md`
- `game1_toolchain_status.md`
- `game1_autolab_and_elo.md`
- `game1_saiblo_api_and_workflow.md`
- `game1_codex_iteration_constraints.md`

## 3. 规则与参考页

- `mhtml_parsed/antgame2_game48.md`
- `mhtml_parsed/deepclue_game.md`
- `reference_antwar_game22.md`

## 4. 当前文档使用原则

Game2 当前判断优先级：

1. `docs/game2_*`
2. `docs/generated/game2_*`
3. `Game2/tools/*` 与 `Game2/runtime/*` 实际产物

Game1 当前判断优先级：

1. `Game1/Ant-Game` 代码
2. `docs/game1_*`
3. `reference_antwar_game22.md`

## 5. 当前已经同步进文档的关键信息

Game2 当前已经明确写入文档的事实包括：

- batch 是“双边独立跑分”，不是传统双边一局
- `exit_code=9` 不能单独当失败信号
- `v2` 是当前最强基线，但同码存在 `607 / 407 / 607` 波动
- `v7` 比 `v2` 更差，额外追问会把第一案嫌疑人带偏
- 高分对手 `admin` 的问题更短、更直接
- 平台在 `stage >= 8` 后继续 `chat` 存在已确认后端异常
- 当前已启动 `v2` 对 `admin` 的受控复测 batch `75665`
