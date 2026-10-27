package com.example.pic_ai_app.domain.remote

import com.example.pic_ai_app.domain.model.MaskedTranscript

interface MaskedTranscriptSender {
    suspend fun send(transcript: MaskedTranscript)
}

class MaskedTranscriptTransmissionException : RuntimeException(
    "Masked transcript transmission failed",
)
