# API 30 ARM64 native bridge：首启崩溃记录

本页记录一次真实但未完成的设备验收：GitHub KVM 上的 Android 11 / API 30 Google APIs x86_64 模拟器已启动并解锁，通过 `libndk_translation.so` 提供 ARM64 翻译。**旧版 1.1.0 安装成功，但首次启动的产品进程发生 native SIGSEGV；新版 1.1.1 尚未安装。** 不能把这次结果写成输入、升级或隐私流程通过。

## 实际结果

| 项目 | 观察结果 |
|---|---|
| 环境与发行 APK 身份 | 通过 |
| 产品安装前断网 | 通过：飞行模式 1、Wi-Fi 0、移动数据 0 |
| 旧版 1.1.0 与独立编辑器 host 安装 | 通过 |
| 首启向导 / Rime / IME 设置 | 失败：向导出现前产品进程 native 崩溃 |
| 后续中文、英文、模板、升级与工具舱 | 8 项因前置失败而阻塞 |
| core 中的剪贴板占位项 | 1 项未运行 |
| 独立跨进程剪贴板步骤 | core 失败后被工作流跳过 |

原始 core 报告为 **3 passed / 1 failed / 8 blocked / 1 not_run**。这些是该次设备脚本的结果，与本地 JUnit 或源码 CI 的测试数分开计算。

## 崩溃及定责边界

2026-11-17 15:03:30 UTC，旧版 `app.lantype.keyboard` 的 PID 5049 收到 `SIGSEGV / SEGV_MAPERR`，错误地址 `0x8`。短回溯记录 ABI 为 x86_64，仅有以下匿名帧：

```text
#00 pc 0000000000377e43 <anonymous:7435eea72000>
```

日志确认 aarch64 NDK translation 0.2.2 已初始化，最终截图和 UI XML 显示正常 Pixel Launcher。**该证据能证明 ARM64 翻译环境中的产品进程崩溃，但匿名帧不能识别责任库，也不能判定是翻译桥还是产品原生代码的缺陷。** 缺失向导标题是崩溃后的现象，不能通过更换文字选择器或延长等待把这次失败计为通过。下一次诊断需保留完整产品 tombstone、内存映射和 DropBox native crash 信息。

这台 guest 的页面大小为 4096 字节，不能替代 ARM64 真机、16 KiB 页面运行、性能或耗电验收。后续 API 35 对照若产生结果，应单独记录，不回填本次状态。

## 原始证据附件

- [GitHub run 44109387258](https://github.com/ZPJJJ/LanType/actions/runs/44109387258)，job `134130526696`。
- workflow head：`c88037c3eeaec198aa80c0337523c3e3a88dbae9`。
- [原始 Actions artifact 14341085571](https://github.com/ZPJJJ/LanType/actions/runs/44109387258/artifacts/14341085571)，原平台保留期至 2026-11-24。
- RC 配套附件文件名：`LanType-1.1.1-api30-native-bridge-evidence.zip`；当前归档状态：**已发布并核对服务端大小与 SHA-256**。
- 文件大小：**13,437,261 字节**，77 个成员；附件逐字节复用原 artifact，未改写证据。
- SHA-256：`e6abd41854bbaa6d13d13a46deae8a811188c5590c82d7089fea203f84c763c3`。

ZIP 内关键成员：

- `smoke/result.json`：逐 case 结果和 APK / guest 身份。
- `smoke/commands.jsonl`：实际执行命令与返回。
- `smoke/first-run-rime-and-ime-setup-crash.txt`：native 崩溃短回溯。
- `smoke/first-run-rime-and-ime-setup-logcat.txt`：同次诊断日志。
- `smoke/0025-first-run-rime-and-ime-setup-failure.png` / `.xml`：最终画面和 UI 树。

机器可读回执见 [receipt.json](receipt.json)。此次归档只增加验收文档及证据附件，不修改产品源码、签名 APK 或用户设备。

发行附件：[下载原始证据](https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/LanType-1.1.1-api30-native-bridge-evidence.zip)。
