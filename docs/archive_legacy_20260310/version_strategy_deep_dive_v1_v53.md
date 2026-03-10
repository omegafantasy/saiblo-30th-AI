# 蚁洋陷役2 C++ AI 版本思路全量梳理（v1-v66）

更新时间：2026-03-04（UTC）

数据口径：

- 生产 Elo：`/www/autolab/runtime/latest.json`（`eval_20260304_175404`，61408 局 cumulative）
- 迭代 Elo：`/www/autolab/runtime/scopes/iter/latest.json`（`eval_20260304_180039`，100 局）
- 迭代日志主文档：`/www/docs/round2_autolab_and_iterations.md`

判读原则：

- 生产 Elo 为最终口径；iter Elo 只用于候选筛选。
- 当前生产为 adaptive 抽样池；最近一轮 `champion.old/new` 已回到 `cpp_v66_generals_weapon_econ -> cpp_v66_generals_weapon_econ`，但跨 tag 仍不能直接比较 Elo 绝对值。

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

## 逐版本思路分析（v1-v66）

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

### v64（`cpp_v64_generals_rebuild`）

- 设计假设：把 Generals-AI 的“技能/主将动作/击杀序列”重建到当前框架，获得比 v53 更高的主动进攻能力。
- 关键机制：强制击杀序列搜索、主将技能链（rout/command/defence/weaken）、主将先动再军团推进。
- 评测证据：
  - 生产口径 `eval_20260304_121021`：rank#8（1576.98）。
  - iter 口径 `eval_20260304_122143`：`v66 vs v64 = 48/100`（反向可见 v64 对当前 v66 仍有压制）。
- 结论标签：`promising`（已进入生产上游，但仍需关键对位 confirm）。

### v66（`cpp_v66_generals_weapon_econ`，本轮 in-place 更新）

- 设计假设：在不恢复“全量来源扫描”的前提下，用 threat-source 饱和计数与双层危险触发，减少扫描分支同时保留近身中风险预警能力。
- 关键机制：
  - Generals 借鉴：`threat_origin_cnt` 映射为 `count_threat_sources_to_cell(...)`；
  - ANTWar 借鉴：`danger/reserved` 映射为 `apply_reserved_main_floor(...)` + `apply_reserved_release_floor(...)`（危险态保留，安全态释放）；
  - 简化改动：新增 `should_enable_reserved_gate(...)`，仅高压态计算 threat-source；
  - 进一步简化：移除 `move_cap` 硬减步路径，仅保留 reserve floor 软约束（更贴近 ANTWar 的 reserved 思路）。
  - 本轮补充：在 `select_best_move_overlay(...)` 中移除 pressure-loss 次级 veto/penalty 分支，保留 `base_reply_veto` + `dominance` 主约束。
  - 本轮补充2：加入 `pressure_drop_veto`（仅高压态启用，单阈值 veto），不恢复 pressure-loss penalty 链。
  - 本轮补充3：移除非高压态 conservative overlay，改为 `!high_risk` 直接 `tuning.enabled=false`（非危险态仅走 base chooser）。
  - 本轮补充4：在 `choose_overlay_tuning(...)` 增加 `main_threat_sources` 判定；仅当 `duel_close` 且（`main_danger` 或 `source_alert`）满足时才启用高风险 overlay，并在低来源压力下收缩 `pool_limit`。
  - 本轮补充5：把 `main_danger/main_threat_sources` 改为 step 级预计算并传入 overlay 调参，去除 `choose_overlay_tuning(...)` 内部重复 threat-source 扫描。
  - 本轮补充6：进一步把 `duel_close` 的 threat-source 扫描改为仅在 `step_main_danger>=0.40` 时触发（尝试继续减扫描）。
  - 本轮补充7：`count_threat_sources_to_cell` 改为饱和计数（`cap` 早停）；step 触发改为双层门控：`reserve_gate -> cap=4`，`duel_close && danger>=0.28 -> cap=2`。
  - 本轮补充8：把 `duel_close` 门控从单阈值改为滞回锁存（`on=0.28/off=0.22`），映射 ANTWar 的 `global_state` 稳态切换思路，减少边界抖动。
  - 本轮补充9：移除滞回锁存状态，改为无状态 danger 分级探测：`reserve_gate->cap=4`，`duel_close&&danger>=0.28->cap=2`，`duel_close&&danger>=0.48->cap=4`（critical 分支）。
  - 本轮补充10：继续简化 high-risk overlay，删除 `pressure_drop_veto` 次级分支，仅保留 `base_reply_veto + dominance + reserved/danger` 主约束链。
  - 本轮补充11：移除 `tactical_escape` 特例链（含 drop relax / anchor scale / tactical reply bonus），high-risk 候选统一采用单套评分规则。
  - 本轮补充12：新增 `enemy_skill_window` 单状态门控（敌方主将近域技能可用时），仅在 high-risk 下收紧 `pool_limit/max_raw_drop/base_reply_veto_slack/dominance_threat_gain_min`，不引入额外搜索层。
  - 本轮补充13：撤销“技能窗口收紧 overlay 参数”路径，改为仅在技能窗口抬升 `main_safe_reserve`（`apply_skill_window_reserve_floor`），把借鉴点收敛到 ANTWar 风格的 `reserved` 主干，减少分支状态穿透。
  - 本轮补充14：把 `high_risk/source_alert` 离散门控收敛为单一 `risk_score` 连续路径（`main_danger + source_pressure + duel_pressure`），并用 `risk_alpha` 连续驱动 `enemy_weight/base_anchor_penalty/max_raw_drop/base_reply_*`，减少 overlay 补丁分支。
  - 保留 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` 硬截止与 `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate `eval_20260304_122143`（seed=20260320，每对手 100 局）：vs `v1` `78/100`，vs `v2` `81/100`，vs `v53` `55/100`，vs `v64` `48/100`。
  - iter gate `eval_20260304_124223`（seed=20260321，每对手 100 局，简化后）：vs `v1` `76/100`，vs `v2` `80/100`，vs `v53` `58/100`，vs `v64` `50/100`。
  - iter confirm `eval_20260304_125633`（seed=20260323，`v66 vs v64` 200 局）：`106/200`（53.0%）。
  - iter confirm `eval_20260304_130613`（seed=20260324，`v66 vs v64` 200 局）：`106/200`（53.0%，与上一轮一致）。
  - iter gate-min `eval_20260304_133531`（seed=20260327，`v66 vs v64` 100 局）：`51/100`（51.0%，本轮减法未体现增益）。
  - iter confirm-split `eval_20260304_134431`（seed=20260330，100 局）+ `eval_20260304_134710`（seed=20260331，100 局）：
    合计 `v66 vs v64 = 101/200`（50.5%）。
  - iter confirm-split `eval_20260304_135424`（seed=20260332，100 局）+ `eval_20260304_135654`（seed=20260333，100 局）：
    合计 `v66 vs v64 = 111/200`（55.5%）。
  - iter confirm-split `eval_20260304_140823`（seed=20260334）+ `eval_20260304_141535`（seed=20260335）：
    `v66 vs v1 = 159/200`（79.5%），`v66 vs v2 = 154/200`（77.0%）。
  - iter confirm-split `eval_20260304_142919`（seed=20260336）+ `eval_20260304_144359`（seed=20260337）：
    `v66 vs v1 = 165/200`（82.5%），`v66 vs v2 = 143/200`（71.5%）。
  - iter confirm-split `eval_20260304_145707`（seed=20260338）+ `eval_20260304_145932`（seed=20260339）：
    `v66 vs v64 = 114/200`（57.0%）。
  - iter gate `eval_20260304_152053`（seed=20260340，关键三基线各 100 局）：
    `v66 vs v1 = 80/100`，`v66 vs v2 = 73/100`，`v66 vs v64 = 46/100`。
  - iter confirm-split（当前代码）`eval_20260304_152053` + `eval_20260304_152333`（seed=20260341）：
    `v66 vs v64 = 105/200`（52.5%）。
  - iter gate `eval_20260304_154112`（seed=20260342，关键三基线各 100 局）：
    `v66 vs v1 = 80/100`，`v66 vs v2 = 73/100`，`v66 vs v64 = 46/100`。
  - iter confirm（当前补充7）`eval_20260304_154813`（seed=20260343，100 局）：
    `v66 vs v64 = 59/100`。
  - 合并（当前补充7）`154112 + 154813`：
    `v66 vs v64 = 105/200`（52.5%）。
  - iter gate（补充8）`eval_20260304_160144`（seed=20260344）：
    `v66 vs v1 = 80/100`，`v66 vs v2 = 73/100`，`v66 vs v64 = 45/100`。
  - iter confirm（补充8）`eval_20260304_161040`（seed=20260345）：
    `v66 vs v64 = 58/100`。
  - 合并（补充8）`160144 + 161040`：
    `v66 vs v64 = 103/200`（51.5%）。
  - iter gate（补充9）`eval_20260304_163017`（seed=20260346）：
    `v66 vs v1 = 80/100`，`v66 vs v2 = 73/100`，`v66 vs v64 = 47/100`。
  - iter confirm（补充9）`eval_20260304_164010`（seed=20260347）：
    `v66 vs v64 = 57/100`。
  - 合并（补充9）`163017 + 164010`：
    `v66 vs v64 = 104/200`（52.0%）。
  - iter gate（补充10）`eval_20260304_170145`（seed=20260348）：
    `v66 vs v1 = 81/100`，`v66 vs v2 = 73/100`，`v66 vs v64 = 47/100`。
  - iter confirm（补充10）`eval_20260304_172021`（seed=20260349）：
    `v66 vs v64 = 56/100`。
  - 合并（补充10）`170145 + 172021`：
    `v66 vs v64 = 103/200`（51.5%）。
  - iter gate（补充11）`eval_20260304_174158`（seed=20260350）：
    `v66 vs v1 = 82/100`，`v66 vs v2 = 73/100`，`v66 vs v64 = 48/100`。
  - iter confirm（补充11）`eval_20260304_180039`（seed=20260351）：
    `v66 vs v64 = 57/100`。
  - 合并（补充11）`174158 + 180039`：
    `v66 vs v64 = 105/200`（52.5%）。
  - iter gate（补充12）`eval_20260304_182150`（seed=20260352，关键三基线各 100 局）：
    `v66 vs v1 = 81/100`，`v66 vs v2 = 74/100`，`v66 vs v64 = 49/100`。
  - iter gate（补充13）`eval_20260304_190128`（seed=20260353，关键三基线各 100 局）：
    `v66 vs v1 = 81/100`，`v66 vs v2 = 74/100`，`v66 vs v64 = 56/100`。
  - iter confirm（补充13）`eval_20260304_192127`（seed=20260354）：
    `v66 vs v64 = 54/100`。
  - 合并（补充13）`190128 + 192127`：
    `v66 vs v64 = 110/200`（55.0%）。
  - iter smoke（补充14）`eval_20260304_194044`（seed=20260355，每对手 20 局）：
    `v66 vs v1 = 16/20`，`v66 vs v2 = 14/20`，`v66 vs v64 = 13/20`（仅方向筛选）。
  - iter gate（补充14）`eval_20260304_194245`（seed=20260356，关键三基线各 100 局）：
    `v66 vs v1 = 80/100`，`v66 vs v2 = 72/100`，`v66 vs v64 = 57/100`。
  - iter confirm（补充14）`eval_20260304_200105`（seed=20260357，`v66 vs v64` 100 局）：
    `v66 vs v64 = 52/100`。
  - 合并（补充14）`194245 + 200105`：
    `v66 vs v64 = 109/200`（54.5%）。
  - replay 分析 `replay_analysis/latest.json`（tag=`192127`）：
    `analyzed_matches=100`，`missing_replay=0`；`v66-v64` 为 `54/100`。
    正例 seed `20260354` turning point 在 round122（`delta_army_lead_p0=+94`，同回合出现敌方技能动作 `Action=[4,18,2,9,9]`）；
    负例 seed `20261265` turning point 在 round136（`delta_army_lead_p0=+353`，出现技能动作 `Action=[4,21,2,8,9]` 后失衡）。
  - replay 分析 `replay_analysis/latest.json`（tag=`200105`）：
    `analyzed_matches=100`，`missing_replay=0`；`v66-v64` 为 `52/100`，`avg_rounds=119.94`；
    正例 seed `20260357` turning point 在 round52（`delta_army_lead_p0=+82`，当窗以军团推进交换为主）；
    负例 seed `20260358` turning point 在 round131（`delta_army_lead_p0=-29`，出现对手征召 `Action=[7,7,3]` 后继续失衡）。
  - replay 分析 `replay_analysis/latest.json`（tag=`182150`）：
    `analyzed_matches=300`，`missing_replay=0`；`v66-v64` pair_stats 为 `49/100` vs `51/100`。
    正例 seed `20263282` turning point 在 round169（`delta_army_lead_p0=-51`，v66 在 p1 受益）；
    负例 seed `20262370` turning point 在 round174（`delta_army_lead_p0=-20`），并出现技能动作 `Action=[4,16,2,14,13]` 后续推进。
  - replay 分析 `replay_analysis/latest.json`（tag=`164010`）：
    `v66` 的 `no_effect_rate=0.06325` 与 `v64` 的 `0.06499` 接近；正例 seed `20260347` turning point 在 round166（`delta_army_lead_p0=+44`），负例 seed `20261265` 在 round136 出现大摆动（`delta_army_lead_p0=+353`）。
  - replay 分析 `replay_analysis/latest.json`（tag=`172021`）：
    `v66` 的 `no_effect_rate=0.06421`，`v64` 的 `0.06623`；正例 seed `20261260` 在 round19 出现 `delta_army_lead_p0=-17`（v66收益），负例 seed `20260358` 在 round131 出现 `delta_army_lead_p0=-29`（v66失衡）。
  - replay 分析 `replay_analysis/latest.json`（tag=`180039`）：
    `v66` 的 `no_effect_rate=0.06563` 与 `v64` 的 `0.06605` 接近；正例 seed `20260351` 在 round120 出现 `delta_army_lead_p0=+78`，负例 seed `20260353` 在 round39 出现技能窗口后摆动（`delta_territory_lead_p0=-1`,`delta_army_lead_p0=+57`）。
  - 生产口径 `eval_20260304_175404`：`mode=adaptive`，`champion.old/new = v66 -> v64`（发生切换）。
  - 生产口径 `eval_20260304_180902`：`mode=adaptive`，`champion.old/new = v64 -> v64`（稳定未切换）。
  - 生产口径 `eval_20260304_191239`：`mode=adaptive`，`champion.old/new = v66 -> v66`（稳定未切换）。
  - 生产口径 `eval_20260304_195549`：`mode=adaptive`，`champion.old/new = v64 -> v64`（本 tag 内未切换，且 `config.pairs` 含 `v64-v66` 直接对局）。
