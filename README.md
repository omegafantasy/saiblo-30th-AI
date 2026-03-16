# AI Workspace

本仓库现在同时服务两个游戏：

- `Game1/`
  - 当前重点：`蚁洋陷役2`
  - 游戏代码：`Game1/Ant-Game/`
  - C++ AI：`Game1/antgame_ai_cpp/`
- `Game2/`
  - 当前仅完成规则页归档；本轮不做 AI 开发。

## 当前阶段结论

Game1 已经完成第一轮重新梳理：

1. 新规则页已重新解析到 markdown。
2. `Game1/Ant-Game` 与旧 `ANTWar-Logic` 的主要差异已按代码真值重新整理。
3. 旧 `ANTWar-AI` 的可迁移思路已重新分析。
4. 已落地一个新的 `Game1` C++ 基线 `cpp_v1`，并在本地逻辑中跑通。
5. 旧 root 级 Elo / autolab / 本地评测脚本已确认大多仍指向旧目录，当前只能视为“方法学资产”，不能直接用于 Game1。

## 目录结构

- `Game1/Ant-Game/`
  - Game1 官方/上游游戏仓库。
  - 当前代码真值来源。
- `Game1/antgame_ai_cpp/`
  - Game1 的 C++ AI 目录。
  - 当前已有：`v1/`
- `Game2/`
  - 第二个游戏的工作目录。
- `past_AIs/`
  - 历史强 AI 与旧逻辑：
    - `ANTWar-AI/`
    - `ANTWar-Logic/`
    - 其他历史脚本与 bearer 来源
- `docs/`
  - 当前有效文档以 Game1 重构结果为主。
- `autolab/`, `autolab_eval.py`, `ai_cpp_policy.py`, `eval_cpp_local.py`
  - 旧自动评测/版本管理链路。
  - 当前仍保留，但尚未迁移到 `Game1` 新目录。
- `saiblo_tools.py`
  - Saiblo HTTP API 工具，主体仍可复用。

## 当前有效文档

- `docs/mhtml_parsed/antgame2_game48.md`
- `docs/mhtml_parsed/deepclue_game.md`
- `docs/game1_antgame2_code_truth_and_antwar_diff.md`
- `docs/game1_antwar_ai_migration_and_cpp_v1.md`
- `docs/game1_toolchain_status.md`

## Game1 当前可用链路

构建 C++ AI：

```bash
cd /www/Game1/antgame_ai_cpp/v1
make
```

打包为 `Ant-Game` 可运行 AI：

```bash
cd /www/Game1/Ant-Game
bash AI/package_ai.sh cpp_v1 /tmp/game1_cpp_v1_pkg
```

本地跑一局：

```bash
cd /www/Game1/Ant-Game
python3 tools/run_local_match.py --ai0 cpp_v1 --ai1 example --seed 7 --keep-dir /tmp/game1_cpp_v1_smoke
```

当前已完成的实测：

- `cpp_v1` vs `example`：完整跑完并获胜。
- `cpp_v1` vs `random`：本地跑通并获胜。

## 自动化状态

- root `crontab` 已根据备份恢复。
- 但全局暂停文件 `autolab/runtime/automation.paused` 仍在，因此自动化不会实际启动。
- CPU 上限相关脚本已调整为 8 核上限。

## 需要特别注意的事

- `Game1/Ant-Game` 是当前规则和实现的唯一真值；规则页与旧文档只作参考。
- 旧 `ai_cpp/`、旧 Elo、旧版本迭代文档大多不再代表当前 Game1 状态。
- 目前不要直接使用旧 `autolab` / `eval_cpp_local.py` / `ai_cpp_policy.py` 来评测 Game1，除非先完成路径迁移。
