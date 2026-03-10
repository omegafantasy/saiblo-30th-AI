# Game1 本地评测、Autolab 与 Elo

## 1. 当前可信链路

当前 `Game1` 的本地批评测链路以真实 `Game1/Ant-Game` 对局二进制为基准，不再依赖旧根目录下已经失效的 Python 逻辑模拟器。

核心组件：

- `autolab/common.py`
  - `ANT_GAME_DIR` 现在从配置读取，默认指向 `Game1/Ant-Game`
- `autolab/game1_match_runner.py`
  - 负责打包 AI、拉起 `game/output/main`、转发协议并保存 replay
- `autolab/evaluator.py`
  - 负责并行调度、累计 Elo、最新轮次产物输出
- `autolab/registry.json`
  - 当前只保留 `Game1` 仍然存在且可执行的版本

## 2. 版本注册表

当前最小可信版本集：

- `cpp_v1_current`
- `greedy`
- `random`
- `example`
- `cpp_v2_antwar_structured`
  - 仅保留作实验候选，默认 `enabled=false`

结论：旧 `/www/ai_cpp/v*` 版本已经全部退出当前 Elo 池。

## 3. CPU 与并发约束

硬约束保持为最多 `8 CPU`：

- `autolab_eval.py`
  - `DEFAULT_MAX_JOBS_CAP = 8`
- `scripts/autolab_idle_eval_loop.sh`
  - 默认 `MAX_JOBS=8`
- `scripts/systemd/autolab-idle-eval.service`
  - 描述也已写为 `up to 8 CPUs`

说明：

- 生产评测默认 `idle_only + pin_cpu`
- 评测 worker 与其子进程会继承 CPU 亲和性
- 这样 `game` 与 AI 子进程都会落在选中的核心集合内

## 4. 生产 Elo 与实验 Elo

生产 Elo：

- 路径：`autolab/runtime/latest.json`
- 口径：累计 Elo、累计总对局
- 用途：唯一权威榜、champion 判定

实验 Elo：

- 路径：`autolab/runtime/scopes/iter/latest.json`
- 用途：候选筛选，不直接作为最终强弱结论

当前实现要点：

- 生产 `latest.json` 使用累计口径重算 Elo
- 已不存在或不可执行的版本会自动从累计榜中剔除
- `elo_web/server.py` 直接读取 `latest.json` 与 `scopes/iter/latest.json`

## 5. Replay 保存与分析

从现在起，本地评测默认保存全部 replay。

生产 replay：

- `autolab/runtime/replays/<eval_tag>/`

实验 replay：

- `autolab/runtime/scopes/<scope>/replays/<eval_tag>/`

分析器：

- `autolab/replay_analysis.py`
  - 已改为 `Game1` 真实 replay 格式：JSON 数组，每帧包含 `op0/op1/round_state/seed`
- `autolab_replay_analyze.py`
  - 包装调用入口

生成文档默认落点：

- `docs/generated/idle_eval_latest.md`
- `docs/generated/iter_eval_latest.md`
- `docs/generated/replay_analysis/*.md`

## 6. 当前已知限制

- `max_rounds` 参数目前只保留在评测配置中，`Game1` 真实对局仍由游戏内核自己终止，不能像旧 Python 逻辑一样随意截断。
- `cpp_v1` 仍是“Python SDK 桥接 + C++ 决策”的本地形态，因此本地 Elo 强度结论只对本地链路直接成立。
