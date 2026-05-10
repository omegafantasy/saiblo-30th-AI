# Game53 DeepClue Saiblo 对局元信息与平均分看板

目标：持续同步 Saiblo `game_id=53` 的所有对局元信息，按独立 AI 版本 `code_id` 统计有效先手样本的平均分，并在本地 `elo_web` 看板展示。

## 统计口径

Game53 是 DeepClue，本质不是双人强弱对战。

- 对局详情和列表 API 的 `info[0].score` 是该场有效 raw score。
- `info[1]` 如果存在，只是占位或另一份独立自跑样本的上下文，不参与该场计分。
- 不按胜负、rank、对手强度或 Elo 计算；榜单按 `avg_score` 从高到低排序。
- 评分单位仍是 `code_id`，不是用户名或 AI 名。
- `评测成功 + seat0 有 code_id + seat0 有 score` 才计入平均分。
- `准备中`、`评测中`、`队列中` 等状态进入等待队列并低频轮询；终态失败只记录状态，不计入平均分。

## 信息来源

- 对局列表 API：`/api/matches/?game=53&limit=...&offset=...`
- 对局详情 API：`/api/matches/{match_id}/`

当前已确认：列表/详情中的 `info` 已包含用户名、AI 名、版本、`code.id`、备注、`end_state` 和 `score`，所以 Game53 不需要下载 replay。

## 本地存储

脚本：`saiblo_game53_score.py`

默认路径：

- SQLite：`autolab/runtime/saiblo_game53_score/matches.sqlite3`
- Web 快照：`autolab/runtime/saiblo_game53_score/latest.json`
- 后台日志：`autolab/runtime/saiblo_game53_score/crawler.log`

SQLite 表：

- `matches`：对局状态、创建时间、是否成功、先手分数、轮询状态。
- `match_players`：每局所有 `info` seat 的 username、user_id、AI 名、版本、code id、remark、rank/score、end_state。
- `versions`：按 `code_id` 汇总 AI 版本元信息。
- `crawl_state`：最近同步状态、token 来源、列表/详情轮询摘要、错误信息。

## 同步策略

默认每轮：

1. 用有效 Saiblo bearer token 分页扫描 `/api/matches/?game=53`。
2. 对列表里发现的每场 Game53 对局保存轻量元信息。
3. 对未完成状态维护等待队列，并按 backoff 拉 `/api/matches/{match_id}/`。
4. 对成功但缺少 `info[0].score` 或 `info[0].code.id` 的对局补拉详情。
5. 对终态失败记录状态和错误，不继续下载或计分。

默认列表/详情请求是串行请求，`--request-delay` 默认为 `0.25s`，避免对 Saiblo 接口造成高并发压力。

## 常用命令

单轮同步：

```bash
python3 saiblo_game53_score.py crawl
```

后台启动 crawler：

```bash
scripts/saiblo_game53_score_start.sh
```

查看状态：

```bash
scripts/saiblo_game53_score_status.sh
```

停止 crawler：

```bash
scripts/saiblo_game53_score_stop.sh
```

启动本地看板：

```bash
scripts/elo_web_start.sh
```

看板 API 包含 `views.saiblo_game53`，网页中可通过顶部 `<-` / `->` 在 Game1 Elo 和 “Saiblo Game53 DeepClue AI 版本平均分” 两页之间切换。

看板默认按用户名折叠：每个用户只显示其当前全量排序中平均分最高的 AI 版本，`Rank` 仍保留该版本在全量 AI 版本榜里的总排名；顶部开关可切回全部版本。

Game53 表格每行右侧提供两个操作：

- `复制`：复制该 AI 版本完整 `code_id`。
- `对局`：打开该版本最近一场计分样本的 Saiblo 对局页。

## 与 Game1 的区别

- Game1 使用 Elo，考虑对手 Elo、胜负、血量差和样本数。
- Game53 不使用 Elo，只统计先手有效 raw score 的均值、最高分、最低分、标准差和样本数。
- Game53 不下载 replay，因为分数在轻量元信息里已经足够。
