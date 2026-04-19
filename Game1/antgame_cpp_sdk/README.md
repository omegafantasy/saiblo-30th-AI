# Game1 C++ SDK

这是一套面向 `Game1/Ant-Game` 当前规则实现的外置原生 C++ SDK，目标是给 Game1 C++ AI 提供统一的：

- 比赛协议读写
- 公共状态镜像与规则查询
- 基于原生裁判内核的高速本地模拟
- 可直接复用的简化 baseline 决策逻辑

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
- `include/antgame_sdk/heavy_baseline.hpp`
  - 当前 C++ baseline 的核心决策逻辑
  - 包含高操作惩罚、少量候选动作与轻量 rollout

## 3. Build

```bash
cd Game1/antgame_cpp_sdk
make
```

常见生成物：

- `build/libantgame_cpp_sdk.a`
- `build/sdk_example_ai`
- `build/sdk_smoke`
- `build/sdk_json_runner`
- `build/sdk_heavy_baseline_bench`

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
- `examples/sdk_heavy_baseline_bench.cpp`
  - 当前 baseline 搜索路径的调用耗时基准

## 6. 当前推荐用法

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

## 7. Scope Notes

这版 SDK 优先解决：

- C++ AI 不再手写协议
- 在线状态处理和费用/合法性检查统一
- 本地 rollout / 对拍可直接走原生裁判内核

高层策略库没有一并迁入；当前保留目标是正确、简洁、可高速模拟。

当前 baseline 的行为边界：

- 默认强烈偏向少操作，避免无收益的频繁建拆
- 战斗蚁近基地时优先空城与返还经济
- 安全窗口内先做 `Heavy`，再转 `Bewitch`
- 只在少量支撑位补 `Quick`
- 用持久化 `NativeSimulator` 做轻量 rollout，而不是每回合从公开状态裸重建
