# Game2 Late Poker/Yuan Probe Audit

更新时间：`2026-05-10 05:16 UTC+8 / 2026-05-09 21:16 UTC`

## 目标

当前目标是尽可能拓展 Game2/Game53 后两个剧本 Poker/Yuan 的剧情和 stage 上限，不继续围绕 `2757/2797` 已知高分骨架做细节微调；在 Saiblo 恢复后用单人房间并发评测，不使用 batch、不上天梯、不暴露策略命名。

## 已落地产物

候选覆盖：

- Yuan 隔离与答案字段：`n577a-d`、`n580a-d`、`n582a-d`。
- Yuan direct 骨架高层探针：`n583a-c`、`n586a-b`、`n587a-b`、`n590a-c`、`n591a-c`，固定 Rose/Z/F/Poker direct，只测 Yuan 身份置换/隐藏证据 meta、两人作案、尸源/DNA、手机数字取证、投票 custody、周五揭发缓存、传闻源、行李箱来源、主角身份/网页截图和出国名额行政记录。
- Yuan 完整骨架/隔离条件线：`n577e`、`n583d`、`n586c-d`、`n587c-d`、`n590d`、`n591d`。
- Poker 字段/隐藏链隔离：`n578a-d`、`n579a`、`n579d`、`n581a-b`、`n584a-c`、`n585a-c`、`n588a-c`、`n589a-c`、`n592a-c`、`n574c`。
- Poker/Yuan 完整骨架交叉线：`n578e-f`、`n579b-c`、`n581c-d`、`n584d`、`n585d`、`n588d`、`n589d`、`n590d`、`n592d`。
- 新增 stage 上限扇出：`n593a-b` 用 Poker `401/402 -> 密码/身份 -> 404/501` 后的官方卷宗多 holder 扇出追 `405/502`；`n593c` Yuan 隔离追 `705 -> 706` 官方来源；`n593d` 在完整骨架中把 Poker `404/501` late flag 带入 Yuan，测试跨案隐藏链是否打开 `706+`。
- 新增全员粗粒度 BFS：`n594a-b` 在 Poker late gate 后对所有可见 NPC 做 stage4/`405/502` 角色与物证扇出，降低 holder 解析错误风险；`n594c` Yuan 隔离按 `703-708` 官方来源做 BFS；`n594d` 完整骨架中组合 Poker all-NPC stage4 扇出与 Yuan 跨案 `703-708` BFS。
- 新增大答案假设矩阵：`n595a-b` 在 Poker 隔离中分别提交真梅花5/林渝植和 late-holder 作为最终凶手；`n595c-d` 在 Yuan 隔离中分别提交竞争者和隐藏链关键人，验证后两案是否因最终答案大方向错误而丢失答案层。
- 新增非微调 ceiling 拆轴：`n596a-b` 追 Poker `404/501` 后的警方卷宗、车辆/转账持有人、真梅花5、DNA/指纹、银行流水和 `405/502` 续证；`n596c-d` 追 Poker 空间权限/刀具/toolmark/门禁/清洁动线，并在完整骨架中接 Yuan 官方跨案链；`n596e-g` 分别隔离 Yuan 周五揭发缓存/行政记录、尸源-DNA-行李箱-手机数字取证、`705` 隐藏来源/全局姓名直连与 `706+` 续追；`n596h` 组合 Poker 官方卷宗链与 Yuan 跨案官方来源链。
- 新增鲁棒 holder ceiling：`n597a` Poker 隔离，`401/402` 后对全局姓名做一次受控 `405/502` holder 探测；`n597b` Yuan 隔离，解析“保安许大叔/江大叔”、生物馆跑出者、尸检报告来源等半名后直连可能全名；`n597c` Yuan 隔离，专门走失忆侦探/眼熟保安/网页截图/保安缺岗/旧案系统轴；`n597d-e` 完整骨架中分别测试鲁棒 Yuan holder 链和不依赖 Poker late flag 的跨案官方链。
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
- `Game2/tools/make_n593_candidates.py`
- `Game2/tools/make_n594_candidates.py`
- `Game2/tools/make_n595_candidates.py`
- `Game2/tools/make_n596_candidates.py`
- `Game2/tools/make_n597_candidates.py`