- 结论标签：`neutral`（补充14 结构更简，但关键对位合并仅 `109/200=54.5%`，未达 `>55%` 严格宣称线）。

### v66（补充15：危险态门控下的前线征召窗口，in-place）

- 设计假设：`v66` 在与 `v64` 的关键对位里，技能/征召节奏仍偏被动；借鉴 Generals 的前线副将补位思路，在“主将贴近且我方副将数落后”时短时放开征召阈值，尝试提高中盘反压能力。
- 关键机制：
  - 保持 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` CPU 硬截止与 `hard_cutoff_hit` 回退（搜索链不新增层数）；
  - 新增 `count_sub_generals_alive(...)` 计数我方/敌方副将；
  - 征召逻辑新增 `recruit_attack_window = duel_close && !reserve_state && enemy_sub_count > my_sub_count`；
  - 窗口开启时降低征召门槛：`owned_cells>=8`、`accept_threshold=14`（默认 `10/20`），并提高前线/敌主将邻近权重；
  - ANTWar 映射：在 `reserve_state`（危险态）下禁止 aggressive recruit window，维持保守主干。
- 评测证据：
  - iter smoke `eval_20260304_202203`（每对手 20 局）：
    - vs `v1` `14/20`，vs `v2` `16/20`，vs `v64` `13/20`（仅方向）。
  - iter gate `eval_20260304_202328`（每对手 100 局）：
    - vs `v1` `82/100`，vs `v2` `74/100`，vs `v64` `55/100`。
  - iter confirm `eval_20260304_204034`（`v66 vs v64` 100 局）：
    - `52/100`。
  - 合并关键对位（gate+confirm）：
    - `v66 vs v64 = 107/200`（53.5%）。
  - replay 分析（`eval_20260304_204034`）：
    - `analyzed_matches=100`，`missing_replay=0`；
    - `v64` 的 `general_skill/call_general` 仍高于 `v66`（`475/347` vs `361/215`）。
- 结论标签：`regression`。
  - 原因：关键目标 `v64` 在 200 局仅 `53.5%`，未过 `>55%` 严格线，且相较补充14（`109/200=54.5%`）出现回撤；当前改动不宜固化为新分支。

### v66（补充16：征召金币缓冲 + 技能窗口收敛，in-place）

- 设计假设：补充15的前线征召窗口仍可能在关键对位中透支技能预算；借鉴 Generals 的资源保留思路，把征召改成“先留金币缓冲，再补位”，并用 ANTWar 式危险态门控收敛征召触发。
- 关键机制：
  - 保持 `CLOCK_THREAD_CPUTIME_ID` 的 `<=200ms` 硬截止与 `hard_cutoff_hit` 回退；
  - 新增 `compute_recruit_coin_buffer(...)`，按 `reserve/duel_close/enemy_skill_window/sub_count差` 计算征召保留金币；
  - `recruit_attack_window` 收敛为：`duel_close && !reserve && enemy_sub_count>my_sub_count && enemy_skill_window`；
  - 征召阈值回收：`owned_need=9`、`accept_threshold=16`（相对补充15更保守）；
  - 执行条件新增：`my_coin >= 50 + recruit_coin_buffer`。
- 评测证据：
  - smoke `eval_20260304_210144`：vs `v1` `17/20`，vs `v2` `15/20`，vs `v64` `11/20`（仅方向）。
  - gate `eval_20260304_210310`（每对手100局）：
    - vs `v1` `81/100`，vs `v2` `72/100`，vs `v64` `53/100`。
  - confirm `eval_20260304_212040`（`v66 vs v64` 100局）：`44/100`。
  - 合并关键对位（gate+confirm）：`v66 vs v64 = 97/200`（48.5%）。
  - replay `eval_20260304_212040`：`analyzed=100`，`missing=0`；`v64` 的 `general_skill/call_general` 仍显著更高（`466/392` vs `351/146`）。
- 结论标签：`regression`。
  - 原因：关键对位从补充15（`107/200=53.5%`）进一步下滑到 `97/200=48.5%`，说明本轮“征召收紧”对关键对手是负收益。

### v66（补充17：征召缓冲简化后的 confirm 复验，in-place）

- 设计假设：
  - 维持补充16后的“危险态保币 + 前线窗口征召”框架，在不增加分支复杂度的前提下，通过追加 confirm 判断该方向是否对关键对位（`v64`）有稳定收益。
- 关键机制：
  - 继续使用 `compute_recruit_coin_buffer(...)`（`reserve_state/duel_close/sub_gap`）与 `recruit_attack_window` 的简化逻辑；
  - 保持 `CLOCK_THREAD_CPUTIME_ID` + `200ms` 单步 CPU 硬截止与 `hard_cutoff_hit` 回退；
  - 不新建版本目录，保持 `v66` in-place 小步迭代。
- 评测证据：
  - smoke `eval_20260304_214146`：`v66-v64=10/20`（仅方向）。
  - gate `eval_20260304_214520`：`v66-v1=82/100`，`v66-v2=75/100`，`v66-v64=58/100`。
  - confirm-1 `eval_20260304_220042`：`v66-v64=50/100`。
  - confirm-2 `eval_20260304_220641`：`v66-v64=58/100`。
  - 关键对位合并：
    - gate + confirm-2：`116/200 = 58.0%`；
    - gate + confirm-1 + confirm-2：`166/300 = 55.3%`。
  - replay（latest=`220641`）：`analyzed=100`、`missing=0`；动作分布 `v66 general_skill/call_general=362/206`，`v64=504/397`。
- 结论标签：`promising`。
  - 说明：关键对位在新增 confirm 回升，且 `>=200` 局窗口下可达 `>55%`；
  - 但仍存在 seed 波动（`50/100` 与 `58/100` 分歧），尚需继续补样本确认稳定性。

### v66（补充18：征召“主将支持半径”门控，in-place）

- 设计假设：
  - 目前 `v66-v64` 已回到 `>55%` 区间，但 replay 中仍有高地盘波动；
  - 借鉴 Generals 的“安全位置优先”和 ANTWar 的“danger 下收敛扩张”，把征召限制在主将可支持半径内，降低远端孤立扩张。
- 关键机制：
  - `choose_recruit_cell(...)` 新增 `main_dist_cap` 门控；超过主将支持半径的候选直接剔除；
  - 增加主将距离支持分，优先更易联动的征召点；
  - `recruit_main_dist_cap = reserve_state ? 9 : (recruit_attack_window ? 12 : 10)`；
  - 搜索链硬约束不变：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter confirm `eval_20260304_224141`（seed=20260391，100局，`v66 vs v64`）：`56/100`。
  - replay `224141`：`analyzed=100`、`missing=0`、`parse_errors=0`；
    `v66` 动作分布 `general_skill/call_general=409/209`，`v64=551/402`；
    胜例 seed `20260391` 关键摆动在 round136（`delta_army_lead_p0=+321`），
    负例 seed `20261302` 关键摆动在 round121（`delta_territory_lead_p0=+2`,`delta_army_lead_p0=+46`）。
- 结论标签：`neutral`。
  - 原因：关键对位仍 `>55%`，但波动风险未明显收敛，尚无足够证据表明此改动较补充17形成稳定增益。

### v66（补充19：主将支持半径征召的二次 confirm，in-place）

- 设计假设：
  - 补充18的“主将支持半径征召”能压制远端孤立扩张，但需要再做 confirm 判断其在关键对位（`v64`）是否稳定生效。
- 关键机制：
  - 继续使用 `choose_recruit_cell(..., main_dist_cap)` 的半径硬门控；
  - `reserve_state ? 9 : (recruit_attack_window ? 12 : 10)` 的分态半径；
  - 保持搜索链 CPU 硬约束：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + 回退。
- 评测证据：
  - iter confirm（本轮）`eval_20260304_230146`：`v66 vs v64 = 53/100`；
  - 与补充18 confirm（`eval_20260304_224141`，`56/100`）合并：`109/200 = 54.5%`；
  - replay（`230146`）`analyzed=100`、`missing=0`；动作分布：
    - `v66 general_skill/call_general=289/237`
    - `v64 general_skill/call_general=351/350`
  - 波动证据：`largest_army_swing` 峰值样本达 `814`，中后盘摆动仍明显。
- 结论标签：`neutral`。
  - 理由：关键对位仍为正胜率，但 `200` 局窗口未过 `>55%` 严格线，且波动未收敛到可宣称“稳定优于 v64”的程度。

### v66（补充20：征召 source-alert 门控二次 confirm，in-place）

- 设计假设：
  - 补充18/19 的主将支持半径门控仍有波动；
  - 进一步借鉴 Generals 的 threat-source 与 ANTWar 的 danger/reserved，把“近主将来源压力”直接映射到征召窗口开关，减少高压时的误征召。
- 关键机制：
  - 新增 `recruit_main_threat_sources`（cap=2）与 `recruit_source_alert`；
  - `recruit_attack_window` 改为：`duel_close && !reserve_state && !recruit_source_alert && sub_gap > 0`；
  - source alert 下统一收紧：`recruit_coin_buffer += 10`、`recruit_main_dist_cap=8`、`accept_threshold=22`；
  - 搜索 CPU 硬约束保持不变：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + 回退。
- 评测证据：
  - confirm-A `eval_20260304_232120`：`v66 vs v64 = 58/100`；
  - confirm-B `eval_20260304_232544`：`v66 vs v64 = 49/100`；
  - 同代码合并：`107/200 = 53.5%`。
  - replay（A）动作分布：`v66 general_skill/call_general=371/204`，`v64=512/401`；
  - replay（B）动作分布：`v66=327/180`，`v64=379/322`；
  - 两批均 `rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`。
- 结论标签：`regression`。
  - 理由：尽管一批次达 `58/100`，但二次 confirm 回落到 `49/100`，合并仅 `53.5%`，未过 `>55%` 严格线且波动更大；当前门控强度（尤其阈值抬升）偏保守。

### v66（补充21：source-alert 阈值回滚，in-place）

- 设计假设：
  - 补充20中 `source_alert -> accept_threshold=22` 可能过度保守，导致关键对位振荡；
  - 借鉴 ANTWar 的 `reserved` 最小约束思路，保留保币与半径收紧，移除额外评分阈值分支以简化结构。
- 关键机制：
  - 保留 `recruit_main_threat_sources/recruit_source_alert` 门控；
  - 保留 `recruit_coin_buffer += 10` 与 `recruit_main_dist_cap=8`；
  - 回滚阈值：`accept_threshold` 简化为 `recruit_attack_window ? 15 : 20`（移除 `22` 分支）；
  - 搜索硬约束不变：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + 回退。
- 评测证据：
  - iter confirm `eval_20260305_000203`：`v66 vs v64 = 53/100`；
  - replay：`rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`；
  - 动作分布：`v66 general_skill/call_general=317/203`，`v64=498/377`；
  - 与补充20低点（`49/100`）相比回升，但仍未过 `55%`。
- 结论标签：`neutral`。
  - 理由：回滚后性能回升但不足以形成稳定优势，需继续补 `>=100` 局 confirm 才能判断是否有效收敛波动。

### v66（补充22：征召连续 aggression 计划，in-place）

- 设计假设：
  - 现有征召链路仍有 `source_alert + attack_window` 离散分叉，容易在边界局面抖动；
  - 借鉴 Generals 的 `threat_origin` 与 ANTWar 的 `reserved/safe_coin`，把征召策略收敛为单一连续风险主干，优先减少分支层数并降低 patch 叠加。
- 关键机制：
  - 新增 `RecruitPlan` + `choose_recruit_plan(...)`，由连续 `aggression` 分数统一输出：
    `coin_buffer/main_dist_cap/owned_need/accept_threshold/attack_window`；
  - 移除征召段原有多重 ternary 组合，调用点仅消费 `RecruitPlan`；
  - Generals 映射：`main_threat_sources` 作为 `aggression` 扣分项（来源越多越保守）；
  - ANTWar 映射：`reserve_state` 直接压低 `aggression`，并抬升保币、收紧半径；
  - 搜索链硬约束保持不变：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate `eval_20260305_010140`（seed=20260395，`v66 vs v64`，100局）：
    `56/100`（达到两 AI 比较门槛 `>=100`，但尚非 `>=200` confirm）。
  - replay `eval_20260305_010140`：
    `rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`；
    动作分布 `v66 general_skill/call_general=261/176`，`v64=492/395`；
    `army_swing` 峰值 `619`、`terr_swing` 峰值 `104`，波动仍大。
  - 原始回放核对：
    - 胜例 `seed=20261307`：
      `/www/autolab/runtime/scopes/iter/replays/eval_20260305_010140/20260305_010140_p0-cpp_v64_generals_rebuild_p1-cpp_v66_generals_weapon_econ_seed-20261307_rounds-180.jsonl`
      turning point 在 round `86`（`delta_army_lead_p0=-37`）；可见 `v66` 征召动作 `Round 44/104`（`Action=[7,...]`）。
    - 负例 `seed=20260396`：
      `/www/autolab/runtime/scopes/iter/replays/eval_20260305_010140/20260305_010140_p0-cpp_v66_generals_weapon_econ_p1-cpp_v64_generals_rebuild_seed-20260396_rounds-180.jsonl`
      turning point 在 round `140`（`delta_army_lead_p0=-241`）；该局 `v64` 更高频征召（`Round 24/49/81/96`）。
  - 生产口径（唯一权威）`eval_20260305_005347`：
    `champion.old/new = v66 -> v64`（发生切换），提示跨 tag 对手池风险上升，需以额外 head-to-head confirm 复验。
- 结论标签：`neutral`。
  - 理由：本轮方向转正（`56/100`）且结构更简，但样本仍不足以形成“稳定优于 v64”结论，且 replay 高波动未收敛。

### v66（补充23：征召评分去布尔化，连续 aggression 落点，in-place）

- 设计假设：
  - 补充22 已将征召门控统一到 `RecruitPlan`，但 `choose_recruit_cell` 仍残留 `attack_window` 布尔分支，边界局面仍会离散跳变；
  - 借鉴 Generals 的 threat-origin 连续威胁观与 ANTWar 的 reserved 连续保币观，把征召评分权重也改成连续 `aggression`，继续减少分支层。
- 关键机制：
  - `choose_recruit_cell(...)` 入参由 `bool attack_window` 改为 `double aggression`；
  - 评分权重改为连续函数：
    - `front_weight = 20.0 + 2.0 * aggression`
    - `main_support_weight = 0.75 - 0.30 * aggression`
    - `enemy_main_weight = 1.0 + 0.8 * aggression`
  - 调用点直接使用 `choose_recruit_plan(...)` 输出的 `aggression`，维持 `coin_buffer/main_dist_cap/accept_threshold` 同源；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + `hard_cutoff_hit` 回退（未新增搜索层）。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_012201`（seed=20260396，`v66 vs v64` 100 局）：
    - `v66 vs v64 = 56/100`（达到两 AI 结论门槛 `>=100`，但仍非 `>=200` confirm）。
  - replay（同 tag）：
    - `rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`；
    - 动作分布：`v66 general_skill/call_general=326/177`，`v64=522/391`；
    - 高波动仍在：`army_swing` 峰值 `619`、`terr_swing` 峰值 `104`。
  - 原始回放核对（来自 `paths.matches`）：
    - 胜例 seed `20261313`：turning point round `171`（`delta_army_lead_p0=-224`，p1 为 `v66` 受益），round `176` 出现 `v66` 征召 `Action=[7,2,4]`，随后 round `177/178` 连续技能动作；
    - 负例 seed `20260439`：turning point round `138`（`delta_army_lead_p0=-177`，p0 为 `v66` 失衡），同窗出现 `Action=[4,25,2,7,10]` 后接对手征召 `Action=[7,5,11]`。
  - 生产口径（唯一权威）`eval_20260305_011624`：
    - `champion.old/new = v64 -> v64`（本 tag 未切换）；但 gauntlet 仍受 champion 与配对集影响，iter Elo 只作筛选依据。
