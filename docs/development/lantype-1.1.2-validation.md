# LanType 1.1.2 验证与发行准备（工作稿）

## 结论和使用范围

本页记录 `1.1.2 / versionCode 4` 的证据与未完成项。**已成功的是独立 ORT 原生候选构建及已记录的静态检查；普通 Android API 正向检查、应用整包和真实设备验收尚未通过登记。** 本页不是发布批准单，也不是“首启故障已修好”的声明。

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
| AAR 处理 | full/companion/ELF 三输出及原始 AAR 成员比较已记录 | ARM64 主库之外的官方 Java/JNI 内容保持身份；candidate 状态不变 |
| SDK/NDK 来源取证 | [run 44173535722](https://github.com/ZPJJJ/LanType/actions/runs/44173535722) 的 tools 阶段保存 NDK 29 输入身份与通知 | 安装工具链来源证据；不是 Android API 运行通过 |
| 普通 API QA 第四次运行 | [run 44175344640](https://github.com/ZPJJJ/LanType/actions/runs/44175344640) 因宿主 emulator loader 的 `libsndfile` 依赖受阻 | 未进入候选原生 API 正向检查，不能判为候选 API 通过或候选原生运行失败 |
| 普通 API QA 第五次运行 | [run 44177101937](https://github.com/ZPJJJ/LanType/actions/runs/44177101937) 的 tools、probe APK 构建、宿主 emulator 版本和 KVM 检查完成；在系统镜像安装阶段因存储保留量门禁停止 | loader 前置问题已有实际进展；没有启动 guest 或执行候选 API probe |
| 17 份离线许可通知 | [提交 1e7daacdaeac91983a436e1a2614ede02f725125](https://github.com/ZPJJJ/LanType/commit/1e7daacdaeac91983a436e1a2614ede02f725125)；396 个 assets、11 个 raw 的源码资源校验通过 | 新通知已按原始证据字节加入受锁资源；最终 APK 随包核验仍待完成 |

上述候选及回执的详细大小、摘要、配置和来源来自 [ORT 1.28.0-r1 组件说明](../licensing/ORT-RUNTIME-1.28.0-r1.md)。本页没有新增运行、生成假回执或将环境准备成功当作组件运行成功。

第五次运行的 workflow head 为 `9df415c407d8b4759de7e5da2099b4ceb9cdd01d`，job 为 `134371272874`。实际 evidence artifact `14369573492` 为 207,832 字节，SHA-256 `b9fe53f35c323beb0d313d0d609300435eaac651421c740e9e542be7aeb79549`。其中 `host-loader-dependencies.json` 的 `unresolved` 为 `[]`，emulator 版本命令与 KVM 检查通过；`image-026-sdk-image-install` 在解包 `x86_64/system.img`、进度 43% 时触及 256 MiB 工作卷保留量门禁，退出码为 143，`timedOut=false`、`storageReserveStop=true`。0.25 秒采样观察到的工作卷已用量峰值为 4,426,526,720 字节，不是连续测得的整个任务峰值。

`result.json` 实际记录为 `status=failed / stage=image`，错误为 `Command stopped with less than 256 MiB work-volume reserve; see image-026-sdk-image-install`。本次没有 guest 身份、app-runner 输出或 probe JSON，属于环境准备失败；新 ORT 的运行结果继续待验证。

## 下一次普通 Android API 检查

本次普通路径由 [ort-api-qa.yml](../../.github/workflows/ort-api-qa.yml) 与 [run-ort-api-qa.py](../../scripts/run-ort-api-qa.py) 管理：固定候选 run、head、artifact 和 manifest SHA；核对 GitHub 来源与文件身份；将正常 C API probe 放入临时 Android instrumentation APK，在专用 worker 调用，保存原始 JSON 输出、日志和 guest 身份。

目标是现有 API 35 x86_64、KVM 与 ARM64 bridge 环境。检查范围为候选 `dlopen`、C API 28 表、provider 枚举和 `CreateEnv` / 释放；APK 使用临时调试证书，没有产品签名或 INTERNET 权限。此项不覆盖模型推理质量、全部 provider 的实际推理、实体 ARM64 或 16 KiB 系统行为。

| 后续结果字段 | 当前状态 |
|---|---|
| 新 API run ID / workflow commit | 待实际新运行后登记 |
| 实际 guest API / ABI / native bridge / 页大小 | 待 guest 身份回执 |
| 原始 probe JSON 和 worker 正常返回 | 待实际结果 |
| API summary、stdout/logcat 与结果回执 SHA | 待实际结果 |
| 对新 ORT 运行状态的判断 | 当前仍待验证 |

环境 loader 修正只是让正常检查能够开始，不直接改变候选的验收状态。新的 run 只追加实际结果，不覆盖第四、第五次运行的环境失败记录。

新增的 [API 35 镜像准备脚本](../../scripts/prepare-api35-system-image.py) 与 [固定镜像锁](../qa/android-api35-image.lock.json) 已完成静态审阅。该入口采用固定官方镜像身份、分块校验及稀疏文件准备；目前没有执行其完整下载、解包、AVD 启动或 Android API 检查，不能登记为已通过的环境修复。

### 云端 QA 存储预算：提案尚未启用

第五次运行暴露的是镜像解包期间的实际空间停止。后续独立评估还发现：现有 5 GiB 总预算方案中的工作卷，在容纳镜像和工具后，无法同时满足官方模拟器 fresh-AVD 启动至少 5 GB 空闲空间的检查。优化镜像准备过程本身不能证明启动阶段可在原预算内完成。

[Android QA 存储预算提案](../qa/ANDROID-QA-STORAGE-PROPOSAL.md) 提出仅对云端普通 Android API / 产品设备 QA 使用总计 16 GiB 的预算，并提供尚未应用的变更方案。**该提案未启用，待用户决定预算后才能安排下一轮云端 QA；当前没有因此启动新 CI。** 本地、独立原生构建与既有 offline 整包构建预算保持原约束，API、原生及产品验收通过条件不因预算提案而改变。

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

新 ORT component ZIP 尚未公开，accepted distribution 锁尚待真实组件包和验收信息。这里不构造外层 ZIP SHA、asset ID、URL 或 accepted 状态。长期证据需随组件发行保留，不能仅依赖短期 Actions artifact。

## 整包与签名的待填记录

| 验证项 | 当前状态 / 后续须登记的实际材料 |
|---|---|
| 新 ORT component ZIP | 待真实文件、大小、SHA、manifest、公开资产身份 |
| accepted 运行锁 | 待实际输出身份和验收引用；当前不能用 candidate 锁替代 |
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

发行者后续只登记实际 run、文件和设备结果：先补普通 API 结果，再补 accepted 组件与新整包身份，随后分别补产品 QA、真实设备、最终来源与签名发行材料。任一失败保留原证据和具体阶段，不由本页的计划文字推导为通过。
