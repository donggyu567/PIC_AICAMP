package com.example.pic_ai_app.presentation.stt

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun SttScreen(
    state: SttUiState,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onDismissError: () -> Unit,
) {
    Scaffold { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 24.dp, vertical = 20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                text = "온디바이스 음성 인식",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "음성 원문은 이 기기의 앱 전용 저장소에만 보관됩니다.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            StatusCard(state)
            TranscriptCard(
                title = "실시간 인식 (저장 안 함)",
                text = state.partialText.ifEmpty {
                    if (state.status == SttStatus.LISTENING) "말씀해 주세요…" else "대기 중"
                },
                emphasized = state.partialText.isNotEmpty(),
            )
            TranscriptCard(
                title = "마지막 확정 발화",
                text = state.lastFinalText.ifEmpty { "아직 저장된 발화가 없습니다." },
                emphasized = state.lastFinalText.isNotEmpty(),
            )

            Spacer(modifier = Modifier.weight(1f))

            state.errorMessage?.let { message ->
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                    ),
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = message,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                        OutlinedButton(onClick = onDismissError) {
                            Text("확인")
                        }
                    }
                }
            }

            MicrophoneButton(
                status = state.status,
                onStart = onStart,
                onStop = onStop,
            )
        }
    }
}

@Composable
private fun StatusCard(state: SttUiState) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .background(statusColor(state.status), CircleShape),
                )
                Text(
                    text = statusLabel(state.status),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Text(
                text = "conversation_id: ${state.conversationId ?: "-"}",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = "저장된 발화: ${state.savedUtteranceCount}개",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun TranscriptCard(
    title: String,
    text: String,
    emphasized: Boolean,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(132.dp),
        shape = RoundedCornerShape(16.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = text,
                style = MaterialTheme.typography.bodyLarge,
                color = if (emphasized) {
                    MaterialTheme.colorScheme.onSurface
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }
    }
}

@Composable
private fun MicrophoneButton(
    status: SttStatus,
    onStart: () -> Unit,
    onStop: () -> Unit,
) {
    val active = status == SttStatus.INITIALIZING || status == SttStatus.LISTENING
    val stopping = status == SttStatus.STOPPING
    Button(
        onClick = if (active) onStop else onStart,
        enabled = !stopping,
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp),
        colors = if (active) {
            ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
        } else {
            ButtonDefaults.buttonColors()
        },
    ) {
        if (status == SttStatus.INITIALIZING || stopping) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                strokeWidth = 2.dp,
                color = MaterialTheme.colorScheme.onPrimary,
            )
            Spacer(modifier = Modifier.size(10.dp))
        }
        Text(
            text = when (status) {
                SttStatus.INITIALIZING -> "모델 준비 중 · 중지"
                SttStatus.LISTENING -> "녹음 중지"
                SttStatus.STOPPING -> "발화 확정 중"
                SttStatus.IDLE, SttStatus.ERROR -> "마이크 시작"
            },
            fontWeight = FontWeight.SemiBold,
        )
    }
}

private fun statusLabel(status: SttStatus): String = when (status) {
    SttStatus.IDLE -> "대기"
    SttStatus.INITIALIZING -> "모델 준비 중"
    SttStatus.LISTENING -> "인식 중"
    SttStatus.STOPPING -> "마지막 발화 확정 중"
    SttStatus.ERROR -> "오류"
}

private fun statusColor(status: SttStatus): Color = when (status) {
    SttStatus.IDLE -> Color(0xFF73777F)
    SttStatus.INITIALIZING, SttStatus.STOPPING -> Color(0xFFF9A825)
    SttStatus.LISTENING -> Color(0xFF2E7D32)
    SttStatus.ERROR -> Color(0xFFC62828)
}
