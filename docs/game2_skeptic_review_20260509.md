# Game2 Skeptic Review 2026-05-09

更新时间：`2026-05-09 07:42 UTC`

本文件是旁路审计，不接管另一个 Codex 进程的 `n*` 版本线；本轮已按要求执行独立上传与并发评测。新增产物使用 `skeptic` 命名：

- `Game2/tools/skeptic_room_feature_mine.py`
- `Game2/tools/skeptic_eval_gate.py`
- `Game2/tools/skeptic_gap_mode_audit.py`
- `Game2/tools/skeptic_residual_trace_diff.py`
- `Game2/tools/skeptic_identity_factor_audit.py`
- `Game2/tools/skeptic_role_mapping_audit.py`
- `docs/generated/game2_skeptic_room_feature_mine.md`
- `docs/generated/game2_skeptic_eval_gate.md`
- `docs/generated/game2_skeptic_gap_mode_audit.md`
- `docs/generated/game2_skeptic_residual_trace_diff.md`
- `docs/generated/game2_skeptic_identity_factor_audit_n548.md`
- `docs/generated/game2_skeptic_identity_factor_audit_sk548.md`
- `docs/generated/game2_skeptic_role_mapping_audit_n548.md`
- `docs/generated/game2_skeptic_role_mapping_audit_sk548.md`
- `Game2/tools/skeptic_ablation_summary.py`
- `docs/generated/game2_skeptic_ablation_summary_sk548e0910.md`

## 独立审视结论

当前瓶颈不应再被简单表述为“Poker stage3 不稳定”。这是把多个不同低尾来源混成一个问题：

- 一类低尾能被前案路径解释。`skeptic_room_feature_mine` 在 `529` 条核心可比样本中发现，`rose.reply_count=44` 只出现在低分侧；例如 `n527e_expand1` 中低分 `2717 x5` 的 Rose reply count 为 `44`，高分 `2757 x10` 为 `41`。这说明部分 stage3 低尾不是 Poker 证据或答案文本问题，而是前案额外问句/效率/路径污染。
- 另一类低尾目前仍是真不可见因子。`n539d`、`n545d` 的低分与高分在 Rose reply count、record count、Poker stage、Poker evidence、Z/F err8 上高度同形，脚本没有找到稳定的 NPC 身份或接待者回复分隔器。继续微调 Poker 问句很可能是在噪声上过拟合。
- Yuan 方向不能因为出现 `703/704` 就升优先级。核心样本里 `yuan.evidence_ids=001,703,704` 当前只有 `4` 条且全高分，支持度太低；反向证据是 `n544a` 这类低成本 Yuan 投票问法已经出现 `2467`。
- 最新可见的 `n547a/b/c/d` 房间结果很低：`n547a=207 x5`，`n547b=207 x5`，`n547c=1607 x4, 1407 x1`，`n547d=1257 x2, 1217 x1`。只读 diff 显示它们引入了 `ISO_MODE=zero_hard/zero_soft/direct_min/rose_only`，更像故意牺牲总分的隔离探针；因此它们不应被当作生产候选，也不应和高分主线直接比较。

## 对现有思路的批判

小样本高分被赋予了过高权重。`n546e` 的 `4/4` 全 `2757` 不能证明稳定；Wilson 95% 上界显示即使零低尾，`4` 样本仍允许约 `49%` 的真实低尾概率。`16/16` 也只能作为晋级筛，不能作为定版证明。

最低分口径是对的，但当前门槛还不够定量。`n518b` 的 `25` 样本 min `2657` 仍是保守地板；`n539d` 均值更高但已有 `2557`，`n545d` 也已有 `2557`。若目标是稳定提交，低于 `2657` 的概率应被明确量化，而不是用“前缀看起来稳定”描述。

把所有 stage3 低尾都归咎于 hidden scorer 会掩盖可修的问题。先把 `rose.reply_count=44/39` 这类可见污染分离出去，再讨论剩下的同形低尾，才更有利于突破。

## 下一步建议

1. 把 `n547a/b/c/d` 明确标注为隔离探针，不进入生产候选池；若继续做 isolation，应记录每个模式的目标分案和预期牺牲。
2. 对高分路线分层评估：`n527e` 类先修前案 reply count，`n539d/n545d` 类才进入 hidden/final-answer 假设。
3. 新候选不要再增加 Poker/Yuan 聊天；优先做零交互 final-answer 文本 A/B，或者做完全等交互的答案文本 A/B。
4. 扩样门槛改为两层：晋级用 `>=16` 且无 `<2657`；定版至少 `30+`，并用 `skeptic_eval_gate.py` 报告 `<2657` Wilson 上界。
5. 继续用 `skeptic_room_feature_mine.py` 作为旁路审计器，每轮新房间后先看是否出现新的可见分隔器，再决定是否需要改代码。

## 新增独立突破：Gap 模式审计

新增脚本：`Game2/tools/skeptic_gap_mode_audit.py`  
产物：

- `docs/generated/game2_skeptic_gap_mode_audit.json`
- `docs/generated/game2_skeptic_gap_mode_audit.md`

这个审计不沿用“某标签是否稳定”的叙事，而是按每条样本相对本标签上限分 `gap = label_max - score` 做分解：

- 可解释缺口：`rose_lag(+40)`、`poker_stage_3_to_1(+100)`。
- 残余缺口：`residual = gap - estimated`，用于定位真正未解释模式。

对 `n548` 的独立结论：

- `n548g/h/i` 的 `2717` 大多是 `rose_lag`，属于 `+40` 可解释模式；
- `n548h` 的 `2657` 对应 `poker stage 3->1` 与关键证据缺失，可解释 `-100`；
- 关键未解释点是 residual `200`：
  - `n548d` 的 `2417`（`rose_lag+residual`）
  - `n548e` 的 `1957`（`residual_only`）

因此卡点不是“泛化地再加样本”，而是应先围绕 residual=200 模式做隔离对照。

新增跟进脚本：`Game2/tools/skeptic_residual_followup_queue.py`

- 从 `game2_skeptic_gap_mode_audit.json` 自动挑 residual 最大的标签；
- 当前自动选择结果是 `n548e`, `n548d`；
- 可直接触发恢复队列（可先 dry-run）：

```bash
python3 Game2/tools/skeptic_residual_followup_queue.py \
  --label-prefix n548 \
  --min-residual 200 \
  --top-k 2 \
  --run-queue \
  --dry-run-queue
```

## 独立上传探针（旁路）

为了避免影响主线 `n548*` 实体，本轮用了独立实体名：

- entity: `sk548e0909a`
- source: `Game2/deepclue_ai/n548e/ai.py`
- upload result: 编译成功，code_id=`e3e758f8836940bdabfa6774df093abb`
- room eval: `sk548e0909a_probe1` 3 局 -> `2117, 2117, 2157`
  - out_dir: `Game2/runtime/room_matches/20260509_020711_sk548e0909a_probe1_room`

这证明 `n548e` 低平台并非只存在于历史数据，独立上传后仍可复现。

## 最新旁观发现（来自实时追踪）

`n548i_more2` 新增样本中出现 `2517`（同组还有 `2717/2757`），在 gap 审计中被归为 `rose_lag+residual`，残余缺口仍为 `200`：

- path: `Game2/runtime/room_matches/20260509_020312_n548i_more2_room/matches/8099556/analysis.json`
- gap decomposition: `2757 -> 2517 = 240 = 40(rose_lag) + 200(residual)`

这说明 residual=200 模式已从 `n548d/e` 扩展到 `n548i`，仅靠补样本无法自然消失，必须做专门隔离。

## Continuous Tracking Setup

已新增独立 watcher：`Game2/tools/skeptic_watch_codex_progress.py`，每轮会做四件事：

1. 增量读取 `/root/.codex/sessions/**/rollout-*.jsonl`，提取新命令、新标签、上传信号。
2. 增量扫描 `Game2/runtime/room_matches/*/matches/*/analysis.json`，汇总新样本分布和低分尾部。
3. 在有变化时自动重跑：
   - `Game2/tools/skeptic_room_feature_mine.py`
   - `Game2/tools/skeptic_eval_gate.py`
   - `Game2/tools/skeptic_gap_mode_audit.py`
   - `Game2/tools/skeptic_residual_trace_diff.py`
4. 写出滚动状态：
   - `Game2/runtime/skeptic_watch/status.json`（最新快照）
   - `Game2/runtime/skeptic_watch/history.jsonl`（每轮记录）
   - `Game2/runtime/skeptic_watch/watch.log`（文本日志）

并且在有变化时自动补跑：

- `Game2/tools/skeptic_identity_factor_audit.py`（`n548` 与 `sk548` 两套配置）
- `Game2/tools/skeptic_role_mapping_audit.py`（`n548` 与 `sk548` 两套配置）

管理脚本：

