// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.service

import android.view.inputmethod.InputConnection
import com.kingzcheung.xime.toolcabin.CabinPreview
import com.kingzcheung.xime.toolcabin.CabinProblem
import com.kingzcheung.xime.toolcabin.ToolCabin

/** Rechecked immediately before writing: a keyboard/hardware draft may appear after preview. */
internal fun CandidateState.hasToolCabinComposition(): Boolean = isComposing || inputText.isNotEmpty() ||
    preeditText.isNotEmpty() || pendingEnglishText.isNotEmpty()

/** End the internal typing destination before exposing the host again. Old queued owners expire. */
internal fun InputReadiness.finishToolCabinDraft(state: InputUIState): InputUIState {
    newEditorSession()
    return state.copy(inputSessionId = state.inputSessionId + 1,
        toolPanelInputFocused = false, toolPanelDisplay = "PASSIVE",
        toolCabin = state.toolCabin?.copy(editing = false))
}

/** Reads only a user-selected range, never surrounding/full-field text. All methods run on Main. */
internal class ToolCabinEditor(
    private val connection: () -> InputConnection?,
    private val admission: () -> Long?,
    private val permitted: () -> Boolean,
    private val selection: () -> Pair<Int, Int>?,
    private val composing: () -> Boolean = { false },
) {
    data class Selected(val text: String, val start: Int, val end: Int)
    data class Target(val connection: InputConnection, val admission: Long, val start: Int, val end: Int,
        val original: String?)
    data class Read(val selected: Selected? = null, val problem: CabinProblem? = null)
    data class Capture(val target: Target? = null, val problem: CabinProblem? = null)
    data class Write(val inserted: Boolean, val problem: CabinProblem? = null)

    private fun range(): Pair<Int, Int>? = selection()?.takeIf { it.first >= 0 && it.second >= 0 }
        ?.let { minOf(it.first, it.second) to maxOf(it.first, it.second) }

    fun readSelection(): Read {
        if (!permitted() || admission() == null) return Read(problem = CabinProblem.EDITOR_UNAVAILABLE)
        val ic = connection() ?: return Read(problem = CabinProblem.EDITOR_UNAVAILABLE)
        val range = range() ?: return Read(problem = CabinProblem.NO_SELECTION)
        if (range.first == range.second) return Read(problem = CabinProblem.NO_SELECTION)
        if (range.second - range.first > ToolCabin.MAX_INPUT) return Read(problem = CabinProblem.TOO_LONG)
        val text = runCatching { raw(ic).getSelectedText(0)?.toString() }.getOrNull()
            ?: return Read(problem = CabinProblem.NO_SELECTION)
        if (text.length != range.second - range.first) return Read(problem = CabinProblem.SELECTION_CHANGED)
        return Read(Selected(text, range.first, range.second))
    }

    fun capture(original: Selected?): Capture {
        if (!permitted()) return Capture(problem = CabinProblem.EDITOR_UNAVAILABLE)
        if (composing()) return Capture(problem = CabinProblem.FINISH_COMPOSITION)
        val token = admission() ?: return Capture(problem = CabinProblem.EDITOR_UNAVAILABLE)
        val ic = connection() ?: return Capture(problem = CabinProblem.EDITOR_UNAVAILABLE)
        val range = range() ?: return Capture(problem = CabinProblem.EDITOR_UNAVAILABLE)
        if (original != null && (range.first != original.start || range.second != original.end))
            return Capture(problem = CabinProblem.SELECTION_CHANGED)
        if (original == null && range.first != range.second)
            return Capture(problem = CabinProblem.SELECTED_TEXT_UNREAD)
        return Capture(Target(ic, token, range.first, range.second, original?.text))
    }

    fun commit(target: Target, preview: CabinPreview): Write {
        if (!permitted()) return Write(false, CabinProblem.EDITOR_UNAVAILABLE)
        if (composing()) return Write(false, CabinProblem.FINISH_COMPOSITION)
        val ic = connection()
        if (ic == null || admission() != target.admission || ic !== target.connection)
            return Write(false, CabinProblem.SESSION_CHANGED)
        if (range() != (target.start to target.end)) return Write(false, CabinProblem.SELECTION_CHANGED)
        if (preview.text.length > ToolCabin.MAX_OUTPUT || preview.cursor !in 0..preview.text.length ||
            (preview.cursor in 1 until preview.text.length && preview.text[preview.cursor - 1].isHighSurrogate() &&
                preview.text[preview.cursor].isLowSurrogate())) return Write(false, CabinProblem.INVALID_VALUE)
        val host = raw(ic)
        var inserted = false
        var batchStarted = false
        return try {
            // Verify only the selected source explicitly read by the user; never fetch surrounding text.
            if (target.original != null && host.getSelectedText(0)?.toString() != target.original)
                return Write(false, CabinProblem.SELECTION_CHANGED)
            batchStarted = host.beginBatchEdit()
            inserted = host.commitText(preview.text, 1)
            if (!inserted) return Write(false, CabinProblem.EDITOR_REJECTED)
            (ic as? TrackedInputConnection)?.memory?.edited()
            val cursorAccepted = preview.cursor == preview.text.length ||
                host.setSelection(target.start + preview.cursor, target.start + preview.cursor)
            Write(true, if (cursorAccepted) null else CabinProblem.INSERTED_CURSOR_UNAVAILABLE)
        } catch (_: RuntimeException) {
            // A cursor failure after a successful commit must never invite a duplicate retry.
            Write(inserted, if (inserted) CabinProblem.INSERTED_CURSOR_UNAVAILABLE else CabinProblem.EDITOR_REJECTED)
        } finally {
            if (batchStarted) runCatching { host.endBatchEdit() }
        }
    }

    private fun raw(ic: InputConnection): InputConnection = (ic as? TrackedInputConnection)?.base ?: ic
}
