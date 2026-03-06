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

# 6) 分析最新一轮 replay（iter scope）
python /www/autolab_replay_analyze.py --scope iter --latest
```

## 评测模式

- `round_robin`: 所有已启用版本两两对战。
- `gauntlet`: challenger 对 champion + anchor。
- `adaptive`: 随机加权抽样对阵（推荐生产常驻）：
  - 基础是均匀随机匹配；
  - 当前排名靠前版本获得额外采样权重；
  - 累计局数较少（新版本/低样本）获得额外采样权重。

默认 anchor 是 `greedy` 与 `random_safe`。

可选降采样参数：

- `--anchor-games-per-pair N`：仅对 gauntlet 中 anchor 对手使用更小的种子数；
  - `0` 表示与 `--games-per-pair` 相同；
  - 例如 `--games-per-pair 6 --anchor-games-per-pair 1`，可显著减少 `greedy/random_safe` 对局占比。

`adaptive` 关键参数：

- `--adaptive-pair-count N`：每轮抽样多少个 pair（可重复抽样）。
- `--adaptive-top-k K`、`--adaptive-top-boost B`：前 K 名的加权强度。
- `--adaptive-new-target-games G`、`--adaptive-new-boost B`：累计局数低于 G 时的加权强度。

Replay 相关参数：

- `--save-replays/--no-save-replays`：是否保存每局 replay（默认开启）。
- replay 默认落盘目录：
  - 生产：`/www/autolab/runtime/replays/<eval_tag>/`
  - 实验：`/www/autolab/runtime/scopes/<scope>/replays/<eval_tag>/`

## CPU 策略

- `--cpu-policy all`：使用全部可见 CPU（仍可 `--pin-cpu` 限制到选中的 workers 核）。
- `--cpu-policy idle_only`：先采样 `/proc/stat`，仅选择“低占用核”参与评测。
- `--pin-cpu/--no-pin-cpu`：是否给 worker 进程设置 CPU 亲和性（Linux 下使用 `sched_setaffinity`）。

## 生产评测 vs 实验评测（已隔离）

- 生产评测（autolab idle loop）：
  - 使用默认 runtime 根目录：`/www/autolab/runtime/`
  - 会写 `latest.json`（累计口径）
  - 允许 `--auto-promote`
  - `latest.json` 的 `config.rating_mode=cumulative`：
    - Elo 与局数按生产历史对局累计计算；
    - 自动剔除“注册表中已不存在/不可执行”的版本，不参与累计榜与晋升判定。
- 实验评测（给 codex 迭代使用）：
  - 使用 scope：`/www/autolab/runtime/scopes/iter/`
  - 默认不晋升 champion（`--no-auto-promote`）
  - 入口脚本：`/www/scripts/autolab_eval_experiment_once.sh`
  - 默认高并发：`jobs=14`，`cpu-policy=all`（迭代优先）
  - 实验脚本会在评测后自动生成 replay 分析：
    - `autolab/runtime/scopes/iter/replay_analysis/latest.json`
    - `docs/replay_analysis/iter_latest.md`
  - 强度比较口径：
    - 两 AI 对比至少 `100` 局才可下结论；
    - 声明“新版优于 k 个旧版”时，建议每个对手 `>=200` 局且胜率 `>55%`，或在 `>=1000` 局 Elo 评测中稳定榜首。

Elo 治理规则（必须遵守）：

- 生产 Elo（`/www/autolab/runtime/latest.json`）是唯一权威排名，用于 champion 与版本优劣最终判定。
- 迭代 Elo（`/www/autolab/runtime/scopes/iter/latest.json`）仅用于候选筛选与方向探索。
- 不同 scope、不同对阵池的 Elo 绝对值不可直接横向比较。

新增参数：

- `--runtime-scope <name>`：将产物写到 `autolab/runtime/scopes/<name>/`
- `--write-latest/--no-write-latest`：是否写当前 scope 的 `latest.json`
- `--save-replays/--no-save-replays`：是否保存对局 replay（默认保存）
- `EXPERIMENT_ALLOW_ARG_OVERRIDE=1`：允许实验脚本接受命令行 `--jobs/--cpu-policy` 覆盖（默认关闭）

## 常驻与定时（当前已配置）

- 常驻评测（systemd）：
  - 服务名：`autolab-idle-eval.service`
  - 脚本：`/www/scripts/autolab_idle_eval_loop.sh`
  - unit 模板：`/www/scripts/systemd/autolab-idle-eval.service`
  - 默认：`mode=adaptive`、空闲核优先、最多 14 jobs、绑定亲和性。
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
