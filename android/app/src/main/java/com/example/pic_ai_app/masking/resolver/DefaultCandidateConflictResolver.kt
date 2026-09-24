package com.example.pic_ai_app.masking.resolver

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import com.example.pic_ai_app.masking.rule.RuleCandidateDecision
import com.example.pic_ai_app.masking.rule.RuleValidationResult

class DefaultCandidateConflictResolver :
    CandidateConflictResolver {

    override fun resolve(
        nerCandidates: List<MaskCandidate>,
        ruleResult: RuleValidationResult,
    ): List<MaskCandidate> = resolve(
        nerCandidates + selectRuleCandidates(ruleResult),
    )

    override fun resolve(
        candidates: List<MaskCandidate>,
    ): List<MaskCandidate> {
        if (candidates.isEmpty()) return emptyList()

        val unique = deduplicate(candidates)
        val normalized = mergeOverlappingCandidatesOfSameKind(unique)
        val indexed = normalized
            .sortedWith(stableCandidateOrder)
            .mapIndexed { id, candidate -> IndexedCandidate(id, candidate) }
        val boundaries = indexed
            .flatMap { listOf(it.candidate.start, it.candidate.endExclusive) }
            .distinct()
            .sorted()

        val segments = mutableListOf<ResolvedSegment>()
        for (index in 0 until boundaries.lastIndex) {
            val start = boundaries[index]
            val endExclusive = boundaries[index + 1]
            val active = indexed.filter {
                it.candidate.start < endExclusive && it.candidate.endExclusive > start
            }
            if (active.isEmpty()) continue

            val winner = active.minWithOrNull(winnerOrder)
                ?: error("Resolver failed to select an active candidate")
            val previous = segments.lastOrNull()
            if (previous != null &&
                previous.endExclusive == start &&
                previous.winner.id == winner.id
            ) {
                previous.endExclusive = endExclusive
            } else {
                segments += ResolvedSegment(start, endExclusive, winner)
            }
        }

        return segments.map { segment ->
            val original = segment.winner.candidate
            original.copy(
                start = segment.start,
                endExclusive = segment.endExclusive,
                confidence = original.confidence.takeIf {
                    segment.start == original.start &&
                        segment.endExclusive == original.endExclusive
                },
            )
        }
    }

    private fun selectRuleCandidates(
        ruleResult: RuleValidationResult,
    ): List<MaskCandidate> {
        if (ruleResult.decisions.isEmpty()) return ruleResult.candidates

        val candidatesByRange = ruleResult.candidates.groupBy { candidate ->
            CandidateRange(candidate.start, candidate.endExclusive)
        }
        val decidedRanges = ruleResult.decisions.map { decision ->
            CandidateRange(decision.start, decision.endExclusive)
        }.toSet()

        val selected = ruleResult.decisions.flatMap { decision ->
            val range = CandidateRange(decision.start, decision.endExclusive)
            selectRange(decision, candidatesByRange[range].orEmpty())
        }
        val undecided = ruleResult.candidates.filterNot { candidate ->
            CandidateRange(candidate.start, candidate.endExclusive) in decidedRanges
        }
        return selected + undecided
    }

    private fun selectRange(
        decision: RuleCandidateDecision,
        acceptedCandidates: List<MaskCandidate>,
    ): List<MaskCandidate> {
        val acceptedTypes = acceptedCandidates.map { it.type }.toSet()
        val supportedAcceptedTypes = decision.supportedTypes intersect acceptedTypes
        val acceptedButExcluded =
            decision.acceptedTypesBeforeExclusion intersect decision.excludedTypes

        return when {
            supportedAcceptedTypes.size == 1 -> acceptedCandidates.filter {
                it.type in supportedAcceptedTypes
            }
            supportedAcceptedTypes.size > 1 -> listOf(maskedCandidate(decision))
            acceptedButExcluded.isNotEmpty() -> listOf(maskedCandidate(decision))
            acceptedTypes.size == 1 -> acceptedCandidates
            acceptedTypes.size > 1 -> listOf(maskedCandidate(decision))
            decision.formatValidTypes.size > 1 -> listOf(maskedCandidate(decision))
            else -> emptyList()
        }
    }

    private fun maskedCandidate(decision: RuleCandidateDecision): MaskCandidate =
        MaskCandidate(
            start = decision.start,
            endExclusive = decision.endExclusive,
            type = MaskType.MASKED,
            source = MaskSource.REGEX,
            confidence = null,
        )

    private fun deduplicate(candidates: List<MaskCandidate>): List<MaskCandidate> =
        candidates
            .groupBy { CandidateIdentity(it.start, it.endExclusive, it.type) }
            .values
            .map { duplicates -> duplicates.minWithOrNull(representativeOrder)!! }

    private fun mergeOverlappingCandidatesOfSameKind(
        candidates: List<MaskCandidate>,
    ): List<MaskCandidate> {
        val result = mutableListOf<MaskCandidate>()
        candidates
            .groupBy { it.type to it.source }
            .toSortedMap(
                compareBy<Pair<MaskType, MaskSource>> { it.first.ordinal }
                    .thenBy { it.second.ordinal },
            )
            .values
            .forEach { group ->
                val sorted = group.sortedWith(
                    compareBy<MaskCandidate> { it.start }
                        .thenBy { it.endExclusive },
                )
                var current = sorted.first()
                for (next in sorted.drop(1)) {
                    if (next.start < current.endExclusive) {
                        current = current.copy(
                            endExclusive = maxOf(current.endExclusive, next.endExclusive),
                            confidence = null,
                        )
                    } else {
                        result += current
                        current = next
                    }
                }
                result += current
            }
        return result
    }

    private fun sourceRank(candidate: MaskCandidate): Int = when (candidate.type) {
        MaskType.PERSON, MaskType.ADDRESS -> when (candidate.source) {
            MaskSource.NER -> 0
            MaskSource.RULE -> 1
            MaskSource.REGEX -> 2
        }
        MaskType.PW -> when (candidate.source) {
            MaskSource.RULE -> 0
            MaskSource.REGEX -> 1
            MaskSource.NER -> 2
        }
        else -> when (candidate.source) {
            MaskSource.REGEX -> 0
            MaskSource.RULE -> 1
            MaskSource.NER -> 2
        }
    }

    private fun typeRank(type: MaskType): Int = when (type) {
        MaskType.PW -> 0
        MaskType.RRN -> 1
        MaskType.CARD_NUMBER -> 2
        MaskType.ACCOUNT_NUMBER -> 3
        MaskType.PHONE_NUMBER -> 4
        MaskType.EMAIL -> 5
        MaskType.BIRTH -> 6
        MaskType.MASKED -> 7
        MaskType.ADDRESS -> 8
        MaskType.PERSON -> 9
    }

    private val representativeOrder =
        Comparator<MaskCandidate> { left, right ->
            compareValues(sourceRank(left), sourceRank(right))
                .takeIf { it != 0 }
                ?: compareConfidenceWithinSameSource(left, right)
                    .takeIf { it != 0 }
                ?: stableCandidateOrder.compare(left, right)
        }

    private val stableCandidateOrder =
        compareBy<MaskCandidate> { it.start }
            .thenByDescending { it.endExclusive }
            .thenBy { typeRank(it.type) }
            .thenBy { sourceRank(it) }
            .thenByDescending { it.confidence ?: Float.NEGATIVE_INFINITY }

    private val winnerOrder =
        Comparator<IndexedCandidate> { left, right ->
            compareValues(typeRank(left.candidate.type), typeRank(right.candidate.type))
                .takeIf { it != 0 }
                ?: compareValues(sourceRank(left.candidate), sourceRank(right.candidate))
                    .takeIf { it != 0 }
                ?: compareConfidenceWithinSameSource(left.candidate, right.candidate)
                    .takeIf { it != 0 }
                ?: compareValues(left.candidate.start, right.candidate.start)
                    .takeIf { it != 0 }
                ?: compareValues(right.candidate.endExclusive, left.candidate.endExclusive)
                    .takeIf { it != 0 }
                ?: compareValues(left.id, right.id)
        }

    private fun compareConfidenceWithinSameSource(
        left: MaskCandidate,
        right: MaskCandidate,
    ): Int {
        if (left.source != right.source) return 0
        return compareValues(
            right.confidence ?: Float.NEGATIVE_INFINITY,
            left.confidence ?: Float.NEGATIVE_INFINITY,
        )
    }

    private data class CandidateIdentity(
        val start: Int,
        val endExclusive: Int,
        val type: MaskType,
    )

    private data class CandidateRange(
        val start: Int,
        val endExclusive: Int,
    )

    private data class IndexedCandidate(
        val id: Int,
        val candidate: MaskCandidate,
    )

    private data class ResolvedSegment(
        val start: Int,
        var endExclusive: Int,
        val winner: IndexedCandidate,
    )
}
