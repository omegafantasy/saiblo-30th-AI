# Docs Layout

`docs/` 现在只保留仍需人工阅读、且能直接回指当前代码的最小文档集。

## 1. Game1

Game1 只保留当前规则与实现说明，不再保留历史自动化结果、旧版本结论、细节策略页或旧规则快照。

当前建议只看：

1. `game1_code_truth.md`
2. `game1_known_discrepancies.md`
3. `game1_lure_strategy.md`
4. `game1_random_search_strategy.md`
5. `game1_strength_eval_2026-04-21.md`
6. `Game1/antgame_cpp_sdk/README.md`（需要做 native 复算或本地工具调试时）
7. `Game1/antgame_ai_cpp/cpp_heavy_baseline/README.md`（需要看当前 AI 入口与 self-play 用法时）

读取原则：

- Game1 规则与运行时真值在 `Game1/Ant-Game/`
- Game1 外置 C++ SDK 在 `Game1/antgame_cpp_sdk/`
- Game1 C++ AI 源码在 `Game1/antgame_ai_cpp/`
- 当前已确认官方基础收入为每 `2` 回合 `+3`
- `docs/` 只负责整理当前机制与已确认冲突，不负责保留旧叙事
- 若 `README.md`、SDK、测试、native 实现互相冲突，先看 `game1_known_discrepancies.md`
- 阶段性强度评测笔记按日期单独存放，可作为分析记录，但不替代上面几份“当前实现说明”
- 当前最新一份阶段性评测记录为 `game1_strength_eval_2026-04-21.md`

## 2. 自动化提示

以下文件仍保留，但应按“只基于当前代码真值”理解：

- `codex_automation_runbook.md`
- `codex_iteration_prompt.md`
- `codex_objective_fixed.md`
- `codex_anchor_iteration_prompt.md`
- `codex_anchor_objective_fixed.md`
- `codex_saiblo_iteration_prompt.md`
- `codex_saiblo_objective_fixed.md`

## 3. Game2

Game2 文档不在本轮清理范围内，继续原样保留。

## 4. mhtml

`mhtml_parsed/` 仅保留当前仍有阅读价值的非 Game1 快照。
