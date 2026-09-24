package com.example.pic_ai_app.masking

import com.example.pic_ai_app.domain.model.MaskedTranscript
import com.example.pic_ai_app.domain.model.UtteranceTranscript
import com.example.pic_ai_app.masking.rule.RuleContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

class TranscriptMasker(
    private val pipeline: MaskingPipeline,
) {
    private val contextMutex = Mutex()
    private var activeConversationId: String? = null
    private var ruleContext = RuleContext()

    suspend fun mask(
        transcript: UtteranceTranscript,
    ): MaskedTranscript = withContext(Dispatchers.Default) {
        contextMutex.withLock {
            val context = if (activeConversationId == transcript.conversationId) {
                ruleContext
            } else {
                RuleContext()
            }
            val result = pipeline.maskWithContext(transcript.rawText, context)
            val maskedTypes = result.resolvedCandidates
                .sortedBy { it.start }
                .map { it.type }
                .distinct()

            val maskedTranscript = MaskedTranscript(
                conversationId = transcript.conversationId,
                utteranceId = transcript.utteranceId,
                maskedText = result.maskedText,
                hasMaskedData = maskedTypes.isNotEmpty(),
                maskedTypes = maskedTypes.map { it.name },
            )
            activeConversationId = transcript.conversationId
            ruleContext = result.updatedContext
            maskedTranscript
        }
    }
}
