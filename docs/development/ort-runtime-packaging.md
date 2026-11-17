# ORT 运行组件的准备与恢复

这组工具把经过独立原生构建和 Android API 检查的 ARM64 ORT 库接入现有 Java/JNI 绑定。工具本身不创建验收结论、不执行原生程序、不修改输入锁。生产接受锁必须在真实二进制及其验证结果出现后，由发行者审阅并提交。

## 两种 AAR 的内容关系

输入是固定官方 `onnxruntime-android:1.28.0` AAR，45,634,470 字节，SHA-256 为 `f351a0638696f54b35184290dbc001d66daae17281ad0b548d2c70347d53b8a9`。

| 输出 | 相对官方 AAR 的成员内容变化 | 用途 |
|---|---|---|
| `onnxruntime-android-1.28.0-lantype-r1.aar` | 仅替换 `jni/arm64-v8a/libonnxruntime.so` | 默认预编译 JNI 的发行构建 |
| `onnxruntime-android-1.28.0-lantype-r1-cmake.aar` | 移除同一个 ARM64 ORT 主库成员 | Rime 源码重编模式；主库由 CMake 的 IMPORTED 目标提供 |
| `arm64-v8a/libonnxruntime.so` | 与新主库逐字节相同 | 源码模式链接输入和独立核验 |

官方 AAR 的其他 39 个成员保持内容相同，包括 `classes.jar`、ARM64 Java JNI 桥、manifest、headers 和许可。输出统一排序、时间与权限，采用 ZIP_STORED，避免重打包字节依赖 zlib 版本。此归档策略不改变最终 APK 的压缩策略。

## 明确区分候选锁与接受锁

`scripts/prepare-ort-runtime.py` 必须显式选择 `--candidate-lock` 或 `--accepted-lock`。两种锁共有 `schemaVersion: 1`、`kind: lantype-ort-runtime-lock`、`ortVersion: 1.28.0`、`abi: arm64-v8a`、固定 `originalAar` 身份和实际新 `library` 身份；身份格式为 `bytes` 与 `sha256`。`status` 分别为 `candidate` 或 `accepted`。

候选锁允许准备和逐成员比较。接受锁还必须固定 `outputs.fullAar`、`outputs.companionAar`、`outputs.library`，并提供实际静态 ABI 与 Android API 结果的哈希引用：`acceptanceEvidence.staticAbiReceiptSha256`、`acceptanceEvidence.androidApiReceiptSha256`。工具只核对这些引用的格式，不把引用本身当作设备测试执行；发行者仍须独立审阅实际回执。

准备时使用新的输出目录，已有内容不会被覆盖：

```bash
python3 scripts/prepare-ort-runtime.py \
  --candidate-lock /path/to/reviewed-candidate-lock.json \
  --aar /path/to/onnxruntime-android-1.28.0.aar \
  --library /path/to/new/libonnxruntime.so \
  --output-dir /path/to/new-runtime-directory
```

`preparation-receipt.json` 保存三份输出的实际身份及逐成员未变证明。只有审阅真实构建、ABI 和 Android API 结果后，才把这些实际值写入接受锁；普通准备或校验命令不自动更新它。

## 从长期发行附件恢复

接受锁的发行路径为 `docs/licensing/ort-runtime.lock.json`，三份本地输入为 `vendor/ort-runtime/`。锁中额外的 `distribution` 包含实际公开组件 ZIP 的 `archiveUrl`、`archive` 身份和单层 `root`。ZIP 内的三个固定输出位于该根目录下；允许附带 README、许可和证据，但恢复器只提取三个运行输入。

```bash
# 已有正确输出或已缓存的锁定 ZIP：不联网。
python3 scripts/restore-ort-runtime.py

# 使用本地发行运行包：不联网。
python3 scripts/restore-ort-runtime.py --archive /path/to/locked-runtime.zip

# 显式允许开发期下载；下载地址及内容仍须匹配接受锁。
python3 scripts/restore-ort-runtime.py --download

# 校验已恢复的三输出，不需要再次取得原始官方 AAR。
python3 scripts/prepare-ort-runtime.py \
  --accepted-lock docs/licensing/ort-runtime.lock.json --verify-only
```

恢复器先核对外 ZIP 的大小和哈希，再检查所有成员的路径、重复项及类型，在新暂存目录验证三输出后才原子改名。已有错误输出会保留并报错。下载缓存以哈希命名；不会把临时 Actions artifact 当成长期构建依赖。下载仅发生在这些开发脚本中，与 Android 应用的运行权限无关。

普通运行在预计下载或恢复占用之外保留 5 GiB 空闲空间。受限 CI 可显式传入 `--bounded-work-root <挂载点>`：该目录必须是独立、实际容量不超过 4.5 GiB 的已挂载文件系统，源码、缓存、输出及显式本地输入 ZIP 均须位于其中，且不能通过符号链接或子挂载逃出。只有满足这份契约时，恢复器才改为保留 256 MiB。CI 另行监控整条构建进程及卷外开销；这个参数不扩大工作卷，也不允许在普通目录中跳过空间门禁。

## 最终边界检查

源码模式使用 `--verify-native-input <ELF>` 检查实际 CMake 链接输入；默认发行模式使用：

```bash
python3 scripts/prepare-ort-runtime.py \
  --accepted-lock docs/licensing/ort-runtime.lock.json \
  --verify-apk /path/to/unsigned-or-signed.apk \
  --receipt /path/to/new-apk-native-receipt.json
```

此门禁要求最终 APK 恰含基线中的 12 个 ARM64 原生库：新 ORT 匹配接受锁，其余 11 个匹配已发布 1.1.1 的实际字节。这条整包字节基线只适用于默认预编译管线；源码模式会重编其他 JNI 库，需要独立核验其输出。

资源清单、manifest 的离线权限、签名、APK 对齐，以及产品启动、模型和中文/英文输入由各自入口继续检查。轻量归档回归使用 `python3 scripts/test-ort-runtime.py`，不替代这些验收。
