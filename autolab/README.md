# Autolab for Game1

用于管理 `Game1` AI 版本、本地并行评测、累计 Elo 与 replay 分析。

## 1. 当前评测方式

评测已改为：

- 使用 `Game1/Ant-Game/AI/package_ai.sh` 打包 AI
- 使用 `Game1/Ant-Game/game/output/main` 作为真实对局内核
- 保存真实 `Game1` replay（JSON 数组格式）

这意味着当前 Elo 建立在真实 `Game1` 本地链路上，而不是旧 root 目录下已经失效的模拟逻辑上。

## 2. 关键文件

- `autolab_manage.py`
- `autolab_eval.py`
- `autolab_replay_analyze.py`
- `autolab/game1_match_runner.py`
- `autolab/evaluator.py`
- `autolab/replay_analysis.py`
- `autolab/registry.json`

## 3. 快速开始

```bash
python3 /www/autolab_manage.py list

python3 /www/autolab_eval.py \
  --mode round_robin \
  --versions cpp_v1_current,greedy,random,example \
  --games-per-pair 2 \
  --jobs 4 \
  --cpu-policy all \
  --doc-out /www/docs/generated/idle_eval_latest.md

python3 /www/autolab_replay_analyze.py --latest
```

## 4. 并发限制

当前硬上限：`8 CPU`

来源：

- `autolab_eval.py` 默认 cap 为 `8`
- `scripts/autolab_idle_eval_loop.sh` 默认最多 `8 jobs`

## 5. 结果输出

生产 Elo：

- `autolab/runtime/latest.json`

实验 Elo：

- `autolab/runtime/scopes/iter/latest.json`

生成型文档：

- `docs/generated/idle_eval_latest.md`
- `docs/generated/iter_eval_latest.md`
- `docs/generated/replay_analysis/`
