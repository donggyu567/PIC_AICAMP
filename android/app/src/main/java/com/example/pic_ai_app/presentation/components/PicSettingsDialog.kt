package com.example.pic_ai_app.presentation.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.BuildConfig
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.preview.Scenario
import com.example.pic_ai_app.presentation.screens.scenarioTitle

@Composable
internal fun PicSettingsDialog(
    onDismiss: () -> Unit, onData: () -> Unit,
    liveMode: Boolean, serverUrl: String, onServerUrlChange: (String) -> Unit,
    tokenMessage: String?, onSaveToken: (String) -> Unit,
    scenario: Scenario, onSettings: () -> Unit,
) {
    var tokenInput by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.home_settings)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                LinkAction(stringResource(R.string.data_guide_title), onClick = { onDismiss(); onData() })
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
                    LinkAction(stringResource(R.string.preview_settings), onClick = { onDismiss(); onSettings() })
                } else if (!liveMode) BodyText(stringResource(R.string.analysis_unavailable))
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.close)) }
        },
    )
}