- `scripts/skeptic_watch_start.sh`
- `scripts/skeptic_watch_status.sh`
- `scripts/skeptic_watch_stop.sh`

默认是旁路观察，不触发外部动作。若要“你自己也进行上传等”，可在启动时挂 action 命令（按触发条件与冷却执行）：

```bash
SKEPTIC_WATCH_ACTION_CMD="python3 Game2/tools/run_recovery_eval_queue.py --labels n548e n548f n548g --count 5 --continue-on-error" \
SKEPTIC_WATCH_ACTION_TRIGGER="on_change" \
SKEPTIC_WATCH_ACTION_COOLDOWN=1800 \
bash scripts/skeptic_watch_start.sh
```

或只在检测到低分尾时触发：

```bash
SKEPTIC_WATCH_ACTION_CMD="python3 Game2/tools/run_recovery_eval_queue.py --labels n548d --count 5 --continue-on-error --allow-partial-eval" \
SKEPTIC_WATCH_ACTION_TRIGGER="on_low_score" \
bash scripts/skeptic_watch_start.sh
```

## 增量独立结论：Trace 同构残差

新增脚本：`Game2/tools/skeptic_residual_trace_diff.py`  
产物：

- `docs/generated/game2_skeptic_residual_trace_diff.json`
- `docs/generated/game2_skeptic_residual_trace_diff.md`

它不是再做“低分统计”，而是对每个 residual 行逐项对比同标签 max 样本的**阶段时序、证据解锁次序、布尔选择模式**，检查是否存在可观测分叉。

本轮结果（`n548`, residual>=200）：

- `n548e` `8097078`（`1957`）是 `trace-equivalent-residual`：
  - 与同标签 `2157` 参考样本在可观测轨迹签名完全同构；
  - 没有任何可见阶段/证据/选择模式差异可以解释 `-200`。
- `n548d` `8097052`、`n548i` `8099556`：
  - 仅观察到 Rose stage6 到达滞后 `+4`（对应已知 `+40`）；
  - 其余结构一致，`residual 200` 仍未解释。

结论：`n548` 的核心瓶颈已不是“多跑几局看均值”，而是存在**同轨迹残差**。后续应把精力放在 hidden branch/final scoring 因子隔离，而非继续泛化地改问句。

## 并发旁路探针增量（独立上传 + 并发开房）

本轮按旁路命名继续做独立动作，不改主线实体：

- 新增上传：`sk548i0909a`（source=`Game2/deepclue_ai/n548i/ai.py`，code_id=`340d8c5e8032447a8a10382e424eafa4`，编译成功）
- `sk548i0909a_probe1`（5 局）：`2757, 2757, 2757, 2757, 2757`
- 并发 `probe2`（两路同时开房）：
  - `sk548e0909a_probe2`（4 局）：`2117, 2117, 2157, 2157`
  - `sk548i0909a_probe2`（4 局）：`2717, 2757, 2557, 2757`

新增 `sk548*` 专用 trace diff 产物：

- `docs/generated/game2_skeptic_sk548_trace_diff.json`
- `docs/generated/game2_skeptic_sk548_trace_diff.md`

关键结论：

- `sk548i0909a_probe2` 的 `2557` 相对同批 `2757` 出现 `gap=200`；
- 在可观测轨迹上是 `trace-equivalent-residual`（无阶段/证据/选择模式偏差可解释）；
- 这与 `n548e` 的 `1957` 同轨迹残差现象同型，进一步支持“存在未观测评分因子/隐藏分叉”，而不是单纯 Rose/Poker 可见路径问题。

## 二次并发扩样结论（批判性反证）

本轮继续并发开房（独立实体，不动主线）：

- `sk548d0909a_probe2`（10 局）：`2457 x1, 2657 x9`
- `sk548e0909a_probe4`（10 局）：`1957 x1, 2117 x4, 2157 x5`
- `sk548i0909a_probe4`（10 局）：`2517 x1, 2657 x1, 2717 x3, 2757 x5`

合并历史旁路样本后：

- `sk548d0909a`：`n=18`，`{2457:2, 2617:2, 2657:14}`
- `sk548e0909a`：`n=25`，`{1957:4, 2117:9, 2157:12}`
- `sk548i0909a`：`n=27`，`{2517:1, 2557:1, 2657:1, 2717:4, 2757:20}`

新增 `sk548` trace diff 报告：

- `docs/generated/game2_skeptic_sk548_trace_diff.md`

其中 `residual=200` 行共有 `8` 条，`7` 条是 `trace-equivalent-residual`（`diff_count=0`）：

- `sk548d` 的 `2457`（2 次）均为 `residual_only` 且同轨迹；
- `sk548e` 的 `1957`（4 次）均为 `residual_only` 且同轨迹；
- `sk548i` 的 `2557`（1 次）为 `residual_only` 且同轨迹；
- 仅 `sk548i` 的 `2517` 属于 `rose_lag+residual`（可见 `stage6` 滞后）。

批判点（对“继续调可见路径就能解锁”的反证）：

- `sk548d/e` 的 `200` 缺口可在 Rose/Poker 结构不变时重复出现，不能再归结为“Rose 慢了一点”；
- `sk548e` 的 `1957` 已从偶发变成可复现分布尾部（`4/25`）；
- `sk548i` 虽然高分占优，但仍可出现 `residual_only=200`，说明问题并非某单一标签特有。

## 新角度：身份因子审计（Identity Factor）

新增脚本：`Game2/tools/skeptic_identity_factor_audit.py`

产物：

- `docs/generated/game2_skeptic_identity_factor_audit_sk548.md`
- `docs/generated/game2_skeptic_identity_factor_audit_n548.md`

用途：

- 不再只看 stage/evidence，而是审计 `decoded_stdin_records` 中的身份映射特征（初始可见 NPC 集、首轮 false mark、各 choice 的 false/true 身份集合）与 target residual 的关联。

当前读数：

- `sk548`（target=`residual_only & residual>=200`）：`70` 行中 `7` 行 target（base rate `0.10`）。
- `n548`（target=`residual>=200`，mode=`any`）：`80` 行中 `3` 行 target（base rate `0.0375`）。

批判性结论：

- 身份特征存在高 lift 候选，但多数支持度仍低（`support=2~6`），暂不足以单独解释残差；
- 这支持“有身份相关隐因子”的可能性，但也反证“靠单个可见身份规则就能稳定修复”的过度简化叙事。

## 新角度：角色置换审计（Role Mapping）

新增脚本：`Game2/tools/skeptic_role_mapping_audit.py`

方法：

- 从 `match_download.json` 的 step0 `result_state.evidences` 抽取回忆角色映射（`mem_002/003/004`）；
- 结合首轮 `visible_npcs` 与 `npc_marks` 的 false 集，构造交叉特征（如 `cross.host_false=*`）；
- 评估这些特征对 target residual（`residual>=200`）的 lift。

产物：

- `docs/generated/game2_skeptic_role_mapping_audit_sk548.md`
- `docs/generated/game2_skeptic_role_mapping_audit_n548.md`

当前读数：

- `sk548`（target=`residual_only & residual>=200`）：`70` 行、`7` 行 target（base rate `0.10`）；
- `n548`（target=`residual>=200`, mode=`any`）：`80` 行、`3` 行 target（base rate `0.0375`）。

批判性结论：

- 与 identity audit 一致，角色置换确实出现高 lift 候选，说明残差与身份置换有关联；
- 但高 lift 特征仍普遍低支持度，不能把它当成稳定单因果；
- 这进一步支持“隐藏分支/混合因子”而不是“单一可见规则修复”。

## 三次并发扩样（独立上传 `sk548e0909b`）

新增上传（旁路，不动主线）：

- entity: `sk548e0909b`
- source: `Game2/deepclue_ai/n548e/ai.py`
- code_id: `c8248b0ee38540a09f363a46385e5658`
- compile: `编译成功`

并发 4 路 × 8 局（共 32 局）：

- `sk548e0909b_probe1a`：`2157 x6, 2117 x2`
- `sk548e0909b_probe1b`：`2157 x4, 2117 x4`
- `sk548e0909b_probe1c`：`2157 x2, 2117 x2, 1957 x3, 1917 x1`
- `sk548e0909b_probe1d`：`2157 x2, 2117 x1, 2057 x1, 2017 x2, 1957 x1, 1917 x1`

合并后分布（`sk548e0909*`）：

- `sk548e0909a`：`n=57`，`{1857:1, 1917:2, 1957:9, 2017:2, 2057:2, 2117:15, 2157:26}`
- `sk548e0909b`：`n=32`，`{1917:2, 1957:4, 2017:2, 2057:1, 2117:9, 2157:14}`
- 合并：`n=89`，`{1857:1, 1917:4, 1957:13, 2017:4, 2057:3, 2117:24, 2157:40}`

批判性结论：

