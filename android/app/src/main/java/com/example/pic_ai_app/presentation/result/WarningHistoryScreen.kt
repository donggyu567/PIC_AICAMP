package com.example.pic_ai_app.presentation.result

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.DetectedWarning
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.analysis.AnalysisWarningCard
import com.example.pic_ai_app.presentation.analysis.toWarningUi
import com.example.pic_ai_app.ui.theme.PicInk
import com.example.pic_ai_app.ui.theme.PicMuted
import com.example.pic_ai_app.ui.theme.PicScreenTheme
import com.example.pic_ai_app.ui.theme.PicWhite

@Composable
internal fun WarningHistoryScreen(state: SttState, hasWarningHistory: Boolean, onBack: () -> Unit) {
    val warnings = remember(state.notices) { state.notices.filterIsInstance<DetectedWarning>().asReversed() }
    Surface(Modifier.fillMaxSize(), color = PicWhite, contentColor = PicInk) {
        Column(
            Modifier.windowInsetsPadding(WindowInsets.safeDrawing.union(WindowInsets(top = 32.dp))),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            ResultDetailHeader(stringResource(R.string.history_warning_title), onBack)
            if (warnings.isEmpty()) {
                val message = if (hasWarningHistory) R.string.history_warning_empty else R.string.history_warning_unavailable
                Text(stringResource(message), Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(20.dp), color = PicMuted)
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f).widthIn(max = 480.dp).fillMaxWidth(),
                    reverseLayout = true,
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.Top),
                ) {
                    items(warnings, key = { it.utteranceId }) { warning ->
                        AnalysisWarningCard(warning.toWarningUi(state.maskedTexts), Modifier.fillMaxWidth())
                    }
                }
            }
        }
    }
}

@Preview(name = "경고 누적 화면", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun WarningHistoryPreview() {
    val lines = listOf("기관에서 계좌를 확인하겠습니다.", "안전계좌로 돈을 옮겨 주세요.", "지금 바로 이체해 주세요.")
    val risk = RiskResult(null, null, "위험 · 송금 유도 의심", "ok", null, null, riskTypes = listOf("money_transfer"))
    val firstWarning = 1779600300000L
    val warnings = listOf(0, 3, 5).mapIndexed { index, minutes ->
        val id = index + 1
        DetectedWarning(id, firstWarning + minutes * 60_000L, risk.copy(evidenceIds = listOf(id)))
    }
    PicScreenTheme {
        WarningHistoryScreen(SttState(notices = warnings, maskedTexts = lines), hasWarningHistory = true, onBack = {})
    }
}
