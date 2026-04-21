# Game1 Known Discrepancies

这份文档只记录当前仓库里已经确认存在的高影响冲突。

## 1. 文档层说明

- `Game1/Ant-Game/README.md` 现在只作为入口说明，不再承载完整规则表
- Game1 规则判断应优先基于结构化常量、engine、tests、native 实现与 `cpp_sdk`

## 2. 当前仍需注意的点

### 2.1 `ProducerMedic` 的“范围”定义不统一

现状：

- 规则文字容易让人理解成存在明确支援范围字段
- SDK 常量里 `support_interval = 4`，但 `support_range = 0`
- native `get_support_range()` 也返回 `0`
- 实际治疗逻辑并不是按塔自身范围，而是按“当前最前线距离 + 1”筛目标

结果：

- `Medic` 的行为应以实际代码逻辑理解，而不是以表格里的“范围”字面理解

### 2.2 `Ant-Game/README.md` 仍不是完整结算真值

现状：

- 最新超武“部署当回合立即生效”
- 同回合后手会直接吃到前手 `EMP`
- 这些关键信息应以 engine / native / tests 为准

结果：

- 规则追溯时不要把入口 README 当作完整结算文档

### 2.3 当前随机搜索防守模拟与 native rollout 不等价

现状：

- `random_search_baseline.hpp` 的主防守搜索为了速度，使用外置轻量 `DefenseSimulator`
- 它不是 `Ant-Game` 原生增强移动与原生塔选目标的逐行复写
- 因而搜索分数只代表“当前近似模型的判断”，不代表 native 真值

当前已确认案例：

- `seed_0024`, `player 0`, `round 199`
- 轻量搜索强推 `build 11:4:9`
- 但从同一 replay 状态出发，用原生 `NativeSimulator` 做 `5000` 次未来随机种子复算时，`build 11:4:9` 相对 `hold` 只剩极小优势，已接近平手
- 偏差主要来自当时的 `4` 回合轻量模拟窗口，对“可额外保住多少基地血”的严重高估

结果：

- 不要把 baseline 的动作分数当成规则正确性的证据
- 若遇到明显可疑的动作价值，应优先用 `sdk_rollout_probe` 做原生 replay 复算
- 在修正轻量模拟偏差前，不应优先把问题归因到 rollout 分配或 bandit 剪枝

### 2.4 当前 C++ baseline 的动作模型仍明显弱于官方操作模型

现状：

- 官方 engine 接受的是“同回合有序操作列表”
- 同回合合法链式操作是当前规则的一部分
- 手打 replay `Game1/good.json` 中，player 0 多次使用：
  - `拆塔 -> 建塔`
  - `拆塔 -> 闪电 -> 建塔`
  - `双拆塔 -> 双建塔`
- 但当前 `random_search_baseline.hpp` 仍主要按“单动作 / 固定两回合 followup”建模

结果：

- 当前 baseline 很难表达“先卖诱饵再异地重建”的核心玩法
- 也很难在 rollout 中自适应执行“近身自动拆塔”
- 这不是调参数能补齐的小问题，而是动作表示本身过弱

建议：

- 后续重构时，搜索单位应从单操作改为“同回合有序 op-list”
- 未来 rollout 中应支持按模拟态自适应地产生下一回合 op-list，而不是只承诺固定 second op

## 3. 已对齐的历史分叉

以下两项此前确实存在 Python / native 认识不一致，现在统一按 Python 语义处理：

- `Basic` 塔从新建开始射程就是 `1`
- `Lightning Storm` 对蚂蚁不是 `true damage`，会先消耗回避层

## 4. 当前使用建议

- 做机制判断时，优先信结构化常量、测试和实际执行路径
- 外置 `antgame_cpp_sdk` 现已补齐 `Ant-Game` 头文件依赖追踪；上游更新后应重新 `make`，不要复用旧 `build/` 产物
- 动作估值审计时，优先用 `Game1/antgame_cpp_sdk/examples/sdk_rollout_probe.cpp` 从 replay 精确复算
- 若要继续清理规则层冲突，先处理本页仍保留的 `ProducerMedic` 语义说明问题
- 在这些冲突未修复前，不要把单一文件当成完整真值