- 低尾结构复现且扩宽，不是单次偶然：`1957/1917/2017/2057/1857` 均持续出现。
- 新上传实体与旧实体分布同型，说明问题不是某次上传产物污染。

## Trace Diff 更新（`sk548`, residual>=100）

已更新：

- `docs/generated/game2_skeptic_sk548_trace_diff.json`
- `docs/generated/game2_skeptic_sk548_trace_diff.md`

当前统计：

- residual 行 `22` 条；
- `trace-equivalent-residual`：`15`
- `observable-diff`：`7`

其中 `sk548e0909b` 新增行里，`1957` 仍以 `residual_only` 为主，且已出现多条 `diff_count=0` 的同轨迹残差；说明扩样后“同轨迹残差”没有被样本自然冲掉。

## 新角度：Hidden Branch 分层差分

新增脚本：

- `Game2/tools/skeptic_hidden_branch_diff.py`

新增产物：

- `docs/generated/game2_skeptic_hidden_branch_diff_sk548e.json`
- `docs/generated/game2_skeptic_hidden_branch_diff_sk548e.md`

方法：

- 以 `2157` 为参考档，对各低分档（`2117/2057/2017/1957/1917/1857`）做身份映射与最终答案字段的富集对比；
- 输出每档相对高分档的 lift 特征，直接识别“哪类身份置换在低档位显著偏高”。

关键读数（重点看 `1957` residual-only 档）：

- `1957` 档 `n=13`，全部 `mode=residual_only`；
- 特征 `false_mark=ZhouLinJun` 与 `killer_cn=周林君` 在 `1957` 档的占比为 `3/13`，相对 `2157` 档 `1/40`，lift≈`9.23`；
- 另有 `banker_like=张子韩/叶青衡` 在 `1957` 档也显著抬升（lift≈`6.15`）。

批判性结论：

- residual-only 的 `1957` 不是均匀噪声，更像“特定角色置换组合”的条件性掉分；
- 这比“继续调可见问句流程”更能解释为何同轨迹仍然掉 `200`。

## 自动追踪链路升级

watcher 已重启并加载新审计：

- PID: `905143`
- 状态路径：`Game2/runtime/skeptic_watch/status.json`
- `tools` 新增键：`hidden_branch_diff_sk548e`

这保证后续每轮增量样本都会自动刷新 hidden-branch 分层结果，而不是只靠手工一次性分析。

## 自动动作闭环验证（watcher 自主并发补样）

为满足“持续追踪 + 自主动作”，watcher 已挂 action 命令：

- action cmd: `bash scripts/skeptic_auto_probe_sk548e.sh`
- trigger: `on_change`
- cooldown: `1800s`

本轮已实际触发并完成（非 dry-run）：

- `status.action.status = ran`
- `status.action.ok = true`
- action duration: `264.852s`

自动补样产物（`sk548e0909b_auto1..4`，共 `16` 局）：

- 汇总：`{1957:1, 2017:1, 2057:1, 2117:5, 2157:8}`
- 仍出现 `1957 residual-only`，说明即使改为 watcher 自动触发，低尾模式依旧复现。

更新后 `sk548e0909*` 总分布（`a + b + b_auto*`）：

- `n=105`，`{1857:1, 1917:4, 1957:14, 2017:5, 2057:4, 2117:29, 2157:48}`

## 结构性新结论：`200` 更像离散惩罚项

基于最新 `gap_mode_audit`：

- `sk548` 非 max 行 residual 分布只有两档：`{0: 38, 200: 23}`
- `n548` 非 max 行 residual 分布也是两档：`{0: 15, 200: 3}`

没有出现 `residual=40/80/120/...` 这类连续谱，说明当前瓶颈更像“隐藏二值惩罚（命中则 -200）”，而不是可见路径导致的连续抖动。

这与可见模式分解一致：

- `rose_lag` 解释 `-40`
- `poker_stage_drop` 解释 `-100`
- 其余未解释部分几乎总是精确 `-200`

## 新角度：跨组泛化审计（反过拟合）

新增脚本：

- `Game2/tools/skeptic_feature_generalization_audit.py`

新增产物：

- `docs/generated/game2_skeptic_feature_generalization_audit_sk548.json`
- `docs/generated/game2_skeptic_feature_generalization_audit_sk548.md`

目的：

- 不接受“单组 lift 很高”作为证据；
- 直接检验特征在独立组（`sk548d/e/i`）是否可迁移（leave-one-group-out 风格）。

当前读数（`rows=150`, `target_rows=17`）：

- 组基线：
  - `sk548d0909a`: `0.111111`
  - `sk548e0909a`: `0.157895`
  - `sk548e0909b`: `0.104167`
  - `sk548i0909a`: `0.037037`
- 大多数高 lift 特征只有 `stable_holdouts <= 2`，跨组稳定性弱；
- 相对更稳定的少数特征包括：
  - `partner_like=赵一橙`（`stable_holdouts=3`）
  - `killer_cn=王科瑾`（`stable_holdouts=3`）
  - `false_mark=WangKeJin`（`stable_holdouts=3`）

批判性结论：

- 许多“高 lift”其实是组内模式，不应直接升级为全局因果；
- 后续应优先追踪“跨组稳定”特征，而不是继续追逐单组高分解释。

## 2026-05-09 04:40 UTC 增量迭代：`0910` 系列 A/B 与反证

本轮新增独立变体与产物：

- `sk548e0910d`（`rose_direct_only`）
- `sk548e0910f`（`rose_only`）
- `sk548e0910g`（Rose 条件 guardrail：命中 4 信号中的 `>=2` 才降级 direct）
- `sk548e0910h`（在 `0910g` 基础上追加 `false_mark=ZhouLinJun` 强制 direct）
- 汇总产物：`docs/generated/game2_skeptic_ablation_summary_sk548e0910.md`
- 分层产物：
  - `docs/generated/game2_skeptic_hidden_branch_diff_sk548e0910g.md`
  - `docs/generated/game2_skeptic_hidden_branch_diff_sk548e0910h.md`

关键分布（每组 `n=16`）：

- `0910d`：`807x16`（完全失效）
- `0910f`：`1217x3, 1257x13`（严重退化）
- `0910g`：`1957x1, 2017x1, 2057x2, 2117x3, 2157x9`
- `0910h`：`1707x1, 1917x1, 1957x1, 2117x4, 2157x9`

批判性结论：

- `0910d/f` 已被实证否定，不能继续作为方向。
- `0910g` 明显优于 `0910d/f`，并保持高分平台；但仍存在 `1957 residual_only`（`1/16`）。
- `0910h` 为负结果：引入新的 `1707 residual_only (residual=450)`，属于过激 guard 的回归，不应继续。
- `0910h` 的 `1707` 行在分层报告中出现 `rose_step_count=4` 与 `triplet=||`，提示 Rose 路径被过早截断，属于策略性伤害而非随机波动。

当前策略决议：

- 保留 `0910g` 作为“窄 guardrail”候选；
- 明确淘汰 `0910h`；
- 后续仅在 `0910g` 上做更保守的局部修正，不再做强制型全局触发。

自动追踪链路同步更新：

- watcher 工具链新增 `ablation_summary_sk548e0910`，已并入 `status.json.tools`；
- action 仍为 `on_change + 1800s cooldown` 并调用 `scripts/skeptic_auto_probe_sk548e.sh`；
- 当前 watcher 进程：`pid=939628`（状态文件：`Game2/runtime/skeptic_watch/status.json`）。

## 2026-05-09 04:56 UTC 增量迭代：`0910i` 抗早停复测

本轮在 `sk548e0910i` 上继续并发扩样（4 路并发）：

- 已有 `ab1..ab4`（`n=16`）：`1957x2, 2057x1, 2117x5, 2157x8`
- 新增 `ab5..ab8`（`n=16`）：`2117x6, 2157x10`
- 累计 `0910i`（`n=32`）：`1957x2, 2057x1, 2117x11, 2157x18`，`avg=2127.625`

对比同口径：

- `0910g`（`n=16`）：`1957x1, 2017x1, 2057x2, 2117x3, 2157x9`，`avg=2115.75`
- `0910h`（`n=16`）：`1707x1, 1917x1, 1957x1, 2117x4, 2157x9`，`avg=2091.375`

批判性结论：

- `0910i` 的抗早停修正确实消除了 `0910h` 式灾难尾（`1707/1917` 未复现）。
- 新增 16 局没有产生新的 `<2117` 低尾；稳定性显著好于 `0910g/h`。
- 但 `1957 residual_only` 仍保留 `2/32`，且 trace diff 仍是 `trace-equivalent-residual`，说明隐藏 `-200` 惩罚并未被可见流程修复。

当前策略决议（更新）：

