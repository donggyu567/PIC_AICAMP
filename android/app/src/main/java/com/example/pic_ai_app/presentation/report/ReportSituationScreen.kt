package com.example.pic_ai_app.presentation.report

import androidx.annotation.StringRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.report.MoneyLoss
import com.example.pic_ai_app.data.report.ReportDestination
import com.example.pic_ai_app.data.report.ReportSituation
import com.example.pic_ai_app.data.report.ReportWorkflow
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.*

@StringRes
private fun ReportSituation.label() = when (this) {
    ReportSituation.SuspiciousCallOnly -> R.string.report_situation_call_only
    ReportSituation.MoneyOrInformation -> R.string.report_situation_shared
}

@StringRes
private fun MoneyLoss.label() = when (this) {
    MoneyLoss.Yes -> R.string.report_loss_yes
    MoneyLoss.No -> R.string.report_loss_no
    MoneyLoss.Unsure -> R.string.report_loss_unsure
}

@Composable
internal fun ReportSituationScreen(
    workflow: ReportWorkflow, onChange: (ReportWorkflow) -> Unit,
    onNext: () -> Unit, onTabSelected: (PicTab) -> Unit,
) {
    val context = LocalContext.current
    val showLossQuestion = workflow.situation == ReportSituation.MoneyOrInformation
    ReportStepLayout(
        step = ReportStep.SituationCheck, title = R.string.report_situation_title,
        description = R.string.report_situation_description,
        canContinue = workflow.canAdvance,
        onNext = onNext, onTabSelected = onTabSelected,
    ) {
        Column(
            Modifier.weight(1f).widthIn(max = 480.dp).fillMaxWidth().verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                ReportSituation.entries.forEach { option ->
                    ReportRadioOption(workflow.situation == option, onSelect = { onChange(workflow.selectSituation(option)) }) {
                        Text(stringResource(option.label()), color = PicNavigationSelected,
                            fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
            if (showLossQuestion) {
                Text(stringResource(R.string.report_loss_question), color = PicNavigationSelected,
                    fontSize = 16.sp, fontWeight = FontWeight.Bold)
                Row(Modifier.fillMaxWidth().selectableGroup(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MoneyLoss.entries.forEach { answer ->
                        val selected = workflow.moneyLoss == answer
                        Surface(
                            modifier = Modifier.weight(1f), shape = RoundedCornerShape(10.dp),
                            color = if (selected) reportActiveColor else PicWhite,
                            border = BorderStroke(1.dp, if (selected) reportActiveColor else PicBorder),
                        ) {
                            Box(
                                Modifier.selectable(selected, role = Role.RadioButton, onClick = { onChange(workflow.answerMoneyLoss(answer)) })
                                    .heightIn(min = 44.dp).padding(4.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(stringResource(answer.label()), color = if (selected) PicWhite else reportActiveColor,
                                    fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                            }
                        }
                    }
                }
                if (workflow.showPaymentStopGuidance) {
                    Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp),
                        color = Color(0xFFFFF7ED), contentColor = Color(0xFF9A3412)) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(stringResource(R.string.report_loss_notice_title), fontSize = 15.sp,
                                fontWeight = FontWeight.Bold)
                            Text(stringResource(R.string.report_loss_notice_body), fontSize = 14.sp, lineHeight = 20.sp)
                            OutlinedButton(
                                onClick = { openReportDestination(context, ReportDestination.Emergency112) },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text(stringResource(R.string.report_open_112)) }
                        }
                    }
                }
            }
        }
    }
}
