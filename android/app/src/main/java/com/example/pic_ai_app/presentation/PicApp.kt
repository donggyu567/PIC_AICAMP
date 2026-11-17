package com.example.pic_ai_app.presentation

import android.Manifest
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.pic_ai_app.BuildConfig
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.consent.ConsentStatus
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.presentation.analysis.AnalysisIdleScreen
import com.example.pic_ai_app.presentation.analysis.AnalysisLiveScreen
import com.example.pic_ai_app.presentation.components.*
import com.example.pic_ai_app.presentation.home.HomeScreen
import com.example.pic_ai_app.presentation.history.HistoryScreen
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.presentation.onboarding.OnboardingPermissions
import com.example.pic_ai_app.presentation.onboarding.VoiceReconsentScreen
import com.example.pic_ai_app.presentation.preview.*
import com.example.pic_ai_app.presentation.screens.*
import com.example.pic_ai_app.presentation.result.AnalysisResultDetailScreen
import com.example.pic_ai_app.presentation.report.ReportCallSelectionScreen
import com.example.pic_ai_app.presentation.report.ReportDamagePreparationScreen
import com.example.pic_ai_app.presentation.report.ReportSituation
import com.example.pic_ai_app.presentation.report.ReportSituationScreen
import com.example.pic_ai_app.presentation.report.ReportTipPreparationScreen
import com.example.pic_ai_app.presentation.session.SessionViewModel
import com.example.pic_ai_app.presentation.settings.SettingsScreen
import com.example.pic_ai_app.presentation.settings.openPicSystemSettings
import com.example.pic_ai_app.presentation.settings.rememberNotificationsEnabled
import com.example.pic_ai_app.ui.theme.PicScreenTheme
import kotlinx.coroutines.delay

