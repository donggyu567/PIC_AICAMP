package com.example.pic_ai_app.presentation.call

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.presentation.stt.SttControlsSection
import com.example.pic_ai_app.presentation.stt.SttTranscriptSection
import com.example.pic_ai_app.presentation.stt.SttUiState
import com.example.pic_ai_app.presentation.warning.WarningCard
import com.example.pic_ai_app.presentation.warning.WarningUiState

@Composable
fun CallScreen(
    sttState: SttUiState,
    warning: WarningUiState?,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onDismissError: () -> Unit,
) {
    Scaffold { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            SttTranscriptSection(sttState)
            WarningCard(warning)
            SttControlsSection(sttState, onStart, onStop, onDismissError)
        }
    }
}
