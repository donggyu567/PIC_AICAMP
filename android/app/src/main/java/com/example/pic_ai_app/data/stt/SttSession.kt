package com.example.pic_ai_app.data.stt

import android.annotation.SuppressLint
import com.example.pic_ai_app.audio.AndroidPcmAudioRecorder
import com.example.pic_ai_app.audio.Microphone
import kotlinx.coroutines.*
import okhttp3.*
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit

enum class SttPhase { IDLE, CONNECTING, LISTENING, FINALIZING, STOPPED, ERROR }

data class SttState(
    val phase: SttPhase = SttPhase.IDLE,
    val count: Int = 0,
    val error: String? = null,
)

/** Socket callbacks are serialized onto the supplied main scope. */
class SttSession(
    private val scope: CoroutineScope,
    private val hasPermission: () -> Boolean,
    private val microphoneFactory: () -> Microphone = { AndroidPcmAudioRecorder() },
    private val publish: (SttState) -> Unit,
) {
    private val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).build()
    private var recorder = microphoneFactory()
    @Volatile private var socket: WebSocket? = null
    private var capture: Job? = null
    private var timeout: Job? = null
    @Volatile private var session = 0L
    @Volatile private var state = SttState()
    private var conversationId: String? = null

    private fun update(next: SttState) {
        state = next
        publish(next)
    }

    fun start(url: String) {
        if (state.phase in listOf(SttPhase.CONNECTING, SttPhase.LISTENING, SttPhase.FINALIZING)) return
        val request = try { Request.Builder().url(url).build() } catch (_: IllegalArgumentException) {
            update(SttState(phase = SttPhase.ERROR, error = "서버 주소를 확인해 주세요."))
            return
        }
        recorder = microphoneFactory()
        val id = ++session
        conversationId = null
        update(SttState(phase = SttPhase.CONNECTING))
        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                scope.launch {
                    if (id != session || state.phase != SttPhase.CONNECTING) {
                        webSocket.cancel()
                        return@launch
                    }
                    if (!webSocket.send("""{"type":"start","consent":true,"audio_format":"pcm_s16le","sample_rate":16000,"channels":1}""")) {
                        fail(id, "서버에 시작 요청을 보내지 못했습니다.")
                    }
                }
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                scope.launch { receive(id, text) }
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                scope.launch { fail(id, "음성 인식 연결이 끊겼습니다.") }
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                scope.launch {
                    if (id == session && state.phase != SttPhase.STOPPED) fail(id, "음성 인식 연결이 종료되었습니다.")
                }
            }
        })
        timeout = scope.launch {
            delay(20_000)
            if (id == session && state.phase == SttPhase.CONNECTING) fail(id, "서버 준비 시간이 초과되었습니다.")
        }
    }

    @SuppressLint("MissingPermission")
    private fun receive(id: Long, text: String) {
        if (id != session) return
        val json = try { JSONObject(text) } catch (_: Exception) {
            fail(id, "서버 응답 형식이 올바르지 않습니다.")
            return
        }
        when (json.optString("type")) {
            "ready" -> {
                if (state.phase != SttPhase.CONNECTING) return fail(id, "서버 응답 순서가 올바르지 않습니다.")
                val conversation = json.optString("conversation_id")
                if (conversation.isBlank()) return fail(id, "서버 세션을 확인하지 못했습니다.")
                if (!hasPermission()) return fail(id, "마이크 권한이 필요합니다.")
                conversationId = conversation
                timeout?.cancel()
                update(state.copy(phase = SttPhase.LISTENING))
                capture = scope.launch {
                    try {
                        recorder.capture { bytes ->
                            if (id != session || state.phase != SttPhase.LISTENING) return@capture
                            val activeSocket = socket ?: throw IllegalStateException()
                            if (activeSocket.queueSize() > 320_000 || !activeSocket.send(bytes.toByteString())) {
                                throw IllegalStateException()
                            }
                        }
                    } catch (_: CancellationException) {
                    } catch (_: Exception) {
                        fail(id, "마이크 입력 또는 음성 전송에 실패했습니다.")
                    }
                }
                timeout = scope.launch { delay(600_000); if (id == session) stop() }
            }
            "transcript" -> {
                if (state.phase !in listOf(SttPhase.LISTENING, SttPhase.FINALIZING) ||
                    json.optString("conversation_id") != conversationId ||
                    json.optInt("utterance_id", -1) != state.count + 1) {
                    return fail(id, "서버 발화 순서를 확인하지 못했습니다.")
                }
                // Do not retain, display, or log the unmasked text.
                update(state.copy(count = state.count + 1))
            }
            "status" -> {
                if (json.optString("conversation_id") != conversationId) fail(id, "서버 세션이 일치하지 않습니다.")
                else if (json.optString("status") == "finalizing" && state.phase == SttPhase.LISTENING) stop(sendStop = false)
            }
            "stopped" -> {
                if (json.optString("conversation_id") != conversationId ||
                    json.optInt("last_utterance_id", -1) != state.count) {
                    return fail(id, "마지막 발화 확인에 실패했습니다.")
                }
                recorder.stop()
                capture?.cancel()
                timeout?.cancel()
                update(state.copy(phase = SttPhase.STOPPED))
                socket?.close(1000, null)
                socket = null
            }
            "error" -> fail(id, "음성 인식 처리에 실패했습니다. 다시 시도해 주세요.")
            else -> fail(id, "알 수 없는 서버 응답입니다.")
        }
    }

    fun stop(sendStop: Boolean = true) {
        if (state.phase == SttPhase.CONNECTING) {
            fail(session, "연결을 중단했습니다.")
            return
        }
        if (state.phase != SttPhase.LISTENING) return
        val id = session
        update(state.copy(phase = SttPhase.FINALIZING))
        timeout?.cancel()
        recorder.stop()
        scope.launch {
            capture?.join()
            if (id != session) return@launch
            if (sendStop && socket?.send("""{"type":"stop"}""") != true) {
                fail(id, "종료 요청을 보내지 못했습니다.")
                return@launch
            }
            timeout = scope.launch {
                delay(20_000)
                if (id == session && state.phase == SttPhase.FINALIZING) fail(id, "마지막 음성 처리 시간이 초과되었습니다.")
            }
        }
    }

    fun abort() {
        ++session
        timeout?.cancel()
        recorder.stop()
        capture?.cancel()
        socket?.cancel()
        socket = null
        conversationId = null
        update(SttState())
    }

    private fun fail(id: Long, message: String) {
        if (id != session || state.phase in listOf(SttPhase.STOPPED, SttPhase.ERROR, SttPhase.IDLE)) return
        ++session
        timeout?.cancel()
        recorder.stop()
        capture?.cancel()
        socket?.cancel()
        socket = null
        update(state.copy(phase = SttPhase.ERROR, error = message))
    }
}
