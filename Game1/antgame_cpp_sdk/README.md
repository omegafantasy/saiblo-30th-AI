# Game1 C++ SDK

这是当前 `Game1` 的外置 C++ SDK。

目标：

- 不修改 `Ant-Game/`
- 以当前 `Ant-Game` 代码为规则真值
- 给 `Game1/antgame_ai_cpp/` 提供统一的协议、状态镜像和高速模拟能力

## 1. 代码边界

- 规则真值：`../Ant-Game/`
- SDK：当前目录
- 冻结 baseline AI：`../antgame_ai_cpp/cpp_heavy_baseline/`
- 当前 v2 AI：`../antgame_ai_cpp/cpp_lure_v2/`
- 当前 v3 AI：`../antgame_ai_cpp/cpp_lure_v3/`

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
- `include/antgame_sdk/lure_strategy_baseline.hpp`
  - 冻结 baseline 的核心决策逻辑
- `include/antgame_sdk/lure_strategy_baseline_params.hpp`
  - 冻结 baseline 的策略参数入口
  - 参数类型为 `BaselineLureStrategyTuning`，访问函数为 `baseline_lure_config()`
- `include/antgame_sdk/lure_strategy_v2.hpp`
  - 当前 v2 的核心决策逻辑
  - 包含 root 候选生成、rollout、两层评估、调试输出
- `include/antgame_sdk/lure_strategy_v2_params.hpp`
  - 当前 v2 的策略参数入口
  - 参数类型为 `V2LureStrategyTuning`，访问函数为 `v2_lure_config()`
- `include/antgame_sdk/lure_strategy_v3.hpp`
  - v3 的核心决策逻辑
  - 以 v2 为起点，额外探索进攻性 `Emergency Evasion` 后处理
- `include/antgame_sdk/lure_strategy_v3_params.hpp`
  - v3 的策略参数入口
  - 参数类型为 `V3LureStrategyTuning`，访问函数为 `v3_lure_config()`
- `include/antgame_sdk/lure_strategy.hpp`
  - 默认兼容入口，目前同步为 v2
- `include/antgame_sdk/lure_strategy_params.hpp`
  - 默认兼容参数入口，目前只是 v2 的 alias；调 v2 参数应直接改 `lure_strategy_v2_params.hpp`
- `include/antgame_sdk/position_slots.hpp`
  - 旧版位置名定义
  - 后续讨论站位统一使用这套命名

## 3. Baseline / V2 口径

`cpp_heavy_baseline` 已冻结在 `lure_strategy_baseline.hpp` / `lure_strategy_baseline_params.hpp`。2026-04-27 已用当前 v2 完全覆盖 baseline，因此 baseline 与 v2 当前是同一策略冻结点。默认兼容文件 `lure_strategy.hpp` / `lure_strategy_params.hpp` 也指向 v2 口径；后续探索应新开 v3，不直接改 baseline。

参数已经拆成两套独立符号：

- baseline：`BaselineLureStrategyTuning` / `baseline_lure_config()`
- v2：`V2LureStrategyTuning` / `v2_lure_config()`

因此文件和符号仍然独立，后续新版本不会污染冻结 baseline。`lure_strategy_params.hpp` 只保留旧 include 兼容，不作为主要调参入口。

v3 已新开独立入口，不改 baseline / v2：

- AI 目录：`../antgame_ai_cpp/cpp_lure_v3/`
- 策略文件：`include/antgame_sdk/lure_strategy_v3.hpp`
- 参数文件：`include/antgame_sdk/lure_strategy_v3_params.hpp`
- 打包目标：`package_ai.sh cpp_lure_v3`

v3 当前只在 v2 最优行动之后追加一个进攻性 `Emergency Evasion` 后处理。触发条件是：敌方闪电未生效、敌方闪电 CD 至少 `10`，执行 best action 后金币仍 `>100`，且 C1 仍为 `Sniper`，并且存在一个回避中心覆盖至少 `5` 只己方 `Worker`。战斗蚁不计入覆盖数，平局时优先更靠近敌方基地的位置。

2026-04-27 已完成 v3 vs v2 座位平衡 32 局官方对局：

- 结果目录：`../antgame_ai_cpp/tmp_v3_vs_v2_32_p0/` 与 `../antgame_ai_cpp/tmp_v3_vs_v2_32_p1/`
- 总胜负：v3 `16`，v2 `16`
- 平均终局血量：v3 `19.53125`，v2 `19.1875`
- 平均终局金币：v3 `327.40625`，v2 `321.5`
- v3 紧急回避实际触发 `1` 次
- 触发样本：`seed_0015` 第 `312` 回合，`Emergency Evasion` at `(4,10)`，覆盖 `5` 工蚁、`0` 战斗蚁
- 未发现非法操作或 replay 写入异常

baseline / v2 的共同核心口径是：

