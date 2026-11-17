package com.example.pic_ai_app.data.stt

import kotlin.math.roundToInt

enum class LiveRiskLevel { Normal, Suspect, Caution, Danger }

data class LiveRiskScore(val points: Int) {
    val level: LiveRiskLevel get() = when (points) {
        in 0..30 -> LiveRiskLevel.Normal
        in 31..50 -> LiveRiskLevel.Suspect
        in 51..70 -> LiveRiskLevel.Caution
        else -> LiveRiskLevel.Danger
    }

    companion object {
        fun from(score: Double?): LiveRiskScore? = score?.takeIf { it.isFinite() }
            ?.let { LiveRiskScore(it.coerceIn(0.0, 100.0).roundToInt()) }
    }
}

data class LiveScoreChange(val previous: LiveRiskScore?, val current: LiveRiskScore)

sealed interface LiveAnalysisCard {
    val key: String
}

data class LiveStartNotice(val shownAtMillis: Long, val hasScore: Boolean) : LiveAnalysisCard {
    override val key = "start"
}

data class LiveContextNotice(
    val firstUtteranceId: Int,
    val shownAtMillis: Long,
    val reason: String?,
) : LiveAnalysisCard {
    override val key = "context-$firstUtteranceId"
}

data class LiveScoreUpdate(val change: LiveScoreChange) : LiveAnalysisCard {
    override val key = "score"
}

enum class LiveRiskSource { Ai, ServerWarning, Context }

data class LiveRiskSignal(
    val source: LiveRiskSource,
    val types: Set<String>,
    val evidenceIds: List<Int>,
    val warningMessage: String? = null,
    val actionTypes: Set<String> = types,
)

data class LiveRiskAlert(
    val firstUtteranceId: Int,
    val detectedAtMillis: Long,
    val signal: LiveRiskSignal?,
    val evidenceIds: List<Int>,
    val rise: LiveScoreChange?,
    val actionTypes: Set<String> = emptySet(),
) : LiveAnalysisCard {
    override val key = "risk-$firstUtteranceId"
}

data class LiveAnalysisCards(
    val score: LiveRiskScore? = null,
    val cards: List<LiveAnalysisCard> = emptyList(),
    val lastAddedKey: String? = null,
    private val lastUtteranceId: Int = 0,
    private val lastSignal: LiveRiskSignal? = null,
    private val seenRisk: Boolean = false,
) {
    fun showStartNotice(now: Long): LiveAnalysisCards {
        if (seenRisk || cards.any { it is LiveStartNotice }) return this
        val notice = LiveStartNotice(now, hasScore = score != null)
        return copy(cards = cards + notice, lastAddedKey = notice.key)
    }

    fun record(
        utteranceId: Int, scoreValue: Double?, signal: LiveRiskSignal?, contextAttention: Boolean, now: Long,
        contextReason: String? = null,
    ): LiveAnalysisCards {
        if (utteranceId <= lastUtteranceId) return this
        val nextScore = LiveRiskScore.from(scoreValue) ?: score
        val change = nextScore?.takeIf { it != score }?.let { LiveScoreChange(score, it) }
        val rise = change?.takeIf { it.current.level > (it.previous?.level ?: LiveRiskLevel.Normal) }
        val risk = seenRisk || signal != null || contextAttention ||
            (nextScore?.level ?: LiveRiskLevel.Normal) != LiveRiskLevel.Normal
        val newRiskCard = rise != null || (signal != null && signal.startsAfter(lastSignal))
        val latestAlert = cards.filterIsInstance<LiveRiskAlert>().lastOrNull()
        val continuedRisk = if (signal != null && !newRiskCard) latestAlert?.key else null
        val currentActionTypes = signal?.actionTypes.orEmpty()
        val newActionTypes = currentActionTypes - lastSignal?.actionTypes.orEmpty()
        val actionTypes = newActionTypes.ifEmpty {
            latestAlert?.actionTypes.orEmpty().intersect(currentActionTypes).ifEmpty { currentActionTypes }
        }

        val reason = contextReason?.trim()?.takeIf { it.isNotEmpty() }
        val newContext = if (contextAttention && cards.none { it is LiveContextNotice })
            LiveContextNotice(utteranceId, now, reason) else null
        val updated = cards.mapNotNull { card ->
            when (card) {
                is LiveStartNotice -> if (risk) null else card.copy(hasScore = nextScore != null)
                is LiveContextNotice -> if (contextAttention) card.copy(reason = reason) else null
                is LiveScoreUpdate -> if (change != null) card.copy(change = change) else card
                is LiveRiskAlert -> if (signal != null && card.key == continuedRisk)
                    card.copy(
                        evidenceIds = (card.evidenceIds + signal.evidenceIds).distinct(),
                        actionTypes = actionTypes.ifEmpty { card.actionTypes },
                    ) else card
            }
        }
        val added = when {
            newRiskCard -> LiveRiskAlert(utteranceId, now, signal, signal?.evidenceIds.orEmpty(), rise, actionTypes)
            change?.previous != null && updated.none { it is LiveScoreUpdate } -> LiveScoreUpdate(change)
            else -> null
        }
        val newCards = if (added is LiveRiskAlert) listOfNotNull(newContext, added)
            else listOfNotNull(added, newContext)
        return copy(
            score = nextScore,
            cards = updated + newCards,
            lastAddedKey = newCards.lastOrNull()?.key ?: lastAddedKey,
            lastUtteranceId = utteranceId,
            lastSignal = if (continuedRisk != null && signal?.source == LiveRiskSource.ServerWarning &&
                lastSignal?.source == LiveRiskSource.Ai) {
                lastSignal.copy(actionTypes = currentActionTypes.ifEmpty { lastSignal.actionTypes })
            } else signal,
            seenRisk = risk,
        )
    }

    private fun LiveRiskSignal.startsAfter(previous: LiveRiskSignal?): Boolean {
        if (previous == null) return true
        if (source == LiveRiskSource.ServerWarning && previous.source == LiveRiskSource.Ai &&
            warningMessage != null && warningMessage == previous.warningMessage) return false
        return source != previous.source || !previous.types.containsAll(types) ||
            (source == LiveRiskSource.ServerWarning && warningMessage != previous.warningMessage)
    }
}

internal fun RiskResult.liveSignal(utteranceId: Int): LiveRiskSignal? {
    val activeMessage = warningMessage?.takeIf { warningActive == true && it.isNotBlank() }
    val contextEvidence = if (contextAttention) evidenceIds.filter { it in 1..utteranceId }.distinct() else emptyList()
    val contextTypes = if (contextAttention) riskTypes.toSet() else emptySet()
    val currentContextTypes = if (utteranceId in contextEvidence) contextTypes else emptySet()
    return when {
        detectedTypes.isNotEmpty() -> LiveRiskSignal(
            LiveRiskSource.Ai, detectedTypes, listOf(utteranceId), activeMessage,
            actionTypes = detectedTypes + currentContextTypes,
        )
        warningActive == true -> LiveRiskSignal(
            LiveRiskSource.ServerWarning,
            contextTypes,
            (warningEvidenceIds.filter { it in 1..utteranceId } + contextEvidence).distinct(),
            activeMessage,
            actionTypes = currentContextTypes,
        )
        contextEvidence.isNotEmpty() -> LiveRiskSignal(
            LiveRiskSource.Context, contextTypes, contextEvidence, actionTypes = currentContextTypes,
        )
        else -> null
    }
}
