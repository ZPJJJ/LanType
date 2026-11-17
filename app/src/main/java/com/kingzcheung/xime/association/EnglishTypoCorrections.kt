package com.kingzcheung.xime.association

import java.util.Locale

/**
 * Conservative, local spelling candidates. Exact dictionary words are never
 * corrected. One deletion, insertion, substitution or adjacent transposition
 * is looked up in the existing trie; this never scans the whole dictionary.
 * The caller runs this off the UI thread, only when prefix completion is empty
 * or an explicitly listed frequent typo was typed. Nothing is auto-committed.
 */
internal class EnglishTypoCorrections(lines: Sequence<String>) {
    private val frequent = linkedMapOf<String, String>()

    init {
        lines.forEach { line ->
            val fields = line.substringBefore('#').trim().split(Regex("\\s+"))
            if (fields.size == 2 && fields.all { it.length in 3..MAX_LENGTH && it.all { c -> c in 'a'..'z' } } &&
                fields[0] != fields[1]) frequent[fields[0]] = fields[1]
        }
    }

    fun hasFrequentTypo(typed: String): Boolean = typed.lowercase(Locale.US) in frequent

    fun suggestions(typed: String, limit: Int, rankOf: (String) -> Float?): List<String> {
        if (limit <= 0 || typed.length !in 3..MAX_LENGTH || !typed.all { it in 'a'..'z' || it in 'A'..'Z' }) return emptyList()
        val lower = typed.lowercase(Locale.US)
        val title = typed.first().isUpperCase() && typed.drop(1).all { it.isLowerCase() }
        val upper = typed.all { it.isUpperCase() }
        // Avoid offering rewrites of case-sensitive identifiers such as myVar.
        if (typed != lower && !title && !upper) return emptyList()
        if (rankOf(lower) != null) return emptyList()
        val matches = linkedMapOf<String, Float>()
        val visited = HashSet<String>()
        fun consider(word: String) {
            if (word != lower && visited.add(word)) rankOf(word)?.let { matches[word] = it }
        }
        for (i in 0 until lower.lastIndex) {
            if (lower[i] != lower[i + 1]) consider(lower.substring(0, i) + lower[i + 1] + lower[i] + lower.substring(i + 2))
        }
        for (i in lower.indices) {
            consider(lower.removeRange(i, i + 1))
            for (letter in 'a'..'z') if (letter != lower[i]) {
                consider(lower.substring(0, i) + letter + lower.substring(i + 1))
            }
        }
        for (i in 0..lower.length) for (letter in 'a'..'z') {
            consider(lower.substring(0, i) + letter + lower.substring(i))
        }
        val explicit = frequent[lower]
        val ranked = buildList {
            explicit?.let(::add)
            matches.entries.sortedWith(compareBy<Map.Entry<String, Float>> { it.value }.thenBy { it.key })
                .forEach { if (it.key != explicit) add(it.key) }
        }.take(limit)
        return ranked.map { word -> when {
            upper -> word.uppercase(Locale.US)
            title -> word.replaceFirstChar(Char::uppercaseChar)
            else -> word
        } }
    }

    companion object {
        const val ASSET = "english_typo_corrections.tsv"
        // At most 1,299 distinct probes plus the exact-word probe for 24 letters.
        const val MAX_LENGTH = 24
        val EMPTY = EnglishTypoCorrections(emptySequence())
    }
}
