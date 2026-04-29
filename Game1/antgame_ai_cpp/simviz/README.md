# Game1 SimViz

`simviz/` 提供一个适配无头服务器的本地可视化工具，用于做 Game1 的定点分析。

当前实现分成两层：

- Python 本地 web server
  - 负责静态页面、地图几何、replay 读取、API 转发
- C++ inspector
  - 负责按当前 v3 `lure_strategy` 在线复算候选行动
  - 负责导出某个候选下的 rollout 样本与单样本 trace
  - 与当前 `DefenseSimulator`、root plan 生成、首回合重点蚂蚁采样逻辑保持同步

## 启动

```bash
cd /root/autodl-tmp/saiblo_iter
Game1/antgame_ai_cpp/simviz/run_simviz.sh --host 127.0.0.1 --port 8765
```

默认仅监听本机回环地址。

服务器无公网 IP 时，可在本地机器上做 SSH 转发：

```bash
ssh -L 8765:127.0.0.1:8765 <user>@<server>
```

然后在本地浏览器打开：

```text
http://127.0.0.1:8765
```

## 页面布局

当前页面是三栏调试布局：

1. 左栏 `Unified Board`
   - 统一显示 `Replay / Root / Action` 三种视图
   - 下方显示当前选中的 action 信息
   - 再下方显示 replay 实际操作、root 摘要，以及 `base / lure / lightning` 独立候选全集
2. 中栏 `Actions + Rollout Samples`
   - `Actions` 展示当前策略在线复算得到的全部候选
   - `Actions` 上方的分类按钮按最终 evaluated action 过滤，而不是按原始源候选过滤
   - 当前分类包括 `Hold / Base / Base Followup / Lure / Base + Lure / Lightning / Recycle + Lightning`
   - 表格将本回合操作和 future followup 分列显示，多回合计划不会在一回合内瞬间执行
   - 点击某个 action 后，在线计算该候选的 rollout 样本，默认数量跟随当前 v3 参数文件中的 `rollout_count`
   - `Actions` 表中的 `Total` 以普通数值显示，不使用科学计数法
   - `Rollout Samples` 中的 `Weight` 显示的是当前策略真正用于加权的样本权重
     - 即首回合重点蚂蚁所选动作真实概率的乘积
     - 不是整条 6 回合路径的 `path probability`
   - 样本按 `Weight` 降序显示
3. 右栏 `Trace`
   - 上半部分固定为 `Trace Start`
   - 下半部分固定为 `Trace End`
   - 选择某个 rollout sample 后，展示当前策略 horizon 的 trace
   - 右下同时显示该步蚂蚁动作表、候选方向概率和最终估值分项

## 页面能力

当前页面支持以下工作流：

1. 输入 replay 路径与回合，读取 `Replay Round`
2. 对该回合在线重建 `Strategy Root State`
3. 用当前 C++ 策略重新计算全部候选 action
4. 选择某个 action，在线计算该 action 的 rollout samples
5. 选择某个 sample，查看逐步 trace 与最终估值拆解

页面中的主要信息包括：

- replay 中该回合记录的盘面与双方实际操作
- 当前策略对该回合全部候选行动的打分
- `base / lure / lightning` 原始候选全集，便于检查是否“没显示”还是“根本没生成”
- 每个 rollout sample 的总分、归一化权重、终点核心分项
- 每步 trace 的起始/终止盘面、操作、蚂蚁动作分配、候选方向概率、最终估值分项
- 多步 base followup 会在 trace 中逐未来回合显示，例如 `sell -> build -> upgrade`
- 闪电候选会显示当前策略实际使用的合法中心全集；中心半径、rollout 数、UCB batch 和 exploration 均来自当前 v3 参数文件。普通 action 和闪电 action 使用两套独立 UCB 预算，页面中的 `Rollouts` 是对应 action 实际获得的样本数。
- 当前 v3 trace 会在第 6 回合和第 10 回合分别估值，并按 `mid_eval_weight` 合成最终 rollout 分数

## 交互

所有棋盘都支持：

- 滚轮缩放
- 鼠标拖动画面
- 双击重置视角

三栏之间支持两条可拖动分隔线：

- 左分隔线：调整左栏与中栏宽度
- 右分隔线：调整中栏与右栏宽度

默认布局会适当压缩左栏，优先给中栏和右栏留更多空间。

## 语义说明

页面里同时有两种“状态”：

- `Replay Round`
  - 来自 replay 文件本身
  - 用于看真实对局记录
- `Strategy Root State` / `Sample Trace`
  - 来自当前 C++ 策略在线复算
  - 使用当前 v3 `lure_strategy` 与 `DefenseSimulator`
  - 这是策略真正拿来打分、做 rollout 的模拟状态

因此两者不一定完全一一对应，尤其是：

- `Unified Board` 切到 `Root / Action` 时，显示的也是当前策略内部的模拟视角
- `Sample Trace` 使用的是当前策略内部的防守模拟视角
- 其中重点保留的是“己方塔、敌方蚂蚁、相关特效”等策略关心的信息
- 策略未来模拟不生成未来基地蚂蚁，因此不会显示未来由基地新刷出的蚂蚁
- 快速模拟默认忽略每 10 回合随机移动机制，因此跨 10 回合窗口的 trace 不适合拿来做严格 native 对拍
- 若要做规则级真值对拍，应使用 SDK 的 `sdk_defense_parity`，而不是只看页面上的单条 sample trace

## 代码位置

- server: [server.py](/root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp/simviz/server.py)
- frontend: [index.html](/root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp/simviz/static/index.html)
- frontend js: [app.js](/root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp/simviz/static/app.js)
- C++ inspector: [sdk_lure_inspector.cpp](/root/autodl-tmp/saiblo_iter/Game1/antgame_cpp_sdk/examples/sdk_lure_inspector.cpp)
- v3 params: [lure_strategy_v3_params.hpp](/root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp/cpp_lure_v3/include/antgame_ai/lure_strategy_v3_params.hpp)

## 版本口径

- `cpp_heavy_baseline` 使用 `lure_strategy_v2.hpp`。
- `cpp_lure_v2` 源码目录和打包目标已删除。
- simviz / inspector 默认跟随 `cpp_lure_v3/include/antgame_ai/lure_strategy_v3.hpp`，用于当前 v3 迭代分析。
- 前端不直接解析 `lure_strategy_v3_params.hpp`，也不再传固定 `rollout_count` 覆盖策略参数；`sdk_lure_inspector` 编译时包含当前 v3 参数头，并把编译进来的 `V3LureStrategyTuning` 作为 `strategy_params` 返回给页面。修改参数后需要重新编译 inspector，`run_simviz.sh` 启动时会自动执行对应 make 目标。
- 页面顶部参数摘要来自 `strategy_params`，包括普通/闪电 UCB、horizon、中心半径和金币阶梯权重 `money_weight / money_weight_above_threshold @ money_decay_threshold`。

## 现阶段限制

- `Sample Trace` 目前展示的是当前策略内部使用的模拟盘面，而非完整官方全盘面
- 周期随机移动/传送阶段目前只体现在 step 的前后盘面变化上，没有单独拆成细事件列表
- 页面目前偏调试工具风格，重点仍然是信息完整、定点分析与后续继续扩展
