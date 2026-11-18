# Android 云端 QA 存储预算：16 GiB（已批准并应用）

状态日期：2026-11-18。**用户已在本会话明确回复“允许”，批准以下云端 QA 专用预算。维护者已核对公开基线和补丁摘要，并原样应用四份配置/脚本改动。预算批准与配置应用不代表 Android API 或产品验收通过，实际运行结果仍须另行记录。**

本次已批准的范围是在 GitHub 临时 runner 上，为下面两个 Android QA workflow 单次保留 **16 GiB** 临时数据预算，其中 **15.5 GiB 为独立工作卷，512 MiB 为卷外检查点额度**。这项例外只覆盖 `ort-api-qa.yml` 与 `android-device-qa.yml`；本地任务、原生 ORT 构建和 offline 应用构建仍遵守原有 5 GiB 预算。

[AGENTS.md](../../AGENTS.md) 的“空间硬约束”明确规定单轮新增临时数据预算 5 GiB、重型任务串行，以及不得绕过 `storage_guard.py`。本次用户授权明确覆盖下面两项云端 QA 的 16 GiB 例外；维护者据此应用补丁并按顺序调度。仓库规则文件、全局门禁和 `HOME` 均保持原样，其他构建仍受原预算约束。

补丁：[android-qa-16g-proposal.patch](android-qa-16g-proposal.patch)。它保留为本次已批准修改的原始差异，基于下文的公开提交；当前分支已应用一次，不应重复应用。

## 已发生的结果，与尚未执行的启动门槛

