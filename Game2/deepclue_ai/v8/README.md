# Game2 DeepClue AI v8

基线来自 `v2`，只做受控增强：
- 保持低步数，单剧本预算约 `20` 步
- 在第一次 targeted sweep 后补极少量证据追问
- 收紧最终答案 prompt，减少“只抓表面冲突”的误判
