package com.example.pic_ai_app.domain.model

data class UtteranceTranscript(
    val conversationId: String,
    val utteranceId: Int,
    val rawText: String,
    val maskedText: String,
    val hasMaskedData: Boolean,
    val maskedTypes: List<String>,
) {
    companion object {
        fun unmasked(
            conversationId: String,
            utteranceId: Int,
            finalTranscript: String,
        ) = UtteranceTranscript(
            conversationId = conversationId,
            utteranceId = utteranceId,
            rawText = finalTranscript,
            maskedText = finalTranscript,
            hasMaskedData = false,
            maskedTypes = emptyList(),
        )
    }
}
