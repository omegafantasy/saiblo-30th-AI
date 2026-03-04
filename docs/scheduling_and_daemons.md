# 定时任务与常驻进程（已落地）

更新时间：2026-03-03（UTC）

## 1) 评测常驻：空闲即跑（最多 14 CPU）

- systemd 服务：`autolab-idle-eval.service`
- 启动脚本：`/www/scripts/autolab_idle_eval_loop.sh`
- 仓库内 unit 模板：`/www/scripts/systemd/autolab-idle-eval.service`
- 当前策略：
  - `--cpu-policy idle_only`
  - `--jobs 14`（上限）
  - `--pin-cpu`（worker 绑定核，子进程继承亲和性）
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

## 2) Codex 定时迭代：每 10 分钟（会话续跑）

- 任务入口：`/www/scripts/codex_iterate_once.sh`
- crontab：

```bash
*/10 * * * * /usr/bin/flock -n /tmp/codex-iterate.lock /www/scripts/codex_iterate_once.sh >/dev/null 2>&1
```

- 防重入：`flock`
- 会话机制：
  - 首次运行自动创建 session
  - 后续运行自动 `codex exec resume <session_id>`（若上次已停则继续）
  - session id 文件：`/www/autolab/runtime/codex_session_id.txt`
- 超时控制：脚本内默认 `CODEX_ITER_TIMEOUT_SEC=540`（9 分钟，避免超过 10 分钟心跳周期）
- 日志：`/www/autolab/runtime/codex_iterate.log`
- 事件流：`/www/autolab/runtime/codex_events.jsonl`
- 迭代评测隔离目录：`/www/autolab/runtime/scopes/iter/`
- 迭代评测脚本：`/www/scripts/autolab_eval_experiment_once.sh`
- 迭代评测默认并发：`jobs=14`、`cpu-policy=all`（迭代优先）
- Elo 口径：iter `latest.json` 仅用于候选筛选，不能直接与生产 Elo 横向比绝对值

关键命令：

```bash
crontab -l
rg -n "START codex iteration|END codex iteration" /www/autolab/runtime/codex_iterate.log
```

## 3) CPU 限制有效性验证结论

已做实测：在 `--pin-cpu` 下，`autolab` worker 与 `ai_v*` 子进程亲和性一致，并落在 `selected_cores` 内。

示例（节选）：

- worker affinity：`0,1,4,5,...,15`
- AI 进程 affinity：与其父 worker 对齐（如 `ai_v2 -> core 0`, `ai_v1 -> core 4`）

结论：评测负载可被限制在“本轮选中核心”集合内；当设置 `jobs=14` 时，最多使用 14 个核心。

## 4) 去重说明（quota-guard）

- `quota-guard` 仅保留 cron 一处触发（每 10 分钟）。
- `codex-supervisor.sh` 已移除对 `quota-guard` 的二次调用，避免重复扫描/重复 rotation。
