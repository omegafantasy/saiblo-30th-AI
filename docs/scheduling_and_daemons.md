# 定时任务与常驻进程（已落地）

更新时间：2026-03-05（UTC）

## 1) 评测常驻：空闲即跑（最多 14 CPU）

- systemd 服务：`autolab-idle-eval.service`
- 启动脚本：`/www/scripts/autolab_idle_eval_loop.sh`
- 仓库内 unit 模板：`/www/scripts/systemd/autolab-idle-eval.service`
- 当前策略：
  - `--mode adaptive`
  - `--cpu-policy idle_only`
  - `--jobs 14`（上限）
  - `--pin-cpu`（worker 绑定核，子进程继承亲和性）
  - 自适应匹配：均匀随机为底，前排版本与低样本版本提高抽样权重
  - 空闲检测失败时 20 秒后重试
  - 若检测到 `codex-iterate` 正在运行（锁占用），则暂停生产评测，30 秒后重试
- 数据写入：
  - 生产最新结果：`/www/autolab/runtime/latest.json`
  - 生产报告：`/www/docs/idle_eval_latest.md`
  - Elo 口径：生产 `latest.json` 是唯一权威排名来源

关键命令：

```bash
systemctl status autolab-idle-eval.service --no-pager -l
tail -n 120 /www/autolab/runtime/idle_eval_loop.log
```

## 2) Codex 定时迭代：每 15 分钟（会话续跑）

- 任务入口：`/www/scripts/codex_iterate_once.sh`
- crontab：

```bash
*/15 * * * * /usr/bin/flock -n /tmp/codex-iterate.lock /www/scripts/codex_iterate_once.sh >/dev/null 2>&1
```

- 防重入：`flock`
- 会话机制：
  - 首次运行自动创建 session
  - 后续运行自动 `codex exec resume <session_id>`（若上次已停则继续）
  - session id 文件：`/www/autolab/runtime/codex_session_id.txt`
- 运行时长控制：默认不设超时（同一 session 持续执行）；若需临时调试可设置 `CODEX_ITER_TIMEOUT_SEC>0`
- 全局互斥锁：`/tmp/codex-automation-global.lock`（用于与其他 codex 定时会话互斥）
- 日志：`/www/autolab/runtime/codex_iterate.log`
- 事件流：`/www/autolab/runtime/codex_events.jsonl`
- 迭代评测隔离目录：`/www/autolab/runtime/scopes/iter/`
- 迭代评测脚本：`/www/scripts/autolab_eval_experiment_once.sh`
- 迭代评测默认并发：`jobs=14`、`cpu-policy=all`（迭代优先）
- 迭代 replay 默认保留：`/www/autolab/runtime/scopes/iter/replays/<eval_tag>/`
- 迭代 replay 分析自动产物：
  - `/www/autolab/runtime/scopes/iter/replay_analysis/latest.json`
  - `/www/docs/replay_analysis/iter_latest.md`
- Elo 口径：iter `latest.json` 仅用于候选筛选，不能直接与生产 Elo 横向比绝对值

关键命令：

```bash
crontab -l
rg -n "START codex iteration|END codex iteration" /www/autolab/runtime/codex_iterate.log
```

## 3) Codex Saiblo 定时迭代：每 15 分钟（独立会话）

- 任务入口：`/www/scripts/codex_saiblo_iterate_once.sh`
- 任务目标文档：
  - `/www/docs/codex_saiblo_iteration_prompt.md`
  - `/www/docs/codex_saiblo_objective_fixed.md`
- crontab（15 分钟，错峰）：

```bash
7,22,37,52 * * * * /usr/bin/flock -n /tmp/codex-saiblo-iterate.lock /www/scripts/codex_saiblo_iterate_once.sh >/dev/null 2>&1
```

- 防重入：`/tmp/codex-saiblo-iterate.lock`
- 与主 codex 迭代互斥：共享全局锁 `/tmp/codex-automation-global.lock`
- 会话机制：
  - 首次运行自动创建 session
  - 后续运行自动 `codex exec resume <session_id>`
  - session id 文件：`/www/autolab/runtime/codex_saiblo_session_id.txt`
- 默认等待全局锁：`CODEX_GLOBAL_LOCK_WAIT_SEC=120`
- 运行时长控制：默认不设超时；若需临时调试可设置 `CODEX_SAIBLO_ITER_TIMEOUT_SEC>0`
- 日志：`/www/autolab/runtime/codex_saiblo_iterate.log`
- 事件流：`/www/autolab/runtime/codex_saiblo_events.jsonl`

关键命令：

```bash
rg -n "START codex saiblo|END codex saiblo|SKIP global-lock" /www/autolab/runtime/codex_saiblo_iterate.log
```

## 4) CPU 限制有效性验证结论

已做实测：在 `--pin-cpu` 下，`autolab` worker 与 `ai_v*` 子进程亲和性一致，并落在 `selected_cores` 内。

示例（节选）：

- worker affinity：`0,1,4,5,...,15`
- AI 进程 affinity：与其父 worker 对齐（如 `ai_v2 -> core 0`, `ai_v1 -> core 4`）

结论：评测负载可被限制在“本轮选中核心”集合内；当设置 `jobs=14` 时，最多使用 14 个核心。

## 5) Elo 网站常驻（8000，对公网）

- 服务脚本：`/www/elo_web/server.py`
- 启停脚本：
  - `/www/scripts/elo_web_start.sh`
  - `/www/scripts/elo_web_stop.sh`
  - `/www/scripts/elo_web_ensure.sh`
- 监听地址：`0.0.0.0:8000`
- 定时守护：
  - `@reboot /usr/bin/flock -n /tmp/elo-web-start.lock /www/scripts/elo_web_start.sh >/dev/null 2>&1`
  - `* * * * * /usr/bin/flock -n /tmp/elo-web-ensure.lock /www/scripts/elo_web_ensure.sh >/dev/null 2>&1`
- 数据同步机制：
  - 前端每 15 秒请求 `/api/elo`
  - 后端按请求实时读取 `autolab/runtime/latest.json` 与 `autolab/runtime/scopes/iter/latest.json`
  - 不需要额外手工同步步骤

关键命令：

```bash
ss -ltnp | rg ':8000'
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8000/api/elo | head
```

## 6) 去重说明（quota-guard）

- `quota-guard` 仅保留 cron 一处触发（每 10 分钟）。
- `codex-supervisor.sh` 已移除对 `quota-guard` 的二次调用，避免重复扫描/重复 rotation。
