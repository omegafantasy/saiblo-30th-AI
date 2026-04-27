# Game1 Lure Strategy

这份文档记录当前 Game1 的高层策略方向，以及当前 baseline / v2 已经落实到代码里的部分。

参考 replay：

- `Game1/good.json`

## 1. 策略目标

当前 Game1 的核心不是“尽量把普通蚂蚁全防住”，而是：

- 先建立并维护 `C1` 主锚点
- 把主要精力放在战斗蚂蚁控制上
- 用外圈廉价塔反复引诱战斗蚂蚁偏离基地
- 在战斗蚂蚁即将白拆 lure 塔前主动卖塔回收
- 在合适时机用 `Lightning Storm` 清理积累的战斗蚂蚁

也就是说，lure 塔首先是路线控制工具，不是输出塔。

## 2. 来自 `good.json` 的核心结论

`good.json` 对当前策略方向的启发是：

- `C1` 可以作为长期主锚点
- 外圈少量固定槽位可以反复承担 lure 作用
- “建 lure -> 引走战斗蚁 -> 卖 lure” 的净损耗通常很小
- 真正重要的是把战斗蚁控制在离基地更远的位置
- 普通蚂蚁前期允许漏，不应为此过度操作

因此当前更合理的大方向是：

- 少操作
- 重战斗蚁控制
- 重卖塔回收
- 闪电作为收束工具而不是常规输出工具

## 3. 当前代码已实现的部分

当前 baseline / v2 已经落实了以下几点：

- `base` 与 `lure` 分离建模
- lure 结构默认为“最多一个外部 lure”
- 若 lure 被战斗蚁贴近，会优先执行强制卖塔
- 当前 rollout 中对所有己方塔都保留“战斗蚁贴身则强制回收”的 reactive 逻辑
- 若需要同回合 `sell + build`，会保证“先拆后建”
- 若同回合需要拆多座塔，会优先拆当前血量更高的塔
- 闪电作为独立候选搜索
- 闪电候选当前只包含单次 `Lightning Storm`，不与 `base/lure` 或降级/拆塔组合
- 闪电中心使用棋盘中心半径 5 的 91 个中心做 UCB 搜索，总预算由 `lightning_ucb_total_rollouts` 控制
- future rollout 不再完整生成主动 `base × lure`，只保留贴身回收这类应急 reactive 动作

## 4. 当前代码刻意没有实现的部分

当前 baseline / v2 仍然没有把 lure 策略做到最终形态。

暂未实现：

- 更复杂的同回合 op-list 模板
- `sell lure -> lightning -> build lure` 这种显式三段链
- `downgrade/sell -> lightning` 这种闪电前置回收链
- 主动 `EMP / Deflector / Evasion`，后续从 v3 开始探索
- 更强的 lure 路径级控制
- 基于位置表的 lure 槽位偏好学习

另外，当前 lure 建塔位置已经不再做额外启发式打分：

- 不按离战斗蚁近远加分
- 不按离基地近远加分
- 不做前几名裁剪

这样做的目的，是让 lure 位置完全由 rollout 终点评估来决定。

## 5. 当前 `C1` 路线

当前 `C1` 路线仍是强结构化的：

- `C1` 为空时，考虑 `build C1` 与 `build C1 -> Heavy`
- `C1 Basic` 时：
  - 可升 `Heavy`
  - 钱较多时允许转 `Quick`
- `C1 Quick` 时允许转 `Sniper`
- `C1 Heavy` 在过渡期可通过 `downgrade -> Quick` 切线
- `C1 Sniper` 成型后，其他 base 槽位的二级塔候选放开到 `Heavy / Quick / Mortar`
- 当前还支持结构化 followup：
  - `build slot -> upgrade allowed level-2 tower`
  - `Basic -> Quick -> Sniper`
  - `Heavy(C1) -> downgrade -> Quick`
  - `downgrade/sell source to bottom -> build another base slot`
  - `downgrade/sell source to bottom -> build another base slot -> upgrade allowed level-2 tower`

这里仍保留一个显式金币阈值，用来控制 `Heavy` 与 `Quick / Sniper` 路线切换。

## 6. 当前 lure 结构

当前 lure 的动作模板只有三类：

- `hold`
- `sell`
- `sell + build`

以及在“没有 lure”时：

- `build`

这套结构的含义是：

- lure 是消耗品
- lure 不追求长期留场
- 只要预期价值不足，就可以直接卖

## 7. 当前闪电角色

当前闪电的定位是：

- 独立候选
- 偏战斗蚁应急
- 兼顾敌方塔伤害
- 不与 `base/lure` 相乘
- 不带前置 `downgrade / sell`
- 每个合法中心是一个 arm，UCB 在所有 arm 上分配 rollout
- v2 默认合法中心为距棋盘中心 `(9,9)` 不超过 5 的 91 个格子

当前闪电启发主要看：

- rollout 后相对无闪电对照组减少的战斗蚁 threat
- 破盾收益
- 敌方超武窗口
- 对敌方塔造成的等效价值伤害

不再额外奖励普通蚂蚁数量。

## 8. 当前策略约束

当前 baseline / v2 还有几个明确约束：

- 当前只搜索单回合根动作，不再做旧版“两回合计划”
- 例外：base 主线保留少量显式 followup，用于表达建后升级、`Quick -> Sniper` 与 `Heavy(C1) -> Quick` 转线
- root 组合使用严格合法性判断
  - 组合里有一步非法，整组直接丢弃
- rollout 后续回合仅使用贴身强制回收，不再主动贪心生成完整 `base × lure`
- 所有直接影响评分的参数应统一暴露在 `lure_strategy_params.hpp`

当前根节点候选集合实际是：

- `hold`
- 单独 `base`
- 单独 `lure`
- `recycle-only base + lure`
- 单独 `lightning`

它不是完整的 `base × lure × lightning`。

## 9. 后续优化方向

当前值得继续推进的，不是再加更多零散 heuristic，而是：

- 继续强化战斗蚁控制
- 继续降低无意义操作
- 提高对 lure 卖塔时机的判断质量
- 提高闪电与 lure 联动质量
- 再决定是否逐步把主动超武和 `Medic` 纳入搜索

当前判断一个改动是否有价值，优先看：

- replay
- `ai*.stderr.log` 中的候选分解
- `sdk_lure_inspector` / simviz 的单回合候选与 sample trace
- `sdk_defense_parity` 的轻量模拟与 native 多 rollout 对拍
- 256 回合 self-play 的 HP / 经济 / 操作频率 / 时延统计
