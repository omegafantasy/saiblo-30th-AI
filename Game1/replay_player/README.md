# Game1 Replay Player

一个面向 `Game1` 回放的 Web 播放器，适合在无头服务器上通过浏览器、VSCode 端口转发或公网端口访问。

## 启动

```bash
python3 /www/Game1/replay_player/server.py --host 0.0.0.0 --port 8010
```

当前已验证可用端口：`8010`

访问方式：

- 本机：`http://127.0.0.1:8010/`
- VSCode Remote / SSH：直接转发 `8010`
- 如果需要公网访问，再单独开放 `8010`

## 支持功能

- 加载服务器上的指定 replay 路径
- 直接上传本地 replay 文件
- 扫描常用 replay 目录并点击加载
- 播放 / 暂停 / 上一回合 / 下一回合
- 倍速控制
- 进度条拖动
- 跳转到指定回合
- 棋盘可视化
- 双方基地、金币、蚂蚁等级、产速等级、塔数、蚂蚁数展示
- 当前回合操作列表展示
- 点击棋盘查看格子、塔、蚂蚁详情

## 默认扫描目录

- `/www/autolab/runtime/scopes/game1_v4_eval_core_tight/replays`
- `/www/autolab/runtime/scopes/game1_v4_eval_core/replays`
- `/www/autolab/runtime/scopes/game1_v4_eval_fast/replays`
- `/www/autolab/runtime/scopes/game1_v4_eval/replays`
- `/www/replays/saiblo_api`

## URL 直接加载

支持 URL query 直接指定回放：

```text
http://127.0.0.1:8010/?path=/www/autolab/runtime/scopes/game1_v4_eval_core_tight/replays/eval_20260312_170803/xxx.json
```

## 当前限制

1. 只支持当前 `Game1` 的 JSON 数组 replay。
2. `match_*.json` 这类 Saiblo 对局详情文件不是 replay 本体，不能直接播。
3. replay 本身不包含完整超武状态，因此播放器中的超武面板是“基于操作历史和规则的重建值”。
4. 对 `LightningStorm / EMPBlaster`，由于真实效果会漂移而 replay 不记录漂移后位置，播放器只能展示冷却与激活历史，不能保证实时作用位置完全准确。

## 相关文件

- 服务端：`/www/Game1/replay_player/server.py`
- 前端：`/www/Game1/replay_player/static/index.html`
- 前端脚本：`/www/Game1/replay_player/static/app.js`
- 样式：`/www/Game1/replay_player/static/styles.css`
