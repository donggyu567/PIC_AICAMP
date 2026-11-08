package com.example.pic_ai_app.data.stt

import com.example.pic_ai_app.audio.Microphone
import com.example.pic_ai_app.domain.model.MaskedTranscript
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
        val allowMask = CompletableDeferred<Unit>()
        val session = SttSession(scope, { true }, { microphone }, { _, conversation, number -> allowMask.await(); MaskedTranscript(conversationId=conversation, utteranceId=number, maskedText="[PERSON]", hasMaskedData=true, maskedTypes=listOf("PERSON")) }) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString()) }
            waitFor { received.contains("01000200") }
            withContext(dispatcher) { session.stop() }
            waitFor { states.lastOrNull()?.masking == true }
            assertNotEquals(SttPhase.STOPPED, states.last().phase)
            allowMask.complete(Unit)
            waitFor { states.lastOrNull()?.phase == SttPhase.STOPPED }
            assertTrue(received[0].contains("\"start\""))
            assertEquals("01000200", received[1])
            assertTrue(received[2].contains("\"stop\""))
            assertEquals(1, states.last().count)
            assertEquals(listOf("[PERSON]"), states.last().maskedTexts)
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
    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun maskingFailureNeverDisplaysRawTranscript() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.contains("\"start\"")) {
                    webSocket.send("""{"type":"ready","conversation_id":"test","max_session_seconds":600}""")
                    webSocket.send("""{"type":"transcript","conversation_id":"test","utterance_id":1,"text":"private text"}""")
                }
            }
        }))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val microphone = FakeMicrophone()
        val session = SttSession(scope, { true }, { microphone }, { _, _, _ -> throw UnsatisfiedLinkError("missing native library") }) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString()) }
            waitFor { states.lastOrNull()?.phase == SttPhase.ERROR }
            assertTrue(states.last().maskedTexts.isEmpty())
            assertFalse(states.toString().contains("private text"))
            assertTrue(microphone.stopped.isCompleted)
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun finalMaskedUtteranceIsAnalyzedBeforeStopCompletes() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.contains("\"start\""))
                    webSocket.send("""{"type":"ready","conversation_id":"test","max_session_seconds":600}""")
                else if (text.contains("\"stop\"")) {
                    webSocket.send("""{"type":"transcript","conversation_id":"test","utterance_id":1,"text":"private text"}""")
                    webSocket.send("""{"type":"stopped","conversation_id":"test","reason":"user_stop","last_utterance_id":1}""")
                }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, reason)
            }
        }))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":1,"analysis_status":"ok","correction_status":"ok","current_risk_score":30,"cumulative_risk_score":55,"context_judgment":{"status":"not_run"}}"""))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val microphone = FakeMicrophone()
        val analysis = RiskAnalysisClient()
        val session = SttSession(scope, { true }, { microphone },
            { _, conversation, number -> MaskedTranscript(conversationId=conversation, utteranceId=number,
                maskedText="[PERSON]", hasMaskedData=true, maskedTypes=listOf("PERSON")) },
            analysis::analyze) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString().replaceFirst("http", "ws")) }
            waitFor { microphone.started }
            withContext(dispatcher) { session.stop() }
            waitFor { states.lastOrNull()?.phase == SttPhase.STOPPED }
            assertEquals(55.0, states.last().risk!!.cumulativeScore!!, 0.001)
            assertEquals(listOf("[PERSON]"), states.last().maskedTexts)
            assertFalse(states.toString().contains("private text"))
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun finishFailureKeepsLastResultAndCanRetry() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.contains("\"start\""))
                    webSocket.send("""{"type":"ready","conversation_id":"test","max_session_seconds":600}""")
                else if (text.contains("\"stop\"")) {
                    webSocket.send("""{"type":"transcript","conversation_id":"test","utterance_id":1,"text":"private text"}""")
                    webSocket.send("""{"type":"stopped","conversation_id":"test","reason":"user_stop","last_utterance_id":1}""")
                }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(code, reason) }
        }))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val microphone = FakeMicrophone()
        val result = RiskResult(20.0, 30.0, null, "not_run", null, "ok")
        var attempts = 0
        val session = SttSession(scope, { true }, { microphone },
            { _, conversation, number -> MaskedTranscript(conversationId=conversation, utteranceId=number,
                maskedText="[PERSON]", hasMaskedData=true, maskedTypes=listOf("PERSON")) },
            { _, _ -> result },
            { _, conversation, last ->
                assertEquals("test", conversation)
                assertEquals(1, last)
                if (++attempts == 1) throw java.io.IOException("failure")
                result.copy(cumulativeScore = 40.0)
            }) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString().replaceFirst("http", "ws")) }
            waitFor { microphone.started }
            withContext(dispatcher) { session.stop() }
            waitFor { states.lastOrNull()?.canRetryFinish == true }
            assertEquals(SttPhase.ERROR, states.last().phase)
            assertEquals(30.0, states.last().risk!!.cumulativeScore!!, 0.001)
            withContext(dispatcher) { session.retryFinish() }
            waitFor { states.lastOrNull()?.phase == SttPhase.STOPPED }
            assertEquals(40.0, states.last().risk!!.cumulativeScore!!, 0.001)
            assertEquals(2, attempts)
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun noUtterancesStopsWithoutServerFinalization() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.contains("\"start\"")) webSocket.send("""{"type":"ready","conversation_id":"test","max_session_seconds":600}""")
                else if (text.contains("\"stop\"")) webSocket.send("""{"type":"stopped","conversation_id":"test","reason":"user_stop","last_utterance_id":0}""")
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(code, reason) }
        }))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val microphone = FakeMicrophone()
        var finalized = false
        val session = SttSession(scope, { true }, { microphone }, finalize = { _, _, _ ->
            finalized = true
            throw AssertionError("no HTTP finish for empty session")
        }) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString().replaceFirst("http", "ws")) }
            waitFor { microphone.started }
            withContext(dispatcher) { session.stop() }
            waitFor { states.lastOrNull()?.phase == SttPhase.STOPPED }
            assertEquals(0, states.last().count)
            assertFalse(finalized)
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun failedAnalysisWaitsForRecoveryBeforeFollowingUtteranceAndFinish() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.contains("\"start\"")) {
                    webSocket.send("""{"type":"ready","conversation_id":"test"}""")
                    webSocket.send("""{"type":"transcript","conversation_id":"test","utterance_id":1,"text":"first"}""")
                    webSocket.send("""{"type":"transcript","conversation_id":"test","utterance_id":2,"text":"second"}""")
                } else if (text.contains("\"stop\"")) {
                    webSocket.send("""{"type":"stopped","conversation_id":"test","last_utterance_id":2}""")
                }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(code, reason) }
        }))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val analyzed = CopyOnWriteArrayList<Int>()
        val result = RiskResult(20.0, 30.0, null, "not_run", null, "ok")
        val session = SttSession(scope, { true }, { FakeMicrophone() },
            { _, conversation, number -> MaskedTranscript(conversationId=conversation, utteranceId=number,
                maskedText="[PERSON]", hasMaskedData=true, maskedTypes=listOf("PERSON")) },
            analyze = { _, item -> analyzed.add(item.utteranceId); if (item.utteranceId == 1) throw java.io.IOException(); result },
            finalize = { _, _, last -> assertEquals(2, last); result },
            recover = { _, item -> assertEquals(1, item.utteranceId); result }) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString().replaceFirst("http", "ws")) }
            waitFor { states.lastOrNull()?.canRetryAnalysis == true }
            assertEquals(listOf(1), analyzed.toList())
            withContext(dispatcher) { session.retryAnalysis() }
            waitFor { states.lastOrNull()?.phase == SttPhase.STOPPED }
            assertEquals(listOf(1, 2), analyzed.toList())
            assertEquals(30.0, states.last().risk!!.cumulativeScore!!, 0.001)
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun sendsDeviceTokenWithWebSocketHandshake() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {}))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val session = SttSession(scope, { true }, { FakeMicrophone() }, tokenForServer = { "test-device-token" }) { }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString().replaceFirst("http", "ws")) }
            assertEquals("Bearer test-device-token", server.takeRequest().getHeader("Authorization"))
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }

}
