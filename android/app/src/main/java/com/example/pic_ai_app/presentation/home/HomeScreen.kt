package com.example.pic_ai_app.presentation.home

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.components.*
import com.example.pic_ai_app.presentation.components.navigation.PicNavigationBar
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.presentation.components.navigation.mainTabs
import com.example.pic_ai_app.ui.theme.PicHomeBlue
import com.example.pic_ai_app.ui.theme.PicScreenTheme
import kotlinx.coroutines.launch

@Composable
fun HomeScreen(
    canStart: Boolean, deletionPending: Boolean,
    onStart: () -> Unit, onSettings: () -> Unit, onDeletion: () -> Unit,
    consentSaveFailed: Boolean = false, onRetryConsent: () -> Unit = {},
    activeSession: SttState? = null, onStop: () -> Unit = {}, onAnalysis: () -> Unit = {},
    onHistory: () -> Unit = {},
    onReport: () -> Unit = {},
) {
    val scroll = rememberScrollState()
    val scope = rememberCoroutineScope()
    Scaffold(
        containerColor = PicHomeBlue,
        bottomBar = {
            PicNavigationBar(
                selectedTab = PicTab.Home,
                availableTabs = mainTabs,
                onTabSelected = { tab ->
                    when (tab) {
                        PicTab.Home -> { scope.launch { scroll.animateScrollTo(0) } }
                        PicTab.Analysis -> onAnalysis()
                        PicTab.History -> onHistory()
                        PicTab.Report -> onReport()
                    }
                },
            )
        },
    ) { padding ->
        BoxWithConstraints(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            val viewport = maxHeight
            Column(
                Modifier.widthIn(max = 480.dp).fillMaxWidth().verticalScroll(scroll)
                    .padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                PicHeader(onSettings = onSettings)
                if (activeSession == null) {
                    HomeStartScreen(viewport, canStart, onStart)
                } else {
                    HomeActiveScreen(viewport, activeSession, onStop)
                }
                if (consentSaveFailed) InfoCard(stringResource(R.string.consent_save_error_title), error = true) {
                    BodyText(stringResource(R.string.consent_save_error_body))
                    LinkAction(stringResource(R.string.retry_consent_save), onRetryConsent)
                }
                if (deletionPending) InfoCard(stringResource(R.string.deletion_before_restart)) {
                    LinkAction(stringResource(R.string.view_deletion_status), onDeletion)
                }
                Spacer(Modifier.height(16.dp))
            }
        }
    }
}

@Preview(name = "메인화면(분석시작)", showBackground = true, widthDp = 412, heightDp = 917)
@Preview(name = "작은 폰 · 360 × 800", showBackground = true, widthDp = 360, heightDp = 800)
@Preview(name = "큰 폰 · 480 × 1067", showBackground = true, widthDp = 480, heightDp = 1067)
@Composable
private fun HomeStartPreview() {
    PicScreenTheme {
        HomeScreen(canStart = true, deletionPending = false, onStart = {}, onSettings = {}, onDeletion = {})
    }
}
