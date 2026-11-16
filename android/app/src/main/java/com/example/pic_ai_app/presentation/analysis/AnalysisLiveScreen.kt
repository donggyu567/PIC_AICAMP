package com.example.pic_ai_app.presentation.analysis

import androidx.activity.compose.BackHandler

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.DetectedWarning
import com.example.pic_ai_app.data.stt.AnalysisNotice
import com.example.pic_ai_app.data.stt.AnalysisStatus
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.ui.theme.*

private enum class LiveDetail(val title: Int) {
    Progress(R.string.live_progress), Recognition(R.string.live_recognition)
}

@Composable
internal fun AnalysisLiveScreen(state: SttState, onStop: () -> Unit, onHome: () -> Unit) {
    var detail by rememberSaveable { mutableStateOf<LiveDetail?>(null) }
    val warningsScroll = rememberLazyListState()
    var lastScrolledNotice by rememberSaveable { mutableStateOf<String?>(null) }
    val closeDetail = { detail = null }
    BackHandler(enabled = detail != null, onBack = closeDetail)
    when (detail) {
        LiveDetail.Progress -> {
            UtteranceProgressScreen(state.maskedTexts, state.audioLevels, closeDetail)
            return
        }
        LiveDetail.Recognition -> {
            RecognitionStatusScreen(state, closeDetail)
            return
        }
        null -> Unit
    }
    Surface(Modifier.fillMaxSize(), color = PicWhite, contentColor = PicInk) {
        Column(Modifier.safeDrawingPadding(), horizontalAlignment = Alignment.CenterHorizontally) {
            AnalysisHeader(stringResource(R.string.analysis_in_progress), state.audioLevels, onHome)
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
            val notices = state.notices
            val latestKey = notices.lastOrNull()?.let(::noticeKey)
            LaunchedEffect(latestKey) {
                if (latestKey != null && latestKey != lastScrolledNotice) {
                    warningsScroll.animateScrollToItem(0)
                }
                lastScrolledNotice = latestKey
            }
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth().padding(horizontal = 33.dp),
                state = warningsScroll,
                contentPadding = PaddingValues(vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp, Alignment.Top),
            ) {
                items(notices.asReversed(), key = ::noticeKey) { notice ->
                    when (notice) {
                        is AnalysisStatus -> AnalysisStatusCard(notice.checkedAtMillis, Modifier.fillMaxWidth())
                        is DetectedWarning -> {
                            val result = notice.result
                            AnalysisWarningCard(AnalysisWarningUi(
                                title = result.warningMessage ?: stringResource(R.string.analysis_warning_detection),
                                actionTitle = if ("money_transfer" in result.riskTypes) stringResource(R.string.detail_no_transfer) else "",
                                actionDescription = stringResource(R.string.detail_verify),
                                detectedAtMillis = notice.detectedAtMillis,
                                evidence = result.evidenceIds.distinct().mapNotNull { id ->
                                    state.maskedTexts.getOrNull(id - 1)?.let { WarningEvidence(it) }
                                },
                            ), Modifier.fillMaxWidth())
                        }
                    }
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
}

private fun noticeKey(notice: AnalysisNotice): String = when (notice) {
    is AnalysisStatus -> "status"
    is DetectedWarning -> "warning-${notice.utteranceId}"
}

@Preview(name = "실시간 분석 · 경고와 안내", widthDp = 412, heightDp = 917, showBackground = true)
@Preview(name = "실시간 분석 · 두 카드 전체", widthDp = 412, heightDp = 1300, showBackground = true)
@Composable
private fun AnalysisLivePreview() {
    val risk = RiskResult(83.0, 76.0, "위험 · 송금 유도 의심", "ok", null, "ok",
        riskTypes = listOf("money_transfer"), evidenceIds = listOf(1))
    PicScreenTheme {
        AnalysisLiveScreen(SttState(phase = SttPhase.LISTENING, count = 1, risk = risk,
            maskedTexts = listOf("안전계좌로 돈을 이체해 주세요."),
            notices = listOf(AnalysisStatus(1_794_461_520_000L), DetectedWarning(1, 1_794_461_580_000L, risk)),
            audioLevels = listOf(.3f, .5f, .8f, .45f, .7f, .55f, .4f, .8f, .6f)),
            onStop = {}, onHome = {})
    }
}
