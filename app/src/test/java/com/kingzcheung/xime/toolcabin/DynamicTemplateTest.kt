// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.toolcabin

import java.time.ZonedDateTime
import org.junit.Assert.*
import org.junit.Test

class DynamicTemplateTest {
    private val now = ZonedDateTime.parse("2026-11-17T08:09:10+08:00")
    private fun expanded(source: String, clipboard: String? = null) =
        (DynamicTemplate.expand(source, now, clipboard) as CabinResult.Ready).preview

    @Test fun cSharpSlotLandsBetweenTheQuotesAndDateIsFrozenForPreview() {
        val preview = expanded(ToolCabin.CS_TEMPLATE)
        assertEquals("Debug.Log(\"\"); // 2026-11-17", preview.text)
        assertEquals("Debug.Log(\"".length, preview.cursor)
        assertEquals("Debug.Log(\"hello\"); // 2026-11-17",
            preview.text.substring(0, preview.cursor) + "hello" + preview.text.substring(preview.cursor))
        assertEquals("2026-11-17 08:09:10", expanded("{{datetime}}").text)
    }

    @Test fun clipboardRequiresExplicitSupplyAndItsTokensAreOnlyLiteralText() {
        assertEquals(CabinResult.ClipboardRequired, DynamicTemplate.expand(ToolCabin.CLIPBOARD_TEMPLATE, now))
        val preview = expanded("引用 {{clipboard}} {{cursor}}", "{{date}} & {{cursor}}")
        assertEquals("引用 {{date}} & {{cursor}} ", preview.text)
        assertEquals(preview.text.length, preview.cursor)
    }

    @Test fun slotUsesAndroidUtf16OffsetsAndUnknownTokensStayLiteral() {
        val preview = expanded("🙂{{cursor}} {{name}}")
        assertEquals("🙂 {{name}}", preview.text)
        assertEquals(2, preview.cursor)
        assertEquals("return value", expanded("return value").text)
        assertEquals(12, expanded("return value").cursor)
    }

    @Test fun ambiguousSlotsAndExpansionBombsAreRejected() {
        assertEquals(CabinResult.Failed(CabinProblem.MANY_CURSORS), DynamicTemplate.expand("{{cursor}}x{{cursor}}", now))
        assertEquals(CabinResult.Failed(CabinProblem.TOO_LONG), DynamicTemplate.expand("{{clipboard}}".repeat(5), now, "x".repeat(ToolCabin.MAX_INPUT)))
    }
}
