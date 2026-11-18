# 澜语输入法 LanType

**中文与美式英文的离线效率键盘，按 GPLv3 提供应用源码。**

LanType 基于 [CyIME 1.15.94](https://github.com/Cyletix/CyIME/tree/6f97a555ced063c0bcad73c600fe420f5e4b2536) 和 Rime 开发，保留上游版权和各组件许可，是独立发行版。普通输入、随包语音、单字手写、图片识字及工具舱在手机上运行。应用不申请 `INTERNET` 权限，开发电脑仍可下载公开 SDK、构建依赖和经过校验的资源。

当前开发分支目标：**1.1.2 / versionCode 4**，应用 ID：`app.lantype.keyboard`。支持目标为 **Android 9 及以上、ARM64**。本批正在接入已公开的独立重建 ORT 组件，并补齐构建和许可材料；当前没有已验收的 1.1.2 APK。实际进度见 [1.1.2 验证记录](docs/development/lantype-1.1.2-validation.md)。已发布的 [1.1.1 验证记录](docs/validation-1.1.1/VALIDATION.md) 和 [1.1.0 验收记录](docs/validation-1.1.0/VALIDATION.md) 保留历史证据。

**发行状态：开发候选，已有旧版启动阻塞，尚不具备稳定收费发行条件。** 已发布 **1.1.1** 的源码 CI 有 187 个 JUnit 用例通过；该签名 APK 在 Android 15 的 ARM64 转译模拟器上完成身份、断网和安装检查，但首次启动在 ONNX Runtime 动态库初始化阶段发生原生崩溃。旧版 1.1.0 的 Android 11/15 对照也失败。旧版结果、原始证据与商用门槛见 [发布后验证补充](docs/validation-1.1.1/POST-RELEASE.md)。新候选的输入、升级、模型与物理 ARM64 验收仍待实际执行。

## 1.1.2 当前进度

- [独立 ORT 构建](https://github.com/ZPJJJ/LanType/actions/runs/44164186969) 已成功，10 项静态 ABI 检查通过；[第六次普通 Android API 检查](https://github.com/ZPJJJ/LanType/actions/runs/44232550186) 已实际通过同一新库的加载、C API 28、provider 枚举及环境创建/释放。
- 默认预编译与可选源码模式的接入代码已准备，NDK 统一固定为 29；最终包要求保留其余 11 个原生库的字节身份。
- 17 份 NDK、Dawn 和补丁通知已提交，完整资源检查覆盖 396 个 assets 和 11 个 raw；原有 379 条资产记录保持不变。
- 第六次检查使用 API 35 x86_64、ARM64 转译和 4 KiB 页大小的模拟器；API 结果为 `passed`，但最后工作卷卸载失败，整个 workflow 仍为 `failure`。[第七次运行](https://github.com/ZPJJJ/LanType/actions/runs/44235315243) 停在主机 ADB 登记，未启动 guest、未执行 API probe；[后续诊断修复](https://github.com/ZPJJJ/LanType/commit/b5c46a43eeb48b574e067ff8a12316baea0fc938) 已提交，尚未取得新运行结果。
- 用户于 2026-11-18 批准的[云端 Android QA 专用 16 GiB 预算](docs/qa/ANDROID-QA-STORAGE-PROPOSAL.md) 已用于上述实际运行；独立原生和应用整包构建仍受原 5 GiB 预算约束。

[ORT 1.28.0-r1 组件](https://github.com/ZPJJJ/LanType/releases/tag/ort-runtime-1.28.0-r1) 已于 2026-11-18 作为构建依赖预发布，固定 ZIP、三份输出和 [accepted 锁](docs/licensing/ort-runtime.lock.json) 的身份见[公开发行记录](docs/licensing/ort-runtime-r1-publication.json)。接受范围为静态 ABI 与普通 API 加载/环境生命周期；1.1.2 整包和签名发行仍待完成，模型推理、输入法功能、真实 ARM64 手机或 16 KiB 系统均未因此验收。详见 [本批变更](docs/CHANGELOG-1.1.2.zh-CN.md) 和 [组件来源](docs/licensing/ORT-RUNTIME-1.28.0-r1.md)。

## 已发布 1.1.1 的修复

- 工具舱的复制与剪切在首次写入系统剪贴板时附带私密标记，延迟回调、补读或输入法进程重启后仍排除自动历史。
- Whisper 连续语音从中文切到美式英文或反向切换时，结束上一段并使用对应语言的新识别会话，保留连续采集和已完成文字。
- 恢复旧目录结构的词库遇到同名目标或搬移失败时保留原文件，仅删除已经搬空的目录；不混合两份数据库。

1.1.1 安装包沿用原发行签名和包名；其启动阻塞仍按上述记录处理。详见 [1.1.1 变更](docs/CHANGELOG-1.1.1.zh-CN.md) 与 [安装说明](docs/INSTALLATION.zh-CN.md)。

## 新增：工具舱

从键盘工具栏或工具菜单打开 **工具舱**。三类工具共用“编辑 → 预览 → 插入/替换”的流程，输入框里的内容不会因打开工具而自动改写。

| 功能 | 示例与行为 |
| --- | --- |
| 随手算与单位换算 | `2.5 MiB → B` 得到 `2621440 B`；`60 fps → ms/frame` 得到约 `16.6666666667 ms/frame`。支持时间、字节、长度、角度和温度。算术复用上游计算器，单位换算是本版新增。 |
| 选中文字处理 | 主动读取选区，对常见手机号、身份证号和邮箱做遮罩；支持 JSON 排版、URL 编解码、UTF-8 Base64 编解码。先检查结果，再替换原选区。 |
| 动态模板 | `{{date}}`、`{{time}}`、`{{datetime}}` 插入本地时间；`{{cursor}}` 指定插入后的光标位置。含笔记、C#、Lua 示例，可明确保存一个自定义模板。 |
| 剪贴板模板 | 使用 `{{clipboard}}` 时单独请求确认读取，读取后仍需确认插入。剪贴板内看起来像模板的文本不会再次执行。 |

工具舱在密码、受限、未就绪输入框及组字过程中拒绝处理。输入框或选区变化会使旧预览失效；提交前再次核对连接、选区和原文。遮罩是常见格式匹配，发送前仍需检查姓名、地址及未匹配信息。

## 基础输入能力

| 类别 | 当前实现与边界 |
| --- | --- |
| 中文 | Rime 全拼、九键、双拼、整句组词、简繁、模糊音及本地词库；方案代码延续上游，基础词典改为 AOSP/rime-pinyin-simp 与 CC-CEDICT。 |
| English (US) | QWERTY、词语补全、英文滑行、美式词形优先与错拼候选；采用 SCOWL 美式英文词表，保留用户选择原文的能力。 |
| 语音 | 随包 Whisper multilingual base INT8，中文与英文在设备上识别。按语音片段解码，不承诺连续流式出字；速度与准确率需要在目标手机验证。 |
| 中文手写 | 基于 MakeMeAHanzi 笔画中线的单字模板匹配，按常规笔顺书写；不承诺连笔、草书或整行识别效果。拉丁字母模板为本版重新生成。 |
| 图片识字 | 随包 PP-OCRv5 检测和识别模型，在本机处理相机或所选图片。 |
| 编辑和外观 | 延续上游的数字、符号、Emoji、剪贴板、常用语、光标操作、主题、明暗模式、键盘大小、浮动和分体等。 |
| 本地资源 | 词库、方案与支持的扩展文件导入/导出，随包模型可从 APK 恢复。模型导入不等于任意模型都兼容。 |

主要输入引擎和界面基础来自 CyIME/Xime/Rime。新功能、资源替换和权限调整详见 [1.1.0 变更记录](docs/CHANGELOG-1.1.0.zh-CN.md)。不会把继承能力宣传为独立研发，也不承诺包含主流商业键盘的全部专有功能。

## 离线与隐私

- 应用没有联网权限，不需要账户或在线激活。首次部署使用随包资源。
- 不申请短信和通讯录读取权限；验证码由用户在短信应用或通知中复制，再手动粘贴。
- 麦克风、相机和图片访问按相关功能需要请求；拒绝这些权限仍可普通打字。
- 个性化词频、用户词库和剪贴板记录留在本机，系统云备份关闭。临时工具文本不会自动保存，只有主动保存模板时保留其原文。
- 关于页提供随包许可全文的离线阅读器；项目链接由用户选择在外部浏览器打开。

完整说明：[隐私说明](docs/PRIVACY.zh-CN.md)。安装和使用：[使用说明](docs/INSTALLATION.zh-CN.md)。

## 收费与开源

应用衍生代码按 [GPLv3](LICENSE) 发布，可以收费分发；接收者继续享有 GPL 规定的获取对应源码、修改和再分发权。官方签名安装包、稳定更新和支持可以作为收费服务，源码不承担激活或限制用户使用的作用。

模型、词典、笔迹图形和音效分别保留自己的许可证。顶层 GPL 不会替换第三方资源条款。随包声明在 [NOTICE.txt](app/src/main/assets/NOTICE.txt) 和 [licenses/](app/src/main/assets/licenses/)，资源与原生依赖锁定记录在 [docs/licensing/](docs/licensing/)。

补充核查发现已编入 ORT 的 Dawn/WebGPU 源码未覆盖在原 70 份原生源码归档中；现已另行发布 7 份固定源档的补充包，并逐项核验 13 份许可/通知和来源原文。已随包的 Dawn 许可原文保留。旧三份基础源码包须与新补充一起使用，具体更正、下载和范围边界见 [Dawn 源码补充说明](docs/licensing/DAWN-SOURCE-SUPPLEMENT.md)。补档不改变或修复已签名 APK。

本轮清除了 MathWriting、Google10000、旧混合词频及来源未充分确认的模型资源，改用有明确来源记录的材料。发行时仍必须连同实际二进制提供对应应用源码、必要构建脚本、原生源码归档及许可。未完成目标设备测试与渠道审核前，按预发布版本管理。

[商用方案](docs/COMMERCIAL-PLAN.zh-CN.md) 包含价格实验、收费边界、发行顺序、成本测算与渠道准备。[发布清单](docs/RELEASE-CHECKLIST.zh-CN.md) 用于记录尚待完成的步骤。

## 开发构建

开发需要 JDK 21、Android SDK 36、Build Tools 36、NDK `29.0.14206865` 和项目 Gradle wrapper。默认构建从已公开的固定基础 ZIP 恢复并验证现有原生库、相机 JNI 和模型资源。初次准备可能需要访问公开依赖站点；手机运行不联网。

```sh
python3 scripts/restore-base-runtime.py --download
python3 scripts/prepare-upstream.py --verify-only
python3 scripts/build-camerax-native.py --verify-only
python3 scripts/verify-commercial-resources.py
```

ORT 组件与 `docs/licensing/ort-runtime.lock.json` 已公开。完成上述基础准备后，再按 [完整构建流程](docs/LANTYPE-BUILD-AND-SOURCES.md) 恢复固定的新组件并执行 `:app:assembleOffline`。构建入口核对 accepted 锁与三份输出；构建成功后的安装包还需完成产品验证。

应用代码自行编译；Rime 等引擎复用经固定 SHA-256 校验的上游原生库和 Sherpa Java 绑定。CameraX 的两个 JNI 库使用固定的公开模块源码与 libyuv 源码重新构建，最终 APK 必须通过替换产物的字节校验。原生提取脚本不恢复上游 APK 的旧词库或模型。所需大文件不直接塞入 Git 历史，发行资源归档和固定来源用于恢复它们。

SDK、依赖和资源全部缓存后，Gradle 可使用 `--offline`。这不是首次空环境构建命令。签名私钥不进入仓库；自行构建者使用自己的签名。

原生源码版本、构建流程和对应源码归档详见 [构建与源码来源](docs/LANTYPE-BUILD-AND-SOURCES.md)。

## 来源

- CyIME 固定提交：`6f97a555ced063c0bcad73c600fe420f5e4b2536`，上游项目：[Cyletix/CyIME](https://github.com/Cyletix/CyIME)。
- CyIME 的来源：[Xime](https://github.com/ximeiorg/Xime)，应用衍生代码延续 GPLv3。
- 上游原始 README 保存在 [docs/upstream/README.zh-CN.md](docs/upstream/README.zh-CN.md)。历史开发路径、私人设备约定和旧功能描述不代表本版的发行状态。
- LanType 名称、图标和独立签名用于区分官方构建；不暗示 CyIME、Rime 或第三方资源作者对本产品背书。