- 结论标签：`neutral`。
  - 理由：结构继续简化且关键对位维持正胜率（`56/100`），但样本仍不足以宣称稳定优势，且 replay 高波动未收敛。

### v66（补充24：征召 lead-signal 连续抑攻/提攻，in-place）

- 设计假设：
  - 补充23后征召链已连续化，但在顺风/逆风局仍缺少“局面领先度”反馈，导致部分局面继续出现过度扩张或追分不足；
  - 借鉴 Generals 的 `impact_value`（安全优势下减少冒进）和 ANTWar 的 `global_state/reserved`（顺逆风差异化资源策略），将领先度映射到同一 `aggression` 连续主干。
- 关键机制：
  - 新增 `sum_owned_army(...)` 作为轻量兵力领先估计；
  - `choose_recruit_plan(...)` 新增 `territory_lead/army_lead` 入参，构造：
    - `lead_signal = 0.55 * terr_signal + 0.45 * army_signal`
    - `aggression -= 0.20 * max(0, lead_signal)`（领先时降攻）
    - `aggression += 0.10 * max(0, -lead_signal)`（落后时受控提攻）
  - 保持 `RecruitPlan` 单主干与原有 `coin_buffer/main_dist_cap` 联动，不引入新的离散状态分支；
  - 搜索硬约束不变：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_014143`（seed=20260397，`v66 vs v64`，100 局）：
    - `v66 vs v64 = 57/100`（达到两 AI 结论门槛 `>=100`，仍非 `>=200` confirm）。
  - replay（同 tag）：
    - `rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`；
    - 动作分布：`v66 general_skill/call_general=332/173`，`v64=513/390`；
    - 高波动仍在：`army_swing` 峰值 `619`、`terr_swing` 峰值 `106`。
  - 原始回放核对（来自 `paths.matches`）：
    - 胜例 seed `20260446`：turning point round `133`（`delta_army_lead_p0=332`），round `131/133/134` 出现连续技能动作后 p0（v66）建立兵力优势；
    - 负例 seed `20260439`：turning point round `138`（`delta_army_lead_p0=-177`），同窗出现 `Action=[4,25,2,7,10]` 后接对手征召 `Action=[7,5,11]`。
  - 生产口径（唯一权威）`eval_20260305_013618`：
    - `champion.old/new = v64 -> v66`（发生切换），提示 gauntlet 对手池受 champion 身份影响，需继续 head-to-head confirm。
- 结论标签：`neutral`。
  - 理由：关键对位提升到 `57/100`，但样本仍仅 100 局，且波动指标未显著收敛；当前只可视为正向候选信号。

### v66（补充25：征召 pressure-signal 合并与 owned_need 连续化，in-place）

- 设计假设：
  - 补充24后仍有高波动，且 threat-source 与 skill-window 在征召链里分散作用；
  - 借鉴 Generals 的 `threat_origin/impact_value` 与 ANTWar 的 `global_state/reserved`，把来源压力与技能窗口合并成单一连续 `pressure_signal`，并进一步去掉 `owned_need` 的二值阈值分支。
- 关键机制：
  - `choose_recruit_plan(...)` 新增 `enemy_skill_window` 输入；
  - 构造 `pressure_signal = 0.65 * source_signal + 0.35 * skill_signal`，并统一作用于：
    - `aggression -= 0.32 * pressure_signal`
    - `coin_buffer += round(pressure_signal * 6.0)`
    - `main_dist_cap -= round(pressure_signal)`
  - `owned_need` 从二值分支改为连续公式：`clamp(10 - round(aggression*2), 8, 10)`；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_020147`（seed=20260398，`v66 vs v64`，100 局）：
    - `v66 vs v64 = 46/100`（达到 `>=100` 门槛，但明显回归）。
  - replay（同 tag）：
    - `rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`；
    - 动作分布：`v66 general_skill/call_general=303/174`，`v64=366/369`；
    - 波动恶化：`army_swing` 峰值 `726`、`terr_swing` 峰值 `124`。
  - 原始回放核对（来自 `paths.matches`）：
    - 胜例 seed `20260420`：turning point round `150`（`delta_army_lead_p0=-137`，p1 为 `v66` 受益）；
    - 负例 seed `20261310`：turning point round `157`（`delta_army_lead_p0=472`，p0 为 `v66` 失衡）。
  - 生产口径（唯一权威）`eval_20260305_015407`：
    - `champion.old/new = v66 -> v66`（本 tag 未切换）；但该 tag 无直接 `v64-v66` 对局，仍需 head-to-head confirm 才能判优。
