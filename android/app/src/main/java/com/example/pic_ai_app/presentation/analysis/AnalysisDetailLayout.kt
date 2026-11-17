package com.example.pic_ai_app.presentation.analysis

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.AudioLevelBars
import com.example.pic_ai_app.ui.theme.PicBorder
import com.example.pic_ai_app.ui.theme.PicHomeBlue
import com.example.pic_ai_app.ui.theme.PicWhite

@Composable
internal fun AnalysisHeader(title: String, levels: List<Float>, onBack: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(start = 14.dp, end = 12.dp, top = 8.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = onBack) {
            Icon(painterResource(R.drawable.result_back), stringResource(R.string.back), Modifier.rotate(180f))
        }
        Text(title, Modifier.weight(1f, fill = false), fontSize = 28.sp, lineHeight = 34.sp,
            fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.width(10.dp))
        AudioLevelBars(levels, Modifier.size(44.dp), barCount = 9, barWidth = 3.dp,
            gap = 2.dp, maxBarHeight = 20.dp, color = PicHomeBlue)
    }
}

@Composable
internal fun AnalysisDetailLayout(
    title: String, levels: List<Float>, onBack: () -> Unit, content: @Composable ColumnScope.() -> Unit,
) {
    Surface(Modifier.fillMaxSize(), color = PicWhite, contentColor = Color(0xFF1F1F1F)) {
        Column(Modifier.windowInsetsPadding(WindowInsets.safeDrawing.union(WindowInsets(top = 32.dp)))) {
            AnalysisHeader(title, levels, onBack)
            Column(Modifier.fillMaxSize().padding(horizontal = 24.dp), content = content)
        }
    }
}

@Composable
internal fun AnalysisDetailCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Surface(modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp), color = Color(0xFFF8FAFC),
        contentColor = Color(0xFF1F1F1F), border = BorderStroke(1.dp, PicBorder), content = content)
}
