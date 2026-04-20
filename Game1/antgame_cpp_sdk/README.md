# Game1 C++ SDK

这是一套面向 `Game1/Ant-Game` 当前规则实现的外置原生 C++ SDK，目标是给 Game1 C++ AI 提供统一的：

- 比赛协议读写
- 公共状态镜像与规则查询
- 基于原生裁判内核的高速本地模拟
- 可直接复用的随机搜索 baseline 决策逻辑

## 1. 代码边界

- SDK 与 native rollout 封装位于当前目录
- `Ant-Game` 只作为规则/runtime 只读依赖，不在其中落 SDK 改动
- 当前保留的 Game1 C++ AI 源码在 `../antgame_ai_cpp/`
- 目前实际保留的 AI 入口为 `../antgame_ai_cpp/cpp_heavy_baseline/`

## 2. 主要接口

- `include/antgame_sdk/sdk.hpp`
  - 常量/枚举/地图几何
  - `PublicState`
  - `ProtocolIO`
- `include/antgame_sdk/position_slots.hpp`
  - 旧版 AI 的完整位置定义
  - `BASE/C1/C2/.../STORM`
  - 双边 35 个位置坐标与位置名查询
- `include/antgame_sdk/random_search_params.hpp`
  - 当前随机搜索最关键的 rollout / 估值 / 惩罚参数
  - 核心九格位置奖励也集中在这里
- `include/antgame_sdk/native_sim.hpp`
  - `NativeSimulator`
  - 使用原生 `game/` 裁判逻辑推进回合
- `include/antgame_sdk/random_search_baseline.hpp`
  - 当前 C++ baseline 的核心决策逻辑
  - 包含随机 rollout、候选 action 搜索与终点评估
  - 当前重构后已把：
    - 旧版位置定义移到 `position_slots.hpp`
    - 关键参数移到 `random_search_params.hpp`
  - 头文件内部主要保留：
    - 轻量模拟
    - 候选动作生成
    - 终点评估
    - 调试输出
- `include/antgame_sdk/heavy_baseline.hpp`
  - 仅保留兼容包装，内部已转发到 `random_search_baseline.hpp`

## 3. Build

```bash
cd Game1/antgame_cpp_sdk
make
```

说明：

- `Makefile` 现已跟踪 `Ant-Game` 头文件依赖；上游规则代码更新后，重新执行 `make` 即会自动重编受影响对象
- 默认使用 `-O3 -DNDEBUG`
- 不要复用旧 `build/` 产物去判断当前规则是否一致

常见生成物：

- `build/libantgame_cpp_sdk.a`
- `build/sdk_example_ai`
- `build/sdk_smoke`
- `build/sdk_json_runner`
- `build/sdk_random_search_bench`
- `build/sdk_rollout_probe`

## 4. Smoke

```bash
cd Game1/antgame_cpp_sdk
make smoke
```

## 5. 示例与基准

- `examples/sdk_example_ai.cpp`
  - 最小可运行协议示例
- `examples/sdk_smoke.cpp`
  - 基础连通性验证
- `examples/sdk_json_runner.cpp`
  - 本地状态/操作驱动工具
- `examples/sdk_random_search_bench.cpp`
  - 当前随机搜索 baseline 的调用耗时基准
- `examples/sdk_rollout_probe.cpp`
  - 从 replay 精确回放到指定回合后，直接做 action 复算
  - 可同时比较：
    - 轻量 `DefenseSimulator` 的 Monte Carlo 估值
    - 原生 `NativeSimulator` 的 Monte Carlo 估值

## 6. Self-Play 调试

当前推荐直接使用：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target cpp_heavy_baseline \
  --seeds 1:32 \
  --debug-seeds 7,15,20,24 \
  --jobs 32 \
  --output-dir ./eval_current_strength \
  --force
