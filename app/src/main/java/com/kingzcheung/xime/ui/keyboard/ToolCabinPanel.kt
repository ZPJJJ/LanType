// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.ui.keyboard

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kingzcheung.xime.toolcabin.*

/** Full keyboard overlay. Editing uses the existing in-IME editor above the regular keyboard. */
@Composable
fun ToolCabinPanel(
    state: ToolCabinState,
    onAction: (CabinAction) -> Unit,
    modifier: Modifier = Modifier,
    backgroundColor: Color = MaterialTheme.colorScheme.surface,
    bottomPaddingDp: Int = 0,
    english: Boolean = LocalConfiguration.current.locales[0].language == "en",
) {
    fun word(zh: String, en: String) = if (english) en else zh
    val colors = MaterialTheme.colorScheme
    Surface(modifier.fillMaxSize().testTag("tool-cabin"), color = backgroundColor.copy(alpha = 1f),
        contentColor = colors.onSurface) {
    Column(Modifier.fillMaxSize().padding(bottom = bottomPaddingDp.dp)) {
        Row(Modifier.fillMaxWidth().height(44.dp).padding(start = 16.dp, end = 4.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Text(word("工具舱", "Tool cabin"), style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
            Icon(Icons.Default.Lock, null, Modifier.size(12.dp), tint = colors.primary)
            Text(word("  本机处理", "  On device"), fontSize = 11.sp, color = colors.primary)
            IconButton({ onAction(CabinAction.Close) }, Modifier.size(44.dp).testTag("cabin-close")) {
                Icon(Icons.Default.Close, word("关闭工具舱", "Close tool cabin"), Modifier.size(20.dp))
            }
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp).padding(bottom = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            CabinMode.entries.forEach { mode ->
                ToolTab(mode.label(english), state.mode == mode, { onAction(CabinAction.Mode(mode)) },
                    Modifier.weight(1f).testTag("cabin-mode:${mode.name}"), compact = true)
            }
        }
        Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
            .padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            when (state.mode) {
                CabinMode.CALCULATE -> {
                    Presets(listOf("2.5 MiB → B", "60 fps → ms/frame", "180 deg → rad", "(10+5)/3"), onAction)
                    Text(word("时间 · 字节 · 长度 · 角度 · 温度 · 帧率；KB = 1000 B，KiB = 1024 B",
                        "Time · bytes · length · angles · temperature · frame time. KB = 1000 B; KiB = 1024 B"),
                        fontSize = 11.sp, lineHeight = 15.sp, color = colors.onSurfaceVariant)
                }
                CabinMode.TEXT -> {
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        TextTool.entries.forEach { tool ->
                            FilterChip(selected = state.textTool == tool,
                                onClick = { onAction(CabinAction.Operation(tool)) },
                                label = { Text(tool.label(english), fontSize = 12.sp) },
                                modifier = Modifier.testTag("cabin-operation:${tool.name}"))
                        }
                    }
                    Text(word("只读取你明确选中的文字；不会抓取整个输入框。", "Only text you select is read. The full field is never collected."),
                        fontSize = 11.sp, lineHeight = 15.sp, color = colors.onSurfaceVariant)
                }
                CabinMode.TEMPLATE -> {
                    val templates = listOf("C#" to ToolCabin.CS_TEMPLATE, "Lua" to ToolCabin.LUA_TEMPLATE,
                        word("日期笔记", "Dated note") to ToolCabin.NOTE_TEMPLATE,
                        word("剪贴板引用", "Clipboard quote") to ToolCabin.CLIPBOARD_TEMPLATE)
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        templates.forEach { (label, template) ->
                            SuggestionChip({ onAction(CabinAction.Preset(template)) }, { Text(label, fontSize = 12.sp) })
                        }
                    }
                    Text("{{date}}  {{time}}  {{cursor}}  {{clipboard}}", fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp, color = colors.onSurfaceVariant)
                }
            }
            Surface(shape = RoundedCornerShape(12.dp), color = colors.surfaceContainerHigh,
                modifier = Modifier.fillMaxWidth().testTag("cabin-source").clickable { onAction(CabinAction.Edit) }) {
                Row(Modifier.padding(start = 12.dp, end = 4.dp, top = 4.dp, bottom = 4.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(word(if (state.replacesSelection) "已读取的选区" else "输入", if (state.replacesSelection) "Selected source" else "Input"),
                            fontSize = 10.sp, color = colors.onSurfaceVariant)
                        Text(state.input.ifEmpty { word("点此输入，或读取应用中的选区", "Tap to type, or read a selection") },
                            fontSize = 13.sp, lineHeight = 18.sp, maxLines = 2, overflow = TextOverflow.Ellipsis,
                            fontFamily = FontFamily.Monospace)
                    }
                    IconButton({ onAction(CabinAction.Edit) }, Modifier.size(44.dp).testTag("cabin-edit")) {
                        Icon(Icons.Default.Edit, word("编辑输入", "Edit input"), Modifier.size(18.dp))
                    }
                }
            }
            TextButton({ onAction(CabinAction.ReadSelection) },
                Modifier.testTag("cabin-read-selection"), contentPadding = PaddingValues(horizontal = 8.dp)) {
                Text(word("读取选区", "Read selection"))
            }
            if (state.mode == CabinMode.TEMPLATE) Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                TextButton({ onAction(CabinAction.LoadTemplate) }, Modifier.testTag("cabin-load-template")) {
                    Text(word("我的模板", "My template"))
                }
                TextButton({ onAction(CabinAction.SaveTemplate) }, Modifier.testTag("cabin-save-template"),
                    enabled = state.input.isNotBlank() && state.input.length <= ToolCabin.MAX_INPUT) {
                    Text(word("保存模板原文", "Save template"))
                }
            }
            state.problem?.let { problem ->
                Text(problem.label(english), Modifier.testTag("cabin-message"), fontSize = 12.sp, lineHeight = 16.sp,
                    color = if (problem == CabinProblem.SAVED) colors.primary else colors.error)
            }
            if (state.clipboardRequired) {
                Text(word("这个模板会使用剪贴板。确认读取后先显示预览，再由你决定是否插入。",
                    "This template uses the clipboard. Read it to preview first; insertion needs another tap."),
                    fontSize = 12.sp, lineHeight = 17.sp)
                OutlinedButton({ onAction(CabinAction.ConfirmClipboard) }, Modifier.testTag("cabin-confirm-clipboard")) {
                    Text(word("读取剪贴板并预览", "Read clipboard and preview"))
                }
            }
            state.preview?.let { preview ->
                Surface(shape = RoundedCornerShape(12.dp), color = colors.secondaryContainer,
                    modifier = Modifier.fillMaxWidth().testTag("cabin-result")) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(if (state.mode == CabinMode.TEXT) "${state.textTool.label(english)} · ${word("预览", "Preview")}" else
                            word("预览 · 确认后写入", "Preview · insert when ready"), fontSize = 10.sp,
                            color = colors.onSecondaryContainer.copy(alpha = .75f))
                        if (preview.note.isNotBlank()) Text(preview.note, fontSize = 11.sp, color = colors.onSecondaryContainer)
                        Text(buildAnnotatedString {
                            if (state.mode == CabinMode.TEMPLATE) {
                                append(preview.text.take(preview.cursor))
                                withStyle(SpanStyle(color = colors.primary, fontWeight = FontWeight.Bold)) { append('▏') }
                                append(preview.text.drop(preview.cursor))
                            } else append(preview.text)
                        }, fontFamily = FontFamily.Monospace, fontSize = if (state.mode == CabinMode.CALCULATE) 19.sp else 13.sp,
                            lineHeight = if (state.mode == CabinMode.CALCULATE) 24.sp else 19.sp,
                            color = colors.onSecondaryContainer)
                        if (state.mode == CabinMode.TEXT && state.textTool == TextTool.MASK) Text(
                            word("请检查预览，遮罩不保证识别所有敏感信息。", "Review the result. Other private data may remain."),
                            fontSize = 11.sp, lineHeight = 15.sp, color = colors.onSecondaryContainer)
                    }
                }
            }
            if (state.preview == null && state.mode == CabinMode.TEXT && state.textTool == TextTool.MASK) Text(
                word("遮罩常见手机号、身份证样式和邮箱；请检查预览，不保证识别所有敏感信息。",
                    "Masks common phone, ID and email formats. Review the result; other private data may remain."),
                fontSize = 11.sp, lineHeight = 15.sp, color = colors.onSurfaceVariant)
            Spacer(Modifier.height(2.dp))
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton({ onAction(CabinAction.Preview) }, Modifier.weight(1f).height(44.dp).testTag("cabin-preview"),
                enabled = state.input.isNotBlank()) { Text(word("预览", "Preview")) }
            Button({ onAction(CabinAction.Insert) }, Modifier.weight(1f).height(44.dp).testTag("cabin-insert"),
                enabled = state.preview != null && !state.clipboardRequired) {
                Text(if (state.replacesSelection) word("替换选区", "Replace selection") else word("插入结果", "Insert result"), maxLines = 1)
            }
        }
    }
    }
}

@Composable
private fun Presets(values: List<String>, onAction: (CabinAction) -> Unit) {
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        values.forEach { value ->
            SuggestionChip({ onAction(CabinAction.Preset(value)) }, { Text(value, fontSize = 12.sp) })
        }
    }
}
