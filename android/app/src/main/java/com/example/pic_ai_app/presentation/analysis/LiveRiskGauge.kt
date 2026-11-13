package com.example.pic_ai_app.presentation.analysis

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicMuted
import com.example.pic_ai_app.ui.theme.PicWhite
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

internal enum class RiskBand(val label: Int, val arc: Color, val ink: Color = arc) {
    Normal(R.string.live_normal, Color(0xFF248357)),
    Suspect(R.string.live_suspect, Color(0xFFA3BD38), Color(0xFF5A691A)),
    Caution(R.string.live_caution, Color(0xFFF3C735), Color(0xFF796000)),
    Danger(R.string.live_danger, Color(0xFFC33138)),
}

internal fun bandFor(points: Int) = when (points) {
    in 0..30 -> RiskBand.Normal
    in 31..50 -> RiskBand.Suspect
    in 51..70 -> RiskBand.Caution
    else -> RiskBand.Danger
}

@Composable
internal fun LiveRiskGauge(score: Double?) {
    val target = score?.takeIf { it.isFinite() }?.coerceIn(0.0, 100.0)?.toFloat()
    val preview = LocalInspectionMode.current
    val progress = remember { Animatable(if (preview) target ?: 0f else 0f) }
    LaunchedEffect(target) {
        if (target == null) progress.snapTo(0f)
        else progress.animateTo(target, tween(650, easing = FastOutSlowInEasing))
    }
    val points = progress.value.roundToInt()
    val band = bandFor(points)
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.widthIn(max = 242.dp).fillMaxWidth().aspectRatio(1.9f)) {
            Canvas(Modifier.fillMaxSize()) {
                val radius = minOf(size.width / 2, size.height) - 10.dp.toPx()
                if (radius <= 0f) return@Canvas
                val center = Offset(size.width / 2, size.height - 6.dp.toPx())
                val corner = Offset(center.x - radius, center.y - radius)
                val bounds = Size(radius * 2, radius * 2)
                val stroke = Stroke(width = 10.dp.toPx(), cap = StrokeCap.Round)
                drawArc(Color(0xFFE7EDF2), 180f, 180f, false, corner, bounds, style = stroke)
                if (target != null) {
                    val sweep = 180f * progress.value / 100f
                    drawArc(band.arc, 180f, sweep, false, corner, bounds, style = stroke)
                    val angle = (180.0 + sweep) * PI / 180.0
                    val tip = Offset(center.x + radius * cos(angle).toFloat(), center.y + radius * sin(angle).toFloat())
                    drawCircle(band.arc, 9.dp.toPx(), tip)
                    drawCircle(PicWhite, 4.dp.toPx(), tip)
                }
            }
            Column(Modifier.align(Alignment.BottomCenter).padding(bottom = 4.dp),
                horizontalAlignment = Alignment.CenterHorizontally) {
                if (target == null) {
                    Text(stringResource(R.string.live_waiting_score), color = PicMuted, fontSize = 20.sp)
                } else {
                    Text(stringResource(R.string.live_points, points), color = band.ink,
                        fontSize = 36.sp, lineHeight = 42.sp, fontWeight = FontWeight.Bold)
                    Text(stringResource(band.label), color = band.ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                }
            }
        }
        Row(Modifier.widthIn(max = 242.dp).fillMaxWidth().padding(top = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween) {
            Text(stringResource(R.string.live_points, 0), color = PicMuted, fontSize = 14.sp)
            Text(stringResource(R.string.live_points, 100), color = PicMuted, fontSize = 14.sp)
        }
    }
}
