# Autolab for Game1

用于管理 `Game1` AI 版本、本地并行评测、累计 Elo 与 replay 分析。

## 1. 当前评测方式

当前 Elo 建立在真实 `Game1` 本地链路上：

- 使用 `Game1/Ant-Game/AI/package_ai.sh` 打包 AI
- 使用 `Game1/Ant-Game/game/output/main` 作为真实对局内核
- 本地回放格式与真实 `Game1` replay 对齐

默认生产循环当前口径：

- `adaptive`
- 最多 `24` 并发
- 默认 `--no-save-replays`
- 主要产物写入 `autolab/runtime/latest.json` 与 `docs/generated/idle_eval_latest.md`

额外说明：

- `autolab` 的持续评测默认不保存 replay、`packages`、`match_work`
- `strategy_probe` 是独立分析链路，允许保留 replay 与分析产物
- 当前 `strategy_probe` 默认方向是：
  - `3` 塔骨架
  - 近基地双核心 `heavy`
  - 单前置 `basic/quick` 弹性诱敌位
  - `quick` 默认按压力启用，不作为固定常驻配置
  - 更早 `ant2`
  - 低 churn

注意：

- `2026-04-03` 前后的规则版本不应混合比较 Elo 或 replay 结论
- `autolab` 负责当前本地评测口径，不负责替代 `Game1/Ant-Game` 规则真值

## 2. 关键文件

- `autolab_manage.py`
- `autolab_eval.py`
- `autolab_replay_analyze.py`
- `autolab/game1_match_runner.py`
- `autolab/evaluator.py`
- `autolab/replay_analysis.py`
- `autolab/registry.json`
- `scripts/autolab_idle_eval_loop.sh`

## 3. 快速开始

以下命令默认从仓库根目录执行：

```bash
python3 autolab_manage.py list

python3 autolab_eval.py \
  --mode gauntlet \
  --versions cpp_v3_unified_online,random \
  --games-per-pair 1 \
  --jobs 2 \
  --runtime-scope smoke \
  --no-auto-promote \
  --no-save-replays

python3 autolab_replay_analyze.py --scope smoke --latest
```

## 4. 当前默认版本口径

- 版本集合以 `autolab/registry.json` 为准
- 当前 champion 是 `cpp_v3_unified_online`
- 当前默认只保留 `random` 作为已验证 anchor baseline
- `greedy` 与 `example` 暂时降级为“待重验版本”，默认生产评测不启用

## 5. 时间与 replay 口径

- 官方 `Game1` 规则当前写的是单回合 `10s`
- 当前 match runner 会把 AI 对 game 的上报时间封顶到 `200ms`
- 当前不会在 `200ms` 处硬杀 AI
- 因此这里的 `200ms` 是本地工程口径，不是官方硬限制
- 当前 native judger 仍然按代码内置 `MAX_ROUND=512` 跑；`autolab_eval.py --max-rounds` 现在不能真正截断 native 对局，只能作为文档化配置输入
- 当前 Elo 会按 `ruleset_id` 过滤历史样本，避免把规则大改前后的结果混在一起
- replay 默认不保存；若需要逐局回放，显式传 `--save-replays`
- `scripts/game1_strategy_probe.py` 默认保留 replay 与分析结果，便于策略复盘

## 6. 结果输出

生产 Elo：

- `autolab/runtime/latest.json`

实验或 smoke scope：

- `autolab/runtime/scopes/<scope>/latest.json`

生成型文档：

- `docs/generated/idle_eval_latest.md`
- `autolab/runtime/scopes/<scope>/replay_analysis/`
