package com.example.pic_ai_app.data.history

import com.example.pic_ai_app.data.stt.LiveAnalysisCards
import com.example.pic_ai_app.data.stt.LiveRiskSignal
import com.example.pic_ai_app.data.stt.LiveRiskSource
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CallRecordTitleTest {
    @Test
    fun genericTitleUsesFinancialRequestEvidence() {
        val state = SttState(
            risk = risk().copy(title = "최종 분석 결과.", riskTypes = listOf("institution_impersonation", "personal_information"),
                evidenceIds = listOf(2, 99)),
            maskedTexts = listOf("검찰 수사관이라고 밝혔습니다.", "카드번호 [CARD_NUMBER]를 알려주세요."),
        )
        assertEquals("기관 사칭 및 금융정보 탈취 의심 통화", CallRecordTitle.from(state))
        assertEquals("기관 사칭 및 개인정보 요구 의심 통화",
            CallRecordTitle.from(state.copy(risk = state.risk?.copy(evidenceIds = listOf(1)))))
    }

    @Test
    fun generatedSpecificTitleTakesPrecedence() {
        val state = SttState(risk = risk().copy(title = "예금 보호를 이유로 송금을 요구한 통화",
            riskTypes = listOf("money_transfer")))
        assertEquals("예금 보호를 이유로 송금을 요구한 통화", CallRecordTitle.from(state))
    }

    @Test
    fun titleRetainsEarlierRiskSignalsAfterSavingAndLoading() {
        val state = SttState(
            risk = risk().copy(riskTypes = listOf("money_transfer")),
            liveCards = LiveAnalysisCards().record(1, 15.0,
                LiveRiskSignal(LiveRiskSource.Ai, setOf("institution_impersonation"), listOf(1)),
                contextAttention = false, now = 100),
            conversationId = "title-test",
        )
        val record = AnalysisRecord.completed(state)
        assertTrue(record.result.liveCards.cards.isEmpty())
        val reloaded = decodeAnalysisRecord(record.encode())
        assertEquals("기관 사칭 및 송금 요구 의심 통화", CallRecordTitle.from(reloaded.result))
    }

    @Test
    fun oldRecordWithoutRecordedRiskTypesStillRetainsItsTitle() {
        val old = """
            {"id":"legacy","endedAtMillis":0,"count":1,"maskedTexts":["테스트"],"risk":{
                "score":52,"riskTypes":["money_transfer"],"evidenceIds":[1]
            }}
        """.trimIndent()
        assertEquals("송금 요구 의심 통화", CallRecordTitle.from(decodeAnalysisRecord(old).result))
    }

    @Test
    fun absenceOfEvidenceDoesNotInventAThreatOrCallItSafeWhenIncomplete() {
        val state = SttState(risk = risk().copy(cumulativeScore = 0.0), maskedTexts = listOf("약속 시간을 정했습니다."))
        assertEquals("뚜렷한 위험 신호가 없는 통화", CallRecordTitle.from(state))
        assertEquals("분석이 완료되지 않은 통화",
            CallRecordTitle.from(state.copy(risk = state.risk?.copy(analysisIncomplete = true))))
        assertEquals("인식된 발화가 없는 통화", CallRecordTitle.from(SttState()))
    }

    private fun risk() = RiskResult(null, 64.0, null, "ok", null, null)
}
