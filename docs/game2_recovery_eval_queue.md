# Game2 Recovery Eval Queue

更新时间：`2026-05-08 09:00 UTC`

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

## 2026-05-08 02:46 UTC 恢复后实测队列结论

- 当前 token 复核为 `thebeginning / user_id=2646`；恢复队列继续要求显式传入 `--expected-username thebeginning`，避免上传到错误账号。
- 平台编译和单人房间评测链路已恢复；本轮只使用单人房间，不使用 batch，不带 `--activate`。
- `n518b` 仍是当前稳定基线：15 个有效样本 `2707 x10, 2667 x3, 2657 x2`，code_id `ccab056263c540c4b61c1fec84828ac1`。
- `n520c` 和 `n520e` 可达 `2757`，但扩样均出现 `2517`；`n520f` 5 样本中 `2517 x2`。这些 stage3 路线不能进入稳定队列。
- `n521a/b` 是保守 stage1 兜底问法：`n521a` 总 12 样本出现 `2507`，`n521b` 8 样本出现 `2457`，均不能替代 `n518b`。
- `n521c/d` 是 Poker stage3 答案文本对照：`n521c` 为 `2557 x4, 2707 x1`，`n521d` 已完成 4 样本均 `2557`，均丢弃。
- 队列优先级更新：若继续恢复队列，默认稳定候选仍应优先扩 `n518b` 或从 `n518b` 附近做低扰动 A/B；不要把 `n520c/e` 这类高均值 stage3 版本直接作为稳定版本。
- 对 stage3 的后续探索必须先解决隐藏低尾可预测性。当前已知可见特征，包括 Poker stage、`201-205` 证据、Rose 三项、Z err8、Yuan stage、医生提示、接待者 NPC，都无法可靠区分 `2517/2717/2757`。

## 2026-05-08 03:09 UTC 后续队列结论

- `n518b` 已扩到 25 个有效样本：`2707 x16, 2667 x7, 2657 x2`，min `2657`、avg `2691.8`、max `2707`。继续作为稳定基线。
- `n516d/e` 两个 Yuan 探针均已完成 5 局并出现低尾：`n516d` 为 `2707 x1, 2657 x3, 2617 x1`；`n516e` 为 `2707 x1, 2657 x2, 2617 x1, 2507 x1`。Yuan 704 省聊天方向从当前队列移除。
- `n520d` 扩样后为 7 局 `2757 x3, 2717 x2, 2657 x1, 2557 x1`，医生追问不能作为稳定 stage3 路线。
- 新增 `n522a/b` 门控候选用于过滤 Poker 首答中的高风险词。`n522a` 2 局出现 `2617`；`n522b` 7 局为 `2757 x2, 2717 x2, 2707 x1, 2657 x1, 2617 x1`。两者均丢弃。
- 当前不建议继续自动跑旧 P2/P3 队列；如继续探索，应先提出新的可解释特征或更保守的 stage2 改动，再小样本单房评测。

## 2026-05-08 07:11 UTC n525/n527 队列结论

- 当前 token 复核为 `thebeginning / user_id=2646`；本轮仍只用单人房间评测，不使用 batch，不上天梯。
- 上传实体名 `n525a/b/c/n526a/b/n527a-h` 和备注 `r` 均保持中性；候选 `DEBUG = False`，stderr 未泄露策略。
- `n525a` 合计 20 局为 `2757 x9, 2717 x7, 2707 x1, 2667 x1, 2657 x1, 2557 x1`，医生追问不稳定。
- `n525b` 合计 25 局为 `2757 x20, 2717 x4, 2517 x1`，身份关系追问不稳定。
- `n527a` 5 局为 `2757 x4, 2717 x1`，接待者最小追问初筛最好，但未扩样。
- `n527e` 合计 30 局为 `2757 x22, 2717 x6, 2657 x1, 2517 x1`。它一度 20 局无低尾，但扩样复现 `2517`，不能作为稳定版。
- `n527b/c/d/g/h` 均在 5 局内出现 `<=2657` 或 `2517`；`n527f` 还出现 `score=0/end_state=None` 的交互预算风险，全部从候选队列移除。
- 最新生成汇总见 `docs/generated/game2_room_eval_summary.md` 和 `docs/generated/game2_room_score_factors.md`。
- 当前队列停止；稳定基线继续是 `n518b`，code_id `ccab056263c540c4b61c1fec84828ac1`，25 局 min `2657`、avg `2691.8`。

