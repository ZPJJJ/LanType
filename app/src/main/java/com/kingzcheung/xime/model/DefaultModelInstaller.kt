package com.kingzcheung.xime.model

import android.content.Context
import com.kingzcheung.xime.speech.SpeechModelCatalog
import com.kingzcheung.xime.util.FileLogger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** LanType offline edition: prepare only files already packaged inside this APK.
 * Imported local models remain managed by ModelImporter; there is no network observer,
 * remote catalogue lookup, download queue, retry timer or automatic updater here. */
object DefaultModelInstaller {
    internal val modelIds = setOf(SpeechModelCatalog.WHISPER)
    private val started = AtomicBoolean(false)
    @Volatile private var bundledReady = false
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val waiting = MutableStateFlow(0L)

    private fun preferences(context: Context) = context.getSharedPreferences("default_models", Context.MODE_PRIVATE)

    /** Retained for source compatibility with setup screens; offline preparation never waits for Wi-Fi. */
    val waitingForWifiBytes: StateFlow<Long> = waiting

    /** Legacy UI callback. It can only retry local installation in this offline edition. */
    fun allowMeteredDownload(context: Context) { start(context.applicationContext) }

    internal fun missingBytes(context: Context, ids: List<String>): Long = ids.mapNotNull { ModelManager.getModel(it) }
        .filterNot { ModelManager.isModelDownloaded(context, it) }
        .sumOf { model -> model.files.sumOf { it.sizeBytes } }

    internal fun isHandled(context: Context, id: String): Boolean = preferences(context).getBoolean("handled_$id", false)

    /** Old setup code may call this; only the APK's bundled files are eligible. */
    @Suppress("UNUSED_PARAMETER")
    fun requestGuided(context: Context, ids: Set<String>, allowMetered: Boolean) {
        start(context.applicationContext)
    }

    internal fun requestedModelIds(context: Context): List<String> =
        if (com.kingzcheung.xime.BuildConfig.BUNDLED_MODELS) BundledModelInstaller.bundledIds(context).toList()
        else emptyList()

    internal fun isPendingDefault(context: Context, id: String): Boolean =
        !isHandled(context, id) && id in requestedModelIds(context)

    internal fun markHandled(context: Context, id: String) {
        if (id in requestedModelIds(context)) preferences(context).edit()
            .putBoolean("handled_$id", true).remove("pending_$id").commit()
    }

    /** User-requested restore after deleting a bundled model, still entirely offline. */
    fun prepareLocal(context: Context, id: String) {
        val app = context.applicationContext
        scope.launch {
            try {
                if (BundledModelInstaller.restorePackaged(app, id)) markHandled(app, id)
                else FileLogger.w("DefaultModels", "模型不在安装包中，请从本地导入：$id")
            } catch (error: Exception) {
                FileLogger.e("DefaultModels", "内置模型本地准备失败：$id", error)
            }
        }
    }

    fun start(context: Context) {
        waiting.value = 0L
        if (!com.kingzcheung.xime.BuildConfig.BUNDLED_MODELS || bundledReady) return
        if (!started.compareAndSet(false, true)) return
        val app = context.applicationContext
        scope.launch {
            try {
                ModelManager.initialize()
                BundledModelInstaller.install(app)
                requestedModelIds(app).filter { ModelManager.isModelReady(app, it) }
                    .forEach { markHandled(app, it) }
                bundledReady = true
            } catch (error: Exception) {
                FileLogger.e("DefaultModels", "内置模型本地准备失败，重新打开应用可重试", error)
            } finally {
                started.set(false)
            }
        }
    }
}
