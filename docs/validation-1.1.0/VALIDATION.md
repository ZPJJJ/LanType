# LanType 1.1.0 预发布验证记录

2026-11-17，本轮产品源码提交：`8163acf4ec4a33167517a1e7dc12dcb5ca30fb88`。其后只整理文档、证据和审计脚本。本报告不复用 1.0.0 的验收结果。

**离线发行 APK 编译、R8、签名、包身份、资源清单和原生文件检查通过。20 个测试类最新结果合计 124 项通过、0 失败、0 错误、0 跳过。无 ADB 目标，ARM64 真机验收仍未完成。**

## 最终 APK

| 项目 | 实际结果 |
|---|---|
| 文件 | `LanType-1.1.0-offline-arm64-v8a.apk` |
| 大小 | 179,983,146 字节，约 171.65 MiB |
| SHA-256 | `03e379a9b77fbddba9886e28bfa9fc78e447dc4843917117faf625b4339d18c6` |
| 包名 / 版本 | `app.lantype.keyboard`；`1.1.0` / versionCode `2` |
| Android / ABI | minSdk 28，targetSdk / compileSdk 36；仅 `arm64-v8a` |
| 输入法 subtype | `zh_CN` / `zh-CN`，`en_US` / `en-US` |
| 调试 / 备份 | `debuggable=false`；`allowBackup=false` |
| 构建来源 | BuildConfig `GIT_HASH=8163acf`，同值也在最终 `classes.dex` |
| 证书 SHA-256 | `c03b15a19d2ed8899fee6b71f7be09ea5b54c7db9895d7d87b20a9759d8e090b` |

使用与 1.0.0 相同的独立证书；签名后全部原有 ZIP 文件逐项哈希未变。v1、v2、v3 分别在 API 23、24–27、28–36 范围验证通过；低 API 范围只用于检查签名方案，应用仍要求 API 28。详细值见 [APK 回执](apk-receipt.json) 和 [签名输出](apk-signature-verification.txt)。

实际权限为 VIBRATE、READ_EXTERNAL_STORAGE（maxSdk 32）、READ_MEDIA_IMAGES、READ_MEDIA_VISUAL_USER_SELECTED、RECORD_AUDIO、CAMERA、WAKE_LOCK、自有 DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION。**无 INTERNET、REQUEST_INSTALL_PACKAGES、RECEIVE_SMS、READ_CONTACTS、ACCESS_WIFI_STATE、ACCESS_NETWORK_STATE。** 见 [权限输出](apk-permissions.txt)、[编译 Manifest](apk-manifest-tree.txt) 与 [输入法配置](apk-input-method-tree.txt)。

## 构建、原生与资源结果

| 范围 | 实测结果与证据 |
|---|---|
| 离线发行构建 | 保留 R8，3 分 17 秒成功；80 任务，20 执行、60 已有结果。[构建回执](build-summary.json) |
| 原生库与 16 KiB | 最终 12 个 ARM64 ELF 全部 `PT_LOAD` 对齐至少 16 KiB，offset/vaddr 同余；`zipalign -c -P 16 4` 返回 0。[逐库报告](apk-native-libraries.json)、[zipalign](apk-zipalign.txt) |
| CameraX 源码重编 | 两库实际重编，JNI 导出（8 + 1）、SONAME、动态依赖核对通过；最终 APK 路径唯一、大小/哈希与锁一致，拒绝旧 Maven 二进制。[ABI 报告](camerax-native-abi.json)、[最终全包检查](final-apk-resources.json) |
| 不同路径重编 | 同一主机/固定工具链，在另一绝对路径全新编译 CameraX 两库，哈希一致；未测试不同主机。[重编报告](camerax-other-path-rebuild.json) |
| 资源清单 | 379/379 个 asset、11 个原创 WAV 的大小/哈希通过；扫描签名 APK 全部 2,164 个 ZIP 条目。[资源报告](final-apk-resources.json) |
| 公开源码 | 产品提交 3,015 个路径按实际 staged Git blob 扫描通过；252 条已移除资源记录对应 179 个唯一内容哈希。[Git 内容审计](git-index-resource-audit.json)、[公开文件预检](commercial-public-source-preflight.json) |

**16 KiB 限制说明：** 12 个库均为 ZIP deflate，Manifest 为 `extractNativeLibs=true`，安装时解压。压缩条目的 ZIP 原始偏移不是直接 mmap 地址，不宣称其原始偏移全部页对齐；上面的 ELF 检查和 zipalign 检查分别记录，也不代替真实 16 KiB Android 设备运行。

CameraX 使用 1.6.2 精确模块源码 `9046f07948c1e7a89aaec581463730f4d666611b`，明确选用 libyuv `741c38751c436f60c583110f617340b7f3322d94`，以 NDK 27.2.12479018 / CMake 3.22.1 / API 28 重编。此 libyuv 是本版选定输入，不冒充 Google 原预编译库的内部版本。其余原生文件复用固定二进制并配套对应源码；没有声称全部原生依赖或整 APK 逐位可复现。

