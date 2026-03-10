这是 Saiblo 定时迭代心跳回合，请继续推进上一次工作。

必须先读取并严格遵守：
- /www/docs/codex_saiblo_objective_fixed.md

然后按以下流程执行：

1) 读取状态与上下文
- 生产 Elo：`/www/autolab/runtime/latest.json`
- Saiblo 实体：`python3 /www/saiblo_tools.py entities --game-id 48`
- 全局榜单：`python3 /www/saiblo_tools.py ladders --game-id 48 --limit 30`
- 历史记录：`/www/docs/saiblo_codex_iterations.md`（若不存在则创建）
- 最新回放分析：`/www/docs/replay_analysis/` 下 `saiblo_*` 文件
- 历史 AI：`/www/past_AIs/Generals-AI/main.cpp`、`/www/past_AIs/ANTWar-AI/`

2) 选择本轮类型（二选一）
- `test-round`：执行 Saiblo 对战与回放采集（每轮最多 10 局）
- `analysis-round`：只做回放深度分析 + 代码改进 + 本地验证（可不打 Saiblo）

3) 若是 test-round，执行标准链路
- 选“当前最强 AI”作为上传候选：
  - 优先依据生产 Elo 与近期 head-to-head 证据；
  - 若证据不足，先保守沿用当前线上较强版本，不做激进替换。
- 上传到 Saiblo：
  - 目标实体名：`cpp_v1_current`（如不存在可创建）
  - 使用 `python3 /www/saiblo_tools.py upload-ai ... --wait-compile --activate`
- 选对手策略（禁止把预算浪费在明显过弱 AI）：
  - 优先“分数接近或更强”的对手；
  - 总对局数 `<=10`，建议开启 `--swap`。
- 发起对局并下载 replay：
  - `python3 /www/saiblo_tools.py run-matches ... --download-replay --save-dir <run_dir>`
  - `run_dir` 示例：`/www/replays/saiblo_api/scheduled/YYYYmmdd_HHMM_<tag>/`
- 对战后必须做 replay 分析（可以写临时脚本），并产出：
  - `/www/docs/replay_analysis/saiblo_<tag>.md`
  - 需要包含：关键行为、胜负成因、逻辑正确性判断、后续改进点

4) 若是 analysis-round，执行标准链路
- 优先分析最近 Saiblo replay 与本地 replay，找“算法级”缺陷
- 改进时遵循：
  - 优先简化逻辑和核心策略，不堆参数
  - 若修改 AI 策略代码，必须新建版本目录与新版本 ID，禁止覆盖旧版本源码
  - 借鉴 `Generals-AI` 与 `ANTWar-AI` 各至少一个机制并写明映射
  - 若引入搜索/前瞻，必须单步 CPU `<=200ms` 并有硬截止+回退
- 至少做一次本地验证（编译/小样本评测/回放核对）

5) 回合收尾（强制）
- 更新 `/www/docs/saiblo_codex_iterations.md`，记录：
  - 本轮类型、动作、证据、结论、风险、下一步
  - 是否上传、对手选择理由、是否触发 200ms 风险点
- 若本轮没有发起 Saiblo 对战，明确写“未对战原因”和“下轮触发条件”

注意：
- 不要与主 codex 迭代流程争用同一批关键文件；优先在 Saiblo 专用文档中记录。
- 如果检测到当前会话已在做同类任务，直接继续，不要重新开题。