@Composable
fun PicApp(session: SessionViewModel) {
    val access by session.ui.collectAsStateWithLifecycle()
    val state = access.flow
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var withdrawDialog by rememberSaveable { mutableStateOf(false) }
    var settingsDialog by rememberSaveable { mutableStateOf(false) }
    var consentErrorDismissed by rememberSaveable { mutableStateOf(false) }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        session.permissionResult()
    }
    DisposableEffect(lifecycleOwner, session) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) session.refreshPermission()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // State lives in a ViewModel across rotation. Process restarts reload only consent,
    // never a permission grant or an in-flight analysis from a saved UI bundle.
    LaunchedEffect(state.consented) {
        if (!state.consented) withdrawDialog = false
    }
    LaunchedEffect(access.consentError) {
        if (!access.consentError) consentErrorDismissed = false
    }
    LaunchedEffect(access.ready, state.runId, state.phase, state.sampleCount, state.scenario,
        state.deletion, state.deletionAttempts, access.pendingConsent) {
        if (!BuildConfig.DEBUG || !access.ready || access.pendingConsent != null) return@LaunchedEffect
        val runId = state.runId
        val phase = state.phase
        if (state.deletion == Deletion.DELETING) {
            delay(1_600)
            session.completeDeletion(runId)
        } else {
            PreviewFlow.delayMillis(state)?.let { millis ->
                delay(millis)
                session.tick(runId, phase)
            }
        }
    }

    val back: () -> Unit = {
        if (!access.savingConsent) {
            when (state.screen) {
                Screen.ANALYSIS, Screen.DETAILS, Screen.FINAL, Screen.WITHDRAWAL -> session.showHome()
                else -> session.back()
            }
        }
    }
    val needsMicrophone = state.consented && !state.permissionGranted
    val screen = if (needsMicrophone) Screen.PERMISSION else state.screen
    BackHandler(enabled = access.ready && screen !in listOf(Screen.WELCOME, Screen.HOME, Screen.PERMISSION) &&
        (screen != Screen.VOICE_RECONSENT || access.savingConsent), onBack = back)

    if (!access.ready) {
        PicPage(title = stringResource(R.string.app_name)) {
            CircularProgressIndicator()
            BodyText(stringResource(R.string.loading_consent))
        }
        return
    }

    val capturingOrConnecting = access.stt.phase == SttPhase.CONNECTING || access.stt.phase == SttPhase.LISTENING
    val resultPending = access.stt.phase == SttPhase.FINALIZING || access.stt.canRetryFinish || access.stt.canRetryAnalysis
    val deletionPending = state.deletion in listOf(Deletion.DELETING, Deletion.PENDING)
    val canStart = !state.hasOpenAnalysis && !access.savingConsent && access.pendingConsent == null && !deletionPending
    val openTab: (PicTab) -> Unit = { tab ->
        when (tab) {
            PicTab.Home -> session.showHome()
            PicTab.Analysis -> if (resultPending) session.openResult() else session.openAnalysis()
            PicTab.History -> session.openHistory()
            PicTab.Report -> session.openReport()
        }
    }
    when (screen) {
        Screen.WELCOME -> WelcomeScreen(
            session::openConsent, session::openData, access.declined,
            withdrawn = access.consent == ConsentStatus.WITHDRAWN,
        )
        Screen.CONSENT -> OnboardingPermissions(access.savingConsent, session::agree)
        Screen.VOICE_RECONSENT -> VoiceReconsentScreen(
            deletion = state.deletion, savingConsent = access.savingConsent, consentError = access.consentError,
            notificationsOff = !rememberNotificationsEnabled(), onAgree = session::agree,
            onRetryDeletion = session::retryDeletion, onRetryConsent = session::retryConsent,
        )
        Screen.PERMISSION -> PermissionScreen(
            onAllow = {
                if (session.requestPermission()) permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            },
            denied = access.permissionDenied, requesting = access.permissionRequestPending,
            onSettings = { context.openPicSystemSettings() },
        )
        Screen.HOME -> Box(Modifier.fillMaxSize()) {
            val messages = remember { SnackbarHostState() }
            val completionText = stringResource(R.string.onboarding_permissions_granted)
            LaunchedEffect(Unit) {
                if (access.showOnboardingComplete) {
                    session.dismissOnboardingComplete()
                    messages.showSnackbar(completionText)
                }
            }
            HomeScreen(
                canStart = canStart, deletionPending = deletionPending,
                onStart = session::start, onSettings = session::openSettings, onDeletion = session::showDeletion,
                consentSaveFailed = access.consentError, onRetryConsent = session::retryConsent,
                activeSession = access.stt.takeIf { capturingOrConnecting },
                onStop = session::finishAndOpenResult,
                onAnalysis = if (resultPending) session::openResult else session::openAnalysis,
                onHistory = session::openHistory,
                onReport = session::openReport,
            )
            SnackbarHost(messages, Modifier.statusBarsPadding().padding(horizontal = 16.dp))
        }
        Screen.ANALYSIS, Screen.DETAILS -> {
            if (capturingOrConnecting) {
                AnalysisLiveScreen(
                    state = access.stt, onStop = session::finishAndOpenResult,
                    onHome = session::showHome,
                )
            } else {
                AnalysisIdleScreen(
                    riskCount = null, canStart = canStart,
                    onStart = session::start, onHome = session::showHome,
                    onSettings = session::openSettings,
                    onHistory = session::openHistory,
                    onReport = session::openReport,
                )
            }
        }
        Screen.SETTINGS -> {
            var developerSettings by rememberSaveable { mutableStateOf(false) }
            SettingsScreen(
                microphoneAllowed = state.permissionGranted, notificationsAllowed = rememberNotificationsEnabled(),
                onBack = back, onMicrophone = { context.openPicSystemSettings() },
                onNotifications = { context.openPicSystemSettings(notifications = true) },
                onData = session::openData,
                onDeveloper = if (BuildConfig.DEBUG) ({ developerSettings = true }) else null,
            )
            if (developerSettings && BuildConfig.DEBUG) {
                PicSettingsDialog(
                    onDismiss = { developerSettings = false }, onData = session::openData,
                    liveMode = true, serverUrl = access.serverUrl, onServerUrlChange = session::updateServerUrl,
                    tokenMessage = access.tokenMessage, onSaveToken = session::saveDeviceToken,
                    scenario = state.scenario, onSettings = { settingsDialog = true },
                )
            }
        }
        Screen.HISTORY -> {
            var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
            val listState = rememberLazyListState()
            val record = selectedId?.let { id -> access.records.find { it.id == id } }
            if (record == null) {
                HistoryScreen(
                    records = access.records, storageError = access.historyStorageError, listState = listState,
                    onOpenRecord = { selectedId = it }, onDeleteRecord = session::deleteRecord,
                    onTabSelected = openTab,
                )
            } else {
                val close = { selectedId = null }
                BackHandler(onBack = close)
                AnalysisResultDetailScreen(record.result, onBack = close, onRetryFinish = {}, onRetryAnalysis = {},
                    hasWarningHistory = record.hasWarningHistory)
            }
        }
        Screen.REPORT -> {
            val callSelectionState = rememberSaveableStateHolder()
            var situationCallId by rememberSaveable { mutableStateOf<String?>(null) }
            val call = situationCallId?.let { id -> access.records.find { it.id == id } }
            BackHandler(enabled = call != null) { situationCallId = null }
            if (call == null) {
                callSelectionState.SaveableStateProvider("call-selection") {
                    ReportCallSelectionScreen(
                        records = access.records, storageError = access.historyStorageError, onTabSelected = openTab,
                        onNext = { situationCallId = it },
                    )
                }
            } else {
                val stepState = rememberSaveableStateHolder()
                var preparationFor by rememberSaveable(call.id) { mutableStateOf<ReportSituation?>(null) }
                BackHandler(enabled = preparationFor != null) { preparationFor = null }
                when (preparationFor) {
                    null -> stepState.SaveableStateProvider("situation") {
                        ReportSituationScreen(
                            callId = call.id, onTabSelected = openTab,
                            onNext = { _, situation, _ -> preparationFor = situation },
                        )
                    }
                    ReportSituation.SuspiciousCallOnly -> stepState.SaveableStateProvider("tip") {
                        ReportTipPreparationScreen(call, openTab)
                    }
                    ReportSituation.MoneyOrInfoShared -> stepState.SaveableStateProvider("damage") {
                        ReportDamagePreparationScreen(call, openTab)
                    }
                }
            }
        }
        Screen.FINAL -> AnalysisResultDetailScreen(
            state = access.stt, permissionLost = state.error == PreviewError.PERMISSION,
            onBack = session::showHome, onRetryFinish = session::retryFinish, onRetryAnalysis = session::retryAnalysis,
        )
        Screen.DATA -> DataScreen(
            state, onBack = back, onWithdraw = { withdrawDialog = true },
            onConsent = session::openConsent, onDeletion = session::showDeletion,
        )
        Screen.WITHDRAWAL -> WithdrawalScreen(
            state, onHome = session::showHome, onConsent = session::openConsent,
            onRetry = session::retryDeletion, onData = session::openData,
            savingConsent = access.savingConsent, consentFailed = access.consentError,
            onRetryConsent = session::retryConsent, deletionRetryAvailable = session.deletionRetryAvailable,
        )
    }

    if (withdrawDialog && !needsMicrophone) {
        AlertDialog(
            onDismissRequest = { withdrawDialog = false },
            title = { Text(stringResource(R.string.withdrawal_confirm_title)) },
            text = { Text(stringResource(R.string.withdrawal_confirm_body)) },
            confirmButton = {
                TextButton(onClick = { withdrawDialog = false; session.withdraw() }) { Text(stringResource(R.string.confirm_withdraw)) }
            },
            dismissButton = { TextButton(onClick = { withdrawDialog = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }
    if (access.consentError && !consentErrorDismissed) {
        AlertDialog(
            onDismissRequest = { consentErrorDismissed = true },
            title = { Text(stringResource(R.string.consent_save_error_title)) },
            text = { Text(stringResource(R.string.consent_save_error_body)) },
            confirmButton = {
                TextButton(onClick = session::retryConsent) { Text(stringResource(R.string.retry_consent_save)) }
            },
            dismissButton = {
                TextButton(onClick = { consentErrorDismissed = true }) { Text(stringResource(R.string.close)) }
            },
        )
    }
    if (settingsDialog && screen == Screen.SETTINGS && BuildConfig.DEBUG) {
        AlertDialog(
            onDismissRequest = { settingsDialog = false },
            title = { Text(stringResource(R.string.preview_settings)) },
            text = {
                Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                    Text(stringResource(R.string.preview_settings_description), style = MaterialTheme.typography.bodySmall)
                    Scenario.entries.forEach { scenario ->
                        Row(
                            modifier = Modifier.fillMaxWidth().selectable(
                                selected = state.scenario == scenario, role = Role.RadioButton,
                                onClick = { session.selectScenario(scenario); settingsDialog = false },
                            ).padding(vertical = 4.dp),
                        ) {
                            RadioButton(selected = state.scenario == scenario, onClick = null)
                            Text(stringResource(scenarioTitle(scenario)), Modifier.padding(top = 12.dp))
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { settingsDialog = false }) { Text(stringResource(R.string.close)) } },
        )
    }
}

@Preview(showBackground = true, widthDp = 390, heightDp = 844)
@Composable
private fun PicAppPreview() {
    PicScreenTheme {
        HomeScreen(canStart = false, deletionPending = false, onStart = {}, onSettings = {}, onDeletion = {})
    }
}
