# Game1 Saiblo 对局元信息与 AI 版本 Elo

目标：从 Saiblo Game1 `game_id=48` 的对局 `#7981000` 起持续同步所有对局元信息，按 AI 代码版本 `code_id` 计算稳定 Elo，并在本地 `elo_web` 看板展示。

## 信息来源

- 游戏页：`https://www.saiblo.net/game/48?id=2`
- 游戏/排行榜 API：`/api/games/48/`、`/api/games/48/ladders/`
- 对局列表 API：`/api/matches/?game=48&limit=...&offset=...`
- 对局详情 API：`/api/matches/{match_id}/`
- 回放下载 API：`/api/matches/{match_id}/download/`

目前确认：

- `ladders` 公开可读，可拿到榜单上的 `username`、`entity.name`、`version`、`code.id`、平台分。
- `matches` 列表和单局详情需要有效 Saiblo bearer token。
- 单局详情 `info` 中包含双方用户名、AI 名、版本、code id、备注、rank/score、end_state。
- Game1 回合数与最终双方基地血量不在轻量详情字段中，需临时下载 replay；解析 JSON 数组末帧 `round_state.camps` 和帧数后立即丢弃 replay，不落盘保存完整回放。

## 本地存储

脚本：`saiblo_game1_elo.py`

默认路径：

- SQLite：`autolab/runtime/saiblo_game1_elo/matches.sqlite3`
- Web 快照：`autolab/runtime/saiblo_game1_elo/latest.json`
- 后台日志：`autolab/runtime/saiblo_game1_elo/crawler.log`

SQLite 表：

- `matches`：对局状态、创建时间、是否成功、回合数、最终血量、胜者、轮询状态。
- `match_players`：每局双方 seat、username、user_id、AI 名、版本、code id、remark、rank/score、end_state。
- `versions`：按 `code_id` 汇总的 AI 版本元信息，榜单信息会补充到这里。
- `supplement_requests`：自动补局请求，记录目标版本、对手版本、房间/对局 id、创建状态和补局原因。
- `crawl_state`：最近同步状态、token 来源、错误信息、列表/详情轮询摘要。

## 同步策略

默认每轮：

1. 拉取公开排行榜，更新已知 code 元信息；成功拉到当前排行榜后，会清空不在当前排行榜内 code 的 `ladder_rank/ladder_score`，避免旧天梯残留继续显示成当前榜单信息。
2. 用有效 token 拉 `/api/matches/?game=48` 分页列表，从新到旧扫描，遇到低于 `#7981000` 后停止。
3. 额外用 `/api/matches/?game=48&state=准备中/评测中/...` 扫描当前远端 pending 状态；看板上的 `pending` 优先使用这个实时状态过滤计数，避免本地旧 `准备中` 行掉出普通列表窗口后长期虚高。若本地 `terminal=0` 的旧行不在远端当前 pending 集合中，会被标记为立即复查。
4. 低频按 match id 顺序做缺口探测；若探测到的详情不是 `game_id=48`，只标记 `ignored=1`，不等待、不下载 replay、不计入 Elo。例如 `#7981801` 是 `game_id=53`，会被忽略。
5. 对新发现或未完成的 Game1 对局拉详情；详情轮询优先复查 pending/陈旧 pending，再处理成功但缺 replay 元信息的局。若详情接口返回 `404/403`，会标成终态 `missing_or_forbidden`，不再计入等待。
6. 对 `评测成功` 且缺少回合数/最终血量的 Game1 对局临时下载 replay，解析后只保存元信息；详情轮询保持串行，replay 下载/解析默认最多 `3` 并发，主线程串行写 SQLite。
7. 对 `准备中`、`评测中`、`队列中` 等未完成状态维护等待列表，按低频 backoff 轮询。
8. 对 `评测失败` 等终态失败保存状态和错误，不纳入 Elo。
9. 补局请求创建后也会先写入等待列表，后续仍走同一套详情/回放解析流程。

默认详情/列表请求是串行请求，`--request-delay` 默认为 `0.35s`。replay 回放下载可以通过 `--replay-concurrency` 调整并发，默认 `3`，建议不要超过 `5`，避免对 Saiblo 下载接口和本机内存造成明显压力。

## 自动补样本策略

补局单位仍是独立 AI 版本 `code_id`。候选版本满足：

- `active_matches = 已记录对局 + 未完成补局请求` 小于 `50`。
- 小于 `10` 局的版本默认需进入库满 `2h` 后才补到冷启动样本；该阈值可用 `--supplement-min-age-sec` 调整。
- `10-50` 局之间按 Elo 可靠度和剩余样本缺口继续少量补样本。

