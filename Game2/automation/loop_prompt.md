# Game2 DeepClue 自动迭代循环

你是 DeepClue（头号侦探）游戏 AI 的自动优化系统。每次被调用时，执行一轮完整的 检查→分析→改进→提交 循环。

## 游戏概要

DeepClue 是单人推理剧本杀，2个案件串行进行（Case 0: 蔷薇案6人, Case 1: 校园案5人NPC_A~E）。
通过 `chat` 向 NPC 提问获取证言推进阶段，最后 `answer` 提交凶手/动机/手法。

**评分公式**：`得分 = (正确性≤600 + 进度≤400 + 成就×40) × 效率系数`，总分=Case0+Case1。
- 正确性：凶手/动机/手法 各200分（我们答案已正确，Case0=崔安彦，Case1=NPC_E）
- 进度：阶段比例 × 线索比例，最大400/case
- 效率：基于总token消耗的对数缩放，token越少越高
- Admin 稳定得 2357，我们最高 1928

**核心瓶颈**：Case 1 总是卡在 stage 4（admin 到 stage 8）。原因是 NPC 的 LLM 回复是随机的，同样的问题有时触发证言解锁有时不触发。Stage 4→5 需要 NPC_C 提到"D拖脚修车"(testimony 404)和"F出现"(testimony 407)。

## 关键文件

- `Game2/automation/check_scores.py` — 检查所有对局分数
- `Game2/automation/state.json` — 迭代状态
- `Game2/deepclue_ai/v{N}/ai_v{N}.py` — AI 代码（找最大N的目录）
- `Game2/automation/logs/iteration_{N}/` — 迭代日志
- `docs/mhtml_parsed/deepclue_game.md` — 完整游戏规则和API文档
- `saiblo_tools.py` — Saiblo API（api_request, api_download, resolve_token）
- `C:\Users\win\.claude\projects\D--others-saiblo-iter\memory\project_game2_iteration.md` — 迭代记忆

## 可用的游戏 API

chat(npc, question, evidences=[]) — 提问，返回 {reply, stage, achievements, unlock_testimony}
answer(murderer, motivation, method) — 提交答案
marks — 哪些NPC还有未获取证言 {npc: bool}
npcs — 当前NPC列表
stage — 当前阶段号
testimony — 已获得证言列表
others — 非证言类证据
hint — 当前阶段提示
achievements — 已解锁成就

## 每轮执行步骤

### Step 1: 检查分数
```bash
python Game2/automation/check_scores.py
```
对比历史最高分和之前的 running 状态。

### Step 2: 分析新完成的对局
如果有新完成的对局（score > 0 且之前是 running）：
- 用 `api_download('/api/matches/{mid}/download/', token=token)` 下载 trace
- 解析 trace（JSON，key '0' 和 '1' 分别是两个 case 的步骤列表）
- 每步有 result_state.stage, npc_marks, visible_testimony, achievements
- 重点分析：各 case 最终 stage、testimony 数量、哪些 marks 没清除
- 如果分数比历史最高高，记录该版本的策略作为新基线

### Step 3: 思考改进方向
根据分析结果，从以下角度寻找突破：

**提升阶段进度（最大价值）：**
- 重试触发问题：stage 4→5 的触发问 NPC_C 多问几次（LLM回复每次不同）
- 针对性追问：当 marks 未清除时，问更具体的问题引导 NPC 说出关键信息
- 使用 evidences 参数：出示已有证据可能引导 NPC 给出更详细回复
- 调整问题顺序：不同顺序可能影响 NPC 回复质量
- 增加问题变体：同一个意思用不同措辞问，增加触发概率

**提升效率系数：**
- 减少不必要的 API 调用（marks/stage 查询也占开销）
- 缩短问题文本长度
- 如果 retry 太多反而降低效率，找到最佳 retry 次数

**解锁成就：**
- 分析 admin trace 中是否有成就解锁
- 尝试特定问题组合触发成就

**其他探索：**
- 使用 hint API 获取阶段提示，据此调整提问策略
- 使用 testimony API 查看已收集证据，选择性出示
- 分析 admin trace 中每个证言解锁的具体条件

### Step 4: 创建新版本
- 找到当前最大版本号 N：`ls Game2/deepclue_ai/ | grep "^v" | sort -t v -k 2 -n | tail -1`
- 创建 `Game2/deepclue_ai/v{N+1}/ai_v{N+1}.py`
- 基于分析结果实现改进
- 代码必须包含完整的 SDK 类和 main 函数（参考现有版本）

### Step 5: 提交
```bash
bash Game2/automation/iterate.sh
```
这会自动找到最新版本、上传、创建 batch、轮询结果。

### Step 6: 更新记忆
将本轮发现写入 memory 文件 `project_game2_iteration.md`，包括：
- 新版本号和策略描述
- 新的分数数据
- 关键发现

### Step 7: 输出摘要
简要报告：新完成的分数、当前最高分、本轮改动、下一步计划。
