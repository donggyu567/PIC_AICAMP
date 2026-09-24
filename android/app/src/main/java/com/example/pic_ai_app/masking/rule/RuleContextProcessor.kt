package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskType

internal data class ContextualCandidateGroup(
    val start: Int,
    val endExclusive: Int,
    val candidates: List<MaskCandidate>,
    val possibleTypes: Set<MaskType>,
    val directlySupportedTypes: Set<MaskType>,
    val activeContextSupportedTypes: Set<MaskType>,
    val excludedTypes: Set<MaskType>,
)

internal data class RuleContextProcessingResult(
    val groups: List<ContextualCandidateGroup>,
    val updatedContext: RuleContext,
)

internal class RuleContextProcessor {
    fun process(
        text: String,
        candidates: List<MaskCandidate>,
        context: RuleContext,
    ): RuleContextProcessingResult {
        val events = buildList {
            RuleSupport.findTypeMarkers(text).forEach { marker ->
                add(ContextEvent.Marker(marker))
            }
            groupCandidates(candidates).forEach { group ->
                add(ContextEvent.CandidateGroup(group))
            }
            RuleSupport.findSentenceBoundaries(text).forEach { position ->
                add(ContextEvent.SentenceBoundary(position))
            }
        }.sortedWith(
            compareBy<ContextEvent> { it.position }
                .thenBy { it.priority },
        )

        var updatedContext = context
        var directType: MaskType? = null
        val directlyExcludedTypes = mutableSetOf<MaskType>()
        val processedGroups = mutableListOf<ContextualCandidateGroup>()

        events.forEach { event ->
            when (event) {
                is ContextEvent.Marker -> {
                    when (event.marker.action) {
                        RuleMarkerAction.ACTIVATE -> {
                            updatedContext = updatedContext.activate(event.marker.type)
                            directType = event.marker.type
                            directlyExcludedTypes.remove(event.marker.type)
                        }

                        RuleMarkerAction.REMOVE -> {
                            updatedContext = updatedContext.remove(event.marker.type)
                            directType = null
                            directlyExcludedTypes += event.marker.type
                        }

                        RuleMarkerAction.IGNORE -> Unit
                    }
                }

                is ContextEvent.SentenceBoundary -> {
                    directType = null
                    directlyExcludedTypes.clear()
                }

                is ContextEvent.CandidateGroup -> {
                    val possibleTypes = event.candidates
                        .map { candidate -> candidate.type }
                        .toSet()

                    val directlySupportedTypes = directType
                        ?.takeIf(possibleTypes::contains)
                        ?.let(::setOf)
                        .orEmpty()

                    val activeContextTypes = if (directType == null) {
                        possibleTypes intersect updatedContext.activeTypes.toSet()
                    } else {
                        emptySet()
                    }

                    val activeContextSupportedTypes = activeContextTypes
                        .takeIf { types -> types.size == 1 }
                        .orEmpty()

                    processedGroups += ContextualCandidateGroup(
                        start = event.candidates.first().start,
                        endExclusive = event.candidates.first().endExclusive,
                        candidates = event.candidates,
                        possibleTypes = possibleTypes,
                        directlySupportedTypes = directlySupportedTypes,
                        activeContextSupportedTypes = activeContextSupportedTypes,
                        excludedTypes = possibleTypes intersect directlyExcludedTypes,
                    )
                }
            }
        }

        return RuleContextProcessingResult(
            groups = processedGroups,
            updatedContext = updatedContext,
        )
    }

    private fun groupCandidates(
        candidates: List<MaskCandidate>,
    ): List<List<MaskCandidate>> = candidates
        .groupBy { candidate ->
            CandidateRange(
                start = candidate.start,
                endExclusive = candidate.endExclusive,
            )
        }
        .values
        .sortedWith(
            compareBy<List<MaskCandidate>> { group -> group.first().start }
                .thenBy { group -> group.first().endExclusive },
        )

    private data class CandidateRange(
        val start: Int,
        val endExclusive: Int,
    )

    private sealed interface ContextEvent {
        val position: Int
        val priority: Int

        data class Marker(
            val marker: RuleTypeMarker,
        ) : ContextEvent {
            override val position: Int = marker.start
            override val priority: Int = 0
        }

        data class CandidateGroup(
            val candidates: List<MaskCandidate>,
        ) : ContextEvent {
            override val position: Int = candidates.first().start
            override val priority: Int = 1
        }

        data class SentenceBoundary(
            override val position: Int,
        ) : ContextEvent {
            override val priority: Int = 2
        }
    }
}
