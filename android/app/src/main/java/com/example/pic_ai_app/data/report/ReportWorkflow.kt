package com.example.pic_ai_app.data.report

import com.example.pic_ai_app.data.history.AnalysisRecord
import com.example.pic_ai_app.data.history.CallRecordTitle
import com.example.pic_ai_app.data.stt.LiveRiskScore

enum class ReportStep { SelectCall, ConfirmSituation, PrepareMaterial, Guide }
enum class ReportSituation { SuspiciousCallOnly, MoneyOrInformation }
enum class MoneyLoss { Yes, No, Unsure }

enum class TipCategory(val label: String) {
    Impersonation("기관사칭"),
    CallerIdManipulation("변작의심"),
    Loan("대출"),
    Advertising("광고"),
}

enum class ReportGuide { SuspiciousCall, FinancialLoss, InformationExposure, VerifyMoneyLoss }

enum class ReportDestination(val uri: String) {
    PhishingSos("https://www.counterscam112.go.kr/report/reportGuide.do?type=vop"),
    Ecrm("https://ecrm.police.go.kr/minwon/main"),
    Emergency112("tel:112"),
}

data class ReportReference(val utteranceId: Int, val maskedText: String)

data class ReportCall private constructor(
    val id: String,
    val title: String,
    val endedAtMillis: Long,
    val score: LiveRiskScore?,
    val references: List<ReportReference>,
    internal val suggestedCategory: TipCategory?,
    internal val summary: String,
) {
    companion object {
        fun from(record: AnalysisRecord): ReportCall {
            val risk = record.result.risk
            val references = record.result.maskedTexts.mapIndexedNotNull { index, text ->
                text.trim().takeIf(String::isNotEmpty)?.let { ReportReference(index + 1, it) }
            }
            val types = risk?.riskTypes.orEmpty()
            val suggestions = listOfNotNull(
                TipCategory.Impersonation.takeIf { "institution_impersonation" in types },
                TipCategory.Loan.takeIf { "loan_fraud" in types },
            )
            return ReportCall(
                id = record.id,
                title = CallRecordTitle.from(record.result),
                endedAtMillis = record.endedAtMillis,
                score = LiveRiskScore.from(risk?.cumulativeScore),
                references = references,
                suggestedCategory = suggestions.singleOrNull(),
                summary = risk?.summary?.trim().orEmpty(),
            )
        }
    }
}

data class TipDraft(
    val callerNumber: String = "",
    val receivedAt: String = "",
    val category: TipCategory? = null,
    val body: String = "",
)

data class ReportWorkflow private constructor(
    val step: ReportStep,
    val call: ReportCall? = null,
    val situation: ReportSituation? = null,
    val moneyLoss: MoneyLoss? = null,
    val tip: TipDraft = TipDraft(),
    val harm: HarmDraft = HarmDraft(),
    val referenceIds: Set<Int> = emptySet(),
    private val tipBodyEdited: Boolean = false,
) {
    constructor() : this(ReportStep.SelectCall)

    val showPaymentStopGuidance: Boolean
        get() = situation == ReportSituation.MoneyOrInformation &&
            (moneyLoss == MoneyLoss.Yes || moneyLoss == MoneyLoss.Unsure)

    val guide: ReportGuide?
        get() = when (situation) {
            ReportSituation.SuspiciousCallOnly -> ReportGuide.SuspiciousCall
            ReportSituation.MoneyOrInformation -> when (moneyLoss) {
                MoneyLoss.Yes -> ReportGuide.FinancialLoss
                MoneyLoss.No -> ReportGuide.InformationExposure
                MoneyLoss.Unsure -> ReportGuide.VerifyMoneyLoss
                null -> null
            }
            null -> null
        }

    val canAdvance: Boolean
        get() = when (step) {
            ReportStep.SelectCall -> call != null
            ReportStep.ConfirmSituation -> guide != null
            ReportStep.PrepareMaterial -> situation == ReportSituation.SuspiciousCallOnly
            ReportStep.Guide -> false
        }

    val selectedReferences: List<ReportReference>
        get() = call?.references.orEmpty().filter { it.utteranceId in referenceIds }

    fun selectCall(selected: ReportCall): ReportWorkflow {
        if (step != ReportStep.SelectCall || call?.id == selected.id) return this
        return ReportWorkflow(
            step = step,
            call = selected,
            tip = TipDraft(category = selected.suggestedCategory, body = selected.summary),
            referenceIds = selected.references.map { it.utteranceId }.toSet(),
        )
    }

    fun applySummary(callId: String, summary: String): ReportWorkflow {
        val selected = call ?: return this
        val body = summary.trim()
        if (selected.id != callId || selected.summary.isNotEmpty() || body.isEmpty()) return this
        return copy(
            call = selected.copy(summary = body),
            tip = if (tipBodyEdited) tip else tip.copy(body = body),
        )
    }

    fun selectSituation(selected: ReportSituation): ReportWorkflow =
        if (step != ReportStep.ConfirmSituation || selected == situation) this
        else copy(situation = selected, moneyLoss = null)

    fun answerMoneyLoss(answer: MoneyLoss): ReportWorkflow =
        if (step == ReportStep.ConfirmSituation && situation == ReportSituation.MoneyOrInformation) {
            copy(moneyLoss = answer)
        } else this

    fun editTip(draft: TipDraft): ReportWorkflow =
        if (step == ReportStep.PrepareMaterial && situation == ReportSituation.SuspiciousCallOnly) {
            copy(tip = draft, tipBodyEdited = tipBodyEdited || tip.body != draft.body)
        } else this

    fun editHarm(draft: HarmDraft): ReportWorkflow =
        if (step == ReportStep.PrepareMaterial && situation == ReportSituation.MoneyOrInformation) {
            copy(harm = draft)
        } else this

    fun applyHarmSuggestion(callId: String, suggestion: HarmReportSuggestion): ReportWorkflow =
        if (call?.id == callId && situation == ReportSituation.MoneyOrInformation && step != ReportStep.Guide) {
            copy(harm = harm.withSuggestion(suggestion))
        } else this

    fun completeHarmCopy(): ReportWorkflow =
        if (step == ReportStep.PrepareMaterial && situation == ReportSituation.MoneyOrInformation && harm.canCopyReport) {
            copy(step = ReportStep.Guide)
        } else this

    fun selectReferences(ids: Set<Int>): ReportWorkflow =
        if (step == ReportStep.PrepareMaterial) {
            copy(referenceIds = call?.references.orEmpty().filter { it.utteranceId in ids }
                .map { it.utteranceId }.toSet())
        } else this

    fun next(): ReportWorkflow =
        if (canAdvance) copy(step = ReportStep.entries[step.ordinal + 1]) else this

    fun back(): ReportWorkflow =
        if (step == ReportStep.SelectCall) this else copy(step = ReportStep.entries[step.ordinal - 1])

    fun retainSelection(availableCallIds: Set<String>): ReportWorkflow =
        if (call != null && call.id !in availableCallIds) ReportWorkflow() else this

    fun tipCopyText(): String {
        val body = tip.body.trim()
        if (situation != ReportSituation.SuspiciousCallOnly || body.isEmpty()) return ""
        val transcript = selectedReferences.joinToString("\n") { reference -> "“${reference.maskedText}”" }
        return if (transcript.isEmpty()) body
        else "$body\n\n아래는 개인정보가 마스킹된 통화 텍스트입니다.\n$transcript"
    }
}
