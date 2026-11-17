// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.service

import android.app.Application
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.ExtractedTextRequest
import android.view.inputmethod.InputConnection
import android.view.inputmethod.InputConnectionWrapper
import android.widget.EditText
import androidx.test.core.app.ApplicationProvider
import com.kingzcheung.xime.toolcabin.*
import java.time.ZonedDateTime
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Real editable host connections: no mock can silently accept a write without changing the text. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [30, 34], application = Application::class)
class ToolCabinEditorTest {
    private class Host(text: String = "前后", caret: Int = 1) {
        val view = EditText(ApplicationProvider.getApplicationContext()).apply { setText(text); setSelection(caret) }
        var selectedReads = 0
        var writes = 0
        var allowed = true
        var token: Long? = 7L
        var candidateState = CandidateState()
        var connection: InputConnection? = object : InputConnectionWrapper(view.onCreateInputConnection(EditorInfo()), false) {
            override fun getSelectedText(flags: Int): CharSequence? { selectedReads++; return super.getSelectedText(flags) }
            override fun getTextBeforeCursor(length: Int, flags: Int): CharSequence? = error("Do not read unselected text")
            override fun getTextAfterCursor(length: Int, flags: Int): CharSequence? = error("Do not read unselected text")
            override fun getExtractedText(request: ExtractedTextRequest?, flags: Int) = error("Do not collect the field")
            override fun commitText(text: CharSequence?, newCursorPosition: Int): Boolean {
                writes++; return super.commitText(text, newCursorPosition)
            }
        }
        val editor = ToolCabinEditor({ connection }, { token }, { allowed }, { view.selectionStart to view.selectionEnd },
            { candidateState.hasToolCabinComposition() })
    }

    @Test fun previewAndTargetCaptureNeverReadOrWriteTheHost() {
        val host = Host()
        val preview = (UnitConverter.convert("2.5 MiB → B") as CabinResult.Ready).preview
        val target = host.editor.capture(null).target!!
        assertEquals("前后", host.view.text.toString())
        assertEquals(0, host.selectedReads)
        assertEquals(0, host.writes)
        assertTrue(host.editor.commit(target, preview).inserted)
        assertEquals("前2621440 B后", host.view.text.toString())
        assertEquals(0, host.selectedReads)
        assertEquals(1, host.writes)
    }

    @Test fun explicitlyReadSelectionCanBeReplacedWithoutTouchingItsNeighbors() {
        val source = "13812345678 dev@example.com"
        val host = Host("[${source}]", 1)
        host.view.setSelection(1, source.length + 1)
        assertEquals(CabinProblem.SELECTED_TEXT_UNREAD, host.editor.capture(null).problem)
        assertEquals(0, host.selectedReads)
        val selected = host.editor.readSelection().selected!!
        assertEquals(source, selected.text)
        val preview = (TextTransforms.apply(TextTool.MASK, selected.text) as CabinResult.Ready).preview
        val target = host.editor.capture(selected).target!!
        assertEquals("[${source}]", host.view.text.toString())
        assertTrue(host.editor.commit(target, preview).inserted)
        assertEquals("[138****5678 d***@example.com]", host.view.text.toString())
        assertEquals(2, host.selectedReads) // Explicit read, then verify that same selection before replacing it.
    }

    @Test fun cSharpTemplateCursorGoesInsideTheQuotesInTheActualEditor() {
        val host = Host()
        val preview = (DynamicTemplate.expand(ToolCabin.CS_TEMPLATE,
            ZonedDateTime.parse("2026-11-17T08:09:10Z")) as CabinResult.Ready).preview
        assertTrue(host.editor.commit(host.editor.capture(null).target!!, preview).inserted)
        assertEquals(1 + "Debug.Log(\"".length, host.view.selectionStart)
        host.connection!!.commitText("hello", 1)
        assertEquals("前Debug.Log(\"hello\"); // 2026-11-17后", host.view.text.toString())
    }

    @Test fun switchedSessionOrConnectionRejectsOldPreview() {
        val host = Host()
        val old = host.editor.capture(null).target!!
        host.token = 8L
        assertEquals(CabinProblem.SESSION_CHANGED, host.editor.commit(old, CabinPreview("x")).problem)
        host.token = 7L
        host.connection = InputConnectionWrapper(host.connection, false)
        assertEquals(CabinProblem.SESSION_CHANGED, host.editor.commit(old, CabinPreview("x")).problem)
        assertEquals("前后", host.view.text.toString())
        assertEquals(0, host.writes)
    }

