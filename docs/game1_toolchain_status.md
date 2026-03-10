# Game1 当前工具链状态

## 1. 当前可信的本地链路

已经可视为可信的部分：

- 规则页解析：
  - `docs/mhtml_parsed/antgame2_game48.md`
  - `docs/game1_antgame2_code_truth_and_antwar_diff.md`
- 本地 AI：
  - `Game1/antgame_ai_cpp/v1/ai_v1.cpp`
  - `Game1/Ant-Game/AI/ai_cpp_v1.py`
- 本地单局对战：
  - `Game1/Ant-Game/tools/run_local_match.py`
- 本地批评测 / Elo：
  - `autolab/game1_match_runner.py`
  - `autolab/evaluator.py`
  - `autolab/registry.json`
- Saiblo HTTP 工具：
  - `saiblo_tools.py`

## 2. 这次已经完成的迁移

### 2.1 Autolab

已完成：

- `ANT_GAME_DIR` 迁到 `Game1/Ant-Game`
- 评测不再依赖旧 Python 逻辑 runner
- 改为真实打包 AI + `game/output/main` 对战
- replay 分析器改为 `Game1` 实际 JSON 数组格式
- 版本注册表清空旧 `/www/ai_cpp/v*` 残留

### 2.2 docs

已完成：

- 删除旧 round2 / old replay / old Saiblo 逐轮文档
- 删除 `Generals` 旧文档
- 重新抽出仍有价值的：
  - Codex 迭代约束
  - Saiblo API 工作流
  - Autolab / Elo 说明

### 2.3 任务恢复但暂停

已确认：

- cron 任务定义仍在备份基础上保留
- 自动化暂停文件仍生效：`/www/autolab/runtime/automation.paused`
- 也就是说“定义存在，但当前不会自动跑”

## 3. 当前 AI 状态

### 3.1 `cpp_v1_current`

结论：

- 这是当前最可信、可直接接入本地 Elo 的版本
- 本地已经验证至少能稳定跑通 `example/random` 级别对手
- 它保留了旧 `ANTWar-AI` 的核心高层思路：
  - 固定槽位
  - 攻守切换
  - 留钱防 EMP
  - 建塔/升级/基地升级的统一决策

### 3.2 `cpp_v2_antwar_structured`

结论：

- 已做了一版结构性增强实验
- 当前不进入主链，注册表中默认 `enabled=false`
- 原因：实验冒烟中已经出现对 `example` 的退化，说明还不能拿来当生产候选

## 4. Elo / Autolab 的当前判断

当前可以认为已经跑通的是：

- 版本注册
- 本地真实对局批评测
- 累计 Elo 计算
- replay 保存
- replay 解析
- Elo Web 读取 `latest.json`

仍需额外注意的是：

- `Game1` 对局天然是完整回合制，`max_rounds` 现在只是保留参数，不等于旧逻辑里那种硬截断控制
- `cpp_v1` 是桥接形态，因此“本地最强”不自动等价于“可直接 Saiblo 上传的纯 C++ 版本”

## 5. Saiblo 的当前判断

已确认仍然有效：

- 认证
- 实体查询
- 排行榜查询
- 房间开局
- 对局详情下载
- 回放下载
- 上传接口本身

当前尚未完全打通的关键点：

- 本地最强 `cpp_v1` 不是纯单文件 C++ 参赛入口
- 因此要真正把“当前最强本地 AI”上传到 Saiblo，还需要一版独立的线上 C++ 入口

## 6. 当前最小建议

如果现在继续做 Game1：

1. 本地强度判断只信 `autolab/runtime/latest.json`
2. 本地实验只信 `autolab/runtime/scopes/iter/latest.json`
3. 线上 Saiblo 先把 API 链路和回放下载链路当作已打通
4. 真正的 Saiblo 强 AI 上传，等独立纯 C++ 入口完成后再做
