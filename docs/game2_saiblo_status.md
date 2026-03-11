# Game2 Saiblo 联通与测试状态

## 1. 已确认的线上状态

`Game2` 在 Saiblo 上不是普通 room-match 型游戏，但并不是完全没有对局级反馈。

本轮实测现象：

- `entities --game-id 53` 正常
- `upload-ai` 正常
- `activate` 正常
- `ladders --game-id 53` 会直接显示当前分数
- `recent --game-id 53` 仍返回空
- `POST /api/batches/` 可发起针对榜单 code 的批测
- `GET /api/matches/<id>/download/` 可下载已完成内部 match 的完整调查轨迹

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

此前只看到我方初始分 `1000`，但继续轮询后已确认榜单有真实历史分数：

- `admin / 跑通测试 / 121207`
- `stepp / 头顶圆圆的 / 8360`
- `zhangs24 / 1112 / 8226`
- `theend / g2base0310 / 1000`

因此当前正确结论是：

- Game2 榜单不是“统一初始 1000 后不更新”
- 只是我方当前版本还没有突破初始分

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

- 本地可复现实验环境
- token 计费细项

已经打通的是：

- batch 发起
- batch 结果抓取
- match 详情抓取
- match 调查轨迹下载
- 自动结构化分析

## 5. 当前建议

后续 Game2 迭代应围绕：

- prompt 与调查策略优化
- 证据组织与问题选择优化
- 在线多版本提交对比分数
- 批测轨迹分析

而不是沿用 Game1 的 Elo / 对局回放思路。

## 6. 当前强度判断

截至 `2026-03-11`，当前最强且已经重复验证过的主线仍然是 `v2` 基线：

- 原始上传：
  - 实体：`g2base0310`
  - 线上版本：`3`
  - code_id: `2622a92be4a847809b9e738ae2572a44`
- 参考重传：
  - 实体：`g2v2ref0311`
  - 线上版本：`1`
  - code_id: `ab8d1b740e7d416f83722a8cfb6e36bc`

已确认成绩：

- `7421776`：`607`
- `7422137`：`407`
- `7422139`：`607`

这说明：

- `v2` 仍是当前最值得继续分析的基线
- 但它本身存在明显波动，不能只看单次分数

当前活跃代码已经切回最强基线用于复测：

- 实体：`g2v2ref0311`
- 活跃版本：`1`
- code_id: `ab8d1b740e7d416f83722a8cfb6e36bc`
- 作用：重复验证 `v2` 在强对手下的分数波动

实验版本仍保留在 `g2base0310`：

- `version 11`
- code_id: `f63fc8b0f3b44153b2e57bdd2cb1fb9b`
- 作用：验证 `stage >= 8` 截断能否规避后端异常

已知新实验结果：

- `v7`（线上 `version 8`，match `7422058`）得分 `407`
- 它没有超过 `v2`
- `v10/v11` 仍未拿到我方有效新高分，暂不能视为主线替代

当前对比分析报告：

- `docs/generated/game2_run_comparison.md`

当前新的受控复测 batch：

- `75665`
- 对手：`admin/跑通测试`
- 状态：已创建，等待结果
