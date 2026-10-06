package com.example.pic_ai_app.presentation.warning

enum class WarningStatusUi(val label: String) {
    NONE("경고 없음"),
    ACTIVE("경고 중"),
    PREVIOUS_WARNING("이전 경고"),
}

enum class WarningReasonUi(val label: String) {
    SINGLE_UTTERANCE("개별 발화"),
    CUMULATIVE("누적 위험"),
    BOTH("개별 발화·누적 위험"),
}

data class EvidenceUiItem(
    val utteranceId: Int,
    val text: String,
    val riskScore: Double,
    val riskTypes: List<String>,
)

data class CumulativeEvidenceUiEvent(
    val triggerUtteranceId: Int,
    val riskScore: Double,
    val utterances: List<EvidenceUiItem>,
)

data class WarningUiState(
    val status: WarningStatusUi,
    val reason: WarningReasonUi?,
    val message: String,
    val recent: EvidenceUiItem?,
    val highest: EvidenceUiItem?,
    val cumulativeEvents: List<CumulativeEvidenceUiEvent>,
)
