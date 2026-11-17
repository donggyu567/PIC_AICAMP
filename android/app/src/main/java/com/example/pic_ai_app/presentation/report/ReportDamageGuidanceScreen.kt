package com.example.pic_ai_app.presentation.report

import android.content.Intent
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.PicMuted
import com.example.pic_ai_app.ui.theme.PicScreenTheme

@Composable
internal fun ReportDamageGuidanceScreen(damageText: String, onTabSelected: (PicTab) -> Unit) {
    val context = LocalContext.current
    val copyLabel = stringResource(R.string.report_copy_damage)
    ReportGuidanceLayout(
        title = R.string.report_damage_guidance_title, description = R.string.report_damage_guidance_description,
        instructions = R.array.report_damage_instructions, notice = R.string.report_damage_submission_notice,
        siteLabel = R.string.report_open_ecrm, siteUrl = "https://ecrm.police.go.kr/minwon/main",
        onTabSelected = onTabSelected,
        footer = {
            OutlinedButton(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
                enabled = damageText.isNotBlank(),
                onClick = { copyReportText(context, copyLabel, damageText, R.string.report_damage_copied) }) {
                Text(copyLabel)
            }
        },
    ) {
        ReportFieldLabel(stringResource(R.string.report_info_only))
        Text(stringResource(R.string.report_info_only_description), color = PicMuted, fontSize = 14.sp, lineHeight = 20.sp)
        OutlinedButton(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
            onClick = { openReportLink(context, Intent(Intent.ACTION_DIAL, "tel:1394".toUri())) }) {
            Text(stringResource(R.string.report_open_dialer))
        }
    }
}

@Preview(name = "신고 04B · 금전 피해 신고 안내", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun ReportDamageGuidancePreview() {
    PicScreenTheme { ReportDamageGuidanceScreen("상대가 계좌 이체를 요구했습니다.", {}) }
}
