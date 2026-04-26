# Game1 SimViz

`simviz/` 提供一个适配无头服务器的本地可视化工具，用于做 Game1 的定点分析。

当前实现分成两层：

- Python 本地 web server
  - 负责静态页面、地图几何、replay 读取、API 转发
- C++ inspector
  - 负责按当前 `lure_strategy` 在线复算候选行动
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
   - 点击某个 action 后，在线计算该候选的 20 个 rollout 样本
   - `Actions` 表中的 `Total` 以普通数值显示，不使用科学计数法
   - `Rollout Samples` 中的 `Weight` 显示的是当前策略真正用于加权的样本权重
     - 即首回合重点蚂蚁所选动作真实概率的乘积
     - 不是整条 6 回合路径的 `path probability`
   - 样本按 `Weight` 降序显示
3. 右栏 `Trace`
   - 上半部分固定为 `Trace Start`
   - 下半部分固定为 `Trace End`
   - 选择某个 rollout sample 后，展示未来 6 回合 trace
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
- `base / lure / lightning` 原始候选全集，便于检查是前端没显示，还是当前生成层根本没产生该候选
- 每步 trace 的起始/终止盘面、操作、蚂蚁动作分配、候选方向概率、最终估值分项

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
  - 使用当前的 `lure_strategy` 与 `DefenseSimulator`
  - 这是策略真正拿来打分、做 rollout 的模拟状态

因此两者不一定完全一一对应，尤其是：

- `Unified Board` 切到 `Root / Action` 时，显示的也是当前策略内部的模拟视角
- `Sample Trace` 使用的是当前策略内部的防守模拟视角
- 其中重点保留的是“己方塔、敌方蚂蚁、相关特效”等策略关心的信息
- 快速模拟默认忽略每 10 回合随机移动机制，因此跨 10 回合窗口的 trace 不适合拿来做严格 native 对拍
- 若要做规则级真值对拍，应使用 SDK 的 `sdk_defense_parity`，而不是只看页面上的单条 sample trace

## 代码位置

- server: [server.py](/root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp/simviz/server.py)
- frontend: [index.html](/root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp/simviz/static/index.html)
- frontend js: [app.js](/root/autodl-tmp/saiblo_iter/Game1/antgame_ai_cpp/simviz/static/app.js)
- C++ inspector: [sdk_lure_inspector.cpp](/root/autodl-tmp/saiblo_iter/Game1/antgame_cpp_sdk/examples/sdk_lure_inspector.cpp)

## 现阶段限制

- `Sample Trace` 目前展示的是当前策略内部使用的模拟盘面，而非完整官方全盘面
- 周期随机移动/传送阶段目前只体现在 step 的前后盘面变化上，没有单独拆成细事件列表
- 页面目前偏调试工具风格，重点仍然是信息完整、定点分析与后续继续扩展