- 将 `0910i` 晋升为 skeptic 线当前 base（优先于 `0910g`）。
- 不再引入 `0910h` 这种强制分支规则。
- 下一轮只做“隐藏因子定向隔离”而非再改大流程：在 `0910i` 上围绕 residual-only 样本做身份/答案字段对照，避免重新触发策略性伤害。

## 2026-05-09 05:07 UTC 增量迭代：`i_auto` 闭环反证

为避免“手工并发样本偏乐观”，本轮把 watcher 自动动作链路默认切到 `0910i`：

- `scripts/skeptic_auto_probe_sk548e.sh`
  - 默认 entity：`sk548e0910i`
  - 默认 label 前缀：`sk548e0910i_auto`
- 并手动触发一轮闭环验证（`auto1..4`，共 `16` 局）。

`i_auto` 分布：

- `sk548e0910i_auto1`：`2117x1, 2157x3`
- `sk548e0910i_auto2`：`1957x1, 2117x2, 2157x1`
- `sk548e0910i_auto3`：`2017x1, 2117x1, 2157x2`
- `sk548e0910i_auto4`：`2117x2, 2157x2`
- 合并：`1957x1, 2017x1, 2117x6, 2157x8`（`avg=2120.75`）

与 `0910i_ab` 合并后（`n=48`）：

- `1957x3, 2017x1, 2057x1, 2117x17, 2157x26`，`avg=2125.333`

批判性结论：

- `0910i` 仍显著优于 `0910h`（没有 `1707/1917` 灾难尾），但并未根治 residual 尾部；
- `i_auto` 已复现 `1957 residual_only`，且 `sk548e0910i_all` trace diff 中 residual 行 `3/3` 仍是 `trace-equivalent-residual`；
- 这再次反证“可见流程已修复”的叙事：当前改动主要修复了早停灾难，但隐藏 `-200` 惩罚仍在。

策略修订（保持独立 skeptic 立场）：

- `0910i` 继续作为运行基线，但不得宣称“稳定解锁”；
- 迭代重点转为 hidden-branch 定向隔离，不再继续加大可见流程规则强度。

## 2026-05-09 05:21 UTC 增量迭代：`0910j` 反证试验（已淘汰）

为了检验“`0910h` 的退化是否主要由早停脆弱性触发”，本轮构造最小改动变体：

- 基线：`sk548e0910i`（保留 bootstrap 抗早停）
- 变更：仅加回 `h` 的 forced-direct 规则  
  `false_mark=ZhouLinJun -> rose_direct`
- 新实体：`sk548e0910j`
- 上传：`code_id=912ef0fec0554c4a8024f938fc88da8d`（编译成功并激活）
- 并发评测：`j_ab1..ab4` 共 `16` 局

`0910j` 分布：

- `1917x1, 1957x3, 2017x1, 2117x1, 2157x10`，`avg=2093.25`

与 `0910i` 对比：

- `0910i_ab`（`n=32`）：`avg=2127.625`
- `0910i_auto`（累计 `n=32`）：`avg=2125.75`
- `0910i` 合并口径（`ab+auto`, `n=64`）：`1957x3, 2017x2, 2057x1, 2117x24, 2157x34`，`avg=2126.688`

审计结果（`0910j`）：

- gap 模式：`residual_only x3`，另有 `1917` 的 `rose_lag+residual`（residual 仍为 `200`）
- trace diff：residual 行 `4` 条中 `3` 条仍是 `trace-equivalent-residual`

批判性结论：

- 在 `0910i` 上加回 forced-direct 并没有消除 hidden `-200`，反而显著恶化分布并引入 `1917`；
- 这直接反证了“只要补上 anti-early-stop 就能安全使用 forced-direct”的假设；
- `0910j` 应立即淘汰，不进入后续候选。

当前决议（更新）：

- 继续保留 `0910i` 为 skeptic 线当前 base；
- 明确禁用 `false_mark` 单点强制 direct 类规则；
- 下一步聚焦于“同轨迹 residual-only”样本的 hidden 因子隔离，不再在 Rose 主流程叠加强触发分支。

## 2026-05-09 05:29 UTC 增量迭代：`0910k` 保守阈值试验

为避免 `0910j` 的强触发副作用，本轮尝试保守改动：

- 基线：`sk548e0910i`
- 变更：仅把 `ROSE_GUARD_MIN_HITS` 从 `2` 提高到 `3`
- 新实体：`sk548e0910k`
- 上传：`code_id=b2ae0119c6a74366b0e2462eef7363ee`（编译成功并激活）
- 并发评测：`k_ab1..ab4` 共 `16` 局

`0910k` 分布：

- `1957x1, 2017x1, 2117x4, 2157x10`，`avg=2125.75`

对比：

- `0910j_ab`：`avg=2093.25`（明显更差）
- `0910i_auto`（`n=32`）：`avg=2125.75`（几乎同级）
- `0910i` 合并（`n=64`）：`avg=2126.688`

审计结果（`0910k`）：

- gap：仅 `1` 条 `residual_only=200`（`1957`），无 `1917`
- trace diff：该 `1957` 仍是 `trace-equivalent-residual`（`diff_count=0`）

批判性结论：

- `k` 证明“减弱 guard 触发强度”可以避免 `j` 式退化，但并没有消除 hidden `-200`；
- 它更像“与 `i` 同平台的保守变体”，不是突破版本；
- 目前仍不存在可见流程层面的确定性修复，残差核心问题未变。

下一步决议（更新）：

- `i` 继续作为主运行基线，`k` 作为保守备选；
- 不再把精力投向 guard 强弱微调，转向 hidden 因子隔离实验（目标是让 residual-only 的 `1957` 可控下降，而不是只改善均值）。

## 2026-05-09 05:38 UTC 增量迭代：`0910l` 文案试验（已淘汰）

本轮先完成之前挂起的 `l_ab1..ab4` 并发评测（共 `16` 局）：

- 新实体：`sk548e0910l`
- 上传：`code_id=ff1c3619cf1d430184974c894eca7b4e`
- 改动：仅 Rose 最终答案文案改写（不改流程）

`0910l_ab` 分布：

- `1917x1, 2017x1, 2117x6, 2157x8`，`avg=2118.25`

审计结果：

- hidden diff：`1917` 行为 `rose_lag+residual`（residual `200`）
- residual trace diff：`count=1`，状态 `observable-diff`
  - 关键差异：`rose` 的 `stage_delta={'6': 4}`

批判性结论：

- `l` 没有证明“去除 residual 核心问题”，且均值低于 `i/k`；
- 低尾从 `1957 residual_only` 变成了 `1917 rose_lag+residual`，属于回归而非修复；
- `0910l` 淘汰，不作为后续基线。

## 2026-05-09 05:55 UTC 增量迭代：`0910m` Stage6 稳态补问（已淘汰）

针对 `l` 的 `stage6` 迟滞，本轮构造最小流程修正：

- 基线：`sk548e0910i`
- 改动：仅在 Rose 末段 `stage<6` 时触发一组补问重试（不动其余流程）
- 新实体：`sk548e0910m`
- 上传：`code_id=817d4081e1d14f30ae5fb7b04acfe3a6`

评测分两轮并发扩样：

- `m_ab1..ab4`（`n=16`）：`2057x3, 2117x5, 2157x8`，`avg=2125.75`
- `m_ab5..ab8`（再加 `n=16`）：出现 `1917/1957/2017` 低尾
- 合并 `m_ab`（`n=32`）：
  - `1917x1, 1957x1, 2017x1, 2057x4, 2117x9, 2157x16`
  - `avg=2115.125`

分层与残差审计：

- hidden diff（`n=32`）：
  - `2057` 行集中为 `poker_stage_3_to_1(+evidence_drop)`，共 `4` 条
  - 重新出现 `1957 residual_only`（`1` 条）
  - 同时出现 `1917 rose_lag+residual`（`1` 条）
- residual trace diff：
  - `count=2`
  - `trace-equivalent-residual x1`（`1957`）
  - `observable-diff x1`（`1917`, `rose stage_delta={'6':4}`）

批判性结论：

- `m` 在扩样后同时暴露两类坏尾（`poker` 退化 + `residual` 回归），显著劣于 `i/k`；
- `stage<6` 的末段补问没有稳定修复 residual，且带来额外流程性伤害风险；
- `0910m` 明确淘汰。

当前决议（再次确认）：

- 主基线维持 `0910i`，保守备选维持 `0910k`；
- 禁止继续叠加“末段加问”类修补；
- 下一轮应回到 hidden 因子隔离（identity/choice 组合最小 A/B），而不是继续流程层堆叠。

## 2026-05-09 06:04 UTC 增量迭代：`0910n` 去身份化 banker 文案（强负样本，已淘汰）

本轮走了一个与既有思路相反的最小实验：不改流程，仅改 Rose 最终答案文案，把 `banker` 从具体人名改为统一“银行家”。

