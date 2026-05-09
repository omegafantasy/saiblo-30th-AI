# Game2 Late Poker/Yuan Probe Audit

更新时间：`2026-05-10 04:30 UTC+8 / 2026-05-09 20:30 UTC`

## 目标

当前目标是尽可能拓展 Game2/Game53 后两个剧本 Poker/Yuan 的剧情和 stage 上限，不继续围绕 `2757/2797` 已知高分骨架做细节微调；在 Saiblo 恢复后用单人房间并发评测，不使用 batch、不上天梯、不暴露策略命名。

## 已落地产物

候选覆盖：

- Yuan 隔离与答案字段：`n577a-d`、`n580a-d`、`n582a-d`。
- Yuan direct 骨架高层探针：`n583a-c`、`n586a-b`、`n587a-b`、`n590a-c`、`n591a-c`，固定 Rose/Z/F/Poker direct，只测 Yuan 身份置换/隐藏证据 meta、两人作案、尸源/DNA、手机数字取证、投票 custody、周五揭发缓存、传闻源、行李箱来源、主角身份/网页截图和出国名额行政记录。
- Yuan 完整骨架/隔离条件线：`n577e`、`n583d`、`n586c-d`、`n587c-d`、`n590d`、`n591d`。
- Poker 字段/隐藏链隔离：`n578a-d`、`n579a`、`n579d`、`n581a-b`、`n584a-c`、`n585a-c`、`n588a-c`、`n589a-c`、`n592a-c`、`n574c`。
- Poker/Yuan 完整骨架交叉线：`n578e-f`、`n579b-c`、`n581c-d`、`n584d`、`n585d`、`n588d`、`n589d`、`n590d`、`n592d`。
- 旧待补 witness 双问：`n576a-c`。

生成脚本：

- `Game2/tools/make_n577_candidates.py`
- `Game2/tools/make_n578_candidates.py`
- `Game2/tools/make_n579_candidates.py`
- `Game2/tools/make_n580_candidates.py`
- `Game2/tools/make_n581_candidates.py`
- `Game2/tools/make_n582_candidates.py`
- `Game2/tools/make_n583_candidates.py`
- `Game2/tools/make_n584_candidates.py`
- `Game2/tools/make_n585_candidates.py`
- `Game2/tools/make_n586_candidates.py`
- `Game2/tools/make_n587_candidates.py`
- `Game2/tools/make_n588_candidates.py`
- `Game2/tools/make_n589_candidates.py`
- `Game2/tools/make_n590_candidates.py`
- `Game2/tools/make_n591_candidates.py`
- `Game2/tools/make_n592_candidates.py`

恢复与汇总：

- `scripts/game2_late_probe_retry.sh`：profile 账号守卫通过后并行启动三组 `run_recovery_eval_queue.py`；profile 检查默认 API 超时为 `120s`，外层 wall timeout 为 `180s`，避免服务器慢响应或 Python 网络调用卡死时永久挂住。
- `Game2/tools/check_saiblo_profile.py`：独立 profile 守卫 helper，避免 bash heredoc 后台运行留下孤儿 profile 子进程。
- `Game2/tools/summarize_late_probe_results.py`：恢复队列结束后生成 `docs/generated/game2_late_probe_results.md/json`。

## 当前验证

- watcher 队列共 `71` 个标签，均有对应 `Game2/deepclue_ai/<label>/ai.py`。
- `71` 个标签全部通过 Python `compile()` 检查。
- watcher 标签全部被 `summarize_late_probe_results.py` 覆盖。
- `scripts/game2_late_probe_retry.sh` 通过 `bash -n`。
- 当前后台 watcher 通过 `setsid -f bash scripts/game2_late_probe_retry.sh` 重启，PID 为 `420053`；必须仍通过 `thebeginning` profile 守卫后才上传。

## 阻塞

Saiblo `/api/profile/` 持续 read timeout，未通过 `thebeginning` username safety check，因此尚未上传 `n577-n592`，也没有新的单人房间结果。不能改用 `entities` 作为备用守卫，因为 `saiblo_tools.py entities` 也依赖 `/api/profile/`；直接查 `thebeginning` entities 会绕过当前 token 身份验证。当前只增加外层 wall timeout，不绕过账号守卫。

## 恢复后判定

恢复后首先看 `docs/generated/game2_late_probe_results.md`：

- 隔离态若出现 `>507` 的 Poker 或 `>247` 的 Yuan，应优先扩该方向。
- 完整骨架若出现 `>2797`，直接扩样同 code_id。
- 若只复现 `2797` 但低尾更多，不作为 keeper，只记录剧情上限。
- 若 `404/501/705/706+` 出现但分数不涨，记录为剧情证据，不把它当已证实计分层。

## 2026-05-09 20:15 UTC 高层剧情轴补充

本轮补充不再围绕已知问句做同义变体，而是按未充分覆盖的剧情轴拆：

- `n585a-c`：Poker 隔离，分别验证 post-monitor 后的警方卷宗/DNA/指纹/银行流水、真梅花5本人直问、404车辆/501转账后续物证。
- `n585d`：完整骨架，组合验证 Poker 官方卷宗、404/501 后续物证和真梅花5本人直问是否能打开 `405/502` 或 stage4。
- `n586a-b`：Rose/Z/F/Poker direct + Yuan probe，验证 Yuan 两人作案/分工假设与尸源/DNA/照片元数据轴。
- `n586c`：Yuan 隔离，解析 biology-runner 和保安来源后定向问官方记录、门禁/监控、网页日志和车辆记录。
- `n586d`：完整骨架，保留前案完整路线，Yuan 改为证据来源、两人分工、官方证据 custody 的高层探针。
- `n587a-d`：补 Yuan 手机数字取证、投票原件 custody、完整骨架手机/投票官方材料，以及 Poker `404/501` 后的 Yuan 跨案同源问题。
- `n588a-d`：补 Poker 404 车主本人、501 收款/于书华本人、0512/手机/隐藏房间，以及完整骨架中车主/收款人/信息源三路并查。
- `n589a-d`：补 Poker 公馆空间/权限轴、密码/门锁/隐藏房间权限轴、刀具/刀痕/血迹法医轴，以及完整骨架空间权限+toolmark 合并复原。
- `n590a-d`：补 Yuan 周五揭发证据缓存、张壹/张朔传闻源、黄色行李箱 provenance，以及 Poker/Yuan 刀具与背刺 toolmark 跨案物证轴。
- `n591a-d`：补 Yuan 开场失忆侦探/保安认识你/网页截图轴、尸源身份拆分、出国名额行政记录，以及主角身份/旧案网页完整隔离。
- `n592a-d`：补 Poker Joker 账号数字取证、邀请函/地址表/面具映射、接待定金/五十万承诺付款链，以及完整骨架数字链综合探针。
