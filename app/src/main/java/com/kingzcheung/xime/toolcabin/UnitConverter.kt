// SPDX-License-Identifier: GPL-3.0-or-later
package com.kingzcheung.xime.toolcabin

import java.math.BigDecimal
import java.math.MathContext
import java.math.RoundingMode
import java.util.Locale

/** Deterministic local conversion. KB is decimal; KiB is binary. No currency/rate lookups. */
object UnitConverter {
    private enum class Quantity { TIME, BYTES, LENGTH, ANGLE, TEMPERATURE, FRAME }
    private data class Unit(val symbol: String, val quantity: Quantity, val factor: BigDecimal = BigDecimal.ONE)
    private val mc = MathContext.DECIMAL128
    private val display = MathContext(12, RoundingMode.HALF_UP)
    private val pi = BigDecimal("3.141592653589793238462643383279503")
    private val units = buildMap<String, Unit> {
        fun add(symbol: String, quantity: Quantity, factor: String = "1", vararg aliases: String) {
            val unit = Unit(symbol, quantity, BigDecimal(factor))
            (listOf(symbol) + aliases).forEach { put(it.lowercase(Locale.ROOT), unit) }
        }
        add("ms", Quantity.TIME, ".001", "毫秒")
        add("s", Quantity.TIME, "1", "sec", "秒")
        add("min", Quantity.TIME, "60", "分钟")
        add("h", Quantity.TIME, "3600", "hr", "小时")
        add("B", Quantity.BYTES, "1", "byte", "bytes", "字节")
        add("KB", Quantity.BYTES, "1000"); add("MB", Quantity.BYTES, "1000000")
        add("GB", Quantity.BYTES, "1000000000")
        add("KiB", Quantity.BYTES, "1024"); add("MiB", Quantity.BYTES, "1048576")
        add("GiB", Quantity.BYTES, "1073741824")
        add("mm", Quantity.LENGTH, ".001"); add("cm", Quantity.LENGTH, ".01")
        add("m", Quantity.LENGTH, "1", "米"); add("km", Quantity.LENGTH, "1000", "公里")
        add("in", Quantity.LENGTH, ".0254", "inch"); add("ft", Quantity.LENGTH, ".3048")
        add("deg", Quantity.ANGLE, "1", "°", "度"); add("rad", Quantity.ANGLE, "1", "弧度")
        add("°C", Quantity.TEMPERATURE, "1", "C", "℃")
        add("°F", Quantity.TEMPERATURE, "1", "F", "℉")
        add("K", Quantity.TEMPERATURE)
        add("fps", Quantity.FRAME); add("ms/frame", Quantity.FRAME)
    }
    private val expression = Regex(
        """^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?)\s*([\p{L}°℃℉/]+)\s*(?:->|→|to|到|转)\s*([\p{L}°℃℉/]+)\s*$""",
        RegexOption.IGNORE_CASE,
    )
    private val byteSymbol = Regex("(?:[kmg]i?)?b", RegexOption.IGNORE_CASE)

    private fun resolveUnit(symbol: String): Unit? {
        // Lowercase b conventionally means bits. Reject it instead of silently returning an 8x-wrong byte value.
        if (byteSymbol.matches(symbol) && symbol.last() != 'B') return null
        return units[symbol.lowercase(Locale.ROOT)]
    }

    fun convert(source: String): CabinResult {
        if (source.length > 256) return CabinResult.Failed(CabinProblem.INVALID_CALCULATION)
        val parts = expression.matchEntire(source) ?: return CabinResult.Failed(CabinProblem.INVALID_CALCULATION)
        val value = parts.groupValues[1].toBigDecimalOrNull() ?: return CabinResult.Failed(CabinProblem.INVALID_VALUE)
        if (value.precision() > 64 || value.scale() !in -100..100) return CabinResult.Failed(CabinProblem.INVALID_VALUE)
        val from = resolveUnit(parts.groupValues[2]) ?: return CabinResult.Failed(CabinProblem.UNKNOWN_UNIT)
        val to = resolveUnit(parts.groupValues[3]) ?: return CabinResult.Failed(CabinProblem.UNKNOWN_UNIT)
        if (from.quantity != to.quantity) return CabinResult.Failed(CabinProblem.DIFFERENT_DIMENSIONS)
        val result = when (from.quantity) {
            Quantity.FRAME -> {
                if (value.signum() <= 0) return CabinResult.Failed(CabinProblem.INVALID_VALUE)
                if (from == to) value else BigDecimal("1000").divide(value, mc)
            }
            Quantity.TEMPERATURE -> {
                val kelvin = when (from.symbol) {
                    "°C" -> value + BigDecimal("273.15")
                    "°F" -> (value - BigDecimal("32")).multiply(BigDecimal("5"), mc)
                        .divide(BigDecimal("9"), mc) + BigDecimal("273.15")
                    else -> value
                }
                if (kelvin.signum() < 0) return CabinResult.Failed(CabinProblem.INVALID_VALUE)
                when (to.symbol) {
                    "°C" -> kelvin - BigDecimal("273.15")
                    "°F" -> (kelvin - BigDecimal("273.15")).multiply(BigDecimal("9"), mc)
                        .divide(BigDecimal("5"), mc) + BigDecimal("32")
                    else -> kelvin
                }
            }
            Quantity.ANGLE -> if (from == to) value else if (from.symbol == "deg")
                value.multiply(pi, mc).divide(BigDecimal("180"), mc)
            else value.multiply(BigDecimal("180"), mc).divide(pi, mc)
            else -> value.multiply(from.factor, mc).divide(to.factor, mc)
        }
        val rounded = result.round(display).stripTrailingZeros()
        val formatted = rounded.toPlainString()
        val approximate = rounded.compareTo(result) != 0
        return CabinResult.Ready(CabinPreview("$formatted ${to.symbol}",
            note = "${parts.groupValues[1]} ${from.symbol} ${if (approximate) "≈" else "="} $formatted ${to.symbol}"))
    }
}