    @Test fun compositionStartedAfterPreviewCannotBeReplacedByAToolResult() {
        for (draft in listOf(CandidateState(isComposing = true), CandidateState(inputText = "ni"),
            CandidateState(preeditText = "nǐ"), CandidateState(pendingEnglishText = "hel"))) {
            val host = Host()
            val target = host.editor.capture(null).target!!
            host.candidateState = draft
            assertEquals(CabinProblem.FINISH_COMPOSITION, host.editor.commit(target, CabinPreview("wrong")).problem)
            assertEquals("前后", host.view.text.toString())
            assertEquals(0, host.writes)
            assertEquals(0, host.selectedReads)
        }
    }

    @Test fun movingTheCaretAfterPreviewDoesNotInsertAtAnUnexpectedPosition() {
        val host = Host()
        val target = host.editor.capture(null).target!!
        host.view.setSelection(2)
        assertEquals(CabinProblem.SELECTION_CHANGED, host.editor.commit(target, CabinPreview("x")).problem)
        assertEquals("前后", host.view.text.toString())
        assertEquals(0, host.writes)
    }

    @Test fun changedSelectedTextWithTheSameRangeCannotBeOverwritten() {
        val host = Host("[one]", 1)
        host.view.setSelection(1, 4)
        val selected = host.editor.readSelection().selected!!
        val target = host.editor.capture(selected).target!!
        host.view.setText("[two]"); host.view.setSelection(1, 4)
        assertEquals(CabinProblem.SELECTION_CHANGED, host.editor.commit(target, CabinPreview("masked")).problem)
        assertEquals("[two]", host.view.text.toString())
        assertEquals(0, host.writes)
    }

    @Test fun restrictedOrDisconnectedEditorsAreNotReadAndCannotAcceptResults() {
        val host = Host("sensitive", 0)
        val target = host.editor.capture(null).target!!
        host.view.setSelection(0, 9)
        host.allowed = false
        assertEquals(CabinProblem.EDITOR_UNAVAILABLE, host.editor.readSelection().problem)
        assertEquals(CabinProblem.EDITOR_UNAVAILABLE, host.editor.capture(null).problem)
        assertFalse(host.editor.commit(target, CabinPreview("x")).inserted)
        host.allowed = true; host.token = null
        assertEquals(CabinProblem.EDITOR_UNAVAILABLE, host.editor.readSelection().problem)
        host.token = 7; host.connection = null
        assertEquals(CabinProblem.EDITOR_UNAVAILABLE, host.editor.capture(null).problem)
        assertEquals(0, host.selectedReads)
        assertEquals(0, host.writes)
    }

    @Test fun rejectedInsertionPreservesTheHostAndAllowsTheUserToKeepThePreview() {
        val host = Host()
        host.connection = object : InputConnectionWrapper(host.connection, false) {
            override fun commitText(text: CharSequence?, newCursorPosition: Int) = false
        }
        val result = host.editor.commit(host.editor.capture(null).target!!, CabinPreview("x"))
        assertFalse(result.inserted)
        assertEquals(CabinProblem.EDITOR_REJECTED, result.problem)
        assertEquals("前后", host.view.text.toString())
    }

    @Test fun cursorOrBatchFailureAfterACommitDoesNotInviteDuplicateInsertion() {
        val host = Host()
        host.connection = object : InputConnectionWrapper(host.connection, false) {
            override fun setSelection(start: Int, end: Int): Boolean = throw IllegalStateException("editor gone")
            override fun endBatchEdit(): Boolean { super.endBatchEdit(); throw IllegalStateException("batch gone") }
        }
        val result = host.editor.commit(host.editor.capture(null).target!!, CabinPreview("()", cursor = 1))
        assertTrue(result.inserted)
        assertEquals(CabinProblem.INSERTED_CURSOR_UNAVAILABLE, result.problem)
        assertEquals("前()后", host.view.text.toString())
        assertEquals(1, host.writes)
    }

    @Test fun invalidSurrogateCursorAndExcessiveOutputAreRejectedBeforeWriting() {
        val host = Host()
        val target = host.editor.capture(null).target!!
        assertFalse(host.editor.commit(target, CabinPreview("🙂", cursor = 1)).inserted)
        assertFalse(host.editor.commit(target, CabinPreview("x".repeat(ToolCabin.MAX_OUTPUT + 1))).inserted)
        assertEquals(0, host.writes)
    }

    @Test fun typingStaysInTheCabinWhenItsNativeFieldTemporarilyLosesFocus() {
        val state = InputUIState(toolCabin = ToolCabinState(editing = true), toolPanelInputFocused = true)
        assertTrue(state.toolPanelFocusAfter(false))
        assertEquals(InputTarget.ToolPanel, state.copy(toolPanelInputFocused = state.toolPanelFocusAfter(false)).inputTarget)
        assertEquals(InputTarget.Host, state.copy(toolCabin = null, toolPanelInputFocused = false).inputTarget)
    }
}
