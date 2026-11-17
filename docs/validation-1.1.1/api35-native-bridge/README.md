# API 35 ARM64 native bridge：ORT 首启崩溃对照

本页记录与 API 30 分开的 Android 15 / API 35 对照。**旧签名版 1.1.0 安装成功，首次启动在 `libonnxruntime.so` 动态库构造初始化阶段发生 native SIGSEGV；新版 1.1.1 尚未安装。** 本次保留的 ARM64 guest 回溯已能命名 ORT 库与加载阶段，但不能据此推断物理 ARM64 必然崩溃，也不能直接确定某个源码根因。

## 实际环境与结果

- GitHub KVM 加速可用，guest 已完成启动，user 0 为 `RUNNING_UNLOCKED`。
- 实测 Android 15 / API 35、Google APIs x86_64 镜像 revision 9。
- fingerprint：`google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys`。
- 实际 ABI 为 `x86_64,arm64-v8a`，`libndk_translation.so` 已配置，native bridge execution 为 1。
- guest 页面为 4096 字节；此结果不替代 ARM64 真机、16 KiB 页面、性能或耗电验收。
- 首次安装前飞行模式为 1、Wi-Fi 为 0、移动数据为 0。

| 项目 | 观察结果 |
|---|---|
| 环境与发行 APK 身份 | 通过 |
| 首次产品安装前断网 | 通过 |
| 旧版 1.1.0 与独立编辑器 host 安装 | 通过 |
| 首启向导 / Rime / IME 设置 | 失败：产品进程在向导出现前 native 崩溃 |
| 后续中文、英文、模板、升级与工具舱 | 8 项因前置失败而阻塞 |
| core 中的剪贴板占位项 | 1 项未运行 |
| 独立跨进程剪贴板步骤 | core 失败后被工作流跳过 |

原始 core 为 **3 passed / 1 failed / 8 blocked / 1 not_run**。新 APK 只核对了输入文件身份，没有安装或执行。不得将源码 CI 或本地 JUnit 的通过数并入此次设备计数。

## 命名 guest 回溯

DropBox 记录旧版 `app.lantype.keyboard v2 (1.1.0)`，PID 3574，于 2026-11-17 15:18:48.713724823 UTC 收到 `SIGSEGV / SEGV_MAPERR`，错误地址 `0x8`。

host 帧仍为 `/memfd:exec (deleted)`，但本次 ARM64 guest 帧明确为：

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

对应 ORT BuildId：`b178f5c22304a25ff481e608260312842627e868`。`product-exit-info.txt` 独立记录同一 PID 的 reason 5 / `APP CRASH(NATIVE)` / status 11。完整 SYSTEM_TOMBSTONE 包含更多寄存器与内存映射。

这条回溯将失败范围定位到 ORT 的动态加载构造初始化过程；它没有证明 Rime 初始化错误、具体 ORT 源码缺陷或 native bridge 的责任。最终 PNG 和 UI XML 显示正常 Pixel Launcher，不能将缺少向导文字当作独立的选择器问题。后续若做库加载探针，应与正式 APK 的功能验收分开记录。

## 原始证据附件

- [GitHub run 44112396806](https://github.com/ZPJJJ/LanType/actions/runs/44112396806)，job `134141227368`。
- workflow head：`8811716a1e99b25a9bc97a6b638a45f7d0b04276`。
- [原始 Actions artifact 14341387652](https://github.com/ZPJJJ/LanType/actions/runs/44112396806/artifacts/14341387652)，原平台保留期至 2026-11-24。
- RC 配套附件：`LanType-1.1.1-api35-native-bridge-evidence.zip`；当前状态：**已发布并核对服务端大小与 SHA-256**。
- 文件大小：**24,213,250 字节**，68 个成员。
- SHA-256：`f6236f55f67fccbd3254ea182b71704b42bfb96f1d600d3c12332b0c80994d5c`，下载后与服务端 digest 核对一致；附件原样复用，不改写 ZIP。

ZIP 内关键成员：

- `smoke/result.json` 与 `smoke/commands.jsonl`：逐 case 结果、APK/guest 身份和实际命令。
- `native-app-dropbox.txt`：命名 ORT guest 回溯。
- `native-system-tombstones.txt`：完整原生诊断和内存映射。
- `product-exit-info.txt`：系统退出原因。
- `smoke/0019-first-run-rime-and-ime-setup-failure.png` / `.xml`：最终画面和 UI 树。
- `accel-check.txt`、`system-image.txt`、`emulator-stop.txt`：KVM、镜像与停止记录。

机器可读回执见 [receipt.json](receipt.json)。此次归档仅新增诊断文档和证据附件，没有改变产品源码、签名 APK 或用户设备。

发行附件：[下载原始证据](https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/LanType-1.1.1-api35-native-bridge-evidence.zip)。
