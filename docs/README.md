# Docs Layout

当前 `docs/` 只保留四类内容：

1. 当前规则与代码真值分析
2. 当前 Game1 工具链与自动化说明
3. 当前可复用的 Saiblo / Codex 规约文档
4. 一个旧 `ANTWar` 规则参考页

当前主要文档：

- `game1_antgame2_code_truth_and_antwar_diff.md`
- `game1_antwar_ai_migration_and_cpp_v1.md`
- `game1_antwar_ai_coverage_check.md`
- `game1_cpp_v3_unified_status.md`
- `game1_toolchain_status.md`
- `game1_autolab_and_elo.md`
- `game1_saiblo_api_and_workflow.md`
- `game1_codex_iteration_constraints.md`
- `game2_deepclue_rules_and_sdk_analysis.md`
- `game2_saiblo_status.md`
- `reference_antwar_game22.md`
- `mhtml_parsed/antgame2_game48.md`
- `mhtml_parsed/deepclue_game.md`

生成型报告：

- `docs/generated/`
  - 本地 Elo 最新报告
  - 实验 Elo 最新报告
  - replay 分析最新报告

规则判断优先级：

- `Game1/Ant-Game` 代码
- 当前 `docs/game1_*` 分析文档
- `reference_antwar_game22.md` 仅作历史血缘参考

不再保留：

- 旧 `Generals` 文档
- 旧 root `ai_cpp/*` 迭代记录
- 旧 round2/旧 replay_analysis/旧 Saiblo 逐轮日志