```

该工具会自动：

- 打包当前 `cpp_heavy_baseline`
- 并发启动镜像 self-play
- 为每个 seed 保留：
  - `matches/seed_xxxx/replay.json`
  - `matches/seed_xxxx/ai0.stderr.log`
  - `matches/seed_xxxx/ai1.stderr.log`
  - `matches/seed_xxxx/match_summary.json`
- 汇总生成：
  - `summary.json`

补充工具：

- `../antgame_ai_cpp/tools/eval_cpp_partial_selfplay.py`
  - 固定回合截断的 partial self-play
  - 适合快速检查某次改动有没有把协议、搜索和调试日志链路弄坏
- `../antgame_ai_cpp/tools/plot_old_ai_positions.py`
  - 把旧版 AI 位置名直接画到当前地图上
  - 便于后续按 `C1/C2/L1/...` 讨论站位

调试模式约定：

- 默认 seed 使用 `summary`
  - 保留每回合摘要、候选总数、最终选择、耗时
- `--debug-seeds` 指定的 seed 使用 `plans`
  - 额外输出每回合每个候选 action 的估值拆解

做强度分析时，应优先同时看三类信息：

- `summary.json` 的整体统计
- 典型 seed 的 `replay.json`
- 对应 `ai*.stderr.log` 的候选分数与最终选择

## 7. Native Replay Probe

当搜索日志里出现“明显亏钱但被强推”的操作时，不要先调 bandit 分配，先做原生 replay 复算。

用法示例：

```bash
cd Game1/antgame_cpp_sdk
make build/sdk_rollout_probe
./build/sdk_rollout_probe \
  ../antgame_ai_cpp/tmp_eval_score_debug_15_20_24/matches/seed_0024/replay.json \
  199 0 5000 hold 11:4:9
