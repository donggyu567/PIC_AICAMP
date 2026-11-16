package com.example.pic_ai_app.presentation.result

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicInk
import com.example.pic_ai_app.ui.theme.PicScreenTheme
import com.example.pic_ai_app.ui.theme.PicWhite

private data class ConversationLine(val text: String, val alignEnd: Boolean = false)

private val chatBorder = BorderStroke(1.dp, Color(0xFFE2E8F0))
private val chatLabel = Color(0xFF64748B)

@Composable
internal fun ConversationDetailScreen(maskedTexts: List<String>, onBack: () -> Unit) {
    val lines = remember(maskedTexts) { maskedTexts.map { ConversationLine(it) } }
    ConversationDetailContent(lines, onBack)
}

@Composable
private fun ConversationDetailContent(lines: List<ConversationLine>, onBack: () -> Unit) {
    Surface(Modifier.fillMaxSize(), color = PicWhite, contentColor = PicInk) {
        Column(
            Modifier.windowInsetsPadding(WindowInsets.safeDrawing.union(WindowInsets(top = 32.dp))),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            ResultDetailHeader(stringResource(R.string.detail_conversation_title), onBack, fontSize = 30.sp)
            Column(
                Modifier.weight(1f).widthIn(max = 480.dp).fillMaxWidth()
                    .padding(start = 24.dp, end = 24.dp, top = 8.dp, bottom = 16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(stringResource(R.string.detail_chat), color = chatLabel, fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold)
                Surface(Modifier.weight(1f).fillMaxWidth(), shape = RoundedCornerShape(20.dp),
                    color = Color(0xFFF8FAFC), border = chatBorder) {
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        if (lines.isEmpty()) item { Text(stringResource(R.string.detail_empty_chat), color = chatLabel) }
                        items(lines) { line -> ConversationBubble(line) }
                    }
                }
            }
        }
    }
}

@Composable
private fun ConversationBubble(line: ConversationLine) {
    val alignment = if (line.alignEnd) Alignment.End else Alignment.Start
    val shape = if (line.alignEnd) RoundedCornerShape(20.dp, 20.dp, 8.dp, 20.dp)
        else RoundedCornerShape(20.dp, 20.dp, 20.dp, 8.dp)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp, alignment)) {
        if (!line.alignEnd) SpeakerAvatar(Color(0xFF1E40AF))
        Surface(Modifier.weight(1f, fill = false), shape = shape, color = PicWhite, border = chatBorder) {
            Text(line.text, Modifier.padding(16.dp), color = PicInk, fontSize = 16.sp,
                lineHeight = 26.sp, fontWeight = FontWeight.Medium)
        }
        if (line.alignEnd) SpeakerAvatar(Color(0xFF475569))
    }
}

@Composable
private fun SpeakerAvatar(color: Color) {
    Box(Modifier.size(36.dp).background(color, CircleShape), contentAlignment = Alignment.Center) {
        Icon(painterResource(R.drawable.ic_pic_person_filled), contentDescription = null,
            modifier = Modifier.size(24.dp), tint = PicWhite)
    }
}

@Preview(name = "대화 상세 내용", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun ConversationDetailPreview() {
    val lines = listOf(
        ConversationLine("금융범죄 조사 때문에 연락드렸습니다. 고객님 명의의 계좌가 사건에 이용된 정황이 있어서 확인이 필요합니다."),
        ConversationLine("제 계좌요? 어느 기관에서 전화하신 거예요?", alignEnd = true),
        ConversationLine("지금은 확인 중이라 자세히 말씀드리기 어렵습니다. 다른 사람에게 알리지 마시고, 안전계좌로 돈을 옮겨 주셔야 합니다."),
        ConversationLine("돈을 옮겨야 한다고요? 제가 직접 확인해 볼게요.", alignEnd = true),
        ConversationLine("안전계좌는 우리 기관에서 제공하는 임시 계좌입니다. 확인이 끝나면 원래 계좌로 다시 돌려드릴 예정입니다."),
        ConversationLine("임시 계좌라면 왜 바로 은행 앱에서 확인할 수 없는 거죠?", alignEnd = true),
    )
    PicScreenTheme { ConversationDetailContent(lines, onBack = {}) }
}
