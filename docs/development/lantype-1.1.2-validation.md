# LanType 1.1.2 验证与发行准备（工作稿）

## 结论和使用范围

本页记录 `1.1.2 / versionCode 4` 的证据与未完成项。**独立 ORT 原生构建、静态检查及第六次普通 Android API 正向检查已通过，组件和 accepted 锁已作为构建输入公开；第六次 workflow 因清理失败而整体失败，第七次在主机 ADB 登记阶段失败。应用整包和真实设备验收仍待完成。** 本页不是应用发布批准单，也不是“输入法首启故障已修好”的声明。

本批材料随 `development/1.1.2-runtime` 开发分支保存，主分支保留既有发行状态；开发分支同步不构成稳定版发布或收费发行验收。

旧 1.1.1 在 ARM64 bridge 环境的首次启动失败和旧测试报告保留原义，见 [1.1.1 验证记录](../validation-1.1.1/VALIDATION.md)。不改写旧附件或标签，也不把旧版的 187 项 JUnit 通过转成新版本成绩。

## 已有证据

| 项目 | 实际身份与结果 | 可支持的结论 |
|---|---|---|
| 独立原生构建 | [run 44164186969](https://github.com/ZPJJJ/LanType/actions/runs/44164186969)，`completed / success` | 本次固定源码和工具链生成了 ARM64 ORT 候选 |
| 原生构建源码提交 | `6d80145d1c15e646fae1404ec93c0c9520033e10` | 固定此次构建入口、补丁和检查器 |
| 新主 ORT | 29,568,744 字节；SHA-256 `ae250081faa6cd742f6edade2a23bf29a96ba690fa19a01e3bd192548cf89f1e` | 精确候选 ELF 身份；不是待发布外层 ZIP 的摘要 |
| 原生候选 manifest | SHA-256 `eb7adfcd1fe2c7c000ad29e99649035bea6c59f14aef1803fdf6f9649e2d1a07`，记录 19 个候选文件 | 候选原始目录和文件身份；保留未应用集成、未 Android 接受的标记 |
| 静态 ABI | 组件记录中的 10 项通过；ABI 回执 SHA-256 `d28c2890dbed469701f916c297c681e6bb3f5dec128a9986bb7cc85bdc555e7f` | ELF/ABI、导出、依赖和静态 LOAD 等合同符合；不执行候选 |
| AAR 处理 | 2026-11-18 从固定原始 AAR 重新生成并复验 full/companion/ELF；三输出 SHA 与历史记录完全一致 | ARM64 主库之外的官方 Java/JNI 内容保持身份；此次纯文件准备本身不执行接受动作 |
| ORT 组件公开发行 | [ort-runtime-1.28.0-r1](https://github.com/ZPJJJ/LanType/releases/tag/ort-runtime-1.28.0-r1)，release `449527123`，预发布；ZIP 与外部 accepted 锁均已公开 | 可恢复的固定构建依赖；接受范围为静态 ABI 和第六次 API 加载/环境检查，不代表产品验收 |
| SDK/NDK 来源取证 | [run 44173535722](https://github.com/ZPJJJ/LanType/actions/runs/44173535722) 的 tools 阶段保存 NDK 29 输入身份与通知 | 安装工具链来源证据；不是 Android API 运行通过 |
| 普通 API QA 第四次运行 | [run 44175344640](https://github.com/ZPJJJ/LanType/actions/runs/44175344640) 因宿主 emulator loader 的 `libsndfile` 依赖受阻 | 未进入候选原生 API 正向检查，不能判为候选 API 通过或候选原生运行失败 |
| 普通 API QA 第五次运行 | [run 44177101937](https://github.com/ZPJJJ/LanType/actions/runs/44177101937) 的 tools、probe APK 构建、宿主 emulator 版本和 KVM 检查完成；在系统镜像安装阶段因存储保留量门禁停止 | loader 前置问题已有实际进展；没有启动 guest 或执行候选 API probe |
| 普通 API QA 第六次运行 | [run 44232550186](https://github.com/ZPJJJ/LanType/actions/runs/44232550186)，API `passed`；仅最后工作卷卸载失败，workflow `failure` | 固定新 ELF 在 API 35 ARM64 bridge 中正常加载、取得 API 表、枚举 provider 并创建/释放环境；不覆盖模型或产品功能 |
| 普通 API QA 第七次运行 | [run 44235315243](https://github.com/ZPJJJ/LanType/actions/runs/44235315243)，主机 ADB 登记失败，后续清理也失败 | guest 与 probe 均未运行；既不新增原生通过结果，也不推翻第六次实际 API 结果 |
| 17 份离线许可通知 | [提交 1e7daacdaeac91983a436e1a2614ede02f725125](https://github.com/ZPJJJ/LanType/commit/1e7daacdaeac91983a436e1a2614ede02f725125)；396 个 assets、11 个 raw 的源码资源校验通过 | 新通知已按原始证据字节加入受锁资源；最终 APK 随包核验仍待完成 |

上述候选及回执的详细大小、摘要、配置和来源来自 [ORT 1.28.0-r1 组件说明](../licensing/ORT-RUNTIME-1.28.0-r1.md)。本页没有新增运行、生成假回执或将环境准备成功当作组件运行成功。

第五次运行的 workflow head 为 `9df415c407d8b4759de7e5da2099b4ceb9cdd01d`，job 为 `134371272874`。实际 evidence artifact `14369573492` 为 207,832 字节，SHA-256 `b9fe53f35c323beb0d313d0d609300435eaac651421c740e9e542be7aeb79549`。其中 `host-loader-dependencies.json` 的 `unresolved` 为 `[]`，emulator 版本命令与 KVM 检查通过；`image-026-sdk-image-install` 在解包 `x86_64/system.img`、进度 43% 时触及 256 MiB 工作卷保留量门禁，退出码为 143，`timedOut=false`、`storageReserveStop=true`。0.25 秒采样观察到的工作卷已用量峰值为 4,426,526,720 字节，不是连续测得的整个任务峰值。

第五次的 `result.json` 实际记录为 `status=failed / stage=image`，错误为 `Command stopped with less than 256 MiB work-volume reserve; see image-026-sdk-image-install`。当次没有 guest 身份、app-runner 输出或 probe JSON，属于环境准备失败；后续实际结果分别记录如下，原失败回执保留原义。

## 普通 Android API：已取得的结果与边界

本次普通路径由 [ort-api-qa.yml](../../.github/workflows/ort-api-qa.yml) 与 [run-ort-api-qa.py](../../scripts/run-ort-api-qa.py) 管理：固定候选 run、head、artifact 和 manifest SHA；核对 GitHub 来源与文件身份；将正常 C API probe 放入临时 Android instrumentation APK，在专用 worker 调用，保存原始 JSON 输出、日志和 guest 身份。

实际运行环境为 API 35 x86_64、KVM 与 ARM64 bridge。检查范围为候选 `dlopen`、C API 28 表、provider 枚举和 `CreateEnv` / 释放；APK 使用临时调试证书，没有产品签名或 INTERNET 权限。此项不覆盖模型推理质量、各 provider 的实际推理、输入法功能、实体 ARM64 或 16 KiB 系统行为。

### 第六次：API 通过，workflow 最后清理失败

| 结果字段 | 实际值 |
|---|---|
| run / job | `44232550186` / `134560859337` |
| workflow commit | `e909dd8e5050cb80537761ff6fe5acb34b96be1a` |
| guest | API `35`；ABI `x86_64,arm64-v8a`；bridge `libndk_translation.so`；页大小 `4096` 字节 |
| 执行路径 | ARM64 APK instrumentation JNI，64 位 worker；原 C probe SHA-256 `3dd1152dd8298d4f6475ff529bdde207a060440a49cb3465e792985f4d4f5bec` |
| probe 结果 | `mainReturnedNormally: true`、退出码 `0`；13 个阶段通过，原始 stdout 共 19 条 JSON |
| runtime / API | `1.28.0` / `28` |
| 枚举所得 provider | `CPUExecutionProvider`、`NnapiExecutionProvider`、`XnnpackExecutionProvider`、`WebGpuExecutionProvider`；仅枚举，没有执行模型推理 |
| 运行前断网记录 | 飞行模式 `1`、Wi-Fi `0`、移动数据 `0`；active default network 为 `none` |
| API `result.json` | 1,132 字节；SHA-256 `097cd558327c1b6bac8a5bac1b097423f30b1f12d4ddbe8cbfe6a26389eac11e`；`status: passed` |
| `app-probe-stdout.jsonl` | 2,870 字节；SHA-256 `179b862194cfe054ae4845496145207718f64d5e49d83408c3705ef81818c0e6` |
| `app-probe-stderr.txt` | 76 字节；SHA-256 `f017de3c853e96b4903d2c64a4a9bd4fae3ab1b2bafbfa6c2214c1bee4d7e506` |
| evidence artifact | `14395707319`；ZIP 994,614 字节；SHA-256 `13c048ba2c6237abefe24662da992f634d60e70ab96e1b8de932787c196d2b98` |

该次身份回执再次核对原生构建的 19 项 manifest 及上述 `ae250081…` ELF，运行时加载的正是固定候选。stderr 保留 `Unknown CPU vendor. cpuinfo_vendor value: 0` 警告，不能写成“无警告”。API、日志收集和 evidence 上传步骤均成功；最后 `umount` 报 `target is busy`，退出码 32，runner 随后清理残留的 adb/netsimd。因此 **整个 job/workflow 仍为 failure，普通 API 结果为 passed**。

该次 `ndk-source-inputs.json` 仍为 2,449 字节、SHA-256 `2bd815d11926c30be0091cabc82ddf92c7665c21f3401665e5990238e2f20b66`；NDK 29 元数据、三份通知和静态输入摘要与已记录来源一致。通知原文实际保留，静态 archive 只记录身份。

### 第七次：主机登记失败，未运行 guest 或原生 probe

第七次 run 的 job 为 `134569926936`，head 为 `f380826b1ea0076cfc20ea4fd278b07c2fc9bb2c`。工具、候选身份、测试 APK、镜像与 AVD 准备通过，随后在主机 `start_adb_server` 的登记检查报 `Cannot record the newly started adb-server process`。没有 guest 身份、emulator 启动日志或 probe 输出；`result.json` 为 `failed / stage=run`，703 字节，SHA-256 `1fe0a118cdd43dcbca53b292d29ef9d3e062da6d3f835d5ffc4177687e4b0dff`。当时工作卷空闲 11,711,422,464 字节，不是空间耗尽。

后续清理在读取尚未确认归属的 `/proc/1117/exe` 时遇到 `Permission denied`；`guest-process-cleanup.json` 为 `passed: false`，534 字节，SHA-256 `77f9dee3d8c7ed4098bcfb0e7ac13ed61034a40977e655879f7ed80ef4e536ee`。evidence 上传成功，正常卸载步骤被跳过。artifact `14397237194` 的 ZIP 为 227,415 字节，SHA-256 `769b37e7238a508b11696834fca56d24840710d32d24086e08a04d4952dc2618`。

该次未保存 ADB 登记失败时的 PID、退出状态和身份观察值，因此目前不能把首个错误确定为 exec 竞态、进程早退或环境标记变化。固定候选 ELF、原始 manifest 及编译后的 probe 身份均与第六次一致；本次没有加载该 ELF，不构成新 ORT 运行失败的证据。

[修复提交 b5c46a43eeb48b574e067ff8a12316baea0fc938](https://github.com/ZPJJJ/LanType/commit/b5c46a43eeb48b574e067ff8a12316baea0fc938) 为新建 ADB 进程增加最多 2 秒的身份登记等待及非敏感诊断；已登记或已确认归属的进程仍严格检查，未登记且无权读取的其他进程只记录并跳过。该修改已经过静态和纯文件检查，**尚未取得实际 SDK/guest 运行回执，不能写为第七次问题已运行修复**。

[API 35 镜像准备脚本](../../scripts/prepare-api35-system-image.py) 与[固定镜像锁](../qa/android-api35-image.lock.json) 已在第六次实际完成官方镜像校验、稀疏解包和 SDK 本地包登记，随后启动 guest。`system-image-registration.json` 记录 revision `9.0.0`、`sdkmanagerListedInstalled: true`、原有许可文件未变，并未接受新许可。上述实际进展不改写第四、第五次失败，也不代替清理和产品验收。

### 云端 QA 存储预算：已批准并应用

第五次运行暴露的是镜像解包期间的实际空间停止。后续独立评估还发现：现有 5 GiB 总预算方案中的工作卷，在容纳镜像和工具后，无法同时满足官方模拟器 fresh-AVD 启动至少 5 GB 空闲空间的检查。优化镜像准备过程本身不能证明启动阶段可在原预算内完成。

用户已于 2026-11-18 在本会话明确回复“允许”，批准[Android QA 专用 16 GiB 预算](../qa/ANDROID-QA-STORAGE-PROPOSAL.md)，并用于第六、七次运行。固定补丁在核对原始 SHA 和四份文件基线后原样应用；分配前仍需 host 空闲至少 36 GiB，guest 启动前工作卷实际空闲至少 7.5 GiB。预算批准本身不代表验收通过，第六次 API 结论来自上述实际结果。本地、独立原生构建与既有 offline 整包构建预算保持原约束，API、原生及产品验收通过条件不因预算变更而改变。

## 本批集成合同

### 原生与工具链

默认预编译和可选 Rime/JNI 源码模式均固定 NDK `29.0.14206865`。默认 APK 的 [最终检查器](../../scripts/prepare-ort-runtime.py) 要求恰好 12 个 ELF：`lib/arm64-v8a/libonnxruntime.so` 匹配新的 accepted 锁，另外 11 个逐文件匹配既有 APK 合同。官方 Java classes 和 `libonnxruntime4j_jni.so` 保留身份。

Sherpa JNI 内静态链接的另一份 ORT 未替换；本批不以动态 ORT 的检查替代 Sherpa 自身验证。可选 Rime 源码重编会形成开发者自己的原生输出，须另行记录，不能套用默认包“其余 11 库保持原字节”的结果。

### 运行资源和通知

默认恢复入口使用已公开旧 ZIP：

- 文件：`LanType-1.1.0-runtime-dependencies.zip`。
- 字节数：139,297,354。
- SHA-256：`42a0e57c002662e2a502719a7f002b061fd49605d92a87cab221bf6d9aa922bc`。
- 原有输入：379 个 assets、11 个 raw、7 个旧 vendor 输入、2 个 CameraX 库，合计 **399**。
- 新增通知：Git 内 `app/src/main/assets/licenses/ort-runtime-r1/` 的 17 份文件，构成为 NDK 29 三份、Dawn 13 份、补丁归属一份；最终资源锁计 396 assets 与 11 raw。

旧 379 项内容、完整锁记录及原顺序保持，新 17 项由当前 Git 和锁提供；基础恢复入口分别识别两者，不能期待旧 ZIP 含有新文件。17 份文件共 1,516,450 字节：NDK 三份逐字节匹配已记录的 NDK 29 证据，Dawn 13 份逐字节匹配已公开补充 ZIP 的已锁成员，补丁说明记录实际来源。上述许可功能已提交为 `1e7daacdaeac91983a436e1a2614ede02f725125`。

实际源码资源检查通过 396 个 assets 与 11 个 raw；基础恢复检查核对了旧 ZIP 的全部 404 个成员和 399 个基础输入，并独立校验 17 个 Git 通知，未从旧 ZIP 恢复或覆盖新通知。资源锁 SHA-256 为 `72b6be5556bb5be6314de209c3caf020ec782874ba3608a28c9443961ab69e97`。实际本地回执身份如下；最后仅将资源数组恢复为旧 379 条原序列后追加 17 条，并同步更新回执摘要，没有重跑或虚构新检查：

| 回执 | SHA-256 | 范围 |
|---|---|---|
| `ort-runtime-r1-notices-resources.json` | `5d820c55dc79f4ce9eb9634135fe6d97b08aea5307be4a5675fb8931d91bcd98` | 源码目录的 396 assets / 11 raw |
| `ort-runtime-r1-notices-base.json` | `144a7fb1483b4360353f0257e9403180af66bbd4e3906e70f102e21cb133a50a` | 旧 ZIP、399 基础输入及 17 Git 通知 |
| `ort-runtime-r1-notices-validation.json` | `5ad5fc452310690128337af6f91a089519629c8b54ca7c1fad6abfa9958b5543` | 通知来源、精确记录保留及纯文件拒绝检查 |

资源生成入口会在生成前后核对固定通知，显式重写资源锁时保留这 17 条已核验来源元数据；缺失、改字节、未知通知、符号链接和重复条目均拒绝。以上是普通文件与源码资源证据，**最终 APK 中的资源和通知仍等待整包回执**，12 库最终门禁保持原要求。

### 对应来源

发行材料须同时列出本批应用源码、三份基础原生源码 ZIP、已公开 Dawn 补充、cpuinfo 生产补丁、独立原生构建器及 NDK 29 实际输入/通知。NDK 29 的静态 C++ 身份不能由旧 `libc++_shared.so` 的来源条目代替。完整材料、固定下载身份和操作入口见 [构建与对应源码](../LANTYPE-BUILD-AND-SOURCES.md)。

### 已公开组件与 accepted 锁

[ORT component Release](https://github.com/ZPJJJ/LanType/releases/tag/ort-runtime-1.28.0-r1) 已于 `2026-11-18T04:33:36Z` 公开，release ID `449527123`，`prerelease: true`、`draft: false`，tag commit 为 `b5c46a43eeb48b574e067ff8a12316baea0fc938`。ZIP 的 asset ID 为 `761904810`，97,731,603 字节，SHA-256 `e03422b48b8a36f7a83cc8a458ec7c97c744d34139f219ee95cb28093e2d9d09`；包内共有 462 个文件，包含两次 Android 运行的实际证据、原生候选回执、通知与来源索引。原始 candidate manifest 和回执保持原字节，后续决定通过独立清单记录。

仓库 [ort-runtime.lock.json](../licensing/ort-runtime.lock.json) 与公开 accepted 附件逐字节相同：2,313 字节，SHA-256 `e751086cb82c90bb631bfdebf45f78e2f7462fcccf52373ca9141f45f0bf207b`，asset ID `761905088`。锁引用静态 ABI 回执和第六次原始 API `result.json`，明确两个 workflow 都为 failure，以及模型、产品、真机和 16 KiB 范围未测。锁与包内清单的“打包时尚未公开”字段保留历史值；实际公开时间和五个附件身份以 [ort-runtime-r1-publication.json](../licensing/ort-runtime-r1-publication.json) 为准，没有重新封包。

组件在公开前已通过正式恢复器的本地 ZIP 恢复与 accepted `--verify-only`，两份纯文件回执随 Release 发布；无凭证访问已确认 ZIP 的 HTTP 200/精确 Content-Length，以及 accepted 附件实际字节和 SHA。此处不把文件恢复与核验计作 SDK、原生或产品执行。11 月 18 日 AAR 重建的新回执与旧历史回执身份分别列在[组件说明](../licensing/ORT-RUNTIME-1.28.0-r1.md)。

## 整包与签名的待填记录

| 验证项 | 当前状态 / 后续须登记的实际材料 |
|---|---|
| 新 ORT component ZIP | 已预发布；真实 ZIP、462 文件清单及公开资产身份见上节 |
| accepted 运行锁 | 已公开并登记同字节仓库锁；只接受固定组件输入的静态 ABI 与普通 API 范围 |
| unsigned offline 整包 CI | 待 run ID、提交、实际退出码、APK 和构建日志 |
| 完整定向 JUnit 与 Compose 渲染 | 待本批实际 XML 统计和 PNG；不沿用旧版通过数 |
| 12 库最终门禁 | 待新 APK 原生回执，包含主 ORT 与其他 11 库身份 |
| 商业资源与 17 份通知随包检查 | 待最终 APK 资源回执 |
| 签名 APK | 待文件名、大小、SHA、实际包名/版本/证书校验 |
| 最终 manifest 与静态对齐 | 待 INTERNET、ABI、min/target SDK、调试/备份标志、ELF/ZIP 对齐回执 |
| 本批应用源码 ZIP | 待最终 Git 清单、对应提交、文件身份与资源校验 |
| 发行状态 | 待实际发布；当前为开发/预发布准备 |

目标 APK 包名/版本为 `app.lantype.keyboard`、`1.1.2`、`4`，官方升级包应保持原证书。目标配置不是从新签名 APK 读出的证据；候选锁必须在实际签名和校验之后填入完整真实身份。

[offline-ci.yml](../../.github/workflows/offline-ci.yml) 使用 4608 MiB 工作卷、卷外 512 MiB 分配量检查点、256 MiB 保留空间和受监控的命令超时；所有新缓存、源码副本和构建输出在卷内。空间或超时失败必须保留实际峰值和日志，不通过扩大预算隐藏。卷外检查点不构成连续的整个任务硬配额。证据成功上传后才清理自有卷。

## 产品设备 QA：分别记录三种数据语义

现有 [产品设备 workflow](../../.github/workflows/android-device-qa.yml) 和 [核心 driver](../../tools/lantype-device-qa/run-device-smoke.py) 使用显式已提交候选锁；新 APK 身份未知时不得默认选择 latest。

| 范围 | 应执行的正常流程 | 可以报告什么 | 不能据此报告什么 |
|---|---|---|---|
| `fresh-candidate` | 新 guest 首次装新候选，正常设置与启用，中文/美式英文输入、工具舱、剪贴板；保存新数据后同一候选 `install -r` | 新候选实际功能、新建数据经同包重装保留；当前待执行 | 旧版用户数据迁移 |
| `replace-uninitialized` | 新 guest 安装固定 1.1.1，立即 `install -r` 新候选；不启动或初始化旧版 | 未初始化旧 APK 的同签名替换及新包功能；当前待执行 | 已使用旧键盘的词库、设置或历史迁移 |
| `legacy-upgrade` | 旧版确实已初始化并形成数据，再升级和检查 | 只有实际完成后才能报告相应旧数据迁移 | 用未初始化替换或候选自身重装冒充旧数据迁移 |

旧 1.1.1 当前 bridge 首启失败，因此旧版完整 onboarding 不能作为新候选功能验收的强制前置。新候选功能与未初始化替换应使用不同的新 guest、分别运行；不能通过跳过旧版失败把 legacy-upgrade 写为通过。剪贴板验收仍要求同一次候选身份和核心实际通过回执。

真实 ARM64 手机另须完成启动、启用、中英文输入、工具舱、剪贴板及相关模型路径；16 KiB 设备须单独运行。模拟器正常 API、静态 LOAD/ZIP 对齐或桌面测试均不能代替这些结果。

## 商业发行边界与后续更新

本批继续按既定 GPL 源码与第三方许可方案准备，商业方案见 [COMMERCIAL-PLAN.zh-CN.md](../COMMERCIAL-PLAN.zh-CN.md)。当前首启修复、完整产品行为和真实 ARM64/16 KiB 验收未闭合，**尚不具备宣布稳定收费首发的验证依据**。

发行者后续只登记实际 run、文件和设备结果：从已公开并锁定的组件继续补新整包身份、产品 QA、真实设备、最终来源与签名发行材料；主机清理修复的实际运行结果另行保留。任一失败保留原证据和具体阶段，不由本页的计划文字推导为通过。
