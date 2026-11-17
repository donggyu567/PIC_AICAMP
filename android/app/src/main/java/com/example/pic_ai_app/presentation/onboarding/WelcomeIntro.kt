package com.example.pic_ai_app.presentation.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicTheme

@Composable
internal fun WelcomeIntro(onContinue: () -> Unit) {
    val shadowRadius = with(LocalDensity.current) { 4.dp.toPx() }
    val messageStyle = TextStyle(
        color = Color.Black,
        fontSize = 35.sp,
        lineHeight = 50.sp,
        fontWeight = FontWeight.Bold,
    )
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White)
            .clickable(
                role = Role.Button,
                onClickLabel = stringResource(R.string.view_consent),
                onClick = onContinue,
            )
            .safeDrawingPadding()
            .padding(horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.weight(0.46f))
        Column {
            Row {
                Text(
                    text = stringResource(R.string.app_name),
                    modifier = Modifier.alignByBaseline(),
                    style = TextStyle(
                        color = Color.Black,
                        fontSize = 64.sp,
                        fontWeight = FontWeight.Bold,
                        shadow = Shadow(
                            color = Color.Black.copy(alpha = 0.25f),
                            offset = Offset(0f, shadowRadius),
                            blurRadius = shadowRadius,
                        ),
                    ),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = stringResource(R.string.welcome_suffix),
                    modifier = Modifier.alignByBaseline(),
                    style = messageStyle,
                )
            }
            Text(text = stringResource(R.string.welcome_message), style = messageStyle)
        }
        Spacer(Modifier.weight(0.40f))
        Text(
            text = stringResource(R.string.welcome_touch_hint),
            color = Color(0xFF919191),
            fontSize = 20.sp,
            fontWeight = FontWeight.Thin,
        )
        Spacer(Modifier.weight(0.14f))
    }
}

@Preview(
    name = "온보딩 시작 → 권한동의",
    showBackground = true,
    widthDp = 412,
    heightDp = 917,
)
@Composable
private fun WelcomeIntroPreview() {
    var showConsent by remember { mutableStateOf(false) }
    PicTheme {
        if (showConsent) {
            ConsentScreen(onRequestPermissions = {})
        } else {
            WelcomeIntro(onContinue = { showConsent = true })
        }
    }
}
