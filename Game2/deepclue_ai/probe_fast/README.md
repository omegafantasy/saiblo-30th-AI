# Game2 Fast Probe

- 用途：诊断 batch 中的 `exit_code=9` 是否主要来自运行时间。
- 策略：
  - 仅请求一次 `npcs`
  - 立即提交答案
  - 不进行调查，不调用 LLM
