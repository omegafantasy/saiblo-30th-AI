# Game1 当前工具链状态

## 1. 当前可用的链路

### 1.1 MHTML 与规则文档

当前已经可用：

- `docs/mhtml_parsed/antgame2_game48.md`
- `docs/mhtml_parsed/deepclue_game.md`
- `docs/game1_antgame2_code_truth_and_antwar_diff.md`
- `docs/game1_antwar_ai_migration_and_cpp_v1.md`

其中：

- `mhtml_parsed/*` 负责复刻页面内容。
- `game1_antgame2_code_truth_and_antwar_diff.md` 负责把规则页和代码真值拉开。

### 1.2 Game1 本地对局

当前已经实测跑通：

- 构建：`/www/Game1/antgame_ai_cpp/v1/Makefile`
- 打包：`/www/Game1/Ant-Game/AI/package_ai.sh cpp_v1`
- 对局：`/www/Game1/Ant-Game/tools/run_local_match.py --ai0 cpp_v1 --ai1 example|random`

也就是说，“新版目录结构 + C++ AI + Python 桥接 + Game1 游戏内核”这条链已经有效。

## 2. 当前仍然有效但需要重新接线的部分

### 2.1 Saiblo HTTP API 工具

`/www/saiblo_tools.py` 目前仍然是可复用的。

原因：

- 它主要处理 HTTP 层接口：
  - 列实体
  - 创建实体
  - 上传代码
  - 激活版本
  - 发起房间对局
  - 下载对局详情和回放
- 这些接口与本地目录结构关系不大。

因此对 Game1 来说，`saiblo_tools.py` 的主体不需要推倒重写。

真正需要改的是“传什么源文件上去”：

- 旧时代脚本默认围绕 `/www/ai_cpp/...`。
- 现在 Game1 正确源应当来自 `/www/Game1/antgame_ai_cpp/...`，并通过 `Game1/Ant-Game/AI/package_ai.sh` 产出上传包。

### 2.2 cron 任务

已确认：

- root `crontab` 已根据备份恢复。
- 全部自动化入口都加了全局暂停文件判断。
- 当前暂停文件：`/www/autolab/runtime/automation.paused`

因此现在的状态是：

- 任务定义已恢复；
- 但默认不会真的运行。

这符合“先恢复但保持暂停”的要求。

## 3. 当前明确失效 / 过时的部分

### 3.1 Autolab / Elo 主链路还没有适配 Game1

目前这些文件仍然明显指向旧根目录结构：

- `autolab/common.py`
  - 仍把 `ANT_GAME_DIR` 写成 `/www/Ant-Game`
- `autolab/registry.py`
  - 默认 champion 仍是 `/www/ai_cpp/v1/ai_v1`
- `autolab/registry.json`
  - 绝大多数版本仍指向旧 `/www/ai_cpp/v*/...`
- `ai_cpp_policy.py`
  - 仍默认读取 `/www/Ant-Game` 和 `/www/ai_cpp/v1/ai_v1`
- `eval_cpp_local.py`
  - 仍默认读取旧路径
- `autolab/README.md`
  - 示例命令仍围绕旧目录和旧版本体系

结论：

- 这些 Elo / 批评测工具当前不能视为“Game1 已适配完成”。
- 现在如果直接跑，会指向错误目录，或者引用已经删除的旧版本文件。

### 3.2 旧文档里的 Elo / 版本结论整体失效

`docs/` 下大量历史文档仍在讨论：

- `/www/ai_cpp/v*`
- 旧生产 Elo / 迭代 Elo
- 旧版 `cpp_v1_current` 及后续迭代

这些文档对“Game1 新规则”已经不再成立，只能保留作“旧方法学参考”，不能继续当作当前版本状态。

## 4. 对 Saiblo 与 Elo 的实际判断

### 4.1 Saiblo

- API 层脚本仍可复用。
- 上传/测试动作的本地源文件路径需要迁移到 `Game1`。
- 由于当前还没开始 Game1 的线上上传实测，本轮只能判定为“接口工具可用，Game1 适配未完成”。

### 4.2 Elo / 自动评测

- 生产 Elo、实验 Elo、版本注册表目前仍是旧工程状态。
- 它们的脚本入口虽然被恢复且暂停，但并没有完成 Game1 迁移。
- 所以本轮不能把当前 Elo 数据视为任何有意义的 Game1 强度指标。

## 5. Game1 真正要迁移的最小清单

后续如果要让 Elo / Saiblo / 本地批评测恢复可用，最小迁移项是：

1. `autolab/common.py`
   - 改成指向 `Game1/Ant-Game`。
2. `autolab/registry.py` 和 `autolab/registry.json`
   - 清空旧 `/www/ai_cpp/*` 版本，换成 `Game1/antgame_ai_cpp/*`。
3. `policy_adapters.py` / `eval_cpp_local.py` / `ai_cpp_policy.py`
   - 全部改成使用 Game1 的桥接与打包逻辑。
4. 基线对手列表
   - 旧 `random_safe` 已不适用；Game1 目前是 `random / example / greedy / mcts / cpp_v1`。
5. Saiblo 上传脚本
   - 把本地上传源从旧单文件 C++，改成 Game1 的打包产物。

## 6. 当前建议

在完成上述迁移前，当前应当只使用这条“可信链”：

- `Game1/antgame_ai_cpp/v1`
- `Game1/Ant-Game/AI/package_ai.sh cpp_v1`
- `Game1/Ant-Game/tools/run_local_match.py`

也就是说：

- 先用 Game1 内部 runner 验证策略与协议；
- 暂时不要相信旧 autolab / 旧 Elo / 旧 root 评测脚本；
- 等 Game1 目录和桥接稳定后，再迁移批评测和 Saiblo 自动化。
