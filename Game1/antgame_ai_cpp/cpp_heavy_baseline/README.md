# cpp_heavy_baseline

这是当前保留的 Game1 C++ baseline 入口。

## 1. 目标

- 基于 `Game1/antgame_cpp_sdk` 提供协议与公共状态
- 复用 `heavy_baseline.hpp` 中的轻量搜索决策逻辑
- 保持代码简单、可维护、可高速模拟

## 2. 文件

- `ai_cpp_heavy_baseline.cpp`
  - 比赛入口
  - 负责协议收发、持久化 `NativeSimulator` 与状态同步
- `Makefile`
  - 构建 `build/ai_cpp_heavy_baseline`

## 3. 构建

```bash
cd Game1/antgame_ai_cpp/cpp_heavy_baseline
make
```

## 4. 打包

```bash
cd Game1/antgame_ai_cpp
bash package_ai.sh cpp_heavy_baseline
```

## 5. 代码边界

- 这里放 AI 可执行入口
- 规则真值仍以 `../../Ant-Game/` 为准
- 外置 SDK 位于 `../../antgame_cpp_sdk/`
- 若 `Ant-Game` 更新，需要先同步确认 SDK 与 baseline 仍然匹配

## 6. 当前策略轮廓

- 对大多数动作施加显式高惩罚，默认优先 `hold`
- 战斗蚁近基地时偏向空城、拆塔返还
- 安全窗口内先做 `Heavy`，再尝试 `Bewitch`
- `Bewitch` 稳定后只补少量 `Quick`
- 搜索只覆盖少量建塔点、`UpgradeGeneratedAnt`、`Lightning Storm`
