# Game2 Recovery Eval Queue

更新时间：`2026-05-07 10:15 UTC`

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

恢复标准：

- 上传接口不再产生新的长期 `未编译` code。
- 单人房间不再卡在 `begin_match` 500。
- `run_room_eval.py` 的失败 summary 若仍失败，应保留 `room_id`，便于继续诊断。

## 优先级

| priority | label | source / code_id | 目的 |
| --- | --- | --- | --- |
| P0 | `n512a` | `673e54c862394b58a2ce790b63416e55` | 已上传，先扩到 `12-16` 个有效样本，验证 `2707/2507` 分布。 |
| P1 | `n514d` | `Game2/deepclue_ai/n514d/ai.py` | 低风险对照：扑克信息源优先从 hint 中文名映射，失败再用唯一 `marks=True`，不追加证据问。 |
| P1 | `n514e` | `Game2/deepclue_ai/n514e/ai.py` | `n512a` 第一问的纯隔离版：案发现场+手中证据两问，不加证据追问、不加短动机。 |
| P1 | `n514g` | `Game2/deepclue_ai/n514g/ai.py` | `n514d` 的条件短动机版：只有 Poker stage2 成功后才把 motivation 从 `未知` 改成短动机。 |
| P1 | `n515b` | `Game2/deepclue_ai/n515b/ai.py` | `n514d` 加 stage2 后接待者合并 hint 单问，不加扑克短动机。 |
| P1 | `n515a` | `Game2/deepclue_ai/n515a/ai.py` | `n515b` 加条件短动机，只有 Poker stage2 成功后改 motivation。 |
| P2 | `n514c` | `Game2/deepclue_ai/n514c/ai.py` | stage2 后携带 `102/104/103` 现场证据问。 |
| P2 | `n514h` | `Game2/deepclue_ai/n514h/ai.py` | `n514c` 加扑克短动机。 |
| P2 | `n515c` | `Game2/deepclue_ai/n515c/ai.py` | 现场证据问 + 接待者旧轨迹两问：异常发现、证词破绽。 |
| P3 | `n514f` | `Game2/deepclue_ai/n514f/ai.py` | 袁案低成本 704 探针：只遍历初始 `marks=True` NPC 问“谁在说谎”，命中投票关键词即停止。 |
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

扩样规则：

- P0 `n512a` 先补到 `12-16` 个有效样本。
- P1 每个候选先跑 `5` 个有效样本；若出现 `2707+` 且低尾不差于 `n511a`，扩到 `12-16`。
- P2 只在 P1 没有明显退化时并行测；证据问和接待者问都可能增加低尾。
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

## 判定口径

- 第一指标：有效样本最低分。
- 第二指标：均值。
- 第三指标：最高分。
- 单局高分不能定版；`2707` 目前只是最高观测，不是稳定上限。
- 若平台失败产生 `0` 或 `end_state != OK`，不计入有效样本，但要记录故障。