- 结论标签：`regression`。
  - 理由：压力信号权重过强导致征召节奏过保守，关键对位从上一轮 `57/100` 回落到 `46/100`，且波动指标同步恶化。

### v66（补充26：pressure 信号软化回退，in-place）

- 设计假设：
  - 补充25出现明显回归，核心问题是同一 pressure 信号对 `aggression/coin_buffer/main_dist_cap` 叠加惩罚过重；
  - 借鉴 Generals 的连续威胁评分与 ANTWar 的“reserved 只在危险态适度生效”，做减法回退：保留连续信号，但降低斜率并去掉二次惩罚。
- 关键机制：
  - `pressure_signal` 从 `0.65*source + 0.35*skill` 调整为 `0.78*source + 0.22*skill`；
  - `aggression` 压力扣分从 `0.32` 降到 `0.14`；
  - `coin_buffer` 压力附加从 `+round(pressure*6)` 降到 `+round(pressure*2)`；
  - 移除 `main_dist_cap` 的压力扣减，避免单信号重复惩罚；
  - 保持搜索硬约束：`CLOCK_THREAD_CPUTIME_ID` + `200ms` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_022119`（seed=20260399，`v66 vs v64`，100 局）：
    - `v66 vs v64 = 59/100`（达到 `>=100` 门槛）。
  - replay（同 tag）：
    - `rows=100`、`analyzed=100`、`missing=0`、`parse_errors=0`；
    - 动作分布：`v66 general_skill/call_general=310/170`，`v64=496/390`；
    - 波动仍高：`army_swing` 峰值 `619`、`terr_swing` 峰值 `106`。
  - 原始回放核对（来自 `paths.matches`）：
    - 胜例 seed `20260446`：turning point round `133`（`delta_army_lead_p0=332`），round `131/133/134` 连续技能动作后 p0（v66）建立优势；
    - 负例 seed `20260439`：turning point round `138`（`delta_army_lead_p0=-177`），同窗出现 `Action=[4,25,2,7,10]` 后接对手征召 `Action=[7,5,11]`。
  - 生产口径（唯一权威）`eval_20260305_021316`：
    - `champion.old/new = v64 -> v64`（本 tag 未切换）；且本 tag 无直接 `v64-v66` 对局，判优仍需 head-to-head confirm。
- 结论标签：`promising`。
  - 理由：在不新增复杂状态的前提下，关键对位从补充25的 `46/100` 恢复到 `59/100`；但样本仍只有 100 局，需补到 `>=200` 才能宣称稳定优势。

### v68（`cpp_v68_overlay_smoothcap`）

- 设计假设：
  - `v66/v67` 的 overlay 仍采用分段阈值切池（`risk<0.70`、`risk>=0.95`），在边界局面会产生候选规模抖动；
  - 借鉴 Generals 的 `threat_origin` 连续威胁表达与 ANTWar 的 `danger/reserved` 危险态收敛思想，将搜索预算改为连续平滑限幅，以减少分支与搜索波动。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v68/ai_v68.cpp`，注册 ID：`cpp_v68_overlay_smoothcap`；
  - `choose_overlay_tuning(...)` 改动：
    - 删除分段 pool 切换逻辑，改为 `smooth_pool_cap = 8 + round(risk_alpha*2)`（上限 `[8,10]`）；
    - `early_stop_gap` 与 `early_stop_min_evals` 改为随 `risk_alpha` 连续调节；
  - 搜索硬约束保持不变：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（`eval_20260305_024959`，规定脚本，14 核，200 局）：
    - `v68 vs v66 = 50/100`
    - `v68 vs v64 = 50/100`
  - replay（同 tag）：`rows=200`、`analyzed=200`、`missing=0`、`parse_errors=0`；
    - 高波动仍在：`largest_army_swing=1047`、`largest_territory_swing=116`。
  - 原始回放核对：
    - 胜例（vs v64，seed `20261414`）round `26` 出现 `P0 Action [4,0,2,5,10]` 后建立领先；
    - 负例（vs v66，seed `20261316`）round `122` 出现 `P1 Action [4,17,2,4,6]` 但随后被反压。
