package com.example.pic_ai_app.presentation.analysis

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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

@Composable
internal fun AnalysisStatusCard(title: String, detail: String, timeMillis: Long? = null, modifier: Modifier = Modifier) {
    Surface(modifier, shape = RoundedCornerShape(20.dp), color = Color(0xFFF1F8F4),
        contentColor = PicNavigationSelected, border = BorderStroke(1.dp, Color(0xFFC6DFD2))) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            AnalysisCardHeader(R.drawable.ic_analysis_info, title, timeMillis)
            Text(detail, fontSize = 17.sp, lineHeight = 22.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Preview(name = "분석 안내 카드", showBackground = true, widthDp = 362)
@Composable
private fun AnalysisStatusCardPreview() {
    PicTheme {
        AnalysisStatusCard(stringResource(R.string.analysis_status_title), stringResource(R.string.analysis_start_listening),
            1_794_461_520_000L, Modifier.fillMaxWidth().padding(8.dp))
    }
}
