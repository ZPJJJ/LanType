package com.kingzcheung.xime.ui.keyboard

import android.app.Activity
import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager as SystemClipboard
import android.content.Context
import android.content.ContextWrapper
import android.graphics.Typeface
import android.os.Looper
import android.os.Parcel
import android.text.SpannableString
import android.text.Spanned
import android.text.style.StyleSpan
import android.view.inputmethod.EditorInfo
import androidx.room3.Room
import androidx.sqlite.driver.AndroidSQLiteDriver
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.kingzcheung.xime.clipboard.ClipboardImages
import com.kingzcheung.xime.clipboard.ClipboardManager
import com.kingzcheung.xime.clipboard.PrivateClipMemory
import com.kingzcheung.xime.clipboard.ToolCabinClipPrivacy
import com.kingzcheung.xime.clipboard.db.ClipboardDatabase
import com.kingzcheung.xime.settings.IncognitoState
import com.kingzcheung.xime.settings.SettingsPreferences
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.Shadows.shadowOf
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.util.ReflectionHelpers
import org.robolectric.util.ReflectionHelpers.ClassParameter

/** Real native copy/cut, Android clipboard parcels and fresh history managers; no screenshot fixture. */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [34], application = Application::class)
class ToolPanelPrivateClipboardTest {
    private lateinit var activityController: ActivityController<Activity>
    private lateinit var activity: Activity
    private lateinit var systemClipboard: SystemClipboard
    private val sensitiveExtra = "android.content.extra.IS_SENSITIVE"

    @Before fun setUp() {
        activityController = Robolectric.buildActivity(Activity::class.java).setup()
        activity = activityController.get()
        systemClipboard = activity.getSystemService(Context.CLIPBOARD_SERVICE) as SystemClipboard
        IncognitoState.manual = false
        IncognitoState.passwordField = false
        IncognitoState.sensitiveEditor = false
        IncognitoState.clipboardSearch = false
        IncognitoState.toolCabin = false
        SettingsPreferences.setIncognito(activity, false)
    }

    @After fun tearDown() {
        SettingsPreferences.setClipboardSensitiveCaptureEnabled(activity, false)
        activityController.pause().stop().destroy()
    }

    private fun editor(content: CharSequence, privateCopies: Boolean = true, context: Context = activity) =
        ToolPanelEditText(context).also {
            it.privateClipboardCopies = privateCopies
            activity.setContentView(it)
            it.requestFocus()
            it.setText(content)
        }

    private fun assertPrivateClip(expected: String): ClipData {
        val clip = requireNotNull(systemClipboard.primaryClip)
        assertEquals(expected, clip.getItemAt(0).text.toString())
        assertTrue(clip.description.extras?.getBoolean(ClipboardManager.TOOL_CABIN_PRIVATE_EXTRA) == true)
        assertTrue(clip.description.extras?.getBoolean(sensitiveExtra) == true)
        return clip
    }

