package com.example.pic_ai_app.presentation.analysis

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.PicHeader
import com.example.pic_ai_app.presentation.components.navigation.PicNavigationBar
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.PicHomeBlue
import com.example.pic_ai_app.ui.theme.PicNavigationSelected
import com.example.pic_ai_app.ui.theme.PicScreenTheme
import com.example.pic_ai_app.ui.theme.PicWhite

private val cardColor = Color(0xFFF2F7FC)

@Composable
internal fun AnalysisIdleScreen(
    riskCount: Int?, canStart: Boolean, onStart: () -> Unit, onHome: () -> Unit, onSettings: () -> Unit,
) {
    Scaffold(
        containerColor = PicHomeBlue,
        bottomBar = {
            PicNavigationBar(
                selectedTab = PicTab.Analysis,
                availableTabs = setOf(PicTab.Home, PicTab.Analysis),
                onTabSelected = { if (it == PicTab.Home) onHome() },
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(horizontal = 24.dp)) {
                PicHeader(onSettings)
            }
            Column(
                Modifier.widthIn(max = 431.dp).fillMaxWidth().padding(horizontal = 36.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Spacer(Modifier.height(15.dp))
                RiskCountCard(riskCount)
                Spacer(Modifier.height(15.dp))
                WaitingCard()
                Spacer(Modifier.height(20.dp))
                Button(
                    onClick = onStart, enabled = canStart,
                    modifier = Modifier.widthIn(max = 284.dp).fillMaxWidth().heightIn(min = 64.dp),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = PicNavigationSelected, contentColor = PicWhite),
                ) {
                    Text(stringResource(R.string.home_start_action), fontSize = 22.sp, fontWeight = FontWeight.ExtraBold)
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}

@Composable
private fun RiskCountCard(riskCount: Int?) {
    Surface(
        modifier = Modifier.fillMaxWidth().heightIn(min = 169.dp),
        shape = RoundedCornerShape(20.dp), color = cardColor, contentColor = PicNavigationSelected,
        shadowElevation = 3.dp,
    ) {
        Column(Modifier.padding(24.dp)) {
            Text(stringResource(R.string.analysis_idle_count_title), fontSize = 20.sp,
                lineHeight = 24.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(9.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val displayedCount = riskCount ?: 0
                Text(
                    stringResource(R.string.analysis_idle_count, displayedCount),
                    modifier = Modifier.alignByBaseline(),
                    fontSize = 35.sp, lineHeight = 44.sp, color = PicHomeBlue,
                )
                Text(stringResource(R.string.analysis_idle_count_caption), Modifier.alignByBaseline(),
                    fontSize = 15.sp, color = PicHomeBlue)
            }
            Text(stringResource(R.string.analysis_idle_count_note), fontSize = 17.sp,
                lineHeight = 22.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
private fun WaitingCard() {
    Surface(
        modifier = Modifier.fillMaxWidth().heightIn(min = 377.dp),
        shape = RoundedCornerShape(30.dp), color = cardColor, contentColor = PicNavigationSelected,
        shadowElevation = 3.dp,
    ) {
        Column(Modifier.padding(horizontal = 28.dp, vertical = 20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Image(painterResource(R.drawable.ic_analysis_idle), contentDescription = null, modifier = Modifier.size(32.dp))
                Text(stringResource(R.string.analysis_idle_title), fontSize = 26.sp,
                    lineHeight = 34.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(20.dp))
            Text(stringResource(R.string.analysis_idle_description), fontSize = 18.sp,
                lineHeight = 28.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(11.dp))
            Text(stringResource(R.string.analysis_idle_guide_title), fontSize = 18.sp,
                lineHeight = 24.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(12.dp))
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                stringArrayResource(R.array.analysis_idle_guide).forEach { line ->
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Image(painterResource(R.drawable.ic_analysis_bullet), contentDescription = null,
                            modifier = Modifier.size(6.dp))
                        Text(line, fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.Medium)
                    }
                }
            }
        }
    }
}

@Preview(name = "분석 대기 · 피그마 기준", widthDp = 412, heightDp = 917, showBackground = true)
@Composable
private fun AnalysisIdlePreview() {
    PicScreenTheme { AnalysisIdleScreen(riskCount = 0, canStart = true, onStart = {}, onHome = {}, onSettings = {}) }
}
