// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.service

import android.app.Application
import android.view.inputmethod.EditorInfo
import android.widget.EditText
import androidx.test.core.app.ApplicationProvider
import com.kingzcheung.xime.rime.InputCommandQueue
import com.kingzcheung.xime.toolcabin.*
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** A real suspended FIFO action crosses the same generation fence as the cabin's native field. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = Application::class)
class ToolCabinQueueBoundaryTest {
    @Test fun exitingInternalTypingCancelsOldDeliveryButFreshPreviewStillCommits() = runBlocking {
        for (exit in listOf("preview", "close", "mode", "editor")) {
            val gate = InputReadiness().also { it.completeStartup() }
            var state = InputUIState(inputSessionId = 21, toolPanelVisible = true, toolPanelInputFocused = true,
                toolCabin = ToolCabinState(editing = true))
            val field = EditText(ApplicationProvider.getApplicationContext()).apply { setText("前后"); setSelection(1) }
            val ic = field.onCreateInputConnection(EditorInfo())!!
            val editor = ToolCabinEditor({ ic }, { gate.ticket() }, { true }, { field.selectionStart to field.selectionEnd })
            val oldPreview = editor.capture(null).target!!
            val oldOwner = InputCommandOwner(gate.ticket()!!, state.inputSessionId) {}
            val entered = CompletableDeferred<Unit>()
            val release = CompletableDeferred<Unit>()
            val queue = InputCommandQueue(this, Dispatchers.Default)
            var lateWriteAttempted = false
            try {
                val pending = queue.submit(oldOwner.context()) {
                    entered.complete(Unit)
                    release.await()
                    InputCommandOwner.requireOwner().requireCurrent(gate, state.inputSessionId)
                    // This is the old bug: destination resolution happens after suspension.
                    if (state.inputTarget == InputTarget.Host) {
                        lateWriteAttempted = true
                        ic.commitText("private draft", 1)
                    }
                }
                withTimeout(3000) { entered.await() }
                state = gate.finishToolCabinDraft(state)
                state = when (exit) {
                    "close" -> state.copy(toolCabin = null, toolPanelVisible = false)
                    "mode" -> state.copy(toolCabin = ToolCabinState(mode = CabinMode.TEXT))
                    "editor" -> {
                        gate.newEditorSession()
                        state.copy(inputSessionId = 23, toolCabin = null)
                    }
                    else -> state
                }
                release.complete(Unit)
                withTimeout(3000) { pending.join() }
                assertTrue(exit, pending.isCancelled)
                assertFalse(exit, lateWriteAttempted)
                assertEquals(exit, "前后", field.text.toString())
                assertFalse(exit, editor.commit(oldPreview, CabinPreview("stale")).inserted)

                // New work remains usable, including when the old Enter owner was on the caller thread.
                val freshOwner = InputCommandOwner(gate.ticket()!!, state.inputSessionId) {}
                var freshRan = false
                withContext(oldOwner.context()) {
                    val fresh = queue.submit(freshOwner.context()) {
                        assertEquals(freshOwner, InputCommandOwner.requireOwner())
                        InputCommandOwner.requireOwner().requireCurrent(gate, state.inputSessionId)
                        freshRan = true
                    }
                    withTimeout(3000) { fresh.join() }
                }
                assertTrue(exit, freshRan)
                if (exit == "preview") {
                    val preview = (UnitConverter.convert("2.5 MiB → B") as CabinResult.Ready).preview
                    val freshTarget = editor.capture(null).target!!
                    assertTrue(editor.commit(freshTarget, preview).inserted)
                    assertEquals("前2621440 B后", field.text.toString())
                }
            } finally {
                release.complete(Unit)
                queue.close()
            }
        }
    }
}
