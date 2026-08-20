package com.example.pic_ai_app.data.serialization

import com.example.pic_ai_app.domain.model.UtteranceTranscript

class TranscriptJsonSerializer {
    fun serialize(transcript: UtteranceTranscript): String = buildString {
        append("{\n")
        append("  \"conversation_id\": ")
        appendJsonString(transcript.conversationId)
        append(",\n")
        append("  \"utterance_id\": ")
        append(transcript.utteranceId)
        append(",\n")
        append("  \"raw_text\": ")
        appendJsonString(transcript.rawText)
        append(",\n")
        append("  \"masked_text\": ")
        appendJsonString(transcript.maskedText)
        append(",\n")
        append("  \"has_masked_data\": ")
        append(transcript.hasMaskedData)
        append(",\n")
        append("  \"masked_types\": [")
        transcript.maskedTypes.forEachIndexed { index, type ->
            if (index > 0) append(", ")
            appendJsonString(type)
        }
        append("]\n")
        append('}')
    }

    private fun StringBuilder.appendJsonString(value: String) {
        append('"')
        value.forEach { character ->
            when (character) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                '\b' -> append("\\b")
                '\u000C' -> append("\\f")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> {
                    if (character.code < 0x20) {
                        append("\\u")
                        append(character.code.toString(16).padStart(4, '0'))
                    } else {
                        append(character)
                    }
                }
            }
        }
        append('"')
    }
}
