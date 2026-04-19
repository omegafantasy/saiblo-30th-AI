# Docs Layout

`docs/` 现在只保留仍需人工阅读、且能直接回指当前代码的最小文档集。

## 1. Game1

Game1 只保留当前规则与实现说明，不再保留历史自动化结果、旧版本结论、细节策略页或旧规则快照。

当前建议只看：

1. `game1_code_truth.md`
2. `game1_known_discrepancies.md`
3. `game1_random_search_strategy.md`
4. `Game1/antgame_cpp_sdk/README.md`（需要做 native 复算或本地工具调试时）

读取原则：

- Game1 规则与运行时真值在 `Game1/Ant-Game/`
- Game1 外置 C++ SDK 在 `Game1/antgame_cpp_sdk/`
- Game1 C++ AI 源码在 `Game1/antgame_ai_cpp/`
- `docs/` 只负责整理当前机制与已确认冲突，不负责保留旧叙事
- 若 `README.md`、SDK、测试、native 实现互相冲突，先看 `game1_known_discrepancies.md`
- 阶段性强度评测笔记、partial debug 样本与本地 replay 分析结果不进入正式文档集

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
