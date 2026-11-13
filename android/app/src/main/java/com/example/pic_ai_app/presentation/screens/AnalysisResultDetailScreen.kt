package com.example.pic_ai_app.presentation.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.analysis.bandFor
import com.example.pic_ai_app.ui.theme.PicInk
import com.example.pic_ai_app.ui.theme.PicScreenTheme
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone
import kotlin.math.roundToInt

private val panel = Color(0xFFF8FAFC)
private val edge = Color(0xFFE2E8F0)
private val secondary = Color(0xFF64748B)
private val danger = Color(0xFF991B1B)

@Composable
fun AnalysisResultDetailScreen(
    state: SttState, onBack: () -> Unit, onRetryFinish: () -> Unit, onRetryAnalysis: () -> Unit,
    permissionLost: Boolean = false,
) {
    val risk = state.risk
    val points = risk?.cumulativeScore?.roundToInt()
    val band = points?.let(::bandFor)
    val warningMessage = risk?.analysisWarning?.takeIf { it.isNotBlank() }
        ?: risk?.warningMessage?.takeIf { it.isNotBlank() }
    val warningTitle = warningMessage ?: stringResource(R.string.no_warning_yet)
    val warningReason = risk?.contextReason?.takeIf { warningMessage != null && it.isNotBlank() }
    val finished = state.phase == SttPhase.STOPPED
    val waiting = state.phase == SttPhase.FINALIZING && state.error == null
    val title = risk?.riskTypes.orEmpty().distinct().mapNotNull { type ->
        when (type) {
            "institution_impersonation" -> stringResource(R.string.detail_institution)
            "money_transfer" -> stringResource(R.string.detail_transfer)
            else -> null
        }
    }.joinToString(" · ").ifEmpty { stringResource(R.string.final_title) }
    var showWarning by rememberSaveable { mutableStateOf(false) }
    var showChat by rememberSaveable { mutableStateOf(false) }
    Surface(color = Color.White, contentColor = PicInk, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.safeDrawingPadding(), horizontalAlignment = Alignment.CenterHorizontally) {
            Row(Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) {
                    Icon(painterResource(R.drawable.result_back), stringResource(R.string.back), Modifier.rotate(180f))
                }
                Text(title, fontSize = 25.sp, fontWeight = FontWeight.ExtraBold)
            }
            Column(
                Modifier.widthIn(max = 480.dp).fillMaxWidth().verticalScroll(rememberScrollState())
                    .padding(horizontal = 24.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (waiting || permissionLost || state.error != null || risk?.analysisIncomplete == true ||
                    (finished && state.count == 0)) {
                    ResultPanel {
                        if (waiting) LinearProgressIndicator(Modifier.fillMaxWidth())
                        Text(state.error ?: stringResource(when {
                            permissionLost -> R.string.detail_permission
                            waiting -> R.string.finalizing_title
                            risk?.analysisIncomplete == true -> R.string.incomplete_title
                            else -> R.string.no_result_final
                        }))
                        if (state.canRetryAnalysis) TextButton(onClick = onRetryAnalysis) {
                            Text(stringResource(R.string.detail_retry_analysis))
                        }
                        if (state.canRetryFinish) TextButton(onClick = onRetryFinish) {
                            Text(stringResource(R.string.detail_retry_finish))
                        }
                    }
                }
                ResultPanel {
                    Row(verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        val scoreLabel = if (points == null || (finished && risk?.analysisIncomplete != true))
                            R.string.detail_score else R.string.last_success_score
                        Text(stringResource(scoreLabel), Modifier.weight(1f), color = secondary)
                        Text(stringResource(R.string.live_points, points ?: 0), fontSize = 25.sp,
                            fontWeight = FontWeight.ExtraBold, color = band?.ink ?: PicInk)
                        if (band != null) Surface(shape = CircleShape, color = band.arc.copy(alpha = .14f)) {
                            Text(stringResource(band.label), Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                color = band.ink, fontWeight = FontWeight.Bold)
                        }
                    }
                    risk?.endedAt?.let { stamp ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(stringResource(R.string.detail_date), Modifier.weight(1f), color = secondary)
                            Text(remember(stamp) { displayTime(stamp) }, fontWeight = FontWeight.Bold)
                        }
                    }
                }
                if (risk != null) {
                    ResultPanel {
                        Text(stringResource(R.string.detail_summary), color = secondary)
                        Text(risk.contextReason ?: stringResource(R.string.detail_no_context), lineHeight = 24.sp)
                    }
                    ResultPanel {
                        SectionAction(R.string.detail_warning, R.string.detail_more) { showWarning = true }
                        Text(warningTitle,
                            fontWeight = FontWeight.Bold, color = if (risk.assessment == "suspicious") danger else PicInk)
                        warningReason?.let { Text(it, color = secondary, lineHeight = 22.sp) }
                        if (risk.assessment == "suspicious") {
                            val steps = listOfNotNull(
                                R.string.detail_no_transfer.takeIf { "money_transfer" in risk.riskTypes },
                                R.string.detail_verify.takeIf { "institution_impersonation" in risk.riskTypes },
                            )
                            if (steps.isNotEmpty()) Text(stringResource(R.string.detail_actions), fontWeight = FontWeight.Bold)
                            steps.forEachIndexed { index, label ->
                                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Surface(shape = CircleShape, color = Color(0xFF1E40AF)) {
                                        Box(Modifier.size(24.dp), contentAlignment = Alignment.Center) {
                                            Text((index + 1).toString(), color = Color.White, fontSize = 12.sp)
                                        }
                                    }
                                    Text(stringResource(label), fontSize = 15.sp)
                                }
                            }
                        }
                    }
                }
                SectionAction(R.string.detail_chat, R.string.detail_expand) { showChat = true }
                Surface(shape = RoundedCornerShape(20.dp), color = Color.White, border = BorderStroke(1.dp, edge)) {
                    Transcript(state.maskedTexts, enlarged = false)
                }
            }
        }
    }
    if (showChat || showWarning) {
        val close = { showChat = false; showWarning = false }
        AlertDialog(onDismissRequest = close, title = {
            Text(stringResource(if (showChat) R.string.detail_chat else R.string.detail_warning))
        }, text = {
            if (showChat) Transcript(state.maskedTexts, enlarged = true)
            else Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(warningTitle)
                warningReason?.let { Text(it) }
                risk?.evidenceIds.orEmpty().distinct().forEach { id ->
                    state.maskedTexts.getOrNull(id - 1)?.let { Text(stringResource(R.string.detail_evidence_line, id, it)) }
                }
            }
        }, confirmButton = { TextButton(onClick = close) { Text(stringResource(R.string.close)) } })
    }
}

