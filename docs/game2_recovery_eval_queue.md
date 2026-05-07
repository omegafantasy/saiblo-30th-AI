# Game2 Recovery Eval Queue

更新时间：`2026-05-07 12:05 UTC`

## 约束

- 只评测 Game53 / Game2。
- 不上天梯，不使用 `--activate`。
- 不用 batch 作为版本判断。
- 只用单人房间评测，直接看我方 raw score。
- Saiblo 可见实体名使用中性编号，如 `n514d`；备注统一用 `r`。

## 恢复探针

先确认平台是否恢复：

```bash
python3 saiblo_tools.py codes --entity-id 21072

python3 Game2/tools/run_room_eval.py \
  --code-id a2b68a7ec9b84a59a8dfd836defd930c \
  --label n511a_recover_probe \
  --count 1 \
  --timeout 420 \
  --poll-interval 2 \
  --request-timeout 90
```

低频 watcher：

```bash
python3 Game2/tools/watch_saiblo_recovery.py \
  --initial-delay 900 \
  --interval 900 \
  --probe-code-id a2b68a7ec9b84a59a8dfd836defd930c \
  --callback 'python3 Game2/tools/run_room_eval.py --code-id a2b68a7ec9b84a59a8dfd836defd930c --label n511a_recovered_once --count 1 --timeout 420 --poll-interval 2 --request-timeout 90'
```

说明：

- 默认 `--interval 900` 即 15 分钟检查一次，避免高频打扰服务器。
- 后台运行建议加 `--initial-delay 900`，避免刚手动探测后立即重复探测。
- watcher 会记录 `Game2/runtime/recovery_watch/status.jsonl`。
- 历史 `未编译` code 默认只记日志，不作为恢复阻塞；真正恢复标准是单人房间 `begin_match` 成功。
- 如果要把历史 pending compile 也作为阻塞条件，再加 `--require-compile-clear`。

恢复标准：

- 上传接口不再产生新的长期 `未编译` code。
- 单人房间不再卡在 `begin_match` 500。
- `run_room_eval.py` 的失败 summary 若仍失败，应保留 `room_id`，便于继续诊断。

## 优先级

