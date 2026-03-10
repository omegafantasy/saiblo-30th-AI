# Agent A：Docs 与 mhtml 复刻准确性核查

## 核查范围

- `docs/mhtml_parsed/*.md` 与 `docs/*.mhtml` 的一致性
- `docs/antwar2_rules_and_code_analysis.md`
- `docs/legacy_overlap_analysis.md`
- `docs/mhtml_three_games_parsed.md`
- 根文档 `README.md` 中的路径与描述一致性

## 核查方法

1. 重新执行解析：`python /www/scripts/parse_mhtml_rules.py`
2. 检查乱码：确认输出中不存在 `�`
3. 关键词抽样回对（源 mhtml 片段 vs 解析 markdown）
4. 交叉核对 `Ant-Game/logic/*.py` 与分析文档中的规则描述

## 结果

### 1) mhtml 复刻准确性

- 三份解析 markdown 均无乱码：
  - `antwar_game22.md`
  - `generals_game35.md`
  - `antwar2_game48.md`
- 抽样关键词在源页面与解析文档中均存在（如“胜负判定”“结算流程”“超级武器”等）。
- 图片提取结果与页面实际一致：
  - ANTWar：2 张图（`1.PNG`、`2.JPEG`）
  - Generals：0 张图
  - 蚁洋陷役2：0 张图

### 2) 发现并修复的问题

- 解析脚本原先只从仓库根目录读取 mhtml；当前实际文件位于 `docs/`，会导致后续复现失败。
  - 已修复：`scripts/parse_mhtml_rules.py` 现在会按“根目录优先，`docs/` 回退”查找输入文件。
- 文档中仍有旧路径（`/www/蚁洋陷役2 - Saiblo.mhtml` 等）：
  - 已修复到 `/www/docs/*.mhtml`：
    - `README.md`
    - `docs/antwar2_rules_and_code_analysis.md`
    - `docs/legacy_overlap_analysis.md`
    - `docs/mhtml_three_games_parsed.md`

### 3) 其他规则描述准确性

- `docs/antwar2_rules_and_code_analysis.md` 中关于以下结论与代码一致：
  - 地图 `15x15`、四方向移动、主将/副将/农夫框架；
  - `round > 500` 触发平局裁决；
  - `main.py` 在 `update_round` 后存在额外一次双方 `+1 coin`。

## 结论

- 当前 `docs/` 下 mhtml 复刻产物可用，且可复现。
- 规则分析文档的关键结论与当前代码实现一致。
