# Game1 旧 ANTWar AI 迁移与 cpp_v1 说明

## 1. 旧强 AI 里真正值得保留的东西

`past_AIs/ANTWar-AI/main.cpp` 的强点不在“某几个具体数值”，而在以下结构：

- 固定战略槽位 `positions[2][35][2]`。
- 明确的塔位分组和分支升级逻辑。
- `safe_coin()` 这类“为对手 EMP 预留反制资金”的经济观念。
- `global_state` / `attack_flag` 这样的攻守模式切换。
- 把“建塔 / 升级 / 基地升级 / 超级武器”当成统一决策问题来处理，而不是分散写死。

这些思想在 Game1 仍然成立。

## 2. 不能照搬的旧实现

下面这些在新规则下已经不可信：

- 旧 `Simulator` 与 `fast_next_round()`。
- 旧塔数值假设，尤其是 13 号塔和 32 号塔。
- 旧超级武器语义。
- 旧版对蚂蚁移动的确定性假设。
- 旧版协议和局面字段。

最关键的一点是：旧 AI 的很多效果评估依赖“前线可预测、控制语义稳定、无传送、无漂移”。Game1 四个条件都不再满足。

## 3. 这次 v1 采用的迁移路线

`Game1/antgame_ai_cpp/v1/ai_v1.cpp` 没有硬复刻旧模拟器，而是保留旧 AI 的高层骨架：

- 用旧 AI 的槽位顺序作为主要建塔顺序。
- 把槽位分成 `heavy / quick / mortar` 三类分支。
- 继续使用“攻守模式”来影响 EMP、升级分支和基地升级。
- 继续使用 `safe_coin_threshold` 控制花钱上限。
- 用轻量候选搜索替代旧的深模拟搜索：
  - 空操作
  - 单建塔
  - 单升级
  - 建塔 + 升级
  - 紧急闪电风暴
  - 进攻 EMP
  - 基地升级

## 4. 为什么改成 Python SDK 快照 + C++ 决策

本轮最重要的架构变更是：

- `Game1/Ant-Game/AI/ai_cpp_v1.py` 使用当前 `SDK.backend` 的精确状态。
- 每回合把精确状态快照发给 C++ 二进制。
- C++ 只负责策略，不再自己维护协议、冷却、漂移和隐藏状态。
- Python 桥接层负责最终合法性过滤和发包。

这样做有三个现实好处：

1. 直接复用当前代码真值，不再受旧协议拖累。
2. C++ 仍然是决策核心，满足“AI 必须是 C++”。
3. 后续如果要继续增强搜索或评估，不需要先重写完整 Judger/模拟器。

## 5. cpp_v1 当前策略概述

当前版本的决策核心：

- 攻守模式：
  - 自己基地血量落后时更偏进攻。
  - 自己血量领先时更偏防守和稳态升级。
  - 平血时根据前线压力和回合数做轻量切换。
- 经济：
  - 使用 SDK 的 `safe_coin_threshold(player)`，尽量避免把钱花到无法应对对手 EMP 的程度。
- 建塔：
  - 优先使用旧 AI 的关键槽位顺序。
  - 中心/近基地槽位优先走 `heavy` 分支。
  - 中层与侧翼更多走 `quick` 分支。
  - 中远端槽位更多走 `mortar` 分支。
- 升级：
  - `heavy` 分支在高压时优先 `Ice`，其余情况偏 `Heavy+`，进攻时也会考虑 `Bewitch/Cannon(13)`。
  - `quick` 分支在进攻态更倾向 `Sniper`，否则 `Double` / `Quick+`。
  - `mortar` 分支在守压时偏 `Pulse`，进攻态偏 `Missile`。
- 超级武器：
  - `LightningStorm` 仅作紧急防守。
  - `EMPBlaster` 仅在进攻态且敌塔密集时主动使用。
- 基地升级：
  - 优先升级蚂蚁生命等级，再考虑出兵速度。

## 6. 已完成的本地验证

已跑通的新链路：

- 构建：`make -C /www/Game1/antgame_ai_cpp/v1`
- 打包：`bash /www/Game1/Ant-Game/AI/package_ai.sh cpp_v1 <dir>`
- 本地对局：`python3 /www/Game1/Ant-Game/tools/run_local_match.py ...`

本轮实际冒烟结果：

- `cpp_v1` vs `example`：完整跑满 512 回合，`cpp_v1` 获胜。
- `cpp_v1` vs `random`：在 456/487 回合左右结束，`cpp_v1` 获胜。
- 经过经济合法性修正后，最近一轮 `cpp_v1` vs `random` 已无桥接层过滤非法操作的日志。

## 7. 当前版本的已知不足

`cpp_v1` 现在只是“迁移基线”，还不是强版复刻：

- 没有复刻旧版深层节点搜索。
- 没有做对手行为建模。
- 超级武器只实现了最关键的两类使用场景。
- 对 `BEWITCHED` / `CONTROL_FREE` / 漂移区域的价值评估仍然比较粗。
- 还没有接入新的 Game1 Elo/批量评测体系。

## 8. 下一步该怎么迭代

后续如果继续提升，优先顺序应当是：

1. 在当前快照桥接架构上补一个轻量 lookahead，而不是回头复刻旧模拟器。
2. 单独分析 13 号塔、Pulse、Deflector/Evasion 的真实收益。
3. 把 replay 分析改造成面向 `Game1` 的格式，再做批量定位。
4. 最后才是迁移 autolab / Elo / Saiblo 上传流水线。

补充：

- 关于“当前到底复刻了旧 ANTWar-AI 哪些部分、还缺哪些”，见 `docs/game1_antwar_ai_coverage_check.md`。
