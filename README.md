# AI Workspace

本仓库同时包含两个游戏工作目录：

- `Game1/`
- `Game2/`

当前 `Game1` 只以现有代码实现为基线。

## 1. Game1 入口

- 规则与运行时：`Game1/Ant-Game/`
- C++ AI：`Game1/antgame_ai_cpp/`

## 2. 文档入口

`Game1` 当前只建议看这些文档：

- `docs/game1_code_truth.md`
- `docs/game1_known_discrepancies.md`

`docs/` 中的历史自动化结果、旧版本结论、细节策略和 Game1 旧规则快照已经清空。

## 3. 目录说明

- `Game1/Ant-Game/`
  当前规则实现与测试基线
- `Game1/antgame_ai_cpp/`
  Game1 AI 代码
- `Game2/`
  第二个游戏目录
- `docs/`
  当前保留的最小文档集
- `autolab/`
  评测与自动化脚本
- `saiblo_tools.py`
  Saiblo API 工具

## 4. 读取原则

- 先信当前代码，再信文档
- 若代码内部互相冲突，先记录冲突，再决定修改路径