## 2026-05-08 07:40 UTC n527 扩样与 n528 对照结论

- `n527a` 追加 4 个有效样本后累计 9 局为 `2757 x6, 2717 x2, 2557 x1`；小样本高分被低尾证伪。
- `n527g` 追加 7 个有效样本后累计 12 局为 `2757 x9, 2717 x1, 2657 x1, 2557 x1`；Rose 问句重排不能过滤 stage3 同形低尾。
- `n528a` 从 `n527g` 派生，删除两个 Rose like 型问句，5 局为 `2717 x4, 2627 x1`；删除这些问句会降低上限并可能漏掉 Rose stage6。
- `n528b` 从 `n527g` 派生，把“喜欢你？”改成关系问句，5 局为 `2757 x3, 2657 x1, 2557 x1`；非 like 文本可达 `2757`，但不能消除 `2557`。
- 当前稳定基线仍为 `n518b`；`n527e/g`、`n528a/b` 均不进入稳定队列。

## 2026-05-08 07:49 UTC n529 小实验

- 只读复盘 103 个 Poker stage3 样本后，Rose stage6 触发词与 `2717/2757` 有强相关：stage3 且触发词为 like/好 类型的样本集中在 `2717/2517`，非 like 触发集中在 `2757/2557`。
- `2517/2557` 相当于在 `2717/2757` 基础上额外掉约 `200`，更像某个后案答案组件隐藏 false；当前按 Z/F 角色、Poker 信息源/接待者、Yuan `marks=False` 嫌疑人仍没有稳定过滤特征。
- 新增 `n529a`：从 `n525b` 派生，只重排 Rose 末段，让“态度怪/冷淡/代替上台”先于 like 型问句，同时保留 `n525b` 的 Poker 身份关系追问路线。
- 新增 `n529b`：在 `n529a` 基础上，仅当 Poker 两个信息源问句后仍 `stage<2` 时，加一句“手机、聊天记录和随身物品”兜底问。
- `n529a/b` 均已通过 `python3 -m py_compile`，`DEBUG = False`；已用中性实体名和备注 `r` 并行上传、开单人房间各 5 局，等待结果。

## 2026-05-08 09:00 UTC n529-n531 评测回填

- `n529a`，code_id `b93415861eb8457d933150ac5396dddc`，5 局 `2557 x3, 2617 x1, 2757 x1`，丢弃。
- `n529b`，code_id `97dd8a7454534ab4aa62f0527e4d970a`，初筛 5 局 `2757 x1, 2717 x3, 2657 x1`；`expand1` 10 局 `2757 x7, 2717 x3`；`expand2` 第 3 局出现 `2457` 后停止。累计 18 局 `2757 x10, 2717 x6, 2657 x1, 2457 x1`，丢弃。
- `n525c` 补扩累计 12 局 `2757 x6, 2717 x3, 2707 x2, 2617 x1`；Yuan 嫌疑人证据追问方向不稳定。
- `n530a`，code_id `44452e96bdf14dff8ce1a40d996f307d`，累计 9 局 `2757 x7, 2717 x1, 2517 x1`，丢弃。
- `n530b`，code_id `72ebafeb7fbd4ae59b7627d8c9cdaa29`，3 局 `2667, 2507, 2467`，提前停止。
- `n530c`，code_id `d2496ac3333a4d90bb8d72b341f5bdce`，5 局 `2757 x3, 2657 x1, 2617 x1`，丢弃。
- `n531a`，code_id `fd0e8e0b24f944d491ded1b1663e3915`，5 局 `2757 x2, 2717 x2, 2557 x1`，丢弃。
- `n531b`，code_id `5eaa1d3cb95f4f939cee6c668a2d533f`，初筛 5 局全 `2757`；扩样后累计 11 局 `2757 x9, 2717 x1, 2557 x1`，丢弃。
- 本轮结论：`n529b` 和 `n531b` 都证明 stage3 路线存在小样本稳定假象。当前稳定版仍为 `n518b`，code_id `ccab056263c540c4b61c1fec84828ac1`，25 局 `2707 x16, 2667 x7, 2657 x2`。

