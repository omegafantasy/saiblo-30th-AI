# Codex Automation Runbook

适用范围：

- `scripts/codex_iterate_once.sh`
- `scripts/codex_anchor_iterate_once.sh`
- `scripts/codex_saiblo_iterate_once.sh`

这份 runbook 不再保留历史版本、历史结果或历史策略。

## 1. 固定输入

本地迭代：

- `docs/codex_objective_fixed.md`
- `docs/codex_iteration_prompt.md`

本地第二线：

- `docs/codex_anchor_objective_fixed.md`
- `docs/codex_anchor_iteration_prompt.md`

Saiblo 迭代：

- `docs/codex_saiblo_objective_fixed.md`
- `docs/codex_saiblo_iteration_prompt.md`

共同前提：

- `docs/game1_code_truth.md`
- `docs/game1_known_discrepancies.md`

## 2. 默认流程

1. 先确认当前代码真值有没有变化
2. 再确认当前任务是本地还是在线
3. 再做最小必要操作
4. 完成后只记录当前这轮的输入、输出和验证

## 3. 本地侧

默认先检查：

- `Game1/Ant-Game/SDK/utils/constants.py`
- `Game1/Ant-Game/SDK/backend/engine.py`
- `Game1/Ant-Game/tests/test_engine.py`
- `Game1/Ant-Game/game/src/*`

本地验证优先级：

1. 小范围 smoke
2. 必要时 replay 复现
3. 必要时再扩大样本

## 4. 在线侧

默认顺序：

1. 先只读
2. 再上传
3. 再等待编译
4. 再做非 ladder 验证
5. 只有在明确要求时才激活或发 ladder

## 5. 输出要求

每轮至少保留：

- 改动内容
- 当前验证结果
- 若涉及在线链路，则记录 `entity_id`、`code_id`、`version`、`compile_status`、`match_id`

不再保留：

- 历史胜率榜单
- 历史版本排名
- 历史细节策略总结