| priority | label | source / code_id | 目的 |
| --- | --- | --- | --- |
| P0 | `n514d` | `Game2/deepclue_ai/n514d/ai.py` | 安全版 `n511a` 对照：关闭 stderr，Poker 信息源优先从当前 NPC 中文名精确匹配 hint，失败再用唯一 `marks=True`。 |
| P0 | `n514e` | `Game2/deepclue_ai/n514e/ai.py` | 安全版 `n512a` 问法隔离：案发现场+手中证据两问，不加证据追问、不加短动机。 |
| P1 | `n512a` | `673e54c862394b58a2ce790b63416e55` | 历史已上传样本 `2707,2507,2507`；因上传版仍有 verbose stderr，不作为恢复后的默认扩样目标。 |
| P1 | `n514g` | `Game2/deepclue_ai/n514g/ai.py` | `n514d` 的条件短动机版：只有 Poker stage2 成功后才把 motivation 从 `未知` 改成短动机。 |
| P1 | `n515b` | `Game2/deepclue_ai/n515b/ai.py` | `n514d` 加 stage2 后接待者合并 hint 单问，不加扑克短动机。 |
| P1 | `n515a` | `Game2/deepclue_ai/n515a/ai.py` | `n515b` 加条件短动机，只有 Poker stage2 成功后改 motivation。 |
| P1 | `n517a` | `Game2/deepclue_ai/n517a/ai.py` | `n514e` 问法 + stage2 后接待者合并 hint 单问；补齐 `n512a` 高 stage2 触发问法与接待者路线的组合缺口。 |
| P1 | `n517c` | `Game2/deepclue_ai/n517c/ai.py` | `n514e` 问法 + 条件短动机，不加接待者问，用于隔离 `n514e` 触发 stage2 后答案文本是否有净收益。 |
| P1 | `n518a` | `Game2/deepclue_ai/n518a/ai.py` | `n514d` 问法 + Poker stage2 后只调用一次 `others()` 刷新 `102/103/104`，不新增聊天。 |
| P1 | `n518b` | `Game2/deepclue_ai/n518b/ai.py` | `n514e` 问法 + Poker stage2 后只调用一次 `others()` 刷新 `102/103/104`，不新增聊天。 |
| P1 | `n519a` | `Game2/deepclue_ai/n519a/ai.py` | `n518a` 的鲁棒对照：动态处理最多 12 个剧本，Poker 信息源先按上下文正则匹配，未知新增案优先 `marks=False` 兜底。 |
| P1 | `n519b` | `Game2/deepclue_ai/n519b/ai.py` | `n518b` 的鲁棒对照：同样修复新增剧本与 NPC 名字混淆风险，保留 `n514e/n518b` 信息源问法。 |
| P2 | `n516a` | `Game2/deepclue_ai/n516a/ai.py` | `n515b` 的接待者更短问法：stage2 后只问“公馆内有什么异常发现？”。 |
| P2 | `n516b` | `Game2/deepclue_ai/n516b/ai.py` | `n515b` 的接待者关键词问法：异常发现 + 电脑/塑料盒/厨房少刀。 |
| P2 | `n516c` | `Game2/deepclue_ai/n516c/ai.py` | 按旧 hint 分拆接待者三问：聊天记录、到达时间表、异常发现；不问证词破绽。 |
| P2 | `n517b` | `Game2/deepclue_ai/n517b/ai.py` | `n514e` 问法 + stage2 后接待者异常关键词问。 |
| P2 | `n517d` | `Game2/deepclue_ai/n517d/ai.py` | `n514e` 问法 + stage2 后接待者分拆旧 hint 三问。 |
| P2 | `n517e` | `Game2/deepclue_ai/n517e/ai.py` | `n514e` 问法 + stage2 后接待者三证据精确问：电脑、塑料盒、少三把刀。 |
| P2 | `n517f` | `Game2/deepclue_ai/n517f/ai.py` | `n514e` 问法 + stage2 后接待者低泄露关键词问：电脑、冰柜、刀具异常。 |
| P2 | `n517h` | `Game2/deepclue_ai/n517h/ai.py` | `n514e` 问法 + 条件 Poker 手法文本，不加接待者问，用于隔离答案文本本身。 |
| P2 | `n517g` | `Game2/deepclue_ai/n517g/ai.py` | `n517e` 加 Poker 手法文本候选：死者用冰块固定刀具自杀并伪装他杀。 |
| P2 | `n518c` | `Game2/deepclue_ai/n518c/ai.py` | `n517a` 加两次 `others()`：stage2 后刷新 `102/103/104`，接待者问后刷新 `203/204/205`。 |
| P2 | `n518d` | `Game2/deepclue_ai/n518d/ai.py` | `n517e` 加两次 `others()`：stage2 后刷新 `102/103/104`，三证据问后刷新 `203/204/205`。 |
| P2 | `n514c` | `Game2/deepclue_ai/n514c/ai.py` | stage2 后携带 `102/104/103` 现场证据问。 |
| P2 | `n514h` | `Game2/deepclue_ai/n514h/ai.py` | `n514c` 加扑克短动机。 |
| P2 | `n515c` | `Game2/deepclue_ai/n515c/ai.py` | 现场证据问 + 接待者旧轨迹两问：异常发现、证词破绽。 |
| P3 | `n514f` | `Game2/deepclue_ai/n514f/ai.py` | 袁案低成本 704 探针：只遍历初始 `marks=True` NPC 问“谁在说谎”，命中投票关键词即停止。 |
| P3 | `n516d` | `Game2/deepclue_ai/n516d/ai.py` | 袁案省聊天 704 探针：只问初始 `marks=True` NPC 课程展示投票是否异常，命中投票关键词即停止。 |
| P3 | `n516e` | `Game2/deepclue_ai/n516e/ai.py` | 袁案极省聊天 704 探针：优先只问第二个 `marks=True` NPC 课程展示投票异常，验证老师顺序假设。 |
| P3 | `n514i` | `Game2/deepclue_ai/n514i/ai.py` | 袁案短动机替换，不新增袁案聊天。 |
| P3 | `n515d` | `Game2/deepclue_ai/n515d/ai.py` | 袁案基础问定位老师，再问“谁在说谎”。 |
| P3 | `n515e` | `Game2/deepclue_ai/n515e/ai.py` | `n515d` 加 `703` 手机照片追问。 |

## 上传模板

不要加 `--activate`。

