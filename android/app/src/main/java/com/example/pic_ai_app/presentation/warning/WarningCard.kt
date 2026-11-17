package com.example.pic_ai_app.presentation.warning

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.util.Locale

@Composable
fun WarningCard(warning: WarningUiState?) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (warning?.status == WarningStatusUi.ACTIVE) {
                MaterialTheme.colorScheme.errorContainer
            } else {
                MaterialTheme.colorScheme.surfaceVariant
            },
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("경고·근거", style = MaterialTheme.typography.titleMedium)

            if (warning == null) {
                Text("아직 서버 분석 결과가 없습니다.")
            } else {
                Text(warning.status.label, fontWeight = FontWeight.Bold)
                warning.reason?.let { Text("사유: ${it.label}") }
                Text(warning.message)

                warning.recent?.let { EvidenceLine("최근 근거", it) }
                warning.highest?.let { EvidenceLine("최고 근거", it) }

                warning.cumulativeEvents.forEachIndexed { index, event ->
                    Text(
                        "누적 경고 ${index + 1} · " +
                            "${event.triggerUtteranceId}번 발화 · " +
                            "${formatScore(event.riskScore)}점",
                    )
                    event.utterances.forEach {
                        EvidenceLine("기여 발화", it)
                    }
                }
            }
        }
    }
}

@Composable
private fun EvidenceLine(label: String, evidence: EvidenceUiItem) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, fontWeight = FontWeight.SemiBold)
        Text("${evidence.utteranceId}번 발화 · ${formatScore(evidence.riskScore)}점")
        Text(evidence.text)

        if (evidence.riskTypes.isNotEmpty()) {
            Text(
                "유형: " + evidence.riskTypes.joinToString(", ") {
                    riskTypeLabel(it)
                },
            )
        }
    }
}

private fun formatScore(score: Double): String =
    String.format(Locale.KOREA, "%.1f", score)

private fun riskTypeLabel(code: String): String = when (code) {
    "institution_impersonation" -> "기관 사칭"
    "money_transfer" -> "송금 요구"
    "personal_information" -> "개인정보 요구"
    "app_installation" -> "앱 설치 유도"
    "secrecy" -> "비밀 유지 요구"
    "threat_pressure" -> "협박·압박"
    "loan_fraud" -> "대출 사기"
    "information_probing" -> "정보 탐색"
    else -> code
}
