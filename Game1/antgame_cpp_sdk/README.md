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
- `include/antgame_sdk/native_sim.hpp`
  - `NativeSimulator`
  - 使用原生 `game/` 裁判逻辑推进回合
- `include/antgame_sdk/random_search_baseline.hpp`
  - 当前 C++ baseline 的核心决策逻辑
  - 包含随机 rollout、候选 action 搜索与终点评估
  - 当前终点评估已简化为：基地血、金币、塔可回收价值、塔类型/位置奖励、蚂蚁威胁与 `hold` 偏置
  - 当前双回合计划只保留核心九格 `Build -> Upgrade` 与 `Downgrade -> Followup`
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

## 6. Native Replay Probe

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

## 7. 当前推荐用法

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

## 8. Scope Notes

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
- `Upgrade` 当前只作为单回合动作
- 双回合搜索当前只保留：
  - 核心九格 `Build -> Upgrade`
  - `Downgrade -> Followup`，且第二步若为建塔也只允许核心九格
- 通过共享进攻 EV + 防守随机 rollout 做终点估值
- 首版实现使用外置轻量防守模拟，`NativeSimulator` 主要保留给校验、进攻 EV 采样与 replay 复算

当前轻量防守模拟的主要提速手段：

- O(1) 塔占位查询
- 静态风险场缓存
- move phase cache / tower-path cache 按需构建