恢复与汇总：

- `scripts/game2_late_probe_retry.sh`：profile 账号守卫通过后并行启动五组 `run_recovery_eval_queue.py`，分别覆盖 Yuan core、Yuan stage/answer、Poker core、Poker stage/answer、full/cross；profile 检查默认 API 超时为 `120s`，外层 wall timeout 为 `180s`，避免服务器慢响应或 Python 网络调用卡死时永久挂住。
- `Game2/tools/check_saiblo_profile.py`：独立 profile 守卫 helper，避免 bash heredoc 后台运行留下孤儿 profile 子进程。
- `Game2/tools/summarize_late_probe_results.py`：恢复队列结束后生成 `docs/generated/game2_late_probe_results.md/json`。

## 当前验证

- watcher 队列共 `96` 个标签，均有对应 `Game2/deepclue_ai/<label>/ai.py`。
- `96` 个标签全部通过 Python `compile()` 检查。
- watcher 标签全部被 `summarize_late_probe_results.py` 覆盖。
- `scripts/game2_late_probe_retry.sh` 通过 `bash -n`。
- 当前后台 watcher 已用 `nohup + setsid` 重启为五队列并发版本，PID `425776`；必须仍通过 `thebeginning` profile 守卫后才上传。已确认 profile wall-time 超时后 bash 本体仍存活并进入 `sleep 300` 退避。

## 阻塞

Saiblo `/api/profile/` 持续 read timeout，未通过 `thebeginning` username safety check，因此尚未上传 `n577-n596`，也没有新的单人房间结果。不能改用 `entities` 作为备用守卫，因为 `saiblo_tools.py entities` 也依赖 `/api/profile/`；直接查 `thebeginning` entities 会绕过当前 token 身份验证。当前只增加外层 wall timeout，不绕过账号守卫。

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
- `n593a-d`：补“stage 上限扇出”而不是问句同义变体。Poker 侧把信息源、密码 holder、真梅花5、404 车主、501 收款人、接待者全部作为可能的 `405/502` holder，但只在 `401/402` 后触发；Yuan 侧把 `705` 尸检报告来源、biology runner、guard/web/source 三类来源作为 `706+` holder，并在完整骨架里把 Poker `404/501` late flag 作为跨案条件。
- `n594a-d`：补全员粗粒度 BFS。Poker 侧不再依赖已解析出的 owner/recipient/true-club，而是 late gate 后遍历所有可见 NPC，问其是否是 stage4/`405/502` 的角色或物证 holder；Yuan 侧不再只追 `705`，而是按 `703-708`、官方系统、安保/警方/法医/车辆/网站后台来源做更高预算 BFS。
- `n595a-d`：补最终答案大假设矩阵。Poker 用隔离骨架验证“真梅花5/林渝植杀 Joker”和“404/501 late-holder 参与杀人/移尸”两种大方向；Yuan 用隔离骨架验证“出国名额竞争者”和“biology/guard/705 隐藏链关键人”两种大方向。
- `n596a-h`：按用户提醒停止细节抠问，改为补后两案 stage/theory ceiling。Poker 分为官方卷宗/车辆/转账持有人链与空间权限/刀具/toolmark 链，且若 `405/502` 出现会继续问下一层。Yuan 分为周五揭发缓存与行政记录、尸源/DNA/行李箱/手机云端数字取证、`705` 来源姓名可能不可见时的全局姓名直连与可见 NPC 代理追问，且若 `706/707/708` 出现会继续闭环最终层。完整骨架版把 Poker `404/501/405/502` late flag 带入 Yuan，测试 Joker 人口贩卖、匿名转账、李海天、1919 黑车、生物馆、保安网页、蓝色背包和手机照片是否共享同一官方来源链。
- `n597a-e`：针对游戏更新后的 NPC 名字混淆补鲁棒性，而不是继续改同义问句。关键变化是把“保安许大叔/江大叔/叶大叔”这类半名解析到可能全名，允许对非当前可见但全局存在的 NPC id 做一次无重试探测；Poker 隔离用全局姓名扫 `405/502` holder，Yuan 隔离分别扫旧案 holder 与失忆网页/保安身份轴，完整骨架再测试跨案官方链是否不需要先显性出现 Poker `404/501`。
