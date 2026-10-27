package com.example.pic_ai_app.stt

interface StreamingSttEngine : AutoCloseable {
    fun initialize()

    fun startStream()

    fun acceptAudio(samples: FloatArray): SttDecodeResult

    fun finishStream(): SttDecodeResult

    fun stopStream()
}

data class SttDecodeResult(
    val partialText: String,
    val finalText: String? = null,
    val endpointDetected: Boolean = false,
)
