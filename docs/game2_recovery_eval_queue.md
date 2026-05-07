# Game2 Recovery Eval Queue

更新时间：`2026-05-07 09:45 UTC`

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
| P1 | `n514d` | `Game2/deepclue_ai/n514d/ai.py` | 低风险对照：扑克信息源从唯一 `marks=True` 取，不追加证据问。 |
| P1 | `n514g` | `Game2/deepclue_ai/n514g/ai.py` | `n514d` 加扑克短动机，验证 stage2 后直接答案是否加分。 |
| P1 | `n515b` | `Game2/deepclue_ai/n515b/ai.py` | `n514d` 加 stage2 后接待者最小异常问，不加扑克短动机。 |
| P1 | `n515a` | `Game2/deepclue_ai/n515a/ai.py` | `n515b` 加扑克短动机。 |
| P2 | `n514c` | `Game2/deepclue_ai/n514c/ai.py` | stage2 后携带 `102/104/103` 现场证据问。 |
| P2 | `n514h` | `Game2/deepclue_ai/n514h/ai.py` | `n514c` 加扑克短动机。 |
| P2 | `n514e` | `Game2/deepclue_ai/n514e/ai.py` | `n512a` 问法加现场证据追问。 |
| P2 | `n515c` | `Game2/deepclue_ai/n515c/ai.py` | 现场证据问 + 接待者异常问叠加。 |
| P3 | `n514f` | `Game2/deepclue_ai/n514f/ai.py` | 袁案只加全员基础问，保留 `marks=False` 凶手。 |
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

## 判定口径

- 第一指标：有效样本最低分。
- 第二指标：均值。
- 第三指标：最高分。
- 单局高分不能定版；`2707` 目前只是最高观测，不是稳定上限。
- 若平台失败产生 `0` 或 `end_state != OK`，不计入有效样本，但要记录故障。
