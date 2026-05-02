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
- 当前快速模拟默认忽略每 10 回合周期随机移动机制
  - 这是策略搜索层的主动取舍
  - 做 native 对拍时应尽量选择不跨 10 回合窗口的 case

当前已确认案例：

- `seed_0024`, `player 0`, `round 199`
- 轻量搜索强推 `build 11:4:9`
- 但从同一 replay 状态出发，用原生 `NativeSimulator` 做 `5000` 次未来随机种子复算时，`build 11:4:9` 相对 `hold` 只剩极小优势，已接近平手
- 偏差主要来自当时的 `4` 回合轻量模拟窗口，对“可额外保住多少基地血”的严重高估

结果：

- 不要把 baseline 的动作分数当成规则正确性的证据
- 若遇到明显可疑的动作价值，应优先用 `sdk_lure_inspector` 看单回合候选与 trace
- 若怀疑轻量模拟本身，应优先用 `sdk_defense_parity` 做 native 多 rollout 对拍
- 在修正轻量模拟偏差前，不应优先把问题归因到 rollout 分配或 bandit 剪枝

### 2.4 当前 C++ baseline 的动作模型仍明显弱于官方操作模型

现状：

- 官方 engine 接受的是“同回合有序操作列表”
- 同回合合法链式操作是当前规则的一部分
- 手打 replay `Game1/good.json` 中，player 0 多次使用：
  - `拆塔 -> 建塔`
  - `拆塔 -> 闪电 -> 建塔`
  - `双拆塔 -> 双建塔`
- 当前 `lure_strategy.hpp` 已经支持部分同回合 op-list
  - `lure` 的 `sell + build`
  - 纯回收类 `base` 与 `lure` 的组合
  - 受限 base swap
  - 少量 `C1` followup
- 但它仍不是完整官方操作列表空间

结果：

- 当前 baseline 已能表达一部分“先卖诱饵再异地重建”
- 但仍不能表达 `sell -> lightning`、`sell -> lightning -> build` 与更复杂多塔多点联动
- rollout 中目前只保留“贴身自动回收”，不做完整主动计划生成

建议：

- 后续重构时，搜索单位应从单操作改为“同回合有序 op-list”
- 未来 rollout 中可以逐步恢复更强的自适应 op-list，但必须控制 STL/候选生成开销

### 2.5 官方 `game` 二进制当前不执行 `config.max_rounds`

现状：

- `Game1/antgame_ai_cpp/tools/eval_cpp_selfplay.py` 会把 `--max-rounds` 写进 init 包的 `config.max_rounds`
- 但当前 `Game1/Ant-Game/game/output/main` 并不会据此提前截断正式对局
- 已确认案例：
  - `Game1/antgame_ai_cpp/eval_lure_256_cap_2026_04_21`
  - 启动参数显式传了 `--max-rounds 256`
  - 实际 replay 仍分别跑到了 `396 / 381 / 403 / 450` 回合

结果：

- 看到 `summary.json` 里的 `max_rounds` 字段时，不要默认以为 replay 真被硬截到了该值
- 若需要“严格前 256 回合”的强度结论，应使用 `Game1/antgame_ai_cpp/tools/eval_cpp_partial_selfplay.py` 这种会在评测驱动层主动截断的 wrapper，或对 replay 和 decision log 做前 `256` 回合裁切后再统计
- 不要把 `eval_cpp_selfplay.py --max-rounds 256` 的完整 replay 结果当成严格 256 回合结果

## 3. 已对齐的历史分叉

以下几项此前确实存在认识不一致或 SDK 镜像偏差，现在已经对齐：

- `Basic` 塔从新建开始射程就是 `1`
- `Lightning Storm` 对蚂蚁不是 `true damage`，会先消耗回避层
- `PublicState::apply_operation_list()` 现在按官方有序操作列表语义顺序应用，覆盖“先降/卖塔筹钱，再建塔，再 EMP”的 salvage-funded EMP；p0 accepted 操作会在 p1 读取前进入公开状态

## 4. 当前使用建议

- 做机制判断时，优先信结构化常量、测试和实际执行路径
- 外置 `antgame_cpp_sdk` 现已补齐 `Ant-Game` 头文件依赖追踪；上游更新后应重新 `make`，不要复用旧 `build/` 产物
- 动作估值审计时，优先用 `Game1/antgame_cpp_sdk/examples/sdk_lure_inspector.cpp`
- 轻量模拟与 native 对拍时，优先用 `Game1/antgame_cpp_sdk/examples/sdk_defense_parity.cpp`
- 若要继续清理规则层冲突，先处理本页仍保留的 `ProducerMedic` 语义说明问题
- 在这些冲突未修复前，不要把单一文件当成完整真值