- 根节点搜索：`hold + base + lure + recycle_base*lure` 加上独立 `lightning`
  - `base` 和 `lure` 不再乘算
  - 只有纯回收类 `base` 动作可与 `lure` 组合
  - 全 hold 只使用一次统一 `hold_bonus`
- future rollout：只保留贴身强制回收的 reactive 逻辑
- future rollout 的防守视角不生成未来基地蚂蚁
  - `DefenseSimulator` 使用 `ignore_enemy_spawns`
  - native 对拍使用 `advance_round_without_base_spawns()`
  - 实际对局同步仍使用官方 `resolve_turn()` / `advance_round()`
- 首回合 rollout：只对威胁最高的最多 `5` 只蚂蚁做独立覆盖采样
  - 每只重点蚂蚁的所有正概率动作至少覆盖一次
  - 各蚂蚁独立打乱后按 rollout 下标配对，不做笛卡尔积硬枚举
  - 单个 rollout 的样本权重是这些重点蚂蚁所选动作真实概率的乘积
- 终点评估：基地血、塔价值、金币、worker threat、combat threat

当前实现还包含几个重要约束：

- 所有组合操作使用严格合法性检查
  - 整组非法就整组丢弃
- 当前 `base` 可生成受限 swap 操作，但不生成完整任意 op-list
- `lure` 的 relocate 仍允许“拆/卖 + 建”，并按先拆后建排序
- 若同回合拆多座塔，则优先拆当前血量更高的塔
- `base` 操作使用旧版位置名中的 `C / L / R / LL / RR` 系列槽位
- 非 lure 塔最多允许 `max_non_lure_towers = 2`
- `base` 二级塔候选按 C1 状态区分：
  - C1 自身保留 `Heavy` 与 `Quick -> Sniper` 路线
  - C1 已是 `Sniper` 时，其他 base 槽位二级候选为 `Heavy / Quick / Mortar`
  - C1 未成 `Sniper` 时，其他 base 槽位二级候选为 `Heavy / Mortar`
  - 任意 base 槽位上的 `Quick` 后续都只允许继续升为 `Sniper`
  - `Sniper` 是当前唯一 3 级塔候选
- `base` followup 支持最多 3 个未来单回合步骤：
  - `build slot -> upgrade allowed level-2 tower`
  - `upgrade Basic -> Quick -> Sniper`
  - `downgrade slot -> downgrade same slot`
  - `downgrade/sell source to bottom -> build another base slot`
  - `downgrade/sell source to bottom -> build another base slot -> upgrade allowed level-2 tower`
  - swap 源塔只允许 Basic 或一级塔，最多连续 2 次降级/出售，不处理顶级塔卖到底
  - 同回合多塔操作只允许多个 `downgrade/sell`
- 除 `C1` 外，base 槽位不做额外结构奖励/惩罚
- 当前 lure 建塔不再做额外位置打分
  - 所有合法 lure 槽位等价进入候选
  - 当前已开放除 `C / L / R / LL / RR` 系列之外的旧版位置槽位
- future rollout 中的自适应操作当前只保留“战斗蚁贴身时强制降级/拆塔回收”
  - 不再每个未来回合重新生成完整 `base/lure` 计划
  - 这是为了降低 STL/plan 生成开销，并避免 rollout 里引入过强的额外主动策略
- 闪电候选当前是单闪电：
  - 遍历以棋盘唯一中心 `(9,9)` 为中心、六边形距离 `<= lightning_center_radius` 的合法中心
  - 默认半径为 `5`，因此候选中心数为 `1 + (1+2+3+4+5)*6 = 91`
  - 不与 `base/lure` 或前置降级/拆塔组合
  - 全部闪电中心共享 `lightning_ucb_total_rollouts` 的 UCB rollout 预算

当前冻结点还包含：

- 常规 action rollout 采用 10 回合两层评估
  - 第 6 回合和第 10 回合分别估值
  - 用 `mid_eval_weight` 混合，默认第 6 回合权重 `0.5`
- 允许 `basic -> quick -> sniper` 三连升候选
  - 仅限 `C / L / R` 系列格子
  - 只有 `C1` 继续获得额外奖励或转型惩罚
- 闪电在敌方无激活超武效果时施加 `lightning_no_enemy_super_penalty`
- Sniper 降级额外施加 `sniper_downgrade_penalty`
- C1 出 Sniper 前，非 C1 位置不生成 Quick / Sniper 路线
- base+lure 组合最多只关联同一座 base 塔的回收，不生成多座 base 塔同时降级
- 当战斗蚁贴身己方塔时，闪电候选额外允许“该塔降级/拆 + 闪电”

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
- 搜索/对拍中的 native 未来推进默认走“无基地出兵”口径，避免官方基地出兵消耗 RNG 后再裁剪导致与 fast 不一致
- `DefenseSimulator` 是搜索用快速模拟，不复制官方对象图
- `DefenseSimulator::clone()` 只复制真实局面字段，不复制派生 move cache / lookup cache
  - 当前 `MoveCache` 约 `208KB`
  - 避免在每个 rollout clone 时复制该缓存，是当前最重要的性能优化之一
