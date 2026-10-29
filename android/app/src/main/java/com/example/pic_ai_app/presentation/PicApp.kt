package com.example.pic_ai_app.presentation

import android.Manifest
import android.content.Intent
import androidx.core.net.toUri
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
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
import com.example.pic_ai_app.presentation.components.*
import com.example.pic_ai_app.presentation.home.HomeScreen
import com.example.pic_ai_app.presentation.preview.*
import com.example.pic_ai_app.presentation.screens.*
import com.example.pic_ai_app.presentation.session.SessionViewModel
import com.example.pic_ai_app.ui.theme.PicTheme
import kotlinx.coroutines.delay

@Composable
fun PicApp(session: SessionViewModel) {
    val access by session.ui.collectAsStateWithLifecycle()
    val state = access.flow
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var stopDialog by rememberSaveable { mutableStateOf(false) }
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
    LaunchedEffect(state.hasOpenAnalysis, state.consented) {
        if (!state.hasOpenAnalysis) stopDialog = false
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
                Screen.ANALYSIS -> if (state.phase != Phase.FINALIZING) stopDialog = true
                Screen.WITHDRAWAL -> session.showHome()
                else -> session.back()
            }
        }
    }
    BackHandler(enabled = access.ready && state.screen !in listOf(Screen.WELCOME, Screen.HOME), onBack = back)

    if (!access.ready) {
        PicPage(title = stringResource(R.string.app_name)) {
            CircularProgressIndicator()
            BodyText(stringResource(R.string.loading_consent))
        }
        return
    }

    when (state.screen) {
        Screen.WELCOME -> WelcomeScreen(
            session::openConsent, session::openData, access.declined,
            withdrawn = access.consent == ConsentStatus.WITHDRAWN,
        )
        Screen.CONSENT -> ConsentScreen(
            onAgree = session::agree, onDecline = session::decline, onBack = back,
            saving = access.savingConsent, failed = access.consentError,
        )
        Screen.PERMISSION -> PermissionScreen(
            onAllow = {
                if (session.requestPermission()) permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            },
            onDeny = session::deferPermission, onBack = back,
            denied = access.permissionDenied, requesting = access.permissionRequestPending,
            onSettings = {
                context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    ("package:" + context.packageName).toUri()))
            },
        )
        Screen.HOME -> HomeScreen(
            scenario = state.scenario,
            canStart = BuildConfig.DEBUG && !access.savingConsent && access.pendingConsent == null &&
                state.deletion !in listOf(Deletion.DELETING, Deletion.PENDING),
            deletionPending = state.deletion in listOf(Deletion.DELETING, Deletion.PENDING),
            onStart = session::start, onData = session::openData,
            onSettings = { settingsDialog = true }, onDeletion = session::showDeletion,
            consentSaveFailed = access.consentError, onRetryConsent = session::retryConsent,
        )
        Screen.ANALYSIS, Screen.DETAILS -> AnalysisScreen(
            state, state.screen == Screen.DETAILS, onBack = back,
            onStop = { stopDialog = true }, onDetails = session::toggleDetails, onData = session::openData,
        )
        Screen.FINAL -> FinalScreen(
            state, onHome = session::showHome, onNew = session::start, onData = session::openData,
        )
        Screen.DATA -> DataScreen(
            state, onBack = back, onWithdraw = { withdrawDialog = true },
            onConsent = session::openConsent, onDeletion = session::showDeletion,
        )
        Screen.WITHDRAWAL -> WithdrawalScreen(
            state, onHome = session::showHome, onConsent = session::openConsent,
            onRetry = session::retryDeletion, onData = session::openData,
            savingConsent = access.savingConsent, consentFailed = access.consentError,
            onRetryConsent = session::retryConsent,
        )
    }

    if (stopDialog) {
        AlertDialog(
            onDismissRequest = { stopDialog = false },
            title = { Text(stringResource(R.string.stop_analysis)) },
            text = { Text(stringResource(R.string.stop_confirmation)) },
            confirmButton = {
                TextButton(onClick = { stopDialog = false; session.finish() }) { Text(stringResource(R.string.confirm_stop)) }
            },
            dismissButton = { TextButton(onClick = { stopDialog = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }
    if (withdrawDialog) {
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
    if (settingsDialog && BuildConfig.DEBUG) {
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
    PicTheme {
        HomeScreen(Scenario.NORMAL, canStart = false, deletionPending = false,
            onStart = {}, onData = {}, onSettings = {}, onDeletion = {})
    }
}
