# LanType 1.1.1 发布后的验证补充

记录日期：2026-11-17/18（中国标准时间；原始执行回执保留 UTC）。本页补充已经公开的 **1.1.1-rc1**，不改写发布时的验证附件、源码 ZIP、签名 APK 或发行标签。构建和单元测试证据与 Android 运行证据分开列示。

**当前结论：实际签名 1.1.1 已在 Android 15 的 ARM64 转译模拟器上复现 ORT 原生首启崩溃，尚不能作为稳定收费产品。** 该目标上的安装成功和源码 CI 通过均不能代替输入法运行验收；物理 ARM64 行为尚未知。

## 1. 交付物身份保持不变

- 发行页：https://github.com/ZPJJJ/LanType/releases/tag/v1.1.1-rc1
- APK：`LanType-1.1.1-offline-arm64-v8a.apk`，179,987,242 字节，版本 1.1.1 / code 3，包名 `app.lantype.keyboard`。
- APK SHA-256：`b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497`。
- 对应产品源码：公开提交 `abb0b9369424029f1d7418ca56fc6d38f2872f96`；产品树 `eaf49f2c975a33bda75c2d4dfdb9e1cc9cf0c481`。
- 发行标签和应用源码 ZIP 冻结于 `dc5f32d9775fb741962f8d7c0d983ee78f225627`；源码 ZIP SHA-256 为 `c4e727acdada3e2722a4d8d39eb4de21d211f628257a73a5cdf4a1fcd4ac0d69`。

本批后续修改仅涉及验收脚本、测试宿主、CI 环境、源码收集和文档；它们没有替换已发布 APK 的任何字节。当前仓库主分支的测试工具可以继续演进，因此不把主分支新提交误称为发行标签，也不把整个 CI APK 和正式签名 APK 说成字节相同。

## 2. GitHub 源码 CI：通过

