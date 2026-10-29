package com.example.pic_ai_app.presentation.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
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
) {
    PicPage(
        title = stringResource(R.string.app_name),
        actions = { if (BuildConfig.DEBUG) TextButton(onClick = onSettings) { Text(stringResource(R.string.preview_settings)) } },
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
        PrimaryAction(stringResource(R.string.start_analysis), onStart, enabled = canStart)
        if (deletionPending) {
            BodyText(stringResource(R.string.deletion_before_restart))
            LinkAction(stringResource(R.string.view_deletion_status), onDeletion)
        }
        LinkAction(stringResource(R.string.data_guide_title), onData)
        if (BuildConfig.DEBUG) BodyText(stringResource(R.string.selected_preview, stringResource(scenarioTitle(scenario))), muted = true)
        else BodyText(stringResource(R.string.analysis_unavailable), muted = true)
    }
}