- 结论标签：`neutral`。
  - 说明：结构简化目标达成（去掉分段阈值切换），但强度未提升（两个关键对位均 `50/100`），且波动未显著收敛。

### v69（`cpp_v69_overlay_followup_prune`）

- 设计假设：
  - `v68` 已做 overlay 池平滑上限，但仍对所有候选都执行 `my_follow` 深评估，导致高风险局面下计算链偏长且波动大；
  - 借鉴 Generals 的 threat-origin 连续筛选与 ANTWar 的 danger/reserved 预算收敛，在不增加状态机的前提下，用连续 `raw_drop` 门控跳过低收益 follow-up。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v69/ai_v69.cpp`，注册 ID：`cpp_v69_overlay_followup_prune`；
  - `OverlayTuning` 新增 `followup_raw_drop_cap` 与 `followup_skip_penalty`；
  - `choose_overlay_tuning(...)` 内按 `risk_alpha` 连续映射：
    - `followup_raw_drop_cap = 16 - 8*risk_alpha`
    - `followup_skip_penalty = 1.5 + 1.5*risk_alpha`
  - `select_best_move_overlay(...)` 中对非 base 且 `raw_drop` 超 cap 的候选跳过 `my_follow` 评估，仅施加轻惩罚后继续统一打分；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（`eval_20260305_030348`，规定脚本，14 核，400 局）：
    - `v69 vs v66 = 51/100`
    - `v69 vs v64 = 48/100`
    - `v69 vs v1 = 84/100`
    - `v69 vs v2 = 76/100`
  - replay（同 tag）：`rows=400`、`analyzed=400`、`missing=0`、`parse_errors=0`；
    - `v69 no_effect_rate=0.0567`；
    - 但高波动仍在：`largest_army_swing=1232`、`largest_territory_swing=151`。
  - 原始回放核对：
    - 胜例（vs v66，seed `20261317`）turning round `92`，`delta_army_lead_p0=+206`（p1 为 v69 受益）；
    - 负例（vs v64，seed `20261415`）turning round `18`，`delta_territory_lead_p0=-2`、`delta_army_lead_p0=-4`，早盘丢节奏。
- 结论标签：`neutral`。
  - 理由：该改动在 `v1/v2` 对位上有明显 gate 增益，但对当前生产 champion `v64` 仍为 `48/100`，尚不能作为晋升候选结论。

### v70（`cpp_v70_overlay_opening_subpressure`）

- 设计假设：
  - `v69` 的 follow-up 剪枝已降低部分无效深评估，但在“开局近距对抗 + 子将劣势”场景仍可能出现验证深度不足，导致早中盘节奏波动；
  - 借鉴 Generals 的 `threat_origin`（威胁来源连续化）与 ANTWar 的 `danger/reserved`（危险态预算收敛），把“开局子将压力”压缩为单一连续信号，直接驱动 overlay 预算，不新增状态机分支。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v70/ai_v70.cpp`，注册 ID：`cpp_v70_overlay_opening_subpressure`；
  - `choose_overlay_tuning(...)` 中新增：
    - `my_sub_count/enemy_sub_count -> sub_gap_signal`
    - `opening_signal = clamp((60-round)/60)`
    - `opening_sub_pressure = duel_close ? opening_signal * sub_gap_signal : 0`
  - 用 `opening_sub_pressure` 连续联动：
    - `base_anchor_penalty`、`max_raw_drop`、`base_reply_veto_slack`
    - `followup_raw_drop_cap`、`followup_skip_penalty`
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_033232`（seed=20260407，500 局）：
    - `v70 vs v69 = 52/100`
    - `v70 vs v66 = 46/100`
    - `v70 vs v64 = 51/100`
    - `v70 vs v1 = 74/100`
    - `v70 vs v2 = 70/100`
  - replay（同 tag）：
    - `rows=500`、`analyzed=500`、`missing=0`、`parse_errors=0`；
    - 波动仍高：`largest_army_swing=1047`、`largest_territory_swing=152`。
  - 原始回放核对（来自 `paths.matches`）：
    - 胜例（vs v66，seed `20262369`）turning round `149`，`delta_army_lead_p0=-211`（p1 为 `v70` 受益）；
    - 负例（vs v64，seed `20262458`）turning round `176`，`delta_army_lead_p0=-402`（p0 为 `v70` 终盘被反打）。
  - 与上一轮 `v69` 同量级 gate（`eval_20260305_030348`）相比（仅方向信号）：
    - 对 champion `v64`：`48/100 -> 51/100`；
    - 对 `v66`：`51/100 -> 46/100`。
  - 生产口径（唯一权威）`/www/autolab/runtime/latest.json`：
    - 当前 tag `eval_20260305_032841`，`champion.old/new = v64 -> v64`（未切换）；iter Elo 仅候选筛选。
- 结论标签：`neutral`。
  - 理由：对当前 champion 的 head-to-head 从 `48/100` 小幅提升到 `51/100`，但对 `v66` 回退到 `46/100`，且高波动问题未收敛；尚不满足 confirm 判优条件。

### v71（`cpp_v71_overlay_replyrisk_gate`）

- 设计假设：
  - `v70` 在 `v66` 对位回退（`46/100`）的主要风险来自 overlay 风险过滤的双阈值分支（`dominated` 与 `base_reply`）在领先局仍可能放行高波动切换；
  - 借鉴 Generals 的 `threat_origin` 连续威胁表达与 ANTWar 的 `global_state/reserved` 领先态预算收敛，将该过滤链改为单一连续风险闸门，并在领先时自动收紧预算。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v71/ai_v71.cpp`，注册 ID：`cpp_v71_overlay_replyrisk_gate`；
  - `choose_overlay_tuning(...)` 新增 `ahead_signal`（由 `territory_lead + army_lead` 连续映射）；
  - `ahead_signal` 直接收紧 `base_anchor_penalty/max_raw_drop/base_reply_veto_slack/base_reply_drop_scale`；
  - `select_best_move_overlay(...)` 中将双 veto 分支合并为：
    - `reply_risk = reply_surplus + 0.45*dominance_surplus - 1.25*threat_credit`
    - 只保留单一 `reply_risk > 0` 闸门；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_040307`（seed=20260408，600 局）：
    - `v71 vs v70 = 52/100`
    - `v71 vs v68(champion) = 48/100`
    - `v71 vs v66 = 54/100`
    - `v71 vs v64 = 51/100`
    - `v71 vs v1 = 79/100`
    - `v71 vs v2 = 83/100`
  - replay（同 tag）：
    - `rows=600`、`analyzed=600`、`missing=0`、`parse_errors=0`；
    - `v71 win_rate=0.6117`、`avg_rounds=125.88`、`no_effect_rate=0.0591`；
    - `largest_army_swing=1047`（高波动仍在）。
  - 原始回放核对（来自 `paths.matches`）：
    - 胜例（vs v66，seed `20262442`）turning round `179`，`delta_army_lead_p0=541`；
    - 负例（vs v68，seed `20261450`）turning round `179`，`delta_army_lead_p0=340`。
  - 生产口径（唯一权威）`/www/autolab/runtime/latest.json`：
    - 当前 tag `eval_20260305_035840`，`champion.old/new = v68 -> v68`（本 tag 未切换）；
    - 但近期 tag 出现过 `v64 -> v68` 切换，gauntlet 对手池口径风险需继续按生产规则判读。
- 结论标签：`neutral`。
  - 理由：`v71` 修复了 `v70` 对 `v66` 的回退并对 `v70` 本体有小幅优势，但对当前生产 champion `v68` 仍为 `48/100`，且尚无 `>=200` confirm 样本与波动收敛证据。

### v72（`cpp_v72_overlay_endgame_lock`）

- 设计假设：
  - `v71` 将风险过滤收敛到单一 `reply_risk` 后，对 `v66` 有修复，但终盘高 swing 仍明显，且在部分对位出现后程反转；
  - 借鉴 Generals 的连续威胁评分与 ANTWar 的 `global_state/reserved` 思路，把“领先终盘保守化”压缩为一个连续 `endgame_lock` 信号，避免新增离散状态机。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v72/ai_v72.cpp`，注册 ID：`cpp_v72_overlay_endgame_lock`；
  - `choose_overlay_tuning(...)` 新增：
    - `endgame_lock = ahead_signal * clamp((round-120)/60)`；
    - 并统一联动 `switch_margin/base_anchor_penalty/followup_raw_drop_cap/base_reply_veto_slack/base_reply_drop_scale`；
  - `select_best_move_overlay(...)` 在原单闸门上叠加：
    - `reply_risk += 0.60 * lock_penalty`（`lock_penalty=endgame_lock_signal*max(0,raw_drop-2)`）；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_043217`（seed=20260409，700 局）：
    - `v72 vs v71 = 53/100`
    - `v72 vs v69(champion) = 49/100`
    - `v72 vs v68 = 53/100`
    - `v72 vs v66 = 53/100`
    - `v72 vs v64 = 45/100`
    - `v72 vs v1 = 80/100`
    - `v72 vs v2 = 82/100`
  - replay（同 tag）：
    - `rows=700`、`analyzed=700`、`missing=0`、`parse_errors=0`；
    - `v72 win_rate=0.5929`、`avg_rounds=122.79`、`no_effect_rate=0.0589`；
    - `largest_army_swing=1047`（高波动仍未显著收敛）。
  - 原始回放核对（来自 `paths.matches`）：
    - 胜例（vs v69，seed `20262339`）turning round `137`，`delta_army_lead_p0=383`；
    - 负例（vs v69，seed `20261426`）turning round `130`，`delta_army_lead_p0=-290`；
    - 负例（vs v64，seed `20264483`）turning round `161`，`delta_army_lead_p0=184`（后程被反压）。
  - 生产口径（唯一权威）`/www/autolab/runtime/latest.json`：
    - 当前 tag `eval_20260305_042619`，`champion.old/new = v69 -> v69`（本 tag 未切换）；
    - 但近期存在 `v68 -> v69` 切换，gauntlet 对手池口径变化风险仍在。
- 结论标签：`neutral`。
  - 理由：对 `v71/v68/v66` 有小幅正向，但对当前 champion `v69` 仅 `49/100` 未过线，且 `v64` 对位退化为 `45/100`，尚不能作为晋升候选。

### v73（`cpp_v73_overlay_calm_endgame_lock`）

- 设计假设：
  - `v72` 的终盘锁定强度过高，导致对 `v64` 对位明显退化（`45/100`），推测“锁定”在非危险局面也过度抑制反击窗口；
  - 借鉴 Generals 的连续威胁刻画与 ANTWar 的危险态 reserved 预算，只在“领先 + 终盘 + 低风险”场景触发轻量稳定化，减少副作用。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v73/ai_v73.cpp`，注册 ID：`cpp_v73_overlay_calm_endgame_lock`；
  - `choose_overlay_tuning(...)` 引入：
    - `calm_signal = clamp((0.92 - risk_score)/0.50)`；
    - `endgame_stable_signal = ahead_signal * endgame_signal * calm_signal`；
    - 仅轻量联动 `switch_margin` 与 `base_anchor_penalty`，不再广泛收紧多项预算；
  - `select_best_move_overlay(...)`：
    - `lock_penalty = endgame_stable_signal * max(0, raw_drop - 4.0)`；
    - `reply_risk` 中 lock 权重从 `0.60` 下调到 `0.35`；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_050157`（seed=20260410，600 局）：
    - `v73 vs v72 = 48/100`
    - `v73 vs v69 = 48/100`
    - `v73 vs v64(champion) = 51/100`
    - `v73 vs v71 = 53/100`
    - `v73 vs v1 = 78/100`
    - `v73 vs v2 = 82/100`
  - replay（同 tag）：
    - `rows=600`、`analyzed=600`、`missing=0`、`parse_errors=0`；
    - `v73 win_rate=0.6000`、`avg_rounds=124.80`、`no_effect_rate=0.0584`；
    - `largest_army_swing=1047`（极端波动未收敛）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v73-v64` 胜例（seed `20263386`）turning round `175`，`impact_score=480`；
    - `v73-v64` 负例（seed `20262467`）turning round `149`，`impact_score=425`；
    - `v73-v72` 负例（seed `20261329`）turning round `158`，`impact_score=662`。
  - 与上一轮 `v72` 对比（方向信号）：
    - 对生产 champion `v64`：`45/100 -> 51/100`（回修）；
    - 对 `v69/v72`：均 `48/100`（未过线）。
