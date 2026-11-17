package com.example.pic_ai_app.presentation.analysis

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicScreenTheme

@Composable
internal fun UtteranceProgressScreen(maskedTexts: List<String>, audioLevels: List<Float>, onBack: () -> Unit) {
    val listState = rememberLazyListState()
    LaunchedEffect(maskedTexts.size) {
        if (maskedTexts.isNotEmpty()) listState.animateScrollToItem(0)
    }
    AnalysisDetailLayout(stringResource(R.string.live_progress), audioLevels, onBack) {
        Spacer(Modifier.height(48.dp))
        AnalysisDetailCard(Modifier.weight(1f)) {
            Column(Modifier.padding(20.dp)) {
                Text(stringResource(R.string.live_transcript_title), fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(16.dp))
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    state = listState,
                    reverseLayout = true,
                    verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.Top),
                ) {
                    if (maskedTexts.isEmpty()) item { Text(stringResource(R.string.live_transcript_empty)) }
                    // In the reversed layout, slot zero is the newest utterance at the bottom.
                    items(maskedTexts.size, key = { slot -> maskedTexts.lastIndex - slot }) { slot ->
                        Text(maskedTexts[maskedTexts.lastIndex - slot], fontSize = 16.sp, lineHeight = 24.sp)
                    }
                }
            }
        }
        Spacer(Modifier.fillMaxHeight(.123f))
    }
}

@Preview(name = "발화 진행 상황", widthDp = 412, heightDp = 917, showBackground = true)
@Composable
private fun UtteranceProgressPreview() {
    PicScreenTheme {
        UtteranceProgressScreen(
            maskedTexts = listOf(
                "여보세요. 금융범죄 조사 때문에 연락드렸습니다. 고객님 명의의 계좌가 사건에 이용된 정황이 있어서 확인이 필요합니다.",
                "제 계좌요? 저는 그런 일 없는데요. 어느 기관에서 전화하신 거예요?",
                "지금은 확인 중이라 자세히 말씀드리기 어렵습니다. 우선 다른 사람에게 알리지 마시고, 안내해 드리는 안전계좌로 돈을 옮겨 주셔야 합니다.",
            ),
            audioLevels = listOf(.35f, .55f, .8f, .45f, .7f, .4f, .65f, .8f, .5f), onBack = {},
        )
    }
}
