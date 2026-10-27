package com.example.pic_ai_app.data.serialization

import com.example.pic_ai_app.domain.model.UtteranceTranscript
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TranscriptJsonSerializerTest {
    private val serializer = TranscriptJsonSerializer()

    @Test
    fun `unmasked transcript is serialized with the required schema`() {
        val transcript = UtteranceTranscript.unmasked(
            conversationId = "20260820_2246",
            utteranceId = 1,
            finalTranscript = "김동규 씨 안녕하세요",
        )

        assertEquals(
            """{
  "conversation_id": "20260820_2246",
  "utterance_id": 1,
  "raw_text": "김동규 씨 안녕하세요",
  "masked_text": "김동규 씨 안녕하세요",
  "has_masked_data": false,
  "masked_types": []
}""",
            serializer.serialize(transcript),
        )
    }

    @Test
    fun `serializer escapes JSON syntax without normalizing transcript text`() {
        val raw = " 앞 공백\n\"인용\"\\경로\t뒤 공백 "
        val transcript = UtteranceTranscript.unmasked(
            conversationId = "20260820_2246_02",
            utteranceId = 12,
            finalTranscript = raw,
        )

        val json = serializer.serialize(transcript)
        val encodedValue = " 앞 공백\\n\\\"인용\\\"\\\\경로\\t뒤 공백 "

        assertEquals(raw, transcript.rawText)
        assertEquals(raw, transcript.maskedText)
        assertTrue(json.contains("\"raw_text\": \"$encodedValue\""))
        assertTrue(json.contains("\"masked_text\": \"$encodedValue\""))
    }
}