## 2026-05-08 10:48 UTC n532-n537 评测回填

- 本轮继续只用 Game53 单人房间评测，不使用 batch，不上天梯；上传实体名 `n532a/b/c/n533a/n534a/n535a/n536a/n537a/b/c/d` 与备注 `r` 均保持中性，账号守卫为 `thebeginning / user_id=2646`。
- `n532a`，code_id `72bb08a99f2c4c5ab865eb8ed80ef72b`，5 局 `2707 x2, 2667 x2, 2657 x1`。只改 Rose 明确假冒兜底，基本等同 `n518b` 小样本，未见收益。
- `n532b`，code_id `e97f3c72a3d14b9e8e4f05b2f2fa629b`，5 局 `2757 x2, 2717 x1, 2557 x2`，丢弃。
- `n532c`，code_id `64681042e873470684a03a737ce682f4`，5 局 `2757 x3, 2717 x1, 2557 x1`，丢弃。
- `n533a`，code_id `65864a8c337046e99822b1540d1d96d2`，累计 9 局 `2757 x5, 2717 x3, 2617 x1`；低尾来自 Poker stage1 卡住，丢弃。
- `n534a`，code_id `b6e65d342e00413b8a725fc46aaedb31`，累计 20 局 `2757 x10, 2717 x6, 2657 x2, 2557 x2`；stage3 占优但仍有 `2557` 隐藏低尾，不能作为稳定版。
- `n535a`，code_id `7d5b7fa5bf404b0abecb7f2a1c040d6f`，5 局 `2757 x2, 2717 x1, 2557 x1, 2517 x1`；移除 stage3 后关系追问反而更差，丢弃。
- `n536a`，code_id `9f0955053f1344d7b656187c39b347e8`，5 局 `2707 x2, 2667 x2, 2507 x1`；Rose 动机与顺序改动不安全，丢弃。
- `n537a`，code_id `3f1894a51daa4337b494476a93d9f640`，累计 10 有效局 `2707 x6, 2667 x3, 2617 x1`。显式“不是本人/冒充”兜底不能稳定提升 Rose，出现 `2617` 后停止扩样。
- `n537b`，code_id `11ba3fd0bdf247238e1dadf3b4c3c399`，5 局 `2707 x2, 2667 x1, 2657 x1, 2257 x1`。只后置 like 问句会引入严重低尾，丢弃。
- `n537c`，code_id `36b8cfc5ecb3497cb314b8fb175e1062`，5 局 `2557 x2, 2517 x3`；`n537d`，code_id `e4e239b7813645788ae7599aabcde97e`，5 局 `2557 x2, 2517 x2, 2357 x1`。Poker `203/204/205` 虽指向自杀伪装剧情，但把最终手法或凶手字段改向自杀均为明显负收益。
- 新增归因：`n534a` 的 `2557` 可在 Rose 三项全真、Poker stage3 全证据、Z 双 `KeyError('8')` 的可见同形条件下发生；`n537c/d` 说明 Poker 最终答案字段很可能不按剧情自杀文本计分，当前高分仍更依赖调查进度而不是正确解释 `203/204/205`。
- 当前稳定结论不变：`n518b` 仍是唯一经过 25 局且最低分 `>=2657` 的版本。后续若继续探索，应优先寻找新的可观测低尾过滤特征；没有新特征时，不建议继续扩 stage3 答案文本或 Rose 尾段微调。

## 2026-05-08 12:48 UTC n538-n540 评测回填

