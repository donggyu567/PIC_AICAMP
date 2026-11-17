package com.example.pic_ai_app.presentation.report

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.report.HarmDraft
import com.example.pic_ai_app.data.report.ReportDestination
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.PicMuted

@Composable
internal fun ReportDamageGuidanceScreen(draft: HarmDraft, onTabSelected: (PicTab) -> Unit) {
    val context = LocalContext.current
    val copyLabel = stringResource(R.string.report_copy_damage)
    ReportGuidanceLayout(
        title = R.string.report_harm_guidance_title, description = R.string.report_harm_guidance_description,
        instructions = R.array.report_damage_instructions, notice = R.string.report_damage_submission_notice,
        siteLabel = R.string.report_open_ecrm, destination = ReportDestination.Ecrm,
        onTabSelected = onTabSelected,
        footer = {
            OutlinedButton(
                modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp), enabled = draft.hasTimeline,
                onClick = { copyReportText(context, copyLabel, draft.timelineText(), R.string.report_damage_copied) },
            ) { Text(copyLabel) }
        },
    ) {
        ReportFieldLabel(stringResource(R.string.report_harm_copy_done))
        Text(stringResource(R.string.report_harm_copy_reference), color = PicMuted, fontSize = 14.sp, lineHeight = 20.sp)
    }
}