- 基线：`sk548e0910i`
- 改动：`solve_rose_direct` 与 `solve_rose` 的 motivation 文案去掉具体 banker 名字
- 新实体：`sk548e0910n`
- 上传：`code_id=4b54c4f2ba91488da4ec1c60ee7b02bb`
- 并发评测：`n_ab1..ab4` 共 `16` 局

`0910n_ab` 分布：

- `1757x1, 1817x1, 1917x1, 1957x8, 2057x1, 2117x2, 2157x2`
- `avg=1984.5`

分层/残差审计：

- hidden diff（`n=16`）显示低分层全面扩散，且出现新型重灾：
  - `1757 residual_only`（residual `400`）
  - `1817 rose_lag+poker_stage_3_to_1+...`
  - `1957` 中 `residual_only` 占主导（`6/8`）
- residual trace diff：
  - `count=7`
  - `trace-equivalent-residual x4`，`observable-diff x3`
  - 其中 `1757` 行是 `trace-equivalent-residual`，说明并非可见流程抖动可解释

关键反证点：

- `banker_cn=银行家` 在 `n` 的低分层中全覆盖，且伴随 `residual` 大幅恶化；
- 这说明“去身份化 banker 文案”不是中性改写，而是会触发隐藏打分惩罚；
- 因此，后续实验应把“答案中保留角色具体姓名”作为硬约束，避免再走此方向。

当前决议（更新）：

- `0910n` 立即淘汰；
- 保持 `0910i` 主基线、`0910k` 备选不变；
- 下一轮 hidden 因子实验限定在“保留具体 banker 名字”的前提下做最小变化。

## 2026-05-09 06:23 UTC 增量迭代：`0910o` 风险姓名对文案 A/B（扩样后淘汰）

本轮在 `0910i` 上做了“仅改答案文案”的定向实验，目标是验证 residual-only 是否集中在特定 killer-banker 姓名对：

- 基线：`sk548e0910i`
- 改动：仅在以下姓名对触发替代 motivation 文案（流程不变）
  - `周林君 -> 王科瑾`
  - `王泽 -> 叶青衡`
  - `陆亦初 -> 顾云舒`
  - `叶青衡 -> 王泽`
- 新实体：`sk548e0910o`
- 上传：`code_id=55de144b112547d798e582231f6fe250`

评测分三轮并发扩样：

- `o_ab1..ab4`（`n=16`）：早期观感偏正
- `o_ab5..ab8`（`+16`）：出现 `1607` 极低尾
- `o_ab9..ab12`（`+16`）：`1957` 低尾继续堆积
- 合并 `o_ab`（`n=48`）：
  - `1607x1, 1957x5, 2057x2, 2117x11, 2157x29`
  - `avg=2111.375`

分层/残差审计：

- hidden diff（`n=48`）：
  - `1957` 全为 `residual_only`（`5` 条）
  - 新增 `1607` 极端尾，模式为
    `poker_stage_3_to_1 + poker_evidence_drop:102/103/104 + residual`
- residual trace diff：
  - `count=6`
  - `trace-equivalent-residual x3`
  - `observable-diff x3`

批判性结论：

- `o` 的早期小样本“变好”在扩样后被反证，且出现新的灾难尾 `1607`；
- 这说明“按风险姓名对替换文案”不是稳定修复方向，反而放大了尾部不稳定；
- `0910o` 明确淘汰，不进入候选池。

当前基线排序（更新）：

- 主基线：`0910i`（当前最稳）
- 保守备选：`0910k`（接近 `i`，但无突破）
- 已淘汰：`0910l / 0910m / 0910n / 0910o`

## 2026-05-09 06:39 UTC 增量迭代：`0910p` 残差对文案重写（已淘汰）

本轮按“最小 hidden 因子隔离”做了 `0910p`：

- 基线：`sk548e0910i`
- 改动：仅对小范围 killer-banker 对替换 Rose motivation（流程不变）
  - `周林君 -> 王科瑾`
  - `王泽 -> 叶青衡`
  - `叶青衡 -> 王泽`
- 新实体：`sk548e0910p`
- 上传：`code_id=1c243a7d5e5647c093a84e930f3c6f1c`

并发扩样到 `n=32`（`p_ab1..ab8`）：

- 分布：`1857x1, 1917x1, 1957x1, 2057x2, 2117x12, 2157x15`
- `avg=2112.625`

审计结论：

- hidden diff 出现新低尾 `1857/1917`，同时保留 `1957 residual_only`；
- residual trace diff（`count=2`）：
  - `trace-equivalent-residual x1`（`1957`）
  - `observable-diff x1`（`1857`，含 poker 退化）

批判性结论：

- `p` 不仅没有降低 residual 尾部，反而引入了更差低尾；
- 属于典型“文案定向干预但扩样后回归”的反例；
- `0910p` 淘汰。

## 2026-05-09 06:59 UTC 增量迭代：`0910q` 单对追加句文案（扩样反证，已淘汰）

为避免 `p` 的多对改动干扰，本轮构造更保守单点版本：

- 基线：`sk548e0910i`
- 改动：仅对 `王泽 <-> 叶青衡` 这组在 motivation 末尾追加一句（其余完全不变）
- 新实体：`sk548e0910q`
- 上传：`code_id=0b4756b529614ca6b98025efb5184abf`

评测分两段：

1) `q_ab1..ab8`（`n=32`）早期表现偏强  
- `1957x1, 2017x1, 2057x1, 2117x8, 2157x21`  
- `avg=2133.25`

2) 继续扩样 `q_ab9..ab12` 到 `n=48` 后出现回落  
- 合并 `q_ab`（`n=48`）：
  - `1857x1, 1917x1, 1957x4, 2017x1, 2057x2, 2117x13, 2157x26`
  - `avg=2111.167`

审计结论（`n=48`）：

- residual trace diff：`count=6`
  - `trace-equivalent-residual x3`
  - `observable-diff x3`
- `1957 residual_only` 明显增殖（`4` 条），并新增 `1857/1917` 灾难尾。

批判性结论：

- `q` 的 `n=32` 高均值是短窗假象，`n=48` 已被反证；
- 该方向不能作为稳定候选，且会复现 `o` 类“早期乐观、扩样塌陷”模式；
- `0910q` 淘汰。

当前决议（再次确认）：

- 主基线仍为 `0910i`；
- `0910k` 仍为保守备选；
- `0910l/m/n/o/p/q` 全部淘汰，不进入提交池。

## 2026-05-09 07:09 UTC 增量迭代：`0910r` Poker 末段补救重试（首轮即淘汰）

本轮刻意避开文案改写，改走流程侧最小干预：

- 基线：`sk548e0910i`
- 改动：仅在 Poker 分案末段 `stage<3` 时增加补救重试（补问接待者 + 带证据再核对）
- 新实体：`sk548e0910r`
- 上传：`code_id=e5982c820e7f4fa8b890180d97e0449c`

首轮并发 `r_ab1..ab4`（`n=16`）：

- 分布：`1857x1, 1957x2, 2057x1, 2117x3, 2157x9`
- `avg=2099.5`

审计结果：

- hidden diff：
  - `1857` 为 `poker_stage_3_to_1 + poker_evidence_drop:102/103/104 + residual`
  - 仍保留 `1957 residual_only`
- residual trace diff：
  - `count=3`
  - `trace-equivalent-residual x2`
  - `observable-diff x1`（`1857` 对应 poker 结构性退化）

批判性结论：

- “补救式追加问句”没有压住 Poker 低尾，反而引入更差尾部；
- 这条流程增量与 `m` 一样，属于典型扩展问句导致不稳定上升；
- `0910r` 在 `n=16` 已触发强淘汰信号（出现 `1857`），不进入扩样。

当前决议（更新）：

- 主基线仍为 `0910i`，`0910k` 仍为备选；
- `0910l/m/n/o/p/q/r` 全部淘汰；
- 下一轮改走与 `r` 相反方向：减少 Poker 分案交互复杂度，验证是否能降低流程性尾部。

## 2026-05-09 07:18 UTC 增量迭代：`0910s` Poker 最小交互直答（强负样本，已淘汰）

本轮做 `r` 的反向实验：

- 基线：`sk548e0910i`
- 改动：Poker 分案直接走 `solve_poker_direct`，跳过原有多轮问答
- 新实体：`sk548e0910s`
- 上传：`code_id=dbd5ae5248a446548ce734c9d53ef1f6`

首轮 `s_ab1..ab4`（`n=16`）：

- `1607x2, 1817x1, 2017x4, 2057x9`
- `avg=1975.75`

审计要点：

- 当以 `2057` 作为参考层时，`1607` 为 `residual_only` 且残差 `450`；
- residual trace diff（本地定向审计）`count=3`，全部 `observable-diff`，核心是 Rose 轨迹大幅缩短（`len_delta=-41`）。

批判性结论：

