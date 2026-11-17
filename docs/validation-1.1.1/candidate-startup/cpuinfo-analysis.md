# 候选 1.1.1 首启：CPU 视图与 cpuinfo 两遍处理假说

[GitHub Actions run 44117540529](https://github.com/ZPJJJ/LanType/actions/runs/44117540529) 直接安装并启动了正式签名的 **1.1.1 / code 3**，不再以前一轮旧版 1.1.0 的失败代替候选版结果。`candidate-startup/result.json` 记录候选 APK 为 179,987,242 字节，SHA-256 `b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497`；签名核验得到证书 SHA-256 `c03b15a19d2ed8899fee6b71f7be09ea5b54c7db9895d7d87b20a9759d8e090b`。环境身份、安装前网络设置关闭和全新安装三项前置检查通过；网络证据是飞行模式/Wi-Fi/移动数据的设置回读与系统状态，不是抓包。候选首启失败，不能记录为输入法功能通过。

`candidate-native-dropbox.txt` 明确记录 `app.lantype.keyboard v3 (1.1.1)`，`pid = tid = 3541`，于 **2026-11-17 15:45:49.072229879 UTC** 发生 `SIGSEGV / SEGV_MAPERR`，访问地址 `0x8`。ARM64 guest 的 ORT 帧仍为 `0x9caedc`、`0x9c9f60`、`0x16f550c`、`0x10d8160`，BuildId 仍为 `b178f5c22304a25ff481e608260312842627e868`，后接 `pthread_once` 和 linker 构造/加载链；现场 `x28 = 0`。这与旧版 API 35 失败的 ORT 加载构造路径一致，受检 ORT 文件的 SHA-256 仍是 `f826d8efb03adf0a84f10e7ba408f9d4cd11b0a2ccd8d08aeb0f7451fb50cacc`。已有 ELF 匹配、反汇编和源码对应说明见 [API 35 原生加载分析](../api35-native-bridge/native-loading-analysis.md)。本轮自动化最终还记录了一次 UI dump 超时；原生崩溃由更早的 DropBox 独立证实，不能把整次失败仅解释成选择器或等待时间问题。

## 同一 guest 实际采集的 CPU 资料

`commands.jsonl` 的命令 171、172 记录两次读取均成功退出：分别于 **15:47:48.352771 UTC** 和 **15:47:48.370129 UTC** 执行。它们是崩溃后、同一模拟器 guest 的 **adb shell 视图**，不是崩溃瞬间在 ARM64 产品进程内插桩所得的数据。`/proc/cpuinfo` 输出 3,328 字节，低于 256 KiB 读取上限；cache 文件共 64 个字段，低于 256 字段上限，未出现截断或不可读标记。

| 原始文件与字段 | 实际观察 |
|---|---|
| `candidate-cpuinfo.txt` | 处理器编号为 `0,1,2,3`；每项 `vendor_id` 为 `AuthenticAMD`，`model name` 为 `Android virtual processor`，含 x86 特征字段。 |
| 同一 `/proc/cpuinfo` 文本 | 未包含 ARM 常见的 `CPU architecture`、`CPU implementer`、`CPU part` 或 `Hardware` 字段；这是对此 shell 输出的检查，不能直接等同于 ARM64 库的输入。 |
| `candidate-cpu-cache-topology.txt`：各 CPU 的 `index2` | `level=2`、`type=Unified`、`size=512K`；`shared_cpu_list` 分别为 `0`、`1`、`2`、`3`，呈现每核独享 L2。 |
| 同文件：各 CPU 的 `index3` | `level=3`、`type=Unified`、`size=16384K`；全部 `shared_cpu_list=0-3`，呈现四核共享 L3。 |

## 对计数／填充假说增加了什么支持

锁定 cpuinfo 提交 `4628dc060ce4e82345dc166bbac875609db4ff69` 的 `src/arm/linux/init.c`，第一遍第 784–827 行根据**解码所得** L2/L3 信息决定是否增加 `l2_count`；第 830–850 行只在计数非零时分配 L2 数组。第二遍第 872–898 行重新读取 sysfs L2 大小，并可因 `l2_is_per_core` 进入写入路径。新资料实际补足了一个外部条件：该 guest 的 shell sysfs 确实提供非零、每核独享的 L2，而 shell `/proc/cpuinfo` 提供 x86 格式身份，未提供 ARM 型号解码通常使用的字段。

因此，**如果 ARM64 库读到相同或同样缺乏 ARM 身份的视图，且第一遍解码得到零 L2/L3，那么第一遍可能保持零计数、跳过分配，第二遍却因非零 sysfs L2 进入写入路径。** 这个条件链与相同 ORT PC、`x28 = 0` 和 `0x8` 错误地址相容，较此前没有 CPU 文件时更有依据。shell 中存在 16 MiB L3 并不自动证明第一遍 `temp_l3.size` 非零，因为该分支使用的是库内解码结果，不能把另一个 sysfs 字段直接代入。这里的处理器数量在两个 shell 视图中都是四个，也不能把上游 PR 的容器 CPU 数量不一致场景原样套用到本次设备。

但本轮**没有直接观测** `l2_count`、`l2_index`、`temp_l2/temp_l3`、分配返回值或 ARM64 库实际打开并读取的文件内容。native bridge 可能拦截、转换或合成部分 CPU 查询；普通 adb shell 的读取也没有证明与产品的 UID、命名空间、native bridge 文件访问行为完全相同。故不能写成“内部 count 已观测为 0”或“已完全证明 native bridge 是根因”。guest PC 可能标记翻译块位置的边界仍成立，不能由相邻反汇编虚构精确故障 C 行。本次也不构成物理 ARM64、16 KiB 页面或运行性能结论。

## 上游修复线索及版本边界

cpuinfo 官方仓库中的 [PR #457](https://github.com/pytorch/cpuinfo/pull/457) 在本轮查阅时为 **open / unmerged**，head 为 `9c259216cb2180d7af681a5caa039a660f4e508e`。它处理相同类型的两遍不一致：计数阶段采用与填充阶段一致的 sysfs L2 信息，并给两处 L2 写入增加边界保护，附带缺少 ARM architecture 信息时的 mock 回归。该 PR 是可审阅的上游修复线索，不代表维护者已合并，也不代表本产品已应用或验证修复。

本项目固定的 cpuinfo 版本早于 PR 基线：部分 L3 上下文不同，原树没有 PR 使用的 `test/mock/arm-linux-topology.cc`。因此需要对固定提交做明确的 **backport**，逐项审阅生产逻辑与回归适配，不能直接使用 PR 当前行号替代本地行号，也不能声称整份 PR 能原样套用。此次仅保存证据分析，没有改动 native 库、应用代码或发布 APK，没有运行重编或新增设备任务。

## 原始材料校验

下表路径相对于该 run 的原始证据归档根目录；命令、APK 身份及环境信息另见 `candidate-startup/commands.jsonl`、`candidate-startup/result.json` 和 `candidate-startup/candidate-signature.txt`。

| 成员 | 字节数 | SHA-256 |
|---|---:|---|
| `candidate-startup/candidate-cpuinfo.txt` | 3,328 | `82fac115ac5af28253d2d74431668a20980b6f54339a268c07865c6cce746ba8` |
| `candidate-startup/candidate-cpu-cache-topology.txt` | 3,574 | `ebfe83ad01a62c7f3ce8c6fc9102241b8c5ffc5fcc17d1886efa9f9642e125d3` |
| `candidate-startup/candidate-native-dropbox.txt` | 4,080 | `9f3a57b0816f305fd014a83aa58fbeaf1a68c2ef691b4c1831bb7d055a16111e` |
