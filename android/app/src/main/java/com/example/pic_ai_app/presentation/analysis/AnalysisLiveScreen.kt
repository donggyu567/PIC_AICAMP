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
import com.example.pic_ai_app.data.stt.LiveAnalysisCards
import com.example.pic_ai_app.data.stt.LiveContextNotice
import com.example.pic_ai_app.data.stt.LiveRiskAlert
import com.example.pic_ai_app.data.stt.LiveRiskSource
import com.example.pic_ai_app.data.stt.liveSignal
import com.example.pic_ai_app.data.stt.LiveScoreChange
import com.example.pic_ai_app.data.stt.LiveScoreUpdate
import com.example.pic_ai_app.data.stt.LiveStartNotice
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
    var lastScrolledCard by rememberSaveable(state.conversationId) { mutableStateOf<String?>(null) }
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
                    LiveRiskGauge(state.liveCards.score)
                }
            }
            val liveCards = state.liveCards
            val latestCard = liveCards.lastAddedKey
            LaunchedEffect(latestCard) {
                if (latestCard != null && latestCard != lastScrolledCard && liveCards.cards.lastOrNull()?.key == latestCard) {
                    warningsScroll.animateScrollToItem(0)
                    lastScrolledCard = latestCard
                }
            }
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth().padding(horizontal = 33.dp),
                state = warningsScroll,
                contentPadding = PaddingValues(vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp, Alignment.Top),
            ) {
                items(liveCards.cards.asReversed(), key = { it.key }) { card ->
                    when (card) {
                        is LiveStartNotice -> AnalysisStatusCard(
                            title = stringResource(R.string.analysis_status_title),
                            detail = stringResource(if (card.hasScore) R.string.analysis_start_no_warning else R.string.analysis_start_listening),
                            timeMillis = card.shownAtMillis,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        is LiveContextNotice -> AnalysisStatusCard(
                            title = stringResource(R.string.analysis_context_card_title),
                            detail = card.reason ?: stringResource(R.string.live_context_attention),
                            timeMillis = card.shownAtMillis,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        is LiveScoreUpdate -> AnalysisStatusCard(
                            title = stringResource(R.string.analysis_score_change),
                            detail = scoreChangeText(card.change),
                            modifier = Modifier.fillMaxWidth(),
                        )
                        is LiveRiskAlert -> LiveAlertCard(card, state.maskedTexts)
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

@Composable
private fun scoreChangeText(change: LiveScoreChange, showRise: Boolean = false): String {
    val previous = change.previous
    val stage = stringResource(change.current.level.labelRes())
    if (previous == null) return stringResource(R.string.analysis_score_initial, change.current.points, stage)
    val format = when {
        showRise -> R.string.analysis_score_increased
        change.current.level < previous.level -> R.string.analysis_score_decreased
        else -> R.string.analysis_score_transition
    }
    return stringResource(format, previous.points, change.current.points, stage)
}

@Composable
private fun LiveAlertCard(card: LiveRiskAlert, maskedTexts: List<String>) {
    val signal = card.signal
    val types = signal?.types.orEmpty()
    val detected = types.map { type -> stringResource(detectedTypeLabel(type)) }.joinToString(", ")
    val contextOnly = signal?.source == LiveRiskSource.Context
    val rise = card.rise
    val title = when {
        contextOnly && detected.isNotEmpty() -> stringResource(R.string.analysis_type_suspected, detected)
        contextOnly -> stringResource(R.string.analysis_context_heading)
        signal?.source == LiveRiskSource.ServerWarning ->
            signal.warningMessage ?: stringResource(R.string.analysis_warning_detection)
        detected.isNotEmpty() -> stringResource(R.string.analysis_type_detected, detected)
        rise?.previous != null -> stringResource(R.string.analysis_level_increased,
            stringResource(rise.current.level.labelRes()))
        rise != null -> stringResource(R.string.analysis_level_reached, stringResource(rise.current.level.labelRes()))
        else -> stringResource(R.string.analysis_warning_detection)
    }
    val action = liveRiskActions.entries.firstOrNull { it.key in card.actionTypes }?.value
    val actionDescription = when {
        action != null -> stringResource(action.second)
        signal != null -> stringResource(R.string.detail_verify)
        else -> ""
    }
    AnalysisWarningCard(AnalysisWarningUi(
        title = title,
        actionTitle = action?.let { stringResource(it.first) }.orEmpty(),
        actionDescription = actionDescription,
        heading = if (contextOnly) stringResource(R.string.analysis_context_heading) else null,
        detectedAtMillis = card.detectedAtMillis,
        evidence = card.evidenceIds.mapNotNull { id -> maskedTexts.getOrNull(id - 1)?.let { WarningEvidence(it) } },
        scoreDetail = rise?.let { scoreChangeText(it, showRise = signal != null) },
    ), Modifier.fillMaxWidth())
}

private val liveRiskActions = linkedMapOf(
    "money_transfer" to (R.string.detail_no_transfer to R.string.detail_verify),
    "personal_information" to (R.string.analysis_action_personal_title to R.string.analysis_action_personal_detail),
    "app_installation" to (R.string.analysis_action_app_title to R.string.analysis_action_app_detail),
    "loan_fraud" to (R.string.analysis_action_loan_title to R.string.analysis_action_loan_detail),
    "institution_impersonation" to (R.string.analysis_action_impersonation_title to R.string.detail_verify),
    "threat_pressure" to (R.string.analysis_action_threat_title to R.string.analysis_action_threat_detail),
    "secrecy" to (R.string.analysis_action_secrecy_title to R.string.analysis_action_secrecy_detail),
    "information_probing" to (R.string.analysis_action_probing_title to R.string.analysis_action_probing_detail),
)

private fun detectedTypeLabel(type: String) = when (type) {
    "institution_impersonation" -> R.string.analysis_type_impersonation
    "money_transfer" -> R.string.analysis_type_transfer
    "personal_information" -> R.string.analysis_type_personal_information
    "app_installation" -> R.string.analysis_type_app
    "secrecy" -> R.string.analysis_type_secrecy
    "threat_pressure" -> R.string.analysis_type_threat
    "loan_fraud" -> R.string.analysis_type_loan
    "information_probing" -> R.string.analysis_type_probing
    else -> R.string.analysis_type_other
}

@Preview(name = "실시간 분석 · 경고", widthDp = 412, heightDp = 917, showBackground = true)
@Composable
private fun AnalysisLivePreview() {
    val risk = RiskResult(83.0, 76.0, "위험 · 송금 유도 의심", "ok", null, "ok",
        detectedTypes = setOf("money_transfer"))
    PicScreenTheme {
        AnalysisLiveScreen(SttState(phase = SttPhase.LISTENING, count = 2, risk = risk,
            maskedTexts = listOf("기관에서 계좌를 확인해야 하니 통화를 유지해 주세요.", "안전계좌로 돈을 이체해 주세요."),
            liveCards = LiveAnalysisCards().record(1, 48.0, null, false, 1_794_461_570_000L)
                .record(2, 76.0, risk.liveSignal(2), false, 1_794_461_580_000L),
            audioLevels = listOf(.3f, .5f, .8f, .45f, .7f, .55f, .4f, .8f, .6f)),
            onStop = {}, onHome = {})
    }
}