@Composable
private fun ResultPanel(content: @Composable ColumnScope.() -> Unit) {
    Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp), color = panel, border = BorderStroke(1.dp, edge)) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
    }
}

@Composable
private fun SectionAction(title: Int, action: Int, onClick: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(stringResource(title), Modifier.weight(1f), fontWeight = FontWeight.Bold)
        Surface(onClick = onClick, shape = CircleShape, color = Color(0xFF697384), contentColor = Color.White) {
            Text(stringResource(action), Modifier.padding(horizontal = 12.dp, vertical = 6.dp), fontSize = 13.sp)
        }
    }
}

@Composable
private fun Transcript(lines: List<String>, enlarged: Boolean) {
    LazyColumn(Modifier.fillMaxWidth().heightIn(max = if (enlarged) 480.dp else 200.dp),
        contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (lines.isEmpty()) item { Text(stringResource(R.string.detail_empty_chat), color = secondary) }
        items(lines) { line ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Image(painterResource(R.drawable.result_speaker), null, Modifier.size(28.dp))
                Surface(shape = RoundedCornerShape(16.dp, 16.dp, 16.dp, 4.dp), color = panel) {
                    Text(line, Modifier.padding(12.dp), fontSize = if (enlarged) 19.sp else 14.sp,
                        lineHeight = if (enlarged) 28.sp else 21.sp)
                }
            }
        }
    }
}

private fun displayTime(value: String): String {
    val seconds = value.replace(Regex("\\.\\d+(?=Z|[+-])"), "")
    val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US)
    val date = try { format.parse(seconds) } catch (_: java.text.ParseException) { null }
    val displayFormat = SimpleDateFormat("yyyy.MM.dd a h:mm", Locale.KOREA).apply {
        timeZone = TimeZone.getTimeZone("Asia/Seoul")
    }
    return date?.let { displayFormat.format(it) } ?: value
}

@Preview(name = "분석 결과 디테일", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun AnalysisResultPreview() {
    PicScreenTheme {
        val risk = RiskResult(82.0, 82.0, "송금 유도 의심", "ok", "다른 사람에게 알리지 말고 안전계좌로 송금하라고 요구했습니다.",
            null, endedAt = "2026-11-08T14:32:00+09:00", riskTypes = listOf("institution_impersonation", "money_transfer"),
            assessment = "suspicious", evidenceIds = listOf(1))
        AnalysisResultDetailScreen(SttState(phase = SttPhase.STOPPED, count = 1, risk = risk,
            maskedTexts = listOf("안전계좌 [ACCOUNT_NUMBER]로 돈을 옮겨 주세요.")), {}, {}, {})
    }
}
