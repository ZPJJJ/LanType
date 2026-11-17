package com.kingzcheung.xime.speech

import android.content.Context
import android.content.SharedPreferences
import com.kingzcheung.xime.service.AsrInferenceClient
import com.kingzcheung.xime.settings.InputLanguage
import com.kingzcheung.xime.settings.SettingsPreferences
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.mockito.Mockito.mockConstruction
import org.mockito.kotlin.*

/** The backend and resident cache are real; IPC, native inference and storage selection are mocked. */
class OfflineWhisperLanguageSwitchTest {
    @get:Rule val temporaryFolder = TemporaryFolder()

    @Test fun whisperSwitchRestartsInTheNewLanguageEvenWhenTheSelectedModelIsUnchanged() = withBackend { backend, client ->
        assertTrue(backend.prepareForRecording(InputLanguage.CHINESE))
        assertFalse(backend.canContinueIn(InputLanguage.CHINESE))
        assertTrue(backend.start(InputLanguage.CHINESE))
        assertTrue(backend.canContinueIn(InputLanguage.CHINESE))
        assertFalse(backend.canContinueIn(InputLanguage.ENGLISH))

        backend.stop()
        assertTrue(backend.start(InputLanguage.ENGLISH))
        assertTrue(backend.canContinueIn(InputLanguage.ENGLISH))
        assertFalse(backend.canContinueIn(InputLanguage.CHINESE))

        backend.stop()
        assertTrue(backend.start(InputLanguage.CHINESE))
        assertTrue(backend.canContinueIn(InputLanguage.CHINESE))
        assertFalse(backend.canContinueIn(InputLanguage.ENGLISH))

        val languages = argumentCaptor<InputLanguage>()
        runBlocking {
            verify(client, times(3)).startAsr(eq(SpeechModelCatalog.WHISPER), any(), languages.capture())
            verify(client, times(2)).stopAsr()
        }
        assertEquals(listOf(InputLanguage.CHINESE, InputLanguage.ENGLISH, InputLanguage.CHINESE), languages.allValues)
    }

    @Test fun failedRemoteStartDoesNotKeepThePreviousWhisperConfigurationReusable() = withBackend { backend, client ->
        assertTrue(backend.prepareForRecording(InputLanguage.CHINESE))
        assertTrue(backend.start(InputLanguage.CHINESE))
        backend.stop()
        runBlocking { whenever(client.startAsr(any(), any(), anyOrNull())).thenReturn(false) }

        assertFalse(backend.start(InputLanguage.ENGLISH))
        assertFalse(backend.canContinueIn(InputLanguage.CHINESE))
        assertFalse(backend.canContinueIn(InputLanguage.ENGLISH))
    }

    @Test fun failedBindingDoesNotKeepThePreviousWhisperConfigurationReusable() = withBackend { backend, client ->
        assertTrue(backend.prepareForRecording(InputLanguage.ENGLISH))
        assertTrue(backend.start(InputLanguage.ENGLISH))
        backend.stop()
        runBlocking { whenever(client.ensureBound()).thenReturn(false) }

        assertFalse(backend.start(InputLanguage.CHINESE))
        assertFalse(backend.canContinueIn(InputLanguage.CHINESE))
        assertFalse(backend.canContinueIn(InputLanguage.ENGLISH))
    }

    @Test fun explicitlyUnloadedWhisperCannotContinueInItsPreviousLanguage() = withBackend { backend, _ ->
        assertTrue(backend.prepareForRecording(InputLanguage.ENGLISH))
        assertTrue(backend.start(InputLanguage.ENGLISH))
        backend.releaseModel()

        assertFalse(backend.canContinueIn(InputLanguage.ENGLISH))
        assertFalse(backend.canContinueIn(InputLanguage.CHINESE))
        assertFalse(backend.start(InputLanguage.ENGLISH))
    }

    @Test fun serviceCacheReplacesWhisperForAnotherLanguageAndReusesItForTheSameLanguage() {
        val modelDir = temporaryFolder.newFolder("whisper-base")
        AsrModelManager.DEFAULT_MODEL.files.forEach { name -> modelDir.resolve(name).writeText("fixture") }
        val chinese = AsrModelManager.Selection(
            mode = SpeechModelCatalog.WHISPER,
            first = AsrModelManager.DEFAULT_MODEL,
            firstDir = modelDir,
            secondDir = null,
            recognitionLanguage = "zh",
        )
        val english = chinese.copy(recognitionLanguage = "en")
        assertNotEquals("The same weights with another language must have another resident key", chinese.key, english.key)

        val owner = ResidentSpeechSessionOwner { it() }
        val chineseEngine = mock<LocalSpeechEngine>()
        val englishEngine = mock<LocalSpeechEngine>()
        val usedEngines = mutableListOf<LocalSpeechEngine>()
        val createSession: (LocalSpeechEngine) -> ResidentSession = { engine ->
            usedEngines += engine
            mock()
        }
        try {
            assertTrue(owner.start(chinese.key, { chineseEngine }, createSession))
            assertTrue(owner.start(english.key, { englishEngine }, createSession))
            verify(chineseEngine).close()
            assertTrue(owner.start(english.copy().key, { error("Same-language weights should stay resident") }, createSession))
            assertEquals(listOf(chineseEngine, englishEngine, englishEngine), usedEngines)
            verify(englishEngine, never()).close()
        } finally {
            owner.release()
        }
        verify(chineseEngine, times(1)).close()
        verify(englishEngine, times(1)).close()
    }

    private fun withBackend(test: (OfflineAsrBackend, AsrInferenceClient) -> Unit) {
        val context = mock<Context>()
        val preferences = mock<SharedPreferences>()
        whenever(context.getSharedPreferences(any(), any())).thenReturn(preferences)
        whenever(preferences.getBoolean(any(), any())).thenReturn(true)
        whenever(preferences.getBoolean(eq(SettingsPreferences.KEY_STT_WHOLE_SENTENCE), any())).thenReturn(false)
        mockConstruction(AsrInferenceClient::class.java) { client, _ ->
            runBlocking {
                whenever(client.ensureBound()).thenReturn(true)
                whenever(client.startAsr(any(), any(), anyOrNull())).thenReturn(true)
                whenever(client.stopAsr()).thenReturn("")
            }
        }.use { clients ->
            mockConstruction(AsrModelManager::class.java) { manager, _ ->
                val selection = mock<AsrModelManager.Selection> {
                    on { mode } doReturn SpeechModelCatalog.WHISPER
                }
                whenever(manager.selectionForLanguage(any())).thenReturn(selection)
                whenever(manager.getSelectedModelId(any())).thenReturn(SpeechModelCatalog.WHISPER)
            }.use {
                test(OfflineAsrBackend(context), clients.constructed().single())
            }
        }
    }
}