    @Test fun nativeCopyPublishesBothMarkersBeforeTheFirstListenerAndKeepsStyles() {
        val draft = SpannableString("AprivateB").apply {
            setSpan(StyleSpan(Typeface.BOLD), 1, 8, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        val field = editor(draft)
        field.setSelection(8, 1) // A reverse selection must copy exactly the selected text.
        val observed = mutableListOf<Pair<Boolean, Boolean>>()
        val listener = SystemClipboard.OnPrimaryClipChangedListener {
            val extras = systemClipboard.primaryClipDescription?.extras
            observed += (extras?.getBoolean(ClipboardManager.TOOL_CABIN_PRIVATE_EXTRA) == true) to
                (extras?.getBoolean(sensitiveExtra) == true)
        }
        systemClipboard.addPrimaryClipChangedListener(listener)
        try {
            assertTrue(field.onTextContextMenuItem(android.R.id.copy))
            shadowOf(Looper.getMainLooper()).idle()
            assertEquals(listOf(true to true), observed)
            val copied = assertPrivateClip("private").getItemAt(0).text as Spanned
            val style = copied.getSpans(0, copied.length, StyleSpan::class.java).single()
            assertEquals(Typeface.BOLD, style.style)
            assertEquals(0, copied.getSpanStart(style))
            assertEquals(7, copied.getSpanEnd(style))
            assertEquals("AprivateB", field.text.toString())
        } finally { systemClipboard.removePrimaryClipChangedListener(listener) }
    }

    @Test fun inputConnectionCutCopiesStylesAndDeletesOnlyItsSelectedRange() {
        val draft = SpannableString("AprivateB").apply {
            setSpan(StyleSpan(Typeface.ITALIC), 1, 8, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
        val field = editor(draft)
        field.setSelection(8, 1)
        val connection = requireNotNull(field.onCreateInputConnection(EditorInfo()))
        assertTrue(connection.performContextMenuAction(android.R.id.cut))
        val copied = assertPrivateClip("private").getItemAt(0).text as Spanned
        assertEquals(Typeface.ITALIC, copied.getSpans(0, copied.length, StyleSpan::class.java).single().style)
        assertEquals("AB", field.text.toString())
        assertEquals(1, field.selectionStart)
        assertEquals(1, field.selectionEnd)
    }

    @Test fun reusedFieldReturnsToOrdinaryCopyAndCutWhenItLeavesTheCabin() {
        val field = editor("private")
        field.selectAll()
        field.onTextContextMenuItem(android.R.id.copy)
        assertPrivateClip("private")
        // AndroidView.update resets this property when the same view serves a plugin/search field.
        field.privateClipboardCopies = false
        field.setText("AordinaryB")
        field.setSelection(1, 9)
        assertTrue(field.onTextContextMenuItem(android.R.id.copy))
        assertEquals("ordinary", systemClipboard.primaryClip?.getItemAt(0)?.text.toString())
        assertFalse(systemClipboard.primaryClipDescription?.extras?.getBoolean(ClipboardManager.TOOL_CABIN_PRIVATE_EXTRA) == true)
        assertFalse(systemClipboard.primaryClipDescription?.extras?.getBoolean(sensitiveExtra) == true)
        field.setSelection(1, 9)
        assertTrue(field.onTextContextMenuItem(android.R.id.cut))
        assertEquals("AB", field.text.toString())
        assertFalse(systemClipboard.primaryClipDescription?.extras?.getBoolean(ClipboardManager.TOOL_CABIN_PRIVATE_EXTRA) == true)
    }

    @Test fun emptySelectionDoesNotOverwriteClipboardOrDeleteText() {
        systemClipboard.setPrimaryClip(ClipData.newPlainText("prior", "ordinary"))
        val field = editor("draft")
        field.setSelection(2)
        assertTrue(field.onTextContextMenuItem(android.R.id.copy))
        assertTrue(field.onTextContextMenuItem(android.R.id.cut))
        assertEquals("draft", field.text.toString())
        assertEquals("ordinary", systemClipboard.primaryClip?.getItemAt(0)?.text.toString())
    }

    @Test fun deniedCopyConsumesTheActionWithoutAnUnmarkedFallbackOrDeletingTheCut() {
        systemClipboard.setPrimaryClip(ClipData.newPlainText("prior", "ordinary"))
        var denyClipboard = false
        val deniedContext = object : ContextWrapper(activity) {
            override fun getSystemService(name: String): Any? {
                if (name == Context.CLIPBOARD_SERVICE && denyClipboard) throw SecurityException("denied")
                return super.getSystemService(name)
            }
        }
        val field = editor("AprivateB", context = deniedContext)
        field.setSelection(1, 8)
        denyClipboard = true
        assertTrue(field.onTextContextMenuItem(android.R.id.copy))
        assertTrue(field.onTextContextMenuItem(android.R.id.cut))
        assertEquals("AprivateB", field.text.toString())
        assertEquals(1, field.selectionStart)
        assertEquals(8, field.selectionEnd)
        assertEquals("ordinary", systemClipboard.primaryClip?.getItemAt(0)?.text.toString())
        denyClipboard = false
    }

    @Test fun copiedDraftStaysOutAfterFreshHistoryManagersRereadTheSystemClipboard() =
        assertFreshManagerIsolation(android.R.id.copy)

    @Test fun cutDraftStaysOutAfterFreshHistoryManagersRereadTheSystemClipboard() =
        assertFreshManagerIsolation(android.R.id.cut)

    /**
     * Only Android's system clipboard parcel survives. No cabin-open call, timestamp guard or
     * prior manager cache is used to classify it. Two newly constructed managers do the actual
     * readMissedCopy path with sensitive capture ON, then an ordinary copy must reach real Room.
     */
    private fun assertFreshManagerIsolation(action: Int) {
        val field = editor("temporary draft")
        field.selectAll()
        assertTrue(field.onTextContextMenuItem(action))
        val copiedAt = System.currentTimeMillis()
        setCurrentClipSystemTimestamp(copiedAt)
        val parcel = Parcel.obtain()
        val restoredClip = try {
            assertPrivateClip("temporary draft").writeToParcel(parcel, 0)
            parcel.setDataPosition(0)
            ClipData.CREATOR.createFromParcel(parcel)
        } finally { parcel.recycle() }
        assertEquals(copiedAt, restoredClip.description.timestamp)
        systemClipboard.setPrimaryClip(restoredClip)
        setCurrentClipSystemTimestamp(copiedAt)
        assertPrivateClip("temporary draft")
        assertFalse(IncognitoState.active)
        SettingsPreferences.setClipboardSensitiveCaptureEnabled(activity, true)

        val database = Room.inMemoryDatabaseBuilder<ClipboardDatabase>(activity.applicationContext)
            .setDriver(AndroidSQLiteDriver()).setQueryCoroutineContext(Dispatchers.IO).build()
        val dbInstance = ClipboardDatabase::class.java.getDeclaredField("instance").apply { isAccessible = true }
        val previousDb = dbInstance.get(null)
        val imagesInstance = ClipboardImages::class.java.getDeclaredField("instance").apply { isAccessible = true }
        val previousImages = imagesInstance.get(null)
        dbInstance.set(null, database)
        val managers = mutableListOf<ClipboardManager>()
        try {
            val stamp = requireNotNull(systemClipboard.primaryClipDescription).timestamp
            assertTrue(ClipboardManager.shouldReadOnOpen(stamp, -1L, System.currentTimeMillis(), false, true))
            val guard = ClipboardManager::class.java.getDeclaredField("toolCabinCopies").apply { isAccessible = true }
                .get(null) as ToolCabinClipPrivacy
            assertFalse(guard.isPrivate(stamp))
            repeat(2) {
                val manager = ClipboardManager::class.java.getDeclaredConstructor(Context::class.java)
                    .apply { isAccessible = true }.newInstance(activity.applicationContext)
                managers += manager
                runBlocking { withTimeout(5_000) { manager.historyLimits() } }
                val memory = managerField(manager, "privateClips") as PrivateClipMemory
                val key = PrivateClipMemory.key(stamp, "temporary draft")
                assertFalse(key in memory)
                manager.readMissedCopy()
                // This is the real reader's result, not just a call to the policy helper.
                assertTrue(key in memory)
                assertEquals(stamp, managerField(manager, "lastReadClipTimestamp"))
                assertTrue(runBlocking { database.clipboardDao().observeAll().first().isEmpty() })
                if (it == 0) stopManager(manager)
            }
            assertFalse(guard.isPrivate(stamp))

            systemClipboard.setPrimaryClip(ClipData.newPlainText("ordinary", "ordinary after restart"))
            setCurrentClipSystemTimestamp(System.currentTimeMillis())
            shadowOf(Looper.getMainLooper()).idle()
            managers.last().readMissedCopy()
            val records = runBlocking {
                withTimeout(5_000) { database.clipboardDao().observeAll().first { rows -> rows.any { it.text == "ordinary after restart" } } }
            }
            assertEquals(listOf("ordinary after restart"), records.map { it.text })
            assertFalse(records.single().sensitive)
        } finally {
            managers.forEach(::stopManager)
            if (previousImages == null) {
                (imagesInstance.get(null) as? ClipboardImages)?.let { images ->
                    val scope = ClipboardImages::class.java.getDeclaredField("scope").apply { isAccessible = true }.get(images) as CoroutineScope
                    runBlocking { scope.coroutineContext[Job]?.cancelAndJoin() }
                    val listener = ClipboardImages::class.java.getDeclaredField("pinListener").apply { isAccessible = true }.get(images)
                        as android.content.SharedPreferences.OnSharedPreferenceChangeListener
                    activity.getSharedPreferences("clipboard_board", Context.MODE_PRIVATE).unregisterOnSharedPreferenceChangeListener(listener)
                    val handler = ClipboardImages::class.java.getDeclaredField("mainHandler").apply { isAccessible = true }.get(images) as android.os.Handler
                    handler.removeCallbacksAndMessages(null)
                }
                imagesInstance.set(null, null)
            }
            dbInstance.set(null, previousDb)
            database.close()
        }
    }

    /**
     * Robolectric 4.14.1 ShadowClipboardManager uses SystemClock.uptimeMillis for this field;
     * Android's ClipboardService stamps copies with System.currentTimeMillis. Supply only that
     * missing system-service behavior, after the shadow's setPrimaryClip has overwritten it.
     * API contract: https://developer.android.com/reference/android/content/ClipDescription#getTimestamp()
     * Content, private extras, Parcel transport, the 30-second gate and history reads stay real.
     */
    private fun setCurrentClipSystemTimestamp(timestamp: Long) {
        ReflectionHelpers.callInstanceMethod<Void>(requireNotNull(systemClipboard.primaryClipDescription),
            "setTimestamp", ClassParameter.from(java.lang.Long.TYPE, timestamp))
        assertEquals(timestamp, systemClipboard.primaryClipDescription?.timestamp)
    }

    private fun managerField(manager: ClipboardManager, name: String): Any? =
        ClipboardManager::class.java.getDeclaredField(name).apply { isAccessible = true }.get(manager)

    private fun stopManager(manager: ClipboardManager) {
        systemClipboard.removePrimaryClipChangedListener(managerField(manager, "clipboardListener") as SystemClipboard.OnPrimaryClipChangedListener)
        SettingsPreferences.getPrefsPublic(activity).unregisterOnSharedPreferenceChangeListener(
            managerField(manager, "incognitoSwitchListener") as android.content.SharedPreferences.OnSharedPreferenceChangeListener)
        val scope = managerField(manager, "scope") as CoroutineScope
        runBlocking { scope.coroutineContext[Job]?.cancelAndJoin() }
    }
}
