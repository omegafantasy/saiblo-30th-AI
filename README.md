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
    - `saiblo_api_mapping_and_match_smoke.md`
    - `agent_a_docs_accuracy_audit.md`
    - `agent_b_saiblo_status_audit.md`
    - `agent_c_ai_migration_report.md`
    - `round2_autolab_and_iterations.md`
    - `version_strategy_deep_dive_v1_v53.md`
  - 自动解析产物：
    - `mhtml_parsed/`（3 个 mhtml 的正文 markdown）
    - `mhtml_assets/`（mhtml 中提取出的图片资源）
- `ai_cpp/`
  - C++ AI 版本目录：
    - `v1/`：当前稳定基线。
    - `v2/`：beam 序列规划实验版。
    - `v3/`：hybrid（beam+greedy）实验版。
- `ai_cpp_policy.py`
  - 根目录独立的 C++ AI Python 桥接（默认调用 `ai_cpp/v1/ai_v1`）。
- `eval_cpp_local.py`
  - 根目录独立的本地自动评测脚本。
- `saiblo_tools.py`
  - 根目录独立的 Saiblo 接口脚本（可从 `past_AIs/zdata.py` 自动读取 bearer）。
  - 已支持上传、榜单查询、房间对局、回放下载、批量实测链路。

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

## 本地配置（建议）

- 复制 `config.example.json` 为 `config.local.json` 并填写你本机配置。
- `config.local.json` 已被 `.gitignore` 忽略，可安全保存本地 token/路径。
- 目前已接入配置读取的脚本：
  - `saiblo_tools.py`（`saiblo.api_base`、`saiblo.bearer`）
  - `ai_cpp_policy.py`（`cpp_ai.exe`、`cpp_ai.seed`、`paths.ant_game_dir`）
  - `eval_cpp_local.py`（`cpp_ai.exe`）
- 配置优先级：
  - 命令行参数 > 环境变量 > `config.local.json` > 代码默认值（`saiblo_tools` 还会继续回退 `past_AIs/zdata.py`）

## 第二轮自动迭代（Autolab）

- 版本管理：`python /www/autolab_manage.py list`
- 批量评测 + Elo：`python /www/autolab_eval.py --mode gauntlet --games-per-pair 20 --jobs 14`
- 空闲核评测（含亲和性绑定）：`python /www/autolab_eval.py --mode gauntlet --games-per-pair 20 --jobs 14 --cpu-policy idle_only --idle-threshold 0.02 --pin-cpu`
- 定时调度：`python /www/autolab_schedule.py --interval-min 30 --cycles 8 --eval-args "--mode gauntlet --games-per-pair 20 --jobs 14"`
- 回放分析（最新轮次）：`python /www/autolab_replay_analyze.py --scope iter --latest`
- 已落地常驻/定时：
  - `autolab-idle-eval.service` 常驻空闲核评测（默认最多 14 CPU）
  - cron 每 15 分钟触发 `scripts/codex_iterate_once.sh`（含防重入锁 + session 续跑，默认不设超时）
  - cron 每 15 分钟触发 `scripts/codex_saiblo_iterate_once.sh`（Saiblo 专用 session，错峰触发，最多 10 局/轮）
  - 两个 codex 会话共享全局互斥锁：`/tmp/codex-automation-global.lock`
  - 迭代实验评测与生产评测已隔离：实验产物写入 `autolab/runtime/scopes/iter/`
  - 评测默认保存所有对局 replay：`autolab/runtime[/scopes/<scope>]/replays/<eval_tag>/`
  - 迭代评测后自动产出 replay 分析：
    - `autolab/runtime/scopes/iter/replay_analysis/latest.json`
    - `docs/replay_analysis/iter_latest.md`
  - Elo 治理：`autolab/runtime/latest.json`（生产）是唯一权威；`scopes/iter/latest.json`（实验）仅用于筛选
- 详细说明：`/www/autolab/README.md`
- 运维检查清单：`/www/docs/scheduling_and_daemons.md`

## Elo 展示网站（8000 端口）

- 代码目录：`/www/elo_web/`
- 后端服务：`/www/elo_web/server.py`（零依赖，实时读取本地 Elo 文件）
- 数据来源：
  - 生产：`/www/autolab/runtime/latest.json`（累计 Elo/累计总局数）
  - 迭代：`/www/autolab/runtime/scopes/iter/latest.json`
- 展示内容：
  - Elo 排名
  - 版本号（version id）
  - 每版本局数（games）
  - 胜率 / score 比例

启动与运维：

```bash
/www/scripts/elo_web_start.sh
/www/scripts/elo_web_stop.sh
/www/scripts/elo_web_ensure.sh
```

- 监听地址：`0.0.0.0:8000`
- 定时守护：
  - `@reboot` 自动启动
  - 每分钟 `elo_web_ensure.sh` 自检拉起
- 本机访问：`http://127.0.0.1:8000`
- 公网访问（示例）：`http://154.40.43.84:8000`

## 关键新增文件（阶段一）

- `ai_cpp/v1/ai_v1.cpp`：当前基线 C++ AI（stdin 行输入 + 4 字节长度前缀输出）。
- `ai_cpp/v1/Makefile`：`v1` 编译入口。
- `ai_cpp/v2/ai_v2.cpp`：第二轮算法迭代（beam 序列规划）。
- `ai_cpp/v3/ai_v3.cpp`：第二轮算法迭代（hybrid 规划）。
- `ai_cpp_policy.py`：根目录 C++ AI 桥接策略。
- `eval_cpp_local.py`：根目录本地自动评测入口（支持并行、多局、换先）。
- `saiblo_tools.py`：根目录 Saiblo 接口脚本（拉取对局、创建房间并发起对局、拉取对局详情）。
  - 新增命令：
    - `entities`：列出账号在某 game 下的实体与当前激活版本
    - `upload-ai`：自动上传源码到实体，支持 `--wait-compile --activate`
    - `ladders`：查询 game 的全局榜单与 code token
    - `run-matches`：批量发起对局并等待完成，支持自动下载回放与详情
    - `download-replay`：下载指定对局回放并保存详情 JSON
- `ai_cpp/saiblo_baseline/ai_baseline_v1.cpp`：纯标准库基础 C++ AI（协议链路验证版）。

## 快速开始

```bash
cd /www/ai_cpp/v1
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
  - `config.local.json` 的 `saiblo.bearer`
  - `past_AIs/zdata.py` 中的 `bearer`
