package com.example.pic_ai_app.presentation.components.analysis

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicHomeBlue
import com.example.pic_ai_app.ui.theme.PicNavigationSelected
import com.example.pic_ai_app.ui.theme.PicTheme
import com.example.pic_ai_app.ui.theme.PicWhite
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

internal data class AnalysisWarningUi(
    val title: String,
    val actionTitle: String,
    val actionDescription: String,
    val detectedAtMillis: Long? = null,
    val evidence: List<WarningEvidence> = emptyList(),
)

internal data class WarningEvidence(
    val maskedText: String,
    // Indices refer to maskedText. The end index is exclusive.
    val highlight: TextRange? = null,
)

private val cardBorder = BorderStroke(1.dp, Color(0xFFD7E3EE))
private val sectionShape = RoundedCornerShape(14.dp)

@Composable
internal fun AnalysisWarningCard(warning: AnalysisWarningUi, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(20.dp),
        color = PicWhite,
        contentColor = PicNavigationSelected,
        border = cardBorder,
        shadowElevation = 3.dp,
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Box(
                        Modifier.size(32.dp).background(PicHomeBlue, CircleShape),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(painterResource(R.drawable.ic_analysis_warning), contentDescription = null, tint = PicWhite)
                    }
                    Text(
                        stringResource(R.string.analysis_warning_detection),
                        Modifier.weight(1f),
                        color = PicHomeBlue, fontWeight = FontWeight.Bold, fontSize = 15.sp,
                    )
                    warning.detectedAtMillis?.let { millis ->
                        val time = remember(millis) {
                            SimpleDateFormat("HH:mm", Locale.KOREA).apply {
                                timeZone = TimeZone.getTimeZone("Asia/Seoul")
                            }.format(Date(millis))
                        }
                        Text(time, color = PicHomeBlue, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                    }
                }
                Text(warning.title, fontWeight = FontWeight.Bold, fontSize = 22.sp, lineHeight = 26.sp)
            }
            if (warning.actionTitle.isNotBlank() || warning.actionDescription.isNotBlank()) {
                Column(
                    Modifier.fillMaxWidth().background(Color(0xFFEEF4F8), sectionShape).padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    WarningLabel(stringResource(R.string.analysis_warning_action))
                    if (warning.actionTitle.isNotBlank()) {
                        Text(warning.actionTitle, fontWeight = FontWeight.Bold, fontSize = 20.sp, lineHeight = 22.sp)
                    }
                    if (warning.actionDescription.isNotBlank()) {
                        Text(warning.actionDescription, fontSize = 16.sp, lineHeight = 18.sp)
                    }
                }
            }
            val evidence = warning.evidence.filter { it.maskedText.isNotBlank() }
            if (evidence.isNotEmpty()) {
                EvidenceSection(evidence)
            }
        }
    }
}

@Composable
private fun EvidenceSection(evidence: List<WarningEvidence>) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = sectionShape,
        color = Color(0xFFF7FAFD),
        contentColor = PicNavigationSelected,
        border = BorderStroke(1.dp, Color(0xFFE3EAF2)),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                WarningLabel(stringResource(R.string.analysis_warning_utterance), Modifier.weight(1f))
                Surface(shape = CircleShape, color = PicWhite, border = cardBorder) {
                    Text(
                        stringResource(R.string.analysis_warning_evidence),
                        Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        color = PicHomeBlue, fontWeight = FontWeight.Bold, fontSize = 11.sp, lineHeight = 14.sp,
                    )
                }
            }
            evidence.forEach { item ->
                val text = buildAnnotatedString {
                    append(item.maskedText)
                    val range = item.highlight
                    if (range != null && range.start >= 0 && range.end > range.start && range.end <= length) {
                        addStyle(SpanStyle(color = PicHomeBlue, fontWeight = FontWeight.Bold), range.start, range.end)
                    }
                }
                Text(text, fontSize = 16.sp, lineHeight = 20.sp)
            }
        }
    }
}

@Composable
private fun WarningLabel(text: String, modifier: Modifier = Modifier) {
    Text(text, modifier, color = PicHomeBlue, fontWeight = FontWeight.Bold, fontSize = 14.sp, lineHeight = 18.sp)
}

private fun previewWarning(): AnalysisWarningUi {
    val quote = "“안전계좌로 돈을 이체해 주세요.”"
    val phrase = "이체해 주세요."
    val start = quote.indexOf(phrase)
    return AnalysisWarningUi(
        title = "위험 · 송금 유도 의심",
        actionTitle = "지금 송금하지 마세요",
        actionDescription = "통화를 끊고 해당 기관의 공식 번호로 직접 확인하세요.",
        detectedAtMillis = 1_794_461_520_000L, // 2026-11-12 14:32 KST
        evidence = listOf(WarningEvidence(quote, TextRange(start, start + phrase.length))),
    )
}

@Preview(name = "경고 카드", showBackground = true, widthDp = 362)
@Composable
private fun AnalysisWarningCardPreview() {
    PicTheme { AnalysisWarningCard(previewWarning(), Modifier.fillMaxWidth().padding(8.dp)) }
}

@Preview(name = "여러 줄 발화", showBackground = true, widthDp = 362)
@Composable
private fun LongEvidencePreview() {
    val warning = previewWarning().copy(
        evidence = listOf(
            WarningEvidence("기관에서 계좌를 확인해야 하니 지금 통화를 유지해 달라고 했어요."),
            WarningEvidence("안내받은 계좌로 돈을 보내면 확인 후 돌려준다고 했어요."),
        ),
    )
    PicTheme { AnalysisWarningCard(warning, Modifier.fillMaxWidth().padding(8.dp)) }
}
