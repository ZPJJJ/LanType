# LanType 1.1.1 构建、资源与对应源码

本文件说明 1.1.1 兼容修复批次的构建与交付方式。实际构建、测试、APK 指纹和未验收范围见 [1.1.1 验证报告](validation-1.1.1/VALIDATION.md)；本说明不预先声明安装包或设备验收通过。`docs/validation-1.1.0/` 与 `docs/validation/` 分别保留 1.1.0、1.0.0 的历史材料，不能代替本批验证。

**2026-11-17 来源范围更正：** 实际 ORT 共享库包含 Dawn/WebGPU，原 70 份基础原生源码归档没有包含这部分嵌套来源。补充包正在核验，当前不能把原三份源码包单独称为完整覆盖。APK、旧归档和 tag 不变；状态与后续独立校验方法见 [Dawn 源码补充说明](licensing/DAWN-SOURCE-SUPPLEMENT.md)。

本批修复工具舱复制内容进入普通剪贴板历史的隐私边界、连续录音期间 Whisper 中英语言切换，以及遗留词库恢复中冲突或搬移失败数据被删除的问题。后者保留旧路径中的数据，不自动合并或启用两份数据库；完整范围见 [1.1.1 变更记录](CHANGELOG-1.1.1.zh-CN.md)。SDK、JDK、发行签名、模型、词库、原生库及其运行资源锁沿用 1.1.0。

## 版本与构建方式

| 项目 | 本版固定值 |
|---|---|
| 应用 ID | `app.lantype.keyboard` |
| versionName / versionCode | `1.1.1` / `3` |
| 支持 ABI | `arm64-v8a` |
| 最低 Android | API 28 / Android 9 |
| compileSdk / targetSdk | 36 / 36 |
| 本轮 JDK | 21.0.13 |
| Gradle / Android Gradle Plugin | 9.5.0 / 9.1.0 |
| Android Build Tools | 36.0.0 |
| 发行变体 | `offline`，保留 R8 |
| Rime JNI 源码模式的 NDK / CMake | 29.0.14206865 / 3.22.1 |
| CameraX 首次源码构建 NDK / CMake | 27.2.12479018 / 3.22.1 |

应用 Java/Kotlin、Compose、插件宿主和资源从本项目重新编译。常规构建复用经过 SHA-256 锁定的 ARM64 原生二进制；不复用上游 DEX。源码 namespace 保留 `com.kingzcheung.xime`，与 JNI 类名契约一致。包名、产品资源和发行签名由 LanType 独立管理。

应用运行时没有 `INTERNET` 权限。初始化语音资源只读取安装包，本地恢复也不下载。开发阶段取得 Gradle、Maven、SDK、源代码和模型构建输入需要网络；与手机运行时权限无关。

## 发行物与复用依赖

- 本批安装包：`LanType-1.1.1-offline-arm64-v8a.apk`。以本批 Release 的实际附件、签名校验和 SHA-256 为准。
- 本批应用源码：`LanType-1.1.1-source-release.zip`，解压根目录为 `LanType-1.1.1/`，包含经审阅的应用源码、构建脚本、许可证、测试、受许可的生成源与小资源。
- 运行依赖：复用已发布的 `LanType-1.1.0-runtime-dependencies.zip`，内容与本批资源及原生锁一致，不重新命名为 1.1.1 内容。
- 基础原生源码：复用已发布的三个 `LanType-1.1.0-native-source-part-*-of-3.zip`，合计 70 份实际固定版本源码归档。三个文件都是普通独立 ZIP，应分别解压到同一目录。Dawn/WebGPU 的独立补充源包还需一并提供和校验，不能由这 70 份的数量推导完整覆盖。

Git 不存放 ONNX 模型、预编译 `.so`、大第三方树、APK、签名私钥、口令、私人测试照片或历史插件二进制。大文件在配套附件中提供，或由显式开发准备命令校验下载。

### 固定下载地址与 SHA-256

