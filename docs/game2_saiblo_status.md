# Game2 Saiblo 联通与测试状态

## 1. 已确认的线上状态

`Game2` 在 Saiblo 上不是普通 room-match 型游戏。

本轮实测现象：

- `entities --game-id 53` 正常
- `upload-ai` 正常
- `activate` 正常
- `ladders --game-id 53` 会直接显示当前分数
- `recent --game-id 53` 仍返回空

因此当前判断是：

- Game2 的评测结果主要通过榜单体现
- 它不复用 `matches` 列表作为主要反馈通道

## 2. 本轮 baseline 上传结果

实体与代码：

- entity: `g2base0310`
- entity_id: `20404`
- code_id: `b2d77026701f4fcc8985a794e5e09e4f`
- language: `python`
- compile_status: `编译成功`
- activation: `成功`

## 3. 当前榜单结果

本轮上传后，榜单已出现本账号版本：

- `theend / g2base0310 / version 1 / score 1000`

同时 `recent --game-id 53` 仍为空，这进一步说明：

- Game2 的线上反馈口径和 Game1 不同
- 不能继续沿用 Game1 的 replay / match 下载链路

## 4. 当前能认为已打通的链路

可以认为已经跑通的是：

- Game2 单文件 AI 编写
- Python 上传
- 编译
- 激活
- 榜单可见

尚未打通的是：

- 可下载的逐步调查日志
- 与 Game1 类似的 replay 分析链
- 本地可复现实验环境

## 5. 当前建议

后续 Game2 迭代应围绕：

- prompt 与调查策略优化
- 证据组织与问题选择优化
- 在线多版本提交对比分数

而不是沿用 Game1 的 Elo / 对局回放思路。
