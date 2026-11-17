# LanType 1.1.1 验证记录

记录日期：2026-11-17。本文根据本目录的构建、签名、APK 检查与 JUnit 原始回执整理。

**发布后的结果已另行补充：** [最新验证记录](POST-RELEASE.md) 包含已通过的 GitHub 源码 CI
（27 类、187 个唯一 JUnit 用例；另有 12 项 Python 源码检查）和两次 KVM 原生崩溃记录。
本页以下主体保留首次公开时的验证范围，不将后续结果倒填进原始发行附件。

本轮已有结果为：**10 个定向测试类、96 个不同用例最终全部通过；正式离线变体构建成功，
最终签名 APK 的资源与原生库静态检查通过。本地软件模拟器仅完成旧签名 1.1.0 安装，
系统 ANR 阻碍了可靠功能验收；1.1.1 安装、实际输入与覆盖升级尚未通过设备验证。**
单元测试和静态检查不作为安装、首次部署、实际输入体验或 16 KiB 页设备运行通过的证明。

## 1. 被验证的 APK 与对应源码

以下身份信息来自 [apk-receipt.json](apk-receipt.json)，包信息另见
[apk-badging.txt](apk-badging.txt)。本地产品提交的 Git tree 已与回执核对。

| 项目 | 值 |
| --- | --- |
| 最终文件 | `LanType-1.1.1-offline-arm64-v8a.apk` |
| 大小 | 179,987,242 字节 |
| 版本 | `versionName=1.1.1`，`versionCode=3` |
| 应用 ID | `app.lantype.keyboard` |
| SDK | `minSdk=28`，`targetSdk=36` |
| APK 中的 ABI | `arm64-v8a` |
| APK SHA-256 | `b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497` |
| 签名证书 SHA-256 | `c03b15a19d2ed8899fee6b71f7be09ea5b54c7db9895d7d87b20a9759d8e090b` |
| 本地产品源码 Git commit | `a83eadd5c0b5d22ffbff248e99b4d9db137b02a6` |
| 对应公开产品源码 Git commit | `abb0b9369424029f1d7418ca56fc6d38f2872f96` |
| 产品源码 Git tree | `eaf49f2c975a33bda75c2d4dfdb9e1cc9cf0c481` |
| DEX 中找到的构建源码标记 | `a83eadd` |

表中的 Git commit/tree 是源码 Git 对象标识，不能当作源码 ZIP 的 SHA-256。
本地和公开提交标识不同；本报告保留回执里的对应关系，不声称两个 commit SHA 相同。
后续加入本验证报告的文档提交也不改变该 APK 已有的产品源码标记。

## 2. 最终定向测试结果

[targeted-tests-summary.json](targeted-tests-summary.json) 汇总为 96 个不同用例、10 个类，
最终失败、错误、跳过均为 0。逐类最终 XML 放在 [junit/final](junit/final/)；
该目录是各类最新有效回执的汇集，没有另外执行一批测试。

| 测试类 | 用例数 | 本轮覆盖重点 | 最终结果 |
| --- | ---: | --- | --- |
| `OfflineWhisperLanguageSwitchTest` | 5 | 离线 Whisper 语言切换及识别器更新边界 | 通过 |
| `SpeechRecognitionLanguageSessionTest` | 22 | 语音识别会话中的语言更新、取消及旧结果隔离 | 通过 |
| `LegacyRimeDirectoryMigrationTest` | 7 | 旧 Rime 目录迁移与已有数据保护 | 通过 |
| `InputPrivacyTest` | 9 | 手动、编辑器、搜索、工具舱隐私来源及关闭顺序 | 通过 |
| `ToolCabinClipPrivacyTest` | 11 | 延迟回调、补读、重复开闭及当前复制身份保留 | 通过 |
| `ClipboardSensitiveTest` | 8 | 敏感历史开关、隐藏及过期行为 | 通过 |
| `PrivateClipMemoryTest` | 2 | 已识别私密复制的进程内记忆 | 通过 |
| `ToolCabinEditorTest` | 24 | 预览、选区、宿主输入连接和确认写入边界 | 通过 |
| `ToolCabinQueueBoundaryTest` | 1 | 工具舱退出时旧队列与输入目标隔离 | 通过 |
| `ToolPanelPrivateClipboardTest` | 7 | 原生复制/剪切、元数据传输、新历史管理器补读及 Room 正反例 | 通过 |
| **合计** | **96** | **10 类，0 失败、0 错误、0 跳过** | **通过** |

### 执行次数与失败记录

| 批次 | 有 JUnit 回执的执行数 | 当次结果 | 计数方式 |
| --- | ---: | --- | --- |
| 最初与虚拟机并行的尝试 | 0 | 内存压力期间 Gradle daemon 异常消失，未形成 JUnit 结果 | 不计为通过，也不计入 103 次执行 |
| [首次正式串行批次](junit/first-serial/) | 96 | 94 通过、2 个夹具先决条件失败；0 错误、0 跳过 | 保留当次原始回执 |
| [修正后的剪贴板单类批次](junit/clipboard-walltime-final/) | 7 | 7 通过、0 失败、0 跳过 | 以该类最新结果替换首轮同类结果 |
| **实际产生 JUnit 结果的执行总数** | **103** | 包含修正前的两次失败执行 | 最终按“类名 + 用例名”去重为 96 个通过用例 |

