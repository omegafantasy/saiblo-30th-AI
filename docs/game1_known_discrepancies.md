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

## 3. 已对齐的历史分叉

以下两项此前确实存在 Python / native 认识不一致，现在统一按 Python 语义处理：

- `Basic` 塔从新建开始射程就是 `1`
- `Lightning Storm` 对蚂蚁不是 `true damage`，会先消耗回避层

## 4. 当前使用建议

- 做机制判断时，优先信结构化常量、测试和实际执行路径
- 若要继续清理规则层冲突，先处理本页仍保留的 `ProducerMedic` 语义说明问题
- 在这些冲突未修复前，不要把单一文件当成完整真值
