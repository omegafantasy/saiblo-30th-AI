# Game2 Batch 与结果分析机制

## 1. 关键新发现

虽然 `recent --game-id 53` 为空，`matches` 列表也不直接暴露 Game2 的日常评测，但前端与 API 实测表明：

- `POST /api/batches/` 可用于 `game 53`
- `GET /api/batches/<batch_id>/` 会返回一组内部 `matches`
- 每个内部 match 都包含：
  - `id`
  - `state`
  - `info[2]`
  - 每个玩家的 `rank / score / end_state / code`

更关键的是：

- 对已完成的内部 match，可进一步访问 `GET /api/matches/<match_id>/`
- 并下载 `GET /api/matches/<match_id>/download/`
- 下载文件是完整调查轨迹，不是单纯分数

因此 Game2 不是“只有榜单一个分数点”，而是存在可用的回放分析链。

## 2. 当前脚本

### 2.1 提交与榜单跟踪

脚本：

- `Game2/tools/submit_and_track.py`

作用：

- 上传单文件 AI
- 等待编译
- 激活版本
- 轮询榜单直到当前 code_id 出现并稳定
- 保存归档目录与最新 markdown/json

产物：

- `Game2/runtime/submissions/<timestamp>_<entity>_v<version>/`
- `docs/generated/game2_latest_submission.md`
- `docs/generated/game2_latest_submission.json`

### 2.2 Batch 横向评测与自动回放抓取

脚本：

- `Game2/tools/run_batch_eval.py`

作用：

- 读取当前活跃 code
- 从榜单选前 `k` 个对手 code
- 创建 batch
- 轮询直到 batch 完成或超时
- 汇总每个对手的双边独立跑分
- 自动抓取所有已结束内部 match 的详情与下载文件
- 自动生成每个 match 的结构化分析
- 对 `评测失败` 的 match 也会单独归档 `detail / analysis`

产物：

- `Game2/runtime/batches/<timestamp>_<entity>_batch_<batch_id>/summary.json`
- `Game2/runtime/batches/<timestamp>_<entity>_batch_<batch_id>/matches/<match_id>/match_detail.json`
- `Game2/runtime/batches/<timestamp>_<entity>_batch_<batch_id>/matches/<match_id>/match_download.json`
- `Game2/runtime/batches/<timestamp>_<entity>_batch_<batch_id>/matches/<match_id>/analysis.json`
- `Game2/runtime/batches/<timestamp>_<entity>_batch_<batch_id>/matches/<match_id>/analysis.md`
- `docs/generated/game2_latest_batch.md`
- `docs/generated/game2_latest_batch.json`

### 2.3 单场回放分析

脚本：

- `Game2/tools/analyze_match.py`

作用：

- 拉取 `match` 详情
- 下载 `match` 轨迹
- 统计每个剧本的：
  - 提问步数
  - 阶段推进
  - 每个 NPC 被问次数
  - 证据出示次数
  - 最终答案与正确性
  - 运行时间与内存样本

## 3. 关键语义修正

Game2 batch 中每个对手对应的是“一对 matches”，不是一场传统双边对局。

更准确的解释是：

- pair 中有两个 `match`
- 每个 `match` 只代表“第一个 code 自己的一次独立跑分”
- 该 `match` 里第二个 code 的 `score=0` 只是占位，不能当真分

因此比较两个 AI 时，必须取：

- `my_score` = pair 中“我方 code 在第一个位置”的那场 raw score
- `opp_score` = pair 中“对手 code 在第一个位置”的那场 raw score

不能再把单场里的两边 score 直接相减或平均。

另一个修正：

- `exit_code=9` 并不等于本场无效
- 已观察到成功出分的对局同样可能出现 `exit_code=9`
- 判断有效性应以：
  - `match.state`
  - `end_state`
  - 是否有 replay/download
  - 是否拿到有效 raw score
  为准

## 4. 当前解释口径

对 Game2，后续分析应区分三层：

- 榜单分数：最终目标，最重要
- batch 结果：横向比较辅助信号，用来判断与前几名相比的差距
- match 回放：具体调查过程与失败原因分析

仍然不能沿用 Game1 的：

- Elo
- 本地对战评测

## 5. 当前限制

当前仍缺少这些信息：

- 官方直接给出的 token 使用明细
- 每次 `call_llm` 的真实 prompt / completion 计费统计
- 本地可复现 judge

