# LanType 1.1.2 构建、资源与对应源码（工作稿）

本文件描述 `1.1.2 / versionCode 4` 的构建与发行准备。**新 ORT 已取得一次普通 Android API 通过结果，组件 ZIP 与 accepted 锁已公开；当前没有本批已验收的 APK，不能据本文宣布应用首启问题已修好或稳定收费版已经可用。** 原生构建、API 检查、workflow 失败、组件发行身份及待完成的设备验收分别记录在 [1.1.2 验证工作稿](development/lantype-1.1.2-validation.md)。

已有 [1.1.1 变更记录](CHANGELOG-1.1.1.zh-CN.md)、[1.1.1 验证记录](validation-1.1.1/VALIDATION.md)、旧 APK、源码 ZIP、附件和标签保留原样。本批变更见 [1.1.2 变更工作稿](CHANGELOG-1.1.2.zh-CN.md)，旧测试结果不作为本批通过记录。

## 当前构建和验收状态

[原生构建 run 44164186969](https://github.com/ZPJJJ/LanType/actions/runs/44164186969) 已成功生成带 cpuinfo 生产补丁的 ARM64 ORT 候选。实际 `libonnxruntime.so` 为 **29,568,744 字节**，SHA-256：

```text
ae250081faa6cd742f6edade2a23bf29a96ba690fa19a01e3bd192548cf89f1e
```

静态 ABI 检查及 AAR 成员比较的身份和范围见 [ORT 1.28.0-r1 组件说明](licensing/ORT-RUNTIME-1.28.0-r1.md)。这些结果不等于 Android 正常初始化、模型推理或输入法功能通过。

[普通 API QA 第六次运行 44232550186](https://github.com/ZPJJJ/LanType/actions/runs/44232550186) 在 API 35 x86_64、ARM64 bridge、4 KiB 页大小的 guest 中，通过上述同一 ELF 的 `dlopen`、C API 28、四种 provider 枚举及 `CreateEnv` / 释放。`result.json` 为 `passed`，SHA-256 `097cd558327c1b6bac8a5bac1b097423f30b1f12d4ddbe8cbfe6a26389eac11e`；最后普通卸载工作卷因 `target is busy` 退出 32，因此 **整个 workflow 为 failure**。这份通过结果只覆盖 API 加载和环境生命周期。

[第七次运行 44235315243](https://github.com/ZPJJJ/LanType/actions/runs/44235315243) 在主机 ADB 进程登记阶段失败，未启动 guest，也未执行 probe；没有新增原生通过或失败结论。[修复提交 b5c46a43](https://github.com/ZPJJJ/LanType/commit/b5c46a43eeb48b574e067ff8a12316baea0fc938) 增加有界身份等待和具体诊断，区分已登记进程与无权读取的其他进程，尚未取得实际运行结果。

第五次运行的空间失败保留在验证记录中。[云端 QA 专用 16 GiB 预算](qa/ANDROID-QA-STORAGE-PROPOSAL.md) 已于 2026-11-18 获用户批准，并用于第六、七次运行；官方镜像准备及 guest 启动已在第六次实际完成。独立原生和 offline 整包构建仍受原 5 GiB 预算约束。新组件 ZIP 与 accepted 锁已作为固定构建输入公开；整包 CI、签名 APK 和产品设备验证仍待完成。

## 运行离线与开发联网

发行目标仍为中文及美式英文离线输入法。`offline` 变体不申请 `INTERNET` 权限；最终 APK 还须重新读取 manifest 核对。随包模型、词库和初始化数据由设备本地读取，运行时不依赖服务器或联网激活。

开发阶段取得 Gradle、Maven、Android SDK、固定源码和发行构建输入可以联网。`--download` 仅是开发准备命令的显式授权，不表示手机输入法需要联网。没有预先准备完整开发缓存时，不承诺整个编译过程也能断网完成。配置与权限入口见 [应用构建脚本](../app/build.gradle.kts) 和 [offline manifest](../app/src/offline/AndroidManifest.xml)。

## 版本与工具链

| 项目 | 本批配置 |
|---|---|
| 应用 ID | `app.lantype.keyboard` |
| versionName / versionCode | `1.1.2` / `4` |
| ABI / 最低 Android | `arm64-v8a` / API 28 |
| compileSdk / targetSdk / Build Tools | `36` / `36` / `36.0.0` |
| JDK / Python | 21 / 3.12 |
| Gradle / Android Gradle Plugin | 9.5.0 / 9.1.0 |
| 默认预编译模式与可选 Rime/JNI 源码模式的 NDK | 两种模式都固定 `29.0.14206865` |
| 可选 Rime/JNI 源码构建的 CMake | `3.22.1` |
| 独立 ORT 原生构建 | NDK `29.0.14206865`、CMake `3.31.6`、ARM64/API 28 |
| 发行变体 | `offline`，保留 R8 |

应用 Java/Kotlin、Compose、插件宿主和资源从当前源码重新编译，不复用上游 DEX。默认模式使用锁定原生输入；本批默认 APK 的合同是 **恰好 12 个原生库，仅主 ORT 换成 accepted 锁中的新 ELF，其余 11 个库逐文件保持旧版身份**。源码 namespace 保留 JNI 所需的 `com.kingzcheung.xime`；应用 ID、品牌和官方签名由 LanType 管理。

上述配置以 [app/build.gradle.kts](../app/build.gradle.kts)、[版本目录](../gradle/libs.versions.toml) 和 [ORT 构建器](../scripts/build-ort-native.py) 为准。独立重建旧 CameraX 组件仍有其历史 NDK 27.2/CMake 3.22.1 合同；默认整包流程直接校验已发布的两份 CameraX 输出，不重新下载旧工具链。

## 发行材料的组合

本批应提供以下互相可追溯的材料；尚未发布的项目不填写臆造的 URL、大小或摘要。

| 材料 | 当前用途和状态 |
|---|---|
| 本批应用源码 | 计划交付 `LanType-1.1.2-source-release.zip`；尚待最终源码清单和实际打包回执 |
| 已公开 `LanType-1.1.0-runtime-dependencies.zip` | 只恢复当前合同继续复用的 **399 个旧输入**，不覆盖新源码或控制文件 |
| 新 ORT component ZIP | 已在 [ort-runtime-1.28.0-r1](https://github.com/ZPJJJ/LanType/releases/tag/ort-runtime-1.28.0-r1) 预发布；[accepted 锁](licensing/ort-runtime.lock.json) 固定外层 ZIP、三输出和有限范围的验收引用 |
| 三份基础原生源码 ZIP | 已公开，共 70 份固定源档，分别解压；需要与 Dawn 补充、项目补丁和当前构建器一起提供 |
| Dawn/WebGPU 源码补充 ZIP | 已公开，补充 7 份源档及原始通知；见 [来源补充说明](licensing/DAWN-SOURCE-SUPPLEMENT.md) |
| 本批 Git 内 17 份新增通知 | NDK 29 三份、Dawn 原始许可/通知 13 份、项目补丁归属一份；已在提交 `1e7daacdaeac91983a436e1a2614ede02f725125` 公开，396 assets / 11 raw 检查通过；最终新 APK 随包核验仍待构建 |

基础 ZIP 的 399 项为 **379 个 assets、11 个 raw 资源、7 个旧 vendor 输入（6 个原生库及 Sherpa Java JAR）、2 个 CameraX 原生库**。本批新增 17 份通知由 Git 提供，不存在于旧 ZIP；最终资源合同对应 396 个 assets 与 11 个 raw 资源。旧 379 项的内容身份保留，新通知的路径和摘要另行进入当前资源锁。

[restore-base-runtime.py](../scripts/restore-base-runtime.py) 只恢复旧集合并校验当前合同；旧 ZIP 内的根 LICENSE、清单及三份旧锁不覆盖本批文件。不要将旧 runtime 根目录整体复制到新源码目录。新增通知也不能靠重新恢复旧 ZIP 补齐。

### 已公开附件的固定身份

| 附件 | 字节数 | SHA-256 |
|---|---:|---|
| [旧运行输入 ZIP](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-runtime-dependencies.zip) | 139,297,354 | `42a0e57c002662e2a502719a7f002b061fd49605d92a87cab221bf6d9aa922bc` |
| [基础源码 1 / 3](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-1-of-3.zip) | 339,827,618 | `00223f5255a7b6b1d9f32ea52402fd2693cc879c530e59a60d8e80fa11882b57` |
| [基础源码 2 / 3](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-2-of-3.zip) | 339,828,069 | `1ef3f166b8992957e5518b451de50def7db42d1443a1dc32811c3a7fc46c9eec` |
| [基础源码 3 / 3](https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-native-source-part-3-of-3.zip) | 339,828,348 | `7f3b2a772532ba5ff65086efd289ac214577d498974d2253a6e4078547b8b4f7` |
| [Dawn/WebGPU 补充](https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/LanType-native-source-webgpu-supplement-v1.zip) | 105,554,498 | `6eabae67a60bdb0f3eaab9858f58b1f712edb9f85bb4c5cf75d800e7f530691d` |
| [ORT 1.28.0-r1 运行组件](https://github.com/ZPJJJ/LanType/releases/download/ort-runtime-1.28.0-r1/LanType-ORT-1.28.0-r1-runtime.zip) | 97,731,603 | `e03422b48b8a36f7a83cc8a458ec7c97c744d34139f219ee95cb28093e2d9d09` |

公开身份与来源范围见 [Dawn 发布回执](licensing/dawn-source-publication.json)、[ORT 发布回执](licensing/ort-runtime-r1-publication.json)及 [ORT 组件说明](licensing/ORT-RUNTIME-1.28.0-r1.md)。ORT release ID 为 `449527123`，公开时间为 `2026-11-18T04:33:36Z`，`prerelease: true`、`draft: false`；运行 ZIP 的 asset ID 为 `761904810`。仓库 accepted 锁与公开附件为同一份 2,313 字节文件，SHA-256 `e751086cb82c90bb631bfdebf45f78e2f7462fcccf52373ca9141f45f0bf207b`。组件的接受范围不包括应用整包、模型推理或实体设备验收。

## 默认整包构建

准备 Linux、JDK 21、Python 3.12、SDK Platform 36、Build Tools 36.0.0 和 NDK 29.0.14206865。`JAVA_HOME`、`ANDROID_HOME` 指向真实工具目录；本机 SDK 路径、代理、发行私钥和口令不得提交。

在当前源码根目录先恢复旧输入，并为回执选择一个尚不存在的文件：

```bash
mkdir -p app/build/reports/lantype-native
python3 scripts/restore-base-runtime.py --download \
  --receipt app/build/reports/lantype-native/base-restoration.json
python3 scripts/prepare-upstream.py --verify-only
python3 scripts/build-camerax-native.py --verify-only
python3 scripts/verify-commercial-resources.py
```

已有已校验旧 ZIP 时，把第一条恢复命令的 `--download` 改为 `--archive /absolute/path/LanType-1.1.0-runtime-dependencies.zip`。已有全部本地输入时，可单独执行 `restore-base-runtime.py --verify-only`。当前 Git 提供的新增通知也必须存在，资源检查通过后才能进入打包。

以下命令读取仓库已登记的 accepted 锁，从固定公开附件恢复 ORT；锁中的准备阶段状态字段保留历史原义，实际公开身份由上述发布回执记录。恢复器仍要求精确大小和摘要，不选择 latest。

```bash
python3 scripts/restore-ort-runtime.py --download \
  > app/build/reports/lantype-native/ort-restoration.json
python3 scripts/prepare-ort-runtime.py \
  --accepted-lock docs/licensing/ort-runtime.lock.json --verify-only
./gradlew :app:assembleOffline --no-daemon --max-workers=1 \
  -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx4096m -Dfile.encoding=UTF-8'
```

[ORT 恢复器](../scripts/restore-ort-runtime.py) 只按外部 accepted 锁恢复三份输出：full AAR、companion AAR 和 ARM64 主 ELF。full AAR 保留官方 Java classes 与 JNI bridge；companion 仅省去主 ELF，供已经从 CMake 输入主库的源码模式使用。替换和逐成员比较规则见 [prepare-ort-runtime.py](../scripts/prepare-ort-runtime.py)，不是修改 AAR 文件名后就视为验证通过。

默认构建的 `preBuild` 继续核验资源、旧原生输入、CameraX 和 accepted ORT。构建逻辑只同步批准的 JNI 文件；即使 vendor 中残留其他旧库也不能成为获准输入。依赖版本和 Maven 内容校验表保持固定，CI 不自动放宽校验。

## 对应源码与独立 ORT 构建

对应来源材料由 **本批应用源码和构建器、三份基础源码 ZIP、Dawn 补充、cpuinfo 生产补丁、实际 NDK 29 来源与通知记录**共同构成。只提供三份旧基础源码包不包含已知 Dawn 嵌套来源；只提供新 ELF 或补丁也不构成完整来源说明。

三个基础 ZIP 是独立包，分别解压到同一外部归档目录，不能用 `cat` 拼接，也不能用其中的历史锁覆盖当前源码锁：

```bash
unzip -n LanType-1.1.0-native-source-part-1-of-3.zip -d native-source
unzip -n LanType-1.1.0-native-source-part-2-of-3.zip -d native-source
unzip -n LanType-1.1.0-native-source-part-3-of-3.zip -d native-source
python3 scripts/restore-native-sources.py \
  --archive-dir /absolute/path/native-source/archives --all --verify-only
python3 scripts/collect-dawn-source-supplement.py \
  --verify /absolute/path/LanType-native-source-webgpu-supplement-v1.zip \
  --expected-zip-sha256 6eabae67a60bdb0f3eaab9858f58b1f712edb9f85bb4c5cf75d800e7f530691d
```

验证全部归档与展开全部源码是不同操作。按实际任务分阶段准备，遵守空间门禁和同一时刻只运行一个重型任务；不要在同一受限 ORT 卷内额外展开全部 70 份来源。构建器只选用本次所需的固定集合。

[build-ort-native.py](../scripts/build-ort-native.py) 和 [原生 workflow](../.github/workflows/native-ort-build.yml) 是本次 ORT 的生产构建入口。固定 ORT 提交 `da9b5e364c465de65c49d91e696cd6485270757f`，在 cpuinfo `4628dc060ce4e82345dc166bbac875609db4ff69` 上应用 [项目生产补丁](../patches/onnxruntime/cpuinfo-4628dc0-pr457-l2-backport.patch)，并按顺序应用固定 ORT 已有的七个 Dawn 补丁。输入、补丁前后文件、工具链和输出身份均进入回执；补丁归属与具体变更见组件说明。

以下示例要求 `ORT_WORK_ROOT` 已是**空的、独占、实际挂载且容量不超过 4608 MiB** 的工作文件系统；其余变量指向预装工具和已核验归档。构建器会拒绝普通未挂载目录、错误版本或不足的空间。`--download` 只用于 prepare；即使基础源档已在本地，首次准备仍需要取得固定的宿主 protoc 工具。

```bash
python3 scripts/build-ort-native.py --stage prepare \
  --work-root "$ORT_WORK_ROOT" --sdk "$ANDROID_HOME" \
  --ndk "$ANDROID_HOME/ndk/29.0.14206865" --cmake "$ORT_CMAKE_BIN" \
  --archive-dir "$NATIVE_SOURCE_ARCHIVES" --dawn-supplement "$DAWN_SUPPLEMENT_ZIP" \
  --download
for stage in configure build verify; do
  python3 scripts/build-ort-native.py --stage "$stage" \
    --work-root "$ORT_WORK_ROOT" --sdk "$ANDROID_HOME" \
    --ndk "$ANDROID_HOME/ndk/29.0.14206865" --cmake "$ORT_CMAKE_BIN"
done
```

输出是 `build/Release/libonnxruntime.so`，实际来源与命令分别在工作卷 `receipts/`、`logs/` 和 `src/` 中。该入口构建原生候选，**不会自行接受新库、改写运行锁、集成应用或签名发布**。原始候选 manifest 保留当时的未接受标记；第六次普通 Android API 通过另以实际回执登记，应用层验证仍待完成。

### 可选 Rime/JNI 源码模式

在基础输入和 accepted ORT 已准备完成后，当前 [prepare-native-build.py](../scripts/prepare-native-build.py) 从该 accepted 组件取得精确 ORT 主库并准备固定头文件；不再另取一份未替换的官方主库。

```bash
python3 scripts/restore-native-sources.py \
  --archive-dir /absolute/path/native-source/archives
python3 scripts/prepare-native-build.py
./gradlew :app:assembleOffline -Plantype.nativeFromSource=true \
  --no-daemon --max-workers=1 -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx4096m -Dfile.encoding=UTF-8'
```

该模式重建 Rime/JNI 包装层，仍复用锁定的 Sherpa 等输入；独立 ORT 重建使用上节入口。**Sherpa JNI 内静态链接的另一份 ORT 没有在本批替换或重编。** 切换 `nativeFromSource` 不能表述为一次重编全部第三方库。自行重编 Rime 会产生自己的 ELF 身份，需要独立记录；本批默认发行 APK 的“其他 11 库不变”门禁不等于接纳任意源码重编结果。

基础源码中的旧 LLVM 来源条目针对旧 `libc++_shared.so`，不能用来证明 NDK 29 静态 C++ 输入的精确来源。新 NDK 的实际静态 archive 摘要、随包通知和来源边界见 [ORT 组件说明](licensing/ORT-RUNTIME-1.28.0-r1.md)。原供应商完整参数及所有旧库的逐字节复现仍未建立。

## 资源、许可与来源范围

逐文件资源网址、修订、许可、变换、大小和 SHA-256 由 [resources.lock.json](licensing/resources.lock.json) 管理，拒绝的旧资源身份在 [excluded-resources.json](licensing/excluded-resources.json)。本批原有中文/美式英文词库、手写、Whisper、OCR 与 VAD 输入延续既有合同，新增的是上述通知；不重新引入已排除的旧模型和语料。

应用采用既定 GPL 源码发行方案；第三方组件、字体、数据和模型保留各自条款。Sherpa 的静态依赖包含 eSpeak NG，不能将整个 Sherpa JNI 简称为 Apache-only。ORT、cpuinfo、Dawn 和 NDK 通知不能用一份顶层 GPL 替换。具体原文、作者和来源以应用随包许可、来源锁及组件说明为准。

17 份新增通知位于 Git，并由本批资源校验覆盖。旧 ZIP 只能恢复其原有内容；当前源码中的许可文本、补丁归属和锁文件必须作为新版本材料一并提供。来源补齐、编译成功和静态对齐均不能替代运行验收。

## 测试、最终 APK 与签名

保留现有完整定向测试和 Compose 渲染入口：

```bash
bash scripts/test-targeted.sh
```

`CYIME_RENDER_OUT` 默认指向 `app/build/lantype-test-renders`。本批通过数、失败数和实际图像须从新运行的 XML、日志和 PNG 登记；1.1.1 的 187 个通过用例不能直接复用为 1.1.2 的结果。

默认预编译 APK 的最终内容检查：

```bash
python3 scripts/prepare-ort-runtime.py \
  --accepted-lock docs/licensing/ort-runtime.lock.json \
  --verify-apk /absolute/path/final.apk --receipt /absolute/path/final.apk.native.json
python3 scripts/build-camerax-native.py --verify-apk /absolute/path/final.apk
python3 scripts/verify-commercial-resources.py \
  --apk /absolute/path/final.apk --json /absolute/path/final.apk.assets.json
```

首项强制恰好 12 个 ELF、新主 ORT 精确身份及其余 11 库不变；CameraX 与资源继续独立核验。签名后还须读取真实包名、版本、权限、ABI、调试/备份标志、ZIP 与 ELF 对齐和证书指纹。`checkedAgainstSourceVersion` 只是检查器的源码版本，不能代替 APK manifest 中的版本。

发行私钥不进入 Git、公开附件或 unsigned CI。官方升级包须保持原签名；源码使用者可用自己的签名。新签名 APK 尚未形成实际身份回执，不在本文填写预期大小或假 SHA。

产品验证按 [设备 workflow](../.github/workflows/android-device-qa.yml) 的显式候选锁分别记录：fresh candidate 的实际功能与同一候选重装数据保留，以及安装未初始化的固定旧 1.1.1 后直接 `install -r` 替换。后者没有已初始化旧用户数据，不能记作旧用户数据迁移通过。真实 ARM64 手机与 16 KiB 系统验收仍待完成。

## 源码打包和 CI 的边界

最终输入准备齐全、Git 清单审阅完成后，才生成新应用源码 ZIP：

```bash
python3 scripts/check-public-source.py
python3 scripts/verify-commercial-resources.py --git-index
python3 scripts/package-source.py \
  --source-output /absolute/path/LanType-1.1.2-source-release.zip --source-only
python3 scripts/verify-commercial-resources.py \
  --source-zip /absolute/path/LanType-1.1.2-source-release.zip
```

`--source-only` 仍核验本地运行输入和 accepted ORT。源码 ZIP 使用经审阅的 Git 文件清单；发行清单同时链接旧基础运行 ZIP、三份基础源码 ZIP、Dawn 补充和已公开 ORT component ZIP。旧基础 ZIP 本来没有新增 17 份通知，不能把它单独当作一套完整 1.1.2 运行材料。本批应用 APK、源码 ZIP 及其附件的实际大小、SHA、公开资产身份与源码提交仍须在真实打包和发布后登记；冻结的旧附件不重写。

[offline-ci.yml](../.github/workflows/offline-ci.yml) 只有 `contents: read`，构建 unsigned APK，不接收正式签名材料或发布 Release。它复制含 `.git` 的源码到 4608 MiB 工作卷，重用预装 JDK/SDK/NDK，将 Gradle、Java 缓存和所有新增构建文件放入卷内；以 256 MiB 空间保留量和命令超时停止自己的进程组。卷外 512 MiB 使用分配块计量检查点，**不是整个 job 的连续硬配额**。实际 stdout/stderr、观测峰值、APK、测试与图像先上传，成功后才清理自有卷。

完整来源和固定输入提高可重建性；本批仍未宣称独立机器能生成逐字节相同 APK。商业发行继续遵循 [商用方案](COMMERCIAL-PLAN.zh-CN.md)，目前保留免费预发布/开发候选状态；新包功能、真实 ARM64 与 16 KiB 验收以及对应来源和渠道准备完成前，不宣布稳定收费首发。
