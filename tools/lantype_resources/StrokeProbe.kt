import com.kingzcheung.xime.handwriting.LicensedStrokeRecognizer
import java.io.File
import kotlin.system.measureNanoTime

// Original manual replay paths, independent of the source font/template coordinates.
fun paths(vararg strokes: List<Pair<Float, Float>>) = strokes.toList()
fun stroke(vararg xy: Int) = xy.toList().chunked(2).map { it[0].toFloat() to it[1].toFloat() }
fun main(args: Array<String>) {
    val root = File(args[0])
    val freq = File(root, "handwriting/hanzi_frequency.tsv").readLines().filterNot { it.startsWith("#") }
        .mapNotNull { val f = it.split('\t'); f.getOrNull(1)?.toIntOrNull()?.let { f[0] to it } }.toMap()
    lateinit var engine: LicensedStrokeRecognizer
    val loadMs = measureNanoTime { engine = LicensedStrokeRecognizer.load(File(root,"handwriting/lantype-strokes.lth").inputStream(),freq) } / 1000000.0
    val cases = listOf(
        "一" to paths(stroke(12,51,48,48,91,50)),
        "二" to paths(stroke(26,24,76,25),stroke(8,78,92,77)),
        "三" to paths(stroke(17,15,85,14),stroke(28,48,76,49),stroke(8,84,94,84)),
        "十" to paths(stroke(10,46,90,44),stroke(52,7,50,96)),
        "人" to paths(stroke(53,10,45,49,12,91),stroke(48,43,65,72,91,94)),
        "大" to paths(stroke(10,38,91,39),stroke(53,8,47,55,11,95),stroke(47,44,63,76,94,94)),
        "口" to paths(stroke(18,17,20,83),stroke(18,18,83,17,82,84),stroke(20,82,83,83)),
        "中" to paths(stroke(17,28,18,72),stroke(17,28,84,28,83,72),stroke(18,72,83,71),stroke(51,5,50,95)),
        "木" to paths(stroke(11,34,92,35),stroke(50,5,49,96),stroke(47,37,14,87),stroke(53,39,88,87)),
        "日" to paths(stroke(20,12,21,92),stroke(20,12,80,12,79,92),stroke(21,52,79,51),stroke(21,91,79,91)),
        "A" to paths(stroke(10,92,51,9,89,92),stroke(29,59,73,60)),
        "H" to paths(stroke(16,9,17,93),stroke(83,8,82,93),stroke(17,51,82,52)),
        "L" to paths(stroke(17,7,18,94,86,94)),
        "T" to paths(stroke(13,9,90,8),stroke(51,9,51,95)),
        "X" to paths(stroke(13,8,87,92),stroke(88,8,12,92)),
        "4" to paths(stroke(65,7,13,63,90,64),stroke(66,8,64,95)),
    )
    var hits = 0
    val timing = ArrayList<Double>()
    println("{\"templateCount\":${engine.templateCount},\"loadMs\":$loadMs,\"cases\":[")
    for ((i, entry) in cases.withIndex()) {
        val (expected, points) = entry
        val latin = expected[0].code < 128
        var candidates = emptyList<LicensedStrokeRecognizer.Result>()
        val ms = measureNanoTime { candidates = engine.recognize(points,latin,10) } / 1000000.0
        val rank = candidates.indexOfFirst { it.text == expected } + 1
        if (rank > 0) hits++
        println("{\"expected\":\"$expected\",\"rank\":$rank,\"top\":\"${candidates.take(5).joinToString(""){it.text}}\",\"ms\":$ms}${if(i<cases.size-1) "," else ""}")
    }
    repeat(12) { for ((expected, points) in cases) timing += measureNanoTime { engine.recognize(points,expected[0].code<128,10) } / 1000000.0 }
    var checks=0
    val cancelled=runCatching { engine.recognize(cases[7].second,false,10) { if (++checks==3) throw InterruptedException("superseded") };false }.exceptionOrNull() is InterruptedException
    check(cancelled)
    check(engine.recognize(List(65){stroke(0,0,1,1)},false,10).isEmpty())
    check(engine.recognize(listOf(listOf(Float.NaN to 1f)),false,10).isEmpty())
    timing.sort()
    println("],\"top10Hits\":$hits,\"caseCount\":${cases.size},\"timedReplays\":${timing.size},\"medianMs\":${timing[timing.size/2]},\"p95Ms\":${timing[(timing.size*.95).toInt()]},\"cancelledOnThirdCheckpoint\":$cancelled,\"limitsVerified\":true,\"scope\":\"JVM host manual single-character replay; not Android UI or corpus accuracy benchmark\"}")
    check(hits == cases.size) { "Manual replay missing expected characters" }
}
