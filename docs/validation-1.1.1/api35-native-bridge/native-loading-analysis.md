# API 35：ORT 加载构造与 cpuinfo 缓存拓扑分析

本分析针对 [run 44112396806](https://github.com/ZPJJJ/LanType/actions/runs/44112396806) 中**已发布的旧签名版 1.1.0 / code 2**，不是新版 1.1.1 的运行结果。API 35 的 `native-app-dropbox.txt` 记录主进程 `app.lantype.keyboard`、`pid = tid = 3574`、`SIGSEGV / SEGV_MAPERR`、错误地址 `0x8`；ARM64 guest 回溯包含 `libonnxruntime.so`、`pthread_once` 和 linker 的 `call_constructors / do_dlopen`。这比 API 30 的匿名 x86_64 帧进一步确定了**ORT 动态库加载构造阶段**。完整运行范围、环境和原始附件见本目录 [README](README.md) 与 [receipt.json](receipt.json)；本页没有新增设备运行、编译或修复结果。

## 固定二进制与可复核调用链

分析从固定旧 APK 的 ZIP 成员读取 ORT，先与现有构建目录的 ELF 逐字节比较，再执行 `readelf`、`llvm-symbolizer` 和 NDK `llvm-objdump`。APK SHA-256 为 `03e379a9b77fbddba9886e28bfa9fc78e447dc4843917117faf625b4339d18c6`；受检 `lib/arm64-v8a/libonnxruntime.so` 为 **28,637,280 字节**，SHA-256 为 `f826d8efb03adf0a84f10e7ba408f9d4cd11b0a2ccd8d08aeb0f7451fb50cacc`，BuildId 为 `b178f5c22304a25ff481e608260312842627e868`，与 tombstone 一致。该 ELF 没有 `.symtab` 或 `.debug`，四个回溯 PC 的 `llvm-symbolizer` 输出均为 `??`，因此下列源码函数归属是固定源码、调用指令与字符串共同支持的对应分析，**不是恢复了调试符号或精确 C/C++ 故障行**。实际命令、选定地址段和输出保存在 [native-loading-evidence.txt](native-loading-evidence.txt)。

| 实际 ELF 位置 | 可直接确认的行为 | 与固定源码的对应及边界 |
|---|---|---|
| `.init_array` 的重定位项 `0x1b4c460` | 构造函数入口为 `0x10d80d4`。 | 结合 guest linker 回溯确认是动态库构造阶段，无需假定已经开始模型推理。 |
| `0x10d8160` | 调用 `0x16f54d8`。 | 后一实现的字段初始化、调用次序及警告字符串与 ORT `CPUIDInfo` 构造一致。 |
| `0x16f550c` | 调用 `0x9c9f48`。 | 对应 `CPUIDInfo::CPUIDInfo()` 中的 `cpuinfo_initialize()`；地址 `0x2b33c2` 的初始化失败警告与固定源码完全一致。 |
| `0x9c9f60` | 调用 `pthread_once@plt`，传入回调 `0x9ca028`。 | 与 cpuinfo 的 ARM/Linux 初始化选择分支相符；回调内部的处理与 `cpuinfo_arm_linux_init()` 对应。 |
| `0x9cac00`、`0x9cac94` | 零计数分支跳过分配并把 `x28` 清零；非零分支按每项 32 字节分配并把结果存入 `x28`。 | 与 L2 cache 数组的条件分配相符。 |
| `0x9caedc` 至 `0x9caf20` 附近 | 从栈读取索引，以 `x28 + index × 32` 形成地址，包含 `0x9caefc: stp w10,w12,[x9,#8]`。 | 与第二遍写入 cache 结构字段相符；现场 `x28 = 0`，但不能把相邻写指令直接当作已符号化的精确故障指令。 |

`objdump` 的部分输出使用最近导出符号 `OrtSessionOptionsAppendExecutionProvider_CPU` 加巨大偏移作为标签；该导出函数本身只有 240 字节，这些标签不能作为内部函数名。此前已核实的冷启动路径 `XimeApplication → RimeEngine.isInitialized() → System.loadLibrary("rime_jni") → DT_NEEDED libonnxruntime.so` 见 [API 30 加载分析](../api30-native-bridge/native-loading-analysis.md)。该路径解释了为什么未启用键盘、未点击语音也会进入 ORT 加载；此次 guest 回溯提供了更直接的库内构造阶段证据。

## L2 两遍处理不一致：具体假说

源码版本取自 [原生源码锁](../../licensing/native-sources.lock.json)：ORT 1.28.0 提交 `da9b5e364c465de65c49d91e696cd6485270757f`，对应 `onnxruntime/core/common/cpuid_info.cc`；cpuinfo 提交 `4628dc060ce4e82345dc166bbac875609db4ff69`，对应 `src/init.c` 和 `src/arm/linux/init.c`。本次直接读取并校验了锁定 cpuinfo 归档，SHA-256 为 `2ed3ebc6c2656cc0aafc7af319e5cb0f97cc9b415eae180f566def84f1ca6a29`，没有以其他版本源码替代。以下行号属于该固定 cpuinfo 提交。

`src/arm/linux/init.c` 第一遍第 784–827 行，只有解码所得 `temp_l3.size != 0` 或 `temp_l2.size != 0` 才增加 `l2_count`；第 830–850 行仅在计数非零时分配 L2 数组。第二遍第 872–898 行重新读取 sysfs，允许 `sysfs_l2_size > 0` 覆盖原先为零的 L2 大小，并因 `l2_is_per_core` 进入写入路径。因此存在一个具体可检验的输入组合：**ARM 型号解码得到 L2/L3 大小为零，而 sysfs 报告每核 L2；第一遍计数可能保持零，第二遍却写入尚未分配的 L2 数组。** ELF 中的零计数分支、现场 `x28 = 0`、32 字节结构写入及 `0x8` 错误地址均与此路径相容。这是有源码和二进制依据的原因假说，仍未记录该 guest 实际返回的 CPU 型号、cache size 和共享拓扑输入，不能宣布已经完成根因证明。

## 因果边界与下一项诊断

guest 报告的 `0x9caedc` 本身是读取 `SP + 0xa8`，并非直接访问 `NULL + 8`；相邻块内才有上述字段写入。经过 native translation 的 guest PC 可能对应翻译块位置，所以不能虚构精确源码行或断言单条 guest 指令就是硬件故障点。`ro.hardware.chipname` 访问警告仍只是相邻线索，不是本分析认定的根因。当前证据也不能区分是上游两遍处理对某种合法拓扑不健壮、桥接环境暴露了特殊或不一致拓扑，还是其他尚未排除的因素；不能推断物理 ARM64 必然崩溃，不能据此认为语音模型或 Sherpa 已执行，更不能把挪到后台线程视为修复。

重复 ORT／Rime／Sherpa 三项独立 load 探针，对当前“加载阶段已经失败”的定位增益有限，且不能补足上述拓扑输入。下一项已准备、尚未由本分析执行的诊断，是独立首次安装正式签名候选 1.1.1，并保留同一 guest 的 `candidate-cpuinfo.txt` 与 `candidate-cpu-cache-topology.txt`。前者读取 `/proc/cpuinfo`；后者读取 CPU cache 的 `level/type/size/shared_cpu_list`。这些输入可用于核对第一遍计数与第二遍写入是否分歧；候选版的实际结果必须单独记录，不沿用旧版的失败或其他测试的通过结论。正式 APK、原生库和用户设备在本次分析中均未改动。
