# LanType 1.1.0：Gitiles 源码归档 CI 修复

本补丁基于原始发行源码 `8c69112fa83b51e75b41bda17bd51a907338efa0`。GitHub 首次完整源码提交 `f7735fd4c0d5a158fe32423e6d620956bc57dc30` 与该本地提交的源码树相同，因此也可直接应用。补丁只修改构建准备、源码内容锁、回归与 CI 证据采集，不修改应用产品源码或已签名 APK。

## 原因与修复范围

[GitHub run 44012376086](https://github.com/ZPJJJ/LanType/actions/runs/44012376086) 在准备 CameraX 源码时报告整档 SHA 不匹配，尚未开始 Gradle 构建和测试。官方 Gitiles `+archive` 每次请求会重新生成 tar/PAX `mtime`；同一固定 commit 的文件字节相同，归档字节仍会变化。

`native-sources.lock.json` 仅为 6 个明确的 `https://android.googlesource.com/.../+archive/<40 位固定提交>` 条目增加 `gitiles_content` 指纹。这些指纹全部从本次已审核、与原锁 SHA 完全匹配的发行原档生成。原有 70 个 `archive_sha256` 均保留，原生源码附件仍能按原 SHA 验证。

新校验先尝试原始整档 SHA；只有上述明确批准的 Gitiles 条目才允许成员身份校验。身份包括精确路径集合、类型、mode、uid/gid、属主名称、链接目标、大小、设备号、全部非 mtime 的成员/全局 PAX 字段，以及每个普通文件的 SHA-256。仅排除修改时间；重复路径、特殊或稀疏文件拒绝。未知 URL、浮动提交、未批准格式及其他来源的下载仍使用原整档 SHA 规则。

CI 新增这套校验器的回归步骤。Compose 截图改写入 `app/build/lantype-ci-renders`，避免准备失败时把 Git 已保存的旧截图上传成新运行证据。

## 实际验证

- 6 份已审核原档均按原整档 SHA 通过；6 份现今重新下载的漂移档均按固定成员指纹通过。
- 12 项回归通过，覆盖源码同长度篡改、增删/重命名/重复路径、类型/权限/属主、符号与硬链接、非 mtime PAX、错误来源和格式、缓存及坏归档。
- 对真实 CameraX 归档另做 5 项修改：源码字节改变、增加/删除/重命名路径、mode 改变，均被拒绝。
- 记录见 [ci-source-verification.json](ci-source-verification.json) 与 [ci-source-unit-tests.txt](ci-source-unit-tests.txt)。本记录只说明本地修复验证；未将尚未重跑的远端 CI 宣称为成功。

## 使用

完整的 `LanType-1.1.0-source-with-ci-fix.zip` 提供已应用补丁的源码。原始 `LanType-1.1.0-source.zip` 和其余已校验发行附件保持不变；需要保留原始源码快照时，可在该快照根目录执行：

```bash
git apply --check /path/to/LanType-1.1.0-ci-source-fix.patch
git apply /path/to/LanType-1.1.0-ci-source-fix.patch
python3 scripts/test-native-source-verification.py
python3 scripts/build-camerax-native.py --download
```

最后一条仅在需要从源码准备 CameraX 时运行，已有批准运行依赖可直接验证复用。签名 APK 仍为 `03e379a9b77fbddba9886e28bfa9fc78e447dc4843917117faf625b4339d18c6`，没有重新编译或重新签名。