```bash
python3 saiblo_tools.py upload-ai \
  --game-id 53 \
  --entity-name <label> \
  --create-if-missing \
  --language python \
  --source Game2/deepclue_ai/<label>/ai.py \
  --remark r \
  --wait-compile \
  --poll-interval 2 \
  --poll-max 60
```

## 房间评测模板

```bash
python3 Game2/tools/run_room_eval.py \
  --code-id <code_id> \
  --label <label> \
  --count 5 \
  --timeout 420 \
  --poll-interval 2 \
  --request-timeout 90
```

## 恢复队列脚本模板

如果目标账号是 `theend`，必须先确认 token 已切回该账号，再运行队列：

```bash
python3 Game2/tools/run_recovery_eval_queue.py \
  --expected-username theend \
  --labels n514d n514e n518a n518b n519a n519b \
  --count 5
```

说明：

- `--expected-username <username>` 会在任何上传前校验当前 token；也可以用环境变量 `SAIBLO_EXPECTED_USERNAME=<username>`。
- 当前本地 token 实测仍是 `thebeginning`，因此不能在目标为 `theend` 时直接跑恢复队列。
- 脚本只做中性上传和单人房间评测，不使用 batch，不上天梯，不带 `--activate`。
- 默认遇到第一个失败就停止；若只想收集恢复后的多候选故障信息，可加 `--continue-on-error`。

扩样规则：

- P0 先上传并评测安全版 `n514d/n514e`，各跑 `5` 个有效样本；若 `n514e` 复现 `n512a` 的 stage2 触发优势，再扩到 `12-16`。
- P1 每个候选先跑 `5` 个有效样本；若出现 `2707+` 且低尾不差于 `n511a`，扩到 `12-16`。`n518a/b` 是最低聊天扰动的 evidence-refresh 对照，应在 `n514d/e` 后、接待者聊天候选前插入；`n519a/b` 是更新后“新增剧本/NPC 名字混淆”的鲁棒性对照，应和 `n518a/b` 相邻评测。
- P2 只在 P1 没有明显退化时并行测；接待者问、证据问和分拆问都可能增加低尾。优先顺序为 `n516a/b`、`n516c`、`n517e/f`、`n518c/d`、`n517h/g`、`n517b/d`、`n514c/h`、`n515c`。
- P3 最后测；袁案历史负收益较多，除非 P1/P2 无法突破再扩样。

## 2026-05-07 10:00 UTC 队列修订

- `n515a/b/c` 的接待者问句已从“只问公馆异常/厨房刀具/门窗/血迹/面具”改成 `请说说聊天记录、宾客到达时间表，以及公馆内的异常发现。`。
- 修订原因：旧 `v52` match `8065213` 的 stage2 hint 明确要求这三类信息；只问异常可能无法稳定复现 `203/204/205` 证据解锁。
- `n514c-i/n515a-e` 的 Poker 名字解析已扩展为多模式：`X是个好的信息来源`、`X会是...好的信息来源`、`问问X关于...`、`接待者X知道...`。样例 `陆亦初/林晚舟/张子韩` 均能正确解析，避免中文姓名边界吞掉后续字。
- `n514e` 已改为纯 `n512a` 问法隔离版；`n514g` 已改为 stage2 成功才启用短动机。
- `n515c` 已改成 P2 高风险对照：保留现场证据问，接待者部分从合并 hint 单问改为旧 `v52` 中最贴近 `203/204/205` 刷新的两问，即“异常发现”和“证词破绽”。
- `n514f` 已从袁案全员基础问改为更省聊天的 704 探针；全员基础问方向已有历史低收益证据，当前更需要隔离“少量说谎问能否直接触发 704”。
- 十二个候选文件均已通过 `python3 -m py_compile`。
- `2026-05-07 10:14 UTC` 恢复探针仍卡在 `begin_match` 500，`n513a` 仍有两个长期 `未编译` code；不要上传新候选，避免继续制造长期 `未编译` code。

## 2026-05-07 10:29-10:39 UTC 队列修订