- 本轮继续只用 Game53 单人房间评测，不使用 batch，不上天梯；上传实体名 `n538a/b/c/n539a/b/c/d/n540a` 与备注 `r` 均保持中性，账号守卫为 `thebeginning / user_id=2646`。
- `n538a`，code_id `3560b9409de24a108a032ed15b76cc97`，5 局 `2757 x2, 2717 x1, 2657 x1, 2557 x1`，Poker 信息源解析回退无收益。
- `n538b`，code_id `aeb9674e0abf4052807157af57fbd99f`，首 5 局 `2757 x3, 2717 x2`，但扩样第 1 局出现 `2517`；Rose 假冒兜底不能稳定。
- `n538c`，code_id `5f0ce8e49df64a20a3d9eee2ad815cb4`，5 局 `2757 x2, 2717 x2, 2617 x1`，合并改动不稳。
- `n539a`，code_id `2b890369c8eb4e168695bf966f4409de`，累计 8 局 `2757 x5, 2717 x2, 2517 x1`，Rose like 前后顺序不能消除低尾。
- `n539b`，code_id `e1d1f4eecbdf4167a5405902fec3878b`，5 局 `2707 x4, 2657 x1`，保守拒绝语义接待者兜底基本等同基线小样本。
- `n539c`，code_id `906c4545e04c4ab3aa6d2bb40972641d`，5 局 `2757 x4, 2717 x1`，但差分比 `n539d` 更大，未作为主扩样对象。
- `n539d`，code_id `fb11515cb46243a79491fbbb3dbf2170`，累计 36 局 `2757 x23, 2717 x10, 2657 x2, 2557 x1`。前 27 局最低仅 `2657`，但 expand3 复现 `2557`，不能替代稳定版。
- `n540a`，code_id `04dd107dc52e459a8ac27b4d7212e0ca`，10 局 `2757 x4, 2717 x3, 2617 x1, 2557 x1, 2517 x1`，从 `n525b` 只跳过已达 stage3 后总括问是负收益。
- 当前结论：`n539d` 是高均值方向中最接近稳定的一次，但 `8091812=2557` 仍满足 Rose TTT、Poker stage3 全证据、Z 双 err8、Yuan stage1 的可见同形条件；稳定版本仍为 `n518b`。

## 2026-05-08 14:17 UTC n541-n543 队列结论

- 本轮继续只用 Game53 单人房间评测，不使用 batch，不上天梯；上传实体名 `n541a/b/c/d/n542a/b/n543a/b` 与备注 `r` 均保持中性，账号守卫为 `thebeginning / user_id=2646`。
- `n541a`，code_id `ed84bfbf04e44b909b23dff74345cf5a`，累计 8 局 `2757 x4, 2717 x3, 2617 x1`。Rose 已达 stage6 后跳过“你对 X 好？”不是稳定修复。
- `n541b`，code_id `322f1183188d4c85b51bf40ddc30926e`，5 局 `2757 x3, 2657 x1, 2557 x1`。显式上台兜底仍有低尾。
- `n541c`，code_id `38038949c06340539fd28a096075dc6d`，累计 9 局 `2757 x5, 2717 x2, 2657 x1, 2617 x1`。Poker stage1 拒证后换接待者兜底不能稳定。
- `n541d`，code_id `1c9be70becca4f0a881a08af69cde3d4`，首 5 局 `2757 x4, 2717 x1`，但包含已在 `n541a` 扩样中证伪的 Rose 跳过策略，未继续扩样。
- `n542a`，code_id `46240e41938645158571c29c33e6afbc`，5 局 `2757 x2, 2717 x2, 2557 x1`。拒证后转回信息源本人索证仍不能过滤 stage3 低尾。
- `n542b`，code_id `bf3ccfa136f24417a29ca5b03848f721`，首 5 局全 `2757`，扩样后累计 9 局 `2757 x7, 2717 x1, 2557 x1`。再次证明 5/5 高分不能定版。
- `n543a`，code_id `24e4feb1253d4c26a4ca8e546a3dbacf`，5 局 `2707 x3, 2667 x1, 2417 x1`。从 `n518b` 保守救 stage2 的泛化问句破坏稳定。
- `n543b`，code_id `d939ed925f784f62b13a1c6370ee0a46`，首 5 局 `2707 x3, 2667 x2`，扩样后累计 15 局 `2707 x9, 2667 x5, 2507 x1`。收窄的保守 stage2 救援也不能替代 `n518b`。
- 当前队列停止；稳定基线仍为 `n518b`，code_id `ccab056263c540c4b61c1fec84828ac1`，25 局 `2707 x16, 2667 x7, 2657 x2`。除非出现新的可观测低尾过滤特征，不建议继续扩同类 Poker stage3、拒证兜底、信息源索证或保守 stage2 救援问法。

## 判定口径

- 第一指标：有效样本最低分。
- 第二指标：均值。
- 第三指标：最高分。
- 单局高分不能定版；`2757` 目前只是最高观测，不是稳定上限。
- 若平台失败产生 `0` 或 `end_state != OK`，不计入有效样本，但要记录故障。
