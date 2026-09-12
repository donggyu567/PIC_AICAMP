package com.example.pic_ai_app.masking.resolver

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType

class DefaultCandidateConflictResolver :
    CandidateConflictResolver {

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
        MaskType.ADDRESS -> 7
        MaskType.PERSON -> 8
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
