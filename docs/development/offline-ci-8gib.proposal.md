# 云端 offline-ci 8 GiB 预算调整提案

状态：**仅供审阅，尚未应用，未获执行授权，没有触发第 20 次运行。**

可审查的远端基础为 [5e25abe0f8e6ff89043136985c8fd2fa2cf35726](https://github.com/ZPJJJ/LanType/commit/5e25abe0f8e6ff89043136985c8fd2fa2cf35726)，源码树 `3ec7a2546616fce5c3ff1e166af3ff513c93e429`。该提交已独立发布早期非 ARM64 ABI 过滤；没有新构建结果，以下节省仍是估计。补丁已在此基础再次通过只读 `git apply --check`，active workflow 仍保持原 5 GiB 规则。

## 为什么提出

[第 19 次运行](https://github.com/ZPJJJ/LanType/actions/runs/44242764644)（`44242764644`） 的两个固定下载缓存已成功复核并回收，实际释放 **237,035,520 字节**。APK 构建随后仍由原空间守护停止；退出码 143，`storageReserveStop=true`，不是编译语法错误或超时。stdout 最后已到 `reportOfflineComposeMappingErrors`，还没有资产合并、资产压缩、最终 APK 成功或目标测试的执行证据。

停止时工作卷的实际容量是 **4,670,029,824 字节**，已用 **4,545,748,992 字节**，可用 **107,503,616 字节**。与保留线 **268,435,456 字节**相比，已少 **160,931,840 字节**。收集阶段释放既有 8 MiB 紧急诊断预留后可用增加到 115,892,224 字节；这不能算作下一次构建的长期余量。

| 已测路径 | 实际分配字节 | 判断 |
|---|---:|---|
| `gradle-user/caches/9.5.0/transforms` | 1,573,351,424 | 最大可再生缓存；其中哪些输入仍被任务使用没有逐项证据，不建议活跃构建中删除 |
| `app/build/intermediates/mapping` | 351,838,208 | R8/Compose 相关中间产物；不能将其当作 Kotlin 增量缓存，也不能在消费任务结束前删除 |
| `app/build/intermediates/merged_native_libs` | 293,613,568 | 33 个文件，含非目标 ABI 中间件 |
| `app/build/intermediates/stripped_native_libs` | 293,523,456 | 第二份原生中间件；早期 ABI 过滤已独立发布，不在此补丁中 |
| `app/build/generated/lantype-assets` | 214,499,328 | 已生成的批准资源；后续还要合并和打包 |
| `gradle-user/caches/9.5.0/generated-gradle-jars` | 189,800,448 | Gradle 自身生成依赖；不是可随意删除的下载 ZIP |
| `app/build/kotlin` + `plugin-core/build/kotlin` | 14,733,312 | 已量到的整个 Kotlin 缓存目录只有约 14 MiB |
| `app/build/kspCaches` | 7,159,808 | KSP 独立缓存；即使连同 Kotlin 全部省掉，也远不足当前缺口 |

这些目录分层有重叠，表中父子层不能再次合计。另有未被默认预编译模式读取的 `generated/lantype-runtime-jniLibs` 24,219,648 字节；这是可以另行讨论的小范围免生成优化，仍不足解决现有空间缺口。

[Kotlin 官方文档](https://kotlinlang.org/docs/gradle-compilation-and-caches.html) 支持 `kotlin.incremental=false`，但也说明 JVM classpath snapshots 可能处于 Gradle 缓存。当前回执没有把 transforms 按类型细分，所以不能把整个 1.57 GB 归因到该开关，也不能声称该开关的节省已实测。已测到的两个 Kotlin 目录不足，是目前可以确认的结论。

## 为什么不能只跨过现有停点

固定 12 个 ARM64 库的新逻辑字节合计是 **86,937,280**。假设在 merge/strip 前排除其他 ABI，两份 native 中间件预计可减少约 **413,262,464 字节**；这是按现有分配与目标逻辑字节做的估计，非新运行结果。即便全部兑现，扣掉当前保留线缺口后，后续新增空间也只有约 **252,330,624 字节**。

资源锁中的 396 项资产合计 **212,907,126 逻辑字节**，生成目录实占 214,499,328 字节。[官方 AGP 9.1.0 源码包](https://dl.google.com/dl/android/maven2/com/android/tools/build/gradle/9.1.0/gradle-9.1.0-sources.jar)的 `MergeSourceSetFolders` 和 `CompressAssetsTask` 表明，合并资产和每项资产的压缩 JAR 都是独立输出，不是原地替换。只增加一份合并资产就接近吃完上述余量，压缩输出和 APK 尚未计入。

旧 1.1.1 APK 的已锁大小为 **179,987,242 字节**。规划时将后续压缩资产按不超过约 215 MiB、最终 APK 按约 320 MiB 的保守量级讨论，并为映射、打包临时写入和尚未运行的 Robolectric SDK 30/34/35 保留余量。它们均是**估计而非实际峰值**；8 GiB 也不是经过证明的数学最小值。当前证据不支持继续把 5 GiB 作为可完成全流程的承诺。

## 提议的明确范围

| 项目 | 提议值 | 控制方式 |
|---|---:|---|
| 每个串行 app CI job 的总临时预算 | 8 GiB | 仅 `build-offline` 与 `tests-and-renders`，两个 fresh runner，按 `needs` 串行 |
| 独占工作卷镜像 | 7,680 MiB，即 7.5 GiB | `fallocate` 固定大小；helper 核验镜像身份和实际挂载容量 |
| 卷外开销 | 512 MiB | 原有测量范围与检查点断言不变，不声称整体硬配额 |
| 卷内停止保留线 | 256 MiB | 原有守护采样与停止行为不变 |
| 建卷前目标文件系统可用空间 | 至少 28 GiB | 20 GiB 主机底线 + 8 GiB 本轮预算，写独立 JSON 回执 |
| 原 `storage_guard.py` | 原文件、原调用、原 25 GiB Linux 预检不变 | 新 28 GiB 检查是额外检查，不代替或绕过原 gate |
| 原生构建预算 | 5 GiB | 不改 |
| Android QA 预算 | 16 GiB | 不改 |
| HOME、本地构建行为 | 不改 | 不进行本地构建、不把缓存移到卷外 |

当前实际 Gradle 脚本与 `gradlew` 没有第二次 `storage_guard` 调用；本地 auto-deliver、原生构建和回放入口的独立 gate 保持原样。新检查针对真正承载工作卷的 `RUNNER_TEMP` 文件系统，原 guard 仍检查真正的 HOME 和既有生成物上限。

## 补丁内容与检查

补丁仅涉及以下三个文件：

1. `.github/workflows/offline-ci.yml`：两个 job 增加实际 28 GiB 前检，将工作卷设为 7,680 MiB；保留同 SHA、完整准备、全部测试选择器、APK 三项门禁、证据上传和成功上传后清理条件。
2. `scripts/run-offline-build-env.py`：容量常量、说明和精确镜像尺寸检查同步改为 7,680 MiB；256 MiB 保留线、512 MiB 卷外检查和两个已核验 ZIP 的精确回收逻辑不变。
3. `scripts/restore-ort-runtime.py`：增加显式 `--bounded-work-limit-mib 7680` 以配合该 CI 工作卷；默认仍为 4,608 MiB，未指定 bounded root 时拒绝较大档。普通恢复仍保留原 5 GiB 余量与 5 GiB 单次输入/输出限制，所有 size/SHA/路径/挂载检查保留。若不配套修改，旧 4.5 GiB 限制会让新 CI 在恢复阶段必然拒绝。

已完成的轻量检查：两份 Python AST、两个内嵌前检 Python AST、YAML 两个同 SHA 串行 job、19 个 shell 块 `bash -n`、常量与默认行为的静态核对、`git apply --check`。没有执行补丁中的预检、创建卷、挂载、SDK、Gradle、原生代码或 CI。

补丁及说明路径：

- [offline-ci-8gib.proposal.patch](offline-ci-8gib.proposal.patch)：未应用的完整补丁，11,700 字节，SHA-256 `de36483f0f21119c47aeeeb33f4784efca85c431ebcfe0e27e5f57ff12f437a1`。
- 基础树、补丁前后 SHA、原始回执 SHA、轻量检查结果和未执行状态另存完整回执；原始构建证据见上面的运行链接。

实施前需要取得本次 app CI 从 5 GiB 到 8 GiB 的明确授权；现有 16 GiB 授权只适用于 Android QA，不能自动用于 APK/测试构建。批准后仍须以新的真实运行记录确认 APK 与测试分别完成，不能把本提案当作成功回执。
