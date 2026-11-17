package com.kingzcheung.xime.handwriting

import android.content.Context
import android.os.Looper
import android.util.Log
import com.kingzcheung.xime.settings.InputLanguage
import java.io.File

data class HandwritingCandidate(val char: String, val score: Float)
data class HandwritingRawCandidate(val char: String, val index: Int, val score: Float)

/** Licensed single-character stroke templates; no CASIA/OCHWPro or formula model is loaded. */
object HandwritingEngine {
    private const val ASSET = "handwriting/lantype-strokes.lth"
    @Volatile private var recognizer: LicensedStrokeRecognizer? = null

    /** Call on a worker thread. No model extraction, JNI, service or network is needed. */
    @Synchronized
    fun initialize(context: Context, language: InputLanguage = InputLanguage.CHINESE): Boolean {
        if (!HandwritingLanguages.supports(language)) return false
        if (recognizer != null) return true
        if (Looper.myLooper() == Looper.getMainLooper()) return false
        return try {
            val frequencies = context.assets.open("handwriting/hanzi_frequency.tsv").bufferedReader().useLines { lines ->
                lines.filterNot { it.startsWith("#") }.mapNotNull { line ->
                    val fields = line.split('\t')
                    fields.getOrNull(1)?.toIntOrNull()?.let { fields[0] to it }
                }.toMap()
            }
            recognizer = LicensedStrokeRecognizer.load(context.assets.open(ASSET), frequencies)
            true
        } catch (error: Exception) {
            Log.e("HandwritingEngine", "Unable to load packaged stroke templates", error)
            false
        }
    }

    fun isInitialized(): Boolean = recognizer != null
    fun hasModel(context: Context, language: InputLanguage = InputLanguage.CHINESE): Boolean =
        HandwritingLanguages.supports(language) && runCatching { context.assets.open(ASSET).use { true } }.getOrDefault(false)

    fun predict(strokes: List<List<Pair<Float, Float>>>, topK: Int = 10,
        language: InputLanguage = InputLanguage.CHINESE, checkCancelled: () -> Unit = {}): List<HandwritingCandidate> {
        if (!HandwritingLanguages.supports(language) || Looper.myLooper() == Looper.getMainLooper()) return emptyList()
        return recognizer?.recognize(strokes, language == InputLanguage.ENGLISH, topK, checkCancelled)
            ?.map { HandwritingCandidate(it.text, it.score) }.orEmpty()
    }

    /** Compatibility for optional diagnostics. These scores are template similarity, not probabilities. */
    fun predictRaw(strokes: List<List<Pair<Float, Float>>>, n: Int): List<HandwritingRawCandidate> =
        predict(strokes, n).mapIndexed { index, result -> HandwritingRawCandidate(result.char, index, result.score) }

    // Paths remain for users' own old files; this edition neither loads nor deletes them.
    fun personalModelFile(context: Context): File =
        File(context.getExternalFilesDir(null) ?: context.filesDir, "handwriting_models/ochwpro-personal.onnx")
    fun disabledPersonalModelFile(context: Context): File = File(personalModelFile(context).path + ".disabled")
    @Suppress("UNUSED_PARAMETER")
    fun setPersonalModelEnabled(context: Context, enabled: Boolean): Boolean = false
    @Synchronized fun release() { recognizer = null }
}
