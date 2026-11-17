package com.example.pic_ai_app.data.history

import com.example.pic_ai_app.data.stt.LiveAnalysisCards
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
) {
    companion object {
        fun completed(state: SttState): AnalysisRecord {
            val stamp = state.risk?.endedAt?.replace(Regex("\\.\\d+(?=Z|[+-])"), "")
            val endTime = try {
                stamp?.let { SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).parse(it)?.time }
            } catch (_: ParseException) { null }
            return AnalysisRecord(state.conversationId ?: UUID.randomUUID().toString(),
                endTime ?: System.currentTimeMillis(), state.copy(
                    recordedRiskTypes = CallRecordTitle.riskTypes(state),
                    liveCards = LiveAnalysisCards(), audioLevels = emptyList(),
                ))
        }
    }
}

// Only the masked transcript and fields displayed in the final result are retained.
internal fun AnalysisRecord.encode(): String = JSONObject().apply {
    put("id", id)
    put("endedAtMillis", endedAtMillis)
    put("count", result.count)
    put("maskedTexts", JSONArray(result.maskedTexts))
    put("recordedRiskTypes", JSONArray(result.recordedRiskTypes))
    result.risk?.let { risk ->
        put("risk", JSONObject().apply {
            put("title", risk.title)
            put("summary", risk.summary)
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
    val risk = json.optJSONObject("risk")?.let {
        RiskResult(
            currentScore = null, cumulativeScore = (it.opt("score") as? Number)?.toDouble(),
            warningMessage = it.text("warning"), contextStatus = "not_run", contextReason = it.text("reason"),
            correctionStatus = null, endedAt = it.text("endedAt"), riskTypes = it.strings("riskTypes"),
            assessment = it.text("assessment"), evidenceIds = it.getJSONArray("evidenceIds").let { ids ->
                List(ids.length()) { index -> ids.getInt(index) }
            }, analysisIncomplete = it.optBoolean("incomplete"), analysisWarning = it.text("analysisWarning"),
            title = it.text("title"),
            summary = it.text("summary"),
        )
    }
    val recordedTypes = json.optJSONArray("recordedRiskTypes")?.let { values ->
        List(values.length()) { values.getString(it) }.toSet()
    }.orEmpty()
    return AnalysisRecord(json.getString("id"), json.getLong("endedAtMillis"),
        SttState(phase = SttPhase.STOPPED, count = json.getInt("count"), maskedTexts = json.strings("maskedTexts"),
            risk = risk, recordedRiskTypes = recordedTypes))
}
