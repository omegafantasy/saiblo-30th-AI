# Game1 C++ SDK

这是当前 `Game1` 的外置 C++ SDK。

目标：

- 不修改 `Ant-Game/`
- 以当前 `Ant-Game` 代码为规则真值
- 给 `Game1/antgame_ai_cpp/` 提供统一的协议、状态镜像和高速模拟能力

## 1. 代码边界

- 规则真值：`../Ant-Game/`
- SDK：当前目录
- 当前实际 AI 入口：`../antgame_ai_cpp/cpp_heavy_baseline/`

`Ant-Game/` 只作为只读依赖，不在其中放 SDK 或 AI 改动。

## 2. 当前主要文件

- `include/antgame_sdk/sdk.hpp`
  - 公共状态、协议读写、规则查询
- `include/antgame_sdk/native_sim.hpp`
  - `NativeSimulator`
  - 用官方逻辑推进回合，主要用于同步、校验和对拍
- `include/antgame_sdk/random_search_baseline.hpp`
  - 当前轻量防守模拟器 `DefenseSimulator`
  - baseline 搜索所需的高速模拟能力
- `include/antgame_sdk/lure_strategy.hpp`
  - 当前 baseline 的核心决策逻辑
  - 包含 root 候选生成、rollout、终点评估、调试输出
- `include/antgame_sdk/lure_strategy_params.hpp`
  - 当前 baseline 的策略参数入口
- `include/antgame_sdk/position_slots.hpp`
  - 旧版位置名定义
  - 后续讨论站位统一使用这套命名

## 3. 当前 baseline 口径

当前 baseline 不是旧版“两回合 random search”，而是：

- 根节点搜索：`base × lure` 加上独立 `lightning`
- future rollout：每回合调用 reactive `base + lure` 控制器
- 终点评估：基地血、塔价值、金币、worker threat、combat threat

当前实现还包含几个重要约束：

- 所有组合操作使用严格合法性检查
  - 整组非法就整组丢弃
- 若同回合既拆塔又建塔，则总是先拆后建
- 若同回合拆多座塔，则优先拆当前血量更高的塔
- 当前 lure 建塔不再做额外位置打分
  - 所有合法 lure 槽位等价进入候选

## 4. Build

```bash
cd Game1/antgame_cpp_sdk
make
```

常见产物：

- `build/libantgame_cpp_sdk.a`
- `build/sdk_smoke`
- `build/sdk_json_runner`

## 5. Smoke

```bash
cd Game1/antgame_cpp_sdk
make smoke
```

## 6. Self-Play

当前推荐直接用 AI 目录下的工具：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target cpp_heavy_baseline \
  --seeds 1:8 \
  --debug-seeds 1 \
  --jobs 8 \
  --max-rounds 256 \
  --output-dir ./eval_current \
  --force
```

输出会包含：

- `matches/seed_xxxx/replay.json`
- `matches/seed_xxxx/ai0.stderr.log`
- `matches/seed_xxxx/ai1.stderr.log`
- `matches/seed_xxxx/match_summary.json`
- `summary.json`

进一步分析：

```bash
cd Game1/antgame_ai_cpp
python tools/analyze_selfplay_batch.py ./eval_current
```

注意：

- 当前官方 `game/output/main` 不会因为 init 里的 `config.max_rounds` 自动提前结束对局
- 因而即使传了 `--max-rounds 256`，实际 replay 仍可能长于 `256`
- 若要做严格固定回合分析，应对 replay 与 `ai*.stderr.log` 的 decision 记录手动裁到前 `N` 回合

## 7. 当前规则同步备注

已确认：

- 官方基础收入为每 `2` 回合 `+3`
- 超武部署当回合立即生效
- 前手 `EMP` 可直接影响后手同回合塔操作

如果未来 `Ant-Game` 更新，应优先重新检查：

- `sdk.hpp`
- `native_sim.hpp`
- `random_search_baseline.hpp`
- `lure_strategy.hpp`

是否仍与上游一致。
