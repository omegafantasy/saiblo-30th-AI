# cpp_heavy_baseline

这是当前保留的 Game1 C++ AI 入口。

目录名仍然沿用历史命名，但内部决策逻辑已经不是旧版 `heavy` 脚本基线，而是新的随机搜索基线。

## 1. 目标

- 基于 `Game1/antgame_cpp_sdk` 提供协议与公共状态
- 复用 `random_search_baseline.hpp` 中的轻量随机搜索逻辑
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
- 当前已按最新规则同步：超武部署当回合立即生效，后手同回合会受前手 `EMP` 影响

## 6. 当前策略轮廓

- 使用简化终点评估与 `hold` 偏置，默认倾向少操作
- 主搜索只考虑我方塔/敌方蚂蚁/我方闪电/敌方已激活超武
- 仅搜索 `Build/Upgrade/Downgrade/Lightning/Hold`
- 当前不考虑任何基地升级
- `Upgrade` 当前只作为单回合动作搜索
- 双回合只保留：
  - 核心九格 `C1/C2/C3/L1/L2/L3/R1/R2/R3` 上的 `Build -> Upgrade`
  - `Downgrade -> Followup`，且若第二步是建塔，也只允许核心九格
- 用共享进攻 EV 与终点估值驱动动作选择
