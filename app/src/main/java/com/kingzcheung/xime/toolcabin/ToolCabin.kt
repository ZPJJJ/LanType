// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.toolcabin

import com.kingzcheung.xime.calculator.CalculatorEngine
import java.time.ZonedDateTime

/** All drafts and expanded results are session-only. Only SaveTemplate explicitly persists text. */
enum class CabinMode(val zh: String, val en: String) {
    CALCULATE("随手算", "Calculate"), TEXT("文本工具", "Text"), TEMPLATE("动态模板", "Templates");
    fun label(english: Boolean) = if (english) en else zh
}

enum class TextTool(val zh: String, val en: String) {
    MASK("隐私遮罩", "Mask private data"), JSON("JSON 排版", "Format JSON"),
    URL_ENCODE("URL 编码", "URL encode"), URL_DECODE("URL 解码", "URL decode"),
    BASE64_ENCODE("Base64 编码", "Base64 encode"), BASE64_DECODE("Base64 解码", "Base64 decode");
    fun label(english: Boolean) = if (english) en else zh
}

enum class CabinProblem(val zh: String, val en: String) {
    EMPTY("先输入内容，再预览。", "Enter something to preview."),
    TOO_LONG("内容太长；每次最多处理 16,384 个字符。", "Use at most 16,384 characters at a time."),
    INVALID_CALCULATION("算式不完整。换算示例：2.5 MiB → B、60 fps → ms/frame。", "Check the expression. Try 2.5 MiB → B or 60 fps → ms/frame."),
    UNKNOWN_UNIT("暂不支持这个单位。可换算时间、字节、长度、角度、温度和帧率。", "Supported units cover time, bytes, distance, angles, temperature and frame time."),
    DIFFERENT_DIMENSIONS("这两个单位的量纲不同，不能换算。", "These units measure different quantities."),
    INVALID_VALUE("数值超出支持范围，或低于绝对零度；帧率必须大于零。", "Value is out of range, below absolute zero, or a nonpositive frame rate."),
    INVALID_JSON("JSON 格式有误；不会改动原文。", "Invalid JSON. Your original text is unchanged."),
    JSON_TOO_DEEP("JSON 嵌套太深；最多支持 32 层。", "JSON nesting is limited to 32 levels."),
    INVALID_ENCODING("编码无效，或解码结果不是 UTF-8 文本。", "Invalid encoding or non-UTF-8 text."),
    MANY_CURSORS("每个模板只可放一个 {{cursor}} 光标槽。", "Use only one {{cursor}} slot per template."),
    EDITOR_UNAVAILABLE("当前输入框不允许工具操作，或尚未连接。", "Tools are unavailable in this field or the editor is disconnected."),
    FINISH_COMPOSITION("请先完成当前组字，再打开工具舱或重新预览。", "Finish the current composition, then open the cabin or preview again."),
    NO_SELECTION("请先在应用内选中文字，再点“读取选区”。", "Select text in the app, then tap Read selection."),
    SELECTION_CHANGED("插入位置或选区已改变。请重新读取选区或预览。", "The caret or selection changed. Read the selection or preview again."),
    SELECTED_TEXT_UNREAD("当前有选区。请先读取选区确认替换，或取消选区后再预览。", "Read the selected text to confirm replacement, or clear the selection first."),
    SESSION_CHANGED("输入框已切换，旧预览不能写入。请重新打开工具舱。", "The editor changed. Reopen the cabin for a new preview."),
    EDITOR_REJECTED("应用未接受写入，原预览已保留。", "The app rejected the insertion. Your preview is still available."),
    NO_CLIPBOARD("剪贴板中没有可读取的纯文本。", "No plain text is available on the clipboard."),
    SAVED("已将模板原文保存在本机；展开的选区和剪贴板不会自动保存。", "Template saved locally. Expanded selection and clipboard text are not saved automatically."),
    INSERTED_CURSOR_UNAVAILABLE("文字已插入；此编辑器未接受光标定位。", "Text inserted, but this editor did not accept the cursor position.");
    fun label(english: Boolean) = if (english) en else zh
}

data class CabinPreview(val text: String, val cursor: Int = text.length, val note: String = "")

sealed interface CabinResult {
    data class Ready(val preview: CabinPreview) : CabinResult
    data class Failed(val problem: CabinProblem) : CabinResult
    data object ClipboardRequired : CabinResult
}

data class ToolCabinState(
    val mode: CabinMode = CabinMode.CALCULATE,
    val input: String = "2.5 MiB → B",
    val textTool: TextTool = TextTool.MASK,
    val preview: CabinPreview? = null,
    val problem: CabinProblem? = null,
    val editing: Boolean = false,
    val replacesSelection: Boolean = false,
    val clipboardRequired: Boolean = false,
)

sealed interface CabinAction {
    data class Mode(val value: CabinMode) : CabinAction
    data class Operation(val value: TextTool) : CabinAction
    data class Preset(val value: String) : CabinAction
    data class Input(val value: String) : CabinAction
    data object Edit : CabinAction
    data object Preview : CabinAction
    data object ReadSelection : CabinAction
    data object ConfirmClipboard : CabinAction
    data object Insert : CabinAction
    data object LoadTemplate : CabinAction
    data object SaveTemplate : CabinAction
    data object Close : CabinAction
}

object ToolCabin {
    const val MAX_INPUT = 16_384
    const val MAX_OUTPUT = 65_536
    const val CS_TEMPLATE = "Debug.Log(\"{{cursor}}\"); // {{date}}"
    const val LUA_TEMPLATE = "print(\"{{cursor}}\") -- {{date}}"
    const val NOTE_TEMPLATE = "{{date}} {{time}}\n{{cursor}}"
    const val CLIPBOARD_TEMPLATE = "[{{date}} {{time}}]\n{{clipboard}}\n{{cursor}}"

    fun preview(state: ToolCabinState, now: ZonedDateTime, clipboard: String? = null): CabinResult {
        if (state.input.isBlank()) return CabinResult.Failed(CabinProblem.EMPTY)
        if (state.input.length > MAX_INPUT) return CabinResult.Failed(CabinProblem.TOO_LONG)
        return when (state.mode) {
            CabinMode.CALCULATE -> {
                if (state.input.contains(Regex("→|->|\\bto\\b|到|转", RegexOption.IGNORE_CASE)))
                    UnitConverter.convert(state.input)
                else if (state.input.length > 256) CabinResult.Failed(CabinProblem.INVALID_CALCULATION)
                else CalculatorEngine().evaluate(CalculatorEngine.normalized(state.input))
                    ?.let { CabinResult.Ready(CabinPreview(it)) }
                    ?: CabinResult.Failed(CabinProblem.INVALID_CALCULATION)
            }
            CabinMode.TEXT -> TextTransforms.apply(state.textTool, state.input)
            CabinMode.TEMPLATE -> DynamicTemplate.expand(state.input, now, clipboard)
        }
    }
}
