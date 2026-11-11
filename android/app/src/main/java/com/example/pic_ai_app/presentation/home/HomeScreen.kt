package com.example.pic_ai_app.presentation.home

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.BuildConfig
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.components.*
import com.example.pic_ai_app.presentation.components.navigation.PicNavigationBar
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.presentation.preview.Scenario
import com.example.pic_ai_app.presentation.screens.scenarioTitle
import com.example.pic_ai_app.ui.theme.PicHomeBlue
import com.example.pic_ai_app.ui.theme.PicScreenTheme
import kotlinx.coroutines.launch

@Composable
fun HomeScreen(
    scenario: Scenario, canStart: Boolean, deletionPending: Boolean,
    onStart: () -> Unit, onData: () -> Unit, onSettings: () -> Unit, onDeletion: () -> Unit,
    consentSaveFailed: Boolean = false, onRetryConsent: () -> Unit = {},
    liveMode: Boolean = false, serverUrl: String = "", onServerUrlChange: (String) -> Unit = {},
    tokenMessage: String? = null, onSaveToken: (String) -> Unit = {},
    activeSession: SttState? = null, onStop: () -> Unit = {}, onAnalysis: () -> Unit = {},
    analysisAvailable: Boolean = activeSession != null,
) {
    var showSettings by rememberSaveable { mutableStateOf(false) }
    val scroll = rememberScrollState()
    val scope = rememberCoroutineScope()
    Scaffold(
        containerColor = PicHomeBlue,
        bottomBar = {
            PicNavigationBar(
                selectedTab = PicTab.Home,
                availableTabs = if (analysisAvailable) setOf(PicTab.Home, PicTab.Analysis) else setOf(PicTab.Home),
                onTabSelected = { tab ->
                    if (tab == PicTab.Analysis) onAnalysis() else scope.launch { scroll.animateScrollTo(0) }
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
                if (activeSession == null) {
                    HomeStartScreen(viewport, canStart, onStart, onSettings = { showSettings = true })
                } else {
                    HomeActiveScreen(viewport, activeSession, onStop, onSettings = { showSettings = true })
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
    if (showSettings) {
        var tokenInput by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { showSettings = false },
            title = { Text(stringResource(R.string.home_settings)) },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    LinkAction(stringResource(R.string.data_guide_title), onClick = { showSettings = false; onData() })
                    if (liveMode && BuildConfig.DEBUG) {
                        OutlinedTextField(
                            value = serverUrl, onValueChange = onServerUrlChange,
                            label = { Text(stringResource(R.string.server_address)) },
                            singleLine = true, modifier = Modifier.fillMaxWidth(),
                        )
                        OutlinedTextField(
                            value = tokenInput, onValueChange = { tokenInput = it },
                            label = { Text(stringResource(R.string.home_device_token)) },
                            visualTransformation = PasswordVisualTransformation(),
                            singleLine = true, modifier = Modifier.fillMaxWidth(),
                        )
                        TextButton(onClick = { onSaveToken(tokenInput); tokenInput = "" }, enabled = tokenInput.isNotBlank()) {
                            Text(stringResource(R.string.home_save_token))
                        }
                        tokenMessage?.let { BodyText(it) }
                    }
                    if (!liveMode && BuildConfig.DEBUG) {
                        BodyText(stringResource(R.string.selected_preview, stringResource(scenarioTitle(scenario))))
                        LinkAction(stringResource(R.string.preview_settings), onClick = { showSettings = false; onSettings() })
                    } else if (!liveMode) BodyText(stringResource(R.string.analysis_unavailable))
                }
            },
            confirmButton = {
                TextButton(onClick = { showSettings = false }) { Text(stringResource(R.string.close)) }
            },
        )
    }
}

@Preview(name = "메인화면(분석시작)", showBackground = true, widthDp = 412, heightDp = 917)
@Preview(name = "작은 폰 · 360 × 800", showBackground = true, widthDp = 360, heightDp = 800)
@Preview(name = "큰 폰 · 480 × 1067", showBackground = true, widthDp = 480, heightDp = 1067)
@Composable
private fun HomeStartPreview() {
    PicScreenTheme {
        HomeScreen(Scenario.NORMAL, canStart = true, deletionPending = false,
            onStart = {}, onData = {}, onSettings = {}, onDeletion = {})
    }
}
