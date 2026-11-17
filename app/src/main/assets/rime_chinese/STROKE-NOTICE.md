# 五笔画方案

字符编码来自 rime/rime-stroke（四季的風、雪齋、Kunki Chou、宋天），提交
`1e8fff9b9494ddec23b0cbc526bcfd8171a6fd48`，LGPL-3.0；全文见 `LICENSE-stroke`
及 `../licenses/Rime-Stroke-LGPL-3.0.txt`。
来源：https://github.com/rime/rime-stroke/tree/1e8fff9b9494ddec23b0cbc526bcfd8171a6fd48

LanType 保留字符笔画编码，替换旧字频为声明过来源的 AOSP/CC-CEDICT
派生权重；`stroke_phrase.dict.yaml` 的二至四字词来自 rime-pinyin-simp/AOSP
（Apache-2.0），编码取每字第一笔。原来的雾凇字频和混合词表不再使用。
生成器为 `tools/lantype_resources/prepare_resources.py`；可编辑表和修改源码
在对应源码包中。通配/短码 Lua 功能沿用 CyIME 的 GPL-3.0 代码。
