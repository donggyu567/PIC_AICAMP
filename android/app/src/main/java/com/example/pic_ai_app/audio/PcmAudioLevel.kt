package com.example.pic_ai_app.audio

import kotlin.math.log10
import kotlin.math.sqrt

/** Relative loudness of one signed little-endian PCM16 block, mapped from -60..0 dBFS to 0..1. */
internal fun pcm16Level(bytes: ByteArray): Float {
    val sampleCount = bytes.size / 2
    if (sampleCount == 0) return 0f
    var sumSquares = 0.0
    for (index in 0 until sampleCount) {
        val offset = index * 2
        val sample = (bytes[offset + 1].toInt() shl 8) or (bytes[offset].toInt() and 0xff)
        sumSquares += sample * sample
    }
    val rms = sqrt(sumSquares / sampleCount) / 32768.0
    if (rms <= 0.001) return 0f
    return ((20.0 * log10(rms) + 60.0) / 60.0).toFloat().coerceIn(0f, 1f)
}
