# cpp_heavy_baseline

这是当前保留的 Game1 C++ AI 入口。

目录名沿用历史命名，但内部已经不是旧版 `heavy` 基线。

## 1. 当前入口

- `ai_cpp_heavy_baseline.cpp`
  - 比赛协议入口
  - 维护 `PublicState`
  - 维护 `NativeSimulator`
  - 调用 `antgame_sdk::decide_lure_strategy()`

## 2. 当前真实依赖

- `../../antgame_cpp_sdk/include/antgame_sdk/lure_strategy.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/lure_strategy_params.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/random_search_baseline.hpp`
- `../../antgame_cpp_sdk/include/antgame_sdk/position_slots.hpp`

## 3. 当前策略口径

当前 baseline 的关键点：

- root 动作拆成 `base`、`lure`、`lightning`
- 常规候选是 `base × lure`
- 闪电是独立候选
- rollout 未来回合继续用 reactive `base + lure` 控制器
- 终点评估只看：
  - 基地血
  - 塔可回收价值
  - 金币
  - worker threat
  - combat threat

当前还包含以下实现约束：

- 组合动作必须整组合法
- 若需要拆塔和建塔，则总是先拆后建
- 若需要拆多塔，则优先拆当前血量更高的塔
- 当前 lure 建塔位置不做额外启发式打分

## 4. Build

```bash
cd Game1/antgame_ai_cpp/cpp_heavy_baseline
make
```

## 5. Package

```bash
cd Game1/antgame_ai_cpp
bash package_ai.sh cpp_heavy_baseline
```

## 6. Debug / Eval

推荐工具：

- `../tools/eval_cpp_selfplay.py`
- `../tools/analyze_selfplay_batch.py`

典型流程：

```bash
cd Game1/antgame_ai_cpp
python tools/eval_cpp_selfplay.py \
  --target cpp_heavy_baseline \
  --seeds 1:8 \
  --debug-seeds 1 \
  --jobs 8 \
  --max-rounds 256 \
  --output-dir ./eval_current \
  --force

python tools/analyze_selfplay_batch.py ./eval_current
```

注意：

- 当前官方 `Game1/Ant-Game/game/output/main` 不会主动执行 init 里的 `config.max_rounds`
- 所以 `--max-rounds 256` 目前只能作为“期望测试窗口”的元数据，不保证 replay 真在 `256` 回合结束
- 若要分析严格前 `256` 回合，应对 replay 与 debug log 自行裁切

## 7. 边界说明

- 规则真值仍以 `../../Ant-Game/` 为准
- SDK 与 baseline 都不能把改动写回 `Ant-Game/`
- `eval_*`、`tmp_*`、位置图和临时 replay 分析目录都视为生成物，不进版本库
