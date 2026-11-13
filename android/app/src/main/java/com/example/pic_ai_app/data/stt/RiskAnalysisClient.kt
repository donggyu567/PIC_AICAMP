package com.example.pic_ai_app.data.stt

import com.example.pic_ai_app.domain.model.MaskedTranscript
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.suspendCancellableCoroutine
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

data class RiskResult(
    val currentScore: Double?,
    val cumulativeScore: Double?,
    val warningMessage: String?,
    val contextStatus: String,
    val contextReason: String?,
    val correctionStatus: String?,
    val endedAt: String? = null,
    val riskTypes: List<String> = emptyList(),
    val assessment: String? = null,
    val evidenceIds: List<Int> = emptyList(),
    val analysisIncomplete: Boolean = false,
    val analysisWarning: String? = null,
)

class RiskAnalysisClient(private val tokenForServer: (String) -> String? = { null }) {
    private val client = OkHttpClient.Builder().callTimeout(60, TimeUnit.SECONDS)
        .followRedirects(false).followSslRedirects(false).build()

    private fun authenticated(request: Request): Request {
        val token = tokenForServer(request.url.toString()) ?: return request
        return request.newBuilder().header("Authorization", "Bearer $token").build()
    }

    suspend fun analyze(websocketUrl: String, utterance: MaskedTranscript): RiskResult {
        val base = endpoint(websocketUrl, "/api/v1/utterances/analyze")
        val payload = JSONObject()
            .put("schema_version", utterance.schemaVersion)
            .put("conversation_id", utterance.conversationId)
            .put("utterance_id", utterance.utteranceId)
            .put("masking_status", "succeeded")
            .put("masked_text", utterance.maskedText)
            .put("has_masked_data", utterance.hasMaskedData)
            .put("masked_types", JSONArray(utterance.maskedTypes))
        val request = Request.Builder().url(base)
            .post(payload.toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()
        return parseResult(execute(request), utterance.conversationId, utterance.utteranceId)
    }

    /** 조회가 404여도 최초 요청이 처리 중일 수 있으므로 같은 발화만 다시 보낸다. */
    suspend fun recover(websocketUrl: String, utterance: MaskedTranscript): RiskResult {
        val url = endpoint(websocketUrl, "/api/v1/utterances/results").toHttpUrl()
            .newBuilder().addQueryParameter("conversation_id", utterance.conversationId)
            .addQueryParameter("utterance_id", utterance.utteranceId.toString()).build()
        val (status, data) = execute(Request.Builder().url(url).get().build())
        if (status == 404) {
            try { return analyze(websocketUrl, utterance) }
            catch (error: HttpStatusException) {
                if (error.status != 409) throw error
                return parseResult(execute(Request.Builder().url(url).get().build()), utterance.conversationId, utterance.utteranceId)
            }
        }
        if (status != 200 || data == null) throw IOException("result unavailable")
        if (data.optString("analysis_status") != "error") return parseResult(status to data, utterance.conversationId, utterance.utteranceId)
        require(data.optString("conversation_id") == utterance.conversationId && data.optInt("utterance_id", -1) == utterance.utteranceId)
        val body = JSONObject().put("conversation_id", utterance.conversationId).put("utterance_id", utterance.utteranceId)
        val request = Request.Builder().url(endpoint(websocketUrl, "/api/v1/utterances/analyze/retry"))
            .post(body.toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()
        return parseResult(execute(request), utterance.conversationId, utterance.utteranceId)
    }

    private class HttpStatusException(val status: Int) : IOException("HTTP $status")

    suspend fun registerDevice(websocketUrl: String): String {
        val request = Request.Builder().url(endpoint(websocketUrl, "/api/v1/devices/register"))
            .post("".toRequestBody("application/json; charset=utf-8".toMediaType())).build()
        val (status, data) = execute(request, authenticate = false)
        if (status != 201 || data == null) throw IOException("device registration unavailable")
        return data.getString("token")
    }

    private suspend fun execute(request: Request, authenticate: Boolean = true): Pair<Int, JSONObject?> = suspendCancellableCoroutine { continuation ->
        val call = client.newCall(if (authenticate) authenticated(request) else request)
        continuation.invokeOnCancellation { call.cancel() }
        call.enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                if (continuation.isActive) continuation.resumeWithException(IOException("request unavailable"))
            }
            override fun onResponse(call: Call, response: Response) {
                response.use {
                    try {
                        val body = response.body?.string().orEmpty()
                        val json = if (response.isSuccessful) JSONObject(body) else null
                        if (continuation.isActive) continuation.resume(response.code to json)
                    } catch (_: Exception) {
                        if (continuation.isActive) continuation.resumeWithException(IOException("invalid response"))
                    }
                }
            }
        })
    }

    private fun parseResult(response: Pair<Int, JSONObject?>, conversation: String, utterance: Int): RiskResult {
        val (status, data) = response
        if (status !in 200..299) throw HttpStatusException(status)
        if (data == null || data.optString("conversation_id") != conversation ||
            data.optInt("utterance_id", -1) != utterance || data.optString("analysis_status") != "ok")
            throw IOException("analysis result unavailable")
        return readRisk(data)
    }

    private fun readRisk(data: JSONObject): RiskResult {
        fun score(name: String): Double? {
            if (data.isNull(name)) return null
            val value = data.getDouble(name)
            require(value.isFinite() && value in 0.0..100.0)
            return value
        }
        val context = data.optJSONObject("context_judgment")
        val judgment = context?.takeIf { it.optString("status") == "ok" }?.optJSONObject("result")
        val types = judgment?.optJSONArray("risk_types")
        val evidence = judgment?.optJSONArray("evidence_utterance_ids")
        return RiskResult(score("current_risk_score"), score("cumulative_risk_score"),
            data.optJSONObject("warning")?.optString("message")?.takeIf { it.isNotBlank() },
            context?.optString("status") ?: "not_run",
            judgment?.optString("reason")?.takeIf { it.isNotBlank() },
            if (data.isNull("correction_status")) null else data.optString("correction_status"),
            riskTypes = types?.let { List(it.length()) { index -> it.optString(index) } }.orEmpty(),
            assessment = judgment?.optString("assessment"),
            evidenceIds = evidence?.let { List(it.length()) { index -> it.optInt(index) } }.orEmpty(),
            analysisIncomplete = data.optString("analysis_status") == "error")
    }

    private fun endpoint(websocketUrl: String, path: String): String {
        val uri = java.net.URI(websocketUrl)
        require(uri.scheme == "ws" || uri.scheme == "wss")
        return java.net.URI(if (uri.scheme == "wss") "https" else "http", null,
            uri.host, uri.port, path, null, null).toString()
    }

    suspend fun withdraw(websocketUrl: String, conversationId: String) {
        val body = JSONObject().put("conversation_id", conversationId)
        val request = Request.Builder().url(endpoint(websocketUrl, "/api/v1/conversations/withdraw"))
            .post(body.toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()
        val (status, data) = execute(request)
        if (status != 200 || data?.optString("conversation_id") != conversationId ||
            data.optString("status") != "deleted") throw IOException("deletion unavailable")
    }

    suspend fun finish(websocketUrl: String, conversationId: String, lastUtteranceId: Int): RiskResult {
        val body = JSONObject().put("conversation_id", conversationId)
            .put("last_utterance_id", lastUtteranceId)
        val request = Request.Builder().url(endpoint(websocketUrl, "/api/v1/conversations/end"))
            .post(body.toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()
        val (status, data) = execute(request)
        if (status != 200 || data == null) throw IOException("finish unavailable")
        val last = data.getJSONObject("last_analysis")
        require(data.getString("conversation_id") == conversationId &&
            data.getString("conversation_status") == "ended" &&
            last.getString("conversation_id") == conversationId &&
            last.getInt("utterance_id") == lastUtteranceId &&
            last.getString("analysis_status") in setOf("ok", "error"))
        val risk = readRisk(last)
        return risk.copy(
            endedAt = data.optString("ended_at").takeIf { !data.isNull("ended_at") && it.isNotBlank() },
            analysisWarning = risk.warningMessage,
            warningMessage = data.optJSONObject("warning")?.optString("message")?.takeIf { it.isNotBlank() } ?: risk.warningMessage,
        )
    }
}
