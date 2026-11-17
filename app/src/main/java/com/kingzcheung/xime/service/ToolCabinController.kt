// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.service

import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import com.kingzcheung.xime.keyboard.OverlayRoute
import com.kingzcheung.xime.toolcabin.*
import java.time.ZonedDateTime

/** Built-in offline tool, deliberately separate from plugins and their context/learning pipeline. */
internal class ToolCabinController(private val service: XimeInputMethodService) {
    private var admission: Long? = null
    private var selected: ToolCabinEditor.Selected? = null
    private var target: ToolCabinEditor.Target? = null
    private val editor = ToolCabinEditor({ service.currentInputConnection }, { service.inputReadiness.ticket() },
        { !service.isSecretEditor() && !service.isEditorRestricted() }, { service.toolCabinHostSelection },
        { service.candidateState.value.hasToolCabinComposition() })
    private val english get() = service.resources.configuration.locales[0].language == "en"
    private val state get() = service.uiState.value.toolCabin

    fun open() {
        if (state != null) { service.closeToolPanel(); return }
        if (service.isSecretEditor() || service.isEditorRestricted() || service.currentInputConnection == null ||
            service.inputReadiness.ticket() == null) { toast(CabinProblem.EDITOR_UNAVAILABLE); return }
        if (service.candidateState.value.hasToolCabinComposition()) {
            toast(CabinProblem.FINISH_COMPOSITION); return
        }
        service.closeToolPanel()
        service.closeQuickSend()
        if (service.uiState.value.clipboardSearchVisible) service.closeClipboardSearch(openBoard = false)
        admission = service.inputReadiness.ticket()
        try {
            service.privacy.setToolCabin(true)
            service.predictionManager.invalidatePendingPredictions()
            service.candidateState.value = service.candidateState.value.copy(associationCandidates = emptyList(), pendingEnglishText = "")
            service.uiState.value = service.uiState.value.copy(toolCabin = ToolCabinState(), toolPanelVisible = true,
                toolPanelInputFocused = false, toolPanelDisplay = "PASSIVE", toolPanelPluginId = "",
                toolPanelTitle = if (english) "Tool cabin" else "工具舱")
            service.keyboardViewModel.showOverlay(OverlayRoute.ToolPanel)
        } catch (_: RuntimeException) {
            service.privacy.setToolCabin(false)
            service.closeToolPanel()
            toast(CabinProblem.EDITOR_UNAVAILABLE)
        }
    }

    fun clear() { admission = null; selected = null; target = null }

    fun hostSelectionChanged(start: Int, end: Int) {
        val range = minOf(start, end) to maxOf(start, end)
        val moved = target?.let { range != (it.start to it.end) } == true ||
            selected?.let { range != (it.start to it.end) } == true
        if (moved && state != null) {
            selected = null; target = null
            update { it.copy(preview = null, replacesSelection = false, problem = CabinProblem.SELECTION_CHANGED) }
        }
    }

