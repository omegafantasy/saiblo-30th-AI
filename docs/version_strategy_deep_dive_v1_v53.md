# 蚁洋陷役2 C++ AI 版本思路全量梳理（v1-v62）

更新时间：2026-03-04（UTC）

数据口径：

- 生产 Elo：`/www/autolab/runtime/latest.json`（`eval_20260304_100237`，1008 局）
- 迭代 Elo：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_101631`，500 局）
- 迭代日志主文档：`/www/docs/round2_autolab_and_iterations.md`

判读原则：

- 生产 Elo 为最终口径；iter Elo 只用于候选筛选。
- 当前生产 gauntlet 存在 champion 依赖，`cpp_v1_current` 与 `cpp_v2_beam` 在不同轮次会翻转，不应只看单轮绝对值。

## 全局诊断（先给结论）

1. v2-v6 是当前真正的“强度主干”，v1/v1_baseline/v6/v5/v4/v3 长期占生产前列。
2. v7-v21 是“模式与反 beam”大分支，产生了若干有效中间成果（v8/v15/v17/v18/v21），但总体未超过 v1-v6 主干。
3. v22-v33 是“持续压制/回弹/过渡保护”试验群，表现分化明显，只有少数版本进入中游上半区。
4. v34-v43 是 guardrail/cap 微分化分支，主要在修复特定退化；v40 相对最成功。
5. v44-v50 主要围绕 v9/v10/v19/v27 的局部冲突做手术，存在明显“修一处坏一处”的迁移效应；v45/v47 有一定生产价值，v50 为中游可用。
6. v51 当前是 v50 的源码拷贝，未注册、未编译、未评测，属于“无实质增量版本”。
7. v52-v53 的对照实验表明：创新方向要“保底回退”，直接替换稳态估值会导致大幅回归（v52），而在 v1 内核上叠加轻量对手惩罚可显著提升（v53）。
8. v54 在 CPU 时间硬截止约束下实现了可复现 gate：对 `v1/v2` 各 120 局均为 62.5%，但对 `v53` 为 45.8%，属于“有定向提升但未成为新主干”。
9. v55 引入 dual-mode overlay 剪枝后，对 `v2` 维持正优势，但对 `v53` 100 局仅 43%，总体仍是退化分支。

## 分支级回顾（较新迭代在做什么）

### 1) v40-v44：从“全局收紧”转向“定向限幅”

- 核心目标：避免早期 anti-beam 改动对非目标对局造成全局副作用。
- 方法：把 v6/v19 等风险通道从“一刀切”改成分通道 cap、白名单和 floor 门控。
- 结果：v40 在生产中是该簇最稳版本之一；但 v41-v44 为修补链条，收益波动大。

### 2) v45-v50：处理 v10/v19/v27 三方冲突

- 核心目标：同时保住 v10 反制、v19 壳层安全和 v27 中压保活。
- 方法：互斥、混合抑制、分段 blend、backstop、软硬滞回等策略组合。
- 结果：iter 里 v50 可拿到第一，但生产最新仅 rank#18，说明偏向“对特定对手池有效”，泛化不足。
- 定向复核（`eval_20260304_052738`，每版对 `v1` 120 局）：`v45/v48/v49` 显著弱于 `v1`，`v46/v47/v50` 仅与 `v1` 持平，无版本显著强于 `v1`。

### 3) v51：未落地闭环

- 代码层面：`sha256(v51)==sha256(v50)`，无任何逻辑差异。
- 资产层面：无可执行文件、无 registry 条目、无评测产物。
- 判定：当前应视作无意义迭代（仅目录占位）。

### 4) v52-v55：结构创新的成败分水岭

- v52：尝试“宏观估值 + 轻量 minimax”直接接管决策，结果 26/100 明显回归。
- v53：回到 v1 稳态打分，仅加“候选池 + 敌方一手惩罚 + 回退保护”，双 seed 合计 127/200（63.5%）显著强于 v1。
- v54：在 v53 上加入 CPU 计时硬截止、自适应候选池与提前停止；gate 显示其对 `v1/v2` 有效，但仍落后 `v53`。
- v55：进一步加了 dual-mode overlay 启用门与换招惩罚剪枝；对 `v53` 关键对位依旧失败（43/100）。
- 经验：创新必须建立在可回退的稳态内核上，并同时控制复杂度与搜索预算。

## 逐版本思路分析（v1-v59）

### v1（`cpp_v1_current` / `cpp_v1_r2_baseline`）

- 设计目标：建立稳健、可长跑的强基线，优先保证通用对局稳定性。
- 关键机制：以成熟启发式和稳妥动作选择为主，避免激进高方差规划。
- 生产表现：`cpp_v1_current` rank#1（1669.39）；`cpp_v1_r2_baseline` rank#2（1638.21）。
- 结论：当前生产最强主干之一；后续版本应以“显著超越 v1/v1_baseline”为硬门槛。

### v2（`cpp_v2_beam`）

- 设计目标：把单步贪心升级为多步序列规划，提升中盘主动进攻能力。
- 关键机制：beam 序列搜索 + 局面估值（兵力/经济/主将安全/距离）组合。
- 生产表现：rank#14（1548.57），但与 v1 在生产轮次中有明显互克并触发 champion 翻转。
- 结论：战术上有价值，但全局稳健性不足，容易在非目标局面产生偏置。

### v3（`cpp_v3_hybrid`）

- 设计目标：抑制纯 beam 的过拟合倾向，提升策略稳健性。
- 关键机制：beam 与 greedy 并行生成，按仿真收益仲裁。
- 生产表现：rank#6（1588.55）。
- 结论：是“强中盘 + 稳健”的有效折中版本，泛化优于 v2。

### v4（`cpp_v4_counterfactual`）

- 设计目标：把敌方响应近似真正接入决策，修复单边高估问题。
- 关键机制：反事实首步规划 + optimistic/pessimistic 稳健评分融合。
- 生产表现：rank#5（1590.88）。
- 结论：是后续 counterfactual 分支的关键里程碑，证明“首步稳健化”有效。

### v5（`cpp_v5_counterfactual_2ply`）

- 设计目标：从“首步反事实”扩展到“选择性 2-ply”以提升战术交换质量。
- 关键机制：对 top-k 首步评估二步跟进，并加入过度进攻刹车。
- 生产表现：rank#4（1594.32）。
- 结论：显著有效，属于高价值祖先版本。

### v6（`cpp_v6_adaptive_2ply`）

- 设计目标：降低 2-ply 固定宽度的算力浪费与估值偏差。
- 关键机制：自适应 2-ply 宽度 + 主将邻域破口评估。
- 生产表现：rank#3（1594.62）。
- 结论：当前“规划分支”最稳定核心之一。

### v7（`cpp_v7_mode_switch`）

- 设计目标：引入攻防模式切换，按局势动态调整策略。
- 关键机制：mode-aware 评分与规划仲裁。
- 生产表现：rank#28（1522.13）。
- 结论：方向正确但切换噪声较大，未形成稳定收益。

### v8（`cpp_v8_mode_hysteresis`）

- 设计目标：减少 v7 模式抖动和频繁误切换。
- 关键机制：模式滞回 + offense safety gate。
- 生产表现：rank#10（1555.06）。
- 结论：是 mode 系列里第一个稳定收益版本。

### v9（`cpp_v9_emergency_antibeam`）

- 设计目标：针对 beam-like 压制局面提供紧急防守切换。
- 关键机制：ring/chain 压力特征 + emergency defense trigger。
- 生产表现：rank#31（1512.59）。
- 结论：局部有效但副作用重，容易过防守。

### v10（`cpp_v10_antibeam_gate_release`）

- 设计目标：修复 v9 过度防守，恢复常态局面的进攻流动性。
- 关键机制：adaptive anti-beam gate + defense release hysteresis。
- 生产表现：rank#30（1515.47）。
- 结论：比 v9 更平衡，但仍未解决“泛化与针对性冲突”。

### v11（`cpp_v11_dualgate_release_confirm`）

- 设计目标：增加释放确认，抑制 defense/balanced 来回抖动。
- 关键机制：dual-gate 信号 + 2 回合 release confirm。
- 生产表现：rank#44（1479.67）。
- 结论：确认机制过重，导致节奏损失。

### v12（`cpp_v12_segmented_gate_cooldown`）

- 设计目标：改进 v11 的僵硬确认，增加冷却和分段门控。
- 关键机制：segmented gate + defense reentry cooldown。
- 生产表现：rank#36（1503.37）。
- 结论：较 v11 回升，但仍不足以回到上游。

### v13（`cpp_v13_beamlike_smoothgate`）

- 设计目标：将反 beam 告警从硬阈值改为连续平滑信号。
- 关键机制：三段 initiative gate + beam-like adaptive alert。
- 生产表现：rank#21（1539.70）。
- 结论：平滑化方向有效，属于中游可用版本。

### v14（`cpp_v14_chainjump_reentry_guard`）

- 设计目标：抑制 chain/jump 场景下的误释放回切。
- 关键机制：chain-jump hysteresis memory + rollback guard。
- 生产表现：rank#26（1526.98）。
- 结论：修复了部分回切问题，但整体增益有限。

### v15（`cpp_v15_tempo_filtered_chainjump`）

- 设计目标：在链式防守中恢复中压反击节奏。
- 关键机制：tempo-filtered chainjump defense + mid-pressure recovery。
- 生产表现：rank#7（1581.40）。
- 结论：该分支高点之一，具备较强实战价值。

### v16（`cpp_v16_fastcut_dual_channel`）

- 设计目标：快速切断高风险分支，同时保留双通道规划灵活度。
- 关键机制：fast-cut bypass + dual-channel planner bias。
- 生产表现：rank#23（1538.13）。
- 结论：策略可解释性提升，但稳定收益一般。

### v17（`cpp_v17_family_state_exchange_guard`）

- 设计目标：把状态机记忆和首步交换安全结合，减少冒进首手。
- 关键机制：family-state hysteresis + first-step exchange guard。
- 生产表现：rank#8（1563.17）。
- 结论：兼顾稳健与进攻，属于较成功中上游版本。

### v18（`cpp_v18_conditional_exchange_rebound`）

- 设计目标：在释放后快速恢复可反击能力。
- 关键机制：conditional exchange guard + post-release rebound window。
- 生产表现：rank#9（1555.06）。
- 结论：与 v17 同属“可用稳健分支”，但峰值略低。

### v19（`cpp_v19_rebound_shellfloor_guard`）

- 设计目标：防止反弹阶段壳层防守塌陷。
- 关键机制：rebound suppression gate + shell safety floor hard reject。
- 生产表现：rank#15（1546.49）。
- 结论：是后续 v40+ 与 v45+ 分支反复借鉴的关键组件。

### v20（`cpp_v20_duallayer_counterlane`）

- 设计目标：把壳层门控与反制通道分层，减少互相牵制。
- 关键机制：dual-layer shell gate + conditional counter-relief lane。
- 生产表现：rank#22（1539.04）。
- 结论：结构更清晰，但净收益中等。

### v21（`cpp_v21_beamharden_whitelist`）

- 设计目标：对 beam 风险做强硬收敛，同时给白名单局面留出口。
- 关键机制：beam-hardening tighten + whitelist relief。
- 生产表现：rank#11（1553.58）。
- 结论：是反 beam 分支中比较平衡的一版。

### v22（`cpp_v22_burst_harden_dynamic_relief`）

- 设计目标：在爆发期动态增强防守并连续调整反制松弛。
- 关键机制：burst-triggered hardening + continuous relief weighting。
- 生产表现：rank#51（1444.67）。
- 结论：动态权重副作用大，出现明显退化。

### v23（`cpp_v23_sustainfloor_tempo_decay`）

- 设计目标：让持续压制下防守底线更稳，同时控制节奏衰减。
- 关键机制：sustain floor + low-jump tempo-decay。
- 生产表现：rank#24（1537.39）。
- 结论：中游可用，主要价值在“底线稳定”。

### v24（`cpp_v24_guarded_additive_sustain`）

- 设计目标：叠加持续防守增益并保持白名单衰减保护。
- 关键机制：additive sustain + guarded decay floor。
- 生产表现：rank#47（1467.90）。
- 结论：增益叠加过度，策略变钝。

### v25（`cpp_v25_floorplus_transition_guard`）

- 设计目标：强化防守 floor，并防止状态切换时暴露窗口。
- 关键机制：persistent hardening floor + transition protection。
- 生产表现：rank#50（1449.85）。
- 结论：过保守，导致输出能力不足。

### v26（`cpp_v26_pulse_harden_safety_delta`）

- 设计目标：用脉冲式增强替代常驻重防守，恢复节奏。
- 关键机制：dual-jump pulse hardening + safety-delta transition bonus。
- 生产表现：rank#20（1540.27）。
- 结论：相对 v24/v25 明显回暖，具备可复用性。

### v27（`cpp_v27_midpressure_counterlane`）

- 设计目标：在非 beam 的中压场景提高反制效率。
- 关键机制：non-beam relax + midpressure counter lane bonus。
- 生产表现：rank#27（1526.39）。
- 结论：有定向价值，但泛化不足，后续衍生出 v47-v50 系列。

### v28（`cpp_v28_v6lane_rebound_guard`）

- 设计目标：保护 v6 型 2-ply 通道并增强高压反弹守护。
- 关键机制：v6 lane bonus + high-pressure counterline guard。
- 生产表现：rank#42（1492.13）。
- 结论：对目标对手有效，但整体回报偏低。

### v29（`cpp_v29_layered_counterline_rebound`）

- 设计目标：进一步层化 counterline 并兼顾 v19 回弹。
- 关键机制：layered counterline + v19 rebound lane。
- 生产表现：rank#17（1543.32）。
- 结论：该阶段较成功版本，结构清晰且可解释。

### v30（`cpp_v30_v2burst_guarded_transition`）

- 设计目标：抑制 v2 型爆发并保持转换期安全。
- 关键机制：v2 burst suppression + guarded transition floor。
- 生产表现：rank#41（1495.56）。
- 结论：抑制有效但损失普适进攻能力。

### v31（`cpp_v31_dualcore_release_rebalance`）

- 设计目标：在收窄 v2 门控后重平衡双核心转换通道。
- 关键机制：narrow v2 gate + dual-core transition + v6 min release floor。
- 生产表现：rank#48（1467.03）。
- 结论：复杂度增加但收益不成正比。

### v32（`cpp_v32_v29_narrow_v2burst`）

- 设计目标：基于 v29 做单变量实验，确认 v2 burst 门控影响。
- 关键机制：narrow v2 burst gating（单变量）。
- 生产表现：rank#35（1503.39）。
- 结论：验证价值大于实战价值。

### v33（`cpp_v33_v32_hardline_recovery_lane`）

- 设计目标：弥补 v32 对非 v2 场景的伤害。
- 关键机制：hardline recovery lane outside narrow v2 burst。
- 生产表现：rank#25（1537.20）。
- 结论：成功回收一部分通用对局强度。

### v34（`cpp_v34_split_pulse_recovery`）

- 设计目标：将 pulse 与稳定恢复通道分拆，减小冲突。
- 关键机制：split pulse/stable recovery lanes。
- 生产表现：rank#19（1540.85）。
- 结论：是后续 guardrail 系列的重要基底。

### v35（`cpp_v35_midpulse_guardrail`）

- 设计目标：在 v34 上叠加 v1 防护栏与中脉冲 lane。
- 关键机制：v1 guardrail + hardline mid-pulse lane。
- 生产表现：rank#34（1503.89）。
- 结论：叠加后出现牵制，净收益有限。

### v36（`cpp_v36_v34_guardrail_only`）

- 设计目标：拆解 v35，验证“仅 guardrail”单变量效果。
- 关键机制：v34 + guardrail only。
- 生产表现：rank#40（1497.23）。
- 结论：说明 v35 问题不只来自 mid-pulse，也有 guardrail 参数错配。

### v37（`cpp_v37_v34_narrow_guardrail`）

- 设计目标：收窄 guardrail 激活区间，减少误触发。
- 关键机制：low-jump/low-hardening narrow guardrail。
- 生产表现：rank#32（1508.44）。
- 结论：比 v36 好，但仍是中低位。

### v38（`cpp_v38_v37_segmented_guardrail_release`）

- 设计目标：把 guardrail 释放逻辑做分段，避免二值开关问题。
- 关键机制：segmented guardrail release lane。
- 生产表现：rank#29（1518.64）。
- 结论：分段释放有效，后续成为 v39/v40 基底。

### v39（`cpp_v39_v38_release_protect_v6v19`）

- 设计目标：释放窗口中保护 v6/v19 关键通道不被过度压制。
- 关键机制：release protect window + tight shell。
- 生产表现：rank#37（1500.79）。
- 结论：有保护作用，但对非目标局面副作用仍在。

### v40（`cpp_v40_v38_targeted_v6v19_cap`）

- 设计目标：把全局收紧改成风险窗口内的定向限幅。
- 关键机制：targeted cap for v6/v19 bonus channels。
- 生产表现：rank#16（1543.72）。
- 结论：v34-v43 簇中最成功版本之一。

### v41（`cpp_v41_v40_split_cap_whitelist`）

- 设计目标：继续拆分 v6/v19 cap，并给 v1/v2 设置白名单缓冲。
- 关键机制：split cap gates + whitelist。
- 生产表现：rank#49（1465.81）。
- 结论：分拆后参数耦合失衡，出现明显退化。

### v42（`cpp_v42_v40_midpressure_floor`）

- 设计目标：修复 v41 退化，给中压/转换通道加保底。
- 关键机制：midpressure/transition safeguard floors。
- 生产表现：rank#38（1499.74）。
- 结论：回暖有限，仍在中低位。

### v43（`cpp_v43_v42_v6_priority_floor_gate`）

- 设计目标：当 v6 风险高时下调中压 floor，避免误加压。
- 关键机制：v6 priority gate to downscale floors。
- 生产表现：rank#45（1478.61）。
- 结论：规则偏硬，牺牲了通用进攻效率。

### v44（`cpp_v44_v43_v9restore_v19shellfloor`）

- 设计目标：恢复 v9 反 beam 能力并保护 v19 壳层，且与 rebound 解耦。
- 关键机制：v9 restore window + v19 shellfloor de-couple。
- 生产表现：rank#46（1477.83）。
- 结论：修补方向明确，但整体收益仍低。

### v45（`cpp_v45_v44_v10counter_transition_guard`）

- 设计目标：加入 v10 反制恢复，并约束 v1/v5 转换风险。
- 关键机制：v10 counter-restore gate + transition guard。
- 生产表现：rank#13（1552.08）；近 20 轮平均 rank 约 15。
- 结论：是 v44-v50 簇中较成功版本。

### v46（`cpp_v46_v45_hysteresis_softhard_shell`）

- 设计目标：给 v10 反制去抖，并拆分 v19 壳层软/硬松弛。
- 关键机制：counter hysteresis + soft/hard shell relaxation。
- 生产表现：rank#43（1489.96）；近 20 轮平均 rank 约 37.5。
- 结论：复杂机制引入了新的节奏损失。

### v47（`cpp_v47_v46_v27_safeguard_mutex`）

- 设计目标：利用 v27 保活 floor 修复中压崩盘，并处理与 v10 冲突。
- 关键机制：v27 safeguard floors + v10 mutex whitelist。
- 生产表现：rank#12（1552.93）；近 20 轮平均 rank 约 15.5。
- 结论：与 v45 一样属于后期簇的有效版本。

### v48（`cpp_v48_v47_v27continuous_mutexhyst`）

- 设计目标：把 v27 保活从二值改为连续强度，并加互斥时序阈值。
- 关键机制：continuous safeguard strength + mutex hysteresis。
- 生产表现：rank#33（1505.86）；近 20 轮平均 rank 约 39.5。
- 结论：连续化后调控空间变大，但参数未稳定。

### v49（`cpp_v49_v48_v27dualfloor_mutexblend`）

- 设计目标：将 v27 floor 拆双通道，并把 v10 互斥改为部分抑制。
- 关键机制：dual-channel floor + mutex blend。
- 生产表现：rank#39（1497.35）；近 20 轮平均 rank 约 27。
- 结论：修复 v27 的同时牺牲了 v10/v19/v6 相关对位，迁移退化明显。

### v50（`cpp_v50_v49_v19backstop_pieceblend`）

- 设计目标：保留 v27 修复收益，同时补回 v19 与 v10。
- 关键机制：piecewise blend + v19 protect backstop。
- 生产表现：rank#18（1541.26）；近 20 轮平均 rank 约 19.9。
- 结论：相较 v49 回升明显，但仍未进入生产前十，属于“可用但未破局”。

### v51（`/www/ai_cpp/v51/ai_v51.cpp`）

- 设计目标：当前无明确设计记录。
- 关键机制：与 v50 源码完全一致（`sha256` 相同）。
- 评测状态：未注册、无可执行文件、无评测结果。
- 结论：当前是无意义迭代占位；应先补差异设计再进入评测链。

### v52（`cpp_v52_robust_minimax_lane`）

- 设计目标：做一次“根本级”替换，把贪心动作改成宏观稳健搜索。
- 关键机制：候选池 + 一步敌方应手 + 宏观局面值（兵力/占格/前线/中心/主将安全）。
- 评测证据：`eval_20260304_054223`，对 `v1` 100 局仅 `26/100`。
- 结论标签：`regression`。问题不在“有无搜索”，而在宏观估值与真实战术收益错位，导致系统性误判。

### v53（`cpp_v53_overlay_countercheck`）

- 设计目标：保留 v1 稳定内核，同时引入有限对手应手修正，避免过拟合与估值漂移。
- 关键机制：`v1` 原打分不动；动作层做候选池与敌方一手惩罚；不显著更优时回退基线动作。
- 评测证据：
  - `eval_20260304_054626`：`64/100`（seed=20260306）
  - `eval_20260304_054848`：`63/100`（seed=20260307）
  - 合并：`127/200`（63.5%，95% CI `[56.63%, 69.86%]`，p=`0.000164`）
  - 多对手 smoke `eval_20260304_055621`（每对手 20 局）：对 `v1/v2/v5/v6/v40/v47/v50` 均为正胜率（60%~85%）
- 结论标签：`promising`。该方向证明“稳态内核 + 可回退创新”是有效范式。

### v54（`cpp_v54_overlay_adaptive_timeout`）

- 设计假设：在保留 v53 稳态收益的前提下，通过自适应候选扩展与提前停止提升对 `v1/v2` 的稳健压制，并以 CPU 计时硬截止保证单步上限。
- 关键机制：
  - 截止口径升级为 `CLOCK_THREAD_CPUTIME_ID`（`<=200ms`）+ 超时回退当前最优候选；
  - 候选池宽度按局势自适应（主将压力/阶段/距离/机动）；
  - 引入 top1-top2 分差触发的提前停止；
  - 修正敌方应手评估中的主将定位（按 player 动态定位主将坐标）。
- 评测证据：
  - iter gate：`eval_20260304_072425`（每关键对手 120 局，合计 360 局）
  - vs `v1`: `75/120`（62.5%）
  - vs `v2`: `75/120`（62.5%）
  - vs `v53`: `55/120`（45.8%）
  - 生产单轮 gauntlet（`eval_20260304_072325`）：`v54` Elo `1545.17`，低于 `v53` `1570.73`。
- 结论标签：`neutral`。对 `v1/v2` 有提升信号，但未超过 `v53`，尚不能作为主线替代版本。

### v55（`cpp_v55_overlay_dualmode_prune`）

- 设计假设：通过“高压激活 / 平稳收敛”的 dual-mode overlay，减少 v54 的无效换招与计算开销，同时改善对 `v53` 对位。
- 关键机制：
  - 延续 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与回退；
  - 新增 overlay 启用门（高置信 base 直接跳过 overlay）；
  - 平稳态增加 switch penalty 与更高切换门槛，高压态提高敌方应手权重；
  - 候选生成时按 `player` 动态识别敌主将位置。
- 评测证据：
  - iter gate：`eval_20260304_074045`（每关键对手 100 局，合计 300 局）
  - vs `v1`: `56/100`（56.0%）
  - vs `v2`: `61/100`（61.0%）
  - vs `v53`: `43/100`（43.0%）
- 结论标签：`regression`。虽然对 `v2` 仍有优势信号，但关键目标 `v53` 对位明显退化，未达到主线替代条件。

### v56（`cpp_v56_overlay_baseanchor_prune`）

- 设计假设：`v55` 对 `v53` 退化的核心原因是 overlay 在平稳局面仍过度偏离高价值 base 动作；通过“贴近 base 的正则 + 原始跌幅硬剪枝”收敛无效探索，可在保持 `v1/v2` 优势的同时修复关键对位。
- 关键机制：
  - 延续 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与超时回退；
  - 新增 `base_anchor_penalty`：按候选相对 base 的 `raw_drop` 施加惩罚，抑制高代价换招；
  - 新增 `max_raw_drop`：对跌幅过大候选直接剪枝，平稳态阈值更紧，高压态适度放宽；
  - 保留 dual-mode + early-stop 结构，优先把预算集中在“接近 base 且具战术价值”的分支。
- 评测证据：
  - iter gate：`eval_20260304_080032`（每关键对手 100 局，合计 300 局）
  - vs `v1`: `57/100`（57.0%）
  - vs `v2`: `63/100`（63.0%）
  - vs `v53`: `45/100`（45.0%）
  - iter confirm（关键对手复验）：`eval_20260304_080942`（`v56 vs v53`，`200` 局）
  - vs `v53`: `74/200`（37.0%）
- 生产口径现状：`eval_20260304_075323` 的生产池尚未纳入 `v56`，当前无生产 Elo 证据可用于晋升判断。
- 结论标签：`regression`。虽然对 `v1/v2` 有优势信号，但在 `>=200` 局 confirm 中对 `v53` 明确退化，不能作为主线替代。

### v57（`cpp_v57_overlay_tactical_escape`）

- 设计假设：`v56` 的退化仍可能来自关键战术分支被过早剪枝；通过“战术逃逸候选”机制，仅对高价值战术候选放宽剪枝并降低 anchor 惩罚，可修复对 `v53` 对位。
- 关键机制：
  - 保留 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与超时回退；
  - 新增 `is_tactical_escape_candidate`，识别敌将/关键重兵/主将近域等高价值候选；
  - 对战术候选引入 `tactical_drop_relax`（放宽 raw-drop 剪枝）、`tactical_anchor_scale`（减轻锚定惩罚）与 `tactical_reply_bonus`（敌应手受限时加分）。
- 评测证据：
  - iter gate：`eval_20260304_083140`（每关键对手 100 局，合计 300 局）
  - vs `v1`: `58/100`（58.0%）
  - vs `v2`: `63/100`（63.0%）
  - vs `v53`: `43/100`（43.0%）
- 生产口径现状：`eval_20260304_082422` 的生产池未纳入 `v57`，当前无生产 Elo 证据可用于晋升判断。
- 结论标签：`regression`。对 `v1/v2` 仍有优势，但关键目标 `v53` 对位未改善，暂不具备替代条件。

### v58（`cpp_v58_overlay_dominance_veto`）

- 设计假设：`v57` 仍可能在强对手对位中选择“敌方应手主导”的候选；通过增加应手主导 veto 并收紧战术逃逸放宽，降低高反击风险分支的误选。
- 关键机制：
  - 保留 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与超时回退；
  - 新增 dominance-veto：当敌方最佳应手明显主导且主将威胁改善不足时，过滤该候选；
  - 收紧 `tactical_drop_relax`，并在平稳态关闭 `tactical_reply_bonus`，减少额外奖励噪声。
- 评测证据：
  - iter gate：`eval_20260304_085221`（每关键对手 100 局，合计 300 局）
  - vs `v1`: `58/100`（58.0%）
  - vs `v2`: `62/100`（62.0%）
  - vs `v53`: `42/100`（42.0%）
  - 生产口径现状：`eval_20260304_084115` 的生产池未纳入 `v58`，当前无生产 Elo 证据可用于晋升判断。
- 结论标签：`regression`。对 `v1/v2` 仍保持优势，但关键目标 `v53` 仍退化，且较 `v57` 无改善。

### v59（`cpp_v59_overlay_base_reply_guard`）

- 设计假设：`v58` 的关键问题是 overlay 仍会选择“相对 base 明显放大敌方最佳应手”的换招；通过引入“相对 base 的敌方应手增量门控与软惩罚”，减少这类高反击分支的误选，尝试修复对 `v53` 对位退化。
- 关键机制：
  - 保留 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与超时回退；
  - 新增 base 参考应手：先评估 base 动作后的 `base_enemy_reply_score` 作为对照；
  - 对非 base 候选引入 relative veto：若敌方最佳应手显著高于“base 应手 + 允许增量（raw_drop/威胁改善补偿）”，则过滤；
  - 对未被过滤候选加入 relative penalty：按超额应手幅度扣分，降低误选概率。
- 评测证据：
  - iter gate：`eval_20260304_091146`（每关键对手 100 局，合计 300 局）
  - vs `v1`: `59/100`（59.0%）
  - vs `v2`: `62/100`（62.0%）
  - vs `v53`: `43/100`（43.0%）
  - 生产口径现状：`eval_20260304_090104` 的生产池未纳入 `v59`，当前无生产 Elo 证据可用于晋升判断。
- 结论标签：`regression`。相对 `v58` 仅有局部微调幅度（对 `v53` 42% -> 43%），未形成可支撑主线替代的改善证据。

### v60（`cpp_v60_overlay_pressure_anchor`）

- 设计假设：`v59` 在关键对位中仍可能通过“保守换招”丢失对敌主将压力；通过引入“相对 base 的敌主将压力保持”门控，减少这类丢节奏动作，尝试修复对 `v53` 退化。
- 关键机制：
  - 保留 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与超时回退；
  - 新增 base 敌主将压力参考：计算 `base_enemy_main_pressure`；
  - 对非 base 候选引入 pressure-loss veto：当相对 base 的敌主将压力损失超过允许区间（含 raw-drop/主将威胁改善补偿）时过滤；
  - 对未过滤候选增加 pressure-loss penalty：按超额损失扣分，抑制“过度防守换招”。
- 评测证据：
  - iter gate：`eval_20260304_093304`（每关键对手 100 局，合计 400 局）
  - vs `v1`: `59/100`（59.0%）
  - vs `v2`: `60/100`（60.0%）
  - vs `v53`: `44/100`（44.0%）
  - vs `v59`: `38/100`（38.0%）
  - 生产口径现状：`eval_20260304_091945` 的生产池未纳入 `v60`，当前无生产 Elo 证据可用于晋升判断。
- 结论标签：`regression`。虽然对 `v53` 仅有小幅回升（43% -> 44%），但对前代 `v59` 明显退化（38%），整体不具备替代价值。

### v61（`cpp_v61_overlay_pressure_riskgate`）

- 设计假设：`v60` 的退化主因是 pressure-anchor 在平稳局面也过度生效；将该机制收敛到高风险态，稳定态回退 `v59` 规则，预计可缓解对前代的明显回归。
- 关键机制：
  - 保留 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与超时回退；
  - 新增 `pressure_anchor_enabled` 风险门控：高风险态启用 pressure-loss veto/penalty，平稳态关闭；
  - 候选评估中仅在启用时执行 pressure-loss 相关过滤与扣分，避免稳定局面额外约束。
- 评测证据：
  - iter gate：`eval_20260304_095530`（每关键对手 100 局，合计 500 局）
  - vs `v1`: `59/100`（59.0%）
  - vs `v2`: `59/100`（59.0%）
  - vs `v53`: `44/100`（44.0%）
  - vs `v59`: `39/100`（39.0%）
  - vs `v60`: `51/100`（51.0%）
  - 生产口径现状：`eval_20260304_093957` 的生产池未纳入 `v61`，当前无生产 Elo 证据可用于晋升判断。
- 结论标签：`regression`。相对 `v60` 有止损，但关键对位 `v59/v53` 仍明显负向，未达到主线替代条件。

### v62（`cpp_v62_overlay_baseveto_riskonly`）

- 设计假设：`v61` 仍可能因稳定态 `base-reply veto` 造成候选过早过滤；将 `base-reply` 调整为“高风险态硬 veto，平稳态仅软惩罚”，预计可缓解对 `v59` 的退化。
- 关键机制：
  - 保留 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与超时回退；
  - 新增 `base_reply_veto_enabled` 门控：高风险态启用、平稳态关闭；
  - 稳定局面将 `base-reply` 从“硬 veto + penalty”改为“penalty only”。
- 评测证据：
  - iter gate：`eval_20260304_101631`（每关键对手 100 局，合计 500 局）
  - vs `v1`: `58/100`（58.0%）
  - vs `v2`: `59/100`（59.0%）
  - vs `v53`: `44/100`（44.0%）
  - vs `v59`: `38/100`（38.0%）
  - vs `v61`: `47/100`（47.0%）
  - 生产口径现状：`eval_20260304_100237` 的生产池未纳入 `v62`，当前无生产 Elo 证据可用于晋升判断。
- 结论标签：`regression`。关键对位（`v53/v59`）未改善，且对 `v61` 也未转正。

## 对“最新迭代是否无意义”的判定

1. 若“最新迭代”指 v62：不是无意义迭代（有明确代码差异与评测证据），但当前结果是 `regression`。
2. 若指 v61/v60/v59/v58/v57/v56/v55：同样不是无意义迭代，但结果仍是 `regression`。
3. 若指 v51：是，当前无实质增量。

## 后续文档治理建议（执行标准）

每新增一个 `vN`，文档至少同步四项：

1. 思路假设：要修哪类对局失败模式；
2. 机制改动：新增/删除/替换了哪些评分或门控；
3. 证据链：iter 与生产各自的样本、分对手结果；
4. 结论标签：`promising` / `neutral` / `regression` / `placeholder`。
