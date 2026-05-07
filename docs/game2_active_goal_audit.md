# Game2 Active Goal Audit

更新时间：`2026-05-07 12:06 UTC`

## 目标拆解

当前目标不是简单定版，而是持续迭代 `Game2 / Game53`，直到有证据认为所有剧本接近理论上限。可执行交付物拆成：

- 只改 Game2，不影响 Game1。
- 只用单人房间评测自己 raw score，不用 batch 作为版本判断。
- 不上天梯，不使用 `--activate`。
- Saiblo 可见实体名和备注保持中性，不暴露策略。
- 继续拓展各剧本理论上限，记录剧情、进展、疑点、问题、方法和新方案。
- 条件允许时并发或批量小样本评测候选；条件不允许时保留低频恢复 watcher。
- 阶段性提交 git，避免只依赖会话记忆。

## 证据清单

| 要求 | 当前证据 | 状态 |
| --- | --- | --- |
| 只迭代 Game2 | 近期提交只涉及 `Game2/tools/run_recovery_eval_queue.py` 与 `docs/game2_*`；未改 Game1 代码。 | 已满足 |
| 不用 batch 判断 | 恢复队列只调用 `upload-ai` 与 `run_room_eval.py`；文档明确禁止 batch。 | 已满足 |
| 不上天梯/不激活 | 队列脚本不带 `--activate`；watcher callback 只跑一次单人房评测。 | 已满足 |
| 中性可见信息 | 队列实体名为 `n514d/n514e/n518a/n518b/n519a/n519b`，remark 为 `r`。 | 已满足 |
| 当前最高样本 | `n511a` 19 个有效样本：`2707 x7, 2667 x2, 2657 x5, 2617 x3, 2507 x1, 2457 x1`。 | 已记录 |
| 理论上限判断 | 最高 `2707` 依赖 Poker stage2 + Rose/Z 高阶段；Poker stage3+、Yuan 703/704 净收益、Z/F stage8 正常路径仍未证明。 | 未完成 |
| 恢复后候选 | 默认队列 `n514d n514e n518a n518b n519a n519b` 已准备；后续 P1/P2/P3 队列见 `docs/game2_recovery_eval_queue.md`。 | 已准备 |
| 账号安全 | `run_recovery_eval_queue.py` 已新增 `--expected-username` / `SAIBLO_EXPECTED_USERNAME`，可在上传前校验 token。 | 已加固 |
| 平台可评测 | watcher 第 2 次实际探针 `2026-05-07 12:03 UTC` 仍为 `POST /api/rooms/` 500。 | 阻塞 |
| 当前 token | `entities --game-id 53` 于 `2026-05-07 11:56 UTC` 仍返回 `thebeginning`。若目标为 `theend`，必须切 token 后用账号守卫验证。 | 阻塞/待确认 |

## 未完成项

- 不能认为已达到所有剧本理论上限：后两个新增案仍有明显理论空间，但平台房间链路阻塞导致无法验证。
- `n514d/e` 安全对照、`n518a/b` evidence-refresh、`n519a/b` 鲁棒版本尚未上传和单人房扩样。
- `n518c/d`、`n517a/e/f/h/g`、Yuan P3 候选仍需要在 P0/P1 不退化后小样本评测。
- 当前 token 不是 `theend`，不能直接把恢复队列用于目标账号。

## 下一步条件

只有满足以下条件之一，才继续实质迭代：

- watcher 记录单人房间探针恢复成功，并触发 `n511a_recovered_once`。
- 用户切换 token 并要求在当前账号继续上传，随后用 `--expected-username` 校验通过。
- Saiblo POST 接口恢复到可上传/可开赛状态。

恢复后执行顺序：

1. 先用 `--expected-username <target>` 校验账号。
2. 运行恢复队列，默认每个候选 5 个单人房有效样本。
3. 如果 `n514e/n518b/n519b` 复现或超过 `2707` 且低尾不差，再扩到 12-16 个有效样本。
4. 若 P0/P1 无突破，再进入接待者证据问和 Yuan P3 小样本。
