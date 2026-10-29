package com.example.pic_ai_app.presentation.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.BuildConfig
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.preview.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PicPage(
    title: String,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    footer: (@Composable ColumnScope.() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Scaffold(
        topBar = {
            Column {
                CenterAlignedTopAppBar(
                    title = { Text(title, style = MaterialTheme.typography.titleMedium) },
                    navigationIcon = {
                        if (onBack != null) {
                            val backLabel = stringResource(R.string.back)
                            TextButton(onClick = onBack, modifier = Modifier.semantics { contentDescription = backLabel }) {
                                Text("‹", fontSize = 28.sp)
                            }
                        }
                    },
                    actions = actions,
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface),
                )
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                if (BuildConfig.DEBUG) {
                    Surface(color = MaterialTheme.colorScheme.surfaceContainerLow) {
                        Text(
                            stringResource(R.string.preview_banner),
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        },
        bottomBar = {
            if (footer != null) {
                Surface(color = MaterialTheme.colorScheme.surface) {
                    Column(
                        modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 24.dp, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) { footer() }
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            content = content,
        )
    }
}

@Composable
fun InfoCard(
    title: String,
    error: Boolean = false,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = if (error) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceContainerLow,
        shape = MaterialTheme.shapes.small,
        border = BorderStroke(1.dp, if (error) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Column(verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
        }
    }
}

@Composable
fun PrimaryAction(text: String, onClick: () -> Unit, enabled: Boolean = true, fill: Boolean = false) {
    Button(
        onClick = onClick, enabled = enabled, shape = MaterialTheme.shapes.small,
        modifier = (if (fill) Modifier.fillMaxWidth() else Modifier).heightIn(min = 48.dp),
    ) { Text(text) }
}

@Composable
fun SecondaryAction(text: String, onClick: () -> Unit, enabled: Boolean = true) {
    OutlinedButton(
        onClick = onClick, enabled = enabled, shape = MaterialTheme.shapes.small,
        modifier = Modifier.heightIn(min = 48.dp),
    ) { Text(text) }
}

@Composable
fun LinkAction(text: String, onClick: () -> Unit, enabled: Boolean = true) {
    TextButton(
        onClick = onClick, enabled = enabled,
        contentPadding = PaddingValues(horizontal = 0.dp),
        modifier = Modifier.heightIn(min = 48.dp),
    ) { Text(text, textDecoration = TextDecoration.Underline) }
}

@Composable
fun BodyText(text: String, muted: Boolean = false) {
    Text(text, style = MaterialTheme.typography.bodySmall,
        color = if (muted) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
}

@Composable
fun SectionHeading(title: String) {
    Text(title, style = MaterialTheme.typography.headlineSmall)
}

@Composable
fun DevelopmentNotice() {
    InfoCard(stringResource(R.string.development_notice_title)) {
        BodyText(stringResource(R.string.development_notice_body))
    }
}

@Composable
fun RiskCard(state: PreviewState, final: Boolean = false) {
    val result = state.result
    val label = when {
        state.phase == Phase.INCOMPLETE -> R.string.last_success_score
        final -> R.string.final_risk_score
        else -> R.string.current_risk_score
    }
    InfoCard(stringResource(label)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(result?.score?.toString() ?: "—", fontSize = 28.sp, fontWeight = FontWeight.Bold)
            if (result != null) {
                Surface(color = MaterialTheme.colorScheme.primary, shape = MaterialTheme.shapes.extraLarge) {
                    Text(result.level, modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.labelLarge)
                }
            }
        }
        BodyText(stringResource(when {
            state.phase == Phase.INCOMPLETE -> R.string.incomplete_score_description
            result == null && final -> R.string.no_result_final
            result == null -> R.string.no_result_yet
            final -> R.string.final_result_description
            else -> R.string.live_result_description
        }))
    }
}

@Composable
fun WarningList(state: PreviewState, final: Boolean = false) {
    InfoCard(stringResource(if (final) R.string.warning_summary else R.string.current_warnings)) {
        if (state.samples.isEmpty()) BodyText(stringResource(R.string.no_warning_yet), muted = true)
        else state.samples.map { it.warning }.distinct().forEach { warning ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("⚠", style = MaterialTheme.typography.bodySmall)
                BodyText(warning)
            }
        }
    }
}

@Composable
fun EvidenceList(state: PreviewState, final: Boolean = false) {
    InfoCard(stringResource(if (final) R.string.evidence_summary else R.string.current_evidence)) {
        if (state.samples.isEmpty()) BodyText(stringResource(R.string.no_evidence_yet), muted = true)
        else state.samples.forEach { sample -> BodyText(sample.reason) }
    }
}

@Composable
fun TranscriptList(state: PreviewState) {
    InfoCard(stringResource(R.string.masked_transcripts)) {
        if (state.samples.isEmpty()) BodyText(stringResource(R.string.no_transcript_yet), muted = true)
        else state.samples.forEachIndexed { index, sample ->
            if (index > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            BodyText(sample.maskedText)
        }
    }
}

@Composable
fun ProgressCard(state: PreviewState) {
    InfoCard(stringResource(R.string.processing_status)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (state.busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            BodyText(stringResource(when (state.phase) {
                Phase.CONNECTING -> R.string.state_connecting
                Phase.RECOGNIZING -> R.string.state_recognizing
                Phase.MASKING -> R.string.state_masking
                Phase.ANALYZING -> R.string.state_analyzing
                Phase.FINALIZING -> R.string.state_finalizing
                Phase.ERROR -> R.string.state_error
                else -> R.string.state_listening
            }))
        }
        if (state.phase != Phase.FINALIZING) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(R.string.step_audio, R.string.step_stt, R.string.step_masking, R.string.step_analysis).forEach { label ->
                    Surface(
                        modifier = Modifier.weight(1f),
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                        shape = MaterialTheme.shapes.small,
                    ) { Text(stringResource(label), modifier = Modifier.padding(6.dp), style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
        BodyText(stringResource(R.string.confirmed_utterances, state.sampleCount), muted = true)
    }
}

@Composable
fun ProcessingError(error: PreviewError) {
    InfoCard(stringResource(R.string.processing_error), error = true) {
        BodyText(stringResource(when (error) {
            PreviewError.CONNECTION -> R.string.connection_error
            PreviewError.STT -> R.string.stt_error
            PreviewError.MASKING -> R.string.masking_error
            PreviewError.ANALYSIS -> R.string.analysis_error
            PreviewError.PERMISSION -> R.string.permission_revoked
        }))
        BodyText(stringResource(R.string.error_preserve_result))
    }
}
