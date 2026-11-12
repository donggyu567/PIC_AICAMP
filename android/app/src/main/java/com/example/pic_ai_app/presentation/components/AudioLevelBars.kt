package com.example.pic_ai_app.presentation.components

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.data.stt.AUDIO_LEVEL_BARS
import com.example.pic_ai_app.ui.theme.PicWhite

@Composable
internal fun AudioLevelBars(
    levels: List<Float>, modifier: Modifier = Modifier, barCount: Int = AUDIO_LEVEL_BARS,
    barWidth: Dp = 4.dp, gap: Dp = 4.dp, maxBarHeight: Dp = 38.dp, color: Color = PicWhite,
) {
    Row(modifier.height(40.dp), horizontalArrangement = Arrangement.spacedBy(gap, Alignment.CenterHorizontally),
        verticalAlignment = Alignment.CenterVertically) {
        repeat(barCount) { slot ->
            // Right-align new samples even before the history fills up.
            val level = levels.getOrNull(slot + levels.size - barCount) ?: 0f
            val displayLevel = ((level - 0.2f) / 0.6f).coerceIn(0f, 1f)
            val height by animateDpAsState(
                targetValue = 2.dp + (maxBarHeight - 2.dp) * displayLevel,
                animationSpec = tween(60),
                label = "음성 막대 높이",
            )
            val opacity = .35f + .65f * slot / (barCount - 1).coerceAtLeast(1)
            Spacer(Modifier.width(barWidth).height(height).background(color.copy(alpha = opacity), RoundedCornerShape(2.dp)))
        }
    }
}
