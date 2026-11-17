package com.example.pic_ai_app.presentation.report

import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.report.ReportDestination
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.PicMuted
import com.example.pic_ai_app.ui.theme.PicScreenTheme

@Composable
internal fun ReportTipGuidanceScreen(
    phone: String, receivedAt: String, category: String, onTabSelected: (PicTab) -> Unit,
) {
    ReportGuidanceLayout(
        title = R.string.report_tip_guidance_title, description = R.string.report_tip_guidance_description,
        instructions = R.array.report_tip_instructions, notice = R.string.report_tip_submission_notice,
        siteLabel = R.string.report_open_tip_site,
        destination = ReportDestination.PhishingSos,
        onTabSelected = onTabSelected,
        footer = { Text(stringResource(R.string.report_external_site), color = PicMuted, fontSize = 12.sp) },
    ) {
        ReportFieldLabel(stringResource(R.string.report_tip_items))
        val missing = stringResource(R.string.report_not_entered)
        Column {
            listOf(R.string.report_phone to phone, R.string.report_received_time to receivedAt,
                R.string.report_category to category).forEach { (label, value) ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(stringResource(label), color = PicMuted, fontSize = 14.sp)
                    Text(value.ifBlank { missing }, color = PicMuted, fontSize = 14.sp)
                }
            }
        }
    }
}

@Preview(name = "신고 04A · 피싱안심SOS 제보 안내", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun ReportTipGuidancePreview() {
    PicScreenTheme { ReportTipGuidanceScreen("02-0000-0000", "2026.11.16 오후 2:32", "기관사칭 → 정부 • 공공 → 금감원", {}) }
}
