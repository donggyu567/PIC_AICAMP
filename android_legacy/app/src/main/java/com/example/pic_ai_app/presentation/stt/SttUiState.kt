package com.example.pic_ai_app.presentation.stt

import com.example.pic_ai_app.domain.model.MaskedTranscript
data class SttUiState(
    val status: SttStatus = SttStatus.IDLE,
    val conversationId: String? = null,
    val partialText: String = "",
    val lastFinalText: String = "",
    val lastMaskingSourceText: String = "",
    val lastMaskedTranscript: MaskedTranscript? = null,
    val savedUtteranceCount: Int = 0,
    val maskedUtteranceCount: Int = 0,
    val transmittedUtteranceCount: Int = 0,
    val errorMessage: String? = null,
) {
    val sessionActive: Boolean
        get() = status == SttStatus.INITIALIZING ||
            status == SttStatus.LISTENING ||
            status == SttStatus.STOPPING
}

enum class SttStatus {
    IDLE,
    INITIALIZING,
    LISTENING,
    STOPPING,
    ERROR,
}
