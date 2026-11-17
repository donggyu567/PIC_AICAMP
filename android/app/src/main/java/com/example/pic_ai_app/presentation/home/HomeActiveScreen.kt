package com.example.pic_ai_app.presentation.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.components.AudioLevelBars
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
