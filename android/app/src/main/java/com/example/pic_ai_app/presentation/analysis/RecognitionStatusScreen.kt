package com.example.pic_ai_app.presentation.analysis

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.ui.theme.PicScreenTheme

@Composable
internal fun RecognitionStatusScreen(state: SttState, onBack: () -> Unit) {
    val streaming = state.phase == SttPhase.LISTENING && state.audioLevels.isNotEmpty()
    val transfer = when {
        streaming -> R.string.live_stage_active
        state.phase == SttPhase.ERROR -> R.string.live_stage_interrupted
        state.phase == SttPhase.FINALIZING || state.phase == SttPhase.STOPPED -> R.string.live_stage_ended
        else -> R.string.live_stage_wait
    }
    val maskedCount = state.maskedTexts.size
    val protection = when {
        state.masking && maskedCount < state.count -> R.string.live_stage_active
        maskedCount > 0 && maskedCount == state.count -> R.string.live_stage_complete
        else -> R.string.live_stage_wait
    }
    RecognitionContent(state.audioLevels, onBack) {
        StatusCard(stringResource(R.string.live_transfer_stage, stringResource(transfer)),
            stringResource(if (streaming) R.string.live_streaming else R.string.live_transfer_description))
        StatusCard(stringResource(R.string.live_conversion_stage,
            stringResource(if (state.count > 0) R.string.live_stage_received else R.string.live_stage_wait)),
            if (state.count > 0) stringResource(R.string.live_received_count, state.count)
            else stringResource(R.string.live_waiting_recognition))
        StatusCard(stringResource(R.string.live_mask_stage, stringResource(protection)),
            stringResource(R.string.live_mask_description))
    }
}

@Composable
private fun RecognitionContent(levels: List<Float>, onBack: () -> Unit, cards: @Composable ColumnScope.() -> Unit) {
    AnalysisDetailLayout(stringResource(R.string.live_recognition), levels, onBack) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(top = 54.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(28.dp), content = cards)
    }
}

@Composable
private fun StatusCard(title: String, description: String) {
    AnalysisDetailCard {
        Column(Modifier.fillMaxWidth().heightIn(min = 112.dp).padding(20.dp),
            verticalArrangement = Arrangement.SpaceBetween) {
            Text(title, fontSize = 25.sp, lineHeight = 31.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(12.dp))
            Text(description, fontSize = 18.sp, lineHeight = 24.sp)
        }
    }
}

@Preview(name = "음성인식 상태 상세 · 피그마 예시", widthDp = 412, heightDp = 917, showBackground = true)
@Composable
private fun RecognitionStatusPreview() {
    PicScreenTheme {
        RecognitionContent(listOf(.35f, .55f, .8f, .45f, .7f, .4f, .65f, .8f, .5f), onBack = {}) {
            StatusCard("음성 전송 중(완료)", stringResource(R.string.live_streaming))
            StatusCard("음성 → 텍스트 변환중(진행중)", "ElevenLabs STT 처리중")
            StatusCard("개인정보 보호 처리 중(대기)", stringResource(R.string.live_mask_description))
        }
    }
}
