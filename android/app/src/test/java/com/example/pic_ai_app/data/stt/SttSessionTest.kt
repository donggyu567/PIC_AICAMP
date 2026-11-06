package com.example.pic_ai_app.data.stt

import com.example.pic_ai_app.audio.Microphone
import java.util.concurrent.CopyOnWriteArrayList
import kotlinx.coroutines.*
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okio.ByteString
import org.junit.Assert.*
import org.junit.Test

class SttSessionTest {
    private class FakeMicrophone : Microphone {
        val stopped = CompletableDeferred<Unit>()
        var started = false
        override suspend fun capture(onAudio: suspend (ByteArray) -> Unit) {
            started = true
            onAudio(byteArrayOf(1, 0, 2, 0))
            stopped.await()
        }
        override fun stop() { stopped.complete(Unit) }
    }

    private suspend fun waitFor(condition: () -> Boolean) = withTimeout(5000) {
        while (!condition()) delay(10)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun readyStartsAudioAndStopWaitsForLastTranscript() = runBlocking {
        val server = MockWebServer()
        val received = CopyOnWriteArrayList<String>()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                received.add(text)
                if (text.contains("\"start\"")) {
                    webSocket.send("""{"type":"ready","conversation_id":"test","max_session_seconds":600}""")
                } else if (text.contains("\"stop\"")) {
                    webSocket.send("""{"type":"transcript","conversation_id":"test","utterance_id":1,"text":"private text"}""")
                    webSocket.send("""{"type":"stopped","conversation_id":"test","reason":"user_stop","last_utterance_id":1}""")
                }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, reason)
            }
            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                received.add(bytes.hex())
            }
        }))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val microphone = FakeMicrophone()
        val session = SttSession(scope, { true }, { microphone }) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString()) }
            waitFor { received.contains("01000200") }
            withContext(dispatcher) { session.stop() }
            waitFor { states.lastOrNull()?.phase == SttPhase.STOPPED }
            assertTrue(received[0].contains("\"start\""))
            assertEquals("01000200", received[1])
            assertTrue(received[2].contains("\"stop\""))
            assertEquals(1, states.last().count)
            assertFalse(states.toString().contains("private text"))
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun revokedPermissionBeforeReadyDoesNotStartMicrophone() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                webSocket.send("""{"type":"ready","conversation_id":"test","max_session_seconds":600}""")
            }
        }))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val microphone = FakeMicrophone()
        val session = SttSession(scope, { false }, { microphone }) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString()) }
            waitFor { states.lastOrNull()?.phase == SttPhase.ERROR }
            assertFalse(microphone.started)
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }
}
