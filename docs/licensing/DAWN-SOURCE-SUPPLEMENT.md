# Dawn / WebGPU 原生源码补充说明

记录日期：2026-11-17（中国标准时间）。**补充源码正在收集和核验，尚未宣称此项已完成。** 本页更正早期原生来源清单的范围判断；原 APK、应用源码 ZIP、三份基础原生源码 ZIP 及发行标签保持原字节和标识。

## 已发现的遗漏

原 `native-sources.lock.json` 把 WebGPU 列为不在 Android 构建范围内的组件。对实际交付 ELF 的补充核查发现，库内存在 `WebGpuExecutionProvider::OnRunStart`、`ComputeContext::CreateGPUTensor`、Dawn 实现及 XNNPACK 的实际 RTTI/实现符号。应用当前选择 CPU/NNAPI 路径，不能据此推导整个共享库没有编入其他 provider。

因此，原有 **70 份实际源码归档**的数量、内容和哈希仍成立，但它们遗漏了 Dawn 及相应嵌套构建源码，不能单独描述为已经完整覆盖实际原生依赖。当前主分支已更正这一说明；冻结在旧发行中的锁和 README 作为历史原件保留，阅读时必须结合本补充。

## 适用二进制

| 项目 | 固定身份 |
|---|---|
| APK 内路径 | `lib/arm64-v8a/libonnxruntime.so` |
| 两版库大小 | 28,637,280 字节 |
| 两版库 SHA-256 | `f826d8efb03adf0a84f10e7ba408f9d4cd11b0a2ccd8d08aeb0f7451fb50cacc` |
| ELF BuildId | `b178f5c22304a25ff481e608260312842627e868` |
| 对应 ORT 源码 | 1.28.0，`da9b5e364c465de65c49d91e696cd6485270757f` |
| 官方 Android AAR SHA-256 | `f351a0638696f54b35184290dbc001d66daae17281ad0b548d2c70347d53b8a9` |
| 固定 Dawn 源码提交 | `ec7b457e5bb1fcec6f59733c4f3dd84d2f885a38` |

以上同一 ELF 同时用于 1.1.0 与 1.1.1，依据分别为 [1.1.0 逐库回执](../validation-1.1.0/apk-native-libraries.json) 和 [1.1.1 逐库回执](../validation-1.1.1/apk-native-libraries.json)。这次补充针对该动态 ORT，不自动推断 Sherpa 静态 ORT 采用了全部相同 provider。

## 补充方式与许可

补充包将采用独立 ZIP、独立顶层目录、来源锁和逐档 SHA-256，保留固定 Dawn 与确认所需嵌套依赖的实际源档、原始许可及取证依据。它与旧三份基础源码包一起使用，不覆盖旧包根目录，不移动 tag，不重新签名或替换 APK。已有源码归档与补充依赖的复用关系需要逐项明确；原 `restore-native-sources.py --all` 仅检查主锁里的 70 项，不自动验证补充包。

APK 随带的 `licenses/native/runtime-onnxruntime/ThirdPartyNotices.txt` 已包含 Dawn 的版权及 BSD 3-Clause 条款。此次明确发现的是源码归档和递归依赖覆盖遗漏，不能说 APK 完全没有 Dawn 许可。补充源码继续保留各组件原条款，不统一改标 GPL，也不据源码收集成功宣称全部原生库已经重编或逐字节复现。

## 当前状态

固定依赖清单、源码归档、许可证副本、发布链接与校验回执待本次收集任务完成后填入。该项仍是正式收费发行前的未完成事项。现有设备首启故障和 cpuinfo 候选修复是另一个问题，补齐源码附件本身不会修复已经签名的 APK。
