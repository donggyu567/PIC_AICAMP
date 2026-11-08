package com.example.pic_ai_app.domain.model

const val MASKED_TRANSCRIPT_SCHEMA_VERSION = "1.0"

/** Data that is safe to persist after NER and send to the API server. */
data class MaskedTranscript(
    val schemaVersion: String = MASKED_TRANSCRIPT_SCHEMA_VERSION,
    val conversationId: String,
    val utteranceId: Int,
    val maskedText: String,
    val hasMaskedData: Boolean,
    val maskedTypes: List<String>,
) {
    init {
        require(schemaVersion == MASKED_TRANSCRIPT_SCHEMA_VERSION) {
            "Unsupported masked transcript schema version"
        }
        require(conversationId.isNotBlank()) { "Conversation ID must not be blank" }
        require(utteranceId > 0) { "Utterance ID must be positive" }
        require(maskedText.isNotBlank()) { "Masked text must not be blank" }
        require(maskedTypes.all { it.isNotBlank() }) {
            "Masked types must not contain blank values"
        }
        require(maskedTypes.distinct().size == maskedTypes.size) {
            "Masked types must not contain duplicates"
        }
        require(hasMaskedData == maskedTypes.isNotEmpty()) {
            "Masking flag must match masked types"
        }
    }
}
