# Saiblo Game 48 上传接口实测（我的AI）

更新时间：2026-03-04 (UTC)

## 1) 前端真实调用链（来自 `game/48?id=3` 的 Nuxt bundle）

`我的AI` 页面上传逻辑是两步：

1. 创建 AI 实体（Entity）
- `POST /api/users/<username>/games/<game_id>/entities/`
- body(JSON):
```json
{
  "name": "autolv1_0304",
  "language": "cpp"
}
```

2. 上传代码版本（Code）
- `POST /api/entities/<entity_id>/codes/`
- body(`multipart/form-data`):
- `remark`：文本
- `file`：源码文件（如 `.cpp`）

可选：

3. 激活版本（派遣）
- `PUT /api/entities/<entity_id>/codes/<code_id>/`
- body(JSON):
```json
{"activate": true}
```

说明：`<code_id>` 不是版本号（`version`），而是代码记录的 UUID 字符串。

## 2) 关键约束（实测）

- Entity 名称长度上限 16（超过会返回 400）。
- 只有 `compile_status=编译成功` 的版本可以激活；否则会返回：`无法出战编译失败的代码`。
- 上传后可通过 `GET /api/entities/<entity_id>/codes/` 轮询编译状态。

## 3) 已验证结果

- 已成功创建 Entity：`autolv1_0304`（`id=20339`）。
- 已成功上传版本：
  - `version=3`（编译成功，历史已激活）
  - `version=4`（编译成功，未激活，用于“暂不派遣”测试链路）
- 当前建议：测试默认仅上传不激活，直接使用 `code_id token` 开房对战。

## 4) 自动化命令（已集成到 `saiblo_tools.py`）

1. 查看当前账号在 game 48 的实体与当前激活版本：

```bash
python3 /www/saiblo_tools.py entities --game-id 48
```

2. 上传到已有实体并等待编译后自动激活：

```bash
python3 /www/saiblo_tools.py upload-ai \
  --game-id 48 \
  --entity-id 20339 \
  --source /path/to/main.cpp \
  --remark "upload by autolab" \
  --wait-compile \
  --activate
```

3. 若实体不存在则自动创建后上传：

```bash
python3 /www/saiblo_tools.py upload-ai \
  --game-id 48 \
  --entity-name myai_v1 \
  --create-if-missing \
  --language cpp \
  --source /path/to/main.cpp \
  --wait-compile \
  --activate
```

## 5) 相关扩展文档

- 排行榜/对局/回放/开房接口梳理与 2 局实测：
  - `/www/docs/saiblo_api_mapping_and_match_smoke.md`
