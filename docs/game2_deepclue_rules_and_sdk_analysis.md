# Game2 / DeepClue 规则与 SDK 分析

## 1. 游戏性质

`Game2` 对应 Saiblo `game/53`，是推理型单人游戏，不是传统双 AI 对战。

核心流程：

- 获取背景 `background`
- 获取当前可见 NPC `npcs`
- 根据 `marks` / `hint` 决定调查方向
- 用 `chat` 向 NPC 提问，并可携带 `evidences`
- 收集 `testimony` / `others` / `achievements`
- 最后提交 `answer(murderer, motivation, method)`

评分由这些部分组成：

- 答案正确性
- 调查进度
- 成就解锁
- token 效率系数

## 2. 仓库中现有代码的真实情况

当前 `Game2/` 下只有：

- `DeepClueSDK-python/sdk.py`
- `DeepClueSDK-python/README.md`

这意味着：

- 仓库没有本地逻辑内核
- 没有本地判题器
- 没有像 Game1 那样的本地 Elo / 本地评测环境

因此 Game2 的真实开发模式是：

- 本地写单文件 AI
- 本地做静态检查 / mock / prompt 设计
- 真正评测依赖 Saiblo 在线反馈
- 结果与轨迹分析依赖 Saiblo `batch + match download`

## 3. SDK 与协议

`sdk.py` 的协议很轻：

- 发送：`4 字节大端长度 + JSON`
- 接收：读 4 字节头，再读一行 JSON

SDK 暴露的关键接口：

- `request("background")`
- `request("stage")`
- `request("hint")`
- `request("npcs")`
- `request("marks")`
- `request("testimony")`
- `request("others")`
- `request("achievements")`
- `request("chat", npc=..., question=..., evidences=[...])`
- `request("answer", murderer=..., motivation=..., method=...)`
- `call_llm(...)`

关键点：

- `call_llm` 是由游戏后端代理调用
- 规则页说明后端会强制覆盖模型到 `qwen3.5-plus`
- 因此本地无需 API key，但线上 token 消耗会计入效率分

## 4. 对 AI 设计的直接约束

和 Game1 完全不同，Game2 的核心不是搜索，而是：

- 调查流程控制
- 问题生成质量
- 证据组织
- 最终推理质量
- token 成本控制

实际最重要的设计点：

- 不能盲聊，必须围绕 `marks` 和现有证据问
- 不能只堆问题，阶段推进与证据解锁优先级更高
- 最终答案不能只靠固定模板，必须结合当前证据集合做总结推理

## 5. 当前 baseline 设计

当前首版 AI 采用：

- 先全量抓取背景、NPC、提示、证言、物证、成就
- 用 `marks` 识别当前阶段还有产出的 NPC
- 用 `call_llm` 给每个 NPC 规划 1-3 个高价值问题
- 自动附带少量最近证据 ID
- 每轮刷新状态，再继续调查
- 最后再用 `call_llm` 汇总所有证据，生成 `murderer / motivation / method`

代码位置：

- `Game2/deepclue_ai/v1/ai_v1.py`

## 6. 当前局限

当前 `v1/v2` 仍然只是 baseline：

- 中途 `call_llm` 偏多，存在超时与高 token 风险
- 调查深度明显不足
- 没有对线上回放做闭环分析

但它已经具备：

- 单文件上传能力
- 合法协议实现
- 自动调查闭环
- 自动最终作答闭环

## 7. 当前开发约束

截至 `2026-03-11`，Game2 的真实开发约束已经比最初判断更明确：

- 不应再把单次线上分数直接当成版本强弱
  - 同一份 `v2` 源码已经出现 `607 / 407 / 607` 波动
- 当前主要不稳定源很可能来自两处：
  - 中途 `call_llm` 生成提问计划
  - 最终 `call_llm` 汇总 `murderer / motivation / method`
- 平台在高阶段存在已确认 bug：
  - `stage >= 8` 后继续 `chat`
  - 可能触发 `Stage.py` 的 `KeyError: '8'`

因此现在更合理的 Game2 AI 设计原则是：

1. 先追求稳定和可复现，再追求更深调查
2. 提问模板尽量短、直接、单目标
3. 不要把多条线索和多个判断揉进一条长问题
4. 在高 stage 下优先收束答案，避免继续深挖
5. 新策略必须用重复 batch 验证，而不是只看一次高分
