# Game1 Known Discrepancies

这份文档只记录当前仓库里已经确认存在的高影响冲突。

## 1. 文档层说明

- `Game1/Ant-Game/README.md` 现在只作为入口说明，不再承载完整规则表
- Game1 规则判断应优先基于结构化常量、engine、tests、native 实现与 `cpp_sdk`

## 2. 代码内部的冲突

### 2.1 native 新建 `Basic` 塔射程疑似为 `2`

现状：

- structured constants 和测试都认为 `Basic` 射程应为 `1`
- native `DefenseTower` 构造函数没有调用 `set_stats_for_type(Basic)`
- `DefenseTower` 成员默认 `range = 2`

结果：

- 新建 `Basic` 塔在 native 运行时很可能以默认值 `range = 2` 开局
- 升级或降级后才会重新走 `set_stats_for_type`

涉及位置：

- `Game1/Ant-Game/SDK/utils/constants.py`
- `Game1/Ant-Game/tests/test_engine.py`
- `Game1/Ant-Game/game/include/building.h`
- `Game1/Ant-Game/game/src/building.cpp`

这是当前最需要优先解决的规则层冲突。

### 2.2 `ProducerMedic` 的“范围”定义不统一

现状：

- 规则文字容易让人理解成存在明确支援范围字段
- SDK 常量里 `support_interval = 4`，但 `support_range = 0`
- native `get_support_range()` 也返回 `0`
- 实际治疗逻辑并不是按塔自身范围，而是按“当前最前线距离 + 1”筛目标

结果：

- `Medic` 的行为应以实际代码逻辑理解，而不是以表格里的“范围”字面理解

## 3. 当前使用建议

- 做机制判断时，优先信结构化常量、测试和实际执行路径
- 若要继续清理规则层冲突，先处理本页列出的两项
- 在这些冲突未修复前，不要把单一文件当成完整真值
