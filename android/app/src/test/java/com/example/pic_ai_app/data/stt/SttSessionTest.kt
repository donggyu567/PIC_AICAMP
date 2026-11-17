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

    @Test fun roundsScoresAndShowsTheStartNoticeOnceUntilRiskIsSeen() {
        assertEquals(LiveRiskLevel.Normal, LiveRiskScore.from(30.49)?.level)
        assertEquals(LiveRiskLevel.Suspect, LiveRiskScore.from(30.5)?.level)
        assertEquals(LiveRiskLevel.Caution, LiveRiskScore.from(50.5)?.level)
        assertEquals(LiveRiskLevel.Danger, LiveRiskScore.from(70.5)?.level)
        val listening = LiveAnalysisCards().showStartNotice(3_000)
        assertEquals(LiveStartNotice(3_000, false), listening.cards.single())
        assertEquals(listening, listening.showStartNotice(4_000))
        val normal = listening.record(1, 12.0, null, false, 4_500)
        assertEquals(LiveStartNotice(3_000, true), normal.cards.single())
        val suspected = normal.record(2, 31.0, null, false, 9_000)
        assertTrue(suspected.cards.single() is LiveRiskAlert)
        assertEquals(suspected, suspected.showStartNotice(10_000))
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun updatesScoreAndGroupsAiDetectionsAcrossUtterances() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.contains("\"start\"")) {
                    webSocket.send("""{"type":"ready","conversation_id":"test"}""")
                    for (id in 1..7) {
                        webSocket.send("""{"type":"transcript","conversation_id":"test","utterance_id":$id,"text":"utterance $id"}""")
                    }
                }
            }
        }))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":1,"analysis_status":"ok","cumulative_risk_score":25,"detected_types":["money_transfer"]}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":2,"analysis_status":"ok","cumulative_risk_score":27,"detected_types":["money_transfer"]}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":3,"analysis_status":"ok","cumulative_risk_score":31,"detected_types":["money_transfer"]}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":4,"analysis_status":"ok","cumulative_risk_score":51,"detected_types":["institution_impersonation"]}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":5,"analysis_status":"ok","cumulative_risk_score":52,"detected_types":["institution_impersonation"]}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":6,"analysis_status":"ok","cumulative_risk_score":48,"detected_types":[]}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":7,"analysis_status":"ok","cumulative_risk_score":49,"detected_types":["institution_impersonation"]}"""))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val analysis = RiskAnalysisClient()
        val session = SttSession(scope, { true }, { FakeMicrophone() },
            mask = { _, conversation, id -> MaskedTranscript(conversationId = conversation, utteranceId = id,
                maskedText = "[PERSON] $id", hasMaskedData = true, maskedTypes = listOf("PERSON")) },
            analyze = analysis::analyze) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString().replaceFirst("http", "ws")) }
            waitFor { states.lastOrNull()?.risk?.cumulativeScore == 49.0 }
            val current = states.last()
            assertEquals(SttPhase.LISTENING, current.phase)
            val alerts = current.liveCards.cards.filterIsInstance<LiveRiskAlert>()
            assertEquals(listOf(1, 3, 4, 7), alerts.map { it.firstUtteranceId })
            assertEquals(listOf(1, 2), alerts[0].evidenceIds)
            assertEquals(setOf("money_transfer"), alerts[0].signal?.types)
            assertEquals(LiveRiskLevel.Suspect, alerts[1].rise?.current?.level)
            assertEquals(LiveRiskLevel.Caution, alerts[2].rise?.current?.level)
            assertEquals(listOf(4, 5), alerts[2].evidenceIds)
            assertEquals(LiveScoreChange(LiveRiskScore(48), LiveRiskScore(49)),
                current.liveCards.cards.filterIsInstance<LiveScoreUpdate>().single().change)
            assertEquals((1..7).map { "[PERSON] $it" }, current.maskedTexts)
        } finally {
            withContext(dispatcher) { session.abort() }
            scope.cancel()
            server.shutdown()
        }
    }

    @Test fun updatesActionWhenTheLatestWarningAddsOrNarrowsTypes() {
        val money = LiveRiskSignal(LiveRiskSource.Ai, setOf("money_transfer"), listOf(1))
        val both = LiveRiskSignal(LiveRiskSource.Ai, setOf("money_transfer", "personal_information"), listOf(2))
        val info = LiveRiskSignal(LiveRiskSource.Ai, setOf("personal_information"), listOf(4))
        val app = LiveRiskSignal(LiveRiskSource.Ai, setOf("app_installation"), listOf(5))
        val afterMoney = LiveAnalysisCards().record(1, 25.0, money, false, 1)
        val afterNewType = afterMoney.record(2, 25.0, both, false, 2)
        val afterRepeatedDetection = afterNewType.record(3, 25.0, both.copy(evidenceIds = listOf(3)), false, 3)
        val afterNarrowedTypes = afterRepeatedDetection.record(4, 25.0, info, false, 4)
        val initial = afterMoney.cards.filterIsInstance<LiveRiskAlert>().last()
        val latest = afterNarrowedTypes.cards.filterIsInstance<LiveRiskAlert>().last()
        assertEquals(setOf("money_transfer"), initial.actionTypes)
        assertEquals(setOf("personal_information"), latest.actionTypes)
        assertEquals(2, latest.firstUtteranceId)
        assertEquals(listOf(2, 3, 4), latest.evidenceIds)
        val next = afterNarrowedTypes.record(5, 25.0, app, false, 5).cards.filterIsInstance<LiveRiskAlert>().last()
        assertEquals(setOf("app_installation"), next.actionTypes)
    }

    @Test fun keepsOneCardWhenActiveWarningContinuesBetweenAiDetections() {
        val ai = LiveRiskSignal(LiveRiskSource.Ai, setOf("money_transfer"), listOf(1), "누적 위험 경고")
        val server = LiveRiskSignal(LiveRiskSource.ServerWarning, emptySet(), listOf(1, 2), "누적 위험 경고")
        val cards = LiveAnalysisCards()
            .record(1, 75.0, ai, false, 1)
            .record(2, 75.0, server, false, 2)
            .record(3, 75.0, ai.copy(evidenceIds = listOf(3)), false, 3)
        val alert = cards.cards.single() as LiveRiskAlert
        assertEquals(LiveRiskSource.Ai, alert.signal?.source)
        assertEquals(listOf(1, 2, 3), alert.evidenceIds)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun restoresEvidenceCardsForContextAndActiveWarningsWithoutAiTypes() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().withWebSocketUpgrade(object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.contains("\"start\"")) {
                    webSocket.send("""{"type":"ready","conversation_id":"test"}""")
                    for (id in 1..4) {
                        webSocket.send("""{"type":"transcript","conversation_id":"test","utterance_id":$id,"text":"private $id"}""")
                    }
                }
            }
        }))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":1,"analysis_status":"ok","cumulative_risk_score":26,"detected_types":[],"display":{"context_attention":true},"context_judgment":{"status":"ok","result":{"assessment":"suspicious","risk_types":["institution_impersonation","money_transfer"],"evidence_utterance_ids":[1],"reason":"기관 사칭 후 송금을 요청했습니다."}}}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":2,"analysis_status":"ok","cumulative_risk_score":26,"detected_types":[],"display":{"context_attention":true},"context_judgment":{"status":"ok","result":{"assessment":"suspicious","risk_types":["money_transfer"],"evidence_utterance_ids":[1,2],"reason":"송금을 재촉했습니다."}}}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":3,"analysis_status":"ok","cumulative_risk_score":72,"detected_types":[],"warning":{"status":"active","message":"누적 위험 경고"},"evidence":{"recent":{"utterance_id":3},"highest":{"utterance_id":1}}}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"test","utterance_id":4,"analysis_status":"ok","cumulative_risk_score":73,"detected_types":[],"warning":{"status":"active","message":"누적 위험 경고"},"evidence":{"recent":{"utterance_id":4}}}"""))
        server.start()
        val dispatcher = Dispatchers.Default.limitedParallelism(1)
        val scope = CoroutineScope(SupervisorJob() + dispatcher)
        val states = CopyOnWriteArrayList<SttState>()
        val analysis = RiskAnalysisClient()
        val session = SttSession(scope, { true }, { FakeMicrophone() },
            mask = { _, conversation, id -> MaskedTranscript(conversationId = conversation, utteranceId = id,
                maskedText = "[PERSON] $id", hasMaskedData = true, maskedTypes = listOf("PERSON")) },
            analyze = analysis::analyze) { states.add(it) }
        try {
            withContext(dispatcher) { session.start(server.url("/api/v1/stt").toString().replaceFirst("http", "ws")) }
            waitFor { states.lastOrNull()?.risk?.cumulativeScore == 73.0 }
            val current = states.last()
            val alerts = current.liveCards.cards.filterIsInstance<LiveRiskAlert>()
            assertEquals(listOf(1, 3), alerts.map { it.firstUtteranceId })
            assertEquals(LiveRiskSource.Context, alerts[0].signal?.source)
            assertEquals(setOf("institution_impersonation", "money_transfer"), alerts[0].signal?.types)
            assertEquals(setOf("money_transfer"), alerts[0].actionTypes)
            assertEquals(listOf(1, 2), alerts[0].evidenceIds)
            val contextUpdate = states.first { it.liveCards.cards.filterIsInstance<LiveContextNotice>()
                .any { notice -> notice.reason == "송금을 재촉했습니다." } }.liveCards
            val context = contextUpdate.cards.filterIsInstance<LiveContextNotice>().single()
            assertEquals(1, context.firstUtteranceId)
            assertEquals("risk-1", contextUpdate.lastAddedKey)
            assertTrue(current.liveCards.cards.none { it is LiveContextNotice })
            assertEquals("누적 위험 경고", alerts[1].signal?.warningMessage)
            assertEquals(listOf(3, 1, 4), alerts[1].evidenceIds)
            assertEquals(LiveRiskLevel.Danger, alerts[1].rise?.current?.level)
            assertFalse(current.maskedTexts.any { "private" in it })
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
