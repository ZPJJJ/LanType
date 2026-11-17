# 仓颉五代与速成

字符编码源自 Jackchows/Cangjie5，提交
`c9b64e77951cba48bdfa5de8eaedd1a908666b9b`，MIT；全文见 `LICENSE-cangjie`
和 `../licenses/Cangjie5-MIT.txt`。仓颉由朱邦复发明，原表署名保留于字表。
来源：https://github.com/Jackchows/Cangjie5/tree/c9b64e77951cba48bdfa5de8eaedd1a908666b9b

LanType 修改：保留已有单字编码，删除旧混合语料权重与自动加入的词组，
按 rime-pinyin-simp/AOSP（Apache-2.0）字频重新赋权；速成使用首尾两码。
生成器为 `tools/lantype_resources/prepare_resources.py`。字表可编辑源码随包发布。
`cyime_cangjie.schema.yaml` 沿用 rime/rime-cangjie 的 LGPL-3.0 方案适配；
此方案代码许可不改变字符码表的 MIT 许可。
