# Saiblo Game 48 接口梳理与 2 局实测

更新时间：2026-03-04 (UTC)

## 1. 页面到接口映射

基于以下页面与前端 bundle 逆向：

- `https://www.saiblo.net/game/48?id=3`（我的AI）
- `https://www.saiblo.net/game/48/ranklist`（全局排行榜）
- `https://www.saiblo.net/game/48?id=2`（对局列表）
- `https://www.saiblo.net/match/7413410/`（对局详情/回放）

### 1.1 排行榜（ranklist）

- 页面：`/game/48/ranklist`
- 接口：`GET /api/games/<game_id>/ladders/?offset=<offset>&limit=<limit>`
- 返回核心字段：
  - `results[].user`
  - `results[].score`
  - `results[].code.id`（可用于开房对局的 token，UUID，可带或不带连字符）
  - `results[].code.entity.id/name`

### 1.2 对局列表（game/48?id=2）

- 接口：`GET /api/matches/`
- 常用查询参数（由前端 `match-list` 组件拼装）：
  - `limit`
  - `offset`
  - `game`（游戏 ID）
  - `contest`（比赛 ID）
  - `username`（用户名过滤）
  - `state`（准备中/评测中/评测成功/评测失败）

### 1.3 对局详情与回放

- 详情：`GET /api/matches/<match_id>/`
- 回放下载：`GET /api/matches/<match_id>/download/`
- 详情中常用字段：
  - `state`、`logic_version`、`create_time`
  - `info[]`（玩家、code、rank、score、end_state）
  - `url`（下载路径）

### 1.4 开房发起对局（用于自动化测试）

- 创建房间：`POST /api/rooms/`，body: `{"game_id":48,"player_number":2}`
- 加入座位：`POST /api/rooms/<room_id>/join/`
  - AI 入座 body 示例：
    - `{"order":0,"enter":true,"is_user":false,"is_remote":false,"entity":"<token>"}`
- 开始对局：`POST /api/rooms/<room_id>/begin_match/`

### 1.5 我的 AI（上传链路）

- 获取当前用户：`GET /api/profile/`
- 列实体：`GET /api/users/<username>/games/<game_id>/entities/`
- 创建实体：`POST /api/users/<username>/games/<game_id>/entities/`
- 上传代码：`POST /api/entities/<entity_id>/codes/`（multipart: `remark` + `file`）
- 查版本：`GET /api/entities/<entity_id>/codes/`
- 激活派遣：`PUT /api/entities/<entity_id>/codes/<code_id>/` + `{"activate":true}`

## 2. 自动化脚本能力（`/www/saiblo_tools.py`）

已补齐命令：

- `ladders`：查询榜单与 token
- `entities`：查询我的实体与版本
- `upload-ai`：上传源码（可选激活）
- `room-match`：发起房间对局
- `run-matches`：批量发起 + 等待完成 + 保存详情/回放
- `download-replay`：下载单局回放并保存详情
- `recent` / `match`：查询对局列表与详情

示例：

```bash
python3 /www/saiblo_tools.py ladders --game-id 48 --limit 10

python3 /www/saiblo_tools.py run-matches \
  --game-id 48 \
  --entity-a 58efb19afeaf414e9c0b0b34a3e98621 \
  --entity-b 2247f15809ff450e9febd5af53efe9a5 \
  --count 2 --swap --download-replay \
  --save-dir /www/replays/saiblo_api/20260304_run1
```

## 3. 基础 AI 上传结果（不派遣）

上传文件：`/www/ai_cpp/saiblo_baseline/ai_baseline_v1.cpp`

- 实体：`autolv1_0304`（id=20339）
- 上传版本：`version=4`
- code token：`58efb19afeaf414e9c0b0b34a3e98621`
- 编译状态：`编译成功`
- 激活状态：未激活（满足“暂时不要派遣”）

## 4. 2 局实测记录（已下载）

对阵：

- 我方：`58efb19afeaf414e9c0b0b34a3e98621`（baseline_v1_nojson_noactivate）
- 对手：`2247f15809ff450e9febd5af53efe9a5`（ranklist 榜首）

生成对局：

- `7413427`
- `7413428`

本地文件：

- 详情：
  - `/www/replays/saiblo_api/20260304_run1/match_7413427.json`
  - `/www/replays/saiblo_api/20260304_run1/match_7413428.json`
- 回放：
  - `/www/replays/saiblo_api/20260304_run1/7413427.json`
  - `/www/replays/saiblo_api/20260304_run1/7413428.json`
- 汇总分析（机器可读）：
  - `/www/docs/replay_analysis/saiblo_run1_summary_20260304.json`

结果（按官方详情 `info[].rank/score`）：

- `7413427`：我方 0:1 负
- `7413428`：我方 0:1 负

回放快速统计：

- `7413427`
  - 帧数：512
  - 回放 JSON 尾部脏数据：无
  - 我方动作：全帧仅 `type=8`（结束回合）
  - 对手动作：大量 `type=1/3`
- `7413428`
  - 帧数：189
  - 回放 JSON 尾部脏数据：有（约 43044 字节，需容错解析）
  - 我方动作：全帧仅 `type=8`
  - 对手动作：大量 `type=1`，少量 `type=7/3/5`

说明：`/api/matches/<id>/` 的 `info[]` 顺序不一定可直接当作先后手，先后手建议以建房参数（`entity-a`/`entity-b`）和回放 `op0/op1` 行为对照判断。

结论：

- 自动化链路已打通：上传 -> 发起 -> 等待 -> 下载 -> 分析。
- 当前 baseline 仅用于协议与链路验证，不具备战斗力。
- 回放下载接口偶发返回“合法 JSON + 尾部附加文本”，解析时需用 `raw_decode` 截断首个 JSON 值。