[run 44103398875](https://github.com/ZPJJJ/LanType/actions/runs/44103398875) 已完成，结论为 `success`，绑定源码提交 `1bcafe8b47e6aed3e713a194a64e63bfb8bb9f28`。该提交与签名版本的产品代码一致，后续 QA 工具不在此次 CI 的验收范围内。

| 检查 | 实际结果 |
|---|---|
| JUnit | 27 个类、187 个唯一用例全部通过；失败、错误和跳过均为 0 |
| 固定原生源码验证 | 另外 12 项 Python 测试通过，单列统计 |
| 构建 | 离线发行变体编译成功；此处的“离线”是变体名，CI 首次准备仍可联网下载依赖 |
| CI APK 静态检查 | 379 个 assets、11 个 raw 与固定清单匹配；扫描未签名 APK 的 2,161 个条目 |
| Compose 渲染 | 保存 20 张 PNG；生成成功不等于逐张视觉验收，也不代替设备测试 |

本地 96 个定向用例包含在上述 187 个用例中，不相加为 283。正式签名 APK 的静态记录检查 2,164 个条目，与未签名 CI 产物分开。证据附件为 `LanType-1.1.1-hosted-source-ci-evidence.zip`，1,786,829 字节，SHA-256 为 `91b8de509c3ed9d778ddd7932b072bf1d39f994fee72f67ab182573a5ce2dbee`。详细回执见 [源码 CI 记录](hosted-source-ci/README.md)。

## 3. Android 运行验证：按环境分别记录

### 本地 API 30 软件模拟器

完成旧签名 1.1.0 安装和启动意图前断网。随后 Android framework、Pixel Launcher、System UI 等系统问题阻碍可靠交互，1.1.1 未安装。此尝试已停止，保留原数据；详情见 [本地 TCG 记录](local-tcg/README.md)。不能从安装成功推导输入功能通过，也不能把系统 ANR 直接归为产品缺陷。

### GitHub KVM / API 30：观察到产品进程崩溃

[run 44109387258](https://github.com/ZPJJJ/LanType/actions/runs/44109387258) 使用实际解锁的 Android 11 / API 30 x86_64 guest 和 ARM64 `libndk_translation.so`。在飞行模式 1、Wi-Fi 0、移动数据 0 的条件下，旧签名 1.1.0 安装成功，但首次启动的主进程出现 `SIGSEGV / SEGV_MAPERR`，错误地址 `0x8`，没有出现可用的产品向导。

原始 core 结果为 **3 passed / 1 failed / 8 blocked / 1 not_run**；独立剪贴板步骤未执行。通过的三项为身份、断网和安装前置检查，不是三项输入功能通过。**新版 1.1.1 未安装，因此这次不能算新版运行通过或新版运行失败。**

匿名 x86_64 帧无法确定责任库。源码和实际 ELF 证据确认冷启动会通过 Rime 加载 ONNX Runtime，但属性访问 warning 与崩溃时间相邻不能证明因果，现有证据也不能证明本次主进程加载了 Sherpa。详情见 [API 30 回执](api30-native-bridge/README.md) 和 [加载路径分析](api30-native-bridge/native-loading-analysis.md)。

原始附件 `LanType-1.1.1-api30-native-bridge-evidence.zip` 为 13,437,261 字节、77 个成员，SHA-256 为 `e6abd41854bbaa6d13d13a46deae8a811188c5590c82d7089fea203f84c763c3`，逐字节保留 Actions artifact。

### GitHub KVM / API 35：再次观察到旧版首启崩溃

[run 44112396806](https://github.com/ZPJJJ/LanType/actions/runs/44112396806) 使用相同的两份已发布签名 APK，工作流提交为 `8811716a1e99b25a9bc97a6b638a45f7d0b04276`。实际 guest 为 Android 15 / API 35，指纹 `google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys`；启动、用户解锁、ARM64 ABI 和 native bridge 门禁均通过，页面大小为 4096 字节。

旧签名 1.1.0 再次在首启时崩溃，core 仍为 **3 passed / 1 failed / 8 blocked / 1 not_run**，独立剪贴板步骤跳过，1.1.1 仍未安装。此次 DropBox 保存了 ARM64 guest 回溯：`libonnxruntime.so` 的 `0x9caedc` 等地址，接着是 `pthread_once`、动态链接器 `call_constructors / do_dlopen`；系统 exit-info 同时记录 `APP CRASH(NATIVE)` / status 11。由此可把本次故障定位到 **ORT 动态库加载时的构造初始化阶段**。

BuildId `b178f5c22304a25ff481e608260312842627e868` 与交付库吻合。这个结论仍不能自动推广成所有物理 ARM64 设备都会失败，也不等于已经定位某一行 C 源码或证明 bridge 责任。完整证据与边界见 [API 35 回执](api35-native-bridge/README.md)。原始附件 `LanType-1.1.1-api35-native-bridge-evidence.zip` 为 24,213,250 字节、68 个成员，SHA-256 为 `f6236f55f67fccbd3254ea182b71704b42bfb96f1d600d3c12332b0c80994d5c`。

### 1.1.1 独立首启检查

旧版升级基线失败不能替代新版测试，因此另设只安装 1.1.1 的独立检查。[run 44117540529](https://github.com/ZPJJJ/LanType/actions/runs/44117540529) 实际在全新 API 35 KVM guest 安装了原签名 **1.1.1 / code 3**；安装前确认 APK 大小、SHA-256 和原发行证书，断网读回为飞行模式 1 / Wi-Fi 0 / 移动数据 0。四项检查中 **3 passed / 1 failed**：通过的是身份、断网和安装，失败的是首启。

在 **2026-11-17 23:45:49（中国标准时间）**，产品主进程 PID 3541 发生 `SIGSEGV / SEGV_MAPERR`、错误地址 `0x8`。系统 DropBox 明确记录包版本 3（1.1.1），ARM64 guest 回溯中的 ORT 地址 `0x9caedc`、`0x9c9f60`、`0x16f550c`、`0x10d8160` 和 BuildId 与旧版相同；exit-info 为 `APP CRASH(NATIVE)`、status 11。后来的 UI dump 超时是脚本最终报告的症状，不能据此把已经发生的产品 native crash 归为单纯查找 UI 失败。最后截图和 XML 仅显示 Launcher，产品向导与主进程均未保留。

原始证据为 `LanType-1.1.1-candidate-startup-evidence.zip`，42,881,346 字节、105 个成员，SHA-256 `63ea1d9bfdf1d7317c310f5e86f030fdffca6722508157788570225124d7afc2`。具体运行、文件与证书身份见 [候选版首启回执](candidate-startup/README.md)。它不能证明首次资源部署、IME 输入、保留数据升级或工具舱隐私进程重启通过。

同一 guest 在崩溃后的 adb shell 中显示四核、各核私有 512K L2 及共享 16384K L3。固定 cpuinfo 源码的缓存计数与填充分两阶段进行；其与已观测初始化路径吻合，是具体候选原因。**未直接观察 ARM 进程内部的 `l2_count` 或 native bridge 提供的全部输入，尚不能断言已经证明源代码根因。** 上游候选 PR #457 当时尚未合并，需要适配当前固定版本并完成回归及原生重编；本 APK 尚未应用该补丁。详见 [CPU 信息分析与边界](candidate-startup/cpuinfo-analysis.md)。

此前 [run 44116007517](https://github.com/ZPJJJ/LanType/actions/runs/44116007517) 只在检查器的签名输出格式解析处停止，未安装产品。实际证书摘要正确；兼容新旧两种已观测标签后，才得到上面的真实安装和启动结果。[前置检查回执](candidate-preflight/README.md) 保留这一区别，不将它算作第二次产品启动失败。

## 4. 原生源码覆盖更正

已交付 ORT 的实际 ELF 包含 Dawn/WebGPU；原 70 份基础原生来源归档遗漏了这部分源码和必要嵌套构建依赖。APK 内的 Dawn 许可原文已存在，此次补正的是源码覆盖。固定 **7 份原始归档、13 份许可/通知和 23 份来源原文**已通过独立字节核验，并发布为 `LanType-native-source-webgpu-supplement-v1.zip`；105,554,498 字节，SHA-256 `6eabae67a60bdb0f3eaab9858f58b1f712edb9f85bb4c5cf75d800e7f530691d`。详情、旧来源复用关系、供应商构建参数仍未知的边界与校验方法见 [Dawn 源码补充说明](../licensing/DAWN-SOURCE-SUPPLEMENT.md)。这项补充不修改旧 APK，也不修复上述启动故障。

## 5. 商用状态和剩余门槛

**本版继续标记为预发布，正式收费发行的质量门槛尚未完成。** GPL 允许收费分发的许可结论，不能代替设备兼容性验收或销售渠道审核。

正式收费前仍需可靠目标完成首次部署、中文和美式英文输入、同签名保留数据升级、工具舱实际读写与剪贴板进程重启流程，并在物理 ARM64 手机上验证离线语音、手写、OCR、响应速度和持续使用。16 KiB 页运行只具备静态对齐证据，尚无对应设备运行结论。

商用方案中的人民币 19 元早期价、29 元正式价、4.99 美元海外价均为待验证建议。本次没有创建收款商品、提交商店审核或开始收费。当前应使用免费的 RC 收集明确、可复现的设备反馈；稳定版继续按 GPLv3 提供对应源码和第三方许可，不加入联网激活。

完整计划见 [商用方案](../COMMERCIAL-PLAN.zh-CN.md)，未完成事项见 [收费发行检查表](../RELEASE-CHECKLIST.zh-CN.md)。

## 6. 原生修复工作未完成

CPU 初始化候选修复的辅助任务在准备和隔离 host 回归后，被自动安全审查中止，提示可能的网络安全风险。现有工作记录已保留；未通过改写请求、换执行路径或另起同类任务继续被中止步骤。该执行限制不是对本产品存在可利用安全漏洞的定论，也不构成候选补丁可用于发行的批准。

本轮没有完成 ORT 集成重编，没有把候选改动合入产品，也没有产生新的修复 APK。此前 187 个应用 JUnit 成绩和本轮真实设备失败结论保持各自范围，不把未完成的原生辅助回归混入产品通过计数。
