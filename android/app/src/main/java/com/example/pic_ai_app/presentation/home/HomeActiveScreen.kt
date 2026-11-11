package com.example.pic_ai_app.presentation.home

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.AUDIO_LEVEL_BARS
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.ui.theme.PicHomeBlue
import com.example.pic_ai_app.ui.theme.PicTheme
import com.example.pic_ai_app.ui.theme.PicWhite

@Composable
internal fun HomeActiveScreen(viewport: Dp, state: SttState, onStop: () -> Unit) {
    HomeGuide(viewport, cardGapReduction = 18.dp)
    Spacer(Modifier.height((viewport * .036f).coerceIn(16.dp, 30.dp)))
    AudioLevelBars(state.audioLevels)
    Spacer(Modifier.height(8.dp))
    val status = when {
        state.phase == SttPhase.CONNECTING -> R.string.state_connecting
        state.audioLevels.isEmpty() -> R.string.stt_idle
        else -> R.string.home_listening
    }
    Text(stringResource(status), color = PicWhite.copy(alpha = .8f),
        fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium)
    Spacer(Modifier.height((viewport * .04f).coerceIn(16.dp, 33.dp)))
    HomeAnalysisButton(R.string.stop_analysis, enabled = true, onClick = onStop)
}

@Composable
private fun AudioLevelBars(levels: List<Float>) {
    Row(Modifier.height(40.dp), horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        repeat(AUDIO_LEVEL_BARS) { slot ->
            // Right-align new samples even before the history fills up.
            val level = levels.getOrNull(slot + levels.size - AUDIO_LEVEL_BARS) ?: 0f
            val displayLevel = ((level - 0.2f) / 0.6f).coerceIn(0f, 1f)
            val height by animateDpAsState(
                targetValue = (2 + displayLevel * 36).dp,
                animationSpec = tween(60),
                label = "음성 막대 높이",
            )
            val opacity = .35f + .65f * slot / (AUDIO_LEVEL_BARS - 1)
            Spacer(Modifier.width(4.dp).height(height).background(PicWhite.copy(alpha = opacity), RoundedCornerShape(2.dp)))
        }
    }
}

@Preview(name = "홈 · 분석 중 본문", showBackground = true, widthDp = 412, heightDp = 820)
@Composable
private fun HomeActivePreview() {
    PicTheme {
        Column(
            modifier = Modifier.fillMaxSize().background(PicHomeBlue).padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            HomeActiveScreen(
                viewport = 820.dp,
                state = SttState(phase = SttPhase.LISTENING, audioLevels = listOf(
                    .2f, .55f, .9f, .4f, .8f, .3f, .65f, 1f, .55f, .2f, .4f, .8f, .3f, .65f, .9f, .55f, .2f,
                )),
                onStop = {},
            )
        }
    }
}
