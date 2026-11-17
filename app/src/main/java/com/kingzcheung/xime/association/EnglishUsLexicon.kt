package com.kingzcheung.xime.association

import android.content.Context

/** Shared immutable regional spelling table, read on the existing background lanes. */
internal object EnglishUsLexicon {
    @Volatile private var loaded: AmericanEnglishSpelling? = null
    @Volatile private var loadedTypos: EnglishTypoCorrections? = null

    fun get(context: Context): AmericanEnglishSpelling = loaded ?: synchronized(this) {
        loaded ?: runCatching {
            context.assets.open(AmericanEnglishSpelling.ASSET).bufferedReader().useLines {
                AmericanEnglishSpelling(it)
            }.also { loaded = it }
        }.getOrDefault(AmericanEnglishSpelling.EMPTY)
    }

    fun typos(context: Context): EnglishTypoCorrections = loadedTypos ?: synchronized(this) {
        loadedTypos ?: runCatching {
            context.assets.open(EnglishTypoCorrections.ASSET).bufferedReader().useLines {
                EnglishTypoCorrections(it)
            }.also { loadedTypos = it }
        }.getOrDefault(EnglishTypoCorrections.EMPTY)
    }
}
