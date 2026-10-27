package com.example.pic_ai_app.domain.repository

import com.example.pic_ai_app.domain.model.UtteranceTranscript

interface TranscriptRepository {
    suspend fun createConversation(baseConversationId: String): String

    suspend fun save(transcript: UtteranceTranscript): StoredTranscript
}

data class StoredTranscript(
    val conversationId: String,
    val utteranceId: Int,
    val fileName: String,
)