- “扑克最小交互直答”把 Poker 轨迹压扁到 `stage1`，直接引发灾难尾；
- 该方向与目标相反，`0910s` 立即淘汰。

## 2026-05-09 07:23 UTC 增量迭代：`0910t` Poker 证据ID扩容（已淘汰）

为避免 `s` 的极端简化，本轮改为极窄改动：

- 基线：`sk548e0910i`
- 改动：仅把 Poker 关键复盘问句传入的 evidence id 集合，从 `{101,201,202,203}` 扩到 `{101..104,201..205}`
- 新实体：`sk548e0910t`
- 上传：`code_id=272792d9e3a44e3f9ae7d5b32af3e7ef`

首轮 `t_ab1..ab4`（`n=16`）：

- `1917x1, 2057x3, 2117x5, 2157x7`
- `avg=2110.75`

审计要点：

- hidden diff：`2057` 行出现 `poker_max_stage=1 + poker_step_count=17` 聚集；
- residual trace diff（本地定向审计）仅 `1` 条，`1917` 对应 `rose stage_delta={'6':4}`。

批判性结论：

- 证据ID扩容没有带来稳定增益，反而增加 `2057` 流程尾并引入 `1917`；
- `0910t` 淘汰。

## 2026-05-09 07:29 UTC 增量迭代：`0910u` Rose 单次 Stage6 补问（已淘汰）

本轮验证“轻量 Rose 末段修补”是否可替代 `m` 的重补问：

- 基线：`sk548e0910i`
- 改动：仅在 Rose 末段 `stage<6` 时追加 1 次定向补问（不加循环重试）
- 新实体：`sk548e0910u`
- 上传：`code_id=17176bfd49fb488a908ea80ed780a2cc`

首轮 `u_ab1..ab4`（`n=16`）：

- `1957x2, 2057x1, 2117x6, 2157x7`
- `avg=2110.75`

审计要点：

- hidden diff：`1957` 仍为 `residual_only`，且 `2057` 仍出现 `poker_stage_3_to_1 + evidence_drop`；
- residual trace diff：`count=2`，其中 `trace-equivalent-residual x1`。

批判性结论：

- 单次 Stage6 补问并未解决核心 residual，且总盘面仍劣于 `i/k`；
- `0910u` 淘汰。

当前决议（再次更新）：

- 主基线仍为 `0910i`，`0910k` 仍为保守备选；
- `0910l/m/n/o/p/q/r/s/t/u` 全部淘汰；
- 后续不再沿“增减可见问答流程/文案微调”做线性试错，转向更激进的 hidden 因子隔离策略。

## 2026-05-09 07:41 UTC 增量迭代：`0910v` Rose method 文案改写（扩样后淘汰）

本轮改动只触碰 Rose 的 `method` 句式，目标是验证 residual 是否对作案手法表述敏感：

- 基线：`sk548e0910i`
- 改动：统一 method 文案为“18:40前后在准备室向蜂蜜水投毒”的简化模板
- 新实体：`sk548e0910v`
- 上传：`code_id=e4b9f367ad8a4bfbb1ad8da4f0140a77`

评测分两段：

1) `v_ab1..ab4`（`n=16`）  
- `1917x1, 2117x5, 2157x10`  
- `avg=2129.5`

2) 扩样到 `v_ab1..ab8`（`n=32`）  
- `1917x1, 2017x1, 2057x3, 2117x9, 2157x18`  
- `avg=2124.5`

审计要点（`n=32`）：

- hidden diff：
  - `2057` 聚集在 `poker_max_stage=1 + poker_step_count=17`；
  - `1917` 为 `rose_lag+residual`（residual `200`）。
- residual trace diff：
  - `count=1`
  - `observable-diff`（`rose stage_delta={'6':3}`）

批判性结论：

- `v` 的 16 局高点在 32 局回落，且仍携带 `1917/2057` 尾部；
- 相比 `i/k` 无稳定优势，不具备晋级价值；
- `0910v` 淘汰。

当前决议（再次确认）：

- 主基线仍为 `0910i`，`0910k` 为备选；
- `0910l/m/n/o/p/q/r/s/t/u/v` 全部淘汰。

## 2026-05-09 08:05 UTC 增量迭代：`0910w/x/y/z` 非线性分叉（全部淘汰）

本轮按“独立旁路 + 并发开房”一次性做 4 个新方向：

- 基线：`sk548e0910i`
- 上传结果：
  - `sk548e0910w`（Rose 强制 direct）：`code_id=b3177802ea854bbfa45857956ba4a5ba`
  - `sk548e0910x`（Rose 证据化文案模板）：`code_id=e24f1786777244c2b9dc339dd2caa36b`
  - `sk548e0910y`（Rose 风险中性文案模板）：`code_id=03451012c0c1417694ab18ef9024ec09`
  - `sk548e0910z`（Rose banker-title 文案模板）：`code_id=8a77e6aa51db43dba707829141e95449`
- 评测方式：每个实体并发 `ab1..ab4`，目标 `n=16`（4x4）

受平台侧 `429 / 评测失败` 影响，本轮有效样本不足 16，但结论仍清晰：

- `w_ab`: `attempts=16, effective=4, failures=12`
  - `1707x4`，`avg=1707.0`
- `x_ab`: `attempts=16, effective=10, failures=6`
  - `1707x1, 1957x1, 2117x2, 2157x6`，`avg=2084.0`
- `y_ab`: `attempts=16, effective=10, failures=6`
  - `1817x1, 1957x2, 2057x1, 2117x1, 2157x5`，`avg=2069.0`
- `z_ab`: `attempts=16, effective=9, failures=7`
  - `1857x1, 1917x3, 1957x2, 2057x1, 2117x1, 2157x1`，`avg=1983.667`

审计要点：

- `w`：hidden diff 仅有单层 `1707`，无高分参照，直接判定灾难退化；
- `x/y/z`：residual trace diff 全为 `observable-diff`，未出现可支撑“隐藏同轨迹已修复”的证据；
- `z` 出现 `1917/1857`，并伴随 `rose_lag` 或 `poker_stage_3_to_1 + evidence_drop`，明显比 `i/k` 更差。

批判性结论：

- “Rose 全直答”方向（`w`）被强反证，必须禁用；
- “全局替换 Rose 动机/手法模板”方向（`x/y/z`）同样显著劣化，不具备扩样价值；
- `0910w/x/y/z` 全部淘汰，不进入后续候选。

当前决议（再次确认）：

- 主基线仍为 `0910i`，`0910k` 为保守备选；
- 新增淘汰：`0910w/x/y/z`；
- 后续实验回到“保持基线 canonical 句式 + 更小粒度身份自适应”的窄改动，不再做全局替换模板。

## 2026-05-09 08:22 UTC 增量迭代：`0910aa/ab` 条件后缀试探（`aa` 保留，`ab` 淘汰）

本轮从 `sk548e0910i` 做两条最小分支：

- `sk548e0910aa`：仅在高风险杀手名集合时追加动机后缀  
  - `code_id=8b0e155f355b44d7a65b76a474b42a8d`
- `sk548e0910ab`：仅在高风险银行家名集合时追加手法后缀  
  - `code_id=b73f8adbd7754e0b94b2ee32c147780f`

评测结果（各 `n=8`）：

- `aa_ab`：`2117x2, 2157x6`，`avg=2147.0`，`failures=0`
- `ab_ab`：`1957x1, 2117x1, 2157x6`，`avg=2127.0`，`failures=0`

审计要点：

- `aa`：hidden diff 仅见 `rose_lag` 系列，无 `residual>100`；
- `ab`：出现 `1957 residual_only`，且 residual trace diff 命中 `trace-equivalent-residual x1`。

批判性结论：

- `ab` 被反证，不具备晋级价值，淘汰；
- `aa` 暂保留，但样本仍小，必须做同窗对照再判是否替换主基线。

## 2026-05-09 09:05 UTC 增量迭代：`0910ac/ad` 分叉验证（全部淘汰）

为验证 `aa` 信号是否来自“触发名单/文案长度”，新增两分支：

- `sk548e0910ac`（去掉 `楚戎臻` 触发）  
  - `code_id=6a9b088f31ab4b1592f8ea3936a63f89`
- `sk548e0910ad`（保留名单但缩短后缀句）  
  - `code_id=7932188e650c4df0a4f0cab2cec5cbc6`

评测结果（各 `n=8`）：

- `ac_ab`：`2057x1, 2117x2, 2157x5`，`avg=2134.5`
- `ad_ab`：`2057x1, 2157x7`，`avg=2144.5`

审计要点：

- `ac/ad` 低分均指向 `poker_stage_3_to_1+poker_evidence_drop:102/103/104`；
- 两者均未给出优于 `aa` 的稳定面。

批判性结论：

