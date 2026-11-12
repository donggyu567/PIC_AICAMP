package com.example.pic_ai_app.presentation.analysis

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.DetectedWarning
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.components.AudioLevelBars
import com.example.pic_ai_app.presentation.components.analysis.AnalysisWarningCard
import com.example.pic_ai_app.presentation.components.analysis.AnalysisWarningUi
import com.example.pic_ai_app.presentation.components.analysis.WarningEvidence
import com.example.pic_ai_app.ui.theme.*

private enum class LiveDetail(val title: Int) {
    Progress(R.string.live_progress), Recognition(R.string.live_recognition)
}

@Composable
internal fun AnalysisLiveScreen(state: SttState, onStop: () -> Unit, onHome: () -> Unit, onData: () -> Unit) {
    var detail by rememberSaveable { mutableStateOf<LiveDetail?>(null) }
    Surface(Modifier.fillMaxSize(), color = PicWhite, contentColor = PicInk) {
        Column(Modifier.safeDrawingPadding(), horizontalAlignment = Alignment.CenterHorizontally) {
            Row(Modifier.fillMaxWidth().padding(start = 14.dp, top = 8.dp, bottom = 4.dp),
                verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onHome) {
                    Icon(painterResource(R.drawable.result_back), stringResource(R.string.back), Modifier.rotate(180f))
                }
                Text(stringResource(R.string.analysis_in_progress), fontSize = 28.sp, fontWeight = FontWeight.ExtraBold)
                Spacer(Modifier.width(10.dp))
                AudioLevelBars(state.audioLevels, Modifier.size(44.dp), barCount = 9, barWidth = 3.dp,
                    gap = 2.dp, maxBarHeight = 20.dp, color = PicHomeBlue)
            }
            Surface(
                Modifier.fillMaxWidth().padding(horizontal = 20.dp), shape = RoundedCornerShape(20.dp),
                color = PicWhite, border = BorderStroke(1.dp, Color(0xFFD2E2F2)),
            ) {
                Column(Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(stringResource(R.string.live_risk_title), Modifier.weight(1f), color = PicHomeBlue,
                            fontSize = 19.sp, lineHeight = 24.sp, fontWeight = FontWeight.Bold)
                        Column(horizontalAlignment = Alignment.End) {
                            LiveDetail.entries.forEach { destination ->
                                Text(stringResource(destination.title),
                                    Modifier.clickable(role = Role.Button) { detail = destination }.padding(vertical = 3.dp),
                                    color = PicMuted, fontSize = 15.sp, textDecoration = TextDecoration.Underline)
                            }
                        }
                    }
                    Spacer(Modifier.height(16.dp))
                    LiveRiskGauge(state.risk?.cumulativeScore)
                }
            }
            val warnings = state.warnings
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth().padding(horizontal = 33.dp),
                reverseLayout = warnings.isNotEmpty(),
                contentPadding = PaddingValues(vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (warnings.isEmpty()) item {
                    Text(stringResource(R.string.no_warning_yet), color = PicMuted, fontSize = 15.sp)
                }
                items(warnings.asReversed(), key = { it.utteranceId }) { warning ->
                    val result = warning.result
                    AnalysisWarningCard(AnalysisWarningUi(
                        title = result.warningMessage.orEmpty(),
                        actionTitle = if ("money_transfer" in result.riskTypes) stringResource(R.string.detail_no_transfer) else "",
                        actionDescription = stringResource(R.string.detail_verify),
                        detectedAtMillis = warning.detectedAtMillis,
                        evidence = result.evidenceIds.distinct().mapNotNull { id ->
                            state.maskedTexts.getOrNull(id - 1)?.let { WarningEvidence(it) }
                        },
                    ), Modifier.fillMaxWidth())
                }
            }
            Button(
                onClick = onStop, modifier = Modifier.padding(bottom = 12.dp).fillMaxWidth(.67f).heightIn(min = 63.dp),
                shape = RoundedCornerShape(15.dp), colors = ButtonDefaults.buttonColors(containerColor = PicHomeBlue),
            ) {
                Text(stringResource(R.string.stop_analysis), color = PicWhite, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
    detail?.let { selected ->
        LiveDetailDialog(selected, state, onClose = { detail = null }, onData = { detail = null; onData() })
    }
}

@Composable
private fun LiveDetailDialog(detail: LiveDetail, state: SttState, onClose: () -> Unit, onData: () -> Unit) {
    AlertDialog(onDismissRequest = onClose, title = { Text(stringResource(detail.title)) },
        text = {
            LazyColumn(Modifier.heightIn(max = 400.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                item { Text(stringResource(R.string.confirmed_utterances, state.count)) }
                if (detail == LiveDetail.Progress) {
                    items(state.maskedTexts) { Text(it) }
                } else {
                    item {
                        val status = when {
                            state.phase == SttPhase.CONNECTING -> R.string.state_connecting
                            state.analyzing -> R.string.state_analyzing
                            state.masking -> R.string.state_masking
                            else -> R.string.state_recognizing
                        }
                        Text(stringResource(status))
                    }
                    state.error?.let { item { Text(it) } }
                    state.risk?.contextReason?.let { item { Text(it) } }
                    if (state.risk?.contextStatus == "error") item { Text(stringResource(R.string.live_context_error)) }
                    if (state.risk?.correctionStatus == "fallback") item { Text(stringResource(R.string.live_correction_fallback)) }
                }
            }
        },
        dismissButton = { TextButton(onClick = onData) { Text(stringResource(R.string.data_guide_short)) } },
        confirmButton = { TextButton(onClick = onClose) { Text(stringResource(R.string.close)) } })
}

@Preview(name = "실시간 분석 · 경고 감지", widthDp = 412, heightDp = 917, showBackground = true)
@Composable
private fun AnalysisLivePreview() {
    val risk = RiskResult(83.0, 76.0, "위험 · 송금 유도 의심", "ok", null, "ok",
        riskTypes = listOf("money_transfer"), evidenceIds = listOf(1))
    PicScreenTheme {
        AnalysisLiveScreen(SttState(phase = SttPhase.LISTENING, count = 1, risk = risk,
            maskedTexts = listOf("안전계좌로 돈을 이체해 주세요."),
            warnings = listOf(DetectedWarning(1, 1_794_461_520_000L, risk)),
            audioLevels = listOf(.3f, .5f, .8f, .45f, .7f, .55f, .4f, .8f, .6f)),
            onStop = {}, onHome = {}, onData = {})
    }
}
