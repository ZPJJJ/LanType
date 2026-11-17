# Dawn / WebGPU 原生源码补充说明

更新日期：2026-11-18（中国标准时间）。**本次已确认遗漏的 7 份源码归档已收集、独立核验并公开发布。** 本页更正早期原生来源清单的范围判断；原 APK、应用源码 ZIP、三份基础原生源码 ZIP 及发行标签保持原字节和标识。这是已知来源漏项的补正，不是全部原生库已重编或已达到稳定商用品质的声明。

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

补充包采用独立 ZIP、独立顶层目录、来源锁和逐档 SHA-256，保留固定 Dawn 与确认所需嵌套依赖的实际源档、原始许可及取证依据。它与旧三份基础源码包一起使用，不覆盖旧包根目录，不移动 tag，不重新签名或替换 APK。已有 ORT 与 Abseil 归档的复用身份、ORT 源码内已有 7 个 Dawn patch 的顺序及身份，都保存在计划和独立锁中；收集时未执行 patch。原 `restore-native-sources.py --all` 仅检查主锁里的 70 项，不自动验证补充包。

APK 随带的 `licenses/native/runtime-onnxruntime/ThirdPartyNotices.txt` 已包含 Dawn 的版权及 BSD 3-Clause 条款。此次明确发现的是源码归档和递归依赖覆盖遗漏，不能说 APK 完全没有 Dawn 许可。补充源码继续保留各组件原条款，不统一改标 GPL，也不据源码收集成功宣称全部原生库已经重编或逐字节复现。

## 已发布补充与验证

- [下载源码补充 ZIP](https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/LanType-native-source-webgpu-supplement-v1.zip)：105,554,498 字节；SHA-256 `6eabae67a60bdb0f3eaab9858f58b1f712edb9f85bb4c5cf75d800e7f530691d`。GitHub asset `759718489` 的大小和服务端 digest 已与本地比对。
- [收集任务 44120869197](https://github.com/ZPJJJ/LanType/actions/runs/44120869197) 成功，固定源码提交 `3bffe90fcb50ffd1a327d6d0603ad5be5c546b74`；未执行下载源码、生成器、native 构建或 APK 构建。
- 独立核验 **7/7** 原始归档、**13/13** 许可/通知副本和 **23 份、252,077 字节**来源原文；补充 ZIP 含 50 个文件。Dawn 原始 ZIP 同时匹配 ORT `deps.txt` 的既有 SHA-1 `d4d64d1729104b61e654073566f1a376e16cad92`。
- 固定计划：[dawn-source-plan.json](dawn-source-plan.json)；原始收集锁：[native-sources-webgpu.lock.json](native-sources-webgpu.lock.json)；逐字节独立验收：[dawn-source-collection-receipt.json](dawn-source-collection-receipt.json)；发行者后续审阅与公开资产身份：[dawn-source-publication.json](dawn-source-publication.json)。

| 归档 | 固定提交 | 归档字节 |
|---|---|---:|
| Dawn（含 Tint、代码生成器与原树） | `ec7b457e5bb1fcec6f59733c4f3dd84d2f885a38` | 94,578,448 |
| SPIRV-Headers | `f31ca173eff866369e54d35e53375fadbabd58f4` | 657,699 |
| SPIRV-Tools | `cb38b2342beedde25bcff582dc3528a135cf6e67` | 5,014,046 |
| Vulkan-Headers | `49f1a381e2aec33ef32adf4a377b5a39ec016ec4` | 3,104,128 |
| Vulkan-Utility-Libraries | `50af38b6cd43afb1462f9ad26b8d015382d11a3d` | 1,556,866 |
| Jinja2 | `c3027d884967773057bf74b957e3fea87e5df4d7` | 124,232 |
| MarkupSafe | `4256084ae14175d38a3ff7d739dca83ae49ccec6` | 10,302 |

在当前仓库中执行独立校验：

```bash
python3 scripts/collect-dawn-source-supplement.py \
  --verify /path/to/LanType-native-source-webgpu-supplement-v1.zip \
  --expected-zip-sha256 6eabae67a60bdb0f3eaab9858f58b1f712edb9f85bb4c5cf75d800e7f530691d
```

包内 README 和锁保留采集当时的 `collected-awaiting-review` 状态，便于区分“首次测得摘要”与“后来审阅并发布的身份”。不要因此改写或重新打包原 ZIP；以本页及独立发布回执中的后续审阅结果为准。Gitiles 的两份 tar.gz 也保留实际采集原字节，没有替换时间戳或接受另一份摘要。

## 仍然存在的边界

原供应商的完整 CMakeCache 和未修改的原始构建命令尚不可得；所需来源范围依据固定 ORT Android 配置与实际 provider ELF 证据推定，15 项可选来源的排除条件保存在计划中。当前资料不证明逐字节重建，也不自动证明其他未知配置不存在额外来源需求。

已观察的设备首启故障和 cpuinfo 候选修复是另一个问题。补齐源码附件本身不会修复已经签名的 APK；本版仍不具备稳定收费发行条件。
