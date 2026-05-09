# Game2 Late Poker/Yuan Probe Audit

更新时间：`2026-05-10 03:56 UTC+8 / 2026-05-09 19:56 UTC`

## 目标

当前目标是尽可能拓展 Game2/Game53 后两个剧本 Poker/Yuan 的剧情和 stage 上限，不继续围绕 `2757/2797` 已知高分骨架做细节微调；在 Saiblo 恢复后用单人房间并发评测，不使用 batch、不上天梯、不暴露策略命名。

## 已落地产物

候选覆盖：

- Yuan 隔离与答案字段：`n577a-d`、`n580a-d`、`n582a-d`。
- Yuan direct 骨架高层探针：`n583a-c`，固定 Rose/Z/F/Poker direct，只测 Yuan 身份置换/隐藏证据 meta/短答案字段。
- Yuan 完整骨架条件线：`n577e`、`n583d`。
- Poker 字段/隐藏链隔离：`n578a-d`、`n579a`、`n579d`、`n581a-b`、`n574c`。
- Poker/Yuan 完整骨架交叉线：`n578e-f`、`n579b-c`、`n581c-d`。
- 旧待补 witness 双问：`n576a-c`。

生成脚本：

- `Game2/tools/make_n577_candidates.py`
- `Game2/tools/make_n578_candidates.py`
- `Game2/tools/make_n579_candidates.py`
- `Game2/tools/make_n580_candidates.py`
- `Game2/tools/make_n581_candidates.py`
- `Game2/tools/make_n582_candidates.py`
- `Game2/tools/make_n583_candidates.py`

恢复与汇总：

- `scripts/game2_late_probe_retry.sh`：profile 账号守卫通过后并行启动三组 `run_recovery_eval_queue.py`；profile 检查默认 API 超时为 `120s`，外层 wall timeout 为 `180s`，避免服务器慢响应或 Python 网络调用卡死时永久挂住。
- `Game2/tools/check_saiblo_profile.py`：独立 profile 守卫 helper，避免 bash heredoc 后台运行留下孤儿 profile 子进程。
- `Game2/tools/summarize_late_probe_results.py`：恢复队列结束后生成 `docs/generated/game2_late_probe_results.md/json`。

## 当前验证

- watcher 队列共 `35` 个标签，均有对应 `Game2/deepclue_ai/<label>/ai.py`。
- `35` 个标签全部通过 Python `compile()` 检查。
- watcher 标签全部被 `summarize_late_probe_results.py` 覆盖。
- `scripts/game2_late_probe_retry.sh` 通过 `bash -n`。
- 当前后台 watcher 通过 `setsid -f bash scripts/game2_late_probe_retry.sh` 启动，PID 为 `412695`。

## 阻塞

Saiblo `/api/profile/` 持续 read timeout，未通过 `thebeginning` username safety check，因此尚未上传 `n577-n583`，也没有新的单人房间结果。不能改用 `entities` 作为备用守卫，因为 `saiblo_tools.py entities` 也依赖 `/api/profile/`；直接查 `thebeginning` entities 会绕过当前 token 身份验证。当前只增加外层 wall timeout，不绕过账号守卫。

## 恢复后判定

恢复后首先看 `docs/generated/game2_late_probe_results.md`：

- 隔离态若出现 `>507` 的 Poker 或 `>247` 的 Yuan，应优先扩该方向。
- 完整骨架若出现 `>2797`，直接扩样同 code_id。
- 若只复现 `2797` 但低尾更多，不作为 keeper，只记录剧情上限。
- 若 `404/501/705/706+` 出现但分数不涨，记录为剧情证据，不把它当已证实计分层。