原生源码附件 `LanType-1.1.0-native-source.zip` 包含 **70 份实际源码归档**及锁清单，大小 1,019,291,548 字节，SHA-256：`acc768e67a4daf56ce79e78e1161dadf3998086add7cbef645e2a37f30d9d95e`。Rime 补丁对固定树检查通过：[补丁报告](native-source-patch-check.json)。附件不包含产品模型/词库；上游源码本身的测试夹具保留。若发行渠道拆为独立可解压分卷，分卷值见发行清单。

资源锁 SHA-256 为 `db6c94c9cb44de3b883ba237fc04de3d3e7d61d3ed5ab9f383508f5bc18a6381`。门禁检查未知 asset、重复 ZIP 条目、旧内容哈希；生成资源只允许明确路径并断言内容，没有整目录放行。一个既有非 ASCII 文件名的 AAPT UTF-8 标志缺失以原始名字节精确解码，映射记录在报告中，未跳过其哈希。

最终应用源码 ZIP 根据经审阅的 Git 清单生成，运行依赖 ZIP 根据批准资源和原生锁生成，均不递归打包工作目录。各成品 ZIP 生成后另做内容审计并附发行回执，避免把尚未生成的包预先写成通过。

## 自动化测试与渲染

**20 类、124 个唯一最新用例全部通过。** 8 批合计执行 188 次；重复渲染不算新增覆盖。批次执行数依次为 50、99、5、3、8、5、5、13。证据：[完整汇总](targeted-tests-summary.json)、[最新原始 XML](junit/final)。

| 范围 | 最新用例数 |
|---|---:|
| 美式拼写、错拼、英文启动/缩写、空格和真实编辑器替换 | 42 |
| 工具舱量纲/文本/模板、InputConnection、旧队列边界、渲染 | 45 |
| 工具舱隐私隔离 | 8 |
| 语言偏好迁移与中英边界 | 13 |
| 工具栏布局 | 5 |
| 真 AssetManager 资源读取 | 3 |
| 首启/本地资源、设置/关于、验证码手动粘贴、来源列表 | 8 |

初轮暴露 Mockito 动态附加失败、`I'll` 大小写资产回归和缺少渲染环境变量；修复后重跑。截图发现深色前景色问题，已修复并渲染。Compose `captureToImage` 在此 Robolectric 环境失败，改用核对过 API 的 View 重绘；失败和最终通过 XML 都保留。

测试运行 `testDebugUnitTest`，发行构建运行 `offline`。末尾增量修复只重跑关联范围，再编译完整 APK；不声称最终提交上重新执行过一次包含全部 124 项的单批运行。测试 JVM 的 Mockito premain 及 Robolectric 配置在 `scripts/test-runtime.init.gradle`。

本轮保留 [14 张组件截图](screenshots)，均为 Robolectric 渲染，不是手机截图。6 张因连续绘制静态层缺失的诊断图移出公开包，未作为完整 UI 展示。InputConnection、AssetManager 和 Compose 参与本地测试，但不运行 ARM64 原生引擎。

## 主机补充检查与未验证范围

本轮真实资源补充结果：英文 89,140 词/209,246 节点及排名、Bigram 索引回归通过；9,636 手写模板的 16 个手工单字轨迹均入前十；随包 Whisper INT8 在 x86_64 CPU 实际转写一段中/英样本，中文仍有误差；115 个 Rime 部署文件、147,288 中文词条和 14 个 schema 字典引用静态核对通过。分别见 [词库](commercial-vocabulary-host.json)、[手写](commercial-handwriting-host.json)、[Whisper](commercial-whisper-host.json)、[Rime 静态](commercial-rime-resource-static.json)。这不是广泛准确率或 Android 延迟基准。

实际 [adb devices](adb-devices.txt) 为空。**未完成真机安装、系统 IME 启用/切换、首次 Rime 部署、九键候选质量回放、麦克风/相机及 ARM64 模型推理、真实 16 KiB 设备、持续耗电或升级数据验收。** 本版用于外部测试预发布。GitHub CI 尚未运行，不把本地成功表述为远程 CI 通过。

## 主要重跑命令

准备环境、对应源码及打包详情见 [构建指南](../LANTYPE-BUILD-AND-SOURCES.md)。`APK` 替换为本地成品路径；签名私钥、密码和本环境代理均不在公开源码中。

```bash
python3 scripts/prepare-upstream.py
python3 scripts/build-camerax-native.py --download
python3 tools/lantype_resources/prepare_resources.py --download
./gradlew :app:assembleOffline --no-daemon --max-workers=1 \
  -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx4096m -Dfile.encoding=UTF-8'
./scripts/test-targeted.sh
python3 scripts/build-camerax-native.py --verify-apk "$APK"
python3 scripts/verify-commercial-resources.py --apk "$APK" --json final-apk-resources.json
apksigner verify --verbose --print-certs "$APK"
zipalign -c -P 16 4 "$APK"
```
