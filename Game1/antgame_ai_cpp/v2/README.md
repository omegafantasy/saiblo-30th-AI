# Game1 C++ AI v2

当前版本是基于旧版 `ANTWar-AI` 结构思路重建的首个 `Game1` C++ 基线：

- 保留旧 AI 的核心理念：固定战略槽位、进攻/防守模式切换、EMP 安全留钱、基地升级时机控制。
- 放弃旧版强耦合模拟器实现，改为由 Python 桥接层提供当前 `SDK.backend` 的精确状态快照，再由 C++ 做策略决策。
- 当前版本重点是先打通 `Game1/Ant-Game` 新协议、新目录结构与本地运行链路。

## 构建

```bash
cd /www/Game1/antgame_ai_cpp/v2
make
```

## 本地验证

```bash
cd /www/Game1/Ant-Game
python3 tools/run_local_match.py --ai0 cpp_v2 --ai1 greedy --seed 7 --keep-dir /tmp/game1_cpp_v2_smoke
```

## 当前桥接方式

- 评测入口仍由 `Game1/Ant-Game/AI/main.py` 管理。
- `AI/ai_cpp_v2.py` 会启动本目录下的 `ai_v2`，每回合向其发送一行 JSON 状态快照。
- C++ 只负责选择操作，不直接实现平台通信细节。