```

输出会同时给出：

- 当前轻量搜索模拟的估值
- 原生 `NativeSimulator` 从同一隐藏态分叉不同未来随机种子的估值

当前已确认：

- `seed_0024 round 199 player 0` 上，轻量搜索模拟会严重高估 `build 11:4:9` 相对 `hold` 的保血收益
- 因此 baseline 的搜索分数不能直接当成 native 真值
- 若要审计动作价值，应优先使用该 probe

## 8. 当前推荐用法

若要构建当前保留的 Game1 C++ baseline：

```bash
cd Game1/antgame_ai_cpp/cpp_heavy_baseline
make
```

若要打包提交版本：

```bash
cd Game1/antgame_ai_cpp
bash package_ai.sh cpp_heavy_baseline
```

## 9. Scope Notes

这版 SDK 优先解决：

- C++ AI 不再手写协议
- 在线状态处理和费用/合法性检查统一
- 本地 rollout / 对拍可直接走原生裁判内核

高层策略库没有一并迁入；当前保留目标是正确、简洁、可高速模拟。

当前规则同步备注：

- 超武在玩家操作阶段部署后立即生效
- `Lightning Storm` 部署当下就会先结算一次敌蚁伤害，同回合攻击阶段不会重复结算
- 玩家 `0` 本回合释放的 `EMP`，可以直接让玩家 `1` 同回合在覆盖区内的建/升/降塔失败

当前 baseline 的行为边界：

- 通过简化终点评估与 `hold` 偏置默认偏向少操作
- 主搜索只围绕我方塔、敌方蚂蚁、我方闪电、敌方已激活超武展开
- 仅搜索有限的建塔/升级/降级/闪电候选，不考虑基地升级
- 位置相关逻辑统一基于旧版位置名
  - `BASE/C1/C2/C3/L1/L2/L3/R1/R2/R3/...`
- `Upgrade` 当前只作为单回合动作
  - 当前单回合升级候选为：
    - `Basic -> Heavy / Mortar / Quick`
    - `Heavy -> Bewitch`
    - `Mortar -> Pulse`
    - `Quick -> QuickPlus`
- 双回合搜索当前只保留：
  - 核心九格 `Build -> Upgrade`
  - `Downgrade -> Followup`，且第二步若为建塔也只允许核心九格
- 当前暂时关闭“我方进攻补值”共享 EV，只依赖防守 rollout 终点评估
- 防守 / 普通 action 搜索 horizon 为 `8` 回合
- 闪电候选当前改为：
  - 盘面全格打分而不是只看敌蚁当前格
  - 合并当前 + 未来两回合敌蚁可能位置热度
  - 计入敌方塔在 `Lightning Storm` 下的等效价值损伤
  - 若当前处在敌方超武生效窗口内，会给闪电额外奖励
  - 先做簇去重，再保留最多 `10` 个候选中心
  - 每中心 `20` 次 rollout，`10` 回合 horizon
- 核心位置奖励当前为：
  - `C1=50, C2=50, C3=30`
  - `L1=R1=30, L2=R2=20, L3=R3=15`
- 首版实现使用外置轻量防守模拟，`NativeSimulator` 主要保留给校验、进攻 EV 采样与 replay 复算

当前轻量防守模拟的主要提速手段：

- O(1) 塔占位查询
- 静态风险场缓存
- move phase cache / tower-path cache 按需构建
- rollout 热路径已改为固定容量存储
  - `DefenseSimulator` 内的塔、蚂蚁、effect、move-option、forced-move 均不再使用 STL 容器
  - `reverse_weighted_plan` 不再依赖 `priority_queue`
  - `simulate_round -> move_phase / teleport_phase / manage_ants / update_effects` 这条链路不再使用 `vector/remove_if`
- 当前轻量 rollout 已显式忽略每 `10` 回合一次的随机移动机制
  - 原因是其扰动强、影响蚂蚁占比小，纳入后反而更容易放大搜索噪声
  - 这属于有意识的近似，而不是规则同步 bug
- 几何缓存进一步预处理：
  - 有效格索引 / 邻接 / all-pairs 距离
  - 半径 `<= 4` 的范围格子枚举
  - 本回合可走邻接表
- `reverse_weighted_plan` 当前已改为：
  - 预计算 step-cost
  - 一维 cell-index 存储
  - 固定容量最小堆
  - `float` 风险/路径缓存

当前正确性修复备注：

- `make_defense_simulator()` 不再为每只蚂蚁重复构造隐藏态 `vector`
- `important_ants()` 已修复 top-k 选择中的固定容量溢出问题
- 当前优化目标仍然是“逻辑等价实现”，不是简化规则

## 10. 当前重构说明

本轮代码整理后，和之后调参/讨论最相关的入口主要是：

- `include/antgame_sdk/position_slots.hpp`
  - 以后描述位置时直接使用旧版位置名
- `include/antgame_sdk/random_search_params.hpp`
  - 以后调 rollout 数、估值权重、位置奖励、惩罚时优先看这里
- `include/antgame_sdk/random_search_baseline.hpp`
  - 这里只保留搜索实现本身
  - 已删除一批长期固定为 `0` 的旧惩罚项与未使用 helper

最近一次重构后的基础验证：

- `pytest -q tests/test_cpp_sdk.py`
  - `11 passed`
- `build/sdk_smoke`
  - `cpp_sdk smoke ok`
- 小样本 partial self-play
  - 重构后仍能产出决策日志与逐候选调试日志
  - `seed_0024` 已确认 `plan` / `decision` 调试输出正常

仓库清理约定：

- `Game1/antgame_ai_cpp` 下的评测结果、partial replay、临时验证输出、位置图均视为生成物
- 这些结果现在已加入 `.gitignore`
- 需要长期保留的只应是：
  - baseline 入口
  - SDK
  - 工具脚本
  - 文档

当前定点性能样本：

- `build/sdk_random_search_bench`
- 当前机器上的最近样本：
  - `sdk_random_search_bench 2 1`
    - 3 次均值约 `409205 us / decision`
  - `sdk_random_search_bench 3 1`
    - 3 次均值约 `428176 us / decision`
    - 最好一次约 `397420 us / decision`
- `gprof` 结果显示，当前主要热区仍然是：
  - `reverse_weighted_plan`
  - `prepare_move_cache`
  - `refresh_static_risk_fields`

当前校验备注：

- `sdk_smoke` 通过
- `sdk_rollout_probe` 在真实 replay 上对比 `direct vs native` 时，终点评分仍存在可见误差
- 因此当前搜索模拟仍然只能视为近似估值器；关键动作仍需用 probe 复算