- 结论标签：`neutral`。
  - 理由：终盘锁定软化修复了 `v64` 对位退化，但对 `v69/v72` 仍为负差且波动未收敛；当前仅可作为“局部修复候选”，不足以宣称整体变强。

### v74（`cpp_v74_overlay_calm_margin_only`）

- 设计假设：
  - `v73` 对 `v72/v69` 仍为 `48/100`，怀疑 `reply_risk` 内终盘 `lock_penalty` 仍导致过度抑制；
  - 借鉴 Generals 的连续威胁主干与 ANTWar 的 reserved 思路，尝试进一步减法：完全移除闸门内终盘附加惩罚，只保留预算侧轻量收紧。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v74/ai_v74.cpp`，注册 ID：`cpp_v74_overlay_calm_margin_only`；
  - `select_best_move_overlay(...)`：
    - 删除 `lock_penalty` 与 `reply_risk += w*lock_penalty`；
    - 仅保留 `reply_risk = reply_surplus + 0.45*dominance_surplus - 1.25*threat_credit`；
  - `choose_overlay_tuning(...)` 仍保留 `endgame_stable_signal` 对 `switch_margin/base_anchor_penalty` 的轻量联动；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_053212`（seed=20260411，700 局）：
    - `v74 vs v73 = 50/100`
    - `v74 vs v72(champion) = 49/100`
    - `v74 vs v69 = 49/100`
    - `v74 vs v71 = 51/100`
    - `v74 vs v64 = 44/100`
    - `v74 vs v1 = 79/100`
    - `v74 vs v2 = 82/100`
  - replay（同 tag）：
    - `rows=700`、`analyzed=700`、`missing=0`、`parse_errors=0`；
    - `v74 win_rate=0.5771`、`avg_rounds=120.72`、`no_effect_rate=0.0595`；
    - `largest_army_swing=1047`（未收敛）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v74-v72` 胜例（seed `20262340`）turning round `139`，`impact_score=383`；
    - `v74-v72` 负例（seed `20261426`）turning round `130`，`impact_score=290`；
    - `v74-v64` 负例（seed `20264483`）turning round `161`，`impact_score=192`。
  - 生产口径（唯一权威）`/www/autolab/runtime/latest.json`：
    - 当前 tag `eval_20260305_052402`，`champion.old/new = v70 -> v72`（发生切换，池口径风险升高）。
- 结论标签：`regression`。
  - 理由：去掉 `lock_penalty` 后关键对位未改善（`v72/v69` 仍 `49/100`），且 `v64` 回退到 `44/100`，不满足保留条件。

### v75（`cpp_v75_overlay_calm_micro_lock`）

- 设计假设：
  - `v74` 完全移除 `lock_penalty` 后出现回归（尤其 `v64=44/100`），说明终盘风险闸门不能彻底去除；
  - 借鉴 Generals 连续威胁主干与 ANTWar reserved 思路，采用“微量回滚”：保留单闸门，恢复极小权重 lock，避免 `v73` 的过度惩罚与 `v74` 的完全放开两端问题。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v75/ai_v75.cpp`，注册 ID：`cpp_v75_overlay_calm_micro_lock`；
  - `select_best_move_overlay(...)`：
    - `lock_penalty` 阈值从 `raw_drop-4.0` 放宽到 `raw_drop-5.0`；
    - `reply_risk` 中 lock 权重从 `0.35` 降为 `0.15`；
  - 保持 `reply_risk` 单一连续闸门与 `endgame_stable_signal` 预算联动，不新增状态机；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_060150`（seed=20260412，700 局）：
    - `v75 vs v74 = 52/100`
    - `v75 vs v73(champion) = 49/100`
    - `v75 vs v72 = 55/100`
    - `v75 vs v69 = 51/100`
    - `v75 vs v64 = 45/100`
    - `v75 vs v1 = 80/100`
    - `v75 vs v2 = 82/100`
  - replay（同 tag）：
    - `rows=700`、`analyzed=700`、`missing=0`、`parse_errors=0`；
    - `v75 win_rate=0.5914`、`avg_rounds=121.05`、`no_effect_rate=0.0598`；
    - `largest_army_swing=1047`（未收敛）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v75-v72` 胜例（seed `20262442`）turning round `179`，`impact_score=541`；
    - `v75-v73` 负例（seed `20261426`）turning round `130`，`impact_score=290`；
    - `v75-v64` 负例（seed `20264483`）turning round `161`，`impact_score=192`。
  - 生产口径（唯一权威）`/www/autolab/runtime/latest.json`：
    - 当前 tag `eval_20260305_055542`，`champion.old/new = v72 -> v73`（发生切换，池口径风险高）。
