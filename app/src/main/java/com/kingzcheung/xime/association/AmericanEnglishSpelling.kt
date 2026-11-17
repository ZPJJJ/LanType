package com.kingzcheung.xime.association

import java.util.Locale

/**
 * A small, explicit US spelling preference, not a general spell checker.
 * Only listed whole words are paired; names, mixed-case identifiers and the
 * original British spellings remain usable. No text is committed here.
 */
internal class AmericanEnglishSpelling(lines: Sequence<String>) {
    private val preferred = linkedMapOf<String, String>()

    init {
        lines.forEach { line ->
            val fields = line.substringBefore('#').trim().split(Regex("\\s+"))
            if (fields.size == 2 && fields.all { word -> word.isNotEmpty() && word.all { it in 'a'..'z' } } &&
                fields[0] != fields[1]) preferred[fields[0]] = fields[1]
        }
    }

    /** Whole-word alternatives only: never rewrite a suffix inside a name. */
    fun preferredSpelling(word: String): String? {
        if (word.isEmpty()) return null
        val lower = word.lowercase(Locale.US)
        val form = preferred[lower] ?: return null
        return when {
            word == lower -> form
            word.all { it.isUpperCase() } -> form.uppercase(Locale.US)
            word.first().isUpperCase() && word.drop(1).all { it.isLowerCase() } ->
                form.replaceFirstChar(Char::uppercaseChar)
            else -> null
        }
    }

    /**
     * Add the US form before a known variant, keeping the original word. An
     * exact typed variant also offers its US spelling when the trie has no hit.
     * The editor and its raw-input candidate are never changed automatically.
     */
    fun completions(typed: String, words: List<String>, limit: Int): List<String> {
        if (limit <= 0) return emptyList()
        val result = linkedMapOf<String, String>()
        fun add(word: String) { result.putIfAbsent(word.lowercase(Locale.US), word) }
        val exact = preferredSpelling(typed)
        exact?.let(::add)
        words.forEach { word ->
            preferredSpelling(word)?.let(::add)
            add(word)
        }
        if (exact != null) add(typed)
        return result.values.take(limit)
    }

    /**
     * Missing US forms get the rank of their known variant. This makes prefixes
     * such as "neighbo" complete even if a base lexicon contains only neighbour.
     */
    fun rankedForms(words: Sequence<Pair<String, Float>>): List<Pair<String, Float>> {
        val ranks = linkedMapOf<String, Float>()
        words.forEach { (word, rank) ->
            val form = preferred[word] ?: return@forEach
            ranks[form] = minOf(ranks[form] ?: Float.POSITIVE_INFINITY, rank)
        }
        return ranks.map { it.key to it.value }
    }

    /** US variants gain a frequency preference for glide decoding; none are removed. */
    fun vocabulary(words: List<String>): List<String> {
        val result = LinkedHashSet<String>(words.size + preferred.size)
        words.forEach { word ->
            // The glide lexicon is lowercase. Preserve any future proper-name entries.
            preferred[word]?.let(result::add)
            result.add(word)
        }
        return result.toList()
    }

    companion object {
        const val ASSET = "english_us_spelling.tsv"
        val EMPTY = AmericanEnglishSpelling(emptySequence())
    }
}