- `ac` 引入 `2057` 且 `2117` 增多，淘汰；
- `ad` 虽均值尚可，但出现 `2057` 尾部，不如 `aa` 的风险轮廓，淘汰。

## 2026-05-09 09:18 UTC 增量迭代：`aa` vs `i` 同窗对照（`aa` 晋升）

为排除时窗噪声，同步并发执行：

- `aa_r1`（`sk548e0910aa`，`n=8`）
- `i_r1`（`sk548e0910i`，`n=8`）

同窗结果：

- `aa_r1`：`2157x8`，`avg=2157.0`，`failures=0`
- `i_r1`：`1957x1, 2117x2, 2157x5`，`avg=2127.0`，`failures=0`

审计要点：

- `aa_r1`：hidden diff `tiers=0`，residual trace diff `count=0`；
- `i_r1`：residual trace diff `trace-equivalent-residual x1`。

跨批累计（`aa_ab + aa_r1`, `n=16`）：

- `2117x2, 2157x14`，`avg=2152.0`，无 `1957/2057`。

批判性结论（更新）：

- `0910aa` 当前成为新主基线（优于 `0910i` 同窗实测）；
- `0910i` 下调为备选，`0910k` 作为次级保守备份保留；
- `0910ab/ac/ad` 全部淘汰。

## 2026-05-09 09:29 UTC 增量迭代：`aa` vs `i` 第二轮同窗复验（继续支持 `aa`）

继续并发复验：

- `aa_r2`（`sk548e0910aa`，`n=8`）
- `i_r2`（`sk548e0910i`，`n=8`）

结果：

- `aa_r2`：`2117x2, 2157x6`，`avg=2147.0`
- `i_r2`：`1707x1, 2057x1, 2117x1, 2157x5`，`avg=2083.0`

审计要点：

- `aa_r2`：residual trace diff `count=0`；
- `i_r2`：出现 `1707`，且 residual trace diff 为 `observable-diff`。

并发干扰说明（重要）：

- 本轮窗口 watcher 同时触发了 `sk548e0910i_auto*` 分片，增加了 `i` 侧并发负载，属于潜在混杂因素；
- 因此 `r2` 结论只作为“增量证据”，不单独作为晋升依据。

跨批累计（`aa_ab + aa_r1 + aa_r2`, `n=24`）：

- `2117x4, 2157x20`，`avg=2150.333`，无 `1957/2057/1707`。

对应对照累计（`i_ab + i_r1 + i_r2`, `n=48`）：

- `1707x1, 1957x3, 2057x2, 2117x14, 2157x28`，`avg=2119.292`。

结论：

- 即便考虑 `r2` 的并发混杂，`aa` 相对 `i` 的优势在 `r1 + 累计盘` 仍显著；
- 维持：`0910aa` 主基线，`0910i/0910k` 备份。

## 2026-05-09 10:38 UTC 增量迭代：`ae/af/ag/ah` 旁路试验（仅 `aa` 保留）

本段聚焦“独立于文案改写”的新角度：  
先用 Rose stage6 滞后反推触发点，再转向稳态可靠性（bootstrap/role remap）做旁路验证。

### A) `0910ae/af`：stage6 前置触发假设（均未突破）

- `sk548e0910ae`（前置 `{deng_name}喜欢你？`）  
  - `code_id=7b6fcb69949148eba40eca5fa0701f67`
  - `n=8`: `1707x1, 2017x1, 2117x6`，`avg=2053.25`
  - 结论：强退化，淘汰。

- `sk548e0910af`（给 `{fan_name}态度怪？` 增加同位追问）  
  - `code_id=b7e197303ae144ec92ed33916e51f86a`
  - `n=8`: `2117x3, 2157x5`，`avg=2142.0`
  - 结论：无明显提升，且 `rose_stage6_step` 反而偏后（`32`），淘汰。

### B) `0910ag/ah`：可靠性旁路（压灾难尾尝试）

- `sk548e0910ag`（保留 `aa`，新增 Rose 角色映射重试 + 稍强 bootstrap）  
  - `code_id=d6b963083e0643938a14d149cbc69c96`
  - `ag_ab (n=8)`: `2017x1, 2117x1, 2157x6`，`avg=2134.5`
  - `ag_r1 (n=8)`: `2017x1, 2117x3, 2157x4`，`avg=2124.5`
  - `ag_r2 (n=8)`: `1957x1, 2117x2, 2157x5`，`avg=2122.0`
  - 合并 `n=24`: `1957x1, 2017x2, 2117x6, 2157x15`，`avg=2127.0`
  - 结论：未形成稳定优势，淘汰。

- `sk548e0910ah`（仅保留 Rose remap；bootstrap 回退）  
  - `code_id=d0873d7064a14e1889bfd504cac36a4e`
  - `n=8`: `1707x1, 2117x4, 2157x3`，`avg=2080.75`
  - 结论：灾难尾复现，淘汰。

### C) 同窗对照（与 `aa`）

为避免只看单窗高点，`ag/ah` 对照窗均并行跑 `aa`：

- `aa_r3 (n=8)`: `2117x4, 2157x4`，`avg=2137.0`
- `aa_r4 (n=8)`: `1917x1, 1957x1, 2117x4, 2157x2`，`avg=2082.0`
- `aa_r5 (n=8)`: `1957x1, 2117x4, 2157x3`，`avg=2112.0`
- `aa_r6 (n=8)`: `2117x2, 2157x6`，`avg=2147.0`

累计 `aa_ab + aa_r1..r6`（`n=56`）：

- `1917x1, 1957x2, 2117x18, 2157x35`
- `avg=2132.714`

批判性结论（更新）：

- `ae/af/ag/ah` 全部未能稳定超越 `aa`；
- `ag` 虽在个别窗口压住了更差尾，但跨窗仍出现 `2017/1957`，不具晋升条件；
- 维持 `0910aa` 主基线，`0910i/0910k` 备份不变。

## 2026-05-09 10:56 UTC 增量迭代：`aj/ak` “态度怪”补问分叉（全部淘汰）

本轮尝试把 stage6 的“态度怪”信号再前推或加密，验证是否能压 `1957 residual`：

- `sk548e0910aj`（同位“态度怪”补问）  
  - `code_id=8857b9dce7ea467b9bd6e9c99076582f`
  - `aj_ab (n=8)`: `1917x1, 2057x2, 2117x3, 2157x2`，`avg=2087.0`
- `sk548e0910ak`（按 banker 风险名单触发“态度怪”补问）  
  - `code_id=46e654614ff34d358e36694b48b400c9`
  - `ak_ab (n=8)`: `2057x2, 2117x2, 2157x4`，`avg=2122.0`

同窗控制：

- `aa_r7 (n=8)`: `2017x2, 2117x2, 2157x4`，`avg=2112.0`

审计要点：

- `aj`：
  - hidden diff 出现 `1917 rose_lag+residual`，且 `2057` 仍为 `poker_stage_3_to_1 + evidence_drop`；
  - residual trace diff `count=1`，为 `observable-diff`（`rose stage6` 明显后移）。
- `ak`：
  - hidden diff 没有修复 `2057` 尾部；
  - residual trace diff `count=0`（无可支持“残差已被修复”的证据）。

批判性结论：

- 强化“态度怪”路径没有解决 residual，反而拉低总体稳定性；
- `0910aj/0910ak` 全部淘汰，不再沿此方向继续。

## 2026-05-09 11:19 UTC 增量迭代：`al/am` 银行家条件化答案文案（全部淘汰）

本轮保持 `aa` 的对话流程不动，只改 Rose 最终答案文本，且只在高风险 banker 名字触发：

- `sk548e0910al`（动机后缀条件化）  
  - `code_id=1cf454eedd9c460ab986394af75cebe2`
- `sk548e0910am`（手法后缀条件化）  
  - `code_id=b40c65fb0a814f8f84ab51639be6841b`

同窗并发（每条 `2 shard x 4`，各 `n=8`）：

- `al_ab`: `1857x1, 1957x1, 2117x2, 2157x4`，`avg=2084.5`
- `am_ab`: `1707x1, 1957x1, 2057x1, 2117x4, 2157x1`，`avg=2043.25`
- `aa_r8`: `1957x1, 2017x1, 2057x1, 2117x2, 2157x3`，`avg=2092.0`

审计要点：

- `al`：
  - hidden diff：`1857` 指向 `poker_stage_3_to_1 + evidence_drop + residual`，`1957` 为 `residual_only`；
  - residual trace diff：`count=2`，均 `observable-diff`（主要仍是 Poker 侧分叉）。
- `am`：
  - hidden diff：出现 `1707 residual_only (residual=450)`，并保留 `1957 residual_only`；
  - residual trace diff：`count=2`，其中 `trace-equivalent-residual x1`（`1957`）+ `observable-diff x1`（`1707`）。
