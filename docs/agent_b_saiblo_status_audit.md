# Agent B：Saiblo 状态与脚本可用性核查

## 核查时间

- 2026-03-03（UTC）

## 核查对象

- 根脚本：`/www/saiblo_tools.py`
- 凭据回退：`/www/past_AIs/zdata.py`（`bearer`）
- 目标游戏：`game_id=48`（Antwar2）

## 实测命令与结果

### 1) 最近对局拉取（成功）

命令：

```bash
python /www/saiblo_tools.py recent --game-id 48 --limit 5
```

结果：

- token 来源显示为 `past_AIs/zdata.py`
- 成功返回 `count=5`
- 返回对局均为 `game_id=48`, `game="Antwar2"`, `state="评测成功"`
- 最近 match_id 样本：`7412844` 到 `7412840`

### 2) 单局详情拉取（成功）

命令：

```bash
python /www/saiblo_tools.py match --match-id 7412844
```

结果：

- 成功返回完整对局详情（双方代码信息、end_state、logic_version、下载 URL、message 记录等）

### 3) 鉴权失败路径（成功触发）

命令：

```bash
python /www/saiblo_tools.py --token invalid_token recent --game-id 48 --limit 1
```

结果：

- 正确返回 `HTTP 401`
- 错误信息：`Given token not valid for any token type`

## bearer 有效期核查

对 `zdata.py` 中 JWT payload 解码得到：

- `iat`: 2026-03-03T09:10:02+00:00
- `exp`: 2026-03-10T09:10:02+00:00

结论：以当前时间（2026-03-03）看，token 处于有效期内。

## 结论

- `saiblo_tools.py` 的核心链路（recent/match）可正常工作。
- token 优先级与异常处理行为符合预期。
- 当前可继续用于 game/48 的线上数据抓取与后续自动化。
