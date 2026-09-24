package com.example.pic_ai_app.masking

import com.example.pic_ai_app.domain.model.UtteranceTranscript
import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.ner.NerCandidateDetector
import com.example.pic_ai_app.masking.regex.DefaultRegexCandidateDetector
import com.example.pic_ai_app.masking.renderer.DefaultMaskedTextRenderer
import com.example.pic_ai_app.masking.resolver.DefaultCandidateConflictResolver
import com.example.pic_ai_app.masking.rule.DefaultNumberMaskingRuleEngine
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test

class TranscriptMaskerTest {
    @Test
    fun `account context carries to next utterance only in same conversation`() = runBlocking {
        val pipeline = MaskingPipeline(
            nerDetector = object : NerCandidateDetector {
                override suspend fun detect(text: String): List<MaskCandidate> = emptyList()
            },
            regexDetector = DefaultRegexCandidateDetector(),
            ruleEngine = DefaultNumberMaskingRuleEngine(),
            conflictResolver = DefaultCandidateConflictResolver(),
            renderer = DefaultMaskedTextRenderer(),
        )
        val masker = TranscriptMasker(pipeline)

        val keyword = masker.mask(UtteranceTranscript.unmasked("conversation-a", 1, "계좌번호 알려주세요"))
        val sameConversation = masker.mask(UtteranceTranscript.unmasked("conversation-a", 2, "123456789"))
        val newConversation = masker.mask(UtteranceTranscript.unmasked("conversation-b", 1, "123456789"))

        assertEquals("계좌번호 알려주세요", keyword.maskedText)
        assertEquals("[ACCOUNT_NUMBER]", sameConversation.maskedText)
        assertEquals(listOf("ACCOUNT_NUMBER"), sameConversation.maskedTypes)
        assertEquals("[MASKED]", newConversation.maskedText)
    }
}
