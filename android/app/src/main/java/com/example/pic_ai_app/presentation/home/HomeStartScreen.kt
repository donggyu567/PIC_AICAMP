package com.example.pic_ai_app.presentation.home

import androidx.annotation.StringRes
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.fromHtml
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicHomeBlue
import com.example.pic_ai_app.ui.theme.PicTheme
import com.example.pic_ai_app.ui.theme.PicWhite

@Composable
internal fun HomeStartScreen(viewport: Dp, canStart: Boolean, onStart: () -> Unit) {
    HomeGuide(viewport)
    Spacer(Modifier.height((viewport * .055f).coerceIn(20.dp, 45.dp)))
    HomeAnalysisButton(R.string.home_start_action, canStart, onStart)
}

@Composable
internal fun HomeGuide(viewport: Dp, cardGapReduction: Dp = 0.dp) {
    val cardTopGap = (viewport * .10f).coerceIn(20.dp, 84.dp) - cardGapReduction
    Spacer(Modifier.height(cardTopGap))
    Surface(
        modifier = Modifier.widthIn(max = 318.dp).fillMaxWidth(),
        shape = RoundedCornerShape(30.dp), color = Color(0xFFF2F7FC), shadowElevation = 4.dp,
    ) {
        Box(Modifier.heightIn(min = 431.dp), contentAlignment = Alignment.Center) {
            Box(Modifier.matchParentSize(), contentAlignment = Alignment.Center) {
                Image(painterResource(R.drawable.home_guide_art), contentDescription = null,
                    modifier = Modifier.width(188.dp).aspectRatio(188f / 348f).alpha(.07f).blur(6.dp))
            }
            Column(
                Modifier.padding(horizontal = 16.dp, vertical = 28.dp).widthIn(max = 240.dp).fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                GuideStep(R.string.home_step_start, R.string.home_step_start_body)
                GuideStep(R.string.home_step_analyze, R.string.home_step_analyze_body)
                GuideStep(R.string.home_step_result, R.string.home_step_result_body)
            }
        }
    }
}

@Composable
internal fun HomeAnalysisButton(@StringRes label: Int, enabled: Boolean, onClick: () -> Unit) {
    Button(
        onClick = onClick, enabled = enabled,
        modifier = Modifier.widthIn(max = 275.dp).fillMaxWidth().heightIn(min = 63.dp),
        colors = ButtonDefaults.buttonColors(containerColor = PicWhite, contentColor = PicHomeBlue),
        shape = RoundedCornerShape(15.dp), elevation = ButtonDefaults.buttonElevation(defaultElevation = 3.dp),
    ) {
        Text(stringResource(label), fontSize = 20.sp, fontWeight = FontWeight.ExtraBold)
    }
}

@Composable
private fun GuideStep(@StringRes title: Int, @StringRes body: Int) {
    Column {
        Text(stringResource(title), color = PicHomeBlue, fontSize = 20.sp, lineHeight = 35.sp,
            fontWeight = FontWeight.Bold)
        Text(AnnotatedString.fromHtml(stringResource(body)), color = PicHomeBlue,
            fontSize = 18.sp, lineHeight = 30.sp, letterSpacing = (-0.1).sp)
    }
}

@Preview(name = "홈 · 분석 시작 본문", widthDp = 412, heightDp = 820)
@Composable
private fun HomeStartContentPreview() {
    PicTheme {
        Column(
            modifier = Modifier.fillMaxSize()
                .background(PicHomeBlue)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            HomeStartScreen(
                viewport = 820.dp,
                canStart = true,
                onStart = {},
            )
        }
    }
}
