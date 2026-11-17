# LanType 1.1.0 GitHub 发行准备

本版采用独立仓库 `ZPJJJ/LanType`。这个名称是发行目标，不代表上传已完成；远端是否存在、提交是否可读取以及附件是否能下载，必须在实际操作后核验。

## 公开内容

Git 仓库保存审核过的应用源码、测试、构建脚本、许可、资源生成源和发行说明。大模型、预编译原生库和对应的大源码归档通过同版本附件提供。不要把整个工作目录直接上传；其中包含缓存、历史资源及不应公开的签名备份。

本版先按 **预发布** 管理：APK 的版本号为 `1.1.0`，建议 Git 标签为 `v1.1.0-rc1`。未完成的真机与渠道验收见 [发布清单](RELEASE-CHECKLIST.zh-CN.md)。

## 使用 Git 历史归档恢复

`LanType-1.1.0-git.bundle` 包含本轮公开提交和标签，不含私钥、运行模型或原生二进制。可以在已经安装 Git 的电脑上恢复：

```sh
git clone LanType-1.1.0-git.bundle LanType
cd LanType
git status
```

通过 GitHub 官方登录流程授权 GitHub CLI，不要把密码、访问令牌或签名口令贴进聊天、提交记录或 Issue。确认登录账户为 `ZPJJJ` 后，在该仓库确实尚不存在时创建并推送：

```sh
gh repo create ZPJJJ/LanType --public --source=. --remote=origin --push
git push origin v1.1.0-rc1
```

如果目标仓库已经存在，先检查其内容和默认分支，再设置远端并按正常 Git 流程推送；不要强制覆盖已有历史。包含 `.github/workflows/offline-ci.yml` 的推送还需要授权方式允许更新工作流文件。

## 同版本附件

预发布页应同时提供：

- `LanType-1.1.0-offline-arm64-v8a.apk`
- `LanType-1.1.0-source.zip`
- `LanType-1.1.0-runtime-dependencies.zip`
- `LanType-1.1.0-native-source.zip`，或内容完整、说明明确的对应源码分包
- `LanType-1.1.0-SHA256SUMS.txt` 和发行验证记录

使用 `gh release create` 时通过 `--notes-file` 读取已经检查的发行说明，并使用 `--prerelease` 标记。不要只附 APK 再声称源码已经提供；应用源码和原生对应源码需要同时可获取。源码附件不另行收费。

最后从远端核对默认分支、标签、README、GPL 正文和附件元数据，确认私钥没有上传。GitHub Actions 的首次执行结果应另行记录，本地构建通过不能冒充远端 CI 通过。
