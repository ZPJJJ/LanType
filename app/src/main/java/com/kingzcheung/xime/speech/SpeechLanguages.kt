package com.kingzcheung.xime.speech

import com.kingzcheung.xime.settings.InputLanguage

/** Explicit capabilities of the shipped recognizers. Unknown models are never assumed Chinese. */
object SpeechLanguages {
    fun supports(mode: String, language: InputLanguage): Boolean =
        SpeechModelSelection.primary(mode) == SpeechModelCatalog.WHISPER &&
            language in setOf(InputLanguage.CHINESE, InputLanguage.ENGLISH)

    /** Keep a compatible saved choice. A language fallback is session-local, never persisted. */
    fun select(language: InputLanguage, preferred: String, isReady: (String) -> Boolean): String {
        require(language != InputLanguage.UNSPECIFIED) { "当前方案未标注语言，请在「已安装的方案」里给它选语言" }
        require(language in InputLanguage.speech) { "暂时没有${language.displayName}语音识别" }
        if (supports(preferred, language)) {
            check(isReady(preferred)) { "所选${language.displayName}语音模型尚未准备完成，请在本地模型中恢复" }
            return preferred
        }
        return SpeechModelCatalog.WHISPER.takeIf { supports(it, language) && isReady(it) }
            ?: error("未准备好支持${language.displayName}的内置语音模型；本版支持中文和英文，请在本地模型中恢复 Whisper")
    }
}
