package com.example.pic_ai_app.presentation.report

import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicTheme
import com.example.pic_ai_app.ui.theme.PicWhite

internal enum class ReportStep(@StringRes val label: Int, @DrawableRes val icon: Int) {
    CallSelection(R.string.report_step_call_selection, R.drawable.ic_report_call),
    SituationCheck(R.string.report_step_situation_check, R.drawable.ic_report_assignment_turned_in),
    PrepareMaterials(R.string.report_step_prepare_materials, R.drawable.ic_report_description),
    Guidance(R.string.report_step_guidance, R.drawable.ic_report_flag),
}

internal val reportActiveColor = Color(0xFF36506C)

@Composable
internal fun ReportStepIndicator(currentStep: ReportStep, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().padding(start = 24.dp, end = 24.dp, top = 2.dp, bottom = 18.dp)) {
        ReportStep.entries.forEach { step ->
            val completed = step < currentStep
            val current = step == currentStep
            val status = stringResource(when {
                completed -> R.string.report_step_completed
                current -> R.string.report_step_current
                else -> R.string.report_step_upcoming
            })
            Column(
                modifier = Modifier.weight(1f).heightIn(min = 84.dp)
                    .semantics(mergeDescendants = true) { stateDescription = status },
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(
                    Modifier.size(48.dp).background(
                        if (completed || current) reportActiveColor else Color(0xFFEEF1F5), CircleShape,
                    ),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        painterResource(if (completed) R.drawable.ic_report_check else step.icon),
                        contentDescription = null, modifier = Modifier.size(24.dp),
                        tint = if (completed || current) PicWhite else Color(0xFF8996A8),
                    )
                }
                Text(
                    stringResource(step.label), color = if (current) reportActiveColor else Color(0xFF64748B),
                    fontSize = 13.sp, lineHeight = 19.sp, textAlign = TextAlign.Center,
                    fontWeight = if (current) FontWeight.Bold else FontWeight.Normal,
                )
            }
            if (step != ReportStep.Guidance) {
                Box(Modifier.size(width = 20.dp, height = 48.dp), contentAlignment = Alignment.Center) {
                    Icon(
                        painterResource(R.drawable.ic_report_more_horiz), contentDescription = null,
                        modifier = Modifier.size(20.dp), tint = if (completed) reportActiveColor else Color(0xFFCBD5E1),
                    )
                }
            }
        }
    }
}

@Preview(name = "신고 01 · 통화 선택", widthDp = 412, showBackground = true, backgroundColor = 0xFFFFFFFF)
@Composable
private fun CallSelectionStepsPreview() {
    PicTheme { ReportStepIndicator(ReportStep.CallSelection) }
}

@Preview(name = "신고 02 · 상황 확인", widthDp = 412, showBackground = true, backgroundColor = 0xFFFFFFFF)
@Composable
private fun SituationCheckStepsPreview() {
    PicTheme { ReportStepIndicator(ReportStep.SituationCheck) }
}
