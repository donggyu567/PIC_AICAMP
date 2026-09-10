package com.example.pic_ai_app.domain.repository

import com.example.pic_ai_app.domain.model.MaskedTranscript

interface MaskedTranscriptRepository {
    suspend fun save(transcript: MaskedTranscript): StoredMaskedTranscript
}

data class StoredMaskedTranscript(
    val conversationId: String,
    val utteranceId: Int,
    val fileName: String,
)