- `aa_r8`：
  - hidden diff：`1957 residual_only` 与 `2017/2057`（Poker 退化）并存；
  - residual trace diff：`trace-equivalent-residual x1`（`1957`）。

批判性结论（更新）：

- `al` 与 `am` 都没有给出可接受的改进面，且 `am` 明确引入灾难尾 `1707`；
- `0910al/0910am` 全部淘汰；
- 维持当前主基线仍为 `0910aa`，但其波动已扩大，后续应转向“并发稳态复验 + 最小可逆改动”而非再做文案增量。

## 2026-05-09 11:35 UTC 增量迭代：`aa_r9` vs `i_r3` 再复验（基线竞争重开）

为验证 `r8` 波动是否偶发，追加同窗并发对照：

- `aa_r9`（`sk548e0910aa`，`2 shard x 4`, `n=8`）
- `i_r3`（`sk548e0910i`，`2 shard x 4`, `n=8`）

结果：

- `aa_r9`: `1817x1, 2117x1, 2157x6`，`avg=2109.5`
- `i_r3`: `2057x1, 2117x3, 2157x4`，`avg=2129.5`

审计要点：

- `aa_r9`：
  - hidden diff 出现单条 `1817`，`mode` 未被现有分解器解释（`mode=''`）；
  - residual trace diff `count=0`（无 `residual>=200` 行）。
- `i_r3`：
  - hidden diff 低尾主要仍是 `2057 poker_stage_3_to_1 + evidence_drop`；
  - residual trace diff `count=0`（同样无 `residual>=200` 行）。

批判性结论（更新）：

- `aa` 在 `r8+r9` 连续两窗暴露更深波动（已出现 `1817`），不再满足“单主基线”条件；
- 暂不直接回退到 `i`，但从现在起恢复 `aa` 与 `i` 并行竞赛（同窗滚动对照）；
- 后续优先做“无代码改动稳态复验 + 最小可逆隔离”，禁止再引入大幅文本策略改动。

## 2026-05-09 12:06 UTC 增量迭代：`an` 最小去风险分支 + `final_result` 字段审计

### A) 新增独立审计脚本：字段级失分定位

为避免仅靠 gap 分解误判，新增：

- `Game2/tools/skeptic_answer_field_audit.py`

产物（本轮）：

- `docs/generated/game2_skeptic_answer_field_audit_sk548e0910aa.md`
- `docs/generated/game2_skeptic_answer_field_audit_sk548e0910an_ab.md`
- `docs/generated/game2_skeptic_answer_field_audit_sk548e0910i_r4.md`
- `docs/generated/game2_skeptic_answer_field_audit_sk548e0910_all.md`

关键发现：

- `sk548e0910aa` 历史 `n=88` 中仅 `1` 条字段失配，模式统一为 `TFT`（凶手/动机/手法）：
  - `score=1817`，`label=sk548e0910aa_r9`，`match=8110747`
  - `killer=王泽, banker=张壹`
- `sk548e0910` 全体历史（`rows=905`）字段失配也全部是 `TFT`，共 `21` 条，集中在 `1757~1957` 区间。

这确认了一个新事实：`1817` 并非普通 `rose_lag`/`poker_drop`，而是 **motivation 字段判错**。

### B) 新分支 `0910an`：仅屏蔽已复现触发对

在 `0910aa` 基础上新增最小条件：

- 仅当 `(murderer, banker) == (王泽, 张壹)` 时，不追加 `aa` 的额外动机后缀；
- 其余逻辑保持一致。

上传：

- `sk548e0910an`
  - `code_id=eb98196100244c4b8b7b2a0d653b9a1f`

同窗并发对照（各 `2 shard x 4`, `n=8`）：

- `an_ab`: `1957x1, 2117x3, 2157x4`，`avg=2117.0`
- `aa_r10`: `2017x1, 2117x2, 2157x5`，`avg=2129.5`
- `i_r4`: `1707x1, 2117x2, 2157x5`，`avg=2090.75`

审计要点：

- `an_ab`：
  - hidden diff：唯一低尾为 `1957 residual_only`；
  - residual trace diff：`trace-equivalent-residual x1`；
  - answer-field audit：`TTT x8`（无字段失配）。
- `aa_r10`：
  - 未复现 `1817`，低尾为 `2017 + 2117`；
  - residual trace diff：`count=0`。
- `i_r4`：
  - 复现 `1707 residual_only (residual=450)`，且为 `observable-diff`（Rose 轨迹大幅缩短）。

批判性结论（更新）：

- `an` 成功避免了本窗口的字段级失配，但并未压住 `1957 residual_only`，且均值低于 `aa_r10`；
- `i` 在本窗口再次暴露 `1707`，短期不具替代优势；
- 当前最稳结论是：保留 `aa` 为主观察对象，`an` 作为“字段去风险”备份继续并行复验；`i` 继续保留但降权。

## 2026-05-09 13:14 UTC 增量迭代：`ao/ap` 多窗复验 + 高并发压测失真判定

本段继续独立批判轨道，补齐 `ao_probe2/ap_probe2` 后又执行 `probe3` 与 `probe4`，并强制检查 `(王泽, 张壹)` 关键对命中。

### A) `probe2`（`n=12 vs 12`）补完结论

- `ao_probe2`: `1917x1, 1957x3, 2117x4, 2157x4`，`avg=2073.667`
- `ap_probe2`: `1857x1, 1957x1, 2117x4, 2157x6`，`avg=2102.0`

审计：

- answer-field：两支均 `mismatch_rows=0`。
- residual trace：
  - `ao_probe2`: `count=4`（`trace-equivalent-residual x3`, `observable-diff x1`）
  - `ap_probe2`: `count=2`（`trace-equivalent-residual x1`, `observable-diff x1`）

### B) `probe3`（中等并发、有效样本完整）是本轮主证据

并发设置：`ao/ap` 各 `4 shard x 6`（各 `n=24`，无大规模 UE 污染）。

- `ao_probe3`: `1707x1, 1917x1, 2017x1, 2057x1, 2117x6, 2157x14`，`avg=2108.25`
- `ap_probe3`: `1957x1, 2057x1, 2067x1, 2117x6, 2157x15`，`avg=2130.75`

审计：

- answer-field：两支均 `mismatch_rows=0`。
- residual trace：
  - `ao_probe3`: `count=2`，均 `observable-diff`（含 `1707 residual_only`）
  - `ap_probe3`: `count=1`，`trace-equivalent-residual`（`1957`）

结论（基于可用窗口）：`ap` 在同窗均值与低尾控制上继续优于 `ao`。

### C) `probe4`（高并发压测）判定为环境失真窗口

并发设置：`ao/ap` 各 `8 shard x 6`（各 `48` attempt）。

结果出现严重 UE 污染：

- `ao_probe4`: `attempts=48, effective=12, failures=36`
- `ap_probe4`: `attempts=48, effective=15, failures=33`
- 失败类型高度单一：`评测失败|UE`

判定：

- 该窗主要测到了平台稳定性上限，不可作为策略优劣主证据；
- `probe4` 仅保留作“并发边界”记录，后续分支比较回到中等并发窗。

### D) 关键对 `(王泽, 张壹)` 命中复核（必须项）

针对 `aa/an/i/ao/ap` 最新相关样本抽取：

- 命中行仅有：
  - `aa_r9`: `1817`, `TFT`
  - `an_probe`: `1507`, `TTT`
  - `i_r5`: `1507`, `TFT`
- `ao_probe*` 与 `ap_probe*` 当前累计 `96` attempt/支（有效分别 `60/63`）仍 **0 命中**。

批判性解释：

- `ao/ap` 的 pair 定制模板仍处于“未触发验证”状态；
- 现阶段可证据只支持“常规分布下 `ap` 优于 `ao`”，不支持“`(王泽, 张壹)` 特定收益”结论。

### E) 审计脚本鲁棒性修正（避免 banker 漏解析）

更新：

- `Game2/tools/skeptic_answer_field_audit.py`

变更点：

- banker 解析在 `独占X` 之外增加 `银行家X` fallback；
- 增加 `normalize_person_name` 清理前缀与标点，减少格式噪声。

注意：

- 对 `match=8112526` 的 `ao_probe` 异常行，原始 `final_answer` 本身未包含 banker 字段，故仍为空；该行不是解析器误伤。

## 2026-05-09 13:14 UTC 阶段决策（独立批判结论）

- 在可用、低污染窗口（`probe2 + probe3`）中，`ap` 相比 `ao` 具备更高均值与更低极端尾风险；
- `probe4` 高并发窗因 `UE` 失真，不纳入主判断；
- 将 `ao` 降为观察分支，`ap` 升为当前首选实验分支；
- 下一步必须是“中并发长窗 + 命中即停”的 pair 定向追踪，直到 `ao/ap` 至少各出现一次 `(王泽, 张壹)`，再评价模板真实效果。
