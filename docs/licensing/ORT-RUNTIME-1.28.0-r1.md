# LanType ORT 1.28.0-r1：构建来源、产物与许可

**当前记录状态：组件已公开预发布，accepted 锁用于固定应用集成输入。** 接受依据为原生构建、静态 ABI、AAR 内容核验及第六次普通 Android API 结果；该次 workflow 因最后卸载工作卷失败而整体失败，第七次停在主机登记阶段。真实 ARM64 设备、模型推理和应用整包仍待验收。原始 candidate manifest 和准备回执保持原字节，不追改其中的历史状态。公开 ZIP、锁与清单身份见第 8 节。

`1.28.0-r1` 是 LanType 的组件修订名；ORT 上游版本及 C API 版本仍为 **1.28.0 / API 28**。这是项目采用生产源码补丁后的独立构建，保留上游和第三方各自的许可、版权与归属。

## 1. 实际构建与证据入口

- 原生构建：[GitHub Actions run 44164186969](https://github.com/ZPJJJ/LanType/actions/runs/44164186969)，状态 `completed / success`；构建结束时间 `2026-11-17T20:25:40Z`。
- 固定项目提交：[`6d80145d1c15e646fae1404ec93c0c9520033e10`](https://github.com/ZPJJJ/LanType/commit/6d80145d1c15e646fae1404ec93c0c9520033e10)。
- 同提交的[构建 workflow](https://github.com/ZPJJJ/LanType/blob/6d80145d1c15e646fae1404ec93c0c9520033e10/.github/workflows/native-ort-build.yml)、[原生构建脚本](https://github.com/ZPJJJ/LanType/blob/6d80145d1c15e646fae1404ec93c0c9520033e10/scripts/build-ort-native.py)、[静态 ABI 检查器](https://github.com/ZPJJJ/LanType/blob/6d80145d1c15e646fae1404ec93c0c9520033e10/scripts/verify-ort-abi.py)、[Dawn 来源处理脚本](https://github.com/ZPJJJ/LanType/blob/6d80145d1c15e646fae1404ec93c0c9520033e10/scripts/collect-dawn-source-supplement.py)及[空间门禁](https://github.com/ZPJJJ/LanType/blob/6d80145d1c15e646fae1404ec93c0c9520033e10/scripts/storage_guard.py)共同确定此次构建入口。
- 原生候选 `candidate-manifest.json` SHA-256：`eb7adfcd1fe2c7c000ad29e99649035bea6c59f14aef1803fdf6f9649e2d1a07`。其 **19 个文件**已逐一核对大小和 SHA，候选目录除此清单及 manifest 本身外没有其他文件。manifest 保留 `applicationIntegrated: false`、`androidRuntimeAccepted: false`。
- 构建输入 fingerprint：`3ba54705fc9b1bd484f1a49eb9a309809b19e50d72553064a1ce46f43ee1e581`。`receipts/state.json` 记录 24 个实际源码归档、补丁和命令；`prepared-sources.json`、`configured-sources.json` 与 `provider-compile-inputs.json` 记录准备后源码及编译输入身份。宿主 `protoc` 是另列的构建工具。

Actions 链接用于追溯构建。已公开组件另存上述原始 manifest 和回执，使长期来源记录不只依赖 Actions artifact 的保存期限。

## 2. 固定源码及 cpuinfo 生产补丁

| 输入 | 固定版本或提交 | 归档字节数 | 归档 SHA-256 |
|---|---|---:|---|
| ONNX Runtime | [`da9b5e364c465de65c49d91e696cd6485270757f`](https://github.com/microsoft/onnxruntime/tree/da9b5e364c465de65c49d91e696cd6485270757f)，1.28.0 | 278,684,279 | `bf6f1db69e3bc7d075f97d1bd7271ce7b062b9ba33d8a3ffb82638ad57331f9f` |
| cpuinfo 基线 | [`4628dc060ce4e82345dc166bbac875609db4ff69`](https://github.com/pytorch/cpuinfo/tree/4628dc060ce4e82345dc166bbac875609db4ff69) | 3,857,758 | `2ed3ebc6c2656cc0aafc7af319e5cb0f97cc9b415eae180f566def84f1ca6a29` |
| Dawn / Tint | [`ec7b457e5bb1fcec6f59733c4f3dd84d2f885a38`](https://dawn.googlesource.com/dawn/+/ec7b457e5bb1fcec6f59733c4f3dd84d2f885a38) | 94,578,448 | `4046fc60d9956fd9621ae6ce9148fb81a36b9b54e69952e735c4315909dc56dd` |

其他实际选用依赖的归档名、来源与摘要见固定提交中的 [native-sources.lock.json](https://github.com/ZPJJJ/LanType/blob/6d80145d1c15e646fae1404ec93c0c9520033e10/docs/licensing/native-sources.lock.json)、[native-sources-webgpu.lock.json](https://github.com/ZPJJJ/LanType/blob/6d80145d1c15e646fae1404ec93c0c9520033e10/docs/licensing/native-sources-webgpu.lock.json)及候选 `receipts/state.json`。本次实际选用集合与旧应用的整套 70 项基础来源清单分别记录。

项目补丁位于 [`patches/onnxruntime/cpuinfo-4628dc0-pr457-l2-backport.patch`](../../patches/onnxruntime/cpuinfo-4628dc0-pr457-l2-backport.patch)，4,310 字节，SHA-256 `6281246ef5bafdae6f64a9b1c4bbd64ddcd6b0b65a8150c9bd0343e3cfdf998b`。它回移 [cpuinfo PR 457](https://github.com/pytorch/cpuinfo/pull/457) 的两个生产提交：

- [`956614a1e93e1aca95b1cc03484647a187b199b4`](https://github.com/pytorch/cpuinfo/commit/956614a1e93e1aca95b1cc03484647a187b199b4)：使 L2 计数阶段采用与填充阶段一致的 sysfs 容量覆盖。
- [`bd8f30173a7d7f08842fdaf838fc7c02a86b92ea`](https://github.com/pytorch/cpuinfo/commit/bd8f30173a7d7f08842fdaf838fc7c02a86b92ea)：保护两个 L2 写入位置，并仅为已写入的描述符设置缓存指针。

**截至 2026-11-17 UTC 的官方 PR 元数据核对，PR 457 仍为 open，`merged: false`。** 应描述为项目选择并回移的上游提案，不能称为已合入的官方 cpuinfo 修复版本。补丁保留 Soma Aishwarya、Qubitium 的作者归属；只调整所需上下文，保留冻结基线的 L3 行为。PR 的 mock 测试变更未纳入产品补丁。

| `src/arm/linux/init.c` 身份 | SHA-256 |
|---|---|
| 补丁前 | `daaf6633d55c983e9b517d748d1fdf3df580c6c8bef03e4fd3811ba47f175e4f` |
| 本次编译输入 | `94a7bd19139090a0568e173f80dea5e42ea1326d04e3eddf46554f5243e5229c` |

cpuinfo 补丁以零上下文 fuzz 应用。另按固定 ORT 源码顺序应用其已有的 7 个 Dawn 补丁；每个补丁及目标文件前后哈希均记入 `state.json`。Dawn 补丁保留上游允许的最大 fuzz 2，同时以固定目标文件前后哈希限制实际结果。

## 3. 工具链与功能配置

| 项目 | 此次实际值 |
|---|---|
| Android ABI / 平台 | `arm64-v8a` / `android-28` |
| NDK | `29.0.14206865` |
| 固定 ORT 官方 Android CI 的 NDK 配置 | `28.0.13004108` |
| CMake / Ninja / Python | `3.31.6` / `1.13.2` / `3.12.3` |
| 构建模式 | `Release`、C++20、LTO、`c++_static` |
| ORT 范围 | `MINIMAL_BUILD=OFF`，contrib ops 与 ML ops 均未禁用 |
| Provider 配置 | CPU、NNAPI、XNNPACK、WebGPU；Dawn 静态链接，Vulkan 后端启用 |
| Java / 测试构建 | 原生构建不重编 Java；ORT、cpuinfo、Dawn、XNNPACK 测试未构建或执行 |

NDK 29 是项目为使用 runner 已安装工具链而作出的明确选择；工具二进制 SHA、NDK `source.properties` SHA 均在构建回执的 `tools` 中保存。原供应商的完整 CMakeCache 与原始构建命令仍不可得，因此没有建立与旧供应商 ELF 逐字节相同的复现承诺。官方 NDK 28 配置参照固定 ORT 源树的 [Android CI](https://github.com/microsoft/onnxruntime/blob/da9b5e364c465de65c49d91e696cd6485270757f/.github/workflows/android.yml)。

配置回执还记录了实际编译命令条目：CPU 134、NNAPI 41、XNNPACK 14、WebGPU 81、Dawn 153、Tint 435、cpuinfo 2。这些条目证明相应实现进入编译输入；第六次 API 检查另已枚举四种 provider 名称，但没有创建推理会话或执行模型，实际 provider 推理仍待验收。

`c++_static` 使用 NDK 29 的标准运行时。基础来源锁中 `android-libcxx` / `android-libcxxabi` 的 LLVM `d8003a456d14a3deb8054cdaa529ffbf02d9b262` 条目，仅对应旧 APK 的 `libc++_shared.so` 证据；**不能用它们证明新 NDK 29 静态运行时的精确来源**。本修订另按以下官方发行及实际安装证据记录这两个静态输入。

### NDK 29 来源、实际静态输入与通知

[Android NDK 官方 r29 发行页](https://github.com/android/ndk/releases/tag/r29) 将版本固定为 `29.0.14206865`，并说明采用 `clang-r563880c`，精确 LLVM 版本信息参见发行包内 `clang_source_info.md`。该页列出的 [Linux 官方 ZIP](https://dl.google.com/android/repository/android-ndk-r29-linux.zip) 为 783,549,481 字节，官方 SHA-1 为 `87e2bb7e9be5d6a1c6cdf5ec40dd4e0c6d07c30b`。本次核对了公开发行元数据，没有重新下载这份大型 ZIP，也没有把其官方 SHA-1 当作本地已测 SHA-256。

后续 [API 准备 run 44173535722](https://github.com/ZPJJJ/LanType/actions/runs/44173535722) 的 `tools` 阶段从 runner 实际安装的 `/usr/local/lib/android/sdk/ndk/29.0.14206865` 收集了 `ndk-source-inputs.json`：2,449 字节，SHA-256 `2bd815d11926c30be0091cabc82ddf92c7665c21f3401665e5990238e2f20b66`。其 `source.properties` 为 107 字节，SHA-256 `716f3518a923198cfab037abb32dc3f1b1f7e9a9dcdcda6b66be5906215d2658`，revision 与该文件哈希均和原生构建 run 的工具链记录一致。

| 实际 AArch64 静态输入 | 字节数 | runner 记录的 SHA-256 |
|---|---:|---|
| `toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_static.a` | 24,112,434 | `e5743581dcb88324662ada5adae6036d8ad3568e834eb0f59d5f4e329764d6ab` |
| `toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++abi.a` | 4,877,212 | `44ecebe37ac8fe7495d35374aee70273fefc11cacc28fc95a087eaab65a207ae` |

路径相对于上述 NDK 根目录。回执记录两份 archive 为 `present: true`、`copied: false`：保存了实际大小与摘要，没有把静态二进制再复制进证据包。另有三份原始通知和 `source.properties` 共 1,446,608 字节，已逐份复核复制件的大小和 SHA；通知身份见第 7 节。

这份取证证明该次 runner 上同版 NDK 的安装元数据、标准运行时输入及随包通知身份；它不是完整 NDK/LLVM 源码分发，也不是对既有 ORT 链接过程的独立重演。run 44173535722 没有取得 Android API 运行通过结果。第六次 API run `44232550186` 重新取得了相同 SHA 的 `ndk-source-inputs.json`、元数据和通知；其独立运行结果见第 5 节。

## 4. AAR 处理与三份实际输出

输入为[官方 Maven AAR](https://repo.maven.apache.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/1.28.0/onnxruntime-android-1.28.0.aar)，45,634,470 字节，SHA-256 `f351a0638696f54b35184290dbc001d66daae17281ad0b548d2c70347d53b8a9`。原 arm64 主库是 28,637,280 字节，SHA-256 `f826d8efb03adf0a84f10e7ba408f9d4cd11b0a2ccd8d08aeb0f7451fb50cacc`。

由 [prepare-ort-runtime.py](../../scripts/prepare-ort-runtime.py) 生成以下输出；该次工具 SHA-256 为 `564250437945519eed6908837705beec0816eb7b48cb1a619ff60ac59f5bdde8`。这三份输出在开发构建时恢复到仓库 `vendor/ort-runtime/` 下，原始 AAR 保留原字节。

| 相对文件名 | 字节数 | SHA-256 |
|---|---:|---|
| `onnxruntime-android-1.28.0-lantype-r1.aar` | 120,716,721 | `de572de0c790119e7085144070fc5580e7857c2eba68998aba287f59ad98abc0` |
| `onnxruntime-android-1.28.0-lantype-r1-cmake.aar` | 91,147,839 | `eb70f3c6932b75b20e71ab3e9808385120b7b5bf3c0345d61b689af504fe4562` |
| `arm64-v8a/libonnxruntime.so` | 29,568,744 | `ae250081faa6cd742f6edade2a23bf29a96ba690fa19a01e3bd192548cf89f1e` |

Full AAR 保留原来的 40 个成员，仅把 `jni/arm64-v8a/libonnxruntime.so` 的内容替换成上述新 ELF。其余 **39 个成员内容不变，包含 28 个普通文件和 11 个目录项**。Companion AAR 在此基础上仅省去这一个主库成员，供 CMake 已提供主库的源码构建模式使用；两者保留同一份官方 Java classes 和 JNI bridge。

- `classes.jar`：121,402 字节；SHA-256 `e671acbff1bb86ffbbbe7701cf9351a04e1f58c51ae5b031912451e5988471b6`。
- `jni/arm64-v8a/libonnxruntime4j_jni.so`：111,648 字节；SHA-256 `99db53ca399095cfa17f3f40924b1012a0ff5846c32198e8cef01dd8480f6b45`。

其他 ABI 的原始成员同样保留；本修订只替换 ARM64 主库。ZIP 容器使用固定顺序、时间、权限与 `ZIP_STORED` 重新生成；“成员不变”指解压后的内容身份。重复成员、不安全路径、特殊文件和不符哈希均拒绝处理。

| 此前候选准备证据（历史记录） | 字节数 | SHA-256 |
|---|---:|---|
| `ort-runtime-r1-candidate.lock.json` | 730 | `6e8af18909d056ce02f6e4dea29b5e625901021d7e4225c0583b33cc93814624` |
| `preparation-receipt.json` | 8,171 | `ef2b4b31419bb6a861c1ef020dcb69558b1a433caff99b39fc763d5837c05a63` |
| `ort-runtime-r1-candidate-verify.json` | 8,087 | `54565122c52b1cefcfd5a3142d401c4e31487a7388cb225d125a5124f0b84c28` |

此前准备后已用同一 candidate 锁和原始 AAR 对最终目录再次执行 `--verify-only`，三输出及完整成员比较均一致。上表保留此前文件身份；其中 `acceptedLock: false` 或 `status: candidate` 描述当时准备状态，不改写为 accepted。

### 2026-11-18 恢复输入后的重新准备

本次从同一固定官方 Maven URL 恢复原始 AAR，逐字节核对其 45,634,470 字节和 SHA 后，使用同一工具、原生构建候选和显式 candidate 锁重新生成 full/companion AAR，再执行 `--verify-only`。两条命令均退出 0；三份输出与上表历史身份完全一致，40/39 个成员的内容比较通过。这个步骤只读写 ZIP 和普通文件，没有执行 SDK、编译器或原生代码。

以下是 **11 月 18 日新生成的回执**；上表旧身份继续保留为历史记录。回执记录实际输入路径和锁，因此回执本身的字节数与 SHA 不同；不能用新回执覆盖旧记录或声称两份回执逐字节相同。组件的 `evidence/package/` 使用下表新回执，不把旧回执摘要套用到新文件。

| 11 月 18 日准备证据 | 字节数 | SHA-256 |
|---|---:|---|
| `ort-runtime-r1-candidate.lock.json` | 388 | `99b9af72a8dd32919a8957431419b963a3182ca6f38d1d36cf5a12e53a28b30f` |
| `candidate-runtime/preparation-receipt.json` | 8,195 | `897dd87e0d00d8f32f1d588414bdbc169f4d6ead957dab1b9d2e3d026e9880d8` |
| `candidate-verification.json` | 8,087 | `ed2079985c55c740e335be00d3cc48d3461af9aa72c104cd2e18ba8d2ff30dab` |
| `commands.json` | 3,046 | `44b0dbdaa5c5cdeece05dd06cf5bc3b5d0d396a82ea7867b3a3c677bf0682a4e` |
| `completion.json` | 4,362 | `8d377534d385d2c756fe66e56567b05e1227a1b2baed31ac24f4ade98a4de278` |

新准备回执仍是 candidate 状态，记录 `acceptedLockCreated: false` 和 `applicationIntegrated: false`。后续接受决定已以独立外部锁登记，并引用实际 API 结果；原始 19 文件 candidate manifest 及新旧准备回执记录均保留其当时语义。

## 5. 已通过与待验证范围

候选 `receipts/abi.json` 为 9,336 字节，SHA-256 `d28c2890dbed469701f916c297c681e6bb3f5dec128a9986bb7cc85bdc555e7f`，**10 项静态检查全部通过**：ELF64/AArch64/DYN、SONAME、既有系统库依赖集合、`VERS_1.28.0`、三个版本化 C 函数导出、LOAD 对齐及地址同余、RELRO、无 TEXTREL。新 ELF BuildId 为 `9e2640d89d30723e1d7264e901a5e619a42fff63`。

静态合同来自已签名 LanType 1.1.1 APK 的 12 个原生库；合同 [ort-shipped-abi.json](ort-shipped-abi.json) SHA-256 为 `e0b561300641a4a966f658d5376153d48e9a8a1a6f8d99cf1f6bec49e6c0cc62`。静态结果不执行库，也不验证 C API 函数表、模型推理、驱动可用性、最终 APK ZIP 对齐或 16 KiB 设备行为。

| 验收项 | 本记录状态 |
|---|---|
| 普通 Android 环境的 `dlopen`、API 28 表、provider 枚举、`CreateEnv` / 释放 | 第六次 run `44232550186` 的 API 结果 `passed`；API 35 ARM64 bridge、4 KiB；workflow 因最后清理失败而整体 `failure` |
| 真实 ARM64 设备启动与推理 | 待验证 |
| 输入法启用、中英文输入、OCR、语音及模型路径 | 待应用整包验收 |
| 最终 APK 中新 ORT 精确哈希、其他 11 个库及资产保留 | 待整包构建后核验 |
| accepted 锁、component ZIP 外层大小 / SHA / 公开资产身份 | 已公开预发布；实际身份与有限接受范围见第 8 节 |

[第六次 API run](https://github.com/ZPJJJ/LanType/actions/runs/44232550186) 的 head 为 `e909dd8e5050cb80537761ff6fe5acb34b96be1a`，job 为 `134560859337`。固定 19 项 manifest 和新 ELF 身份再次核对通过；ARM64 instrumentation JNI worker 在 API 35 x86_64、`libndk_translation.so`、4,096 字节页大小的 guest 中正常返回，probe 退出码为 0，13 个阶段通过。检查取得 ORT `1.28.0`、C API `28` 并枚举 CPU/NNAPI/XNNPACK/WebGPU，没有执行模型推理。运行前飞行模式为 1，Wi-Fi/移动数据为 0，active default network 为 `none`。

`result.json` 为 1,132 字节，SHA-256 `097cd558327c1b6bac8a5bac1b097423f30b1f12d4ddbe8cbfe6a26389eac11e`。原始 stdout 为 2,870 字节、SHA-256 `179b862194cfe054ae4845496145207718f64d5e49d83408c3705ef81818c0e6`；stderr 为 76 字节、SHA-256 `f017de3c853e96b4903d2c64a4a9bd4fae3ab1b2bafbfa6c2214c1bee4d7e506`，保留 Unknown CPU vendor 警告。evidence artifact `14395707319` 的 ZIP 为 994,614 字节，SHA-256 `13c048ba2c6237abefe24662da992f634d60e70ab96e1b8de932787c196d2b98`。API、收集和上传步骤成功；最后工作卷 `umount` 报 `target is busy`、退出 32，整个 workflow 没有通过。

[第七次 run](https://github.com/ZPJJJ/LanType/actions/runs/44235315243) 在主机 ADB 登记时报错，未启动 guest、未加载新 ELF、未执行原生 probe，随后清理也失败。它没有新增运行通过结果，也不改变第六次 API 回执。主机诊断修复已提交为 [`b5c46a43eeb48b574e067ff8a12316baea0fc938`](https://github.com/ZPJJJ/LanType/commit/b5c46a43eeb48b574e067ff8a12316baea0fc938)，尚未取得新运行结果。第六、七次的完整范围、失败及回执身份见 [1.1.2 验证记录](../development/lantype-1.1.2-validation.md)。

cpuinfo 提案对两次读取之间的拓扑变化没有提供原子快照；现有 L3 行为和其他缓存几何问题也未在本补丁中重写。因此，本记录不以构建成功或静态通过替代设备上的正常初始化和使用验证。

## 6. 已公开的源码资产索引

三份基础包包含原有 70 份固定源档，均为独立 ZIP；Dawn 补充另含 7 份源档。此次组件复用其实际选用的来源，不重新复制整套大型归档。以下大小与摘要已和公开 GitHub release API 清单核对：[基础资产 API](https://api.github.com/repos/ZPJJJ/LanType/releases/tags/v1.1.0-rc1)、[Dawn 补充资产 API](https://api.github.com/repos/ZPJJJ/LanType/releases/tags/v1.1.1-rc1)。

| 已公开附件 | 字节数 | SHA-256 |
|---|---:|---|
| [基础源码 1 / 3](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-1-of-3.zip) | 339,827,618 | `00223f5255a7b6b1d9f32ea52402fd2693cc879c530e59a60d8e80fa11882b57` |
| [基础源码 2 / 3](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-2-of-3.zip) | 339,828,069 | `1ef3f166b8992957e5518b451de50def7db42d1443a1dc32811c3a7fc46c9eec` |
| [基础源码 3 / 3](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-3-of-3.zip) | 339,828,348 | `7f3b2a772532ba5ff65086efd289ac214577d498974d2253a6e4078547b8b4f7` |
| [Dawn / WebGPU 补充](https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/LanType-native-source-webgpu-supplement-v1.zip) | 105,554,498 | `6eabae67a60bdb0f3eaab9858f58b1f712edb9f85bb4c5cf75d800e7f530691d` |

解包方式与逐档恢复见[基础来源说明](../LANTYPE-BUILD-AND-SOURCES.md)；Dawn 的 7 份源档、13 份原始许可/通知副本及独立审阅见 [DAWN-SOURCE-SUPPLEMENT.md](DAWN-SOURCE-SUPPLEMENT.md) 和 [dawn-source-publication.json](dawn-source-publication.json)。这些来源附件与第 8 节的 ORT 运行组件是分别公开的发行物。

## 7. 许可证、通知与实际组件 ZIP 清单

ORT 本体适用 [MIT](https://github.com/microsoft/onnxruntime/blob/da9b5e364c465de65c49d91e696cd6485270757f/LICENSE)，cpuinfo 适用 [BSD-2-Clause](https://github.com/pytorch/cpuinfo/blob/4628dc060ce4e82345dc166bbac875609db4ff69/LICENSE)，Dawn 及其他第三方依赖保留各自条款和版权。组件包应携带原始许可及通知文本；不能因为 LanType 应用采用 GPL，就给整个 ORT 组件包统一改标 GPL。若随包携带项目构建工具，应同时保留这些工具适用的项目许可证，并明确其适用对象。

| 必须保留的已知文本 | 实际来源位置 | 字节数 / SHA-256 |
|---|---|---|
| ORT MIT 原文 | 固定 ORT 源树 `LICENSE`；原生候选 `licenses/onnxruntime-LICENSE.txt` | 1,073 / `2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c` |
| cpuinfo 原始许可 | 固定 cpuinfo 源树 `LICENSE`；候选 `licenses/cpuinfo-LICENSE.txt` | 1,424 / `8e7e60636c3aa0cb03571a1a841ce5697f9551ff92b3c426c2561613d15ade70` |
| ORT 第三方通知 | 固定 ORT 源树 [`ThirdPartyNotices.txt`](https://github.com/microsoft/onnxruntime/blob/da9b5e364c465de65c49d91e696cd6485270757f/ThirdPartyNotices.txt)；构建清单实际路径 `src/runtime-onnxruntime/ThirdPartyNotices.txt` | 325,054 / `0e07b95f3a8d6230037707c5c4a2b554d12c4cb67369669ac255635528ffcee2` |
| Dawn 补充许可/通知 | 已公开补充 ZIP 中的 13 份原始副本 | 各文件身份见补充来源锁及审阅回执 |
| NDK r29 原始通知 | 实际 NDK 根目录 `NOTICE`；证据 `ndk-source-inputs/NOTICE` | 516,438 / `faf0dc52cf6ce9ab09a04b0c074a378dd2565ee1ed9bc1179d83793bcdba012e` |
| NDK r29 工具链原始通知 | 实际 NDK 根目录 `NOTICE.toolchain`；证据 `ndk-source-inputs/NOTICE.toolchain` | 799,639 / `789714a9076571c580cf531bdcebec776a4d889c12c3c1108adafc6e4338710a` |
| NDK r29 LLVM 原始通知 | `toolchains/llvm/prebuilt/linux-x86_64/NOTICE`；证据保持相同相对路径 | 130,424 / `f96f763beb66a7ba7a667647fc64c0226ace875e590c831fdd9579ec1c1d91e1` |

`ThirdPartyNotices.txt` 的上述身份同时存在于此次 `prepared-sources.json` 中。通常恢复到仓库后的源路径为 `vendor/native-sources/runtime-onnxruntime/ThirdPartyNotices.txt`。应从此固定源码复制通知，不能从 AAR 文件名推测通知已随 AAR 自动包含。

NDK 的 LLVM 通知包含 Apache License 2.0 with LLVM Exceptions 及保留的其他声明；工具链总通知还汇集多种工具和依赖的条款。发行时保留完整原文及各自适用对象，不能据汇总文件中的某一段将整个 ORT 或全部运行时统一改标为该许可证。第 3 节记录的 NDK 原始来源与本次通知取证，独立于旧共享运行时的来源锁。

实际组件 ZIP 采用单一根目录 `LanType-ORT-1.28.0-r1/`，共有 **462 个普通文件，解压内容合计 272,281,795 字节**。下表为实际目录；逐文件大小和 SHA 由包内 `component-manifest.json` 记录。

| 包内内容 | 取自何处 / 作用 |
|---|---|
| 第 4 节三份输出，保持所列相对路径 | 给默认构建、CMake 源码构建和 ELF 输入提供同一实际版本 |
| `README.md` | 实际 API 通过范围、两个 workflow 失败事实、恢复与来源说明 |
| `native-candidate/include/` 的三个 C API 头 | 候选 `onnxruntime_c_api.h`、`onnxruntime_ep_c_api.h`、`onnxruntime_error_code.h`，按原 manifest 校验 |
| `native-candidate/cpuinfo-4628dc0-pr457-l2-backport.patch` | 固定生产补丁原文；作者归属另随通知保留 |
| `native-candidate/candidate-manifest.json`、原始候选 README、`ort-shipped-abi.json`、`ort-api-smoke.c` | 原生构建来源与验收入口快照；原 manifest 描述原始候选布局 |
| `native-candidate/receipts/` | 原始 `prepare`、`configure`、`build`、`verify`、`abi`、`state`、`prepared-sources`、`configured-sources`、`provider-compile-inputs` 九份 JSON |
| `evidence/native-build/`、`evidence/native-build-origin/` | 原生构建证据与来源元数据 |
| `evidence/package/`、`evidence/aar-preparation/` | 11 月 18 日 candidate 锁、准备与复验回执、下载身份及实际日志，保留原字节 |
| `evidence/android-api/run-44232550186/`、`run-44235315243/` 及对应 `-origin/` | 第六、七次完整原始 evidence、GitHub 状态、日志与恢复审阅回执；分别含 218、132 个原始 evidence 文件 |
| 各 Android evidence 内的 `ndk-source-inputs.json` 和 `ndk-source-inputs/` | 实际 NDK 身份、`source.properties` 及三份通知；静态 archive 只记录身份 |
| `source-index/` | 本文列出的四个公开来源附件索引，以及固定的基础锁、WebGPU 锁、Dawn 计划与发布回执等小文件 |
| `native-candidate/licenses/`、`licenses/onnxruntime/`、`licenses/ort-runtime-r1/` | ORT/cpuinfo 许可、ORT 第三方通知及 17 份新通知；按组件区分原条款 |
| `staging-source-map.json`、`component-manifest.json` | 原始整理记录与最终逐文件大小 / SHA，注明原候选路径与包内路径的对应关系 |

原候选中的 `lib/arm64-v8a/libonnxruntime.so` 与运行包 `arm64-v8a/libonnxruntime.so` 是同一内容，可只保存后者，在 component manifest 中记录对应关系。原候选 manifest 本身保持原字节；不能把迁移后的目录冒称为无需路径映射就符合原始 19 文件布局。

## 8. 公开发行身份与恢复

[组件 Release `ort-runtime-1.28.0-r1`](https://github.com/ZPJJJ/LanType/releases/tag/ort-runtime-1.28.0-r1) 已于 `2026-11-18T04:33:36Z` 公开，release ID `449527123`，`prerelease: true`、`draft: false`。标签对应提交 `b5c46a43eeb48b574e067ff8a12316baea0fc938`。五个实际附件的 URL、asset ID、大小和 SHA 见 [ort-runtime-r1-publication.json](ort-runtime-r1-publication.json)。

| 实际发行对象 | 字节数 | SHA-256 | 公开 asset ID |
|---|---:|---|---:|
| [运行组件 ZIP](https://github.com/ZPJJJ/LanType/releases/download/ort-runtime-1.28.0-r1/LanType-ORT-1.28.0-r1-runtime.zip) | 97,731,603 | `e03422b48b8a36f7a83cc8a458ec7c97c744d34139f219ee95cb28093e2d9d09` | `761904810` |
| [外部 accepted 锁](https://github.com/ZPJJJ/LanType/releases/download/ort-runtime-1.28.0-r1/ort-runtime-r1-accepted.lock.json) | 2,313 | `e751086cb82c90bb631bfdebf45f78e2f7462fcccf52373ca9141f45f0bf207b` | `761905088` |
| 包内 `component-manifest.json` | 174,810 | `3db53612cd63bdb905bfb77cf435e343b4fdb5cb35783fa771e01354be47f000` | 包内文件，无独立 asset |

外层 ZIP 采用固定排序、时间、普通文件权限及 DEFLATE level 6；包内两个 AAR 仍保持第 4 节的 ZIP_STORED 身份。component manifest 记录除自身外的 461 个文件；外层 ZIP 的摘要保存在独立锁和发行回执中，没有自引用锁。原始 candidate manifest、`staging-source-map.json`、component manifest 和外部锁中关于各自准备时状态的历史字段均未追改；实际公开状态由发行回执补充，没有在公开后重新封包。

仓库 [ort-runtime.lock.json](ort-runtime.lock.json) 与上述公开锁为同一份文件。它接受固定三输出作为应用集成输入，依据为 `d28c2890…` 静态 ABI 回执和 `097cd558…` 第六次 API 回执，并保留两个 workflow 的 failure、未测产品/推理/真机/16 KiB 范围。`accepted` 不表示这些未测项目已经通过。

正式 [restore-ort-runtime.py](../../scripts/restore-ort-runtime.py) 已从本地发布 ZIP 恢复三输出，随后 accepted `--verify-only` 成功；公开的 `restore-receipt.json` 为 1,082 字节、SHA-256 `bc4bd6856fa5653358fedbac1a503f853b6a6a7ee95bd1afce0ee02d2abe591c`，`accepted-verify-receipt.json` 为 822 字节、SHA-256 `f38dfb0c868c71dbb1a6544579e50bc2654713b7d76f840bbecdfad04a8421c5`。这次恢复按锁比较固定输出和 full/companion 成员，不重新执行第 4 节已完成的官方原始 AAR 比较，也不执行任何原生代码。无凭证访问已确认 ZIP 的 HTTP 200 和精确 Content-Length；公开锁的实际 GET 内容与仓库字节/SHA 相同。

恢复入口只按外部 accepted 锁恢复并验证三份运行输出；开发阶段的显式下载与输入法手机运行时联网需求无关。该组件 Release 是构建依赖预发布，不是 LanType 1.1.2 APK 的发行。

本组件说明只覆盖动态 ORT 修订及其运行包。LanType 应用的 GPL 组合发行、应用源码、其他原生库、模型和词库的对应来源仍应另列，参见[应用构建与来源说明](../LANTYPE-BUILD-AND-SOURCES.md)及[商用方案](../COMMERCIAL-PLAN.zh-CN.md)。本次 ORT 组件记录不自动改变 Sherpa 静态 ORT 等其他组件的版本或许可身份。
