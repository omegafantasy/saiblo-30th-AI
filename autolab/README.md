# Autolab（第二轮本地迭代系统）

用于管理 AI 版本、批量并行评测、Elo 计算与定时自动评测。

## 组件

- `autolab_manage.py`
  - 版本注册/查看/设置 champion/快照。
- `autolab_eval.py`
  - 批量评测 + Elo 计算 + 可选自动晋升 champion。
- `autolab_schedule.py`
  - 定时执行评测轮次（循环调用 `autolab_eval.py`）。
- `autolab/registry.json`
  - 版本注册表。
- `autolab/runtime/`
  - 评测产物（json/jsonl），已默认 `.gitignore`。
- `autolab/versions/`
  - 本地快照版本（含二进制），已默认 `.gitignore`。

## 快速开始

```bash
# 1) 初始化注册表（若不存在）
python /www/autolab_manage.py init

# 2) 查看版本
python /www/autolab_manage.py list

# 3) 快照当前 C++ AI 为一个新版本
python /www/autolab_manage.py snapshot-cpp \
  --version-id cpp_v1_snapshot_001 \
  --src /www/ai_cpp/v1/ai_v1.cpp \
  --exe /www/ai_cpp/v1/ai_v1 \
  --notes "baseline snapshot"

# 4) 跑一轮 gauntlet（默认优先用 14 并行）
python /www/autolab_eval.py --mode gauntlet --games-per-pair 20 --jobs 14

# 4.1) 仅使用“检测到空闲”的 CPU 核，并绑定评测进程
python /www/autolab_eval.py \
  --mode gauntlet \
  --games-per-pair 20 \
  --jobs 14 \
  --cpu-policy idle_only \
  --idle-threshold 0.02 \
  --pin-cpu

# 5) 每 30 分钟跑一轮（示例：共 8 轮）
python /www/autolab_schedule.py \
  --interval-min 30 \
  --cycles 8 \
  --eval-args "--mode gauntlet --games-per-pair 20 --jobs 14"
```

## 评测模式

- `round_robin`: 所有已启用版本两两对战。
- `gauntlet`: challenger 对 champion + anchor。

默认 anchor 是 `greedy` 与 `random_safe`。

## CPU 策略

- `--cpu-policy all`：使用全部可见 CPU（仍可 `--pin-cpu` 限制到选中的 workers 核）。
- `--cpu-policy idle_only`：先采样 `/proc/stat`，仅选择“低占用核”参与评测。
- `--pin-cpu/--no-pin-cpu`：是否给 worker 进程设置 CPU 亲和性（Linux 下使用 `sched_setaffinity`）。

## 生产评测 vs 实验评测（已隔离）

- 生产评测（autolab idle loop）：
  - 使用默认 runtime 根目录：`/www/autolab/runtime/`
  - 会写 `latest.json`
  - 允许 `--auto-promote`
- 实验评测（给 codex 迭代使用）：
  - 使用 scope：`/www/autolab/runtime/scopes/iter/`
  - 默认不晋升 champion（`--no-auto-promote`）
  - 入口脚本：`/www/scripts/autolab_eval_experiment_once.sh`
  - 默认高并发：`jobs=14`，`cpu-policy=all`（迭代优先）

新增参数：

- `--runtime-scope <name>`：将产物写到 `autolab/runtime/scopes/<name>/`
- `--write-latest/--no-write-latest`：是否写当前 scope 的 `latest.json`
- `EXPERIMENT_ALLOW_ARG_OVERRIDE=1`：允许实验脚本接受命令行 `--jobs/--cpu-policy` 覆盖（默认关闭）

## 常驻与定时（当前已配置）

- 常驻评测（systemd）：
  - 服务名：`autolab-idle-eval.service`
  - 脚本：`/www/scripts/autolab_idle_eval_loop.sh`
  - unit 模板：`/www/scripts/systemd/autolab-idle-eval.service`
  - 默认：空闲核优先、最多 14 jobs、绑定亲和性。
- Codex 自动迭代（cron，每 10 分钟）：
  - 脚本：`/www/scripts/codex_iterate_once.sh`
  - 防重入锁：`/tmp/codex-iterate.lock`
  - 自动 session 续跑：首次新建，后续 `exec resume` 继续。
  - session 文件：`/www/autolab/runtime/codex_session_id.txt`
  - 脚本内默认超时：`540s`（避免超过心跳周期）。
  - 迭代评测应使用实验脚本：`/www/scripts/autolab_eval_experiment_once.sh`

状态检查：

```bash
systemctl status autolab-idle-eval.service --no-pager -l
tail -n 120 /www/autolab/runtime/idle_eval_loop.log
crontab -l
rg -n "START codex iteration|END codex iteration" /www/autolab/runtime/codex_iterate.log
```
