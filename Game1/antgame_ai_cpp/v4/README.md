# Game1 C++ AI v4

`cpp_v4` 是当前面向 Game1 的新主线实验版。

核心思路：
- 忽略 `teleport`
- 防守优先
- 候选动作保留建塔 / 升级 / 降级(含销毁) / 基地升级，但强约束、少操作
- 只使用 `Quick` / `Mortar` 两条塔线，不主动考虑 `heavy`、`Sniper`、`Pulse`
- 用 `16` 回合共享场景 rollout 评估候选
- 先做敌蚂蚁威胁预处理，再对关键蚂蚁做首步分层采样
- 评分采用字典序防守优先

本版本通过 `AI/ai_cpp_v1.py` 的桥接快照运行，因此仍然使用当前 `SDK.backend` 的真实公开/私有状态作为输入。

当前状态：

- 一步采样已和 `exact_move_kernel` 做过对拍
- tightened 版本已把高频 `downgrade` 基本压掉
- 小样本本地评测中，当前强度大致与 `cpp_v1_current` / `example` 同量级

详细结果见：

- `/www/docs/game1_cpp_v4_rollout_status.md`
