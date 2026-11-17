# GitHub 托管源码 CI 证据

本页记录 [run 44103398875](https://github.com/ZPJJJ/LanType/actions/runs/44103398875) / job `134109156858` 的已完成结果：**success**。运行绑定的不可变源码提交为 `1bcafe8b47e6aed3e713a194a64e63bfb8bb9f28`，不是对当前工作区所有后续改动的笼统验收。

## 实际结果与范围

- 本次 artifact 的 **27 份 JUnit XML、187 个唯一测试全部通过**，失败、错误和跳过均为 0。统计逐项核对了 testcase 元素与 testsuite 声明，并排除了重复测试标识。
- 固定原生源码验证另有 **12 项 Python 测试通过**，单列统计，不计入上述 187 项。
- 保留 **20 张 Compose 渲染 PNG**。本次整理没有逐张肉眼验收，不能据生成成功宣称视觉验收通过。
- 日志记录离线 APK 构建成功（10 分 50 秒），定向测试与渲染步骤成功（6 分 6 秒）。
- 本次 **未签名 CI APK** 静态检查通过：379 个 assets、11 个 raw 资源、2 个从源码构建的 CameraX JNI 与锁文件匹配；扫描 **2,161 个 ZIP 条目**。已签名交付 APK 的对应记录为 **2,164 个条目**，两者不能互换，也不宣称整个 APK 字节一致。
- 此运行没有 Android guest、实体手机或 16 KiB 页运行结果。

## 源码对应关系

CI 远端提交对应本地 `28a5a21154980097981f41ea8aabe881de2cf791`，共同树为 `4928b462a9464c0a44d621b8f21e3a367dbe465c`。依据上传时记录的 GitHub create_tree 与本地树相等映射，本次再次核对了本地树 ID；摘录及实际差异清单保存在证据包 `commit-map-evidence.json`。

交付产品提交为本地 `a83eadd5c0b5d22ffbff248e99b4d9db137b02a6` / 远端 `abb0b9369424029f1d7418ca56fc6d38f2872f96`。本次只读比较确认：产品提交到 CI 对应提交之间，`app/`、`plugin-core/` 没有变化；CI 对应提交到核对时已提交本地 HEAD `c8f6f4f8a8a9b6b95b830d87878c849efd1a3619`（远端 `6fd9068af31a6f3153c78837a930182f189164a3`）之间只变更文档、QA 工具与 QA workflow，产品代码未变。当前未提交的测试 host 改动不属于此次 CI 证据。

## 附件与校验

附件 **`LanType-1.1.1-hosted-source-ci-evidence.zip`** 已上传到 **1.1.1 RC**；GitHub 返回的字节数和 SHA-256 与本地一致。文件大小为 **1,786,829 字节**，SHA-256：

```text
91b8de509c3ed9d778ddd7932b072bf1d39f994fee72f67ab182573a5ce2dbee
```

附件包含原 artifact 中 78 份 XML、PNG、HTML 等证据，以及小统计、步骤状态、选定日志和提交映射。`inventory.json` 列出其余全部 83 个成员的路径、字节数和 SHA-256；inventory 自身的 SHA-256 与整包 SHA-256 见 [receipt.json](receipt.json)。原 artifact 下载字节已与 GitHub 公布的大小、SHA-256 核对一致，包含未签名 APK 的原始 ZIP 已删除，APK 未提取或重复保存。附件不包含下载链接、认证头、令牌或 APK。

逐类测试数量、时间与文件证据在附件 `ci-evidence-summary.json` 中；本目录只保留紧凑回执，不重复提交完整逐文件哈希列表。