- 结论标签：`neutral`。
  - 理由：micro-lock 回滚修复了 `v74` 对 `v72/v69` 的退化，但对当前 champion `v73` 仍 `49/100`，且 `v64` 仍弱，不满足晋升条件。

### v76（`cpp_v76_overlay_prefilter_prune`）

- 设计假设：
  - `v75` 在 `v73/v72` 对位出现修复，但 `v64` 仍弱且 CPU 风险点集中在 `enemy_best/my_follow` 多次评估链；
  - 借鉴 Generals 的连续威胁排序与 ANTWar 的 reserved 预算收敛，在不增加状态机的前提下，把“高 drop 候选”提前剪掉，减少无效深评估。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v76/ai_v76.cpp`，注册 ID：`cpp_v76_overlay_prefilter_prune`；
  - `select_best_move_overlay(...)` 新增前置轻筛：
    - `precheck_raw_drop_cap = tuning.followup_raw_drop_cap + 3.0 - 2.0 * tuning.endgame_stable_signal`；
    - 非 base 且 `raw_drop > precheck_raw_drop_cap` 直接跳过，不进入 `enemy_best`；
  - 保持单一 `reply_risk` 闸门与原搜索结构，不新增分支状态；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_063214`（seed=20260413，700 局）：
    - `v76 vs v75 = 53/100`
    - `v76 vs v74(champion) = 50/100`
    - `v76 vs v73 = 55/100`
    - `v76 vs v69 = 50/100`
    - `v76 vs v64 = 43/100`
    - `v76 vs v1 = 80/100`
    - `v76 vs v2 = 82/100`
  - replay（同 tag）：
    - `rows=700`、`analyzed=700`、`missing=0`、`parse_errors=0`；
    - `v76 win_rate=0.5900`、`avg_rounds=122.86`、`no_effect_rate=0.0590`；
    - `largest_army_swing=1047`（未收敛）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v76-v74` 胜例（seed `20262340`）turning round `139`，`impact_score=383`；
    - `v76-v74` 负例（seed `20261426`）turning round `130`，`impact_score=290`；
    - `v76-v73` 胜例（seed `20262442`）turning round `179`，`impact_score=541`；
    - `v76-v64` 负例（seed `20264483`）turning round `161`，`impact_score=192`。
  - 生产口径（唯一权威）`/www/autolab/runtime/latest.json`：
    - 当前 tag `eval_20260305_062938`，`champion.old/new = v74 -> v74`（本 tag 未切换；但近期切换风险仍在）。
- 结论标签：`regression`。
  - 理由：前置轻筛对 `v73` 对位有收益且未拖累 `v74`，但对关键基线 `v64` 进一步回退到 `43/100`，当前不可作为晋级候选。

### v77（`cpp_v77_overlay_source_tighten`）

- 设计假设：
  - `v76` 的前置轻筛虽改善 `v73`，但 `v64` 仍弱；且结构上新增了额外剪枝分支；
  - 借鉴 Generals 的 threat-source 连续威胁与 ANTWar 的 danger/reserved 收敛，回到 `v75` 主干，通过 source-pressure 直接收紧 reply 预算，尝试在不新增分支的情况下修复 `v64`。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v77/ai_v77.cpp`，注册 ID：`cpp_v77_overlay_source_tighten`；
  - `choose_overlay_tuning(...)` 增加两条连续回调：
    - `base_reply_veto_slack -= 2.5 * source_pressure`
    - `base_reply_drop_scale -= 0.10 * source_pressure`
  - 不继承 `v76` 的 `precheck_raw_drop_cap` 分支，保持单闸门结构；
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_070231`（seed=20260414，800 局）：
    - `v77 vs v76 = 53/100`
    - `v77 vs v75 = 51/100`
    - `v77 vs v74 = 53/100`
    - `v77 vs v73 = 51/100`
    - `v77 vs v69 = 41/100`
    - `v77 vs v64 = 51/100`
    - `v77 vs v1 = 82/100`
    - `v77 vs v2 = 79/100`
  - replay（同 tag）：
    - `rows=800`、`analyzed=800`、`missing=0`、`parse_errors=0`；
    - `v77 win_rate=0.5763`、`avg_rounds=117.01`、`no_effect_rate=0.0595`；
    - `largest_army_swing=1047`（仍未收敛）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v77-v74` 胜例（seed `20262442`）turning round `179`，`impact_score=541`；
    - `v77-v74` 负例（seed `20262467`）turning round `127`，`impact_score=446`；
    - `v77-v69` 负例（seed `20264455`）turning round `156`，`impact_score=473`；
    - `v77-v64` 胜例（seed `20266406`）turning round `166`，`impact_score=507`。
  - 生产口径（唯一权威）`/www/autolab/runtime/latest.json`：
    - 当前 tag `eval_20260305_065755`，`champion.old/new = v74 -> v71`（发生切换，池口径风险高）。
- 结论标签：`neutral`。
  - 理由：source-pressure 收紧修复了 `v64` 并改善 `v74`，但对 `v69` 出现大幅回归且未覆盖新生产 champion `v71` 的直接对位。

### v78（`cpp_v78_overlay_source_reserve_release`）

- 设计假设：
  - `v77` 对 `v69` 回归（`41/100`）的主因是 source-pressure 对 reply 预算收紧过强，压制了落后态反打；
  - 借鉴 Generals 的 `threat_origin` 连续威胁建模与 ANTWar 的 `global_state/reserved`，将 source 风险压缩为一个 `reserve_signal`，并在落后态释放 reserve，减少过保守副作用。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v78/ai_v78.cpp`，注册 ID：`cpp_v78_overlay_source_reserve_release`；
  - `choose_overlay_tuning(...)`：
    - 新增 `behind_signal = max(0, -lead_signal)`；
    - 新增 `reserve_signal = source_pressure * (0.30 + 0.70 * ahead_signal)`；
    - 新增 `reserve_signal *= (1.0 - 0.85 * behind_signal)`；
    - 仅保留 `base_reply_veto_slack -= 2.2 * reserve_signal`，移除 `v77` 的 source 对 `base_reply_drop_scale` 直接收紧。
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_073355`（seed=20260415，1000 局）：
    - `v78 vs v77 = 52/100`
    - `v78 vs v76 = 50/100`
    - `v78 vs v75 = 54/100`
    - `v78 vs v74 = 50/100`
    - `v78 vs v73(champion) = 40/100`
    - `v78 vs v71 = 52/100`
    - `v78 vs v69 = 53/100`
    - `v78 vs v64 = 52/100`
    - `v78 vs v1 = 80/100`
    - `v78 vs v2 = 81/100`
  - replay（同 tag）：
    - `rows=1000`、`analyzed=1000`、`missing=0`、`parse_errors=0`；
    - `v78 win_rate=0.5640`、`avg_rounds=113.32`、`no_effect_rate=0.0607`；
    - `largest_army_swing=1062`（极端波动未收敛）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v78-v69` 负例（seed `20266518`）turning round `139`，`impact_score=320`；
    - `v78-v69` 胜例（seed `20267422`）turning round `95`，`impact_score=215`；
    - `v78-v73` 负例（seed `20264455`）turning round `156`，`impact_score=473`；
    - `v78-v71` 胜例（seed `20265476`）turning round `149`，`impact_score=188`。
  - 与 `v77` 对比：
    - 关键修复：`v69` 对位 `41/100 -> 53/100`；
    - 关键退化：`v73` 对位 `51/100 -> 40/100`。
- 结论标签：`regression`。
  - 理由：虽然修复了 `v69` 并保持 `v71/v64` 小幅优势，但对当前生产 champion `v73` 在 `>=100` 样本下显著落后，不满足晋级条件。

### v79（`cpp_v79_overlay_risk_weighted_release`）

- 设计假设：
  - `v78` 通过落后释放 reserve 修复了 `v69`，但对 `v73` 出现明显退化（`40/100`）；
  - 借鉴 Generals 的连续威胁源建模与 ANTWar 的 `danger/reserved`，将 behind 释放改成风险加权释放：高风险场景保留 reserve，低风险才释放，尝试在不增分支的前提下同时兼顾 `v73` 与 `v69`。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v79/ai_v79.cpp`，注册 ID：`cpp_v79_overlay_risk_weighted_release`；
  - `choose_overlay_tuning(...)`：
    - 保留 `reserve_signal = source_pressure * (0.30 + 0.70 * ahead_signal)`；
    - 新增 `release_signal = 0.85 * behind_signal * (0.35 + 0.65 * (1.0 - risk_alpha))`；
    - `reserve_signal *= (1.0 - clamp(release_signal, 0.0, 0.90))`；
    - 继续仅作用于 `base_reply_veto_slack`，不新增状态机。
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_080229`（seed=20260416，1100 局）：
    - `v79 vs v78 = 54/100`
    - `v79 vs v77 = 51/100`
    - `v79 vs v76 = 54/100`
    - `v79 vs v75(champion-prod) = 50/100`
    - `v79 vs v74 = 40/100`
    - `v79 vs v73 = 53/100`
    - `v79 vs v71 = 54/100`
    - `v79 vs v69 = 56/100`
    - `v79 vs v64 = 56/100`
    - `v79 vs v1 = 83/100`
    - `v79 vs v2 = 77/100`
  - replay（同 tag）：
    - `rows=1100`、`analyzed=1100`、`missing=0`、`parse_errors=0`；
    - `v79 win_rate=0.5709`、`avg_rounds=113.57`、`no_effect_rate=0.0615`；
    - `largest_army_swing=1062`（高波动仍未收敛）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v79-v73` 胜例（seed `20265501`）turning round `95`，`impact_score=171`；
    - `v79-v73` 负例（seed `20266392`）turning round `148`，`impact_score=354`；
    - `v79-v69` 胜例（seed `20268419`）turning round `157`，`impact_score=603`；
    - `v79-v69` 负例（seed `20267520`）turning round `177`，`impact_score=428`；
    - `v79-v71` 胜例（seed `20267422`）turning round `95`，`impact_score=215`。
  - 与 `v78` 对比：
    - 主修复：`v73` 从 `40/100 -> 53/100`；
    - 持续增益：`v69` 从 `53/100 -> 56/100`；
    - 新副作用：`v74` 回退到 `40/100`。