因此当前最现实的迭代方式是：

1. 修改 prompt / 调查策略
2. 提交并记录榜单分数
3. 运行 batch 对比前几名
4. 下载已完成 match 回放，分析调查路径和最终答案
5. 用版本间分数变化做反推

## 6. 已知重要发现

- `v2` 对 `admin/跑通测试` 的一侧对局 `7421777` 中：
  - 这是对手自己的独立跑分
  - 对手 raw score `2357`
- 下载到的对手轨迹显示：
  - 第一个剧本提问 `42` 步
  - 第二个剧本提问 `41` 步
  - 两个剧本均 `murderer / motivation / method` 全对
- 这说明当前高分策略更接近：
  - 少量或不依赖中途 `call_llm`
  - 高频、稳定、低风险的直接调查
  - 先把阶段和线索打满，再做最终结论

截至 `2026-03-11` 已确认的我方真实跑分：

- `v2` / batch `75631`：`607`
- `v6` / batch `75635`：`371`
- `fast probe` / batch `75636`：`107`

已确认失败的版本：

- `v3` / batch `75632`：我方主跑 `评测失败`
- `v4` / batch `75633`：我方主跑 `评测失败`
- `v5` / batch `75634`：我方主跑 `评测失败`

## 7. 额外修正

`2026-03-11` 又补了一处关键缺口：

- 之前 `run_batch_eval.py` 只会分析 `评测成功` 的 match
- 这会导致失败版本没有结构化归档，难以判断是逻辑差还是平台失败

现在的脚本行为是：

- 只要 match 不再是 `准备中 / 评测中`
- 就会保存：
  - `match_detail.json`
  - `match_download.json`（若可取）
  - `analysis.json`
  - `analysis.md`

即便失败对局拿不到 replay，也会记录：

- `state`
- `error / err`
- `message_present`
- `download_error`
- 玩家与 code 信息

这样后续比较 `v2`、重传 `v2`、`v7+` 的失败模式时，不再依赖人工临时抓接口。

## 8. 已确认的后端异常

`2026-03-11` 对 `7422408`（`admin/跑通测试` 的成功高分对局）重新分析后，`err` 字段里已经能解码出后端异常日志。

关键信息：

- 即使对局最终 `评测成功`
- 第二个剧本在 `stage 8` 后继续 `chat`
- 仍会触发：

```text
File "/sandbox/working/app/services/Stage.py", line 114, in update_npc_question_marks
KeyError: '8'
```

含义：

- Game2 平台在高阶段存在已确认的逻辑缺陷
- “深挖到高 stage 后继续追问”本身有稳定性风险
- 后续版本应显式避免在 `stage >= 8` 后继续聊天

## 9. 当前最重要的分析结论

`2026-03-11` 继续对 `v2 / v7 / admin` 的实际回放做并排对比后，已经可以确认：

- 同一份 `v2` 源码不是稳定输出：
  - `7421776`：`607`
  - `7422137`：`407`
  - `7422139`：`607`
- 这三场都不是“代码不同”，而是：
  - 中途 `call_llm` 规划问题存在随机性
  - 最终 `call_llm` 归纳答案也存在随机性
- 因此 Game2 不能再拿单次 batch 分数直接判断版本优劣，至少要区分：
  - 代码改动带来的趋势
  - 同码自带的随机波动

对 `v7`（线上 `version 8`，match `7422058`）的结论也已经明确：

- 分数只有 `407`
- 相比 `v2`，第一案从 `范敏敏` 进一步偏到了 `叶文潇`
- 额外增加的多条“证据驱动追问”并没有提高正确率，反而强化了错误嫌疑人
- 这说明当前阶段更深、更细的追问并不自动提升效果，反而可能把最终总结推向错误叙事

对高分对手 `admin/跑通测试` 的结论是：

- 它确实通过更多问题推进到了更深 stage，并且两案全对
- 但它的问法明显更短、更直接，而不是我方这种长句综合问法
- 同时它也会踩到 `stage 8` 的后端异常日志

因此当前最合理的下一步不是盲目继续堆问题，而是：

1. 先降低 `call_llm` 带来的随机性
2. 让问题模板更短、更直接、更可复现
3. 用重复 batch 验证“同码波动区间”
4. 在确认稳定收益前，不再因为单场高分就切主线
