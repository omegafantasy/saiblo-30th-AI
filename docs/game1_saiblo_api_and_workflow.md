# Game1 Saiblo API 与操作链路

## 1. 已确认仍可复用的 HTTP 接口

以 game 48 为例，当前仍可直接复用以下接口：

- 排行榜：`GET /api/games/<game_id>/ladders/?offset=&limit=`
- 对局列表：`GET /api/matches/`
- 对局详情：`GET /api/matches/<match_id>/`
- 回放下载：`GET /api/matches/<match_id>/download/`
- 创建房间：`POST /api/rooms/`
- 房间入座：`POST /api/rooms/<room_id>/join/`
- 开始对局：`POST /api/rooms/<room_id>/begin_match/`
- 获取用户实体：`GET /api/users/<username>/games/<game_id>/entities/`
- 创建实体：`POST /api/users/<username>/games/<game_id>/entities/`
- 上传代码：`POST /api/entities/<entity_id>/codes/`
- 激活版本：`PUT /api/entities/<entity_id>/codes/<code_id>/`

## 2. `saiblo_tools.py` 当前能力

当前脚本已覆盖：

- `entities`
- `ladders`
- `upload-ai`
- `room-match`
- `run-matches`
- `download-replay`
- `recent`
- `match`

Bearer 获取优先级：

- `--token`
- `SAIBLO_BEARER`
- `config.local.json`
- `past_AIs/zdata.py`

## 3. 已知约束

- Entity 名称长度上限约为 `16`
- 只有 `compile_status=编译成功` 的版本才能激活
- 回放下载接口偶发返回“合法 JSON + 尾部附加文本”，解析时要用首个 JSON 值截断

## 4. 当前 Game1 的真正限制

`cpp_v1_current` 本地能跑通，但它本质上是：

- Python 协议层 / SDK 状态重建
- C++ 只负责决策

因此它不能直接作为单文件纯 C++ 源上传到 Saiblo。

这意味着：

- `saiblo_tools.py` 的 HTTP 链路是可用的
- 但“上传当前最强本地 AI”这一步，还需要一个真正独立的 Saiblo 参赛版 C++ 入口

## 5. 当前正确判断

可以认为目前已跑通的是：

- 认证
- 查询实体
- 查询排行榜
- 发起对局
- 下载回放
- 基础上传能力

但还不能把本地最强 `cpp_v1` 直接等价为 Saiblo 可上传版本。

后续若要真正打通线上强 AI 链路，应优先补：

1. 纯 C++ 单文件协议入口
2. 与本地策略核心的映射
3. Saiblo 上传后的编译与对战 smoke

## 6. 2026-03-10 实测结果

本轮已实际完成：

- 查询实体：成功
- 查询榜单：成功
- 上传单文件纯 C++ probe：成功，`compile_status=编译成功`
- 开房对战 2 局：成功
- 下载详情与回放：成功
- 用本地 `Game1` replay 解析器解析下载回放：成功

本轮 probe 实体：

- `g1probe0310`
- `entity_id=20401`
- `uploaded_code_id=e1d06b260fd248bbb0405ca105cbb189`

本轮对局：

- `7419724`
- `7419725`

结论更新：

- `Saiblo` API 与回放链路已经不是“理论可用”，而是已经实跑通过。
- 当前未完全打通的只剩“把本地最强桥接 AI 改造成线上可上传的纯 C++ 强版本”。
