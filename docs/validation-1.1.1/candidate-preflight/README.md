# 1.1.1 candidate-only 首启尝试：预检解析阻塞

本次独立 `candidate-startup` run 在安装前的 QA 证书输出解析处停止，**1.1.1 未安装、未启动，不能从本轮推断其实际首启行为。** 这是测试脚本对新版本 apksigner 输出格式的兼容错误，不是发行 APK 证书改变，也不是本次发现的产品 native 崩溃。

## 实际结果

| Case | 结果 |
|---|---|
| candidate-environment-and-signed-identity | failed：证书文本行格式未被解析器接受 |
| disable-network-before-candidate | blocked |
| fresh-candidate-and-host-install | blocked |
| candidate-first-launch | blocked |

原始计数为 **0 passed / 1 failed / 3 blocked / 0 not_run**。模拟器 KVM、API35、user 0 解锁、ARM64/native-bridge 门禁已执行通过；候选文件的固定 SHA、大小、包名和版本检查也已通过。但组合 identity case 在证书格式解析处失败，所以不能把它改记为 passed。断网操作、产品/host 安装和首启均未执行。

## 精确原因

原始 `candidate-startup/candidate-signature.txt` 显示 apksigner 验证退出成功，`Number of signers: 1`，证书行是：

```text
V3.0 Signer: certificate SHA-256 digest: c03b15a19d2ed8899fee6b71f7be09ea5b54c7db9895d7d87b20a9759d8e090b
```

这个 SHA-256 与既有发行证书完全一致。脚本只匹配旧格式 `Signer #1 certificate SHA-256 digest: ...`，未识别 build-tools 37 的 `V3.0 Signer:` 前缀，误将空匹配结果判为不符。后续修正应只兼容这两种明确格式，继续严格保留单 signer、固定证书与 APK 字节校验，不能关闭签名门禁。

本轮 `product-exit-info.txt` 没有产品退出记录，`native-app-dropbox.txt` 为 `No entries found.`。CPU topology 的采集位于首启 finally，因未到首启而未执行；没有可据以讨论的本轮产品 native frame 或 UI 截图。此前 1.1.0 在 API30/API35 上的崩溃证据须分开阅读。

## 候选文件身份

- 包名 `app.lantype.keyboard`；版本 1.1.1 / versionCode 3。
- 大小 179,987,242 字节。
- APK SHA-256：`b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497`。
- 观察到的证书 SHA-256 与固定预期均为 `c03b15a19d2ed8899fee6b71f7be09ea5b54c7db9895d7d87b20a9759d8e090b`。

## 原始证据附件

- [run 44116007517](https://github.com/ZPJJJ/LanType/actions/runs/44116007517)，job `134154114500`。
- head：`41e6cc2c2e0e1980f388a073512a941c4cf17569`。
- [Actions artifact 14343396565](https://github.com/ZPJJJ/LanType/actions/runs/44116007517/artifacts/14343396565)，原平台保留期至 2026-11-24。
- 配套附件：`LanType-1.1.1-candidate-preflight-evidence.zip`；状态 **prepared**，此文不声称已上传。
- 263,000 字节，25 个成员；SHA-256：`290f1bde9103b978857b1c1094e7319aa28a8467e482415557725bf5561f46bd`。
- 下载 SHA 与服务端 digest 一致；ZIP 原样硬链接归档，未改写证据。

主要成员为 `candidate-startup/result.json`、`candidate-startup/candidate-signature.txt`、`candidate-startup/commands.jsonl`、`release-apks.json`、`product-exit-info.txt` 和 `native-app-dropbox.txt`。机器可读记录见 [receipt.json](receipt.json)。

这次归档没有改变产品源码、签名 APK 或用户设备，也不包含任何源 CI/JUnit 通过数作为设备结果。
