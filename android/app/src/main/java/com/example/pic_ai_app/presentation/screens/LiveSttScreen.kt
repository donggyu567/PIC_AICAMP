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
import com.example.pic_ai_app.presentation.components.*

@Composable
fun LiveSttScreen(state: SttState, onStop: () -> Unit, onHome: () -> Unit, onData: () -> Unit) {
    val active = state.phase in listOf(SttPhase.CONNECTING, SttPhase.LISTENING, SttPhase.FINALIZING)
    PicPage(title = stringResource(R.string.analysis_title), onBack = if (active) onStop else onHome) {
        SectionHeading(stringResource(R.string.analysis_title))
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
            state.error?.let { BodyText(it) }
        }
        BodyText(stringResource(R.string.stt_privacy_notice))
        if (active) {
            PrimaryAction(stringResource(if (state.phase == SttPhase.FINALIZING) R.string.finalizing_button else R.string.stop_analysis),
                onStop, enabled = state.phase != SttPhase.FINALIZING)
            LinkAction(stringResource(R.string.data_guide_title), onData)
        } else {
            PrimaryAction(stringResource(R.string.home), onHome)
        }
    }
}
