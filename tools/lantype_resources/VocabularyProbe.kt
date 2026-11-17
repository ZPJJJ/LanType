package com.kingzcheung.xime.association

import com.kingzcheung.xime.glide.EnglishBigrams
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.system.measureNanoTime
import kotlinx.coroutines.runBlocking

/** Reads the actual generated binary and executes the production English query engine on the JVM. */
fun main(args: Array<String>) = runBlocking {
    val assets = File(args[0])
    val words = File(assets,"english.txt").readLines()
    val bytes = ByteBuffer.wrap(File(assets,"english_trie.bin").readBytes()).order(ByteOrder.LITTLE_ENDIAN)
    check(bytes.int == 0x45495254 && bytes.get().toInt()==1)
    val count = bytes.int
    val nodes = Array(count) {
        val edges = bytes.get().toInt() and 255
        val chars = ByteArray(edges); val indices = IntArray(edges)
        repeat(edges) { chars[it]=bytes.get(); indices[it]=bytes.int; check(indices[it] in 0 until count) }
        if (bytes.get().toInt()==1) {
            val text=ByteArray(bytes.get().toInt() and 255);bytes.get(text)
            TrieNodeData(chars,indices,text.toString(Charsets.UTF_8),bytes.int)
        } else TrieNodeData(chars,indices)
    }
    check(!bytes.hasRemaining())
    fun node(word:String):TrieNodeData? {
        var index=0
        for (c in word) {
            val at=nodes[index].children.indexOf(c.code.toByte())
            if(at<0)return null
            index=nodes[index].childIndices[at]
        }
        return nodes[index]
    }
    for((rank,word) in words.withIndex()) check(node(word)?.let { it.word==word && it.frequency==rank+1 }==true)
    for(w in listOf("hello","world","keyboard","color","favorite","organize","language","offline","accessibility")) check(node(w)?.word==w)
    val engine=TrieAssociationEngine()
    fun field(name:String,value:Any) { TrieAssociationEngine::class.java.getDeclaredField(name).apply{isAccessible=true}.set(engine,value) }
    field("nodes",nodes);field("isInitialized",true)
    val spelling = File(assets,"english_us_spelling.tsv").bufferedReader().useLines { AmericanEnglishSpelling(it) }
    val forms=spelling.rankedForms(words.asSequence().mapIndexed { index, word -> word to (index+1).toFloat() }).map{AssociationCandidate(it.first,it.second)}
    field("americanForms",forms);field("americanRanks",forms.associate{it.text to it.score})
    field("typoCorrections",File(assets,"english_typo_corrections.tsv").bufferedReader().useLines { EnglishTypoCorrections(it) })
    val timings=ArrayList<Double>()
    val prefixes=listOf("s","c","p","a","th","hel","key","color","favorite","organize")
    val results=ArrayList<String>()
    for(prefix in prefixes) {
        val found=engine.predict(prefix,10)
        check(found.isNotEmpty())
        val expected=(words.filter{it.startsWith(prefix)}.map{AssociationCandidate(it,node(it)!!.frequency.toFloat())}+forms.filter{it.text.startsWith(prefix)})
            .sortedBy{it.score}.distinctBy{it.text}.take(10).map{it.text}
        check(found.map{it.text}==expected) { "Top-K changed for $prefix" }
        results += "\"$prefix\":[${found.take(3).joinToString(","){"\"${it.text}\""}}]"
    }
    repeat(30) { for(prefix in prefixes) timings += measureNanoTime { engine.predict(prefix,10) }/1000000.0 }
    val lm=EnglishBigrams(words, File(assets,"english_bigrams.txt").readLines().asSequence())
    check(lm.cost("thank","you")==2f)
    val collision=EnglishBigrams(words,sequenceOf("${words[0]} ${words[40000]} 11","${words[1]} ${words[7232]} 22","${words[88000]} ${words[88001]} 33"))
    check(collision.cost(words[0],words[40000])==1.1f)
    check(collision.cost(words[1],words[7232])==2.2f)
    check(collision.cost(words[88000],words[88001])==3.3f)
    timings.sort()
    println("{\"wordCount\":${words.size},\"nodeCount\":$count,\"allTerminalRanksVerified\":true,\"maxRank\":${nodes.maxOf{it.frequency}},\"americanFormsCount\":${forms.size},\"prefixResults\":{${results.joinToString(",")}},\"queriesTimed\":${timings.size},\"medianMs\":${timings[timings.size/2]},\"p95Ms\":${timings[(timings.size*.95).toInt()]},\"bigramCollisionRegressionPassed\":true,\"scope\":\"JVM production TrieAssociationEngine queries with actual SCOWL binary; Android initialization and UI latency not measured\"}")
}
