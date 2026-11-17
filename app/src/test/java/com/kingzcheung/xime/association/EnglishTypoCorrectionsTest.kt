package com.kingzcheung.xime.association

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EnglishTypoCorrectionsTest {
    private val corrections = listOf(File("src/main/assets/${EnglishTypoCorrections.ASSET}"),
        File("app/src/main/assets/${EnglishTypoCorrections.ASSET}")).first { it.isFile }
        .useLines { EnglishTypoCorrections(it) }
    private val words = mapOf("the" to 1f, "and" to 2f, "receive" to 50f, "hello" to 10f,
        "world" to 12f, "form" to 5f, "from" to 3f, "color" to 20f)

    @Test fun commonMistakesOfferRealCorrections() {
        for ((typed, expected) in listOf("teh" to "the", "adn" to "and", "recieve" to "receive")) {
            assertEquals(expected, corrections.suggestions(typed, 5, words::get).first())
        }
    }

    @Test fun oneEditFallbackUsesTheDictionaryForTyposOutsideTheExplicitTable() {
        // Extra, omitted, substituted and adjacent-swapped letters.
        for (typed in listOf("helllo", "helo", "hrllo", "hlelo")) {
            assertEquals("hello", corrections.suggestions(typed, 5, words::get).first())
        }
    }

    @Test fun realWordsIdentifiersAndNonWordsOutsideTheBoundAreNotRewritten() {
        for (typed in listOf("form", "hello", "myVar", "foo@example.com", "ab", "x".repeat(25))) {
            assertTrue(typed, corrections.suggestions(typed, 5, words::get).isEmpty())
        }
        assertTrue(corrections.suggestions("teh", 0, words::get).isEmpty())
    }

    @Test fun caseAndResultLimitArePreserved() {
        assertEquals(listOf("The"), corrections.suggestions("Teh", 1, words::get))
        assertEquals(listOf("THE"), corrections.suggestions("TEH", 1, words::get))
    }

    @Test fun worstLengthHasABoundedNumberOfTrieQueries() {
        var probes = 0
        corrections.suggestions("abcdefghijklmnopqrstuvwx", 5) { probes++; null }
        assertTrue("bounded independent of dictionary size: $probes", probes <= 1300)
    }
}
