# Game2 Tools

当前 Game2 已有可直接使用的线上分析/评测脚本：

- `run_room_eval.py`
  - 当前 Game53 迭代的默认评测方式
  - 创建 `player_number=1` 的单人房间
  - 只把我方 code 放在 `order=0`
  - 不产生后手/反向样本
  - 自动下载 match detail / replay / analysis
  - 输出到 `Game2/runtime/room_matches/`

- `submit_and_track.py`
  - 上传单文件 AI
  - 等待编译
  - 激活
  - 记录榜单快照

- `run_batch_eval.py`
  - 创建 batch 或按 `batch-id` 回填
  - 正确按“双边独立跑分”语义汇总结果
  - 自动下载所有已结束 match 的详情
  - 对成功对局下载回放，对失败对局保存失败分析
  - 当前 Game53 迭代不要使用；保留作历史回填工具

- `analyze_match.py`
  - 下载单个 match 的完整调查轨迹
  - 解析 `stdinRecords`
  - 输出步骤数、阶段推进、提问分布、最终答案等分析
  - 对失败对局也会保留 `state / error / download_error`

- `summarize_versions.py`
  - 汇总历史提交版本
  - 汇总每个版本已知最好 batch 分数
  - 生成版本级总览

- `extract_story_unlocks.py`
  - 扫描 `Game2/runtime/**/analysis.json`
  - 提取关键剧情证据第一次可见的位置
  - 当前跟踪 Poker `102/103/104/203/204/205` 与 Yuan `703/704`
  - 输出到 `docs/generated/game2_story_unlocks.{md,json}`

- `compare_match_runs.py`
  - 对比多个已下载 match 的调查路径
  - 汇总每个 case 的步数、阶段、最终答案
  - 统计版本间新增/移除的问题，定位“同码不同分”与误导性追问

常用命令：

```bash
python3 /www/Game2/tools/submit_and_track.py \
  --source /www/Game2/deepclue_ai/v9/ai_v9.py \
  --entity-name g2base0310 \
  --remark 'game2 v9'

python3 /www/Game2/tools/run_batch_eval.py \
  --entity-name g2base0310 \
  --top-k 1

python3 /www/Game2/tools/run_batch_eval.py \
  --entity-name dummy \
  --batch-id 75635

python3 /www/Game2/tools/run_room_eval.py \
  --code-id <code_id> \
  --label n507x \
  --count 5 \
  --timeout 420 \
  --poll-interval 2

python3 /www/Game2/tools/analyze_match.py \
  --match-id 7421814 \
  --out-dir /www/Game2/runtime/manual_match_7421814

python3 /www/Game2/tools/summarize_versions.py

python3 /www/Game2/tools/extract_story_unlocks.py --limit 12

python3 /www/Game2/tools/compare_match_runs.py \
  --input v2_best=/www/Game2/runtime/manual_match_7421776_v2 \
  --input v2_repeat_admin=/www/Game2/runtime/batches/20260311_130148_g2v2ref0311_batch_75646/matches/7422137 \
  --input v7_407=/www/Game2/runtime/batches/20260311_130147_g2base0310_batch_75642/matches/7422058 \
  --out /www/docs/generated/game2_run_comparison.md
```
