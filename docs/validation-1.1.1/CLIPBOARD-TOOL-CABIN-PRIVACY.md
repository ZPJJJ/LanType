# 工具舱复制内容的剪贴板隐私修复

## 原因和复现路径

检查基线为本地 `60903e824410c66a4a62608348dcf7e5c0b03c1e`。工具舱打开时，
`InputPrivacy.setToolCabin(true)` 已禁止学习和插件输入事件，但
`ClipboardManager.readClipboard` 的自动收录条件只包含手动无痕和剪贴板搜索，漏掉了工具舱。

可复现操作：在普通宿主输入框中打开工具舱，进入编辑，在工具舱的原生 `EditText`
中输入一段临时文字，长按选中并复制，然后关闭工具舱、打开键盘剪贴板历史。
原路径为 `OnPrimaryClipChanged → readClipboard → addItem → dao.upsert`，会把该复制作为普通历史。
这是代码调用路径确认的缺陷；本说明不把代码检查称为真机验收。

仅在读取时增加 `IncognitoState.toolCabin` 判断不充分：系统监听回调可能晚于面板关闭，
首次读取为空还会在 100 ms 后重试，键盘重新显示及剪贴板面板也可能补读。

另一个边界是 IME 进程退出后重启：当前复制仍在系统剪贴板且不足 30 秒时，
`readMissedCopy` 会进入 `readClipboard(live = false)`。仅有内存中的时间戳和 `privateClips`
无法识别此前的工具舱复制；原生 `EditText` 原本也没有为复制、剪切写入私有元数据。
单独添加 `IS_SENSITIVE` 还不够，因为开启“记录密码等敏感内容”时它会成为 `SECRET` 历史。

## 最小修复

- `ClipboardManager` 把工具舱当前无痕状态和已标记的当前复制身份一并纳入现有私密分支。
  该分支继续使用 `privateClips` 记忆完整的时间戳/内容指纹，避免同一条补读进入历史。
- `InputPrivacy.setToolCabin` 在清除工具舱隐私标志之前调用一个边界 hook。
  hook 只读取当前 `ClipDescription.timestamp`，不读取文本、URI 内容或 intent，也不写磁盘。
- 系统的复制监听不携带旧内容；监听、重试和补读都会重新读取当前 `primaryClip`。
  因而关闭前记住当前复制的时间戳，可以覆盖尚未派发的回调。若重试前系统剪贴板已被一条
  新的普通复制替换，新的不同时间戳正常收录，不继承旧重试的无痕状态。
- 开闭 hook 幂等。重复关闭不会把关闭后出现的新普通复制标成私密。
  当前私密复制的时间戳单独保留，没有容量淘汰或超时；既有 `PrivateClipMemory` 仍负责已读内容指纹。
- 工具舱原生编辑框的显式复制、剪切统一经过 `ToolPanelEditText.onTextContextMenuItem`。
  它在首次 `setPrimaryClip` 前就给所选内容加上 `lantype.tool_cabin_private` 和系统
  `android.content.extra.IS_SENSITIVE` 两个布尔标志，不先发布普通复制再补标记。
  这覆盖原生选择菜单和内部 `InputConnection` 的复制、剪切；剪切仅在系统复制成功后删除选区。
  选中文字的样式保留，空选区和失败复制不会覆盖原剪贴板、删除文字或触发无标记回退。
- `ClipboardManager` 对明确的工具舱私有标记始终分类为 `PRIVATE`，不受敏感历史开关影响。
  标记跟随系统 `ClipData`，所以进程内的记忆全部丢失后，同一条复制仍不进入普通或敏感历史。
  只给工具舱实例启用该行为，`AndroidView` 创建和更新均同步标志；普通插件、搜索编辑框沿用原生复制。

## 元数据边界

时间戳只用作不透明的复制身份，不用于判断墙上时钟区间或先后关系。系统时间回拨不会
让一整个时间区间内的普通复制都被隐藏；同毫秒发生时间戳碰撞时保守视为私密。

