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
  - 使用固定容量数组为主，尽量避免在单回合模拟热路径中使用 STL
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
- future rollout：只保留贴身强制回收的 reactive 逻辑
- 首回合 rollout：只对威胁最高的最多 `5` 只蚂蚁做独立覆盖采样
  - 每只重点蚂蚁的所有正概率动作至少覆盖一次
  - 各蚂蚁独立打乱后按 rollout 下标配对，不做笛卡尔积硬枚举
  - 单个 rollout 的样本权重是这些重点蚂蚁所选动作真实概率的乘积
- 终点评估：基地血、塔价值、金币、worker threat、combat threat

当前实现还包含几个重要约束：

- 所有组合操作使用严格合法性检查
  - 整组非法就整组丢弃
- 若同回合既拆塔又建塔，则总是先拆后建
- 若同回合拆多座塔，则优先拆当前血量更高的塔
- `C1` 防守路线当前以 `Mortar / Quick / Sniper` 为主，不再把 `Heavy` 当作主线塔
- 当前 lure 建塔不再做额外位置打分
  - 所有合法 lure 槽位等价进入候选
  - 当前已开放除 `C / L / R / LL / RR` 系列之外的旧版位置槽位
- future rollout 中的自适应操作当前只保留“战斗蚁贴身时强制降级/拆塔回收”
  - 不再每个未来回合重新生成完整 `base × lure` 计划
  - 这是为了降低 STL/plan 生成开销，并避免 rollout 里引入过强的额外主动策略

## 4. Build

```bash
cd Game1/antgame_cpp_sdk
make
```

常见产物：

- `build/libantgame_cpp_sdk.a`
- `build/sdk_smoke`
- `build/sdk_json_runner`
- `build/sdk_lure_inspector`
- `build/sdk_lure_perf`
  - 基于 replay 抽样若干回合，测当前 `lure_strategy` 的整套决策、根计划生成、rollout 和底层模拟 profile
- `build/sdk_defense_parity`
  - 从 replay 指定回合出发，对比轻量 `DefenseSimulator` 与 native 模拟的多 rollout 终点评估均值

## 5. Smoke

```bash
cd Game1/antgame_cpp_sdk
make smoke
```

## 6. Perf / Parity

常用性能拆解：

```bash
cd Game1/antgame_cpp_sdk
build/sdk_lure_perf \
  ../antgame_ai_cpp/eval_partial_256_union_2026_04_21/matches/seed_0003/unused_game_replay.json \
  0 80 220 20 1 96 384
```

常用轻量模拟对拍：

```bash
cd Game1/antgame_cpp_sdk
build/sdk_defense_parity \
  ../antgame_ai_cpp/eval_partial_256_union_2026_04_21/matches/seed_0003/unused_game_replay.json \
  100 0 1000 6 123456789
```

当前性能口径：

- `NativeSimulator` 是官方 `Ant-Game/game` C++ 逻辑封装，用于真值同步和对拍
- `DefenseSimulator` 是搜索用快速模拟，不复制官方对象图
- `DefenseSimulator::clone()` 只复制真实局面字段，不复制派生 move cache / lookup cache
  - 当前 `MoveCache` 约 `208KB`
  - 避免在每个 rollout clone 时复制该缓存，是当前最重要的性能优化之一
- 当前 2026-04-26 抽样 profile：
  - 完整决策平均约 `0.32s`
  - 单个 best rollout 约 `190us`
  - 纯 6 回合模拟约 `180us`
  - 内层最大热点仍是 `move_cache` 反向路径规划
- 当前快速模拟默认忽略每 10 回合随机移动机制
  - 这是搜索口径选择
  - 做 native 对拍时应尽量选择不跨 10 回合随机移动窗口的 case

## 7. Self-Play

若只想跑完整对局汇总，可用：

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

若要严格停在前 `256` 回合并保留该窗口的 replay / stderr log，应改用：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_partial_selfplay.py \
  --target cpp_heavy_baseline \
  --seeds 1:8 \
  --debug-seeds 1:8 \
  --jobs 8 \
  --max-rounds 256 \
  --output-dir ./eval_partial_full_log_256 \
  --force
```

## 8. 当前规则同步备注

已确认：

- 官方基础收入为每 `2` 回合 `+3`
- 超武部署当回合立即生效
- 前手 `EMP` 可直接影响后手同回合塔操作

如果未来 `Ant-Game` 更新，应优先重新检查：

- `sdk.hpp`
- `native_sim.hpp`
- `random_search_baseline.hpp`
- `lure_strategy.hpp`
- `sdk_defense_parity.cpp`

是否仍与上游一致。
