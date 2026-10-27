package com.example.pic_ai_app.domain.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UtteranceTranscriptTest {
    @Test
    fun `unmasked factory preserves final transcript exactly`() {
        val finalTranscript = "  교정하면 안 되는  문자열 "

        val transcript = UtteranceTranscript.unmasked(
            conversationId = "20260820_2246",
            utteranceId = 3,
            finalTranscript = finalTranscript,
        )

        assertEquals(finalTranscript, transcript.rawText)
        assertEquals(finalTranscript, transcript.maskedText)
        assertFalse(transcript.hasMaskedData)
        assertTrue(transcript.maskedTypes.isEmpty())
    }
}
