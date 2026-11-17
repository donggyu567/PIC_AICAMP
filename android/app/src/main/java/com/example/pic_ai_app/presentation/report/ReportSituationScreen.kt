package com.example.pic_ai_app.presentation.report

import androidx.annotation.StringRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.*

internal enum class ReportSituation(@StringRes val label: Int) {
    SuspiciousCallOnly(R.string.report_situation_call_only),
    MoneyOrInfoShared(R.string.report_situation_shared),
}

internal enum class MoneyLossAnswer(@StringRes val label: Int) {
    Yes(R.string.report_loss_yes), No(R.string.report_loss_no), Unsure(R.string.report_loss_unsure),
}

@Composable
internal fun ReportSituationScreen(
    callId: String, onNext: (String, ReportSituation, MoneyLossAnswer?) -> Unit, onTabSelected: (PicTab) -> Unit,
) {
    var situation by rememberSaveable(callId) { mutableStateOf<ReportSituation?>(null) }
    var loss by rememberSaveable(callId) { mutableStateOf<MoneyLossAnswer?>(null) }
    SituationContent(
        situation, loss,
        onSituation = {
            if (situation != it) loss = null
            situation = it
        },
        onLoss = { loss = it },
        onNext = { situation?.let { onNext(callId, it, loss) } },
        onTabSelected = onTabSelected,
    )
}

@Composable
private fun SituationContent(
    situation: ReportSituation?, loss: MoneyLossAnswer?,
    onSituation: (ReportSituation) -> Unit, onLoss: (MoneyLossAnswer) -> Unit,
    onNext: () -> Unit, onTabSelected: (PicTab) -> Unit,
) {
    val showLossQuestion = situation == ReportSituation.MoneyOrInfoShared
    ReportStepLayout(
        step = ReportStep.SituationCheck, title = R.string.report_situation_title,
        description = R.string.report_situation_description,
        canContinue = situation == ReportSituation.SuspiciousCallOnly || (showLossQuestion && loss != null),
        onNext = onNext, onTabSelected = onTabSelected,
    ) {
        Column(
            Modifier.weight(1f).widthIn(max = 480.dp).fillMaxWidth().verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                ReportSituation.entries.forEach { option ->
                    ReportRadioOption(situation == option, onSelect = { onSituation(option) }) {
                        Text(stringResource(option.label), color = PicNavigationSelected,
                            fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
            if (showLossQuestion) {
                Text(stringResource(R.string.report_loss_question), color = PicNavigationSelected,
                    fontSize = 16.sp, fontWeight = FontWeight.Bold)
                Row(Modifier.fillMaxWidth().selectableGroup(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MoneyLossAnswer.entries.forEach { answer ->
                        val selected = loss == answer
                        Surface(
                            modifier = Modifier.weight(1f), shape = RoundedCornerShape(10.dp),
                            color = if (selected) reportActiveColor else PicWhite,
                            border = BorderStroke(1.dp, if (selected) reportActiveColor else PicBorder),
                        ) {
                            Box(
                                Modifier.selectable(selected, role = Role.RadioButton, onClick = { onLoss(answer) })
                                    .heightIn(min = 44.dp).padding(4.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(stringResource(answer.label), color = if (selected) PicWhite else reportActiveColor,
                                    fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                            }
                        }
                    }
                }
                if (loss == MoneyLossAnswer.Yes || loss == MoneyLossAnswer.Unsure) {
                    Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp),
                        color = Color(0xFFFFF7ED), contentColor = Color(0xFF9A3412)) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(stringResource(R.string.report_loss_notice_title), fontSize = 15.sp,
                                fontWeight = FontWeight.Bold)
                            Text(stringResource(R.string.report_loss_notice_body), fontSize = 14.sp, lineHeight = 20.sp)
                        }
                    }
                }
            }
        }
    }
}

@Preview(name = "신고 02 · 상황 확인", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun ReportSituationPreview() {
    PicScreenTheme {
        ReportSituationScreen(callId = "preview", onNext = { _, _, _ -> }, onTabSelected = {})
    }
}

@Preview(name = "신고 02 · 송금·출금 안내", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun MoneyLossPreview() {
    PicScreenTheme {
        SituationContent(ReportSituation.MoneyOrInfoShared, MoneyLossAnswer.Yes, {}, {}, {}, {})
    }
}
