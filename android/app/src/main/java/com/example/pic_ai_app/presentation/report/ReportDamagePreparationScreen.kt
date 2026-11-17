package com.example.pic_ai_app.presentation.report

import android.widget.Toast
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.report.HarmDraft
import com.example.pic_ai_app.data.report.ReportWorkflow
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.PicMuted

@Composable
internal fun ReportDamagePreparationScreen(
    workflow: ReportWorkflow, onChange: (ReportWorkflow) -> Unit, onTabSelected: (PicTab) -> Unit,
    prefill: HarmPrefill, onRetry: (() -> Unit)?, onCopied: () -> Unit,
) {
    val draft = workflow.harm
    val context = LocalContext.current
    val copyLabel = stringResource(R.string.report_harm_copy_report)
    val edit: (HarmDraft) -> Unit = { onChange(workflow.editHarm(it)) }
    ReportPreparationLayout(
        R.string.report_harm_title, R.string.report_harm_description, onTabSelected,
        onNext = {
            if (copyReportText(context, copyLabel, draft.toReportText(), R.string.report_harm_report_copied)) {
                onCopied()
            } else {
                Toast.makeText(context, R.string.report_harm_copy_failed, Toast.LENGTH_SHORT).show()
            }
        },
        canContinue = draft.canCopyReport,
        primaryButtonLabel = R.string.report_harm_copy_report,
    ) {
        when (prefill) {
            HarmPrefill.Loading -> Text(stringResource(R.string.report_harm_prefill_loading), color = PicMuted)
            HarmPrefill.Failed, HarmPrefill.Idle -> {
                if (prefill == HarmPrefill.Failed || onRetry == null) {
                    Text(stringResource(R.string.report_harm_prefill_unavailable), color = PicMuted)
                    if (onRetry != null) {
                        TextButton(onClick = onRetry) { Text(stringResource(R.string.report_harm_prefill_retry)) }
                    }
                }
            }
            HarmPrefill.Ready -> Text(stringResource(R.string.report_harm_prefill_review), color = PicMuted)
        }

        ReportFieldLabel(stringResource(R.string.report_harm_victim))
        ReportField(stringResource(R.string.report_harm_name), draft.victimName,
            { edit(draft.copy(victimName = it)) }, R.string.report_harm_name_hint)
        ReportField(stringResource(R.string.report_harm_birth), draft.victimBirthDate,
            { edit(draft.copy(victimBirthDate = it)) }, R.string.report_harm_birth_hint)
        ReportField(stringResource(R.string.report_harm_contact), draft.victimPhone,
            { edit(draft.copy(victimPhone = it)) }, R.string.report_harm_contact_hint,
            keyboard = KeyboardType.Phone)

        ReportFieldLabel(stringResource(R.string.report_harm_suspect))
        ReportField(stringResource(R.string.report_harm_claim), draft.claimedIdentity.orEmpty(),
            { edit(draft.copy(claimedIdentity = it)) }, R.string.report_harm_claim_hint)
        ReportField(stringResource(R.string.report_phone), draft.suspectPhone,
            { edit(draft.copy(suspectPhone = it)) }, R.string.report_phone_hint,
            keyboard = KeyboardType.Phone)
        ReportField(stringResource(R.string.report_harm_messenger), draft.messengerId,
            { edit(draft.copy(messengerId = it)) }, R.string.report_harm_optional)
        ReportFieldLabel(stringResource(R.string.report_harm_recipient_account))
        ReportField(stringResource(R.string.report_harm_bank), draft.bankName,
            { edit(draft.copy(bankName = it)) }, R.string.report_harm_optional)
        ReportField(stringResource(R.string.report_harm_account), draft.accountNumber,
            { edit(draft.copy(accountNumber = it)) }, R.string.report_harm_optional,
            keyboard = KeyboardType.Phone)
        ReportField(stringResource(R.string.report_harm_account_holder), draft.accountHolder,
            { edit(draft.copy(accountHolder = it)) }, R.string.report_harm_optional)

        ReportFieldLabel(stringResource(R.string.report_harm_timeline))
        ReportField(stringResource(R.string.report_harm_first_contact), draft.firstContact.orEmpty(),
            { edit(draft.copy(firstContact = it)) }, R.string.report_harm_first_contact_hint,
            multiline = true)
        ReportField(stringResource(R.string.report_harm_deception), draft.deception.orEmpty(),
            { edit(draft.copy(deception = it)) }, R.string.report_harm_deception_hint,
            multiline = true)
        ReportField(stringResource(R.string.report_harm_damage), draft.damage,
            { edit(draft.copy(damage = it)) }, R.string.report_harm_damage_hint,
            multiline = true)
        ReportField(stringResource(R.string.report_harm_discovery), draft.discoveryAndResponse,
            { edit(draft.copy(discoveryAndResponse = it)) }, R.string.report_harm_discovery_hint,
            multiline = true)

        ReportFieldLabel(stringResource(R.string.report_harm_evidence))
        Text(stringResource(R.string.report_harm_evidence_note), color = PicMuted, fontSize = 13.sp)
    }
}
