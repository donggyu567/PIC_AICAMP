package com.example.pic_ai_app.presentation.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.*
import com.example.pic_ai_app.presentation.preview.*

@Composable
fun FlowExplanation() {
    InfoCard(stringResource(R.string.analysis_flow_title)) {
        stringArrayResource(R.array.analysis_flow_steps).forEachIndexed { index, step ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BodyText((index + 1).toString())
                Text(step, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
            }
        }
    }
}

@Composable
fun WelcomeScreen(onContinue: () -> Unit, onData: () -> Unit, declined: Boolean, withdrawn: Boolean = false) {
    PicPage(title = stringResource(R.string.app_name)) {
        SectionHeading(stringResource(R.string.welcome_title))
        BodyText(stringResource(R.string.home_description))
        if (declined || withdrawn) InfoCard(stringResource(R.string.consent_needed)) { BodyText(stringResource(if (withdrawn) R.string.consent_withdrawn else R.string.consent_declined)) }
        FlowExplanation()
        DevelopmentNotice()
        PrimaryAction(stringResource(R.string.view_consent), onContinue)
        LinkAction(stringResource(R.string.data_guide_title), onData)
    }
}

@Composable
fun ConsentScreen(
    onAgree: () -> Unit, onDecline: () -> Unit, onBack: () -> Unit,
    saving: Boolean = false, failed: Boolean = false,
) {
    PicPage(title = stringResource(R.string.consent_title), onBack = onBack) {
        SectionHeading(stringResource(R.string.consent_heading))
        BodyText(stringResource(R.string.consent_intro))
        FlowExplanation()
        InfoCard(stringResource(R.string.data_principles)) { BodyText(stringResource(R.string.data_principles_body)) }
        if (saving) {
            CircularProgressIndicator(Modifier.size(24.dp))
            BodyText(stringResource(R.string.saving_consent))
        }
        if (failed) InfoCard(stringResource(R.string.consent_save_error_title), error = true) {
            BodyText(stringResource(R.string.consent_save_error_body))
        }
        PrimaryAction(stringResource(R.string.agree_continue), onAgree, enabled = !saving)
        SecondaryAction(stringResource(R.string.decline), onDecline, enabled = !saving)
    }
}

@Composable
fun PermissionScreen(
    onAllow: () -> Unit, onDeny: () -> Unit, onBack: () -> Unit, denied: Boolean,
    requesting: Boolean = false, onSettings: () -> Unit = {},
) {
    PicPage(title = stringResource(R.string.permission_title), onBack = onBack) {
        SectionHeading(stringResource(R.string.permission_title))
        BodyText(stringResource(R.string.permission_description))
        InfoCard(stringResource(R.string.permission_preview_title)) { BodyText(stringResource(R.string.permission_preview_body)) }
        if (denied) InfoCard(stringResource(R.string.permission_required), error = true) { BodyText(stringResource(R.string.permission_denied_body)) }
        if (requesting) {
            CircularProgressIndicator(Modifier.size(24.dp))
            BodyText(stringResource(R.string.permission_requesting))
        }
        PrimaryAction(stringResource(R.string.request_microphone_permission), onAllow, enabled = !requesting)
        if (denied) LinkAction(stringResource(R.string.open_app_settings), onSettings)
        SecondaryAction(stringResource(R.string.later), onDeny, enabled = !requesting)
    }
}

@Composable
fun AnalysisScreen(
    state: PreviewState, details: Boolean, onBack: () -> Unit,
    onStop: () -> Unit, onDetails: () -> Unit, onData: () -> Unit,
) {
    val finishing = state.phase == Phase.FINALIZING
    PicPage(
        title = stringResource(if (details) R.string.live_detail_title else R.string.analysis_title),
        onBack = onBack,
        footer = {
            BodyText(stringResource(if (finishing || state.error != null) R.string.microphone_off_preview else R.string.microphone_preview), muted = true)
            PrimaryAction(
                stringResource(if (finishing) R.string.finalizing_button else R.string.stop_analysis),
                onStop, enabled = !finishing, fill = true,
            )
            if (!finishing) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    LinkAction(stringResource(if (details) R.string.back_to_analysis else R.string.view_live_detail), onDetails)
                    LinkAction(stringResource(R.string.data_guide_short), onData)
                }
            }
        },
    ) {
        SectionHeading(stringResource(when {
            finishing -> R.string.finalizing_title
            details -> R.string.live_detail_title
            else -> R.string.analysis_in_progress
        }))
        RiskCard(state)
        if (finishing) {
            ProgressCard(state)
            BodyText(stringResource(R.string.finalizing_description))
        } else {
            state.error?.let { ProcessingError(it) }
            WarningList(state)
            if (details) EvidenceList(state)
            TranscriptList(state)
            if (!details) ProgressCard(state)
            if (state.samples.isNotEmpty()) {
                InfoCard(stringResource(R.string.response_advice)) { BodyText(stringResource(R.string.response_advice_body)) }
            }
        }
        DevelopmentNotice()
    }
}

