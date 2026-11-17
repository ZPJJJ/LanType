package com.kingzcheung.xime.service

import android.text.InputType
import android.view.inputmethod.EditorInfo
import com.kingzcheung.xime.settings.IncognitoState
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InputPrivacyTest {
    private val saved = Triple(IncognitoState.manual, IncognitoState.sensitiveEditor, IncognitoState.clipboardSearch)
    private val savedPasswordField = IncognitoState.passwordField
    private val savedToolCabin = IncognitoState.toolCabin
    private val engine = mutableListOf<Boolean>()
    private val privacy = InputPrivacy(toolCabinBoundary = {}) { engine += it }.also {
        it.loadManual(false)
        IncognitoState.sensitiveEditor = false
        IncognitoState.clipboardSearch = false
        IncognitoState.toolCabin = false
    }

    @After fun restore() {
        IncognitoState.manual = saved.first
        IncognitoState.sensitiveEditor = saved.second
        IncognitoState.clipboardSearch = saved.third
        IncognitoState.passwordField = savedPasswordField
        IncognitoState.toolCabin = savedToolCabin
    }

    private fun field(inputType: Int, imeOptions: Int = 0) =
        EditorInfo().apply { this.inputType = inputType; this.imeOptions = imeOptions }
    private val text = InputType.TYPE_CLASS_TEXT
    private val password = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD

    @Test fun theEngineFollowsEveryFieldOnceWithoutRepeats() {
        privacy.beginEditor(field(text))
        privacy.beginEditor(field(text))
        privacy.beginEditor(field(password))
        privacy.beginEditor(field(InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD))
        privacy.beginEditor(field(text, EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING))
        privacy.beginEditor(field(text))
        assertEquals(listOf(false, true, false), engine)
    }

    @Test fun searchOpenedInAPasswordFieldKeepsItPrivateAfterClosing() {
        privacy.beginEditor(field(password))
        privacy.setClipboardSearch(true)
        privacy.setClipboardSearch(false)
        assertTrue(IncognitoState.active)
        assertEquals(listOf(true), engine)
    }

    @Test fun aFieldChangeDuringSearchIsNotUndoneWhenSearchCloses() {
        privacy.beginEditor(field(text))
        privacy.setClipboardSearch(true)
        privacy.beginEditor(field(password))
        privacy.setClipboardSearch(false)
        assertTrue(IncognitoState.active)
        // And back: a normal field learns again once search closes.
        privacy.setClipboardSearch(true)
        privacy.beginEditor(field(text))
        privacy.setClipboardSearch(false)
        assertFalse(IncognitoState.active)
        assertEquals(listOf(false, true, false), engine)
    }

    @Test fun theManualSwitchDuringSearchOutlivesIt() {
        privacy.beginEditor(field(text))
        privacy.setClipboardSearch(true)
        privacy.setManual(true)
        privacy.setClipboardSearch(false)
        assertTrue(IncognitoState.active)
        privacy.setManual(false)
        assertEquals(listOf(false, true, false), engine)
    }

    @Test fun theSavedSwitchWaitsForTheFirstField() {
        privacy.loadManual(true)
        assertTrue(engine.isEmpty())
        privacy.beginEditor(field(text))
        assertEquals(listOf(true), engine)
    }

    @Test fun closingCabinDoesNotDisableManualOrNewPasswordFieldPrivacy() {
        privacy.beginEditor(field(text))
        privacy.setToolCabin(true)
        assertTrue(IncognitoState.active)
        privacy.beginEditor(field(password))
        privacy.setManual(true)
        privacy.setToolCabin(false)
        assertFalse(IncognitoState.toolCabin)
        assertTrue(IncognitoState.active)
        privacy.beginEditor(field(text))
        assertTrue(IncognitoState.active)
        privacy.setManual(false)
        assertFalse(IncognitoState.active)
        assertEquals(listOf(false, true, false), engine)
    }

    @Test fun cabinAndClipboardSearchReleaseTheirOwnSourceIndependently() {
        privacy.beginEditor(field(text))
        privacy.setClipboardSearch(true)
        privacy.setToolCabin(true)
        privacy.setClipboardSearch(false)
        assertTrue(IncognitoState.active)
        privacy.beginEditor(field(text))
        assertTrue(IncognitoState.active)
        privacy.setToolCabin(false)
        privacy.setToolCabin(false) // Close after an exception or a later lifecycle callback is idempotent.
        assertFalse(IncognitoState.active)
        assertEquals(listOf(false, true, false), engine)
    }

    @Test fun cabinCloseMarksClipboardBeforeItsPrivacyFlagIsCleared() {
        val boundaries = mutableListOf<Pair<Boolean, Boolean>>()
        val observed = InputPrivacy(toolCabinBoundary = { open ->
            boundaries += open to IncognitoState.toolCabin
        }) {}
        observed.setToolCabin(true)
        observed.setToolCabin(false)
        assertEquals(listOf(true to false, false to true), boundaries)
        assertFalse(IncognitoState.toolCabin)
    }

    /** 用户 11-09：网页上复制的普通文字被当成密码。剪贴板只认开着的藏字密码框。 */
    @Test fun clipboardCountsOnlyAnOpenHiddenPasswordField() {
        privacy.beginEditor(field(text, EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING))
        assertTrue(IncognitoState.active)
        assertFalse(IncognitoState.passwordField)
        privacy.beginEditor(field(InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD))
        assertFalse(IncognitoState.passwordField)
        privacy.beginEditor(field(InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD))
        assertTrue(IncognitoState.passwordField)
        privacy.beginEditor(field(InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD))
        assertTrue(IncognitoState.passwordField)
        privacy.beginEditor(field(password))
        assertTrue(IncognitoState.passwordField)
        // Leaving the field: a copy made on a web page afterwards is not from a password field.
        privacy.endEditor()
        assertFalse(IncognitoState.passwordField)
        assertTrue(IncognitoState.active)
    }
}
