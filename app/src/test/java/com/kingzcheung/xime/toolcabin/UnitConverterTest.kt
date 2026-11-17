// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.toolcabin

import java.time.ZonedDateTime
import org.junit.Assert.*
import org.junit.Test

class UnitConverterTest {
    private fun converted(input: String) = (UnitConverter.convert(input) as CabinResult.Ready).preview

    @Test fun binaryAndDecimalStorageAreDifferentAndExact() {
        assertEquals("2621440 B", converted("2.5 MiB → B").text)
        assertEquals("2500000 B", converted("2.5 MB -> B").text)
        assertEquals("1 GiB", converted("1024 MiB to GiB").text)
        assertEquals("1 KB", converted("1000字节到KB").text)
    }

    @Test fun developerFrameAndAngleConversionsSignalRounding() {
        assertEquals("16.6666666667 ms/frame", converted("60 fps -> ms/frame").text)
        assertTrue(converted("60 fps -> ms/frame").note.contains("≈"))
        assertEquals("50 fps", converted("20 ms/frame → fps").text)
        assertEquals("3.14159265359 rad", converted("180 deg → rad").text)
        assertEquals("500 ms", converted(".5 s to ms").text)
    }

    @Test fun temperatureUsesAnOffsetAndLengthUsesExactFactors() {
        assertEquals("0 °C", converted("32 F → C").text)
        assertEquals("212 °F", converted("100 ℃ → ℉").text)
        assertEquals("273.15 K", converted("0 C → K").text)
        assertEquals("30.48 cm", converted("1 ft → cm").text)
    }

    @Test fun invalidDimensionsAndNonphysicalValuesDoNotInventAResult() {
        assertEquals(CabinResult.Failed(CabinProblem.DIFFERENT_DIMENSIONS), UnitConverter.convert("5 ms → B"))
        assertEquals(CabinResult.Failed(CabinProblem.UNKNOWN_UNIT), UnitConverter.convert("1 USD → CNY"))
        assertEquals(CabinResult.Failed(CabinProblem.UNKNOWN_UNIT), UnitConverter.convert("2 Mb → MB"))
        for (input in listOf("0 fps → ms/frame", "-1 K → C", "-274 C → F", "1e999 s → ms"))
            assertEquals(input, CabinResult.Failed(CabinProblem.INVALID_VALUE), UnitConverter.convert(input))
        assertEquals(CabinResult.Failed(CabinProblem.INVALID_CALCULATION), UnitConverter.convert("1 + 2 ms"))
    }

    @Test fun arithmeticReusesExistingEngineWithoutChangingTheDraft() {
        val state = ToolCabinState(input = "（１０＋５）÷３".replace('（', '(').replace('）', ')'))
        assertEquals("5", (ToolCabin.preview(state, ZonedDateTime.parse("2026-11-17T08:09:10Z")) as CabinResult.Ready).preview.text)
        assertEquals("(１０＋５)÷３", state.input)
        assertTrue(ToolCabin.preview(state.copy(input = "1/0"), ZonedDateTime.now()) is CabinResult.Failed)
    }
}
