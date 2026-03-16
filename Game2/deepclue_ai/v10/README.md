# Game2 DeepClue AI v10

相对 `v9` 的重点变化：
- 新增稳定性保护：`stage >= 8` 后不再继续 `chat`
- 背景原因：线上回放已确认后端在 `stage 8` 后继续问话可能触发 `Stage.py KeyError '8'`
- 仍保留 `v9` 的“method 过泛时补 1 条手法追问”
