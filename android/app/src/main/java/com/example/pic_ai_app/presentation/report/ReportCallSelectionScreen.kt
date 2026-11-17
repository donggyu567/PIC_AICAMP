package com.example.pic_ai_app.presentation.report

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.history.AnalysisRecord
import com.example.pic_ai_app.data.history.CallRecordTitle
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.analysis.bandFor
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.presentation.history.AnalysisSummaryContent
import com.example.pic_ai_app.ui.theme.*
import kotlin.math.roundToInt

@Composable
internal fun ReportCallSelectionScreen(
    records: List<AnalysisRecord>, selectedId: String?, onSelect: (AnalysisRecord) -> Unit,
    onNext: () -> Unit, onTabSelected: (PicTab) -> Unit, storageError: Boolean = false,
) {
    val selectedCall = records.firstOrNull { it.id == selectedId }
    val reportRecords = remember(records) {
        records.sortedWith(
            compareByDescending<AnalysisRecord> { record ->
                val score = record.result.risk?.cumulativeScore
                score?.takeIf { it.isFinite() }?.roundToInt()?.let(::bandFor)
            }.thenByDescending { it.endedAtMillis }
        )
    }
    ReportStepLayout(
        step = ReportStep.CallSelection, title = R.string.report_call_title, description = R.string.report_call_description,
        canContinue = selectedCall != null, onNext = onNext, onTabSelected = onTabSelected,
    ) {
        Spacer(Modifier.height(12.dp))
        HorizontalDivider(
            modifier = Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(horizontal = 24.dp),
            color = PicBorder,
        )
        Spacer(Modifier.height(8.dp))
        LazyColumn(
            Modifier.weight(1f).widthIn(max = 480.dp).fillMaxWidth().selectableGroup(),
            contentPadding = PaddingValues(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Surface(Modifier.padding(horizontal = 24.dp), shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFF8FAFC)) {
                    Text(stringResource(R.string.report_call_privacy), Modifier.fillMaxWidth().padding(14.dp),
                        color = PicMuted, fontSize = 14.sp, lineHeight = 20.sp)
                }
            }
            if (storageError) item {
                Text(stringResource(R.string.history_storage_error), Modifier.padding(horizontal = 24.dp), color = PicMuted)
            }
            if (records.isEmpty() && !storageError) item {
                Text(stringResource(R.string.report_call_empty), Modifier.padding(horizontal = 24.dp), color = PicMuted)
            }
            items(reportRecords, key = { it.id }) { record ->
                ReportCallCard(record, selected = record.id == selectedId, onSelect = { onSelect(record) })
            }
        }
    }
}

@Composable
private fun ReportCallCard(record: AnalysisRecord, selected: Boolean, onSelect: () -> Unit) {
    ReportRadioOption(selected, onSelect, Modifier.padding(horizontal = 24.dp)) {
        AnalysisSummaryContent(CallRecordTitle.from(record.result), record.result.risk?.cumulativeScore,
            record.endedAtMillis, Modifier.weight(1f))
    }
}

@Preview(name = "신고 01 · 통화 선택 화면", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun ReportCallSelectionPreview() {
    val records = listOf("계좌 보호를 이유로 송금을 요청한 통화" to 82.0, "대출 권유를 받은 통화" to 62.0,
        "인증번호를 요청한 통화" to 58.0).mapIndexed { index, (title, score) ->
        val risk = RiskResult(null, score, null, "not_run", null, null, title = title)
        AnalysisRecord(index.toString(), 1_794_461_520_000L - index * 86_400_000L, SttState(risk = risk))
    }
    PicScreenTheme { ReportCallSelectionScreen(records, records.firstOrNull()?.id, {}, {}, {}) }
}
