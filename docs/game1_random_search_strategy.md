# Game1 Current Search Baseline

这份文档描述当前 `Game1/antgame_ai_cpp/cpp_heavy_baseline` 实际使用的搜索与估值逻辑。

说明：

- 文件名沿用历史命名
- 当前实现已经不是旧版 `random_search_baseline.hpp` 的两回合搜索
- 当前真实入口是 `antgame_sdk/lure_strategy.hpp`

## 1. 当前动作分解

每回合动作被拆成三部分：

- `base`
- `lure`
- `lightning`

根节点候选集合为：

- `base × lure`
- `lightning`

也就是：

- 常规防守操作由 `base` 与 `lure` 组合
- 闪电是独立候选，不与 `base/lure` 相乘

## 2. 当前允许的 base 动作

`base` 只围绕靠近基地的固定槽位展开。

当前结构：

- 永远保留 `base_hold`
- 若 `C1` 为空，只考虑 `build C1`
- 若 `C1` 不是 `Sniper`，只考虑：
  - `Basic -> Heavy` 或 `Basic -> Quick`
  - `Heavy -> downgrade`
  - `Quick -> Sniper`
- 若 `C1` 已经是 `Sniper`，才开放：
  - `L1 / R1 / C2` 的建塔
  - `Basic -> Quick`
  - `Quick -> Sniper`

当前这些非 `hold` 的 base 动作没有额外 heuristic 奖励，只有：

- `base_hold_bonus`
- `c1_build_bonus`

## 3. 当前允许的 lure 动作

当前只允许单 lure 结构。

具体规则：

- 永远保留 `lure_hold`
- 若存在 lure 塔且有战斗蚁贴近到给定距离内，直接只生成“强制卖塔”
- 若当前没有 lure 塔：
  - 所有合法 lure 槽位都生成 `build`
  - 不做额外位置打分
- 若当前已有 lure 塔：
  - 生成该 lure 的 `sell`
  - 对所有其他合法 lure 槽位生成 `sell + build`
  - 不做额外位置打分

当前不会再对 lure 建塔位置做：

- 距战斗蚁加分
- 距基地远近加分
- 候选前几名裁剪

也就是说，lure 的位置优劣完全交给 rollout 终点评估决定。

## 4. 当前闪电候选

闪电单独生成。

当前流程：

- 若冷却或金币不足，则不生成闪电候选
- 否则对全图合法格子打分
- 排除离地图边界过近的位置
- 再做簇去重，只保留有限个中心

当前闪电启发只考虑：

- 对敌方塔的等效价值伤害
- 当前敌方超武窗口
- 覆盖到的战斗蚁 threat
- 覆盖到带盾战斗蚁的破盾收益

不再给：

- 普通蚂蚁 presence 额外奖励
- 战斗蚁纯数量奖励

## 5. 合法性与操作顺序

当前所有组合操作都使用“严格合法”规则：

- 要么整组操作全部合法
- 要么整组候选直接丢弃

不会再出现：

- 一个组合里某一步非法
- 然后被静默裁成子集继续搜索

同回合操作顺序还做了统一优化：

- `DowngradeTower` 永远先于 `BuildTower`
- 若有多个 `DowngradeTower`，按当前塔血量从高到低执行

这样可以稳定利用：

- 先拆后建带来的金币与塔数优势
- 多拆时先拆高血塔带来的更高返还

## 6. Rollout

每个根节点候选都独立做 Monte Carlo rollout。

当前设置：

- 普通候选 horizon: `search_horizon`
- 闪电候选 horizon: `lightning_horizon`
- 每个候选 rollout 次数: `rollout_count`

rollout 中未来回合不是 `hold`，而是每回合再调用一次轻量 reactive 控制器：

- 重新生成当前模拟态下的 `base` 候选
- 重新生成当前模拟态下的 `lure` 候选
- 在所有严格合法的 `base × lure` 组合中
- 直接取 heuristic 最大的那个作为该回合动作

因此当前 rollout 是：

- 根节点用“搜索 + 终点评估”
- 后续回合用“反应式贪心控制器”

## 7. 终点评估

终点评估只看以下几项：

- 基地血量
- 己方塔全部拆完后的可回收价值
- 当前金币
- 普通蚂蚁 threat
- 战斗蚂蚁 threat

其中：

- 普通蚂蚁 threat 只看离基地距离与血量比例
- 战斗蚂蚁 threat 取“对基地威胁”和“对己方塔钱的威胁”的较大者
- 战斗蚂蚁的威胁缩放还会受到 `Random` / `Bewitched` 行为影响

当前 `combat threat` 不再只看 `C1/L1/R1/C2/C3` 这些塔位，而是对所有己方存活塔统一估值。

## 8. 参数入口

当前所有直接影响策略打分的参数，统一放在：

- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_params.hpp`

当前实现里，`lure_strategy.hpp` 不应再包含未暴露到参数文件的隐藏评分常数。

## 9. 代码入口

关键文件：

- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy.hpp`
- `Game1/antgame_cpp_sdk/include/antgame_sdk/lure_strategy_params.hpp`
- `Game1/antgame_ai_cpp/cpp_heavy_baseline/ai_cpp_heavy_baseline.cpp`

辅助工具：

- `Game1/antgame_ai_cpp/tools/eval_cpp_selfplay.py`
- `Game1/antgame_ai_cpp/tools/analyze_selfplay_batch.py`

## 10. 当前局限

当前实现仍然是简化 baseline，不代表最终策略。

主要局限：

- `base` 和 `lure` 仍是模板化候选，不是完整同回合 op-list 生成
- 主动 `EMP/Deflector/Evasion` 还没纳入搜索
- lure 的自适应性主要来自“贴近即卖”和未来回合 reactive 控制器，尚未发展成更强的路径级控制
- `C1` 路线切换仍保留一个显式金币阈值
- 对普通蚂蚁和战斗蚂蚁的估值比例仍需要继续校准
