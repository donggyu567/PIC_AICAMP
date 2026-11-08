package com.example.pic_ai_app.data.stt

import com.example.pic_ai_app.domain.model.MaskedTranscript
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class RiskAnalysisClientTest {
    private fun utterance() = MaskedTranscript(conversationId="call", utteranceId=1,
        maskedText="[EMAIL] 주소입니다.", hasMaskedData=true, maskedTypes=listOf("EMAIL"))

    @Test fun sendsMaskedContractAndParsesSuccessfulResponse() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().setBody("""{"conversation_id":"call","utterance_id":1,"analysis_status":"ok","correction_status":"ok","current_risk_score":30.0,"cumulative_risk_score":45.0,"warning":{"message":"주의"},"context_judgment":{"status":"ok","result":{"reason":"의심 맥락"}}}"""))
        server.start()
        try {
            val result = RiskAnalysisClient().analyze(server.url("/api/v1/stt").toString().replaceFirst("http", "ws"), utterance())
            val request = server.takeRequest()
            val body = JSONObject(request.body.readUtf8())
            assertEquals("/api/v1/utterances/analyze", request.path)
            assertEquals("succeeded", body.getString("masking_status"))
            assertEquals("[EMAIL] 주소입니다.", body.getString("masked_text"))
            assertEquals("EMAIL", body.getJSONArray("masked_types").getString(0))
            assertFalse(body.has("raw_text"))
            assertEquals(45.0, result.cumulativeScore!!, 0.001)
            assertEquals("의심 맥락", result.contextReason)
        } finally { server.shutdown() }
    }

    @Test fun failedAiIsNotDisplayedAsZero() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().setBody("""{"conversation_id":"call","utterance_id":1,"analysis_status":"error","cumulative_risk_score":null}"""))
        server.start()
        try {
            try {
                RiskAnalysisClient().analyze(server.url("/api/v1/stt").toString().replaceFirst("http", "ws"), utterance())
                fail("failed analysis must not be displayed as a zero score")
            } catch (_: java.io.IOException) { }
        } finally { server.shutdown() }
    }
    @Test fun finishSendsLastIdAndReadsFinalResult() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().setBody("""{"conversation_id":"call","conversation_status":"ended","warning":{"message":"종료"},"last_analysis":{"conversation_id":"call","utterance_id":1,"analysis_status":"ok","current_risk_score":30,"cumulative_risk_score":45,"correction_status":"ok","context_judgment":{"status":"ok","result":{"reason":"근거"}}}}"""))
        server.start()
        try {
            val result = RiskAnalysisClient().finish(server.url("/api/v1/stt").toString().replaceFirst("http", "ws"), "call", 1)
            val request = server.takeRequest()
            val body = JSONObject(request.body.readUtf8())
            assertEquals("/api/v1/conversations/end", request.path)
            assertEquals("call", body.getString("conversation_id"))
            assertEquals(1, body.getInt("last_utterance_id"))
            assertEquals(45.0, result.cumulativeScore!!, 0.001)
            assertEquals("종료", result.warningMessage)
        } finally { server.shutdown() }
    }

    @Test fun recoveryUsesSavedResultOrRetriesStoredAiFailure() = runBlocking {
        val server = MockWebServer()
        val success = """{"conversation_id":"call","utterance_id":1,"analysis_status":"ok","cumulative_risk_score":45}"""
        val failure = """{"conversation_id":"call","utterance_id":1,"analysis_status":"error"}"""
        server.enqueue(MockResponse().setBody(success))
        server.enqueue(MockResponse().setBody(failure))
        server.enqueue(MockResponse().setBody(success))
        server.start()
        try {
            val url = server.url("/api/v1/stt").toString().replaceFirst("http", "ws")
            val client = RiskAnalysisClient()
            assertEquals(45.0, client.recover(url, utterance()).cumulativeScore!!, 0.001)
            assertTrue(server.takeRequest().path!!.startsWith("/api/v1/utterances/results?"))
            assertEquals(45.0, client.recover(url, utterance()).cumulativeScore!!, 0.001)
            assertTrue(server.takeRequest().path!!.startsWith("/api/v1/utterances/results?"))
            val retry = server.takeRequest()
            assertEquals("/api/v1/utterances/analyze/retry", retry.path)
            assertEquals(1, JSONObject(retry.body.readUtf8()).getInt("utterance_id"))
        } finally { server.shutdown() }
    }

    @Test fun missingResultAndDuplicateSubmissionReadsSavedResult() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().setResponseCode(404))
        server.enqueue(MockResponse().setResponseCode(409))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"call","utterance_id":1,"analysis_status":"ok","cumulative_risk_score":45}"""))
        server.start()
        try {
            val url = server.url("/api/v1/stt").toString().replaceFirst("http", "ws")
            assertEquals(45.0, RiskAnalysisClient().recover(url, utterance()).cumulativeScore!!, 0.001)
            assertTrue(server.takeRequest().path!!.startsWith("/api/v1/utterances/results?"))
            val submitted = server.takeRequest()
            assertEquals("/api/v1/utterances/analyze", submitted.path)
            assertEquals(1, JSONObject(submitted.body.readUtf8()).getInt("utterance_id"))
            assertTrue(server.takeRequest().path!!.startsWith("/api/v1/utterances/results?"))
        } finally { server.shutdown() }
    }

    @Test fun withdrawalRequiresMatchingDeletionResponse() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().setBody("""{"conversation_id":"call","status":"deleted"}"""))
        server.enqueue(MockResponse().setResponseCode(503))
        server.start()
        try {
            val url = server.url("/api/v1/stt").toString().replaceFirst("http", "ws")
            val client = RiskAnalysisClient()
            client.withdraw(url, "call")
            val request = server.takeRequest()
            assertEquals("/api/v1/conversations/withdraw", request.path)
            assertEquals("call", JSONObject(request.body.readUtf8()).getString("conversation_id"))
            try { client.withdraw(url, "call"); fail("server failure must not count as deletion") }
            catch (_: java.io.IOException) { }
        } finally { server.shutdown() }
    }

    @Test fun sendsDeviceTokenOnAnalysisAndWithdrawal() = runBlocking {
        val server = MockWebServer()
        server.enqueue(MockResponse().setBody("""{"conversation_id":"call","utterance_id":1,"analysis_status":"ok","cumulative_risk_score":45}"""))
        server.enqueue(MockResponse().setBody("""{"conversation_id":"call","status":"deleted"}"""))
        server.start()
        try {
            val url = server.url("/api/v1/stt").toString().replaceFirst("http", "ws")
            val client = RiskAnalysisClient { "test-device-token" }
            client.analyze(url, utterance())
            client.withdraw(url, "call")
            assertEquals("Bearer test-device-token", server.takeRequest().getHeader("Authorization"))
            assertEquals("Bearer test-device-token", server.takeRequest().getHeader("Authorization"))
        } finally { server.shutdown() }
    }

}
