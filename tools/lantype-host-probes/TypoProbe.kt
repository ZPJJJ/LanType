package com.kingzcheung.xime.association
import java.io.File
fun main(args: Array<String>) {
 val c=File(args[0]).useLines { EnglishTypoCorrections(it) }
 val words=mapOf("the" to 1f,"and" to 2f,"receive" to 50f,"hello" to 10f,"world" to 12f,"form" to 5f,"from" to 3f,"color" to 20f)
 for((typo,target) in listOf("teh" to "the","adn" to "and","recieve" to "receive","helllo" to "hello","helo" to "hello","hrllo" to "hello","hlelo" to "hello")) {
  val results=c.suggestions(typo,5,words::get)
  check(results.firstOrNull()==target) { "$typo expected $target actual $results" }
  println("PASS $typo -> $target")
 }
 for(word in listOf("form","hello","myVar","foo@example.com","ab","x".repeat(25))) check(c.suggestions(word,5,words::get).isEmpty()) { word }
 check(c.suggestions("Teh",1,words::get)==listOf("The"))
 check(c.suggestions("TEH",1,words::get)==listOf("THE"))
 var probes=0
 c.suggestions("abcdefghijklmnopqrstuvwx",5) { probes++; null }
 check(probes<=1300) { "probes=$probes" }
 println("PASS real-word, identifier, case, length guards; worst-length trie probes=$probes")
}
