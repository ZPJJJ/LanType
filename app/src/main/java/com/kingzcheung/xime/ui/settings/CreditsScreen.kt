package com.kingzcheung.xime.ui.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp

/** 鸣谢里的一项：名称、作者（不清楚时留空）、用在哪里、许可证（设计参考没有许可证），点开是项目主页。 */
data class CreditItem(
    val name: String,
    val author: String,
    val use: String,
    val license: String?,
    val url: String,
)

/**
 * 设置 › 关于 › 鸣谢：只列主要的引擎、词库、数据、模型和设计参考，开发基础放最后。
 * 此处与 LanType 随包 NOTICE、许可锁定清单同步；完整许可正文可在本机阅读。
 */
object Credits {
    val groups: List<Pair<String, List<CreditItem>>> = listOf(
        "输入引擎" to listOf(
            CreditItem("Rime(librime)", "佛振及 Rime 社区", "输入引擎", "BSD-3-Clause", "https://github.com/rime/librime"),
            CreditItem("OpenCC", "BYVoid", "简繁转换", "Apache-2.0", "https://github.com/BYVoid/OpenCC"),
            CreditItem("sherpa-onnx", "k2-fsa 及依赖贡献者", "本地语音运行库；静态依赖见随包许可", "Apache-2.0；另含 GPL 等依赖", "https://github.com/k2-fsa/sherpa-onnx"),
            CreditItem("ONNX Runtime", "Microsoft", "语音、识字的模型推理", "MIT",
                "https://github.com/microsoft/onnxruntime"),
            CreditItem("OpenCV", "OpenCV 贡献者", "离线图片处理", "Apache-2.0", "https://github.com/opencv/opencv"),
        ),
        "词库与数据" to listOf(
            CreditItem("雾凇拼音", "iDvel", "方案与 Lua 代码；本版重新生成基础词库", "GPL-3.0", "https://github.com/iDvel/rime-ice"),
            CreditItem("rime-pinyin-simp", "Android Open Source Project；Rime 社区", "中文基础词典", "Apache-2.0", "https://github.com/rime/rime-pinyin-simp"),
            CreditItem("CC-CEDICT", "MDBG 及词典贡献者", "中文词条与读音", "CC BY-SA 4.0", "https://www.mdbg.net/chinese/dictionary?page=cedict"),
            CreditItem("SCOWL", "Kevin Atkinson 及词表贡献者", "美式英文词表及其派生索引", "SCOWL 宽松许可（全文随包）", "https://github.com/en-wl/wordlist"),
            CreditItem("倉頡五代", "Jackchows", "仓颉码表", "MIT", "https://github.com/Jackchows/Cangjie5"),
            CreditItem("rime-stroke", "Rime", "笔画方案", "LGPL-3.0", "https://github.com/rime/rime-stroke"),
            CreditItem("小麦注音", "OpenVanilla；libtabe 贡献者", "台湾词和读音", "MIT；BSD-3-Clause", "https://github.com/openvanilla/McBopomofo"),
        ),
        "模型" to listOf(
            CreditItem("Whisper", "OpenAI；sherpa-onnx 转换贡献者", "中文与英文离线语音识别", "MIT",
                "https://github.com/openai/whisper"),
            CreditItem("Silero VAD", "Silero Team", "本地语音活动检测", "MIT", "https://github.com/snakers4/silero-vad"),
            CreditItem("PP-OCRv5", "PaddlePaddle；RapidAI", "拍照识字", "Apache-2.0", "https://github.com/PaddlePaddle/PaddleOCR"),
            CreditItem("MakeMeAHanzi 图形", "Shaunak Kishore 及图形贡献者", "中文单字笔顺模板；图形数据使用 Arphic 许可", "Arphic Public License", "https://github.com/skishore/makemeahanzi"),
        ),
        "设计参考" to listOf(
            CreditItem("三星键盘", "Samsung", "键盘交互和外观", null, "https://www.samsung.com/"),
            CreditItem("Gboard", "Google", "键盘交互和外观", null,
                "https://play.google.com/store/apps/details?id=com.google.android.inputmethod.latin"),
            CreditItem("Typewise", "", "蜂窝六边形布局", null, "https://www.typewise.app/"),
            CreditItem("首道双拼", "", "首道双拼键位", null, "https://sspai.com/post/108949"),
            CreditItem("小鹤双拼", "小鹤音形", "小鹤双拼键位", null, "https://flypy.cc/"),
        ),
        "开发基础" to listOf(
            CreditItem("CyIME", "Cyletix 及贡献者", "澜语基于 CyIME 1.15.94 开发", "GPL-3.0", "https://github.com/Cyletix/CyIME"),
            CreditItem("Xime", "", "CyIME 基于它开发", "GPL-3.0", "https://github.com/ximeiorg/Xime"),
        ),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CreditsContent(onBack: () -> Unit) {
    val uriHandler = LocalUriHandler.current
    Scaffold(
        containerColor = MaterialTheme.colorScheme.surface,
        topBar = {
            TopAppBar(
                title = { Text("鸣谢") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface
                ),
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp).settingsVerticalScroll(),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Credits.groups.forEach { (title, items) ->
                SettingsSection(title = title) {
                    items.forEachIndexed { index, item ->
                        if (index > 0) SettingsRowDivider()
                        val detail = listOfNotNull(item.author, item.use, item.license).filter { it.isNotBlank() }.joinToString(" · ")
                        SettingsListRow(item.name, detail, Modifier.clickable { uriHandler.openUri(item.url) }) {
                            Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(end = 12.dp).size(18.dp))
                        }
                    }
                }
            }
            Column {
                LocalLicenseDocuments()
                SettingsNote("上方是主要来源，完整声明和许可正文可离线阅读。澜语原创的拉丁字母笔迹模板、示例短语与按键音效按 CC0 提供。点项目名称会在外部浏览器打开主页。")
            }
        }
    }
}
