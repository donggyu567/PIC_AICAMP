package com.example.pic_ai_app.ui.theme

import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalViewConfiguration
import androidx.compose.ui.platform.ViewConfiguration
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.DpSize
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
internal fun PicScreenTheme(content: @Composable () -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        if (maxWidth <= 0.dp || maxHeight <= 0.dp) return@BoxWithConstraints
        // Compare matching edges so rotating the phone keeps the same design scale.
        val shortSide = minOf(maxWidth, maxHeight)
        val longSide = maxOf(maxWidth, maxHeight)
        val scale = minOf(shortSide / 412.dp, longSide / 917.dp)
        val deviceDensity = LocalDensity.current
        val scaledDensity = remember(deviceDensity, scale) {
            Density(deviceDensity.density * scale, deviceDensity.fontScale)
        }

        // Keep touch targets at least as large as the device's unscaled minimum.
        val deviceConfig = LocalViewConfiguration.current
        val touchScale = minOf(1f, scale)
        val touchConfig = remember(deviceConfig, touchScale) {
            object : ViewConfiguration by deviceConfig {
                override val minimumTouchTargetSize = DpSize(
                    deviceConfig.minimumTouchTargetSize.width / touchScale,
                    deviceConfig.minimumTouchTargetSize.height / touchScale,
                )
            }
        }
        CompositionLocalProvider(
            LocalDensity provides scaledDensity,
            LocalViewConfiguration provides touchConfig,
            LocalMinimumInteractiveComponentSize provides (48.dp / touchScale),
        ) {
            PicTheme(content)
        }
    }
}

@Composable
fun PicTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = PicColors,
        typography = PicTypography,
        shapes = PicShapes,
        content = content,
    )
}
