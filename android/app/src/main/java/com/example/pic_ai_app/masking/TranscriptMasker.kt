package com.example.pic_ai_app.masking

import com.example.pic_ai_app.domain.model.MaskedTranscript
import com.example.pic_ai_app.domain.model.UtteranceTranscript
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class TranscriptMasker(
    private val pipeline: MaskingPipeline,
) {
    suspend fun mask(
        transcript: UtteranceTranscript,
    ): MaskedTranscript = withContext(Dispatchers.Default) {
        val result = pipeline.mask(transcript.rawText)

        MaskedTranscript(
            conversationId = transcript.conversationId,
            utteranceId = transcript.utteranceId,
            maskedText = result.maskedText,
            hasMaskedData = result.hasMaskedData,
            maskedTypes = result.maskedTypes.map { it.name },
        )
    }
}