- 结论标签：`neutral`。
  - 理由：风险加权释放修复了 `v73` 并保持 `v69/v71/v64` 正差，但对现生产 champion `v75` 仅 `50/100`，且 `v74` 出现明显回退，仍需 confirm 样本再判优。

### v80（`cpp_v80_overlay_release_time_decay`）

- 设计假设：
  - `v79` 修复了 `v73` 与 `v69`，但对 `v74` 明显回退，且后期高波动未收敛；
  - 借鉴 Generals 的连续 threat-source 主干与 ANTWar 的 `global_state/reserved` 后期策略切换，将“落后释放 reserve”改成随回合衰减，尝试不加分支地降低后期过度释放。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v80/ai_v80.cpp`，注册 ID：`cpp_v80_overlay_release_time_decay`；
  - `choose_overlay_tuning(...)`：
    - 保留 `reserve_signal = source_pressure * (0.30 + 0.70 * ahead_signal)`；
    - 新增 `release_window = 0.20 + 0.80 * (1.0 - endgame_signal)`；
    - `release_signal = 0.85 * behind_signal * (0.35 + 0.65 * (1.0 - risk_alpha)) * release_window`；
    - `reserve_signal *= (1.0 - clamp(release_signal, 0.0, 0.90))`，仍仅作用于 `base_reply_veto_slack`。
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate-A（规定脚本）`eval_20260305_083630`（seed=20260417，1200 局）：
    - `v80 vs v79 = 54/100`
    - `v80 vs v78 = 51/100`
    - `v80 vs v77 = 53/100`
    - `v80 vs v76 = 50/100`
    - `v80 vs v75 = 39/100`
    - `v80 vs v74 = 53/100`
    - `v80 vs v73 = 55/100`
    - `v80 vs v71 = 56/100`
    - `v80 vs v69 = 51/100`
    - `v80 vs v64 = 50/100`
  - 生产切换后 h2h gate-B（规定脚本）`eval_20260305_090453`（seed=20260418，400 局）：
    - `v80 vs v70(champion-prod) = 54/100`
    - `v80 vs v75 = 53/100`
    - `v80 vs v73 = 55/100`
    - `v80 vs v79 = 52/100`
  - replay（latest=`090453`）：
    - `rows=400`、`analyzed=400`、`missing=0`、`parse_errors=0`；
    - `v80 win_rate=0.535`、`avg_rounds=106.28`、`no_effect_rate=0.0616`；
    - `largest_army_swing=1047`（仍高）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v80-v70` 胜例（seed `20261340`）turning round `116`，`impact_score=115`；
    - `v80-v70` 负例（seed `20260464`）turning round `150`，`impact_score=61`；
    - `v80-v75` 胜例（seed `20261471`）turning round `143`，`impact_score=253`；
    - `v80-v75` 负例（seed `20261457`）turning round `130`，`impact_score=133`；
    - `v80-v73` 胜例（seed `20263388`）turning round `129`，`impact_score=91`。
  - 与 `v79` 对比（共同对手）：
    - 改善：`v74` 从 `40/100 -> 53/100`；
    - 回退：`v69` 从 `56/100 -> 51/100`、`v64` 从 `56/100 -> 50/100`；
    - `v75` 跨两轮 gate 出现 `39/100` 与 `53/100` 分歧，稳定性不足。
- 结论标签：`neutral`。
  - 理由：在生产 champion 已切换到 `v70` 后，`v80` 对 `v70` 给出 `54/100` 的正向 gate 信号，但仍未达 confirm 门槛；
  - 同时对 `v75` 出现跨 seed 冲突，且波动指标偏高，暂不满足“明确优于多个老版本”的声明条件。

### v81（`cpp_v81_overlay_deficit_late_release`）

- 设计假设：
  - `v80` 对当前 champion 系（`v69/v70`）只到弱正差，且后期释放衰减在部分对局中出现“落后时反打预算不足”；
  - 借鉴 Generals 的连续 threat/impact 信号与 ANTWar 的 `global_state/reserved` 预算机制，在不增加状态机的前提下，为落后态补一条后期释放底线，提升 comeback 稳定性。
- 关键机制：
  - 新版本目录：`/www/ai_cpp/v81/ai_v81.cpp`，注册 ID：`cpp_v81_overlay_deficit_late_release`；
  - `choose_overlay_tuning(...)`：
    - 保留 `v80` 的 `reserve_signal` 与 `release_signal` 主线；
    - 新增 `late_release_floor = 0.20 + 0.45 * behind_signal`；
    - `release_window = max(0.20 + 0.80*(1-endgame_signal), late_release_floor)`；
    - 其余结构不变，保持单闸门 + 连续量。
  - 搜索硬约束保持：`CLOCK_THREAD_CPUTIME_ID` + `kSearchStepBudgetMs=200` + `hard_cutoff_hit` 回退。
- 评测证据：
  - iter gate（规定脚本）`eval_20260305_093220`（seed=20260419，1000 局）：
    - `v81 vs v80 = 56/100`
    - `v81 vs v79 = 54/100`
    - `v81 vs v75 = 53/100`
    - `v81 vs v73 = 52/100`
    - `v81 vs v72 = 39/100`
    - `v81 vs v70 = 54/100`
    - `v81 vs v69 = 55/100`
    - `v81 vs v64 = 53/100`
    - `v81 vs v1 = 79/100`
    - `v81 vs v2 = 81/100`
  - replay（同 tag）：
    - `rows=1000`、`analyzed=1000`、`missing=0`、`parse_errors=0`；
    - `v81 win_rate=0.576`、`avg_rounds=115.71`、`no_effect_rate=0.0602`；
    - `largest_army_swing=1062`（仍高）。
  - 原始回放核对（来自 `paths.matches`）：
    - `v81-v69` 胜例（seed `20267422`）turning round `95`，`impact_score=215`；
    - `v81-v69` 负例（seed `20267433`）turning round `130`，`impact_score=331`；
    - `v81-v70` 胜例（seed `20266423`）turning round `143`，`impact_score=192`；
    - `v81-v72` 负例（seed `20264455`）turning round `156`，`impact_score=473`；
    - `v81-v80` 胜例（seed `20261343`）turning round `148`，`impact_score=421`。
  - 与 `v80` 对比：
    - 改善：`v69` 从 `51/100 -> 55/100`，`v80` 直面对位 `56/100`；
    - 风险：对 `v72` 出现明显回退 `39/100`。
- 结论标签：`neutral`。
  - 理由：对当轮 champion `v69` 为 `55/100`、回合末 champion `v79` 为 `54/100`（均仅 gate 信号），但对 `v72` 显著负差且波动上界仍高，暂不具备稳定判优条件。

#### v81 补注（生产口径刷新）

- 回合末复读生产 `latest.json`：`eval_20260305_092917`，champion 已从 `v69` 切到 `v79`（`v69 -> v79`）。
- 本轮已覆盖 `v81 vs v79 = 54/100`（`>=100` gate），仍未达 `>55%` 与 `>=200` confirm 门槛。
- 因生产口径连续切换，本条目结论保持 `neutral` 不变。
