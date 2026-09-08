package com.example.pic_ai_app.masking.resolver

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DefaultCandidateConflictResolverTest {
    private val resolver = DefaultCandidateConflictResolver()

    @Test
    fun `returns empty for empty input`() {
        assertTrue(resolver.resolve(emptyList()).isEmpty())
    }

    @Test
    fun `deduplicates identical candidates deterministically`() {
        val lowerConfidence = candidate(0, 3, MaskType.PERSON, MaskSource.NER, 0.71f)
        val higherConfidence = candidate(0, 3, MaskType.PERSON, MaskSource.NER, 0.93f)

        assertEquals(listOf(higherConfidence), resolver.resolve(listOf(lowerConfidence, higherConfidence)))
    }

    @Test
    fun `selects password for the same range based on type policy`() {
        val phone = candidate(2, 8, MaskType.PHONE_NUMBER, MaskSource.REGEX)
        val password = candidate(2, 8, MaskType.PW, MaskSource.RULE)

        assertEquals(listOf(password), resolver.resolve(listOf(phone, password)))
    }

    @Test
    fun `keeps uncovered tails when candidates partially overlap`() {
        val account = candidate(0, 6, MaskType.ACCOUNT_NUMBER, MaskSource.REGEX)
        val phone = candidate(4, 10, MaskType.PHONE_NUMBER, MaskSource.REGEX)

        val result = resolver.resolve(listOf(phone, account))

        assertEquals(
            listOf(
                account,
                phone.copy(start = 6, confidence = null),
            ),
            result,
        )
        assertCovers(result, 0, 10)
    }

    @Test
    fun `splits an outer candidate around a higher-priority password`() {
        val phone = candidate(0, 10, MaskType.PHONE_NUMBER, MaskSource.REGEX)
        val password = candidate(3, 6, MaskType.PW, MaskSource.RULE)

        val result = resolver.resolve(listOf(phone, password))

        assertEquals(
            listOf(
                phone.copy(endExclusive = 3, confidence = null),
                password,
                phone.copy(start = 6, confidence = null),
            ),
            result,
        )
        assertCovers(result, 0, 10)
    }

    @Test
    fun `does not merge adjacent non-overlapping candidates`() {
        val first = candidate(0, 3, MaskType.PERSON, MaskSource.NER)
        val second = candidate(3, 8, MaskType.PERSON, MaskSource.NER)

        assertEquals(listOf(first, second), resolver.resolve(listOf(second, first)))
    }

    @Test
    fun `merges overlapping candidates of the same type and source`() {
        val first = candidate(0, 6, MaskType.ADDRESS, MaskSource.NER, 0.8f)
        val second = candidate(4, 10, MaskType.ADDRESS, MaskSource.NER, 0.9f)

        assertEquals(
            listOf(candidate(0, 10, MaskType.ADDRESS, MaskSource.NER)),
            resolver.resolve(listOf(second, first)),
        )
    }

    @Test
    fun `produces the same result regardless of input order`() {
        val candidates = listOf(
            candidate(4, 10, MaskType.PHONE_NUMBER, MaskSource.REGEX),
            candidate(0, 6, MaskType.ACCOUNT_NUMBER, MaskSource.REGEX),
            candidate(3, 5, MaskType.PW, MaskSource.RULE),
        )

        assertEquals(
            resolver.resolve(candidates),
            resolver.resolve(candidates.reversed()),
        )
    }

    private fun assertCovers(candidates: List<MaskCandidate>, start: Int, endExclusive: Int) {
        assertEquals(start, candidates.first().start)
        assertEquals(endExclusive, candidates.last().endExclusive)
        candidates.zipWithNext().forEach { (left, right) ->
            assertEquals(left.endExclusive, right.start)
            assertTrue(left.endExclusive <= right.start)
        }
    }

    private fun candidate(
        start: Int,
        endExclusive: Int,
        type: MaskType,
        source: MaskSource,
        confidence: Float? = null,
    ) = MaskCandidate(start, endExclusive, type, source, confidence)
}
