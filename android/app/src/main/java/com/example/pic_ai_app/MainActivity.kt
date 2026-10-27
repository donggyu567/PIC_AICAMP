package com.example.pic_ai_app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.tooling.preview.Preview
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.pic_ai_app.presentation.stt.SttScreen
import com.example.pic_ai_app.presentation.stt.SttUiState
import com.example.pic_ai_app.presentation.stt.SttViewModel
import com.example.pic_ai_app.ui.theme.PIC_AI_APPTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE,
        )
        enableEdgeToEdge()
        setContent {
            PIC_AI_APPTheme {
                SttRoute()
            }
        }
    }
}

@Composable
private fun SttRoute(viewModel: SttViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) viewModel.startRecording() else viewModel.reportPermissionDenied()
    }

    SttScreen(
        state = state,
        onStart = {
            if (
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.RECORD_AUDIO,
                ) == PackageManager.PERMISSION_GRANTED
            ) {
                viewModel.startRecording()
            } else {
                permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
        },
        onStop = viewModel::stopRecording,
        onDismissError = viewModel::clearError,
    )
}

@Preview(showBackground = true)
@Composable
private fun SttScreenPreview() {
    PIC_AI_APPTheme {
        SttScreen(
            state = SttUiState(),
            onStart = {},
            onStop = {},
            onDismissError = {},
        )
    }
}
