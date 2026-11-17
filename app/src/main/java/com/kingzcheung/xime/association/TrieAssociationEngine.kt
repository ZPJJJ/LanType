package com.kingzcheung.xime.association

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.ensureActive
import java.io.DataInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

data class TrieNodeData(
    val children: ByteArray = ByteArray(0),
    val childIndices: IntArray = IntArray(0),
    val word: String? = null,
    val frequency: Int = 0
)

class TrieAssociationEngine {
    private var nodes: Array<TrieNodeData>? = null
    private var americanForms: List<AssociationCandidate> = emptyList()
    private var americanRanks: Map<String, Float> = emptyMap()
    private var typoCorrections = EnglishTypoCorrections.EMPTY
    private var isInitialized = false
    
    companion object {
        private const val TAG = "TrieAssociationEngine"
        private const val BINARY_FILE = "english_trie.bin"
        private const val TEXT_FILE = "english.txt"
        private var instance: TrieAssociationEngine? = null
        
        fun getInstance(): TrieAssociationEngine {
            if (instance == null) {
                instance = TrieAssociationEngine()
            }
            return instance!!
        }
    }
    
    suspend fun initialize(context: Context): Boolean = withContext(Dispatchers.IO) {
        if (isInitialized) {
            return@withContext true
        }
        
        try {
            val startTime = System.currentTimeMillis()
            
            val binaryExists = try {
                context.assets.list("")?.contains(BINARY_FILE) ?: false
            } catch (e: Exception) {
                false
            }
            
            if (binaryExists) {
                loadBinaryTrie(context)
            } else {
                Log.w(TAG, "Binary trie not found, building from text")
                buildTrieFromText(context)
            }

            americanForms = EnglishUsLexicon.get(context).rankedForms(
                nodes.orEmpty().asSequence().mapNotNull { node ->
                    node.word?.let { it to node.frequency.toFloat() }
                }
            ).map { (word, rank) -> AssociationCandidate(word, rank) }
            americanRanks = americanForms.associate { it.text to it.score }
            typoCorrections = EnglishUsLexicon.typos(context)
            
            isInitialized = true
            val elapsed = System.currentTimeMillis() - startTime
            Log.i(TAG, "Trie engine initialized in $elapsed ms (${nodes?.size ?: 0} nodes)")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize trie engine", e)
            false
        }
    }
    
    private fun loadBinaryTrie(context: Context) {
        val bytes = context.assets.open(BINARY_FILE).use { it.readBytes() }
        val buffer = ByteBuffer.wrap(bytes)
        buffer.order(ByteOrder.LITTLE_ENDIAN)
        
        val magic = ByteArray(4)
        buffer.get(magic)
        require(magic.contentEquals("TRIE".toByteArray())) { "Invalid trie file" }
        
        val version = buffer.get()
        require(version.toInt() == 1) { "Unsupported trie version: $version" }
        
        val nodeCount = buffer.getInt()
        nodes = Array(nodeCount) {
            val childCount = buffer.get().toInt()
            val children = ByteArray(childCount)
            val childIndices = IntArray(childCount)
            
            for (j in 0 until childCount) {
                children[j] = buffer.get()
                childIndices[j] = buffer.getInt()
            }
            
            val hasWord = buffer.get().toInt()
            var word: String? = null
            var freq = 0
            
            if (hasWord == 1) {
                val wordLen = buffer.get().toInt()
                val wordBytes = ByteArray(wordLen)
                buffer.get(wordBytes)
                word = String(wordBytes, Charsets.UTF_8)
                freq = buffer.getInt()
            }
            
            TrieNodeData(children, childIndices, word, freq)
        }
    }
    
