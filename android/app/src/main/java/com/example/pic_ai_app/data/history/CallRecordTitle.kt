package com.example.pic_ai_app.data.history

import com.example.pic_ai_app.data.stt.LiveRiskAlert
import com.example.pic_ai_app.data.stt.LiveRiskLevel
import com.example.pic_ai_app.data.stt.LiveRiskScore
import com.example.pic_ai_app.data.stt.SttState

internal object CallRecordTitle {
    private val genericTitles = setOf(
        "최종 분석 결과", "최종 분석", "최종 결과", "분석 결과", "통화 분석 결과", "통화 분석",
        "보이스피싱 분석 결과", "통화 요약", "통화 기록",
    )
    private val whitespace = Regex("\\s+")
    private val financialInfo = Regex("""계좌\s*번호|카드\s*번호|금융\s*정보|\[(?:ACCOUNT_NUMBER|CARD_NUMBER)]""")

    fun riskTypes(state: SttState): Set<String> = buildSet {
        addAll(state.recordedRiskTypes)
        addAll(state.risk?.riskTypes.orEmpty())
        addAll(state.risk?.detectedTypes.orEmpty())
        state.liveCards.cards.filterIsInstance<LiveRiskAlert>().forEach { alert ->
            addAll(alert.signal?.types.orEmpty())
            addAll(alert.actionTypes)
        }
    }

    fun from(state: SttState): String {
        val risk = state.risk
        val serverTitle = risk?.title?.trim()
        if (!serverTitle.isNullOrEmpty() && serverTitle.trimEnd('.', '!', '?', '…').replace(whitespace, " ") !in genericTitles) {
            return serverTitle
        }

        val types = riskTypes(state)
        val evidence = (risk?.evidenceIds.orEmpty() + risk?.warningEvidenceIds.orEmpty())
            .mapNotNull { state.maskedTexts.getOrNull(it - 1) }
        val financialRequest = ("personal_information" in types || "information_probing" in types) &&
            evidence.any(financialInfo::containsMatchIn)
        val labels = listOfNotNull(
            "기관 사칭".takeIf { "institution_impersonation" in types },
            "금융정보 탈취".takeIf { financialRequest },
            "송금 요구".takeIf { "money_transfer" in types },
            "대출 사기".takeIf { "loan_fraud" in types },
            "개인정보 요구".takeIf { !financialRequest && "personal_information" in types },
            "앱 설치 유도".takeIf { "app_installation" in types },
            "협박·압박".takeIf { "threat_pressure" in types },
            "비밀 유지 요구".takeIf { "secrecy" in types },
            "정보 탐색".takeIf { !financialRequest && "information_probing" in types },
        )
        if (labels.isNotEmpty()) return labels.take(2).joinToString(" 및 ") + " 의심 통화"

        val level = LiveRiskScore.from(risk?.cumulativeScore)?.level
        return when {
            risk?.analysisIncomplete == true || state.error != null -> "분석이 완료되지 않은 통화"
            risk?.assessment == "suspicious" || (level != null && level != LiveRiskLevel.Normal) -> "위험 신호가 감지된 통화"
            risk?.assessment == "no_clear_risk" || level == LiveRiskLevel.Normal -> "뚜렷한 위험 신호가 없는 통화"
            state.maskedTexts.none(String::isNotBlank) -> "인식된 발화가 없는 통화"
            else -> "통화 내용 확인이 필요한 기록"
        }
    }
}
