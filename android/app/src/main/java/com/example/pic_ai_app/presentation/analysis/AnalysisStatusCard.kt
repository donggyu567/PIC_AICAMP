package com.example.pic_ai_app.presentation.analysis

import androidx.annotation.StringRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.analysis.AnalysisCardHeader
import com.example.pic_ai_app.ui.theme.PicNavigationSelected
import com.example.pic_ai_app.ui.theme.PicTheme

private val cautionGreen = Color(0xFF285D49)

@Composable
internal fun AnalysisStatusCard(checkedAtMillis: Long, modifier: Modifier = Modifier) {
    Surface(modifier, shape = RoundedCornerShape(20.dp), color = Color(0xFFF1F8F4),
        contentColor = PicNavigationSelected, border = BorderStroke(1.dp, Color(0xFFC6DFD2))) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            AnalysisCardHeader(R.drawable.ic_analysis_info, stringResource(R.string.analysis_status_title), checkedAtMillis)
            Text(stringResource(R.string.analysis_status_no_new_warning), fontSize = 20.sp, lineHeight = 22.sp,
                fontWeight = FontWeight.Bold)
            Text(stringResource(R.string.analysis_status_caution), color = cautionGreen,
                fontSize = 18.sp, fontWeight = FontWeight.Bold)
            CautionRow(R.string.caution_transfer)
            CautionRow(R.string.caution_app)
            CautionRow(R.string.caution_personal_info)
        }
    }
}

@Composable
private fun CautionRow(@StringRes label: Int) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Spacer(Modifier.padding(top = 10.dp).size(5.dp).background(cautionGreen, CircleShape))
        Text(stringResource(label), Modifier.weight(1f), fontSize = 17.sp,
            fontWeight = FontWeight.Bold, lineHeight = 24.sp)
    }
}

@Preview(name = "분석 안내 카드", showBackground = true, widthDp = 362)
@Composable
private fun AnalysisStatusCardPreview() {
    PicTheme { AnalysisStatusCard(1_794_461_520_000L, Modifier.fillMaxWidth().padding(8.dp)) }
}
