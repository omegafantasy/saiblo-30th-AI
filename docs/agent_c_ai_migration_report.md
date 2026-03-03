# Agent C：基于 past_AIs 的 C++ AI 迁移报告

## 目标

在新规则（`Ant-Game` 当前实现）下，尽可能复刻 `past_AIs/Generals-AI` 的策略思想，并保持根目录独立可运行。

## 迁移对象

- 旧项目：`/www/past_AIs/Generals-AI/main.cpp`
- 新实现：`/www/ai_cpp_v1/ai_v1.cpp`

## 已迁移的核心策略思想

1. 威胁评估（threat map）
- 估计敌方多步可达区域风险（按敌方机动科技映射 2/3/5 步）。
- 用于主将保命阈值与移动方向评分。

2. 多步行动预算
- 按机动科技层级执行多次军队指令，而非单步贪心。

3. 目标价值排序
- 攻击优先级：敌主将 > 敌副将 > 中立副将/农夫 > 一般格子。
- 结合占领收益、送兵成本、与敌主将距离进行综合评分。

4. 经济决策迁移
- 主将升级（产量/防御/机动）策略化触发。
- 机动科技优先（旧 AI 的节奏偏好）。
- 前线征召副将（`[7,x,y]`）而非仅主将邻格兜底。

5. 规则细节兼容
- 攻防倍率估计：将军技能持续效果 + 攻击强化超武区域效果。
- 超武状态限制（Transmission/TimeStop）下的行动可行性判断。

## 本地验证

### 编译

```bash
make -C /www/ai_cpp_v1 clean all
```

结果：成功。

### 对局评测

1) 对 `greedy`：

```bash
python /www/eval_cpp_local.py --games 12 --rounds 120 --opponent greedy --swap-seats --jobs 1
```

结果：`24/24` 胜，`win_rate=1.0`

2) 对 `random_safe`：

```bash
python /www/eval_cpp_local.py --games 10 --rounds 140 --opponent random_safe --swap-seats --jobs 1
```

结果：`20/20` 胜，`win_rate=1.0`

3) 对 `main`：

- 评测脚本在加载 `AI/ai_main.py` 时触发环境依赖问题（`ModuleNotFoundError: No module named 'ai'`），非本次 C++ AI 逻辑回归失败。

## 结论

- 新版 `ai_cpp_v1.cpp` 已从“单步邻域贪心”升级为“接近旧 Generals-AI 的多因素启发式”。
- 在当前本地基线对手上，表现显著提升并稳定可运行。
