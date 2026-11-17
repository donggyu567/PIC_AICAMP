package com.example.pic_ai_app.presentation.history

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.history.AnalysisRecord
import com.example.pic_ai_app.data.history.CallRecordTitle
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.components.PicHistoryHeader
import com.example.pic_ai_app.presentation.components.navigation.PicNavigationBar
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.presentation.components.navigation.mainTabs
import com.example.pic_ai_app.ui.theme.*

@Composable
internal fun HistoryScreen(
    records: List<AnalysisRecord>, onOpenRecord: (String) -> Unit, onDeleteRecord: (String) -> Unit,
    onTabSelected: (PicTab) -> Unit, storageError: Boolean = false,
    listState: LazyListState = rememberLazyListState(),
) {
    Scaffold(
        containerColor = PicWhite,
        bottomBar = { PicNavigationBar(PicTab.History, onTabSelected, mainTabs) },
    ) { insets ->
        Column(Modifier.fillMaxSize().padding(insets), horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(horizontal = 24.dp)) {
                PicHistoryHeader()
            }
            Spacer(Modifier.height(12.dp))
            HorizontalDivider(color = PicBorder)
            LazyColumn(
                modifier = Modifier.weight(1f).widthIn(max = 480.dp).fillMaxWidth(),
                state = listState,
                contentPadding = PaddingValues(horizontal = 34.dp, vertical = 14.dp),
                verticalArrangement = Arrangement.spacedBy(20.dp),
            ) {
                if (storageError) item { Text(stringResource(R.string.history_storage_error), color = PicMuted) }
                if (records.isEmpty()) {
                    item { Text(stringResource(R.string.history_empty), color = PicMuted) }
                } else {
                    item { Text(stringResource(R.string.history_delete_hint), color = PicMuted, fontSize = 12.sp) }
                }
                items(records, key = { it.id }) { record ->
                    AnalysisResultSummaryCard(
                        title = CallRecordTitle.from(record.result),
                        cumulativeScore = record.result.risk?.cumulativeScore, endedAtMillis = record.endedAtMillis,
                        onOpen = { onOpenRecord(record.id) }, onDelete = { onDeleteRecord(record.id) },
                    )
                }
            }
        }
    }
}

@Preview(name = "PIC 기록", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun HistoryScreenPreview() {
    val records = listOf("계좌 보호를 이유로 송금을 요청한 통화" to 82.0, "주말 약속 시간을 정한 통화" to 0.0)
        .mapIndexed { index, (title, score) ->
            val risk = RiskResult(null, score, null, "not_run", null, null, title = title)
            AnalysisRecord(index.toString(), 1_794_461_520_000L - index * 86_400_000L,
                SttState(phase = SttPhase.STOPPED, risk = risk))
        }
    PicScreenTheme { HistoryScreen(records, {}, {}, {}) }
}
