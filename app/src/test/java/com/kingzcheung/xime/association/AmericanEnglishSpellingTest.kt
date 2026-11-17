package com.kingzcheung.xime.association

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AmericanEnglishSpellingTest {
    private val spelling = listOf(File("src/main/assets/${AmericanEnglishSpelling.ASSET}"),
        File("app/src/main/assets/${AmericanEnglishSpelling.ASSET}")).first { it.isFile }
        .useLines { AmericanEnglishSpelling(it) }

    @Test fun commonVariantsOfferUsFirstWithoutLosingTheTypedSpelling() {
        for ((typed, expected) in listOf("colour" to "color", "favourite" to "favorite",
            "centre" to "center", "organised" to "organized")) {
            val suggestions = spelling.completions(typed, listOf(typed), 8)
            assertEquals(expected, suggestions.first())
            assertTrue("The original remains selectable: $typed", typed in suggestions)
        }
    }

    @Test fun partialBritishSpellingCanOfferAnAmericanCompletion() {
        assertEquals(listOf("color", "colour", "colorful", "colourful"),
            spelling.completions("colou", listOf("colour", "colourful"), 8))
        assertEquals(listOf("favorite", "favourite", "favorites", "favourites"),
            spelling.completions("favo", listOf("favourite", "favorites", "favourites"), 8))
    }

    @Test fun usPrefixStillCompletesWhenOnlyTheBritishSpellingWasInTheDictionary() {
        val extra = spelling.rankedForms(sequenceOf("neighbour" to 42f, "colour" to 50f,
            "neighborhood" to 12f, "unrelated" to 2f))
        assertEquals(listOf("neighbor"), extra.filter { it.first.startsWith("neighbo") }.map { it.first })
        assertEquals(42f, extra.first { it.first == "neighbor" }.second)
        assertEquals(listOf("color"), extra.filter { it.first.startsWith("color") }.map { it.first })
    }

    @Test fun capitalizationFollowsTheUserButIdentifiersAndNamesArePreserved() {
        assertEquals("Favorite", spelling.preferredSpelling("Favourite"))
        assertEquals("FAVORITE", spelling.preferredSpelling("FAVOURITE"))
        for (literal in listOf("iPhone", "McColour", "ColourPop", "Grey", "coLOUR", "enterprise", "acre", "analyses")) {
            assertNull("No blanket suffix rewrite: $literal", spelling.preferredSpelling(literal))
            assertEquals(listOf(literal), spelling.completions(literal, listOf(literal), 8))
        }
    }

    @Test fun glideVocabularyPrefersUsFormsAndRetainsEveryExistingWord() {
        val original = listOf("hello", "colour", "world", "color", "favourite", "Grey")
        val ranked = spelling.vocabulary(original)
        assertEquals(listOf("hello", "color", "colour", "world", "favorite", "favourite", "Grey"), ranked)
        assertTrue(ranked.containsAll(original))
        assertEquals(ranked.size, ranked.toSet().size)
    }

    @Test fun ordinaryCompletionsAndExplicitResultLimitsAreRespected() {
        assertEquals(listOf("hello", "help"), spelling.completions("hel", listOf("hello", "help"), 8))
        assertEquals(listOf("color"), spelling.completions("colour", listOf("colour"), 1))
        assertEquals(emptyList<String>(), spelling.completions("colour", listOf("colour"), 0))
        assertEquals(listOf("color", "colour"), spelling.completions("colour", emptyList(), 8))
    }
}
