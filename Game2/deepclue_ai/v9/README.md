# Game2 DeepClue AI v9

相对 `v2` 的重点变化：
- 保持原有低 `call_llm`、少步数主线
- 如果第一次产出的 `method` 过泛，再补一条定向“手法追问”
- 目标是优先补第二个剧本里 `method=false` 的缺口，而不明显增加调查成本