- `2026-05-07 10:26 UTC` 再跑 `n511a` 恢复探针，`room 918439` 仍表现为 `join` 500 但已坐入，`begin_match` 500。
- 当前 token 仍解析为 `thebeginning`；如果需要使用 `theend` 实体，必须先切 token 并重新核验。
- 新增 `n516a/b/c`，用于把 Poker stage2 后接待者路线拆成更细的净收益实验。它们都从 `n515b` 派生，只改变接待者追问，不改变 Poker 提交答案。
- 新增 `n516d/e`，用于 Yuan `704` 的省聊天对照。`n516d` 遍历初始 `marks=True` NPC，`n516e` 优先只问第二个 `marks=True` NPC 以验证老师顺序假设。
- 候选安全修订：`n514c-i/n515a-e/n516a-e` 已统一关闭 stderr 调试日志，避免上传后通过对局 API 泄露 hint、marks、问句和路线。
- 候选鲁棒性修订：Poker 信息源姓名优先从当前 `npcs` 中文名集合精确匹配 hint，fallback 正则不再覆盖已验证 `info_id`；Yuan 相关追问版会在聊天后刷新 `marks` 再确认 `marks=False` 凶手。
- `n514c-i/n515a-e/n516a-e` 已通过 `python3 -m py_compile`，但未上传、未开房间。
- 平台恢复后的执行顺序建议：先上传并测安全版 `n514d/e`，再测 `n514g` 与 `n515b/a`。如果 `n514e` 复现 `n512a` 的高 stage2 触发率，则插入 `n517a/c`，随后测 `n516a/b/c` 与 `n517e/f/h/g/b/d`，最后再测 `n514c/h/n515c` 和袁案 P3 候选。Yuan P3 内部优先 `n514f/n516d/n516e`，再测 `n514i/n515d/n515e`。旧 `n512a` 保留为历史 3 样本，不再作为默认扩样目标。
- `2026-05-07 10:42 UTC` 复核：`n511a` 的 19 个有效样本中 Rose/Z 可见最终进度恒定，低尾不应优先从 Rose/Z 大改入手；队列继续优先 Poker，再 Yuan。
- `2026-05-07 10:50 UTC` 恢复探针仍失败：`room 918471` 表现为 `join` 500 但已坐入，`begin_match` 500；继续不上传新候选。
- `2026-05-07 10:53 UTC` 新增 `n517a/b/c/d`，原因是 `n514e/n512a` 信息源问法历史 3/3 触发 Poker stage2，而此前接待者路线只从 `n511a` 问法派生。四个候选均 `DEBUG = False`，并通过 `python3 -m py_compile`。
- `2026-05-07 10:55 UTC` Poker 子任务复核认为 `203/204/205` 的最小触发应来自接待者“异常发现”，而不是聊天记录/到达时间表/证词破绽；新增 `n517e/f/g/h`，分别测试三证据精确问、电脑/冰柜/刀具低泄露问、自杀伪装谋杀手法文本叠加接待者问，以及不加接待者问的手法文本隔离。四者均 `DEBUG = False`，并通过语法检查。
- `2026-05-07 11:00 UTC` 非开赛检查仍显示 token 为 `thebeginning`，`entity 21072 / n513a` 两个 code 仍是 `未编译`；继续等待平台恢复，不上传新候选。

## 2026-05-07 11:10 UTC 队列修订

- 平台非开赛检查仍未恢复：`entity 21072 / n513a` 两个 code、`21073 / n514a`、`21074 / n514b` 均为 `未编译`。
- `entities --game-id 53` 仍返回 username `thebeginning`，`active=null`。
- Poker 复盘确认：旧 `v52` 中 `102/103/104` 是在 stage2 后显式 `others()` 才可见；`203/204/205` 也是接待者回答后再次 `others()` 才可见。当前高分候选多在聊天后直接 answer，可能没有把已满足的证据刷新成可计分进度。
- 新增 `n518a/b/c/d` 作为低扰动 evidence-refresh 候选：`n518a/b` 不新增聊天，只在 stage2 后刷新 `others()`；`n518c/d` 在接待者追问后再刷新 `others()`，用于隔离 `203/204/205` 是否需要显式取证据才计分。
- 四个候选均 `DEBUG = False`，通过 `python3 -m py_compile`；未上传、未开房。

## 2026-05-07 11:25 UTC 恢复探针补充

