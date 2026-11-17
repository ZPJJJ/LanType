# 受空间预算约束的 ORT ARM64 构建

`scripts/build-ort-native.py` 是独立的原生候选库构建入口。它固定 ONNX Runtime 1.28.0，保留 CPU、NNAPI、XNNPACK 和静态纳入主库的 WebGPU/Dawn，使用 ARM64、Android API 28、Release 与 LTO。构建产物进入独立目录，随后由 ABI 校验和普通 Android 功能验证决定能否用于应用集成。

这个入口不会构建 Java/AAR、测试库或其他 ABI，不会签名、安装、修改 APK 或发布 Release。没有原生内存错误复现实验，也没有运行 host 模拟程序的路径。编译通过或静态 ABI 通过不能代替 Android 首启、模型推理、输入法功能及真机验收。

## 固定输入与工具

| 输入 | 固定值或依据 |
|---|---|
| ORT | `da9b5e364c465de65c49d91e696cd6485270757f`，`VERSION_NUMBER=1.28.0` |
| C API | `ORT_API_VERSION=28`，ELF 符号版本 `VERS_1.28.0` |
| Dawn | `ec7b457e5bb1fcec6f59733c4f3dd84d2f885a38` |
| cpuinfo | `4628dc060ce4e82345dc166bbac875609db4ff69` |
| 生产补丁 | `patches/onnxruntime/cpuinfo-4628dc0-pr457-l2-backport.patch` |
| 补丁 SHA-256 | `6281246ef5bafdae6f64a9b1c4bbd64ddcd6b0b65a8150c9bd0343e3cfdf998b` |
| cpuinfo 原始 `src/arm/linux/init.c` | `daaf6633d55c983e9b517d748d1fdf3df580c6c8bef03e4fd3811ba47f175e4f` |
| 应用生产补丁后的同一文件 | `94a7bd19139090a0568e173f80dea5e42ea1326d04e3eddf46554f5243e5229c` |
| 选定 NDK | runner 预装 `29.0.14206865` |
| CMake | runner 预装 `3.31.6`；ORT 源码要求至少 3.28 |
| C/C++ 标准 | C99 / C++20 |
| protobuf / protoc | 直接 FetchContent 构建路径中的 21.12 |
| 宿主平台 | Linux x86_64；Python 3.11 或以上；预装 Ninja、GNU patch |

**NDK 29 是 LanType 为利用现有 runner 工具、避免新增整套 NDK 下载而选定的工具链。**固定 ORT 提交的官方 Android CI 使用 `28.0.13004108`。本方案不声称复制了供应商的完整构建参数，也不声称新库与旧库逐字节相同。工具的实际版本、编译器与链接器摘要写入回执；环境工具改变时不能复用旧工作根。

输入依据为 `docs/licensing/native-sources.lock.json`、`dawn-source-plan.json`、`native-sources-webgpu.lock.json` 和 `dawn-source-publication.json`。历史 Dawn collection lock 中保存的是当时的基础锁摘要；后来的基础锁元数据增加可能使整体摘要变化。构建器保留两份摘要，并逐项检查复用源档、当前 SHA-256 以及固定 ORT `deps.txt` 中活动依赖的 URL/SHA-1；不重写历史回执。

### 活动依赖与补丁

普通 Android full/native-only 分支使用 16 个基础依赖：`abseil_cpp`、`re2`、`protobuf`、`date`、`mp11`、`json`、`pytorch_cpuinfo`、`microsoft_gsl`、`safeint`、`flatbuffers`、`onnx`、`eigen`、`fxdiv`、`pthreadpool`、`kleidiai`、`googlexnnpack`。归档由现有源锁取得并校验，CMake 使用同一工作根内的本地镜像；镜像用硬链接复用已经验证的归档，不原地改写它们。

cpuinfo 使用单独工作副本，经 SHA-256 校验后应用唯一的生产补丁，并通过 `FETCHCONTENT_SOURCE_DIR_PYTORCH_CPUINFO` 选中。实际编译输入必须指向此副本，且 `init.c` 必须匹配上表中的补丁后摘要。Android 分支不应用 ORT 的 Linux-only cpuinfo sysfs 补丁。

Dawn 的七份源档从已发布的独立补充 ZIP 取得。先校验整个 ZIP，再校验七份内部归档。唯一下载的外层 ZIP 在内部归档全部验证成功后移除，回执保留其摘要；七份原始归档继续保留。调用者提供的外部 ZIP 始终只读。Dawn 的 `test/` 不展开，这与固定 ORT 默认配置应用补丁后删除该目录的行为对应；源码归档本身保持完整。

