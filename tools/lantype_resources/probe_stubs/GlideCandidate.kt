// Host-probe DTO only; actual scoring implementations are compiled unchanged.
package com.kingzcheung.xime.glide
data class GlideCandidate(val word: String, val cost: Float, val shape: Float = cost)
