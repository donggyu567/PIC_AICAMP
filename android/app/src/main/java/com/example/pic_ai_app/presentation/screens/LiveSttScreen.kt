package com.example.pic_ai_app.presentation.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.presentation.components.*

@Composable
fun LiveSttScreen(state: SttState, onStop: () -> Unit, onHome: () -> Unit, onData: () -> Unit, onRetryFinish: () -> Unit, onRetryAnalysis: () -> Unit) {
    val active = state.phase in listOf(SttPhase.CONNECTING, SttPhase.LISTENING, SttPhase.FINALIZING)
    PicPage(title = stringResource(R.string.analysis_title), onBack = onHome) {
        SectionHeading(stringResource(R.string.analysis_title))
        if (state.phase == SttPhase.STOPPED && state.count > 0) {
            InfoCard("최종 분석 결과") {
                state.risk?.let { RiskSummary(it) }
            }
        }
        InfoCard(stringResource(R.string.processing_status)) {
            if (state.phase in listOf(SttPhase.CONNECTING, SttPhase.FINALIZING)) {
                CircularProgressIndicator(Modifier.size(24.dp))
            }
            BodyText(stringResource(when (state.phase) {
                SttPhase.IDLE -> R.string.stt_idle
                SttPhase.CONNECTING -> R.string.state_connecting
                SttPhase.LISTENING -> R.string.state_recognizing
                SttPhase.FINALIZING -> R.string.state_finalizing
                SttPhase.STOPPED -> R.string.stt_finished
                SttPhase.ERROR -> R.string.state_error
            }))
            BodyText(stringResource(R.string.confirmed_utterances, state.count))
            if (state.masking) BodyText("개인정보를 마스킹하고 있습니다.")
            state.maskedTexts.forEach { BodyText(it) }
            if (state.analyzing) BodyText("위험도를 분석하고 있습니다.")
            if (state.phase == SttPhase.STOPPED && state.count == 0) BodyText("분석할 발화가 없습니다.")
            if (state.phase != SttPhase.STOPPED) state.risk?.let { RiskSummary(it) }
            state.error?.let { BodyText(it) }
        }
        if (state.canRetryAnalysis) PrimaryAction("분석 결과 다시 확인", onRetryAnalysis)
        BodyText("확정 발화는 기기에서 마스킹한 뒤 표시합니다.")
        if (active) {
            PrimaryAction(stringResource(if (state.phase == SttPhase.FINALIZING) R.string.finalizing_button else R.string.stop_analysis),
                onStop, enabled = state.phase != SttPhase.FINALIZING)
            LinkAction(stringResource(R.string.data_guide_title), onData)
        } else {
            if (state.canRetryFinish) PrimaryAction("서버 종료 다시 시도", onRetryFinish)
            PrimaryAction(stringResource(R.string.home), onHome)
        }
    }
}

@Composable
private fun RiskSummary(risk: RiskResult) {
    risk.cumulativeScore?.let { BodyText("누적 위험도: %.1f점".format(it)) }
    risk.warningMessage?.let { BodyText(it) }
    risk.contextReason?.let { BodyText(it) }
    if (risk.contextStatus == "error") BodyText("문맥 판단을 완료하지 못했습니다.")
    if (risk.correctionStatus == "fallback") BodyText("발화 보정 없이 분석했습니다.")
}
