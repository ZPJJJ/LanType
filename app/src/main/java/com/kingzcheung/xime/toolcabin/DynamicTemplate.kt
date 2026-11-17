// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.toolcabin

import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

object DynamicTemplate {
    private val tokens = Regex("\\{\\{(date|time|datetime|cursor|clipboard)}}")
    private val date = DateTimeFormatter.ofPattern("yyyy-MM-dd")
    private val time = DateTimeFormatter.ofPattern("HH:mm:ss")

    /** One pass: tokens found inside clipboard text are data, never evaluated. UTF-16 cursor offsets match Android. */
    fun expand(template: String, now: ZonedDateTime, clipboard: String? = null): CabinResult {
        if (template.length > ToolCabin.MAX_INPUT || (clipboard?.length ?: 0) > ToolCabin.MAX_INPUT)
            return CabinResult.Failed(CabinProblem.TOO_LONG)
        val matches = tokens.findAll(template).toList()
        if (matches.count { it.groupValues[1] == "cursor" } > 1) return CabinResult.Failed(CabinProblem.MANY_CURSORS)
        if (clipboard == null && matches.any { it.groupValues[1] == "clipboard" }) return CabinResult.ClipboardRequired
        val output = StringBuilder()
        var cursor: Int? = null
        var position = 0
        for (match in matches) {
            output.append(template, position, match.range.first)
            when (match.groupValues[1]) {
                "date" -> output.append(date.format(now))
                "time" -> output.append(time.format(now))
                "datetime" -> output.append(date.format(now)).append(' ').append(time.format(now))
                "clipboard" -> output.append(clipboard.orEmpty())
                "cursor" -> cursor = output.length
            }
            if (output.length > ToolCabin.MAX_OUTPUT) return CabinResult.Failed(CabinProblem.TOO_LONG)
            position = match.range.last + 1
        }
        output.append(template, position, template.length)
        if (output.length > ToolCabin.MAX_OUTPUT) return CabinResult.Failed(CabinProblem.TOO_LONG)
        return CabinResult.Ready(CabinPreview(output.toString(), cursor ?: output.length))
    }
}
