# 本地 TCG 模拟器尝试：仅完成旧版安装

**结论：旧签名 1.1.0 ARM64 APK 和独立编辑器宿主安装成功；未证明可交互首启、Rime 部署、中文或美国英文输入。1.1.1 未在这次本机尝试中安装，覆盖升级和工具舱设备流程均未执行。**

详细机器回执见 [receipt.json](receipt.json)。本记录属于本地软件模拟环境，不能与后续 GitHub KVM 结果或物理 ARM64 设备结果合并计数。

## 环境与已完成事项

- 官方 Android Emulator 37.2.13；Android 11 / API 30 Google APIs x86_64 revision 16。
- 宿主没有 KVM。实际 guest 属性确认 `libndk_translation.so`、ARM64 到 x86_64 的转换及 `arm64-v8a` ABI 支持；这不等于已证明 Rime JNI 执行正常。
- 最后一次有界尝试使用原 AVD 数据、4 个虚拟 CPU、3072 MiB RAM，用户 0 达到 `RUNNING_UNLOCKED`。
- 产品启动意图发出前，实际读回飞行模式为 1、Wi-Fi 为 0、移动数据为 0；旧 APK 未声明 INTERNET 权限。
- 旧 APK 的 streaming、非 incremental 安装返回 `Success`、exit 0，耗时 511.246 秒。PackageManager 确认版本 1.1.0/code 2、`primaryCpuAbi=arm64-v8a`、非 debuggable。耗时仅为这次慢速环境的记录，不是产品性能基准。
- 独立编辑器宿主同样安装成功。没有使用卸载或 `pm clear`。

## 阻塞与最后状态

早先 2 vCPU / 2 GiB 环境多次发生 Android framework watchdog：`android.fg` 在 `UserDataPreparer.prepareUserData` / 用户解锁路径等待锁，随后 SystemServer 被终止。没有证据足以把它定性为 guest OOM。

唯一一次 4 vCPU / 3 GiB 调整越过了用户解锁阻塞，但后续仍出现 Pixel Launcher、System UI 和 Google Play services 的 ANR。首次 `am start -W` 在 180 秒后超时。实际 XML 明确显示系统应用名称；按 XML bounds 关闭 Launcher 对话框后，又出现 System UI 对话框。

最后约 69 秒的探测按 XML 点击一次 System UI 的 Wait，收集可用进程事件并截图。最后图像是白色内容窗口和系统栏，UIAutomator 返回 null root。ActivityManager 曾记录产品进程启动，但未得到稳定产品进程及可交互产品页面。一次限定范围的 crash buffer 读取为空，不能据此推导所有产品启动路径都正常。上述系统失败也不作为 LanType 缺陷的证据。

模拟器于 **2026-11-17 14:30:26 UTC** 停止。`adb emu kill` 返回 0；宿主 emulator 在清理阶段实际返回 -11，已独立记录，没有把它写成产品崩溃。锁已释放，AVD 数据和已安装旧 APK 保留。最后记录的本任务实际磁盘分配为 4,645,011,456 字节，约 4.326 GiB，低于 5 GiB 预算。不再继续本机重复启动。

## 精选证据包

证据包已准备，作为独立 Release 附件提供；本记录不预先声称上传或发布完成。

| 项目 | 值 |
| --- | --- |
| 文件名 | `LanType-1.1.1-local-tcg-attempt-evidence.zip` |
| 大小 | 79,707 字节 |
| SHA-256 | `a73227de350c87acf18180c1e84e50f965db2f73de7697c7d1e229fe416dc785` |
| 成员数 | 29 |

包中包含安装/断网回执、系统 watchdog/ANR 摘录、三张实际截图与相应 XML；不含 AVD 镜像、APK、签名材料或认证文件。回执中的证据路径均按该 ZIP 的成员路径解释，不要求读者拥有原执行环境的绝对路径。更宽的原始系统日志另外保留，并非全部放入精选包。

本包文件名中的 1.1.1 表示本轮验收任务；它**不表示 1.1.1 已完成设备验证**。