@Composable
fun FinalScreen(state: PreviewState, onHome: () -> Unit, onNew: () -> Unit, onData: () -> Unit) {
    PicPage(
        title = stringResource(R.string.final_title), onBack = onHome,
        footer = {
            BodyText(stringResource(if (state.phase == Phase.INCOMPLETE) R.string.final_incomplete_status else R.string.final_complete_status), muted = true)
            PrimaryAction(stringResource(R.string.start_analysis), onNew, fill = true)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                LinkAction(stringResource(R.string.home), onHome)
                LinkAction(stringResource(R.string.data_guide_short), onData)
            }
        },
    ) {
        SectionHeading(stringResource(R.string.analysis_summary))
        if (state.phase == Phase.INCOMPLETE) {
            InfoCard(stringResource(R.string.incomplete_title), error = true) { BodyText(stringResource(R.string.incomplete_body)) }
        }
        if (state.error == PreviewError.PERMISSION) InfoCard(stringResource(R.string.permission_required), error = true) {
            BodyText(stringResource(R.string.permission_revoked))
        }
        RiskCard(state, final = true)
        WarningList(state, final = true)
        EvidenceList(state, final = true)
        if (state.samples.isNotEmpty()) {
            InfoCard(stringResource(R.string.response_advice)) { BodyText(stringResource(R.string.response_advice_body)) }
        }
        DevelopmentNotice()
    }
}

@Composable
fun DataScreen(state: PreviewState, onBack: () -> Unit, onWithdraw: () -> Unit, onConsent: () -> Unit, onDeletion: () -> Unit) {
    PicPage(title = stringResource(R.string.data_guide_title), onBack = onBack) {
        SectionHeading(stringResource(R.string.data_guide_title))
        InfoCard(stringResource(R.string.transfer_scope)) { BodyText(stringResource(R.string.transfer_scope_body)) }
        InfoCard(stringResource(R.string.data_retention)) { BodyText(stringResource(R.string.data_retention_body)) }
        InfoCard(stringResource(R.string.withdrawal_guide)) { BodyText(stringResource(R.string.withdrawal_guide_body)) }
        when {
            state.consented -> PrimaryAction(stringResource(R.string.withdraw_consent), onWithdraw)
            state.deletion in listOf(Deletion.DELETING, Deletion.PENDING) ->
                PrimaryAction(stringResource(R.string.view_deletion_status), onDeletion)
            else -> {
                BodyText(stringResource(R.string.no_consent_current), muted = true)
                PrimaryAction(stringResource(R.string.view_consent), onConsent)
            }
        }
    }
}

@Composable
fun WithdrawalScreen(
    state: PreviewState, onHome: () -> Unit, onConsent: () -> Unit, onRetry: () -> Unit, onData: () -> Unit,
    savingConsent: Boolean = false, consentFailed: Boolean = false, onRetryConsent: () -> Unit = {},
) {
    val title = when (state.deletion) {
        Deletion.DELETING -> R.string.deletion_processing
        Deletion.PENDING -> R.string.deletion_pending
        else -> R.string.withdrawal_complete
    }
    PicPage(title = stringResource(R.string.withdrawal_title), onBack = onHome) {
        if (savingConsent) {
            CircularProgressIndicator(Modifier.size(24.dp))
            BodyText(stringResource(R.string.saving_withdrawal))
        } else if (consentFailed) {
            InfoCard(stringResource(R.string.consent_save_error_title), error = true) {
                BodyText(stringResource(R.string.consent_save_error_body))
            }
            PrimaryAction(stringResource(R.string.retry_consent_save), onRetryConsent)
        } else {
            InfoCard(stringResource(title)) {
                if (state.deletion == Deletion.DELETING) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        BodyText(stringResource(R.string.deletion_processing_body))
                    }
                } else {
                    BodyText(stringResource(if (state.deletion == Deletion.PENDING) R.string.deletion_pending_body else R.string.withdrawal_complete_body))
                }
            }
            BodyText(stringResource(R.string.withdrawal_collection_stopped))
            when (state.deletion) {
                Deletion.PENDING -> PrimaryAction(stringResource(R.string.retry_deletion), onRetry)
                Deletion.DONE -> PrimaryAction(stringResource(R.string.consent_again), onConsent)
                else -> Unit
            }
        }
        LinkAction(stringResource(R.string.data_guide_title), onData)
    }
}

fun scenarioTitle(scenario: Scenario): Int = when (scenario) {
    Scenario.NORMAL -> R.string.scenario_normal
    Scenario.EMPTY -> R.string.scenario_empty
    Scenario.CONNECTION_ERROR -> R.string.scenario_connection
    Scenario.STT_ERROR -> R.string.scenario_stt
    Scenario.MASKING_ERROR -> R.string.scenario_masking
    Scenario.ANALYSIS_ERROR -> R.string.scenario_analysis
    Scenario.FINISH_ERROR -> R.string.scenario_finish
    Scenario.DELETE_ERROR -> R.string.scenario_delete
}
