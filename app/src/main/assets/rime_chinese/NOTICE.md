# LanType 中文方案资源说明

本版保留 CyIME/Xime 的 Rime 接线与布局，以及固定版本
`9e66b0729083b37d217312294f6d516c8d7234be` 的 rime-ice 方案/Lua（GPL-3.0）。
共享中文字表已替换为 rime-pinyin-simp/AOSP（Apache-2.0）及 CC-CEDICT
2026-11-16 快照（CC-BY-SA-4.0）；原来的雾凇混合来源词表不在本版内。
英文表由 SCOWL 美式词表生成。完整来源、修改和许可见 `../NOTICE.txt`、
`../licenses/` 与源码 `docs/licensing/resources.lock.json`。

`tools/lantype_resources/prepare_resources.py` 生成中文、英文、九键/14键和
手写候选读音资源。词典查询、Rime 组词与用户本地学习均离线；没有外部统计
模型、神经整句打分器或后台资源下载。初始化用新的资源指纹重新部署。

OpenCC 简繁转换表遵守 Apache-2.0。`CyimeTWPhrases.ocd2`、台湾词/读音及
声调表来自 McBopomofo 固定提交 `18e2060dd5d0b511753ad79a8fe0d112e944f1af`；
遵守 MIT，并保留其 BPMF/libtabe 数据的 BSD-3-Clause 通知。台湾词权重重置为 1。
仓颉、笔画和辅助形码分别参见同目录通知；仓颉/注音方案适配沿用上游 LGPL-3.0。
