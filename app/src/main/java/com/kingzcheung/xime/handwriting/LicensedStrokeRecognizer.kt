package com.kingzcheung.xime.handwriting

import java.io.DataInputStream
import java.io.InputStream
import java.util.PriorityQueue
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.hypot
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min

/**
 * Bounded, single-character stroke-order template matching. This is not a neural
 * recognizer or a cursive/whole-word recognizer. Chinese geometry is distributed
 * under the Arphic Public License; Latin geometry is original CC0 artwork.
 * Loading and recognition must run on a worker dispatcher. The caller supplies
 * cancellation checks so a new pen stroke can immediately supersede old work.
 */
class LicensedStrokeRecognizer private constructor(
    private val index: Map<Int, List<Template>>,
    val templateCount: Int,
) {
    data class Result(val text: String, val score: Float)
    private class Template(val text: String, val strokes: Array<FloatArray>, val histogram: FloatArray,
        val latin: Boolean, val prior: Float)
    private data class Coarse(val template: Template, val distance: Float)

    fun recognize(
        input: List<List<Pair<Float, Float>>>,
        latin: Boolean,
        limit: Int,
        checkCancelled: () -> Unit = {},
    ): List<Result> {
        checkCancelled()
        if (input.isEmpty() || input.size > MAX_STROKES || limit <= 0) return emptyList()
        val query = normalize(input) ?: return emptyList()
        val histogram = histogram(query)
        val shape = shape(query)
        val tolerance = if (latin) 1 else max(1, query.size / 8).coerceAtMost(2)
        val best = PriorityQueue<Coarse>(compareByDescending { it.distance })
        var examined = 0
        for (count in max(1, query.size - tolerance)..min(MAX_STROKES, query.size + tolerance)) {
            // Stroke count and bounding-box shape are indexed during background load.
            for (template in index[count * 3 + shape].orEmpty()) {
                if (template.latin != latin) continue
                if (examined++ % 64 == 0) checkCancelled()
                val distance = histogramDistance(histogram, template.histogram) +
                    abs(template.strokes.size - query.size) * 0.035f
                if (best.size < MAX_REFINED || distance < best.peek()!!.distance) {
                    best.add(Coarse(template, distance))
                    if (best.size > MAX_REFINED) best.remove()
                }
            }
        }
        val scores = ArrayList<Result>(best.size)
        for (candidate in best) {
            checkCancelled()
            val template = candidate.template
            val distance = strokeDistance(query, template.strokes, checkCancelled) * 0.9f +
                candidate.distance * 0.1f - template.prior * 0.012f
            scores.add(Result(template.text, exp((-6f * distance.coerceAtLeast(0f)).toDouble()).toFloat()))
        }
        checkCancelled()
        return scores.sortedWith(compareByDescending<Result> { it.score }.thenBy { it.text })
            .distinctBy { it.text }.take(limit.coerceAtMost(64))
    }

    companion object {
        const val MAX_STROKES = 64
        const val MAX_REFINED = 128
        const val POINTS_PER_STROKE = 8
        private const val MAX_INPUT_POINTS_PER_STROKE = 256

        fun load(input: InputStream, frequencies: Map<String, Int> = emptyMap()): LicensedStrokeRecognizer {
            val index = HashMap<Int, MutableList<Template>>()
            var count: Int
            DataInputStream(input.buffered()).use { stream ->
                require(stream.readInt() == 0x4c544831) { "Invalid LanType stroke template header" }
                val headerSize = stream.readInt()
                require(headerSize in 1..65536)
                val header = ByteArray(headerSize)
                stream.readFully(header)
                count = stream.readInt()
                require(count in 1..20000)
                repeat(count) {
                    val size = stream.readUnsignedShort()
                    require(size in 1..8)
                    val bytes = ByteArray(size)
                    stream.readFully(bytes)
                    val text = bytes.toString(Charsets.UTF_8)
                    val strokesCount = stream.readUnsignedShort()
                    require(strokesCount in 1..MAX_STROKES)
                    val strokes = Array(strokesCount) {
                        FloatArray(POINTS_PER_STROKE * 2) { stream.readUnsignedShort() / 4096f }
                    }
                    val latin = text.length == 1 && text[0].let { it in 'A'..'Z' || it in 'a'..'z' || it in '0'..'9' }
                    val prior = (ln(1.0 + (frequencies[text] ?: 0)) / ln(5000000.0)).toFloat().coerceIn(0f, 1f)
                    val template = Template(text, strokes, histogram(strokes), latin, prior)
                    index.getOrPut(strokesCount * 3 + shape(strokes)) { ArrayList() }.add(template)
                }
                require(stream.read() == -1) { "Unexpected trailing stroke-template data" }
            }
            return LicensedStrokeRecognizer(index, count)
        }

        private fun normalize(input: List<List<Pair<Float, Float>>>): Array<FloatArray>? {
            // Bound work even if a stylus driver submits thousands of points per stroke.
            val strokes = input.map { stroke ->
                val finite = stroke.filter { it.first.isFinite() && it.second.isFinite() }
                if (finite.size <= MAX_INPUT_POINTS_PER_STROKE) finite else
                    List(MAX_INPUT_POINTS_PER_STROKE) { finite[it * (finite.size - 1) / (MAX_INPUT_POINTS_PER_STROKE - 1)] }
            }.filter { it.isNotEmpty() }
            if (strokes.isEmpty()) return null
            var minX = Float.POSITIVE_INFINITY; var minY = minX
            var maxX = Float.NEGATIVE_INFINITY; var maxY = maxX
            for (stroke in strokes) for ((x, y) in stroke) {
                minX = min(minX, x); minY = min(minY, y); maxX = max(maxX, x); maxY = max(maxY, y)
            }
            val span = max(maxX - minX, maxY - minY).coerceAtLeast(0.000001f)
            val scaleX = max(maxX - minX, span * 0.35f)
            val scaleY = max(maxY - minY, span * 0.35f)
            val centerX = (minX + maxX) / 2f; val centerY = (minY + maxY) / 2f
            return strokes.map { stroke ->
                val points = stroke.map { (x, y) -> (x - centerX) / scaleX + 0.5f to (y - centerY) / scaleY + 0.5f }
                val lengths = FloatArray(points.size)
                for (i in 1 until points.size) lengths[i] = lengths[i - 1] +
                    hypot(points[i].first - points[i - 1].first, points[i].second - points[i - 1].second)
                var at = 1
                FloatArray(POINTS_PER_STROKE * 2).also { sampled ->
                    for (i in 0 until POINTS_PER_STROKE) {
                        val target = lengths.last() * i / (POINTS_PER_STROKE - 1)
                        while (at < points.size - 1 && lengths[at] < target) at++
                        if (points.size == 1 || lengths.last() < 0.000000001f) {
                            sampled[i * 2] = points[0].first; sampled[i * 2 + 1] = points[0].second
                        } else {
                            val fraction = (target - lengths[at - 1]) / (lengths[at] - lengths[at - 1]).coerceAtLeast(0.000000001f)
                            sampled[i * 2] = points[at - 1].first * (1f - fraction) + points[at].first * fraction
                            sampled[i * 2 + 1] = points[at - 1].second * (1f - fraction) + points[at].second * fraction
                        }
                    }
                }
            }.toTypedArray()
        }

        private fun shape(strokes: Array<FloatArray>): Int {
            var minX = 1f; var minY = 1f; var maxX = 0f; var maxY = 0f
            for (stroke in strokes) for (i in 0 until POINTS_PER_STROKE) {
                minX = min(minX, stroke[i * 2]); maxX = max(maxX, stroke[i * 2])
                minY = min(minY, stroke[i * 2 + 1]); maxY = max(maxY, stroke[i * 2 + 1])
            }
            return when { maxX - minX < 0.6f -> 1; maxY - minY < 0.6f -> 2; else -> 0 }
        }

        private fun histogram(strokes: Array<FloatArray>): FloatArray {
            val result = FloatArray(16)
            for (stroke in strokes) for (i in 0 until POINTS_PER_STROKE) {
                val x = (stroke[i * 2] * 3).coerceIn(0f, 3f)
                val y = (stroke[i * 2 + 1] * 3).coerceIn(0f, 3f)
                val left = x.toInt(); val top = y.toInt(); val right = min(3, left + 1); val bottom = min(3, top + 1)
                val fx = x - left; val fy = y - top
                result[top * 4 + left] += (1 - fx) * (1 - fy)
                result[top * 4 + right] += fx * (1 - fy)
                result[bottom * 4 + left] += (1 - fx) * fy
                result[bottom * 4 + right] += fx * fy
            }
            val divisor = strokes.size * POINTS_PER_STROKE.toFloat()
            for (i in result.indices) result[i] /= divisor
            return result
        }

        private fun histogramDistance(a: FloatArray, b: FloatArray): Float {
            var distance = 0f
            for (i in a.indices) distance += abs(a[i] - b[i])
            return distance
        }

        private fun strokeDistance(a: Array<FloatArray>, b: Array<FloatArray>, checkCancelled: () -> Unit): Float {
            val gap = 0.42f
            var previous = FloatArray(b.size + 1) { it * gap }
            var next = FloatArray(b.size + 1)
            for (i in a.indices) {
                checkCancelled()
                next[0] = (i + 1) * gap
                for (j in b.indices) {
                    var forward = 0f; var reverse = 0f
                    for (p in 0 until POINTS_PER_STROKE) {
                        val q = POINTS_PER_STROKE - 1 - p
                        forward += hypot(a[i][p * 2] - b[j][p * 2], a[i][p * 2 + 1] - b[j][p * 2 + 1])
                        reverse += hypot(a[i][p * 2] - b[j][q * 2], a[i][p * 2 + 1] - b[j][q * 2 + 1])
                    }
                    val cost = min(forward, reverse + 0.15f) / POINTS_PER_STROKE
                    next[j + 1] = min(previous[j] + cost, min(previous[j + 1] + gap, next[j] + gap))
                }
                val swap = previous; previous = next; next = swap
            }
            return previous.last() / max(a.size, b.size)
        }
    }
}
