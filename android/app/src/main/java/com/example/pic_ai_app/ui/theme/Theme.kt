package com.example.pic_ai_app.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp

private val PicColors = lightColorScheme(
    primary = PicInk,
    onPrimary = PicWhite,
    secondary = PicMuted,
    onSecondary = PicWhite,
    background = PicWhite,
    onBackground = PicInk,
    surface = PicWhite,
    onSurface = PicInk,
    surfaceContainerLow = PicCard,
    onSurfaceVariant = PicMuted,
    outline = PicMuted,
    outlineVariant = PicBorder,
)

private val PicShapes = Shapes(
    small = RoundedCornerShape(6.dp),
    medium = RoundedCornerShape(6.dp),
    large = RoundedCornerShape(12.dp),
)

@Composable
fun PicTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = PicColors,
        typography = PicTypography,
        shapes = PicShapes,
        content = content,
    )
}