- `n511a` 恢复探针继续失败：`room 918519` 已坐入但 `begin_match` 返回 500。
- 旧稳定 `n506e` code_id `a63c0344959c4189beba83019bdc4c2b` 也失败：`room 918537` 已坐入但 `begin_match` 返回 500。
- 这确认当前不是单个 code 的问题，而是 Game53 单人房间启动链路仍未恢复。不要上传新候选，避免继续制造长期 `未编译` code。
- 本地差分进一步支持 `n518a/b` 前排验证：Poker stage2 只是约 `+50` 的叠加层，stage2 后显式 `others()` 是否额外计入 `102/103/104` 仍无 A/B 证据。
- 本地差分也说明 `n514e/n518b` 不能只看 stage2 触发率：`n512a` 历史 3/3 stage2 仍有两个 `2507`，其中低尾更可能来自 Rose/隐藏后案答案波动。
- `n512a` 的 `2507/2507/2707` 中，唯一 `2707` 的信息源首答明确含“聊天记录有问题”；两个 `2507` 首答没有稳定给出聊天记录。若 `n518b` 只能稳定 stage2 但不升低尾，后续应优先测 `n517a/n518c` 的接待者合并 hint 问，而不是立刻改 Yuan。
- 恢复后的实际执行顺序微调为：`n514d/e` 安全对照各 5 个有效样本，然后立即测 `n518a/b` 各 5 个有效样本，再进入 `n514g`、`n515b/a`、`n517a/c` 与后续接待者路线。

## 2026-05-07 11:45 UTC 鲁棒候选与恢复队列脚本

- 只读挖掘再次量化确认：当前所有 `2707` 样本共同条件是 Poker stage2、Rose 三项全对且 stage6 由“态度怪？”类问题触发、Z/F 高阶段；Yuan 进度不是冲顶必要条件。
- 更新后风险集中在两个实现点：固定 `range(6)` 可能漏掉新增剧本；Poker 信息源解析若先匹配 hint 中任意 NPC 中文名，遇到多个姓名时可能问错人。
- 新增 `n519a/b`：分别从 `n518a/b` 派生，只改鲁棒性，不改变 Rose/Z/Yuan 主路径和 Poker 答案文本。它们把主循环上限改为 `12` 案，Poker 信息源先按“好的信息来源/问问/接待者知道”等上下文正则解析，再在只有唯一姓名命中时回退；未知新增案默认优先提交 `marks=False` NPC。
- `n519a/b` 均 `DEBUG = False`，通过 `python3 -m py_compile`，未上传、未开房。
- 新增恢复评测脚本 `Game2/tools/run_recovery_eval_queue.py`，默认队列为 `n514d n514e n518a n518b n519a n519b`。dry-run 已验证只调用 `upload-ai --remark r --wait-compile` 和 `Game2/tools/run_room_eval.py`，不使用 batch，不带 `--activate`。
- `2026-05-07 11:43 UTC` 非开赛检查显示 `entity 21072 / n513a` 两个 code 仍为 `未编译`；当前 token 仍解析为 `thebeginning`。继续不上传新候选，等待低频 watcher 的房间恢复信号。
- `2026-05-07 11:48 UTC` watcher 的有效房间探针仍失败；这次 `POST /api/rooms/` 创建房间即返回 500。平台仍未恢复，下一次检查按 900s 间隔等待。
- `2026-05-07 11:56 UTC` 暂停前复核：watcher PID `677676` 仍在后台低频运行，当前命令不带 `--skip-room-probe` 或 `--require-compile-clear`；因此不会因为历史 `未编译` code 自行误判恢复，真正触发条件是 `create_single_player_match()` 成功。恢复后 callback 只运行一次 `run_room_eval.py --code-id a2b68a7ec9b84a59a8dfd836defd930c --label n511a_recovered_once --count 1`，不上传候选、不使用 batch、不上天梯。
- `2026-05-07 11:59 UTC` 加固 `run_recovery_eval_queue.py`：新增 `--expected-username` / `SAIBLO_EXPECTED_USERNAME` 账号守卫，在任何上传前调用 profile 校验当前 token。已验证 `--expected-username thebeginning` dry-run 成功，而 `--expected-username theend` 会在上传前失败退出；这可避免恢复后因 token 未切回目标账号而误上传候选。
- `2026-05-07 12:03 UTC` watcher 第 2 次实际房间探针仍失败：`POST /api/rooms/` 创建房间返回 500。继续等待低频恢复信号，不上传新候选。

## 判定口径

- 第一指标：有效样本最低分。
- 第二指标：均值。
- 第三指标：最高分。
- 单局高分不能定版；`2707` 目前只是最高观测，不是稳定上限。
- 若平台失败产生 `0` 或 `end_state != OK`，不计入有效样本，但要记录故障。
