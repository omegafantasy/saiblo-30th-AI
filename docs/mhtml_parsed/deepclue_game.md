# deepclue_game

- Source mhtml: `头号侦探 - Saiblo.mhtml`
- Reconstructed from the page content captured in the mhtml.

# DeepClue 头号侦探

## 游戏玩法介绍

这是一个推理型剧本杀游戏。你扮演侦探，通过与 NPC 对话、收集证据、推理分析，最终找出凶手、动机和作案手法。

### 核心流程

- 获取背景 → 调用 `background` 了解当前剧本的故事设定
- 与 NPC 对话 → 调用 `chat` 向 NPC 提问，获取证言和线索
- 推进阶段 → 收集足够证据后游戏自动推进到下一阶段，解锁更多 NPC 和证言
- 提交答案 → 调用 `answer` 提交凶手、动机、手法

### 证据体系

游戏中的证据分为三类：

| 类型 | 获取方式 | 说明 |
| --- | --- | --- |
| 回忆 | 游戏开始时自动获得 | 初始线索，ID 以 0 开头 |
| 证言 | 与 NPC 对话时解锁 | 核心信息来源，通过 chat 解锁 |
| 现场勘察 | 阶段推进时自动解锁 | 物证类线索，如日记、凶器等 |

- 证据 ID 为三位数字字符串，如 `"101"`、`"313"`
- 某些证言需要前置条件：你必须先拥有特定证据，NPC 才会透露对应信息
- 向 NPC 出示证据（`evidences` 字段）可以触发需要前置条件的对话

### 阶段系统

- 游戏分为多个阶段（从第 1 阶段开始），满足必要条件后自动推进
- 阶段推进时会自动解锁该阶段的奖励证据（现场勘察类）
- 可通过 `marks`(见 API 章节) 查看哪些 NPC 在当前阶段还有未获取的证言
- 可通过 `hint`(见 API 章节) 获取当前阶段的调查提示

### 多剧本模式

- 游戏包含2个剧本，依次串行进行
- 在初赛阶段，第一个剧本是开放的，可以人类游玩。第二个剧本隐藏，无法在 Saiblo 上以人类玩家的身份游玩，只对 ai 开放。
- 提交 `answer`（见 API 章节）后自动切换到下一个
- 每个剧本的 NPC 名称、证据、背景都不同，需要重新调查
- 总分 = 各剧本分数之和

## API（stdin/stdout JSON）

AI 每轮发送一个 JSON 对象，必须包含 `"action"` 字段。游戏返回对应的 JSON 响应。
API 调用可能会产生错误。有关错误处理的接口格式，详见 错误处理 章节。


### background — 获取当前剧本的故事背景

请求：

```json
{"action": "background"}
```

响应：

```json
{"background": "剧本故事背景..."}
```


### chat — ai玩家与npc对话

请求：

```json
{
  "action": "chat",
  "npc": "小明",
  "question": "你昨天晚上在哪里？",
  "evidences": ["301", "302"]
}
```

- `npc`（必填）：NPC 名称
- `question`（必填）：提问内容
- `evidences`（可选，默认 `[]`）：向 NPC 出示的证据 ID 列表

响应：

```json
{
  "reply": "npc 回复",
  "stage": 2,
  "achievements": [
    {"id": 1, "name": "小明的秘密", "description": "发现小明的身份..."}
  ],
  "unlock_testimony": [
    {"id": "201", "name": "证言名", "type": "证言", "content": "证言内容..."}
  ]
}
```

- `reply`：NPC 回复
- `stage`：当前阶段编号
- `achievements`：本次对话新解锁的成就列表（`{id, name, description}`），无新成就则为 `[]`
- `unlock_testimony`：本次对话新解锁的证言列表（`{id, name, type, content}`），无新证言则为 `[]`


### answer — 提交最终答案

请求：

```json
{
  "action": "answer",
  "murderer": "小明",
  "motivation": "因为小明有精神分裂...",
  "method": "小明召唤了恶魔..."
}
```

响应：

```json
{
  "murderer": true,
  "motivation": true,
  "method": false
}
```

提交后当前剧本结束，自动切换到下一个剧本（如有）。


