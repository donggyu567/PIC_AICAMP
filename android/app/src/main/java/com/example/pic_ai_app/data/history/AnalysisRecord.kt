package com.example.pic_ai_app.data.history

import com.example.pic_ai_app.data.stt.DetectedWarning
import com.example.pic_ai_app.data.stt.RiskResult
import com.example.pic_ai_app.data.stt.SttPhase
import com.example.pic_ai_app.data.stt.SttState
import java.text.ParseException
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject

data class AnalysisRecord(
    val id: String,
    val endedAtMillis: Long,
    val result: SttState,
    val hasWarningHistory: Boolean = true,
) {
    companion object {
        fun completed(state: SttState): AnalysisRecord {
            val stamp = state.risk?.endedAt?.replace(Regex("\\.\\d+(?=Z|[+-])"), "")
            val endTime = try {
                stamp?.let { SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).parse(it)?.time }
            } catch (_: ParseException) { null }
            return AnalysisRecord(state.conversationId ?: UUID.randomUUID().toString(),
                endTime ?: System.currentTimeMillis(),
                state.copy(notices = state.notices.filterIsInstance<DetectedWarning>(), audioLevels = emptyList()))
        }
    }
}

// Only the masked transcript and fields displayed in the final result are retained.
internal fun AnalysisRecord.encode(): String = JSONObject().apply {
    put("id", id)
    put("endedAtMillis", endedAtMillis)
    put("count", result.count)
    put("maskedTexts", JSONArray(result.maskedTexts))
    if (hasWarningHistory) {
        put("warnings", JSONArray().apply {
            result.notices.filterIsInstance<DetectedWarning>().forEach { warning ->
                put(JSONObject().apply {
                    put("utteranceId", warning.utteranceId)
                    put("detectedAtMillis", warning.detectedAtMillis)
                    put("message", warning.result.warningMessage)
                    put("riskTypes", JSONArray(warning.result.riskTypes))
                    put("evidenceIds", JSONArray(warning.result.evidenceIds))
                })
            }
        })
    }
    result.risk?.let { risk ->
        put("risk", JSONObject().apply {
            put("title", risk.title)
            put("score", risk.cumulativeScore)
            put("endedAt", risk.endedAt)
            put("warning", risk.warningMessage)
            put("analysisWarning", risk.analysisWarning)
            put("reason", risk.contextReason)
            put("assessment", risk.assessment)
            put("riskTypes", JSONArray(risk.riskTypes))
            put("evidenceIds", JSONArray(risk.evidenceIds))
            put("incomplete", risk.analysisIncomplete)
        })
    }
}.toString()

private fun JSONObject.text(key: String) = opt(key) as? String

private fun JSONObject.strings(key: String): List<String> =
    getJSONArray(key).let { values -> List(values.length()) { values.getString(it) } }

internal fun decodeAnalysisRecord(raw: String): AnalysisRecord {
    val json = JSONObject(raw)
    val storedWarnings = json.optJSONArray("warnings")
    val warnings = storedWarnings?.let { rows ->
        List(rows.length()) { index ->
            val row = rows.getJSONObject(index)
            val result = RiskResult(
                currentScore = null, cumulativeScore = null, warningMessage = row.text("message"),
                contextStatus = "not_run", contextReason = null, correctionStatus = null,
                riskTypes = row.strings("riskTypes"), evidenceIds = row.ints("evidenceIds"), warningActive = true,
            )
            DetectedWarning(row.getInt("utteranceId"), row.getLong("detectedAtMillis"), result)
        }
    }.orEmpty()
    val risk = json.optJSONObject("risk")?.let {
        RiskResult(
            currentScore = null, cumulativeScore = (it.opt("score") as? Number)?.toDouble(),
            warningMessage = it.text("warning"), contextStatus = "not_run", contextReason = it.text("reason"),
            correctionStatus = null, endedAt = it.text("endedAt"), riskTypes = it.strings("riskTypes"),
            assessment = it.text("assessment"), evidenceIds = it.ints("evidenceIds"),
            analysisIncomplete = it.optBoolean("incomplete"), analysisWarning = it.text("analysisWarning"),
            title = it.text("title"),
        )
    }
    return AnalysisRecord(json.getString("id"), json.getLong("endedAtMillis"),
        SttState(phase = SttPhase.STOPPED, count = json.getInt("count"), maskedTexts = json.strings("maskedTexts"),
            risk = risk, notices = warnings), hasWarningHistory = storedWarnings != null)
}

private fun JSONObject.ints(key: String): List<Int> =
    getJSONArray(key).let { values -> List(values.length()) { values.getInt(it) } }
