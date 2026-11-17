// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.toolcabin

import kotlinx.serialization.json.Json
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.nio.charset.StandardCharsets
import java.util.Base64

/** Stateless transforms of explicitly provided text. No editor/clipboard access, logging or storage. */
object TextTransforms {
    private val identity = Regex("(?<![A-Za-z0-9])(?:[0-9]{17}[0-9Xx]|[0-9]{15})(?![A-Za-z0-9])")
    private val chinesePhone = Regex("(?<![0-9])((?:\\+?86[ -]?)?1[3-9][0-9])[ -]?([0-9]{4})[ -]?([0-9]{4})(?![0-9])")
    private val usPhone = Regex("(?<![0-9])((?:\\+1[ .-]?)?(?:\\([2-9][0-9]{2}\\)|[2-9][0-9]{2})[ .-]?)([0-9]{3})([ .-]?)([0-9]{4})(?![0-9])")
    private val email = Regex("(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\\.[A-Za-z]{2,})(?![A-Za-z0-9._%+-])")

    fun apply(tool: TextTool, text: String): CabinResult {
        if (text.isEmpty()) return CabinResult.Failed(CabinProblem.EMPTY)
        if (text.length > ToolCabin.MAX_INPUT) return CabinResult.Failed(CabinProblem.TOO_LONG)
        return try {
            val output = when (tool) {
                TextTool.MASK -> mask(text)
                TextTool.JSON -> return formatJson(text)
                TextTool.URL_ENCODE -> encodeUrl(text)
                TextTool.URL_DECODE -> decodeUrl(text)
                TextTool.BASE64_ENCODE -> Base64.getEncoder().encodeToString(text.toByteArray(StandardCharsets.UTF_8))
                TextTool.BASE64_DECODE -> utf8(Base64.getDecoder().decode(text.trim()))
            }
            if (output.length > ToolCabin.MAX_OUTPUT) CabinResult.Failed(CabinProblem.TOO_LONG)
            else CabinResult.Ready(CabinPreview(output))
        } catch (_: IllegalArgumentException) {
            CabinResult.Failed(CabinProblem.INVALID_ENCODING)
        } catch (_: java.nio.charset.CharacterCodingException) {
            CabinResult.Failed(CabinProblem.INVALID_ENCODING)
        }
    }

    fun mask(text: String): String {
        var result = identity.replace(text) { match ->
            match.value.take(3) + "*".repeat(match.value.length - 7) + match.value.takeLast(4)
        }
        result = chinesePhone.replace(result) { "${it.groupValues[1]}****${it.groupValues[3]}" }
        result = usPhone.replace(result) { "${it.groupValues[1]}***${it.groupValues[3]}${it.groupValues[4]}" }
        return email.replace(result) { "${it.groupValues[1].first()}***@${it.groupValues[2]}" }
    }

    private fun utf8(bytes: ByteArray): String = StandardCharsets.UTF_8.newDecoder()
        .onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT)
        .decode(ByteBuffer.wrap(bytes)).toString()

    /** RFC 3986 component encoding: spaces become %20, and + remains a literal plus on decoding. */
    private fun encodeUrl(text: String): String = buildString {
        for (byte in text.toByteArray(StandardCharsets.UTF_8)) {
            val value = byte.toInt() and 255
            if (value in 65..90 || value in 97..122 || value in 48..57 || value.toChar() in "-._~") append(value.toChar())
            else { append('%'); append("0123456789ABCDEF"[value ushr 4]); append("0123456789ABCDEF"[value and 15]) }
        }
    }

    private fun decodeUrl(text: String): String {
        val bytes = ByteArrayOutputStream()
        var start = 0
        var index = 0
        while (index < text.length) {
            if (text[index] != '%') { index++; continue }
            bytes.write(text.substring(start, index).toByteArray(StandardCharsets.UTF_8))
            require(index + 2 < text.length)
            val high = text[index + 1].digitToIntOrNull(16) ?: throw IllegalArgumentException()
            val low = text[index + 2].digitToIntOrNull(16) ?: throw IllegalArgumentException()
            bytes.write((high shl 4) or low)
            index += 3; start = index
        }
        bytes.write(text.substring(start).toByteArray(StandardCharsets.UTF_8))
        return utf8(bytes.toByteArray())
    }

    private fun formatJson(text: String): CabinResult {
        var depth = 0
        var quoted = false
        var escaped = false
        for (char in text) {
            if (quoted) {
                if (escaped) escaped = false else if (char == '\\') escaped = true else if (char == '"') quoted = false
            } else when (char) {
                '"' -> quoted = true
                '{', '[' -> if (++depth > 32) return CabinResult.Failed(CabinProblem.JSON_TOO_DEEP)
                '}', ']' -> depth--
            }
        }
        try { Json.parseToJsonElement(text) }
        catch (_: IllegalArgumentException) { return CabinResult.Failed(CabinProblem.INVALID_JSON) }
        // Format lexically after validation: preserve number precision, duplicate keys and escape spellings.
        val output = StringBuilder()
        depth = 0; quoted = false; escaped = false
        fun newline() { output.append('\n'); repeat(depth) { output.append("  ") } }
        var previous: Char? = null
        for ((index, char) in text.withIndex()) {
            if (quoted) {
                output.append(char)
                if (escaped) escaped = false else if (char == '\\') escaped = true else if (char == '"') quoted = false
            } else when {
                char.isWhitespace() -> continue
                char == '"' -> { output.append(char); quoted = true }
                char == '{' || char == '[' -> {
                    output.append(char); depth++
                    var nextIndex = index + 1
                    while (nextIndex < text.length && text[nextIndex].isWhitespace()) nextIndex++
                    val next = text.getOrNull(nextIndex)
                    if (next != '}' && next != ']') newline()
                }
                char == '}' || char == ']' -> {
                    depth--
                    if (previous != '{' && previous != '[') newline()
                    output.append(char)
                }
                char == ',' -> { output.append(char); newline() }
                char == ':' -> output.append(": ")
                else -> output.append(char)
            }
            if (!quoted && !char.isWhitespace()) previous = char
            if (output.length > ToolCabin.MAX_OUTPUT) return CabinResult.Failed(CabinProblem.TOO_LONG)
        }
        return CabinResult.Ready(CabinPreview(output.toString()))
    }
}
