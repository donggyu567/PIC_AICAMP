package com.example.pic_ai_app.presentation.report

import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.history.AnalysisRecord
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.PicScreenTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException

@Composable
internal fun ReportDamagePreparationScreen(call: AnalysisRecord, onTabSelected: (PicTab) -> Unit) {
    var party by rememberSaveable(call.id) { mutableStateOf("") }
    var whenWhere by rememberSaveable(call.id) { mutableStateOf("") }
    var damage by rememberSaveable(call.id) { mutableStateOf("") }
    var editedNarrative by rememberSaveable(call.id) { mutableStateOf<String?>(null) }
    val transcript = remember(call.result.maskedTexts) { call.result.maskedTexts.joinToString("\n") }
    val narrative = editedNarrative ?: transcript
    val partyLabel = stringResource(R.string.report_party)
    val whenWhereLabel = stringResource(R.string.report_when_where)
    val damageLabel = stringResource(R.string.report_damage)
    val narrativeLabel = stringResource(R.string.report_narrative)
    val docTitle = stringResource(R.string.report_pdf_title)
    fun documentText() = reportText(partyLabel to party, whenWhereLabel to whenWhere,
        damageLabel to damage, narrativeLabel to narrative)

    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var showPreview by rememberSaveable { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }
    val saveFile = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/pdf")) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        val text = documentText()
        saving = true
        scope.launch {
            try {
                withContext(Dispatchers.IO) {
                    val output = context.contentResolver.openOutputStream(uri, "wt")
                        ?: throw IOException("Document provider returned no output stream")
                    output.use { ReportDamagePdf(docTitle, text).writeTo(it) }
                }
                Toast.makeText(context, R.string.report_pdf_saved, Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                Toast.makeText(context, R.string.report_pdf_error, Toast.LENGTH_LONG).show()
            } finally {
                saving = false
            }
        }
    }
    val canExport = listOf(party, whenWhere, damage, narrative).any { it.isNotBlank() }
    var showGuidance by rememberSaveable(call.id) { mutableStateOf(false) }
    BackHandler(enabled = showGuidance) { showGuidance = false }
    if (showGuidance) {
        ReportDamageGuidanceScreen(documentText(), onTabSelected)
        return
    }
    ReportPreparationLayout(R.string.report_damage_title, R.string.report_damage_description, onTabSelected,
        onNext = { showGuidance = true },
        actions = {
            OutlinedButton(onClick = { showPreview = true }, enabled = canExport,
                modifier = Modifier.weight(1f), shape = RoundedCornerShape(12.dp)) {
                Text(stringResource(R.string.report_pdf_preview))
            }
            OutlinedButton(onClick = { saveFile.launch(context.getString(R.string.report_pdf_filename)) },
                enabled = canExport && !saving, modifier = Modifier.weight(1f), shape = RoundedCornerShape(12.dp)) {
                Text(stringResource(R.string.report_pdf_save))
            }
        },
    ) {
        ReportField(partyLabel, party, { party = it }, R.string.report_party_hint)
        ReportField(whenWhereLabel, whenWhere, { whenWhere = it }, R.string.report_when_where_hint)
        ReportField(damageLabel, damage, { damage = it }, R.string.report_damage_hint)
        ReportField(stringResource(R.string.report_editable, narrativeLabel), narrative, { editedNarrative = it },
            R.string.report_narrative_hint, R.string.report_masked_damage)
    }
    if (showPreview) {
        val text = documentText()
        val document = remember(docTitle, text) { ReportDamagePdf(docTitle, text) }
        ReportPdfPreview(document, onClose = { showPreview = false })
    }
}

@Preview(name = "신고 03B · 피해 경위 준비", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun ReportDamagePreparationPreview() {
    PicScreenTheme {
        ReportDamagePreparationScreen(AnalysisRecord("preview", 0L,
            SttState(maskedTexts = listOf("지정한 계좌로 이체해 주세요."))), {})
    }
}
