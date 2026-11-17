// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.ui.render

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.view.ViewGroup
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.kingzcheung.xime.service.ToolPanelEditTextHolder
import com.kingzcheung.xime.toolcabin.*
import com.kingzcheung.xime.ui.keyboard.ToolCabinPanel
import com.kingzcheung.xime.ui.keyboard.ToolPanel
import com.kingzcheung.xime.ui.theme.XimeTheme
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import java.time.ZonedDateTime

/** Compose and native in-IME EditText rendering. Real host writes are covered in ToolCabinEditorTest. */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [34], application = Application::class, qualifiers = "w360dp-h800dp-xhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ToolCabinRenderTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val now = ZonedDateTime.parse("2026-11-17T08:09:10+08:00")

    private fun capture(name: String) {
        val out = System.getenv("CYIME_RENDER_OUT") ?: return
        rule.waitForIdle()
        val view = rule.activity.window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        rule.runOnIdle {
            // Robolectric has no continuously drawing Window surface for PixelCopy's redraw wait.
            // Invalidate ALL Compose layers before drawing, not only the dirty nodes from the last
            // action; otherwise repeated captures omit cached headers/icons. This is test-only,
            // using the public AndroidComposeView method in the pinned Compose dependency.
            fun invalidateTree(node: View) {
                if (node.javaClass.name == "androidx.compose.ui.platform.AndroidComposeView")
                    node.javaClass.getMethod("invalidateDescendants").invoke(node)
                if (node is ViewGroup) for (index in 0 until node.childCount) invalidateTree(node.getChildAt(index))
                node.invalidate()
            }
            invalidateTree(view)
            view.draw(Canvas(bitmap))
        }
        val file = File(out, "$name.png")
        file.parentFile!!.mkdirs()
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
    }

    @Test fun unitPreviewAndInsertionAreSeparateActionsOnANarrowKeyboard() {
        val state = mutableStateOf(ToolCabinState())
        val dark = mutableStateOf(false)
        var insertions = 0
        rule.setContent {
            XimeTheme(darkTheme = dark.value) {
                Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface)) {
                    ToolCabinPanel(state.value, { action ->
                        when (action) {
                            CabinAction.Preview -> state.value = state.value.copy(preview = (ToolCabin.preview(state.value, now) as CabinResult.Ready).preview)
                            CabinAction.Insert -> insertions++
                            else -> Unit
                        }
                    }, Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(340.dp), english = false)
                }
            }
        }
        rule.onNodeWithTag("cabin-insert").assertIsDisplayed().assertIsNotEnabled()
        capture("lantype-tools-units-overview-light")
        rule.runOnIdle { dark.value = true }
        capture("lantype-tools-units-overview-dark")
        rule.runOnIdle { dark.value = false }
        rule.onNodeWithTag("cabin-preview").performClick()
        rule.onNodeWithTag("cabin-result").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("2621440 B").assertIsDisplayed()
        assertEquals(0, insertions)
        capture("lantype-tools-units-light")
        rule.runOnIdle { dark.value = true }
        capture("lantype-tools-units-dark")
        rule.onNodeWithTag("cabin-insert").assertIsEnabled().performClick()
        assertEquals(1, insertions)
    }

    @Test fun maskPreviewAndStaleSessionHaveClearStates() {
        val input = "13812345678\ndev@example.com"
        val state = mutableStateOf(ToolCabinState(mode = CabinMode.TEXT, input = input, replacesSelection = true,
            preview = (TextTransforms.apply(TextTool.MASK, input) as CabinResult.Ready).preview))
        rule.setContent {
            XimeTheme(darkTheme = false) {
                Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface)) {
                    ToolCabinPanel(state.value, {}, Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(340.dp), english = false)
                }
            }
        }
        capture("lantype-tools-mask-overview")
        rule.onNodeWithTag("cabin-result").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("138****5678\nd***@example.com").assertIsDisplayed()
        rule.onNodeWithText("替换选区").assertIsEnabled()
        capture("lantype-tools-mask")
        rule.runOnIdle { state.value = state.value.copy(preview = null, problem = CabinProblem.SESSION_CHANGED) }
        rule.onNodeWithTag("cabin-insert").assertIsNotEnabled()
        rule.onNodeWithTag("cabin-message").performScrollTo().assertIsDisplayed()
        capture("lantype-tools-stale-editor")
    }

    @Test fun templateUsesVisibleCursorAndClipboardNeedsItsOwnConfirmation() {
        val state = mutableStateOf(ToolCabinState(mode = CabinMode.TEMPLATE, input = ToolCabin.CS_TEMPLATE,
            preview = (DynamicTemplate.expand(ToolCabin.CS_TEMPLATE, now) as CabinResult.Ready).preview))
        var clipboardReads = 0
        var insertions = 0
        rule.setContent {
            XimeTheme(darkTheme = true) {
                Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface)) {
                    ToolCabinPanel(state.value, { action ->
                        when (action) {
                            CabinAction.ConfirmClipboard -> {
                                clipboardReads++
                                state.value = state.value.copy(clipboardRequired = false,
                                    preview = (DynamicTemplate.expand(state.value.input, now, "user-approved text") as CabinResult.Ready).preview)
                            }
                            CabinAction.Insert -> insertions++
                            else -> Unit
                        }
                    }, Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(340.dp), english = true)
                }
            }
        }
        capture("lantype-tools-templates-overview-en")
        rule.onNodeWithTag("cabin-result").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("Debug.Log(\"▏\"); // 2026-11-17").assertIsDisplayed()
        capture("lantype-tools-csharp-en")
        rule.runOnIdle { state.value = state.value.copy(input = ToolCabin.CLIPBOARD_TEMPLATE, preview = null, clipboardRequired = true) }
        rule.onNodeWithTag("cabin-insert").assertIsNotEnabled()
        assertEquals(0, clipboardReads)
        rule.onNodeWithTag("cabin-confirm-clipboard").performScrollTo().assertIsDisplayed()
        capture("lantype-tools-clipboard-confirm")
        rule.onNodeWithTag("cabin-confirm-clipboard").performClick()
        assertEquals(1, clipboardReads)
        assertEquals(0, insertions)
        rule.onNodeWithTag("cabin-insert").assertIsEnabled().performClick()
        assertEquals(1, insertions)
    }

    @Test fun editModeExposesTheNativeFieldUsedByTheExistingKeyboardRoute() {
        val draft = mutableStateOf("2.5 MiB → B")
        rule.setContent {
            XimeTheme(darkTheme = false) {
                ToolPanel(title = "工具舱", isFocused = true, isLoading = false, initialText = draft.value,
                    backgroundColor = Color.White, textColor = Color.Black, accentColor = Color.Blue,
                    cardBgColor = Color.LightGray, onClose = {}, onFocusChange = {},
                    onTextChange = { draft.value = it }, actionLabel = "预览", statusText = "回车只生成预览，不会写入应用。")
            }
        }
        rule.waitForIdle()
        rule.runOnIdle {
            val field = ToolPanelEditTextHolder.editText!!
            assertEquals("2.5 MiB → B", field.text.toString())
            assertTrue(field.hasFocus())
            field.setSelection(0, 3)
            field.text.replace(field.selectionStart, field.selectionEnd, "8")
            assertEquals("8 MiB → B", draft.value)
        }
        rule.waitForIdle()
        rule.runOnIdle { assertEquals("8 MiB → B", ToolPanelEditTextHolder.editText!!.text.toString()) }
        capture("lantype-tools-native-draft")
        rule.runOnIdle { ToolPanelEditTextHolder.editText = null }
    }

    @Test fun shortEnglishPanelKeepsNavigationAndExplicitInsertionReachable() {
        val state = ToolCabinState(mode = CabinMode.TEMPLATE, input = ToolCabin.CS_TEMPLATE,
            preview = (DynamicTemplate.expand(ToolCabin.CS_TEMPLATE, now) as CabinResult.Ready).preview)
        rule.setContent {
            XimeTheme(darkTheme = true) {
                Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface)) {
                    ToolCabinPanel(state, {}, Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(220.dp), english = true)
                }
            }
        }
        rule.onNodeWithTag("cabin-close").assertIsDisplayed()
        rule.onNodeWithTag("cabin-mode:CALCULATE").assertIsDisplayed()
        rule.onNodeWithTag("cabin-mode:TEMPLATE").assertIsDisplayed()
        rule.onNodeWithTag("cabin-result").performScrollTo().assertIsDisplayed()
        rule.onNodeWithTag("cabin-preview").assertIsDisplayed().assertIsEnabled()
        rule.onNodeWithTag("cabin-insert").assertIsDisplayed().assertIsEnabled()
        capture("lantype-tools-short-en")
    }
}