关闭时无法取得 description（返回空或抛异常）时，保守隔离下一条可读的当前复制。
第一次读到后会保留其时间戳并交给既有私密记忆；不能在重试时因一次性标记清除而把同一条重新收录。
该边界可能使一条普通复制暂不进入自动历史，系统粘贴仍然可用，下一条不同身份的普通复制恢复正常。

即使工具舱内没有发生新复制，关闭前已有的当前剪贴板也被保守标记。元数据不能证明它来自
工具舱还是之前的应用；本修复不自动删除已存在的历史，也不读取正文来区分来源。

跨进程保护针对用户明确从工具舱编辑框复制、剪切的内容。关闭 hook 的保守时间戳标记仍只存在内存中，
不会在关闭时读取正文或改写系统剪贴板。用户把内容粘贴到其他应用后再次普通复制，是新的系统复制，
其隐私语义由那个应用决定。本应用不保证其他应用保留私有标记，也不阻止用户明确粘贴。

## 定向验证

- `ToolCabinClipPrivacyTest`：11 项纯 helper 回归，覆盖打开时复制、首个回调延迟到关闭后、
  100 ms 重试/重复补读、新普通复制替换旧内容、description 异常和空值、幂等边界、
  时间回拨/碰撞、私密记忆淘汰以及原手动/搜索隐私语义。
- `InputPrivacyTest`：新增关闭 hook 先于工具舱隐私标志清除的顺序回归；已有手动、密码、
  搜索和工具舱状态组合回归保留。
- `ToolPanelPrivateClipboardTest`：7 项 Robolectric Android 路径回归。真实原生复制的首个系统监听
  就能看到两个标志；内部 `InputConnection` 剪切、逆向选区、样式、空选区、拒绝复制和视图转回普通模式
  各有断言。复制和剪切各有一项 `ClipData` Parcel 往返后创建两次真实历史管理器的测试，
  无工具舱内存标记、敏感历史开关开启，实际执行 `readMissedCopy`，验证不入 Room，随后普通复制正常入库。
  这验证 Android 元数据与进程内状态重建边界，不冒充设备进程重启验收。
- 建议同时执行既有 `PrivateClipMemoryTest` 和 `ClipboardSensitiveTest`，检查既有私密记忆和敏感开关语义。

首轮串行 Gradle：其余 9 个定向类的 89 项通过；本次新增 Android 路径类 7 项中 5 项通过，
两项在进入历史读取前的“当前复制不足 30 秒”先决条件失败，原始 XML 保留于 `junit/first-serial`。
检查本地 `shadows-framework-4.14.1.jar` 的 `ShadowClipboardManager.setPrimaryClip` 字节码确认，
该版本以 `SystemClock.uptimeMillis()` 设置 `ClipDescription.timestamp`；
[Android 官方 API 契约](https://developer.android.com/reference/android/content/ClipDescription#getTimestamp())
规定其时间基准为 `System.currentTimeMillis()`。测试夹具现明确补上系统服务赋墙上时间的行为，
且保留 Parcel 时间戳往返断言、生产 30 秒门槛及全部读取/Room 断言；产品源码未因此修改。
修正后仅重跑该单类一次，使用既有 JDK/SDK、`--offline --no-daemon --max-workers=1`、
Kotlin in-process 和 Gradle 3 GiB 堆，`BUILD SUCCESSFUL in 1m 26s`。
7 项全部通过，0 失败、0 跳过；最终 XML 保留于 `junit/clipboard-walltime-final`，
日志为工作区 `work/build-logs/tests-1.1.1-clipboard-walltime.log`。
合并首轮其他 9 类的结果后，去重为 96 项全部通过，不重复累计本类首轮已过的 5 项。
本说明不将 Robolectric 回归称为设备进程重启或真机验收。
