package com.example.pic_ai_app.ner

import com.example.pic_ai_app.domain.model.UtteranceTranscript
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PassThroughTranscriptNerTest {
    @Test
    fun `temporary NER preserves text without claiming that it masked data`() = runBlocking {
        val rawText = "홍길동 씨의 전화번호는 010-1234-5678입니다"
        val transcript = UtteranceTranscript.unmasked(
            conversationId = "20260828_1430",
            utteranceId = 1,
            finalTranscript = rawText,
        )

        val masked = PassThroughTranscriptNer().mask(transcript)

        assertEquals("1.0", masked.schemaVersion)
        assertEquals(transcript.conversationId, masked.conversationId)
        assertEquals(transcript.utteranceId, masked.utteranceId)
        assertEquals(rawText, masked.maskedText)
        assertFalse(masked.hasMaskedData)
        assertTrue(masked.maskedTypes.isEmpty())
    }
}
