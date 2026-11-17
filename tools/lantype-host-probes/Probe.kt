package com.kingzcheung.xime.association
import java.io.File
fun main(args: Array<String>) {
    val spelling = File(args[0]).useLines { AmericanEnglishSpelling(it) }
    fun checkCase(name: String, actual: Any?, expected: Any?) {
        check(actual == expected) { "$name: expected=$expected actual=$actual" }
        println("PASS $name")
    }
    checkCase("US variants and literal preserved", spelling.completions("colour", listOf("colour", "colours"), 8), listOf("color", "colour", "colors", "colours"))
    checkCase("Favorite", spelling.completions("favourite", listOf("favourite"), 8), listOf("favorite", "favourite"))
    checkCase("prefix", spelling.completions("colou", listOf("colour", "colourful"), 8), listOf("color", "colour", "colorful", "colourful"))
    checkCase("all caps", spelling.preferredSpelling("FAVOURITE"), "FAVORITE")
    checkCase("name", spelling.preferredSpelling("McColour"), null)
    checkCase("US noun analyses", spelling.preferredSpelling("analyses"), null)
    checkCase("unknown literal", spelling.completions("McColour", listOf("McColour"), 8), listOf("McColour"))
    checkCase("extra US prefix", spelling.rankedForms(sequenceOf("neighbour" to 42f)).filter { it.first.startsWith("neighbo") }.map { it.first }, listOf("neighbor"))
    checkCase("glide order and preservation", spelling.vocabulary(listOf("hello", "colour", "world", "color", "favourite", "Grey")), listOf("hello", "color", "colour", "world", "favorite", "favourite", "Grey"))
    checkCase("unrelated suggestions", spelling.completions("hel", listOf("hello", "help"), 8), listOf("hello", "help"))
}
