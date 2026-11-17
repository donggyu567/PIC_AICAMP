package com.example.pic_ai_app.masking

import com.example.pic_ai_app.domain.model.MaskedTranscript
import com.example.pic_ai_app.domain.model.UtteranceTranscript
import com.example.pic_ai_app.masking.rule.RuleContext
import com.example.pic_ai_app.masking.regex.OtpProtection
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
    private var otpWindow = 0

    suspend fun mask(
        transcript: UtteranceTranscript,
    ): MaskedTranscript = withContext(Dispatchers.Default) {
        contextMutex.withLock {
            val context = if (activeConversationId == transcript.conversationId) {
                ruleContext
            } else {
                RuleContext()
            }
            val priorWindow = if (activeConversationId == transcript.conversationId) otpWindow else 0
            val otp = OtpProtection.protect(transcript.rawText, priorWindow)
            val result = pipeline.maskWithContext(otp.text, context)
            // Never send a result if another masking step altered an OTP token.
            require(Regex("\\[OTP\\]").findAll(otp.text).count() ==
                Regex("\\[OTP\\]").findAll(result.maskedText).count())
            val maskedTypes = result.resolvedCandidates
                .sortedBy { it.start }
                .map { it.type.name }
                .plus(if (otp.count > 0) listOf("OTP") else emptyList())
                .distinct()

            val maskedTranscript = MaskedTranscript(
                conversationId = transcript.conversationId,
                utteranceId = transcript.utteranceId,
                maskedText = result.maskedText,
                hasMaskedData = maskedTypes.isNotEmpty(),
                maskedTypes = maskedTypes,
            )
            activeConversationId = transcript.conversationId
            ruleContext = result.updatedContext
            otpWindow = otp.nextWindow
            maskedTranscript
        }
    }
}
