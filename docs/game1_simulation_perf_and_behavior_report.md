# Game1 Simulation Performance and Behavior Report

本报告由 `/www/Game1/Ant-Game/tools/generate_sim_report.py` 自动生成。

## Reference Cells

- Player `1` own-half sample cell: `11,9`
- Player `1` enemy-half sample cell: `7,9`

## One-Step Survey

| Case | Mean top1 | Median top1 | Mean entropy | P(top1>=0.85) |
| --- | ---: | ---: | ---: | ---: |
| DEFAULT / uniform / none | 0.8547 | 1.0000 | 0.2015 | 0.7093 |
| DEFAULT / center_bias / pair | 0.9926 | 1.0000 | 0.0119 | 0.9826 |
| DEFAULT / lane_bias / cluster | 0.9515 | 1.0000 | 0.0719 | 0.8953 |
| CONSERVATIVE / uniform / none | 1.0000 | 1.0000 | -0.0000 | 1.0000 |
| CONTROL_FREE / uniform / none | 1.0000 | 1.0000 | -0.0000 | 1.0000 |
| BEWITCHED / uniform / none | 0.8049 | 0.9267 | 0.4059 | 0.7093 |
| RANDOM / uniform / none | 0.3527 | 0.3333 | 1.0673 | 0.0000 |

结论：`DEFAULT` 在结构化信息素下非常尖锐，`RANDOM` 才是真正高熵源。`CONSERVATIVE/CONTROL_FREE` 基本可视为确定性。

## Multi-Round Diffusion

| Case | Round 0 top cell | Round 3 top cell | Round 5 top cell | Outcome summary |
| --- | --- | --- | --- | --- |
| DEFAULT / empty | `11,9` 1.000 | `8,10` 0.504 | `7,9` 1.000 | ALIVE:512 |
| RANDOM / empty | `11,9` 1.000 | `10,9` 0.217 | `10,9` 0.184 | ALIVE:512 |
| BEWITCHED retreat / empty | `7,9` 1.000 | `9,8` 0.365 | `11,9` 0.711 | ALIVE:512 |
| DEFAULT / naive_control | `11,9` 1.000 | `8,10` 0.504 | `?,?` 0.000 | removed:512 |

结论：`DEFAULT` 前几回合通常仍是窄分布，`RANDOM` 扩散快得多，控制塔布局会显著提前打散/移除前线质量。

## Teleport Effect

| Case | start_round | teleport_like | mean displacement | own-half landing |
| --- | ---: | ---: | ---: | ---: |
| DEFAULT own-half control | 8 | 0.0000 | 1.000 | 1.0000 |
| DEFAULT own-half teleport | 9 | 0.9883 | 5.512 | 1.0000 |
| RANDOM own-half control | 8 | 0.0000 | 1.000 | 1.0000 |
| RANDOM own-half teleport | 9 | 0.9883 | 5.512 | 1.0000 |
| CONTROL_FREE own-half teleport | 9 | 0.0000 | 1.000 | 1.0000 |
| DEFAULT enemy-half control | 8 | 0.0000 | 1.000 | 0.0000 |
| DEFAULT enemy-half teleport | 9 | 0.9824 | 6.832 | 0.3057 |

结论：

- `DEFAULT` own-half 在 `round 9 -> 10` 的 teleport_like rate: `98.8%`，而 `round 8 -> 9` 对照组为 `0.0%`。
- `RANDOM` own-half 在 teleport 回合同样会被大幅重置：`98.8%`。
- `CONTROL_FREE` 在 teleport 回合保持免疫：`0.0%`。

## Python Engine Throughput

| Case | Move eval/s | Rounds/s | Match-equiv/s (500 rounds) |
| --- | ---: | ---: | ---: |
| empty / 4 ants per player | 22252 | 7437 | 14.875 |
| empty / 8 ants per player | 21128 | 4006 | 8.012 |
| naive_core / 8 ants per player | 21726 | 3248 | 6.496 |
| naive_core / 12 ants per player | 17495 | 4503 | 9.006 |

## C++ Kernel Throughput

| Kernel | Ants/player | Throughput |
| --- | ---: | ---: |
| Exact move | 4 | 4937075 eval/s |
| Exact move | 8 | 5221143 eval/s |
| Exact move | 16 | 3899332 eval/s |
| ExpectedFront 4-step | 4 | 686.5 calls/s, 3432.6 forecast-rounds/s |
| ExpectedFront 4-step | 8 | 412.1 calls/s, 2060.4 forecast-rounds/s |
| ExpectedFront 4-step | 16 | 227.3 calls/s, 1136.3 forecast-rounds/s |

## Practical Guidance

- `DEFAULT / CONSERVATIVE / CONTROL_FREE` 可以优先走短视野 `ExpectedFront`。
- `RANDOM` 仍然应保留单独采样预算。
- `teleport` 是第 `10` 回合最主要的不连续项，任何超过 `4` 回合的格点级预测都应在这里降级为风险估计。
- 现阶段最可靠的工程切法仍是：`一步精确分布 + 3~4 回合 ExpectedFront + 关键 RANDOM 小样本 Monte Carlo`。
