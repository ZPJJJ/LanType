# 1.1.1 直接安装与首启：已观察到 ORT native 崩溃

本次仅安装未改动的正式签名 **1.1.1** 与独立编辑器 host，没有安装旧版作为前置。**固定 APK 身份、证书、断网条件和全新安装均通过；首次启动在 `libonnxruntime.so` 动态库构造初始化阶段发生 native SIGSEGV，未出现产品向导。** 这是对 1.1.1 本身的直接运行证据，不再由旧版失败推断。

## 真实 case 结果

| Case | 结果 |
|---|---|
| candidate-environment-and-signed-identity | passed：API35/user 0/ARM bridge 与固定 APK、单 signer 证书通过 |
| disable-network-before-candidate | passed：飞行模式 1、Wi-Fi 0、移动数据 0 |
| fresh-candidate-and-host-install | passed：实际安装版本 1.1.1 / code 3 与 host 1.0 |
| candidate-first-launch | failed：产品 native 崩溃，向导观察随后到达 120 秒期限 |

合计 **3 passed / 1 failed / 0 blocked / 0 not_run**。脚本最终失败文本是剩余启动期限内的 UIAutomator dump 超时；较早发生的产品 native 崩溃由 DropBox、系统 exit-info 和最终空 PID 独立证实。失败截图与 XML 已核对，显示正常 Pixel Launcher。

这次没有完成启用 IME、Rime 部署、中文/英文输入、升级、工具舱或剪贴板流程。源码 CI / 本地 JUnit 数量不能并入本轮设备结果。前一次只因 apksigner 输出格式解析失败、未安装产品的记录保留于 [candidate-preflight](../candidate-preflight/README.md)，没有改写为本轮结果。

## APK、环境与崩溃

- APK：`app.lantype.keyboard`，1.1.1 / versionCode 3，179,987,242 字节。
- APK SHA-256：`b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497`。
- 唯一证书 SHA-256：`c03b15a19d2ed8899fee6b71f7be09ea5b54c7db9895d7d87b20a9759d8e090b`。
- 实际 Android 15 / API35，fingerprint `google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys`。
- KVM guest、user 0 已解锁，ABI `x86_64,arm64-v8a`、`libndk_translation.so`、bridge execution 1，页大小 4096 字节。

DropBox 明确记录 `Package: app.lantype.keyboard v3 (1.1.1)`，PID **3541** 于 **2026-11-17 15:45:49.072229879 UTC** 收到 `SIGSEGV / SEGV_MAPERR`，地址 `0x8`。ARM64 guest 帧如下：

```text
#00 libonnxruntime.so  pc 0x9caedc
#01 libc.so           pthread_once+148
#02 libonnxruntime.so  pc 0x9c9f60
#03 libonnxruntime.so  pc 0x16f550c
#04 libonnxruntime.so  pc 0x10d8160
#05 linker64          soinfo::call_constructors+604
#06 linker64          soinfo::call_constructors+140
#07 linker64          do_dlopen+2744
#08 linker64          __loader_android_dlopen_ext+72
#09 libnative_bridge_vdso.so  pc 0x4018
```

ORT BuildId 为 `b178f5c22304a25ff481e608260312842627e868`。系统 exit-info 同时记录 PID 3541，reason **5 / APP CRASH(NATIVE)**，status **11**。这些库偏移与之前旧版 API35 记录相同，但本页只依据这一次新版本本体执行作结论。

当前证据定位了 ORT 动态加载构造阶段；不直接推断物理 ARM64 必崩溃，也不把未验证的具体源码假设写成根因。guest 为 4096 字节页，不能当作 16 KiB 页面运行验收。

## 同 guest CPU 拓扑

失败后通过普通只读 shell 读取，未 root 或修改 CPU 属性。`/proc/cpuinfo` 报告四核 `AuthenticAMD / Android virtual processor`；sysfs 收到完整 **64 个 cache 字段**：

| 层级 | 实际 size/type/sharing |
|---|---|
| 每核 L1 Data | 64K，独核 |
| 每核 L1 Instruction | 64K，独核 |
| 每核 L2 | Unified，512K，`shared_cpu_list` 为各自 CPU 编号 |
| L3 | Unified，16384K，`shared_cpu_list=0-3` |

这是同 guest 的 shell 视图，供与匹配 ELF/源码分析交叉核对；它不是对 ARM 进程内 cpuinfo 两遍解析的插桩证据。

## 原始证据附件

- [run 44117540529](https://github.com/ZPJJJ/LanType/actions/runs/44117540529)，job `134159643388`。
- head：`5b5326524885caeaa389ecfe0ca4e7751d92173a`。
- [Actions artifact 14343862840](https://github.com/ZPJJJ/LanType/actions/runs/44117540529/artifacts/14343862840)，原平台保留期至 2026-11-24。
- [RC 配套原始证据](https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/LanType-1.1.1-candidate-startup-evidence.zip)：`LanType-1.1.1-candidate-startup-evidence.zip`，状态 **published_verified**；asset `759703647` 的大小和服务端 SHA-256 已与本地匹配。
- **42,881,346 字节，105 个成员**；SHA-256：`63ea1d9bfdf1d7317c310f5e86f030fdffca6722508157788570225124d7afc2`。
- 下载后验证服务端 digest，并拒绝 ZIP 绝对路径、父目录路径、符号链接和重复成员；归档复用原 ZIP 字节。

主要成员位于 `candidate-startup/`：`result.json`、`commands.jsonl`、`candidate-signature.txt`、`candidate-cpuinfo.txt`、`candidate-cpu-cache-topology.txt`、`candidate-native-dropbox.txt`、`candidate-native-tombstones.txt`、`candidate-exit-info.txt`、`candidate-pid.txt` 及 `0035-candidate-first-launch-failure.png/.xml`。机器回执见 [receipt.json](receipt.json)。模拟器正常停止回执为 `OK: killing emulator, bye bye` / `OK`。

本次记录只新增验收文档与原始证据附件，没有改变产品源码、签名 APK 或用户设备，也未由诊断代理发起其他 CI。
