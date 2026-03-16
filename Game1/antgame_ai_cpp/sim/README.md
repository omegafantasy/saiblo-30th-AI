# Exact Move Kernel

这个目录只做一件事：

- 按当前 `Game1/Ant-Game` 真值规则，计算单只蚂蚁的一步精确移动分布

它暂时不负责：

- 完整回合模拟
- 精确塔控制效果
- deflector / evasion
- teleport 采样

## 文件

- `exact_move_kernel.cpp`
  - C++ 一步分布内核
  - 也包含一个短视野 `ExpectedFront` 原型
  - `ExpectedFront` 当前已包含“近似塔伤”，但不是完整攻击仿真
- `Makefile`
  - 编译入口

## 编译

```bash
make
```

## CLI

默认从 `stdin` 读取 JSON，输出 JSON。

输入字段：

- `pheromone`
  - `2 x 19 x 19` 整数数组
- `ants`
  - 每只蚂蚁至少包含：
    - `id`
    - `player`
    - `x`
    - `y`
    - `status`
    - `behavior`
    - `last_move`
    - `bewitch_target_x`
    - `bewitch_target_y`
- `query_ant_ids`
  - 可选

示例：

```bash
cat payload.json | ./exact_move_kernel
```

短视野期望传播：

```bash
cat payload.json | ./exact_move_kernel --expected-front
```

## Benchmark

```bash
./exact_move_kernel --benchmark 16 50000
```

参数：

- 第一个参数：每方蚂蚁数上限
- 第二个参数：循环次数

## 校验

Python 对拍脚本：

- `/www/Game1/Ant-Game/tools/verify_exact_move_kernel.py`
- `/www/Game1/Ant-Game/tools/compare_expected_front.py`

它会：

1. 编译当前 C++ 内核
2. 构造若干真实 `engine.GameState`
3. 用 Python 真值分布和 C++ 输出逐项对比
