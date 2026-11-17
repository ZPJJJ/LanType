// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.toolcabin

import org.junit.Assert.*
import org.junit.Test

class TextTransformsTest {
    private fun run(tool: TextTool, text: String) = (TextTransforms.apply(tool, text) as CabinResult.Ready).preview.text

    @Test fun commonChineseAndAmericanContactsAreMaskedWhileContextStaysReadable() {
        val source = "联系 13812345678 / +86 139-1234-5678；邮箱 dev@example.com；US +1 (415) 555-0123"
        assertEquals("联系 138****5678 / +86 139****5678；邮箱 d***@example.com；US +1 (415) ***-0123",
            run(TextTool.MASK, source))
        assertTrue(source.contains("13812345678"))
    }

    @Test fun idLikeFormatsAreMaskedBeforeTheirEmbeddedPhoneDigits() {
        assertEquals("证件 110***********123X；旧证 110********1234",
            run(TextTool.MASK, "证件 11010519900101123X；旧证 110105900101234"))
        assertEquals("UnityVector3 token_12345", run(TextTool.MASK, "UnityVector3 token_12345"))
    }

    @Test fun jsonFormattingPreservesHugeNumbersDuplicateKeysAndEscapes() {
        val source = "{\"id\":900719925474099312345,\"x\":1,\"x\":2,\"s\":\"a,}\\n\\u4e2d\",\"a\":[{},[]]}"
        val formatted = run(TextTool.JSON, source)
        assertTrue(formatted.contains("900719925474099312345"))
        assertTrue(formatted.contains("\"x\": 1,\n  \"x\": 2"))
        assertTrue(formatted.contains("\"s\": \"a,}\\n\\u4e2d\""))
        assertEquals(formatted, run(TextTool.JSON, formatted))
        assertEquals("[]", run(TextTool.JSON, "[ ]"))
    }

    @Test fun invalidOrExcessivelyNestedJsonFailsWithNoPartialOutput() {
        for (source in listOf("{\"x\":}", "[1,]", "{abc}"))
            assertEquals(CabinResult.Failed(CabinProblem.INVALID_JSON), TextTransforms.apply(TextTool.JSON, source))
        val nested = "[".repeat(33) + "0" + "]".repeat(33)
        assertEquals(CabinResult.Failed(CabinProblem.JSON_TOO_DEEP), TextTransforms.apply(TextTool.JSON, nested))
    }

    @Test fun urlComponentEncodingRoundTripsUnicodeAndDoesNotTreatPlusAsSpace() {
        val source = "Unity/C# + 中文🙂"
        val encoded = run(TextTool.URL_ENCODE, source)
        assertTrue(encoded.contains("%23%20%2B%20"))
        assertEquals(source, run(TextTool.URL_DECODE, encoded))
        assertEquals("a+b c", run(TextTool.URL_DECODE, "a+b%20c"))
        for (broken in listOf("%", "%GG", "%FF", "%C0%AF"))
            assertEquals(CabinResult.Failed(CabinProblem.INVALID_ENCODING), TextTransforms.apply(TextTool.URL_DECODE, broken))
    }

    @Test fun base64IsUtf8TextAndRejectsBinaryOrDamagedInput() {
        val source = "Lua → C#\n澜语🙂"
        assertEquals(source, run(TextTool.BASE64_DECODE, run(TextTool.BASE64_ENCODE, source)))
        for (broken in listOf("!@#", "/w=="))
            assertEquals(CabinResult.Failed(CabinProblem.INVALID_ENCODING), TextTransforms.apply(TextTool.BASE64_DECODE, broken))
        assertEquals(CabinResult.Failed(CabinProblem.TOO_LONG), TextTransforms.apply(TextTool.MASK, "x".repeat(ToolCabin.MAX_INPUT + 1)))
    }
}