`onnxruntime_CUSTOM_DAWN_SRC_PATH` 会跳过 ORT 默认的自动补丁分支，因此构建器按照锁中的 `applyOrder`，对独立 Dawn 树应用七个固定 ORT 补丁，每份都先核对大小/摘要依据中的 SHA-256。Dawn 使用锁定的 SPIRV-Headers、SPIRV-Tools、Vulkan-Headers、Vulkan-Utility-Libraries、Jinja2 和 MarkupSafe 路径，并复用 ORT 的 Abseil。Vulkan/SPIR-V writer 保持开启；其他依赖仍由固定 ORT CMake 应用其已有补丁。

首次云端准备 [run 44162919449](https://github.com/ZPJJJ/LanType/actions/runs/44162919449) 揭示了一个构建脚本差异：固定 Dawn 的上下文已变动，上游 GNU patch 默认允许的上下文容错不可省略。七个 Dawn 补丁现在显式使用上游默认的最大 `fuzz=2`，并逐步强校验实际目标文件的修改前后 SHA-256；补丁输出保留实际 fuzz 和行偏移。对固定源码的文件级检查确认七步均可应用。cpuinfo 补丁仍要求 `fuzz=0` 及原有前后 SHA-256。该检查只证明源码准备，不代表编译或 Android 运行通过。

## 空间控制

调用者必须提供独占的新文件系统挂载根，容量上限 **4608 MiB（4.5 GiB）**。普通目录、绑定到同一设备的目录、过大文件系统和非 Linux 环境会在执行阶段前被拒绝。脚本不会自行安装 NDK/CMake、挂载卷或清空未知目录。

全部新增下载、解包、构建、生成代码、命令日志、临时文件和明确使用的缓存进入该挂载根。`TMPDIR`、`TMP`、`TEMP`、XDG/pip/ccache 缓存均指向该根；不修改 `HOME`、`CODEX_HOME` 或原 SDK。仓库原有 `scripts/storage_guard.py` 前检继续执行，没有绕过开关。

卷内有两层控制：文件系统容量是硬限制；脚本每 250 ms 检查可用空间，在少于 **256 MiB** 余量或少于 4096 个可用 inode 时停止整个子进程组。下载按块检查，解包前还检查声明大小与分配估计。命令日志有 64 MiB 上限。收到终止信号或命令超时也会终止构建进程组。

本任务另外预留 **512 MiB** 给 checkout、工作流及传输证据。卷外由 workflow 的检查点计量和断言控制，并非文件系统硬配额；回执明确标记 `wholeTaskFiveGiBHardEnforced=false`。不得把卷内 4.5 GiB 硬限制说成整个任务 5 GiB 的绝对硬配额。实际峰值、停止原因与未完成范围以运行回执为准。

完整 ORT+Dawn 编译是否能在这个额度内完成尚需实测。低并发、单 ABI、单 Release 目录和单库目标减少非必要产物，不能证明剩余空间一定够链接。达到停止线时不自动移除 provider、算子或 LTO，也不静默扩容。

## 四个阶段

公共参数示例：

```bash
ort_common=(
  --work-root "$LANTYPE_ORT_WORK_ROOT"
  --sdk "$ANDROID_HOME"
  --ndk "$ANDROID_HOME/ndk/29.0.14206865"
  --cmake "$(command -v cmake)"
)

python3 scripts/build-ort-native.py --stage prepare --download "${ort_common[@]}"
python3 scripts/build-ort-native.py --stage configure "${ort_common[@]}"
python3 scripts/build-ort-native.py --stage build "${ort_common[@]}"
python3 scripts/build-ort-native.py --stage verify "${ort_common[@]}"
```

每个阶段要求前一阶段已经成功，不会隐式调用前置阶段。仅 `prepare --download` 允许构建器取得缺失的固定归档；可用 `--archive-dir` 提供现有基础源档目录，或用 `--dawn-supplement` 提供已有的补充 ZIP。后续配置通过本地镜像解析活动依赖，不准备任何未列出的可选组件。

| 阶段 | 行为与成功依据 |
|---|---|
| `prepare` | 校验源锁/归档、受限解包、应用已锁补丁，检查固定 protoc，生成已准备源文件清单 |
| `configure` | 运行固定 `build.py --update`，关闭测试/Java，检查 provider/CMake 参数及实际 compiler 输入计划，保存完整源树摘要 |
| `build` | 仅 `build.py --build --targets onnxruntime`，1 或 2 个任务；编译前后检查输入未变，保存产物和 Ninja 日志摘要 |
| `verify` | 再核对输入、生成配置与库摘要，检查 AArch64 和三个 `VERS_1.28.0` 导出；完整 consumer ABI 由独立工具检查 |

构建采用 `--use_nnapi --use_xnnpack --use_webgpu static_lib --enable_lto --build_shared_lib`；不启用 minimal build、算子裁剪或共享 WebGPU 插件适配层。`--skip_tests` 之外还显式设置 `onnxruntime_BUILD_UNIT_TESTS=OFF`。静态 C++ runtime 固定为 `c++_static`。

固定路径：

```text
<work-root>/src/runtime-onnxruntime
<work-root>/src/onnx-dependency-pytorch_cpuinfo
<work-root>/src/ort-dawn
<work-root>/build/Release/libonnxruntime.so
<work-root>/receipts/
<work-root>/logs/
```

`prepare.json`、`configure.json`、`build.json`、`verify.json` 表示各阶段实际结果；`state.json` 保存固定输入指纹、工具身份、归档、补丁和阶段检查点。错误写入 `failure.json`，此前成功的证据保留，失败阶段不会标成通过。早于工作根初始化的前置条件错误只输出明确错误信息。

`provider-compile-inputs.json` 保存 CPU、NNAPI、XNNPACK、WebGPU、Dawn、Tint 与补丁后 cpuinfo 的编译命令。源文件清单逐文件记录 SHA-256；CMakeCache、compile_commands、build.ninja、rules.ninja 和最终库均有摘要。编译命令表示配置选择的输入，不能单独证明设备支持某个 GPU provider。

成功阶段可重复运行，前提是输入、工具、脚本和工作根指纹一致。普通中断后的 `build` 可以使用保留的 Ninja 目录续编。若解包或下载中断留下尚未确认的 `.partial` 文件/源目录，脚本会保留并拒绝覆盖；先审阅失败证据，再由操作者显式处理该任务拥有的可再生副本，或使用新的独占卷。没有“自动清理整个目录”的选项。

## ABI 与普通运行验收

工作流随后调用：

```bash
python3 scripts/verify-ort-abi.py \
  --library "$LANTYPE_ORT_WORK_ROOT/build/Release/libonnxruntime.so" \
  --output "$LANTYPE_ORT_WORK_ROOT/receipts/abi.json"
```

完整门禁要核对旧库 SONAME/动态依赖、Rime/Java JNI 使用的版本化符号、ELF 16 KiB 对齐与现有 ABI 合同。XNNPACK 和 WebGPU 在这个固定版本的 `symbols.txt` 为空，不能把没有独立 C 导出误判成 provider 被移除。

静态验收后才进行单独的普通 Android 初始化、`GetApi(28)`/版本、可用 provider 及真实模型功能验证。无真实 ARM64/16 KiB 设备证据时照实标记。构建器的 `verify` 不执行设备程序，不自动用候选库覆盖已发布 APK。

## 入口验证与来源

轻量验证只使用小型合成 ZIP/tar、hash 与参数/预算检查：

```bash
python3 -B scripts/test-ort-native-build.py
```

根源文件均位于固定提交：

- [ORT Android full AAR 参数](https://github.com/microsoft/onnxruntime/blob/da9b5e364c465de65c49d91e696cd6485270757f/tools/ci_build/github/android/default_full_aar_build_settings.json)
- [ORT 分阶段 build.py](https://github.com/microsoft/onnxruntime/blob/da9b5e364c465de65c49d91e696cd6485270757f/tools/ci_build/build.py)
- [ORT external dependencies 与 Dawn patch 分支](https://github.com/microsoft/onnxruntime/blob/da9b5e364c465de65c49d91e696cd6485270757f/cmake/external/onnxruntime_external_deps.cmake)
- [ORT Android CI 的 NDK/CMake 基线](https://github.com/microsoft/onnxruntime/blob/da9b5e364c465de65c49d91e696cd6485270757f/.github/workflows/android.yml)
- [Dawn 固定 Android/Vulkan 配置](https://github.com/google/dawn/blob/ec7b457e5bb1fcec6f59733c4f3dd84d2f885a38/CMakeLists.txt)
- [已发布 Dawn 补充包](https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/LanType-native-source-webgpu-supplement-v1.zip)
