# 三个 mhtml 规则页解析结果（含图片落盘）

本文档记录 3 个 Saiblo `mhtml` 页面已经完成的“可复用解析产物”（正文 Markdown + 图片资源）。

## 1. 输入源文件

- `/www/docs/ANTWar - Saiblo.mhtml`
- `/www/docs/Generals - Saiblo.mhtml`
- `/www/docs/蚁洋陷役2 - Saiblo.mhtml`

## 2. 输出目录（已生成）

- `/www/docs/mhtml_parsed/antwar_game22.md`
- `/www/docs/mhtml_parsed/generals_game35.md`
- `/www/docs/mhtml_parsed/antwar2_game48.md`
- `/www/docs/mhtml_parsed/README.md`

图片资源目录：

- `/www/docs/mhtml_assets/antwar_game22/1.PNG`
- `/www/docs/mhtml_assets/antwar_game22/2.JPEG`

## 3. 每个页面的“实质有用内容”提取结果

### 3.1 ANTWar（game/22）

已提取完整规则正文，包含：

- 游戏简介与回合/时限规则
- 地图坐标系（even-q）与可行走/建塔区域说明
- 防御塔、工蚁、超级武器、经济系统、胜负判定
- 原文代码段（Python/C++）与表格

页面内图片已落盘并在 Markdown 中引用：

![ANTWar 图1](./mhtml_assets/antwar_game22/1.PNG)
![ANTWar 图2](./mhtml_assets/antwar_game22/2.JPEG)

### 3.2 Generals（game/35）

已提取完整规则正文，包含：

- 背景、地图地形、移动规则、攻击结算
- 经济系统（油田/将军升级）、战法与科技
- 超武、胜负判定、AI 接口协议与状态结构

该页面规则正文中无可提取 `<img>` 资源（`images: 0`）。

### 3.3 蚁洋陷役2（game/48）

已提取完整正文，包含：

- 游戏背景与核心玩法说明
- 回合结算与胜负判定描述
- 开发者接入指南（`logic/`、`SDK`、`AI/ai_{name}.py`、`play.py`、`SDK/batch_eval.py`）

该页面规则正文中无可提取 `<img>` 资源（`images: 0`）。

## 4. 复现命令

在仓库根目录执行：

```bash
python /www/scripts/parse_mhtml_rules.py
```

该命令会重新生成上述 markdown 与图片资源，并刷新 `/www/docs/mhtml_parsed/README.md` 的图片统计。
