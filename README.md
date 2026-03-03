# 蚁洋陷役2 AI 项目工作区说明（阶段一）

本目录用于完成 Saiblo `game/48`（蚁洋陷役2）的 AI 开发与自动迭代。

## 目录结构

- `Ant-Game/`
  - 当前目标游戏仓库，包含游戏逻辑、AI 接口、SDK、评测脚本与测试。
- `past_AIs/`
  - 历史项目代码：
    - `ANTWar-AI/`：塔防 AntWar 的 C++ AI。
    - `Generals-AI/`：策略地图 Generals 的 C++ AI。
  - `zdata.py` / `zlocal.py` 等脚本：历史线上数据与本地评测脚本（目前与新游戏不直接兼容）。
- `docs/ANTWar - Saiblo.mhtml`
  - 历史 ANTWar 规则页。
- `docs/Generals - Saiblo.mhtml`
  - 历史 Generals 规则页。
- `docs/蚁洋陷役2 - Saiblo.mhtml`
  - 当前目标游戏规则页（页面中包含规则说明与 SDK 对接说明）。
- `docs/`
  - 阶段一分析与准备文档：
    - `antwar2_rules_and_code_analysis.md`
    - `legacy_overlap_analysis.md`
    - `mhtml_three_games_parsed.md`
    - `agent_a_docs_accuracy_audit.md`
    - `agent_b_saiblo_status_audit.md`
    - `agent_c_ai_migration_report.md`
  - 自动解析产物：
    - `mhtml_parsed/`（3 个 mhtml 的正文 markdown）
    - `mhtml_assets/`（mhtml 中提取出的图片资源）
- `ai_cpp_v1/`
  - 根目录独立的 C++ AI 源码与构建目录。
- `ai_cpp_policy.py`
  - 根目录独立的 C++ AI Python 桥接（默认调用 `ai_cpp_v1/ai_v1`）。
- `eval_cpp_local.py`
  - 根目录独立的本地自动评测脚本。
- `saiblo_tools.py`
  - 根目录独立的 Saiblo 接口脚本（可从 `past_AIs/zdata.py` 自动读取 bearer）。

## 阶段一目标与交付

1. README 与项目地图（本文件）。
2. 新游戏规则与代码实现的逐项对照分析。
3. 历史 AI 与新游戏的重合度分析。
4. 一版可运行的 C++ 初版 AI（适配当前协议）。
5. Saiblo 信息拉取与测试流程脚本迁移。
6. 本地自动评测跑通。

## 仓库管理约定（阶段一）

- 本目录初始化为“阶段一总控仓库”，用于管理根目录下的 AI、脚本与文档。
- `Ant-Game/` 为上游独立仓库，继续由其自身 `.git` 管理，不纳入本仓库版本历史。
- `past_AIs/zdata.py` 含 bearer，默认不纳入版本控制；线上凭据建议优先使用环境变量 `SAIBLO_BEARER`。

## 关键新增文件（阶段一）

- `ai_cpp_v1/ai_v1.cpp`：初版 C++ AI（stdin 行输入 + 4 字节长度前缀输出）。
- `ai_cpp_v1/Makefile`：C++ AI 编译。
- `ai_cpp_policy.py`：根目录 C++ AI 桥接策略。
- `eval_cpp_local.py`：根目录本地自动评测入口（支持并行、多局、换先）。
- `saiblo_tools.py`：根目录 Saiblo 接口脚本（拉取对局、创建房间并发起对局、拉取对局详情）。

## 快速开始

```bash
cd /www/ai_cpp_v1
make
cd /www
python eval_cpp_local.py --games 10 --rounds 120 --opponent greedy --swap-seats
```

## 备注

- 当前页面规则文案存在“塔防 AntWar 叙事”与“Generals 风格代码实现”并存的情况，详见：
  - `docs/antwar2_rules_and_code_analysis.md`
  - `docs/mhtml_three_games_parsed.md`
- `saiblo_tools.py` 默认按以下优先级读取 token：
  - `--token` 参数
  - `SAIBLO_BEARER` 环境变量
  - `past_AIs/zdata.py` 中的 `bearer`