- 当前 2026-04-27 全 log profile：
  - 16 组 256 回合：P0/P1 平均决策约 `1.32s / 1.13s`
  - 16 组 512 回合：P0/P1 平均决策约 `1.38s / 1.18s`
  - 有闪电候选时，闪电 UCB 不是主要耗时；普通 action 的 `plan_count * rollout_count * horizon` 仍占大头
  - 内层最大热点仍是 `move_cache` 反向路径规划
- 当前快速模拟默认忽略每 10 回合随机移动机制
  - 这是搜索口径选择
  - 做 native 对拍时应尽量选择不跨 10 回合随机移动窗口的 case
- 2026-04-27 抽样 fast/native 对拍：
  - 32 个 512 回合 self-play replay 中后期 case，`1000` rollout、`6` 回合窗口
  - 起点均避开跨 10 回合随机移动窗口
  - 终点评分平均绝对差约 `12.04`，最大约 `39.94`
  - 基地血平均绝对差约 `0.049`，最大约 `0.246`
  - 金币平均绝对差约 `0.080`
  - 32 个 case 中包含 4 个 active effect 根状态

## 7. 当前文件结构

- `include/antgame_sdk/sdk.hpp`
  - 协议、公共状态、基础规则常量、位置合法性和操作合法性
- `include/antgame_sdk/native_sim.hpp`
  - 官方 native 封装，负责 replay 同步、真值推进和对拍
- `include/antgame_sdk/random_search_baseline.hpp`
  - 搜索用 `DefenseSimulator`，负责高速防守模拟
- `include/antgame_sdk/lure_strategy_baseline.hpp`
  - 冻结 baseline 决策主体
- `include/antgame_sdk/lure_strategy_baseline_params.hpp`
  - 冻结 baseline 参数入口
- `include/antgame_sdk/lure_strategy_v2.hpp`
  - 当前 v2 决策主体，负责候选生成、rollout、UCB 闪电、两层估值和 debug 输出
- `include/antgame_sdk/lure_strategy_v2_params.hpp`
  - 当前 v2 参数入口
- `include/antgame_sdk/lure_strategy_v3.hpp`
  - 当前 v3 决策主体，继承 v2 搜索并追加进攻性 `Emergency Evasion`
- `include/antgame_sdk/lure_strategy_v3_params.hpp`
  - 当前 v3 参数入口
- `include/antgame_sdk/lure_strategy.hpp`
  - 默认兼容入口，目前等同 v2
- `include/antgame_sdk/lure_strategy_params.hpp`
  - 默认兼容参数入口，目前等同 v2
- `include/antgame_sdk/position_slots.hpp`
  - 旧版位置名与坐标映射
- `examples/sdk_lure_inspector.cpp`
  - simviz 后端和单回合在线审计入口
- `examples/sdk_lure_perf.cpp`
  - 决策、候选生成、普通 action、闪电 UCB、底层模拟 profile
- `examples/sdk_defense_parity.cpp`
  - fast/native 多 rollout 对拍
- `examples/sdk_rollout_probe.cpp`
  - 指定 plan 的直接 rollout 探针

## 8. Self-Play

若只想跑完整对局汇总，可用：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target cpp_lure_v2 \
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

若要测试两个不同版本，应做座位平衡对战。例如历史上测试 v2 相对旧 baseline 的命令为：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target0 cpp_heavy_baseline \
  --target1 cpp_lure_v2 \
  --seeds 1:16 \
  --jobs 16 \
  --output-dir ./eval_baseline_p0_v2_p1 \
  --force

python tools/eval_cpp_selfplay.py \
  --target0 cpp_lure_v2 \
  --target1 cpp_heavy_baseline \
  --seeds 17:32 \
  --jobs 16 \
  --output-dir ./eval_v2_p0_baseline_p1 \
  --force
```

2026-04-27 baseline 覆盖前曾完成一组 32 局 v2-vs-旧-baseline 座位平衡测试：

- 结果目录：`Game1/antgame_ai_cpp/eval_v2_vs_baseline_512_32_20260427/combined_vs_summary.json`
- v2 `17/32`，baseline `15/32`
- v2 平均终局血量 `19.5`，baseline `17.875`
- v2 平均终局金币 `440.75`，旧 baseline `362.375`

覆盖后，`cpp_heavy_baseline` 与 `cpp_lure_v2` 当前应视为同一冻结点，不再用二者互打衡量强度差。

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

## 9. 当前规则同步备注

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
