package com.example.pic_ai_app.data.stt

import com.example.pic_ai_app.masking.regex.OtpProtection
import com.example.pic_ai_app.domain.model.UtteranceTranscript
import com.example.pic_ai_app.masking.MaskingPipeline
import com.example.pic_ai_app.masking.TranscriptMasker
import com.example.pic_ai_app.masking.ner.NerCandidateDetector
import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.regex.DefaultRegexCandidateDetector
import com.example.pic_ai_app.masking.rule.DefaultNumberMaskingRuleEngine
import com.example.pic_ai_app.masking.resolver.DefaultCandidateConflictResolver
import com.example.pic_ai_app.masking.renderer.DefaultMaskedTextRenderer
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class OtpProtectionTest {
    @Test fun protectsDigitsAndSpokenDigitsWithContext() {
        val same = OtpProtection.protect("인증번호 123456 알려주세요", 0)
        assertEquals("인증번호 [OTP] 알려주세요", same.text)
        val cue = OtpProtection.protect("인증번호 알려주세요", 0)
        val next = OtpProtection.protect("일 이 삼 사 오 육", cue.nextWindow)
        assertEquals("[OTP]", next.text)
        assertTrue(next.count > 0)
        assertEquals("123456", OtpProtection.protect("123456", 0).text)
    }
    @Test fun maskedTranscriptIncludesOtpTypeAcrossUtterances() = runBlocking {
        val ner = object : NerCandidateDetector {
            override suspend fun detect(text: String): List<MaskCandidate> = emptyList()
        }
        val masker = TranscriptMasker(MaskingPipeline(ner, DefaultRegexCandidateDetector(),
            DefaultNumberMaskingRuleEngine(), DefaultCandidateConflictResolver(), DefaultMaskedTextRenderer()))
        masker.mask(UtteranceTranscript.unmasked("call", 1, "인증번호 알려주세요"))
        val result = masker.mask(UtteranceTranscript.unmasked("call", 2, "일 이 삼 사 오 육"))
        assertEquals("[OTP]", result.maskedText)
        assertEquals(listOf("OTP"), result.maskedTypes)
        assertTrue(result.hasMaskedData)
    }

}
