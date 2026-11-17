package com.example.pic_ai_app.data.report

import com.example.pic_ai_app.data.history.AnalysisRecord
import com.example.pic_ai_app.data.stt.LiveRiskLevel
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReportWorkflowTest {
    @Test
    fun suspiciousCallCopyUsesEditedBodyAndMaskedReferences() {
        val confirm = ReportWorkflow().selectCall(call()).next()
        assertEquals(LiveRiskLevel.Danger, confirm.call?.score?.level)
        val prepare = confirm.selectSituation(ReportSituation.SuspiciousCallOnly).next()
        assertEquals("", prepare.tip.receivedAt)
        assertEquals("", prepare.tip.callerNumber)
        assertEquals(TipCategory.Impersonation, prepare.tip.category)
        assertEquals("상대가 기관 소속을 주장하며 송금을 요청함.", prepare.tip.body)
        assertEquals(
            "상대가 기관 소속을 주장하며 송금을 요청함.\n\n아래는 개인정보가 마스킹된 통화 텍스트입니다.\n“지정 계좌로 돈을 보내세요.”\n“[PERSON]에게 연락하세요.”",
            prepare.tipCopyText()
        )
        val edited = prepare.editTip(
            prepare.tip.copy(callerNumber = "0212345678", receivedAt = "11월 16일 14:30", body = "확인한 제보 본문")
        ).selectReferences(setOf(2, 99))
        assertEquals(
            "확인한 제보 본문\n\n아래는 개인정보가 마스킹된 통화 텍스트입니다.\n“[PERSON]에게 연락하세요.”",
            edited.tipCopyText()
        )
        val guide = edited.next()
        assertEquals(ReportGuide.SuspiciousCall, guide.guide)
        assertEquals(edited.tip, guide.back().tip)
    }

    @Test
    fun moneyAnswerRoutesImmediatelyAndDoesNotAssumeUnknownLoss() {
        val confirm = ReportWorkflow().selectCall(call()).next()
            .selectSituation(ReportSituation.MoneyOrInformation)
        assertFalse(confirm.canAdvance)
        assertEquals(confirm, confirm.next())
        val yes = confirm.answerMoneyLoss(MoneyLoss.Yes)
        assertEquals(ReportGuide.FinancialLoss, yes.guide)
        assertTrue(yes.showPaymentStopGuidance)
        val no = confirm.answerMoneyLoss(MoneyLoss.No)
        assertEquals(ReportGuide.InformationExposure, no.guide)
        assertFalse(no.showPaymentStopGuidance)
        val unsure = confirm.answerMoneyLoss(MoneyLoss.Unsure)
        assertEquals(ReportGuide.VerifyMoneyLoss, unsure.guide)
        assertTrue(unsure.showPaymentStopGuidance)
    }

    @Test
    fun copyingHarmReportOpensGuideAndUsesTheFourSectionsInOrder() {
        val prepare = ReportWorkflow().selectCall(call()).next()
            .selectSituation(ReportSituation.MoneyOrInformation).answerMoneyLoss(MoneyLoss.Yes).next()
        val draft = prepare.harm.copy(
            victimName = "피해자 직접 입력",
            claimedIdentity = "금융기관 직원이라고 주장",
            firstContact = "전화를 받았습니다.",
            deception = "송금을 요구받았습니다.",
            damage = "직접 확인한 이체 내역",
            discoveryAndResponse = "금융회사에 연락했습니다.",
        )
        val edited = prepare.editHarm(draft)
        assertEquals(ReportStep.PrepareMaterial, edited.next().step)
        assertFalse(edited.canAdvance)
        assertEquals(prepare, prepare.completeHarmCopy())
        val guided = edited.completeHarmCopy()
        assertEquals(ReportStep.Guide, guided.step)
        assertEquals(draft, guided.back().harm)
        val text = guided.harm.toReportText()
        val headings = listOf("1. 피해자 인적사항", "2. 피의자(사기범) 정보", "3. 시간대별 피해 발생 경위", "4. 첨부 증빙자료 목록")
        val positions = headings.map { text.indexOf(it) }
        assertTrue(positions.all { it >= 0 } && positions.zipWithNext().all { it.first < it.second })
        assertTrue(text.contains("성명: 피해자 직접 입력"))
        assertTrue(text.contains("피해 발생 (일시)\n직접 확인한 이체 내역"))
        assertTrue(text.contains(guided.harm.timelineText()))
        assertFalse(guided.harm.timelineText().contains("피해자 직접 입력"))
    }

    @Test
    fun replacingOrDeletingTheRecordClearsItsReportData() {
        val prepare = ReportWorkflow().selectCall(call()).next()
            .selectSituation(ReportSituation.SuspiciousCallOnly).next()
        val edited = prepare.editTip(prepare.tip.copy(body = "이전 기록 초안"))
        val other = ReportCall.from(AnalysisRecord("other", 0, SttState()))
        val changed = edited.back().back().selectCall(other)
        assertEquals(TipDraft(), changed.tip)
        assertEquals(HarmDraft(), changed.harm)
        assertNull(changed.situation)
        assertTrue(changed.selectedReferences.isEmpty())
        assertEquals(ReportWorkflow(), edited.retainSelection(setOf(other.id)))
    }

    @Test
    fun reportUsesLateSummaryBeforeTheMaskedTranscript() {
        val confirm = ReportWorkflow().selectCall(callWithoutSummary()).next()
        val tip = confirm.selectSituation(ReportSituation.SuspiciousCallOnly).next()
        assertEquals("", tip.tip.body)
        assertEquals("", tip.tipCopyText())

        val summary = "금융기관을 사칭한 연락을 받았으며 송금을 요구받았습니다."
        val summarized = tip.applySummary("no-summary", summary)
        assertEquals(summary, summarized.tip.body)
        assertEquals(
            summary + "\n\n아래는 개인정보가 마스킹된 통화 텍스트입니다.\n“[PERSON]에게 연락하세요.”\n“지정 계좌로 돈을 보내세요.”",
            summarized.tipCopyText()
        )
    }

    @Test
    fun lateSummaryPreservesManualEditsAndCannotUpdateAnotherRecord() {
        val prepare = ReportWorkflow().selectCall(callWithoutSummary()).next()
            .selectSituation(ReportSituation.SuspiciousCallOnly).next()
        val manual = prepare.editTip(prepare.tip.copy(body = "제보자가 확인한 내용"))
        assertEquals(manual, manual.applySummary("different-call", "다른 통화 요약"))
        assertEquals(manual.tip, manual.applySummary("no-summary", "뒤늦게 도착한 통화 요약").tip)
        val cleared = manual.editTip(manual.tip.copy(body = ""))
        assertEquals("", cleared.applySummary("no-summary", "뒤늦게 도착한 통화 요약").tip.body)
    }

    private fun callWithoutSummary() = ReportCall.from(
        AnalysisRecord(
            id = "no-summary",
            endedAtMillis = 0,
            result = SttState(
                maskedTexts = listOf("  [PERSON]에게 연락하세요. ", " ", "지정 계좌로 돈을 보내세요."),
            ),
        )
    )

    @Test
    fun harmSuggestionFillsUntouchedFieldsOnlyAndLeavesActualLossBlank() {
        val prepare = ReportWorkflow().selectCall(call()).next()
            .selectSituation(ReportSituation.MoneyOrInformation).answerMoneyLoss(MoneyLoss.Unsure).next()
        val edited = prepare.editHarm(prepare.harm.copy(claimedIdentity = "", damage = "출금 여부 확인 중"))
        val suggestion = HarmReportSuggestion("검찰 수사관이라고 주장", "전화를 받았습니다.", "송금을 요구받았습니다.")
        val applied = edited.applyHarmSuggestion("call", suggestion)
        assertEquals("", applied.harm.claimedIdentity)
        assertEquals(suggestion.firstContact, applied.harm.firstContact)
        assertEquals(suggestion.deception, applied.harm.deception)
        assertEquals("", applied.harm.victimName)
        assertEquals("", applied.harm.accountNumber)
        assertEquals("출금 여부 확인 중", applied.harm.damage)
        assertEquals("", applied.harm.discoveryAndResponse)
        assertEquals(edited, edited.applyHarmSuggestion("different-call", suggestion))
        assertEquals("", prepare.applyHarmSuggestion("call", suggestion).harm.damage)
    }

    @Test
    fun existingRecordWithoutRiskOrTranscriptCanBeReportedManually() {
        val record = AnalysisRecord("legacy", 0, SttState())
        val confirm = ReportWorkflow().selectCall(ReportCall.from(record)).next()
        assertEquals("", confirm.selectSituation(ReportSituation.SuspiciousCallOnly).next().tip.body)
        val prepare = confirm.selectSituation(ReportSituation.MoneyOrInformation).answerMoneyLoss(MoneyLoss.No).next()
        assertFalse(prepare.harm.canCopyReport)
        val knownContact = prepare.harm.copy(suspectPhone = "확인한 연락처")
        assertTrue(knownContact.canCopyReport)
        assertFalse(knownContact.hasTimeline)
        val edited = prepare.editHarm(prepare.harm.copy(damage = "인증번호를 알려줌"))
        assertTrue(edited.harm.canCopyReport)
        assertTrue(edited.harm.toReportText().contains("인증번호를 알려줌"))
        assertEquals(ReportStep.Guide, edited.completeHarmCopy().step)
    }

    private fun call() = ReportCall.from(
        AnalysisRecord(
            id = "call",
            endedAtMillis = 1_737_000_000_000,
            result = SttState(
                maskedTexts = listOf("지정 계좌로 돈을 보내세요.", "[PERSON]에게 연락하세요."),
                risk = RiskResult(
                    currentScore = 40.0, cumulativeScore = 80.0, warningMessage = null,
                    contextStatus = "completed", contextReason = null, correctionStatus = null,
                    title = "기관 사칭 의심 통화", summary = "상대가 기관 소속을 주장하며 송금을 요청함.",
                    riskTypes = listOf("institution_impersonation", "money_transfer"),
                    evidenceIds = listOf(1, 1, 99),
                ),
            ),
        )
    )
}
