# Game1 cpp_v3 统一纯 C++ 版状态

## 1. 目标

`cpp_v3` 的目标不是替代当前本地最强 `cpp_v1_current`，而是解决此前最关键的工程断点：

- 本地主力依赖 Python SDK 桥接，不能直接上传 Saiblo
- 线上 probe 能上传，但策略太弱，不能代表当前思路

因此 `cpp_v3` 采用的策略是：

- 保留 `cpp_v1` 的候选动作 + 打分主线
- 输入改为“公开协议 + 本地状态跟踪”
- 同一份二进制既能本地 Elo，也能直接作为 Saiblo C++ 单文件上传

代码位置：

- `Game1/antgame_ai_cpp/v3/ai_v3.cpp`
- `Game1/Ant-Game/AI/ai_cpp_direct.py`

## 2. 当前已补入的结构

相对于此前的线上 probe，`cpp_v3` 已补入：

- 留钱防 EMP
- 攻守模式切换
- 轻量 danger forecast
- 槽位分组 / 分支约束
- `Deflector` / `EmergencyEvasion` 决策
- 对手操作可见后的公共局面前瞻（先看到 player0 操作再决策）

## 3. 本地结果

### 3.1 单局冒烟

- `cpp_v3` vs `random`：胜
- `cpp_v3` vs `example`：负

### 3.2 小样本 Elo

本轮手动运行：

- tag: `eval_20260310_165010`
- cumulative matches: `18`

当前 Elo：

- `cpp_v1_current`: `1552.17`
- `example`: `1533.37`
- `cpp_v3_unified_online`: `1481.71`
- `random`: `1432.75`

结论：

- `cpp_v3` 已经不是“只能上传的占位版”
- 但它仍明显弱于 `cpp_v1_current`，也弱于 `example`

## 4. Saiblo 结果

上传信息：

- entity: `g1cppv3`
- entity_id: `20403`
- code_id: `c641416121584bafb3b3cdf6bca6c6ae`
- compile_status: `编译成功`

实战对局：

1. `7419784`
   - `g1cppv3` vs `example`
   - 结果：负
   - rounds: `293`
   - final camps: `[0, 45]`
2. `7419785`
   - `example` vs `g1cppv3`
   - 结果：负
   - rounds: `512`
   - final camps: `[47, 16]`

回放位置：

- `replays/saiblo_api/game1_v3_20260310/`

## 5. 当前判断

正确结论是：

- Game1 的“本地 Elo + 本地统一包 + 线上上传 + 线上对局 + 回放下载”链已经全部打通
- `cpp_v3` 解决了“线上无法直接上传主力思路”的工程问题
- 但从强度看，它还不是当前最强版本

因此当前最合理的分工是：

- 本地主强度仍以 `cpp_v1_current` 为准
- 线上纯 C++ 主线暂时以 `cpp_v3` 为基础继续迭代
