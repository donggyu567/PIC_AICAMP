package com.example.pic_ai_app.presentation.history

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
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
import com.example.pic_ai_app.presentation.analysis.bandFor
import com.example.pic_ai_app.ui.theme.PicBorder
import com.example.pic_ai_app.ui.theme.PicMuted
import com.example.pic_ai_app.ui.theme.PicTheme
import com.example.pic_ai_app.ui.theme.PicWhite
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import kotlin.math.roundToInt

@Composable
internal fun AnalysisResultSummaryCard(
    title: String?,
    cumulativeScore: Double?,
    endedAtMillis: Long?,
    onOpen: () -> Unit,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var showDelete by remember { mutableStateOf(false) }

    Box(modifier) {
        Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(15.dp), color = PicWhite,
            border = BorderStroke(1.dp, PicBorder), shadowElevation = 3.dp) {
            Column(
                Modifier.combinedClickable(
                    role = Role.Button, onClick = onOpen,
                    onLongClickLabel = stringResource(R.string.history_delete_menu),
                    onLongClick = { showDelete = true },
                ).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                AnalysisSummaryContent(title, cumulativeScore, endedAtMillis)
            }
        }
        DropdownMenu(expanded = showDelete, onDismissRequest = { showDelete = false }) {
            DropdownMenuItem(text = { Text(stringResource(R.string.history_delete)) }, onClick = {
                showDelete = false
                onDelete()
            })
        }
    }
}

@Composable
internal fun AnalysisSummaryContent(
    title: String?, cumulativeScore: Double?, endedAtMillis: Long?, modifier: Modifier = Modifier,
) {
    val points = cumulativeScore?.takeIf { it.isFinite() }?.roundToInt()
    val band = points?.let(::bandFor)
    val pointsLabel = stringResource(R.string.live_points, points ?: 0)
    Column(modifier, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.detail_score), Modifier.weight(1f), color = PicMuted,
                fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            Surface(shape = CircleShape, color = (band?.arc ?: PicMuted).copy(alpha = .09f)) {
                Text(
                    if (band == null) pointsLabel else stringResource(R.string.history_score_band, pointsLabel, stringResource(band.label)),
                    Modifier.padding(horizontal = 10.dp, vertical = 4.dp), color = band?.ink ?: PicMuted,
                    fontSize = 16.sp, fontWeight = FontWeight.Bold,
                )
            }
        }
        Text(title?.takeIf { it.isNotBlank() } ?: stringResource(R.string.final_title),
            color = Color(0xFF111827), fontSize = 20.sp, lineHeight = 28.sp, fontWeight = FontWeight.Bold)
        endedAtMillis?.let { millis ->
            val date = remember(millis) {
                SimpleDateFormat("yyyy.MM.dd HH:mm", Locale.KOREA).apply {
                    timeZone = TimeZone.getTimeZone("Asia/Seoul")
                }.format(Date(millis))
            }
            Text(date, Modifier.align(Alignment.End), color = Color(0xFF374151),
                fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Preview(name = "분석 결과 간단 정리", showBackground = true, widthDp = 376)
@Composable
private fun AnalysisResultSummaryCardPreview() {
    PicTheme {
        var visible by remember { mutableStateOf(true) }
        if (visible) AnalysisResultSummaryCard(
            title = "계좌 보호를 이유로 송금을 요구한 통화",
            cumulativeScore = 82.0, endedAtMillis = 1_794_461_520_000L,
            onOpen = {}, onDelete = { visible = false }, modifier = Modifier.padding(16.dp),
        )
    }
}
