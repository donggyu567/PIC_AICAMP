package com.example.pic_ai_app.presentation.report

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.annotation.ArrayRes
import androidx.annotation.StringRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.*

@Composable
internal fun ReportGuidanceLayout(
    @StringRes title: Int, @StringRes description: Int, @ArrayRes instructions: Int,
    @StringRes notice: Int, @StringRes siteLabel: Int, siteUrl: String, onTabSelected: (PicTab) -> Unit,
    footer: @Composable () -> Unit, card: @Composable ColumnScope.() -> Unit,
) {
    val context = LocalContext.current
    val tint = Color(0xFFEEF3F8)
    ReportStepLayout(
        step = ReportStep.Guidance, title = title, description = description, canContinue = true,
        primaryButtonLabel = siteLabel, onTabSelected = onTabSelected,
        onNext = { openReportLink(context, Intent(Intent.ACTION_VIEW, siteUrl.toUri())) },
    ) {
        Column(
            Modifier.weight(1f).widthIn(max = 480.dp).fillMaxWidth()
                .verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            stringArrayResource(instructions).forEachIndexed { index, instruction ->
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Surface(shape = CircleShape, color = tint) {
                        Box(Modifier.size(26.dp), contentAlignment = Alignment.Center) {
                            Text((index + 1).toString(), color = reportActiveColor,
                                fontSize = 14.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                    Text(instruction, color = PicNavigationSelected, fontSize = 16.sp, lineHeight = 22.sp)
                }
            }
            Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), color = PicCard,
                border = BorderStroke(1.dp, PicBorder)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp), content = card)
            }
            Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp), color = tint) {
                Text(stringResource(notice), Modifier.padding(12.dp),
                    color = reportActiveColor, fontSize = 14.sp, lineHeight = 20.sp)
            }
        }
        Box(Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(horizontal = 24.dp),
            contentAlignment = Alignment.Center) { footer() }
    }
}

internal fun openReportLink(context: Context, intent: Intent) {
    try {
        context.startActivity(intent)
    } catch (_: ActivityNotFoundException) {
        Toast.makeText(context, R.string.report_no_external_app, Toast.LENGTH_SHORT).show()
    }
}