下列文件名、大小和摘要与 [已发布的 v1.1.0-rc1 API 清单](https://api.github.com/repos/ZPJJJ/LanType/releases/tags/v1.1.0-rc1) 一致，也与本地旧发行校验回执一致。本批 Release 复用这些固定地址和原摘要；应用源码仍必须使用本批的 1.1.1 文件。

| 复用附件 | 大小（字节） |
|---|---:|
| [LanType-1.1.0-runtime-dependencies.zip](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-runtime-dependencies.zip) | 139,297,354 |
| [LanType-1.1.0-native-source-part-1-of-3.zip](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-1-of-3.zip) | 339,827,618 |
| [LanType-1.1.0-native-source-part-2-of-3.zip](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-2-of-3.zip) | 339,828,069 |
| [LanType-1.1.0-native-source-part-3-of-3.zip](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-3-of-3.zip) | 339,828,348 |

下载后在四个 ZIP 所在目录校验：

```sh
sha256sum --check <<'SHA256'
42a0e57c002662e2a502719a7f002b061fd49605d92a87cab221bf6d9aa922bc  LanType-1.1.0-runtime-dependencies.zip
00223f5255a7b6b1d9f32ea52402fd2693cc879c530e59a60d8e80fa11882b57  LanType-1.1.0-native-source-part-1-of-3.zip
1ef3f166b8992957e5518b451de50def7db42d1443a1dc32811c3a7fc46c9eec  LanType-1.1.0-native-source-part-2-of-3.zip
7f3b2a772532ba5ff65086efd289ac214577d498974d2253a6e4078547b8b4f7  LanType-1.1.0-native-source-part-3-of-3.zip
SHA256
```

### 将旧依赖放进新源码目录

先按本批发行摘要校验 `LanType-1.1.1-source-release.zip`，再解压到一个新的工作目录。旧 runtime ZIP 的根目录仍叫 `LanType-1.1.0/`，不能把它误当作本批源码根目录。以下命令只将其中的 `app/` 运行资源和 `vendor/` 原生依赖放到新源码的对应路径：

```sh
unzip LanType-1.1.1-source-release.zip -d build-work
unzip LanType-1.1.0-runtime-dependencies.zip -d runtime-stage
cp -a runtime-stage/LanType-1.1.0/app/. build-work/LanType-1.1.1/app/
mkdir -p build-work/LanType-1.1.1/vendor
cp -a runtime-stage/LanType-1.1.0/vendor/. build-work/LanType-1.1.1/vendor/
```

保留新源码中的根目录 `LICENSE`、`NOTICE`（如有）、`docs/licensing/` 锁文件、构建脚本与说明；不要把旧 runtime 根目录整体覆盖到新源码根目录。`app/` 中的随包许可及资源与本批锁定内容相同，补齐后仍用当前源码的校验脚本检查。旧发行的 source ZIP 或 CI 补丁不需要叠加到 1.1.1 源码。

三个原生源码 ZIP 内没有 `LanType-1.1.0/` 前缀，分别解压到一个单独的源码附件目录：

```sh
unzip -n LanType-1.1.0-native-source-part-1-of-3.zip -d native-source
unzip -n LanType-1.1.0-native-source-part-2-of-3.zip -d native-source
unzip -n LanType-1.1.0-native-source-part-3-of-3.zip -d native-source
```

合并后是 `native-source/archives/` 下的 70 份源档，以及根目录的 `native-sources.lock.json`、`README.md`、`GPL-LICENSE.txt`、`SOURCE-SHA256SUMS.txt` 和 `PARTS-README.txt`。三包的根说明重复且字节相同，`unzip -n` 保留第一份即可；源档分别为 23、23、24 份，没有重复。不要用 `cat` 拼接这些 ZIP。后续 `--archive-dir` 指向该 `archives/` 目录。

原生源码附件内的锁文件是旧发行快照；当前应用源码锁为六项源档补充了 Gitiles 获取元数据，70 项归档的文件名、大小和 SHA-256 均未改变。恢复与校验始终使用当前应用源码里的脚本和 `docs/licensing/native-sources.lock.json`，不要用附件中的旧锁覆盖它。

## 常规构建

在 Linux 上安装 JDK 21、Python 3.12、Android SDK Platform 36 和 Build Tools 36.0.0。设置 `JAVA_HOME`、`ANDROID_HOME`，或在本地 `local.properties` 中设置 SDK 路径。SDK 路径和代理配置不要提交。

从公开源代码准备依赖：

```sh
python3 scripts/prepare-upstream.py
python3 scripts/build-camerax-native.py --download
python3 tools/lantype_resources/prepare_resources.py --download
python3 scripts/verify-commercial-resources.py
./gradlew :app:assembleOffline --no-daemon --max-workers=1 \
  -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx4096m -Dfile.encoding=UTF-8'
```

已经按上节补齐运行依赖时，可以在 `build-work/LanType-1.1.1/` 中先执行以下本地校验，再运行同一条 Gradle 构建命令，不必重新生成或下载这些已锁定资源：

```sh
python3 scripts/prepare-upstream.py --verify-only
python3 scripts/build-camerax-native.py --verify-only
python3 scripts/verify-commercial-resources.py
```

这些本地校验不替代 Gradle/Maven/SDK 准备；开发机器缺少构建依赖时，Gradle 仍需要获取相应公开组件。

`prepare-upstream.py` 只提取 `native-prebuilt.lock.json` 列出的 6 个原生库和 Sherpa Java API JAR。它不会提取上游 APK 的 assets、词库、语音模型、手写数据或 DEX。即使本地旧 vendor 目录还有其他库，Gradle 也只同步锁中批准的 JNI 文件。

Gradle `preBuild` 强制执行资源白名单和原生哈希检查。资源只来自 `app/src/main/assets` 的审核集合，旧上游 `prepareChineseDictionaries`、九键语料下载、SenseVoice、日语和翻译资源任务不挂到本版构建。源码模式也使用同一资源入口。

依赖版本在 `gradle/libs.versions.toml` 与构建脚本中固定；Gradle 发行包有 SHA-256，Maven 实物校验记录在 `gradle/verification-metadata.xml`。改变依赖时应先核对官方来源，再更新校验表。CI 不会自动放宽验证或修改这份表。

## 商业版资源来源

逐文件原始网址、修订、许可、变换、大小和 SHA-256 在 `docs/licensing/resources.lock.json`；被移除内容的拒绝哈希在 `excluded-resources.json`。`tools/lantype_resources/sources.lock.json` 锁定可编辑生成源，生成脚本保留变换过程。

本版从 SCOWL 重建美式英文词表、Trie、滑行输入与相关字典；中文基础数据采用经记录的 AOSP、CC-CEDICT 及各输入方案许可来源。手写采用 Make Me a Hanzi 数据和本项目原创拉丁模板；语音使用随包 Whisper base INT8；OCR 和 VAD 采用各自明确许可的资源。原创联想是小型人工规则表，不宣传为大型统计语料模型。

本版不恢复旧 SenseVoice、OCHWPro、MathWriting、Google 高频英文词表、LCCC、旧大九键统计语料、azooKey 或没有随包模型的 slimt 能力。具体许可边界以资源锁、离线许可证原文和商业说明为准，不能将所有第三方内容统称为 GPL。

AAPT 会对源文件 `.gz` 自动解压并移除后缀。本版运行资源使用与 `AssetManager` 访问一致的显式文件名；手写 `.lth`、原创联想 `.tsv` 与 `.completions` 不再靠不明确的压缩后缀行为。`CommercialAssetPackagingTest` 验证真实测试 APK 中的资产访问。

## 对应原生源码与选用的源码重建

`docs/licensing/native-sources.lock.json` 记录实际下载归档、原始提交、哈希和安装位置，包括：

- 固定 CyIME 提交的 JNI 包装层、CMake、Gradle/build-logic 与补丁原文；归档已排除其全部旧应用 assets。
- librime、Lua、octagram、predict、Snappy、glog、LevelDB、marisa、OpenCC、yaml-cpp 与递归依赖；Boost 1.89.0。
- Sherpa-ONNX 1.13.8 和其静态依赖，包括 kaldi、OpenFst、Piper、eSpeak NG、KissFFT、Eigen 等。
- ONNX Runtime 1.28.0；Sherpa 静态库使用的另一份 ONNX Runtime 1.28.2；相应 Android CPU/NNAPI 依赖源。
- OpenCV 4.12.0、Sora editor 0.24.6、实际 Android C++ 运行时源码与相关原生依赖。

本版不能把整个 Sherpa JNI 称作 Apache-only：其静态依赖还包含 eSpeak NG 的 GPL 条款。Sora 按 LGPL-2.1-or-later 提供，octagram 保留 GPL。实际许可证原文随应用的 `licenses/native/` 等目录离线提供，作者声明保留在完整源码归档中。

先校验实际源码附件，再恢复 JNI 构建输入：

```sh
python3 scripts/restore-native-sources.py \
  --archive-dir /absolute/path/native-source/archives --all --verify-only
python3 scripts/restore-native-sources.py \
  --archive-dir /absolute/path/native-source/archives
python3 scripts/prepare-native-build.py --download
./gradlew :app:assembleOffline -Plantype.nativeFromSource=true \
  --no-daemon --max-workers=1 -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx4096m -Dfile.encoding=UTF-8'
```

也可显式 `restore-native-sources.py --download` 取得相同的已锁定源码；`--all` 恢复额外上游 runtime/dependency 源树。脚本保留现有非空源码目录，不覆盖开发者修改；原始源资产子模块不会恢复到应用。

`-Plantype.nativeFromSource=true` 重建本项目 Rime/JNI 包装层，同时仍使用已锁定 Sherpa 原生库和官方 ORT AAR。独立重建 Sherpa、ORT、OpenCV 等上游项目应使用归档内相应构建脚本和工具版本；该选项不是“一次重新编译所有第三方原生库”的承诺。Sherpa 官方 Android 静态构建使用 NDK 27.0.11718014，与 Rime 的 NDK 29 配置不同。

CameraX 1.6.2 与 Graphics 1.0.1 的精确发布模块、Java/Kotlin sources JAR 和 libyuv prefab 包装层源码也已归档。Google CameraX 发布包的独立 libyuv 提交未能唯一确认，因此本批沿用 1.1.0 从源码重编的两个 JNI 库：保持 CameraX 1.6.2 实现和导出接口，明确选用 AOSP libyuv `741c38751c436f60c583110f617340b7f3322d94`，使用 NDK 27.2.12479018、CMake 3.22.1、ARM64/API28 和静态 C++，不启用 JPEG。真实输出在 `camerax-rebuilt.lock.json` 锁定；最终 APK 必须逐文件匹配，不能只依赖 Gradle pickFirst 顺序。

从 Git 的小文件源码首次构建该组件，需要另外安装 `ndk;27.2.12479018` 和 `cmake;3.22.1`，然后运行 `python3 scripts/build-camerax-native.py --download`。运行资源附件已包含经过验证的两库时，可用 `--verify-only`，不需要重新取得 NDK。这两库的 8+1 个 JNI 导出名、SONAME、系统库依赖和 16 KB LOAD 对齐已与原接口合同核对；没有把选用的 libyuv 说成 Google 旧包的内部版本。

1.1.0 的记录已验证这套固定源码档的哈希、实际解包、ORT 头文件/共享库准备及 Rime/Lua/octagram 补丁适用性；1.1.1 复用相同输入。**未建立全部上游原生二进制的逐字节重现，也未执行全部第三方库源码重编。** 本批实际执行步骤和限制以 1.1.1 验证报告为准。

## 测试与图像证据

```sh
bash scripts/test-targeted.sh
```

脚本设置 `CYIME_RENDER_OUT`，默认为 `app/build/lantype-test-renders`；需要保留发行图像时可显式设置输出路径。默认选择集包含本批 Whisper 语言切换、录音会话、遗留目录迁移和工具舱剪贴板隐私回归。也可以传入类名，只运行与改动相关的测试。`scripts/test-runtime.init.gradle` 从 Maven 解析同版本 Mockito agent，在测试 JVM 启动时使用 premain；这是为不允许动态 self-attach 的环境提供支持，不替换 Mockito 实现、不关闭断言。代理参数只传给开发测试 JVM。

Robolectric 的 Compose 图像、真实 Android `EditText`/`InputConnection` 测试与资源访问测试分别验证不同层面，不能代替 ARM64 手机的输入法启用、首次部署、16 KB 系统运行及语音/手写/OCR体验验收。截图采集不完整的诊断图不用于对外展示。

## 签名、APK 核对与源码打包

发行私钥不在 Git 或公开附件中。开发者可构建 unsigned APK，再用自己的密钥签名；安装官方升级包必须保持原签名。正式签名前执行 `zipalign -P 16`，签名开启 v1/v2/v3，随后 `apksigner verify --verbose --print-certs` 验证。

最终应从已签名 APK 读取包名、版本、SDK、权限、可调试标志、备份标志、ABI、全部原生 ELF LOAD 段对齐、ZIP 对齐和证书指纹。无设备时如实记录 `adb devices` 为空，不能写已真机验收。

资源与公共源码检查：

```sh
python3 scripts/verify-commercial-resources.py --apk /path/to/final.apk --json /path/to/final-apk-assets.json
python3 scripts/check-public-source.py
python3 scripts/verify-commercial-resources.py --git-index
```

`--apk` 流式扫描 ZIP 全部条目并拒绝旧资源内容哈希，普通资源精确比对白名单；生成资产只允许明确路径、源文件精确内容或限定二进制格式。内置 clipboard 插件必须只含与公开源码相符的 `manifest.yaml` 和 `main.lua`，历史市场 `.xipk` 不进入 APK。

校验回执的 `checkedAgainstSourceVersion` 表示校验使用的源码版本，不是从受检 APK 或 ZIP 中读出的版本。实际 APK 的 `versionName`/`versionCode` 仍须从其 Android manifest 单独核对，避免把沿用的旧附件误标成新包。

源代码先经人工审阅并加入 Git 跟踪清单，再打包：

```sh
python3 scripts/package-source.py \
  --source-output /path/to/LanType-1.1.1-source-release.zip \
  --source-only
python3 scripts/verify-commercial-resources.py --source-zip /path/to/LanType-1.1.1-source-release.zip
python3 scripts/verify-commercial-resources.py --source-zip /path/to/LanType-1.1.0-runtime-dependencies.zip
```

`--source-only` 本批只产出新应用源码 ZIP，仍核对本地资源和原生输入；依赖大文件应先按本说明准备。Release 清单同时列出上节四个复用附件的固定链接、大小与原 SHA-256，不重复生成约 1 GB 的基础原生源码附件。新应用源码、复用依赖及后续 Dawn/WebGPU 补充来源应作为一套材料提供；冻结的已发布源码 ZIP 不重打，补正以新附件和说明提供。

每个新附件有 SHA-256/大小回执。应用源码 ZIP 使用经审阅的 `git ls-files`；复用的 runtime ZIP 按资源和 native 锁生成，native ZIP 按源档锁生成。它们都不会递归打包整个工作区。只有运行资源或原生源档锁发生变化时，才需要另行生成并校验相应新附件。

## CI 的范围

`.github/workflows/offline-ci.yml` 将 Actions 固定到核对过的提交，只有 `contents: read` 权限。它准备已批准资源、构建 unsigned offline APK、运行定向测试并保存图像/报告，不接收发行私钥、不自动发布。旧 CyIME 的发布、同步和夜间工作流不会在新仓库启用。

固定输入和完整源码提高可重建性，但本版没有宣称独立机器得到逐字节相同 APK。公开源仓库、配套附件、实际构建记录与后续真机验收状态应同时维护。
