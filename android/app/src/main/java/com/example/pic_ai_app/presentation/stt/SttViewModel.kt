package com.example.pic_ai_app.presentation.stt

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.pic_ai_app.audio.AndroidPcmAudioRecorder
import com.example.pic_ai_app.data.storage.ConversationIdGenerator
import com.example.pic_ai_app.data.storage.InternalTranscriptRepository
import com.example.pic_ai_app.domain.model.UtteranceTranscript
import com.example.pic_ai_app.domain.repository.TranscriptRepository
import com.example.pic_ai_app.stt.SherpaOnnxStreamingSttEngine
import com.example.pic_ai_app.stt.SttDecodeResult
import com.example.pic_ai_app.stt.StreamingSttEngine
import java.util.concurrent.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class SttViewModel(application: Application) : AndroidViewModel(application) {
    private val transcriptRepository: TranscriptRepository =
        InternalTranscriptRepository(application)
    private val conversationIdGenerator = ConversationIdGenerator()
    private val sttEngine: StreamingSttEngine =
        SherpaOnnxStreamingSttEngine(application.assets)
    private val audioRecorder = AndroidPcmAudioRecorder()
    private val sessionMutex = Mutex()

    private val _uiState = MutableStateFlow(SttUiState())
    val uiState: StateFlow<SttUiState> = _uiState.asStateFlow()

    private var recordingJob: Job? = null
    private var nextUtteranceId = 1

    fun startRecording() {
        if (recordingJob?.isActive == true) return

        val buttonPressedAt = System.currentTimeMillis()
        recordingJob = viewModelScope.launch {
            sessionMutex.withLock {
                runRecordingSession(buttonPressedAt)
            }
        }
    }

    fun stopRecording() {
        if (recordingJob?.isActive != true) return
        if (_uiState.value.status == SttStatus.INITIALIZING) {
            recordingJob?.cancel()
            _uiState.value = SttUiState(status = SttStatus.IDLE)
            return
        }
        _uiState.update { it.copy(status = SttStatus.STOPPING) }
        audioRecorder.stop()
    }

    fun reportPermissionDenied() {
        _uiState.update {
            it.copy(
                status = SttStatus.ERROR,
                errorMessage = "마이크 권한이 필요합니다. 권한을 허용한 뒤 다시 시도해 주세요.",
            )
        }
    }

    fun clearError() {
        _uiState.update { state ->
            if (state.status == SttStatus.ERROR) {
                state.copy(status = SttStatus.IDLE, errorMessage = null)
            } else {
                state.copy(errorMessage = null)
            }
        }
    }

    private suspend fun runRecordingSession(buttonPressedAt: Long) {
        var sessionStarted = false
        try {
            _uiState.value = SttUiState(status = SttStatus.INITIALIZING)
            val baseConversationId = conversationIdGenerator.fromTimestamp(buttonPressedAt)
            val conversationId = transcriptRepository.createConversation(baseConversationId)
            nextUtteranceId = 1

            withContext(Dispatchers.Default) {
                sttEngine.initialize()
                sttEngine.startStream()
            }
            sessionStarted = true
            _uiState.value = SttUiState(
                status = SttStatus.LISTENING,
                conversationId = conversationId,
            )

            audioRecorder.capture { samples ->
                handleDecodeResult(
                    conversationId = conversationId,
                    result = sttEngine.acceptAudio(samples),
                )
            }

            val finalResult = withContext(Dispatchers.Default) {
                sttEngine.finishStream()
            }
            handleDecodeResult(conversationId, finalResult)

            _uiState.update {
                it.copy(
                    status = SttStatus.IDLE,
                    partialText = "",
                    errorMessage = null,
                )
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: SecurityException) {
            showError("마이크 권한을 확인할 수 없습니다.")
        } catch (_: Throwable) {
            // Do not expose recognizer details or transcript contents in logs/UI.
            showError("음성 인식을 시작하거나 결과를 저장하지 못했습니다.")
        } finally {
            audioRecorder.stop()
            if (sessionStarted) sttEngine.stopStream()
        }
    }

    private suspend fun handleDecodeResult(
        conversationId: String,
        result: SttDecodeResult,
    ) {
        if (!result.endpointDetected) {
            _uiState.update { it.copy(partialText = result.partialText) }
            return
        }

        _uiState.update { it.copy(partialText = "") }
        val finalText = result.finalText ?: return
        val utteranceId = nextUtteranceId
        val transcript = UtteranceTranscript.unmasked(
            conversationId = conversationId,
            utteranceId = utteranceId,
            finalTranscript = finalText,
        )
        transcriptRepository.save(transcript)
        nextUtteranceId += 1
        _uiState.update {
            it.copy(
                lastFinalText = finalText,
                savedUtteranceCount = utteranceId,
            )
        }
    }

    private fun showError(message: String) {
        _uiState.update {
            it.copy(
                status = SttStatus.ERROR,
                partialText = "",
                errorMessage = message,
            )
        }
    }

    override fun onCleared() {
        recordingJob?.cancel()
        audioRecorder.stop()
        sttEngine.close()
    }
}