    fun action(action: CabinAction) {
        val current = state ?: return
        if (action == CabinAction.Close) { service.closeToolPanel(); return }
        if (admission?.let(service.inputReadiness::accepts) != true) {
            update { it.copy(preview = null, problem = CabinProblem.SESSION_CHANGED) }; target = null; return
        }
        if (service.isSecretEditor() || service.isEditorRestricted() || service.currentInputConnection == null) {
            update { it.copy(preview = null, problem = CabinProblem.EDITOR_UNAVAILABLE) }; target = null; return
        }
        when (action) {
            is CabinAction.Mode -> {
                leaveEditing()
                selected = null; target = null
                val input = when (action.value) {
                    CabinMode.CALCULATE -> "2.5 MiB → B"
                    CabinMode.TEXT -> ""
                    CabinMode.TEMPLATE -> ToolCabin.CS_TEMPLATE
                }
                update { ToolCabinState(mode = action.value, input = input) }
                service.keyboardViewModel.showOverlay(OverlayRoute.ToolPanel)
            }
            is CabinAction.Operation -> { invalidate(); update { it.copy(textTool = action.value, preview = null, problem = null) } }
            is CabinAction.Preset -> {
                selected = null; invalidate()
                update { it.copy(input = action.value, preview = null, problem = null, replacesSelection = false, clipboardRequired = false) }
            }
            is CabinAction.Input -> {
                invalidate()
                update { it.copy(input = action.value, preview = null,
                    problem = CabinProblem.TOO_LONG.takeIf { action.value.length > ToolCabin.MAX_INPUT }, clipboardRequired = false) }
            }
            CabinAction.Edit -> {
                invalidate()
                update { it.copy(editing = true, preview = null, problem = null) }
                service.uiState.value = service.uiState.value.copy(toolPanelInputFocused = true,
                    toolPanelDisplay = EDITING_DISPLAY, toolPanelPrefillText = current.input,
                    enterKeyText = if (english) "Preview" else "预览")
                service.keyboardViewModel.closeOverlay()
            }
            CabinAction.Preview -> preview()
            CabinAction.ReadSelection -> {
                val read = editor.readSelection()
                invalidate(); selected = read.selected
                update { it.copy(input = read.selected?.text ?: it.input, preview = null,
                    replacesSelection = read.selected != null, problem = read.problem, clipboardRequired = false) }
            }
            CabinAction.ConfirmClipboard -> {
                if (!current.clipboardRequired || current.mode != CabinMode.TEMPLATE) return
                // This is the sole clipboard read. It only runs after the explicitly labelled confirmation button.
                val clipboard = service.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                val text = runCatching { clipboard?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.text?.toString() }.getOrNull()
                if (text == null) update { it.copy(problem = CabinProblem.NO_CLIPBOARD) }
                else preview(text)
            }
            CabinAction.Insert -> {
                val preview = current.preview ?: return
                val destination = target ?: return
                val result = editor.commit(destination, preview)
                if (result.inserted) {
                    service.predictionManager.invalidatePendingPredictions()
                    service.predictionManager.clearCommittedText()
                    service.closeToolPanel()
                    result.problem?.let(::toast)
                } else if (result.problem == CabinProblem.FINISH_COMPOSITION ||
                    result.problem == CabinProblem.SELECTION_CHANGED || result.problem == CabinProblem.SESSION_CHANGED) {
                    invalidate(); update { it.copy(preview = null, problem = result.problem) }
                } else update { it.copy(problem = result.problem) }
            }
            CabinAction.LoadTemplate -> {
                val saved = preferences().getString("custom_template", ToolCabin.NOTE_TEMPLATE).orEmpty()
                selected = null; invalidate()
                update { it.copy(input = saved, preview = null, problem = null, replacesSelection = false, clipboardRequired = false) }
            }
            CabinAction.SaveTemplate -> {
                if (current.mode == CabinMode.TEMPLATE && current.input.isNotBlank() && current.input.length <= ToolCabin.MAX_INPUT) {
                    preferences().edit().putString("custom_template", current.input).apply()
                    update { it.copy(problem = CabinProblem.SAVED) }
                }
            }
            CabinAction.Close -> Unit
        }
    }

    private fun preview(clipboard: String? = null) {
        val current = state ?: return
        if (service.candidateState.value.hasToolCabinComposition()) {
            invalidate(); update { it.copy(preview = null, problem = CabinProblem.FINISH_COMPOSITION) }; return
        }
        // Invalidate queued internal typing before capturing a target under the new admission.
        leaveEditing()
        invalidate()
        val result = ToolCabin.preview(current, ZonedDateTime.now(), clipboard)
        when (result) {
            is CabinResult.Ready -> {
                val captured = editor.capture(selected)
                target = captured.target
                update { it.copy(preview = result.preview.takeIf { captured.target != null },
                    problem = captured.problem, clipboardRequired = false, editing = false) }
            }
            is CabinResult.Failed -> update { it.copy(preview = null, problem = result.problem, clipboardRequired = false, editing = false) }
            CabinResult.ClipboardRequired -> update { it.copy(preview = null, problem = null, clipboardRequired = true, editing = false) }
        }
        service.uiState.value = service.uiState.value.copy(toolPanelInputFocused = false, toolPanelDisplay = "PASSIVE")
        ToolPanelEditTextHolder.editText?.clearFocus()
        service.keyboardViewModel.showOverlay(OverlayRoute.ToolPanel)
    }

    private fun invalidate() { target = null }
    private fun leaveEditing() {
        if (state?.editing != true) return
        service.finishToolCabinEditing()
        admission = service.inputReadiness.ticket()
    }
    private fun update(change: (ToolCabinState) -> ToolCabinState) {
        val current = state ?: return
        service.uiState.value = service.uiState.value.copy(toolCabin = change(current))
    }
    private fun preferences() = service.getSharedPreferences("lantype_tool_cabin", Context.MODE_PRIVATE)
    private fun toast(problem: CabinProblem) = Toast.makeText(service, problem.label(english), Toast.LENGTH_SHORT).show()

    companion object { const val EDITING_DISPLAY = "LANTYPE_CABIN_EDIT" }
}
