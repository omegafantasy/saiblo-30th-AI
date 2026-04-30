# cpp_lure_v3n

`cpp_lure_v3n` 是 v3 的性能探针版本，只用于本机与 Saiblo 的 CPU 性能比例测试，不用于正式对局。

行为口径：

- 每回合生成当前 v3 root plans
- 只评估两类计划：active lure 计划与 lightning 计划
- 不评估 base 计划
- 永远发送空操作列表

stderr 每回合输出一行 JSON：

```json
{"kind":"v3n_perf","round":0,"player":0,"serial":1,"lure_plans":1,"lure_simulations":80,"lure_elapsed_ns":123456,"lightning_plans":91,"lightning_simulations":500,"lightning_elapsed_ns":1234567}
```

其中 `*_simulations` 来自对应 UCB trace 的真实 sample 数，`*_elapsed_ns` 是围绕对应评估调用的 `steady_clock` 纳秒计时。

## Saiblo 原生 C++ 打包

普通 `package_ai.sh cpp_lure_v3n` 会生成 Python 协议壳 + C++ 二进制的 `python_zip` 包，适合本地评测和普通平台提交兼容性测试。性能比例测试必须使用原生 C++，避免把 Python wrapper 纳入 Saiblo 语言类型。

原生 C++ zip 使用：

```bash
Game1/antgame_ai_cpp/package_cpp_source_zip.sh cpp_lure_v3n eval_results/ai_cpp_lure_v3n_cppzip.zip
```

该包根目录包含：

- `main.cpp`
- `antgame_ai/*.hpp`
- `antgame_sdk/*.hpp`
- `antgame_sdk/src/native_sim.cpp`
- `Ant-Game/game/include/*`
- `Ant-Game/game/src/*.cpp`
- `Makefile` / `CMakeLists.txt`

Saiblo 的 `cpp_zip` 编译器会递归编译 `.cpp` 文件，但不会自动给源码根目录加 `-I.`。打包脚本会把包内头文件 include 改成相对路径，以匹配平台实际编译方式。

2026-04-29 上传记录：

- Saiblo entity：`v3n-perf-cppzip`，entity id `20780`
- Saiblo language：`cpp_zip`
- 成功 code id：`cd02749306d642e3a409f2dd50d5d32f`
- 版本：`3`

## 2026-04-29 性能测试

本地 16 组自我对战：

- 目录：`eval_results/v3n_selfplay_local_16`
- records：`7740`
- simulations：`10609300`
- 总计时：`2461.151009s`
- 平均：`317.978167 ms / player-round`
- lure 平均：`208.320050 ms`
- lightning 平均：`109.658117 ms`

Saiblo 原生 C++ 16 组自我对战：

- 目录：`eval_results/v3n_selfplay_saiblo_cppzip_16`
- match ids：`7990833`, `7990879`-`7990893`
- records：`7742`
- simulations：`10600140`
- 总计时：`3991.232307s`
- 平均：`515.529877 ms / player-round`
- lure 平均：`339.446099 ms`
- lightning 平均：`176.083778 ms`

Saiblo / 本机耗时比例：

- combined：`1.6213x`
- lure：`1.6294x`
- lightning：`1.6058x`

Saiblo 页面用时统计图的数据源是 match detail 的 `message.record[].time`。这批 16 局中，平台图表数据与 stderr 内部计时一致：

- 平台图表调用数：`7742`
- 平台图表平均：`512.608070 ms / call`
- stderr 平均：`515.529877 ms / call`
- 平台总计时 / stderr 总计时：`0.9943`

差异约 `0.57%`，可认为图表与 v3-n log 口径一致；后续性能比例以 stderr 为准，因为它能拆分 lure 与 lightning 两类计算。
