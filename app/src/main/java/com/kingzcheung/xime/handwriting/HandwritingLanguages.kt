package com.kingzcheung.xime.handwriting

import com.kingzcheung.xime.settings.InputLanguage

/** Packaged single-character templates for Chinese and Latin letters/digits. */
object HandwritingLanguages {
    fun supports(language: InputLanguage): Boolean =
        language == InputLanguage.CHINESE || language == InputLanguage.ENGLISH

    fun recognitionLanguageForKeyboard(language: InputLanguage): InputLanguage? =
        language.takeIf { supports(it) }

    /** 英文候选：只留单个英文字母或数字，按原概率排序去重。 */
    fun latinCandidates(raw: List<HandwritingCandidate>, limit: Int): List<HandwritingCandidate> =
        raw.asSequence().filter { c -> c.char.length == 1 && c.char[0].let { it in 'a'..'z' || it in 'A'..'Z' || it in '0'..'9' } }
            .filter { it.score.isFinite() && it.score >= 0f }
            .distinctBy { it.char }.sortedByDescending { it.score }.take(limit.coerceAtLeast(0)).toList()

    /** 手写打开时切换语言：新语言也能手写（内置手写模型在）就留在手写，换成新语言的识别。 */
    fun keepsHandwritingOnSwitch(language: InputLanguage, hasBuiltinModel: Boolean): Boolean =
        hasBuiltinModel && supports(language)

    fun unavailableMessage(language: InputLanguage): String = if (language == InputLanguage.UNSPECIFIED)
        "当前方案未标注语言，请在「已安装的方案」里给它选语言后再手写" else "暂不支持${language.displayName}手写，请切换到中文或英文"
}
