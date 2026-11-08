package com.example.pic_ai_app.presentation.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringArrayResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.BuildConfig
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.*
import com.example.pic_ai_app.presentation.preview.Scenario
import com.example.pic_ai_app.presentation.screens.FlowExplanation
import com.example.pic_ai_app.presentation.screens.scenarioTitle

@Composable
fun HomeScreen(
    scenario: Scenario, canStart: Boolean, deletionPending: Boolean,
    onStart: () -> Unit, onData: () -> Unit, onSettings: () -> Unit, onDeletion: () -> Unit,
    consentSaveFailed: Boolean = false, onRetryConsent: () -> Unit = {},
    liveMode: Boolean = false, serverUrl: String = "", onServerUrlChange: (String) -> Unit = {},
    tokenMessage: String? = null, onSaveToken: (String) -> Unit = {},
) {
    var tokenInput by remember { mutableStateOf("") }
    PicPage(
        title = stringResource(R.string.app_name),
        actions = { if (BuildConfig.DEBUG && !liveMode) TextButton(onClick = onSettings) { Text(stringResource(R.string.preview_settings)) } },
    ) {
        SectionHeading(stringResource(R.string.home_title))
        BodyText(stringResource(R.string.home_description))
        FlowExplanation()
        InfoCard(stringResource(R.string.usage_title)) {
            stringArrayResource(R.array.usage_notes).forEach { note -> BodyText("· $note") }
        }
        if (consentSaveFailed) InfoCard(stringResource(R.string.consent_save_error_title), error = true) {
            BodyText(stringResource(R.string.consent_save_error_body))
            LinkAction(stringResource(R.string.retry_consent_save), onRetryConsent)
        }
        if (liveMode && BuildConfig.DEBUG) {
            OutlinedTextField(
                value = serverUrl, onValueChange = onServerUrlChange,
                label = { Text(stringResource(R.string.server_address)) },
                singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
        }
        if (liveMode && BuildConfig.DEBUG) {
            OutlinedTextField(value = tokenInput, onValueChange = { tokenInput = it },
                label = { Text("기기 인증 정보") }, singleLine = true,
                visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
            TextButton(onClick = { onSaveToken(tokenInput); tokenInput = "" }, enabled = tokenInput.isNotBlank()) {
                Text("인증 정보 저장")
            }
            tokenMessage?.let { BodyText(it) }
        }
        PrimaryAction(stringResource(R.string.start_analysis), onStart, enabled = canStart)
        if (deletionPending) {
            BodyText(stringResource(R.string.deletion_before_restart))
            LinkAction(stringResource(R.string.view_deletion_status), onDeletion)
        }
        LinkAction(stringResource(R.string.data_guide_title), onData)
        if (BuildConfig.DEBUG && !liveMode) BodyText(stringResource(R.string.selected_preview, stringResource(scenarioTitle(scenario))), muted = true)
        else if (!liveMode) BodyText(stringResource(R.string.analysis_unavailable), muted = true)
    }
}
