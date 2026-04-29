# Docs Layout

`docs/` 现在只保留仍需人工阅读、且能直接回指当前代码的最小文档集。

## 1. Game1

Game1 只保留当前规则与实现说明，不再保留历史自动化结果、旧版本结论、细节策略页或旧规则快照。当前本地最优解是 `Game1/antgame_ai_cpp/cpp_lure_v3/`。

当前建议只看：

1. `game1_code_truth.md`
2. `game1_known_discrepancies.md`
3. `game1_lure_strategy.md`
4. `game1_random_search_strategy.md`
5. `game1_saiblo_elo.md`
6. `Game1/antgame_cpp_sdk/README.md`（需要做 native 复算或本地工具调试时）
7. `Game1/antgame_ai_cpp/cpp_lure_v3/README.md`（需要看当前最优 AI 入口、参数口径和评测结果时）
8. `Game1/antgame_ai_cpp/cpp_heavy_baseline/README.md`（需要看冻结 baseline 入口与 self-play 用法时）
9. `Game1/antgame_ai_cpp/simviz/README.md`（需要做单回合可视化审计时）

读取原则：

- Game1 规则与运行时真值在 `Game1/Ant-Game/`
- Game1 外置 C++ SDK 在 `Game1/antgame_cpp_sdk/`
- Game1 C++ AI 源码在 `Game1/antgame_ai_cpp/`
- 当前已确认官方基础收入为每 `2` 回合 `+3`
- 当前 Game1 baseline 真实实现是 `lure_strategy_v2.hpp`；`lure_strategy.hpp` 是默认兼容转发入口
- 当前 Game1 最优解是 `cpp_lure_v3`；`cpp_lure_v3a` 仅是 2 级基地蚂蚁抗性测试变体
- 当前快速模拟对拍和性能工具在 `Game1/antgame_cpp_sdk/examples/`
- 当前 2026-04-29 v3 vs baseline 128 局、v3-a vs v3 32 局，以及历史 fast/native 对拍结论记录在 `game1_random_search_strategy.md`
- Saiblo Game1 对局元信息同步、AI 版本 Elo 与本地看板见 `game1_saiblo_elo.md`
- `docs/` 只负责整理当前机制与已确认冲突，不负责保留旧叙事
- 若 `README.md`、SDK、测试、native 实现互相冲突，先看 `game1_known_discrepancies.md`
- 历史自动化评测记录不再作为当前策略文档保留；需要复盘时应重新基于当前代码跑 self-play / parity / simviz

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