首次 daemon 退出的日志只说明进程意外消失；当时存在并行虚拟机的内存压力。
该尝试没有成功完成测试，不能因 Kotlin 编译阶段已经结束而计为测试通过。
随后停止虚拟机，重任务串行执行。原始工作区日志分别为
`work/build-logs/tests-1.1.1-runtime.log`、`tests-1.1.1-runtime-serial.log` 和
`tests-1.1.1-clipboard-walltime.log`。

### 两项夹具失败及其修复

首轮失败均位于 `ToolPanelPrivateClipboardTest` 的“当前复制仍在 30 秒内”先决条件，
尚未进入历史读取断言。本地 `shadows-framework-4.14.1.jar` 的字节码显示，
`ShadowClipboardManager.setPrimaryClip` 使用 `SystemClock.uptimeMillis()` 设置复制时间；
[Android `ClipDescription.getTimestamp()` API 契约](https://developer.android.com/reference/android/content/ClipDescription#getTimestamp())
要求该时间采用 `System.currentTimeMillis()` 基准。

修复仅在测试中通过 `ClipDescription.setTimestamp` 补齐系统服务赋墙上时间的行为，并验证
Parcel 往返保留时间戳。产品 30 秒门槛和全部隐私断言保留，没有通过跳过读取、删除断言或放宽产品条件消除失败。
单类重跑耗时 1 分 26 秒，7 项全部通过。

其中复制和剪切分别经过真实 Android `EditText`、系统 `ClipData`、Parcel、两次新建的历史管理器、
实际 `readMissedCopy` 和 Room 查询。用例验证：工具舱元数据在无旧进程内记忆时仍禁止收录，
开启敏感历史开关也不会绕过；后续普通复制能够正常入库。
这是 Robolectric 的 Android 路径回归，不能替代设备上的进程退出/重启操作。
完整缺陷边界见 [CLIPBOARD-TOOL-CABIN-PRIVACY.md](CLIPBOARD-TOOL-CABIN-PRIVACY.md)。

## 3. 正式构建与签名

[build-summary.json](build-summary.json) 记录产品提交 `a83eadd5c0b5d22ffbff248e99b4d9db137b02a6`
的 `:app:assembleOffline` 正式构建成功：**4 分 8 秒**，80 个任务中 24 个执行、56 个复用结果，
启用 R8，编译依赖按离线缓存解析。构建日志为工作区
`work/build-logs/assemble-offline-1.1.1-a83eadd.log`。

编译时的离线依赖解析和应用运行时网络权限是两个检查项。最终清单未声明 `INTERNET`，
`debuggable=false`、`allowBackup=false`、`extractNativeLibs=true`；详见
[apk-permissions.txt](apk-permissions.txt)、[apk-manifest-tree.txt](apk-manifest-tree.txt) 和 APK 回执。

[apk-signature-verification.txt](apk-signature-verification.txt) 记录最终 APK 验证成功，
对本应用支持的 API 范围使用 v3 签名，1 个签名者，证书摘要与上表一致。
另保留 [v1 校验回执](apk-v1-signature-verification.txt) 和
[v2 校验回执](apk-v2-signature-verification.txt)，分别验证 API 23 与 API 24–27 的签名格式路径。
这些额外签名检查不改变应用最低支持 API 28 的声明，也不代表在那些旧系统上安装运行通过。

签名前文件的 SHA-256 为
`58f582cd59e606fc4e80781b8a21fb353a6598195a0a8705a5d4090035333d67`。
APK 回执确认签名后原有 2,161 个 ZIP 条目内容未变；最终签名文件共有 2,164 个条目，
全包资源扫描针对的是上表最终 APK。此前未成功的签名尝试保留为过程证据，
不替代最终签名验证结果。

## 4. 最终 APK 的资源与原生库静态检查

| 检查 | 现有回执中的结果 | 证据 |
| --- | --- | --- |
| 获准分发资产 | 379 项批准资产，实际检查 379 项 | [final-apk-resources.json](final-apk-resources.json) |
| 原始资源 | 11 项 `raw` 资源 | [final-apk-resources.json](final-apk-resources.json) |
| 全包扫描 | 扫描 2,164 个 ZIP 条目，`pass=true`，失败列表为空 | [final-apk-resources.json](final-apk-resources.json) |
| CameraX 来源替换 | 两个 JNI 库均匹配从源码构建的锁定内容，未重复打入其他 ABI 路径 | [camerax-apk-verification.json](camerax-apk-verification.json) |
| 原生库 | 12 个 ARM64 ELF；各库字节与前一签名发布版一致 | [apk-native-libraries.json](apk-native-libraries.json) |
| ELF 页对齐静态条件 | 所有 `PT_LOAD` 段对齐不小于 16,384 字节，且文件偏移与虚拟地址对 16,384 同余 | [apk-native-libraries.json](apk-native-libraries.json) |

资源检查使用的锁文件 SHA-256 为
`db6c94c9cb44de3b883ba237fc04de3d3e7d61d3ed5ab9f383508f5bc18a6381`。
检查回执单列了 AGP 生成的 ART profile 和由已公开源码生成的插件包等允许项，
不是仅按文件名统计数量。

12 个原生库均采用 ZIP Deflate 压缩，清单要求安装时提取原生库。
因此不能把 ELF 的段对齐或 `zipalign` 打包检查描述成“压缩数据在 APK 内按 16 KiB 页对齐”。
本轮保留 [签名前 zipalign 输出](apk-zipalign-before-signing.txt) 与
[最终 zipalign 输出](apk-zipalign.txt)；原生库回执明确写有 `devicePageSizeTested=false`。
**本报告不宣称已在 16 KiB 页设备上执行验证。**

## 5. Android 运行时验证：本地安装部分完成，功能验收未完成

本地尝试见 [精简报告](local-tcg/README.md) 和 [机器回执](local-tcg/receipt.json)。
使用官方 API 30 Google APIs x86_64 镜像，guest 实读到 ARM64 native bridge；宿主没有 KVM，
最终有界尝试使用 4 vCPU、3 GiB RAM。它不是物理 ARM64 手机或平板。

| 验证项 | 实际结果 |
| --- | --- |
| 本地模拟器用户解锁 | 最终尝试确认用户 0 为 `RUNNING_UNLOCKED` |
| 离线首启前置条件 | 启动产品意图之前读回飞行模式 1、Wi-Fi 0、移动数据 0；APK 无 INTERNET |
| 旧签名 1.1.0 与独立编辑器宿主安装 | 均返回 `Success` / exit 0；旧包为 code 2、ARM64、非 debuggable |
| 旧版可交互首启、Rime 部署、中文/美国英文输入 | 未证明；不能从安装成功或 ABI 属性推导通过 |
| 最终 1.1.1 APK 的本机安装与同签名覆盖升级 | 未执行；没有卸载或清除旧应用数据 |
| 工具舱预览/写入、密码及编辑器边界、实际进程重启后的剪贴板隐私 | 设备流程未执行；第 2 节为独立的 Robolectric 回归结果 |
| 物理 ARM64 设备和 16 KiB 页 Android 设备运行 | 未实测 |

早先 2 vCPU / 2 GiB 环境发生 Android framework watchdog：用户数据解锁路径等待锁，
`android.fg` 超时导致 SystemServer 被终止；没有据此认定 guest OOM。
唯一一次参数调整后用户解锁完成、旧包安装成功，但实际截图/XML 随后显示
**Pixel Launcher** 与 **System UI** 的 ANR，系统日志还记录 Google Play services ANR。
这些名称来自实际节点和日志，不作为 LanType 缺陷的证据。

首次产品 `am start -W` 在 180 秒后超时。最后一次约 69 秒的有界探测按 XML bounds
点击系统对话框的 Wait；最后截图为白色内容窗口与系统栏，UIAutomator 返回 null root。
虽有产品进程启动事件，但没有可靠的产品页面、候选或宿主文本上屏证据。
本轮结果不能写成“中文输入通过”或“新版本设备验收完成”。

本机 VM 已于 2026-11-17 14:30:26 UTC 停止，锁释放，AVD 与旧版数据保留。
`adb emu kill` 返回 0，宿主 emulator 在退出清理阶段返回 -11；该退出码单独记录，
不归类为产品崩溃。精选证据包的文件名、大小和 SHA-256 见本节链接的精简报告；
它将作为独立发行附件，源码中只保留小型文本回执。

## 6. 预发布与后续 CI/设备验收边界

**1.1.1 当前定位为待完成设备 QA 的预发布候选版，不是正式商用质量验收结论。**
先公开同一签名 APK 可供只读 KVM 验收任务下载；公开或上传成功本身不增加任何测试通过项。
后续任务必须记录实际下载 APK 的 SHA-256，并与本报告第 1 节的最终文件一致。

新版 CI 与 KVM 结果在本次文档冻结时尚未验收；
[构建任务 44103398875](https://github.com/ZPJJJ/LanType/actions/runs/44103398875)
是后续查看入口，本文不预先把它记为通过，也不把旧版 1.1.0 的 CI 成功沿用为本版结果。
实际 KVM 安装、首次部署、中文/English US、覆盖升级和工具舱跨进程流程应另加完整回执，
与本地 TCG 失败尝试分开记录。KVM 模拟器结果仍不得写成物理真机验收。

正式收费渠道、商店审核及持续使用验收的未完成项见
[发行检查表](../RELEASE-CHECKLIST.zh-CN.md)。
