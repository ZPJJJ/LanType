# API 30 native bridge：冷启动原生库加载分析

[GitHub Actions run 44109387258](https://github.com/ZPJJJ/LanType/actions/runs/44109387258) 在首次打开已发布的 **1.1.0** 时，记录到 `app.lantype.keyboard` 主进程原生崩溃：`pid = tid = 5049`，`SIGSEGV / SEGV_MAPERR`，访问地址 `0x8`。环境为 Android 11 / API 30、`google/sdk_gphone_x86_64/generic_x86_64_arm64:11/RSR1.240422.006/12134477:userdebug/dev-keys`，ARM64 native bridge 为 `libndk_translation.so` 0.2.2。这是旧版在该转译环境中的真实启动失败；不能记录为升级后 1.1.1 已通过或已失败，也尚未确定责任属于产品初始化、某个原生库或转译实现。

源码中存在不依赖启用输入法或点击语音的确定加载链：`Application.onCreate → preInitializeRimeEngine → RimeEngine.isInitialized → RimeEngine 类初始化 → System.loadLibrary("rime_jni") → libonnxruntime.so 依赖加载`。这里的 `isInitialized()` 查询发生在 IO coroutine 启动之前，因此会在调用线程触发静态库加载；返回值为 `false` 不代表尚未加载 native。下表中的源码路径均相对于仓库根目录。现有日志没有标记进入每一层的具体时刻，所以这条确定的冷启动代码路径仍不能单独证明崩溃函数。

| 证据位置 | 已核实内容 |
|---|---|
| `app/src/main/java/com/kingzcheung/xime/XimeApplication.kt`，149–160 行 | `onCreate()` 调用 `preInitializeRimeEngine()`；先查询 `RimeEngine.isInitialized()`，再启动 IO 准备任务。 |
| `app/src/main/java/com/kingzcheung/xime/rime/RimeEngine.kt`，125–143 行 | Companion 静态初始化无条件执行 `System.loadLibrary("rime_jni")`。 |
| `app/src/main/jni/CMakeLists.txt`，172–178 行；旧 APK 的 `lib/arm64-v8a/librime_jni.so` | 构建配置直接链接 ONNX Runtime；对实际库执行 `readelf -d` 也确认 `DT_NEEDED` 含 `libonnxruntime.so`，不是仅据构建文件推测。 |
| `app/src/main/java/com/kingzcheung/xime/MainActivity.kt`，140–156 行 | `onCreate()` 的配置预热同样在 IO `launch` 之前查询 `RimeEngine.isInitialized()`，构成另一个加载入口。 |
| `app/src/main/java/com/kingzcheung/xime/service/AsrInferenceService.kt`，180–185 行；`app/src/main/AndroidManifest.xml`，413–416 行 | 正常 Sherpa 识别器创建路径位于 `:asr` 服务。此轮受检日志未显示该进程或识别器加载，不能因库中存在相同字符串就断言经过了 Sherpa。 |

上述路径已与旧版交付物对应核查：旧 APK 为 `LanType-1.1.0-offline-arm64-v8a.apk`，SHA-256 为 `03e379a9b77fbddba9886e28bfa9fc78e447dc4843917117faf625b4339d18c6`。从 1.1.0 源码归档读取的 `XimeApplication.kt`、`RimeEngine.kt`、`MainActivity.kt`、`DefaultModelInstaller.kt`、`ModelRuntime.kt` 与分析时工作树逐字节相同。旧 APK 内受检 `librime_jni.so` 的 SHA-256 为 `b1aa35c250e301119d19473c10b493486e2a80537bcf70501748c294b909d16f`，与执行 ELF 检查的固定 vendor 文件相同；`libsherpa-onnx-jni.so` 也完成同样的逐字节对应核查。`ModelRuntime.attach()` 只登记内存回调，默认模型安装任务负责后台解包和文件检查；已审阅的启动路径没有直接创建 Sherpa recognizer。以上证据解释了为何尚未使用语音也可能加载 ORT，不意味着已证明进行了语音模型推理。

`ro.hardware.chipname` 访问拒绝紧邻崩溃，是诊断线索而非已证实根因。恢复后的固定 ONNX Runtime 源码 `vendor/native-sources/runtime-onnxruntime/onnxruntime/core/common/cpuid_info.cc` 中，`CPUIDInfo` 构造函数会调用 `cpuinfo_initialize()`；配套 cpuinfo 提交 `4628dc060ce4e82345dc166bbac875609db4ff69` 的 `src/arm/android/properties.c` 确实通过 `__system_property_get()` 读取该属性。旧 APK 的 ORT 库也包含这个字符串。但当前 tombstone 只有匿名 **x86_64** 帧 `#00 pc 0x377e43 <anonymous:7435eea72000>`，不能把它直接当成 ARM64 库内偏移进行归因，也不能仅凭时间相邻就认定属性读取导致空指针访问。进一步判断需要保持 APK 字节不变的环境对照，或能区分库加载阶段、包含完整映射的诊断证据；本分析不提出未经验证的产品修复。将加载简单挪到后台线程不能据此视为修复，因为原生 SIGSEGV 仍会终止整个进程。
