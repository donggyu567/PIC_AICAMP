package com.example.pic_ai_app.presentation.stt

data class SttUiState(
    val status: SttStatus = SttStatus.IDLE,
    val conversationId: String? = null,
    val partialText: String = "",
    val lastFinalText: String = "",
    val savedUtteranceCount: Int = 0,
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
