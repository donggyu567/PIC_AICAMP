package com.example.pic_ai_app.presentation.report

import androidx.activity.compose.BackHandler
import androidx.compose.runtime.*
import com.example.pic_ai_app.data.history.AnalysisRecord
import com.example.pic_ai_app.data.report.HarmReportSuggestion
import com.example.pic_ai_app.data.report.ReportCall
import com.example.pic_ai_app.data.report.ReportGuide
import com.example.pic_ai_app.data.report.ReportStep as WorkflowStep
import com.example.pic_ai_app.data.report.ReportWorkflow
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import java.io.IOException

internal enum class HarmPrefill { Idle, Loading, Ready, Failed }

internal class ReportFlowState {
    var workflow by mutableStateOf(ReportWorkflow())
        private set
    var tipFields by mutableStateOf(ReportTipFields())
        private set
    var prefill by mutableStateOf(HarmPrefill.Idle)
        private set

    fun select(record: AnalysisRecord) {
        val current = workflow.selectCall(ReportCall.from(record))
        if (current.call?.id != workflow.call?.id) {
            tipFields = ReportTipFields(current.tip.category)
            prefill = HarmPrefill.Idle
        }
        workflow = current
    }

    fun update(next: ReportWorkflow) {
        workflow = next
    }

    suspend fun prefillHarm(callId: String, generate: suspend (String) -> HarmReportSuggestion) {
        if (prefill == HarmPrefill.Ready) return
        prefill = HarmPrefill.Loading
        try {
            val suggestion = generate(callId)
            if (workflow.call?.id == callId) {
                workflow = workflow.applyHarmSuggestion(callId, suggestion)
                prefill = HarmPrefill.Ready
            }
        } catch (_: IOException) {
            if (workflow.call?.id == callId) prefill = HarmPrefill.Failed
        } finally {
            if (workflow.call?.id == callId && prefill == HarmPrefill.Loading) prefill = HarmPrefill.Idle
        }
    }

    fun clear() {
        workflow = ReportWorkflow()
        tipFields = ReportTipFields()
        prefill = HarmPrefill.Idle
    }
}

@Composable
internal fun ReportFlow(
    state: ReportFlowState, records: List<AnalysisRecord>, storageError: Boolean,
    summarizingRecords: Set<String>, onRequestSummary: (String) -> Unit,
    generateHarm: suspend (String) -> HarmReportSuggestion,
    onClose: () -> Unit, onTabSelected: (PicTab) -> Unit,
) {
    val ids = remember(records) { records.map { it.id }.toSet() }
    val workflow = state.workflow.retainSelection(ids)
    val record = records.find { it.id == workflow.call?.id }
    val savedSummary = record?.result?.risk?.summary
    LaunchedEffect(record?.id, savedSummary) {
        if (record != null && !savedSummary.isNullOrBlank()) {
            state.update(state.workflow.applySummary(record.id, savedSummary))
        }
    }
    val summaryRecordId = record?.takeIf { it.result.risk?.endedAt != null }?.id
    val preparingHarm = workflow.step == WorkflowStep.PrepareMaterial &&
        workflow.guide != ReportGuide.SuspiciousCall
    var prefillAttempt by remember(summaryRecordId) { mutableIntStateOf(0) }
    LaunchedEffect(workflow.step, workflow.guide, summaryRecordId, prefillAttempt) {
        if (workflow.step == WorkflowStep.PrepareMaterial && summaryRecordId != null) {
            if (preparingHarm) state.prefillHarm(summaryRecordId, generateHarm)
            else if (savedSummary.isNullOrBlank()) onRequestSummary(summaryRecordId)
        }
    }
    val summaryNotice: @Composable () -> Unit = {
        if (savedSummary.isNullOrBlank()) {
            ReportSummaryNotice(
                loading = summaryRecordId != null && summaryRecordId in summarizingRecords,
                onRetry = summaryRecordId?.let { id -> { onRequestSummary(id) } },
            )
        }
    }
    LaunchedEffect(ids) {
        if (state.workflow.retainSelection(ids) != state.workflow) state.clear()
    }
    BackHandler {
        if (workflow.step == WorkflowStep.SelectCall) {
            state.clear()
            onClose()
        } else state.update(workflow.back())
    }
    val onNext = { state.update(state.workflow.next()) }
    val onTab: (PicTab) -> Unit = {
        if (it != PicTab.Report) {
            state.clear()
            onTabSelected(it)
        }
    }
    when (workflow.step) {
        WorkflowStep.SelectCall -> ReportCallSelectionScreen(
            records, workflow.call?.id, state::select, onNext, onTab, storageError,
        )
        WorkflowStep.ConfirmSituation -> ReportSituationScreen(
            workflow, state::update, onNext, onTab,
        )
        WorkflowStep.PrepareMaterial -> if (workflow.guide == ReportGuide.SuspiciousCall) {
            ReportTipPreparationScreen(workflow, state.tipFields, state::update, onNext, onTab, summaryNotice)
        } else {
            ReportDamagePreparationScreen(
                workflow = workflow, onChange = state::update, onTabSelected = onTab,
                prefill = state.prefill, onRetry = summaryRecordId?.let { { prefillAttempt++ } },
                onCopied = { state.update(state.workflow.completeHarmCopy()) },
            )
        }
        WorkflowStep.Guide -> if (workflow.guide == ReportGuide.SuspiciousCall) {
            ReportTipGuidanceScreen(workflow.tip.callerNumber, workflow.tip.receivedAt,
                state.tipFields.categoryLabel(), onTab)
        } else {
            ReportDamageGuidanceScreen(workflow.harm, onTab)
        }
    }
}