调度节奏：

- 每次触发后，下一次触发时间在 `10-20` 分钟之间随机选择。
- 默认每次预算在 `10-30` 局之间。
- 压力指标取 `max(Game1 未完成对局数, 自动补局 outstanding 数)`，相对 `--supplement-max-outstanding`（默认 `80`）分档。
- 空闲时预算接近 `30`，压力升高时逐档降到接近 `10`；每轮再加小幅随机扰动并 clamp 到 `10-30`。
- 如果 outstanding 容量已经不足 `10`，该轮不新建房间，避免在评测队列很满时继续加压。

对手选择：

- 优先选已有足够样本、编译成功、Elo 接近目标版本的对手。
- 同一对 `code_id` 的历史/未完成补局达到 `--supplement-pair-cap` 后跳过，避免重复刷同一 matchup。
- 候选池前几名按权重随机抽取，不固定选择唯一最近邻。
- 自动补局默认排除用户名 `theend` 和 `thebeginning` 的 AI：它们仍会被爬取、记录并参与已有对局的 Elo 统计，但不会被选作补局目标或补局对手，避免主动暴露我方版本强度。排除补局不等于从榜单隐藏；若这些用户名下的版本暂无跨版本有效样本，也会以默认 `1500` 分显示在榜中。

## Elo 计算

评分单位是独立 AI 版本 `code_id`，不是用户名或 AI 名。

只纳入：

- `state=评测成功`
- 双方均有 `code_id`
- 已解析出 replay 元信息：`rounds`、`final_hp0`、`final_hp1`
- 双方 `code_id` 不同

评分按时间顺序重放：

- 基础分 `1500`。
- 期望分采用标准 Elo logistic。
- K 值随该 `code_id` 总对局数下降：少量对局版本变动更快，长期版本更稳定。
- 血量差作为 margin multiplier：胜负方向仍由 rank/score 决定，最终血量差越大，本局 Elo 变化越大。
- 展示分 `elo` 会按可靠度向 `1500` 收缩，可靠度约由总对局数决定；`raw_elo` 是未收缩分。
- 同一个 `code_id` 两边自战不会改变 Elo，因为它不提供跨版本强度信息；但该版本仍会出现在榜单中，默认 `elo=raw_elo=1500`、`games=0`、`reliability=0`，并在 JSON 中记录 `rating_source=default_self_play` 与 `self_play_games`。之后自动补局可以再安排它对其他 AI，逐步把默认分替换为真实跨版本评分。
- 当前排行榜只作为已知版本元信息补充；纯旧天梯残留、天梯占位、仅 pending/失败且没有跨版本有效对局或已完成自战的 code 不再进入 Elo 榜单。

这样可以避免少量对局的版本被过度排序，同时让大样本版本稳定区分强弱。

## 常用命令

单轮同步：

```bash
python3 saiblo_game1_elo.py crawl
```

后台启动 crawler：

```bash
scripts/saiblo_game1_elo_start.sh
```

查看状态：

```bash
scripts/saiblo_game1_elo_status.sh
```

停止 crawler：

```bash
scripts/saiblo_game1_elo_stop.sh
```

启动本地看板：

```bash
scripts/elo_web_start.sh
```

看板 API 会包含 `views.saiblo_game1`，网页中可通过顶部 `<-` / `->` 在 “Saiblo Game1 AI 版本 Elo” 和 Game53 平均分两页之间切换。旧的本地 production/iteration Elo 面板已经从看板移除；Game53/DeepClue 的单人平均分统计见 `game53_saiblo_score.md`。

看板默认按用户名折叠：每个用户只显示其当前全量排序中最强的 AI 版本，`Rank` 仍保留该版本在全量 AI 版本榜里的总排名；顶部开关可切回全部版本。

Saiblo Game1 表格每行右侧提供两个操作：

- `复制`：复制该 AI 版本完整 `code_id`。
- `对局`：打开该版本最近一场已记录的 Saiblo 对局页；有 Elo 对局时优先使用最近的 Elo 对局，没有 Elo 对局时回退到该版本最近出现过的对局。

## 当前限制

- 主动补局依赖有效 Saiblo bearer token；无 token 或 token 失效时仍可更新公开排行榜，但无法拉取详情或创建房间。
- 如果候选版本不足、对手不足、或 outstanding 容量不足，单轮实际创建数可能低于预算；调度器会在下一次随机触发时继续尝试。