### call — 让游戏代理你的 LLM 调用请求

请求：

```json
{
  "action": "call",
  ...
}
```

响应：

```json
{
  ...
}
```

额外字段透传给 `proxy_user_call()`。
注意：不支持流式响应。默认非流式响应。
**`model` 字段会被后端强制覆盖为 `qwen3.5-plus`**，无法自行指定模型。

请求与响应格式与 OpenAI Chat Completions API 的非流式模式一致（参见 [OpenAI API Reference](https://platform.openai.com/docs/api-reference/chat/object)）。


### stage — 获取当前阶段

请求：

```json
{"action": "stage"}
```

响应：

```json
{"stage": 3}
```


### marks — 获取 NPC 问号状态

NPC 问号表示当前阶段该 NPC 仍有待解锁的证言。

请求：

```json
{"action": "marks"}
```

响应：

```json
{
  "NPC_A": false,
  "NPC_B": true,
  "NPC_C": true
}
```

`true` 表示该 NPC 在当前阶段仍有未获取的证言。


### npcs — 获取当前可见 NPC 列表

请求：

```json
{"action": "npcs"}
```

响应：

```json
["NPC_A", "NPC_B", "NPC_C"]
```


### hint — 获取当前阶段提示

请求：

```json
{"action": "hint"}
```

响应：

```json
{"hint": "当前阶段的提示文本..."}
```


### testimony — 获取所有已获得的证言

请求：

```json
{"action": "testimony"}
```

响应： 直接返回数组（不含成就类证言）

```json
[
  {"id": "101", "name": "证言名", "type": "证言", "content": "证言内容..."},
  {"id": "102", "name": "另一条", "type": "证言", "content": "..."},
  ...
]
```


### others — 获取非证言类证据

请求：

```json
{"action": "others"}
```

响应：

```json
{
  "evidences": [
    {"id": "301", "series": 3, "name": "名称", "type": "现场勘察", "content": "内容..."},
    ...
  ]
}
```


### achievements — 获取已解锁的成就

请求：

```json
{"action": "achievements"}
```

响应： 返回已解锁的成就（仅包含玩家已获得的成就类证言对应的成就）

```json
{
  "achievements": [
    {"id": 1, "name": "小明的秘密", "description": "发现小明是都市传说中的..."},
    {"id": 4, "name": "倒霉熊", "description": "得知小明走路摔骨折了..."},
    ...
  ]
}
```

### 错误处理

所有请求如果出错，后端会统一返回包含 `"error"` 字段的 JSON：

```json
{
  "error": "错误描述信息"
}
```

AI 收到响应后，应先检查是否存在 `"error"` 字段，若存在则说明本次请求失败，需要根据 `error` 字段的描述修正请求后重试。

常见错误场景：

| 场景 | error 示例 |
| --- | --- |
| 请求不是合法 JSON | "Invalid JSON format" |
| 缺少必填字段 | "Missing required fields: npc, question" |
| 字段类型不对 | "Field 'npc' must be string" |
| 未知的 action | "Unknown action: xxx" |
| 后端内部异常 | "Internal Server Error: ..." |

## SDK 使用指南

我们提供了 Python SDK（位于 `SDK/sdk.py`），封装了底层的 stdio 二进制通信协议，可以直接调用。 SDK可以在 [Github](https://github.com/SAST-agent/DeepClueSDK-python.git)、[清华git](https://git.tsinghua.edu.cn/deepcluesdk/deep-clue-sdk)、[Gitee](https://gitee.com/fangchen-luo/deep-clue-sdk.git) 上获取。

### 快速开始

```python
from SDK.sdk import SDK

sdk = SDK()

# 游戏启动时会收到一条欢迎消息，需要先消费掉
welcome = sdk._receive()

# 获取背景
resp = sdk.request("background")
print(resp["background"])

# 与 NPC 对话
resp = sdk.request("chat", npc="XiaoDingAng", question="案发时你在哪？", evidences=[])
print(resp["reply"])            # NPC 回复
print(resp["unlock_testimony"]) # 新解锁的证言

# 提交答案
resp = sdk.request("answer", murderer="某人", motivation="动机...", method="手法...")
```

### API 一览

| 方法 | 说明 |
| --- | --- |
| sdk.request(action, **kwargs) | 通用方法，发送任意 action 请求并返回响应字典 |
| sdk.call_llm(**kwargs) | 调用 LLM（通过游戏代理），参数透传给 OpenAI 接口 |

`request` 方法支持所有上文 API 章节中列出的 action，使用方式：

```python
# 所有 action 均通过 request 调用，kwargs 作为 JSON 字段发送
sdk.request("background")
sdk.request("stage")
sdk.request("hint")
sdk.request("npcs")
sdk.request("marks")
sdk.request("testimony")
sdk.request("others")
sdk.request("achievements")
sdk.request("chat", npc="NPC名", question="问题", evidences=["证据ID"])
sdk.request("answer", murderer="凶手", motivation="动机", method="手法")
```

### 调用 LLM

通过 `call_llm` 方法可以让游戏服务器代理你的 LLM 调用请求，无需本地配置 API KEY：

```python
resp = sdk.call_llm(
    messages=[
        {"role": "system", "content": "你是一个推理助手"},
        {"role": "user", "content": "根据以下线索分析凶手..."}
    ],
    temperature=0.7,
)
if "error" not in resp:
    answer = resp["choices"][0]["message"]["content"]
else:
    print(f"调用失败: {resp['error']}")
```

### 通信协议说明

SDK 底层采用二进制帧协议，无需手动处理：

- 发送：4 字节大端序长度前缀 + UTF-8 编码的 JSON 字符串
- 接收：4 字节头部 + 一行 JSON 字符串（`\n` 结尾）

### 注意事项

- `stdout` 被用于与 Judger 通信，日志必须输出到 `stderr`
- 游戏启动后会先收到一条欢迎消息，需要先调用 `sdk._receive()` 消费掉，再开始正常交互
- 多剧本模式下，提交 `answer` 后会自动切换到下一个剧本，需要重新获取背景和 NPC 列表
- `call_llm` 不支持流式响应，使用前请检查响应中是否存在 `error` 字段

## 评分规则

一个剧本中，分数由三部分组成：

- 答案正确性（最多 600 分）：凶手 / 动机 / 手法 各 200 分
- 调查进度（最多 400 分）：按通过的阶段比例和掌握的线索比例计算
- 成就解锁：每解锁一个成就加 40 分
- 效率系数：基于总 token 消耗的对数缩放，token 越少得分越高

公式：`得分 = (正确性得分 + 进度得分 + 成就得分) * 效率系数`

总分 = 各剧本分数之和。

## 其他注意事项详见 Saiblo 网站 AI 编写文档

## 附：可见剧本介绍————无言的蔷薇

### 背景设定

夜幕低垂，霓虹灯牌在雨雾中晕开暧昧的光。你推开舞厅沉重的木门，酒精和烟草的味道扑面而来——这是老友萧定昂经营的地方，今晚他特意邀你来坐坐。演出结束后，一声尖叫从后台传来——头牌舞女 Rose 被发现死在准备室的衣柜里。

萧定昂拦住所有人，转向你："你是侦探，拜托了。"

在场的每个人都面色各异。真相藏在他们的谎言与沉默之中。

### 在场人物

| 角色 | NPC名称 | 身份 | 简介 |
| --- | --- | --- | --- |
| 萧定昂 | XiaoDingAng | 舞厅经理 | 31岁，精明干练，案发当天邀请侦探前来 |
| 白井霆 | BaiJingTing | 客人 | 28岁，混混气质，穿蹩脚西装，戴金丝眼镜 |
| 崔安彦 | CuiAnYan | 客人 | 26岁，女，衣着华丽，与邓达岭关系密切 |
| 邓达岭 | DengDaLing | 客人 | 35岁，银行家，富有 |
| 叶文潇 | YeWenXiao | 领舞 | 25岁，舞技出众但唱功一般 |
| 范敏敏 | FanMinMin | 舞女 | 22岁，人气仅次于Rose |
| Rose | — | 死者 | 21岁，头牌舞女，身份神秘 |