| 事项 | 证据与当前结论 |
| --- | --- |
| ORT 原生构建 | [run 44164186969](https://github.com/ZPJJJ/LanType/actions/runs/44164186969) 成功生成候选 `libonnxruntime.so`；ELF SHA-256 为 `ae250081faa6cd742f6edade2a23bf29a96ba690fa19a01e3bd192548cf89f1e`。构建成功只证明产物产生，不能代替 Android API 验证。 |
| 普通 API QA run 5 | [run 44177101937](https://github.com/ZPJJJ/LanType/actions/runs/44177101937) 的 host loader 与 KVM 检查已完成；官方镜像解包到 `system.img` 时触发 256 MiB 工作卷保留量，任务按约束停止，尚未启动候选原生 API 检查。 |
| 解包停止的实际回执 | `commands.jsonl` 记录 `storageReserveStop=true`、`timedOut=false`、退出码 143；采样所见峰值为 **4,426,526,720 B**。这是观测峰值，不是连续峰值保证。镜像准备前工作卷已用 **977,723,392 B**，实际可用 **3,675,529,216 B**。 |
| 后续 fresh-AVD 启动 | 尚未在该 run 执行。下面的官方空间门槛是对后续步骤的独立核查，不能写成 run 5 的实际报错，也不能声称现有二进制已触发它。 |
| 产品与设备验收 | 本提案不证明输入法启动、中英输入、工具或剪贴板通过；不证明旧用户数据迁移，也不代替真实 ARM64 / 16 KiB 设备验收。 |

官方 [Android Emulator troubleshooting](https://developer.android.com/studio/run/emulator-troubleshooting#check-for-adequate-disk-space) 说明启动至少需要 **5 GB free**。这里保留官方的 **GB** 单位，不改写成 5 GiB。4.5 GiB 卷的总容量只有 4,831,838,208 B，还需容纳工具与镜像，因此无法提供官方要求的空闲空间。

固定的 [AOSP emulator 源码 `ae9d18d2b6261179fbd57fffec720a04f7bfb053`](https://android.googlesource.com/platform/external/qemu/+/ae9d18d2b6261179fbd57fffec720a04f7bfb053/android-qemu2-glue/main.cpp) 中，`firstTimeSetup` 在 wipe 或 userdata 不存在时成立；API ≥ 24 或 Play Store 镜像的首次 userdata 容量至少为 `6 × 1024³` B，即 **6 GiB**。目标 userdata 文件不存在时，创建前还检查至少 **1.2 倍容量，即 7.2 GiB 可用空间**。这是本提案的容量规划依据；尚未建立该源码提交与已安装 emulator 37.2.13 二进制的一一对应关系，因此它不是对该二进制已发生行为的断言。

当前的固定镜像准备工具使用流式校验、经过首遍块哈希绑定的 HTTP Range 读取与保留原始字节的稀疏解包，避免在磁盘另存整份 ZIP。该措施减少解包峰值，不能改变模拟器对真实可用空间的要求。本提案不会制造“已初始化” userdata、修改容量报告或关闭模拟器的空间检查。

## 预算与停止条件

所有 MiB/GiB 按 1024 进制计算；官方文档的 5 GB 保持其原写法。镜像文件长度是工作卷上限，格式化后的实际可用空间还需扣除文件系统元数据。

| 项目 | 已批准数值 | 检查方式 |
| --- | --- | --- |
| QA 工作卷镜像长度 | **15,872 MiB = 15.5 GiB = 16,642,998,272 B** | `fallocate` 建立独占 ext4 卷；共享 driver 验证镜像长度与独立挂载。 |
| 卷外额度 | **512 MiB = 536,870,912 B**，维持原值 | 既有检查器按 `lstat.st_blocks × 512` 计量 checkout、runner temporary、actions 代码；硬链接去重、不跟随 symlink，并排除自有卷镜像与挂载内容。 |
| QA 总预算 | **16 GiB = 17,179,869,184 B** | 15.5 GiB 卷加 512 MiB 卷外检查点额度；`wholeTaskHardQuota=false` 保持不变。 |
| 分配前 host 空闲 | **≥ 36 GiB = 38,654,705,664 B** | 两个 workflow 直接读取 `QA_VOLUME` 父目录 `RUNNER_TEMP` 所在真实文件系统的空闲空间，以 20 GiB host 保留量加本次 16 GiB 预算为预检条件；保留原 `storage_guard.py`。 |
| guest 启动前卷内空闲 | **≥ 7,680 MiB = 7.5 GiB = 8,053,063,680 B** | `before-guest` 和 `before-product-boot` 回执写入 `requiredGuestAvailableBytes`、实际 `volume.availableBytes` 与 `guestAvailablePassed`；不足即 `passed=false` 并在启动前说明实际字节数。 |
| AVD userdata | **`disk.dataPartition.size=6G`** | 使用正常 AVD 配置声明容量；保留 fresh guest、`-wipe-data` 和 `-no-snapshot`。 |
| 运行中保留量 | **256 MiB**，维持原值 | 现有命令监控按真实卷内使用量停止自有进程组，保留日志和失败回执。 |
| 证据紧急保留文件 | **8 MiB**，维持原值 | 沿用现有收集流程。 |

512 MiB 卷外额度仍是指定阶段的计量与断言，**不是卷外硬配额，也不是连续整任务峰值保证**。36 GiB host 检查是分配前置条件，不声称对其他系统进程提供持续空间隔离。若任一真实预算门槛失败，应保留失败证据并停止，不自动放宽数值。

从容量估算看，锁定镜像的全部逻辑内容为 **3,754,673,936 B（约 3.50 GiB）**，即使不依赖稀疏节省，加上 run 5 镜像准备前约 **0.91 GiB** 的已有卷内数据，15.5 GiB 卷仍有约 10 GiB 量级的启动前余量。后续 APK、userdata、文件系统元数据和日志会继续占用空间，因此估算只能支持提案的合理性，实际能否启动必须由上述 **7.5 GiB** 检查决定；完整 QA 成功仍需实际运行证据。

## 已应用补丁的精确范围

| 文件 | 已应用变更 |
| --- | --- |
| `.github/workflows/ort-api-qa.yml` | 工作卷 4,608 → 15,872 MiB；新增真实 `RUNNER_TEMP` 文件系统 36 GiB 预检与 JSON 回执；共享 QA 串行组。 |
| `.github/workflows/android-device-qa.yml` | 同一卷大小与 host 预检；保留显式 mode / candidate lock 和原有产品验收要求；共享 QA 串行组。 |
| `scripts/run-ort-api-qa.py` | QA 容量断言、回执和说明一致更新；两个 guest 前检查点要求 7,680 MiB 实际空闲；AVD userdata 显式 6G。 |
| `scripts/prepare-api35-system-image.py` | 仅更新独立 QA 卷容量上限和说明；固定 ZIP 身份、许可条件、完整性检查与稀疏解包内容不变。 |

两个 QA workflow 改用同一 `concurrency.group=lantype-android-qa`，并保留 `cancel-in-progress=false`。每次只在新的临时 GitHub runner 中建立一个自有环境，使用显式候选身份；现有的手动触发方式不变。原生构建、应用构建及 QA 之间仍按仓库要求人工串行调度，本补丁没有扩张其他工作流的并发或存储权限。

原生构建 `native-ort-build.yml`、应用构建 `offline-ci.yml`、`run-offline-build-env.py`、`storage_guard.py`、`AGENTS.md` 和产品验收脚本不在补丁中。它们的 **4,608 MiB 工作卷 + 512 MiB 卷外检查点**及原有门禁不变。共享 product 环境仅调用原有的 `before-product-boot` 检查点，因此无需复制或改变产品测试代码。

监控、超时、自有进程组管理、原始 stdout / logcat / 界面证据收集均沿用现有流程。只有 `steps.evidence.outcome == 'success'` 时才卸载并删除本次自有卷；上传失败时不主动删除唯一证据。GitHub 临时 runner 的平台生命周期仍可能结束，不能把本地保留视为永久存储。

开发和云端构建可以下载固定工具与依赖；输入法在手机运行时不依赖联网的目标不变。该补丁不会接受新的 SDK 许可、改变候选 ELF、替换产品证书、签名或发布产品。

## 基线与纯静态校验

公开代码基线：[`51ee2119fcecd0d6fd5baa9e853a5b0639097075`](https://github.com/ZPJJJ/LanType/commit/51ee2119fcecd0d6fd5baa9e853a5b0639097075)，位于 `development/1.1.2-runtime` 分支。以下四个文件与该提交的字节一致；应用补丁前仍须核对这些 **SHA-256**，防止后续修改改变基线。

| 基线文件 | SHA-256 |
| --- | --- |
| `.github/workflows/ort-api-qa.yml` | `f5f75dc9889ac5f4133fac388b17d063e71075666f3ddbd006f3c2a6d262d5a0` |
| `.github/workflows/android-device-qa.yml` | `e300e36181cd6ecf3bc1abf0a8c427ab6e8ce5d0e628e64d40ea60a1921d50ae` |
| `scripts/run-ort-api-qa.py` | `f6db3062e102e37ee346b90db7aa72aacec0df2770b92400c76c7f5c255bc02d` |
| `scripts/prepare-api35-system-image.py` | `c74b99e530b38f08f7cf334ef92b46a24267495b83d9f319390b7cdc426ca6b3` |

补丁 SHA-256：`e2756b269af6b3cd2fb6058b2d654a0e9552e942fee17fe881f15bb440fcc3b5`。

| 内存应用后的预期文件 | SHA-256 |
| --- | --- |
| `.github/workflows/ort-api-qa.yml` | `dbe517aa98103e9e54a252af0bc8210038e73e90f287512a2ccad13894696487` |
| `.github/workflows/android-device-qa.yml` | `02d0c810b64e6e2cf6f7939d940d00f245eb143a526b0338844656449c623c4f` |
| `scripts/run-ort-api-qa.py` | `ea58cd3140fb2fa580b03075d5a2331c47645002d39273e3e9c141dfa7891eea` |
| `scripts/prepare-api35-system-image.py` | `5bb663fcf58be7bbdba480c5e446bc6c3756baea1776364801354a6daa767f9a` |

制作时完成以下检查：

- 将四组 unified diff 在内存中逐 hunk 校验并应用，结果与预期文本逐字节一致；没有向现有目标路径写入补丁。
- 两份 Python 文本的 AST / compile 静态检查通过；仅 `Driver.budget()` 与 `Driver.image()` 的方法 AST 发生预期变化，其余 driver 方法保持一致。
- 两份 workflow 的 YAML 解析、全部 **24** 个 shell `run` 块的 `bash -n` 以及 **2** 个内嵌 Python heredoc 的 AST 检查通过。这里没有执行 shell 任务。
- 触发方式、权限、候选参数、成功上传后清理的条件、`-no-snapshot` 和 256 MiB 运行保留量均保留；guest 空间条件与卷外额度共同决定检查点是否通过。
- 补丁目标集合严格为上述四文件；原生与 offline 工作卷仍为 4,608 MiB；四个既有基线文件在生成前后字节一致。

这些只是补丁可应用性与语法检查，**不包括 SDK 安装、镜像下载、CI 调度、guest 启动、原生运行或功能验收**。用户现已明确同意上述 QA 专用预算例外，补丁也已按基线应用；维护者接下来按顺序运行普通 API QA 和两种真实产品 QA。任一步仍应以实际回执记录成功或失败。
