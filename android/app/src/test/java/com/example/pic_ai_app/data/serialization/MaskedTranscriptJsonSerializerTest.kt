package com.example.pic_ai_app.data.serialization

import com.example.pic_ai_app.domain.model.MaskedTranscript
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class MaskedTranscriptJsonSerializerTest {
    private val serializer = MaskedTranscriptJsonSerializer()

    @Test
    fun `server payload contains only the masked contract`() {
        val transcript = MaskedTranscript(
            conversationId = "20260828_1430",
            utteranceId = 7,
            maskedText = "[PERSON] 씨 안녕하세요",
            hasMaskedData = true,
            maskedTypes = listOf("PERSON"),
        )

        val json = serializer.serialize(transcript)

        assertEquals(
            """{
  "schema_version": "1.0",
  "conversation_id": "20260828_1430",
  "utterance_id": 7,
  "masked_text": "[PERSON] 씨 안녕하세요",
  "has_masked_data": true,
  "masked_types": ["PERSON"]
}""",
            json,
        )
        assertFalse(json.contains("raw_text"))
    }
}