    private fun buildTrieFromText(context: Context) {
        val tempChildren = mutableListOf<ByteArray>()
        val tempIndices = mutableListOf<IntArray>()
        val tempWords = mutableListOf<String?>()
        val tempFreqs = mutableListOf<Int>()
        
        tempChildren.add(ByteArray(0))
        tempIndices.add(IntArray(0))
        tempWords.add(null)
        tempFreqs.add(0)
        
        fun getOrCreateChild(parentIdx: Int, char: Char): Int {
            val pChildren = tempChildren[parentIdx]
            val pIndices = tempIndices[parentIdx]
            val charByte = char.code.toByte()
            
            for (i in pChildren.indices) {
                if (pChildren[i] == charByte.toByte()) return pIndices[i]
            }
            
            val newIdx = tempChildren.size
            tempChildren.add(ByteArray(0))
            tempIndices.add(IntArray(0))
            tempWords.add(null)
            tempFreqs.add(0)
            
            val newChildren = ByteArray(pChildren.size + 1)
            val newIndices = IntArray(pIndices.size + 1)
            pChildren.copyInto(newChildren)
            pIndices.copyInto(newIndices)
            newChildren[pChildren.size] = charByte
            newIndices[pIndices.size] = newIdx
            
            tempChildren[parentIdx] = newChildren
            tempIndices[parentIdx] = newIndices
            return newIdx
        }
        
        context.assets.open(TEXT_FILE).bufferedReader().use { reader ->
            var lineNum = 0
            reader.lineSequence().forEach { line ->
                lineNum++
                val word = line.trim().lowercase()
                if (word.isNotEmpty()) {
                    var current = 0
                    for (char in word) {
                        current = getOrCreateChild(current, char)
                    }
                    if (tempWords[current] == null) {
                        tempWords[current] = word
                        tempFreqs[current] = lineNum
                    }
                }
            }
        }
        
        nodes = Array(tempChildren.size) { i ->
            TrieNodeData(tempChildren[i], tempIndices[i], tempWords[i], tempFreqs[i])
        }
    }
    
    suspend fun predict(prefix: String, topK: Int = 5): List<AssociationCandidate> = withContext(Dispatchers.Default) {
        if (!isInitialized || prefix.isEmpty() || nodes == null || topK <= 0) {
            return@withContext emptyList()
        }
        
        val normalizedPrefix = prefix.lowercase()
        val startIdx = findNode(normalizedPrefix)
        
        val candidates = mutableListOf<AssociationCandidate>()
        if (startIdx >= 0) collectWords(startIdx, candidates, topK) { ensureActive() }
        candidates += americanForms.filter { it.text.startsWith(normalizedPrefix) }

        if (candidates.isEmpty() || typoCorrections.hasFrequentTypo(prefix)) {
            val corrections = typoCorrections.suggestions(prefix, topK, ::dictionaryRank)
            if (corrections.isNotEmpty()) {
                // The raw spelling stays selectable immediately after the first
                // correction. Typing/space still commits exactly what was typed.
                val corrected = listOf(corrections.first(), prefix) + corrections.drop(1)
                return@withContext corrected.distinct().take(topK)
                    .mapIndexed { index, text -> AssociationCandidate(text, index.toFloat()) }
            }
        }
        
        val ranked = candidates.sortedBy { it.score }.distinctBy { it.text }.take(topK)
        if (prefix == normalizedPrefix) return@withContext ranked
        val allCaps = prefix.length > 1 && prefix.all { it.isUpperCase() }
        ranked.map { candidate ->
            val tail = candidate.text.substring(normalizedPrefix.length)
            candidate.copy(text = prefix + if (allCaps) tail.uppercase() else tail)
        }
    }
    
    private fun findNode(prefix: String): Int {
        var current = 0
        for (char in prefix) {
            val node = nodes!![current]
            val charByte = char.code.toByte()
            var found = -1
            for (i in node.children.indices) {
                if (node.children[i] == charByte.toByte()) {
                    found = node.childIndices[i]
                    break
                }
            }
            if (found < 0) return -1
            current = found
        }
        return current
    }

    private fun dictionaryRank(word: String): Float? {
        val index = findNode(word)
        val node = nodes?.getOrNull(index)
        val bundled = node?.takeIf { it.word != null }?.frequency?.toFloat()
        val american = americanRanks[word]
        return if (bundled == null) american else minOf(bundled, american ?: Float.POSITIVE_INFINITY)
    }
    
    private fun collectWords(nodeIdx: Int, candidates: MutableList<AssociationCandidate>, limit: Int,
        checkCancelled: () -> Unit) {
        // SCOWL is larger than the former short list. Retain only the best requested
        // completions instead of allocating/sorting every word below a one-letter prefix.
        val best = java.util.PriorityQueue<AssociationCandidate>(compareByDescending { it.score })
        var visited = 0
        fun visit(index: Int) {
            if (visited++ % 256 == 0) checkCancelled()
            val node = nodes!![index]
            val word = node.word
            if (word != null && (best.size < limit || node.frequency.toFloat() < best.peek()!!.score)) {
                best.add(AssociationCandidate(word, node.frequency.toFloat()))
                if (best.size > limit) best.remove()
            }
            for (child in node.childIndices) visit(child)
        }
        visit(nodeIdx)
        checkCancelled()
        candidates += best
    }
    
    fun isInitialized(): Boolean = isInitialized
    
    fun release() {
        nodes = null
        americanForms = emptyList()
        americanRanks = emptyMap()
        typoCorrections = EnglishTypoCorrections.EMPTY
        isInitialized = false
    }
}
