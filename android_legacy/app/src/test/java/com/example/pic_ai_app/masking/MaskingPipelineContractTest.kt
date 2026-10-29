package com.example.pic_ai_app.masking

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import com.example.pic_ai_app.masking.ner.NerCandidateDetector
import com.example.pic_ai_app.masking.regex.RegexCandidateDetector
import com.example.pic_ai_app.masking.renderer.DefaultMaskedTextRenderer
import com.example.pic_ai_app.masking.renderer.MaskedTextRenderer
import com.example.pic_ai_app.masking.resolver.CandidateConflictResolver
import com.example.pic_ai_app.masking.rule.NumberMaskingRuleEngine
import kotlin.coroutines.Continuation
import kotlin.coroutines.EmptyCoroutineContext
import kotlin.coroutines.startCoroutine
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class MaskingPipelineContractTest {
    @Test
    fun `pipeline preserves detector validation resolution and rendering order`() {
        val calls = mutableListOf<String>()
        val text = "김민수 전화 010-1234-5678 주소 서울특별시"
        val person = candidate(text, "김민수", MaskType.PERSON, MaskSource.NER)
        val address = candidate(text, "서울특별시", MaskType.ADDRESS, MaskSource.NER)
        val phone = candidate(text, "010-1234-5678", MaskType.PHONE_NUMBER, MaskSource.REGEX)
        val nerCandidates = listOf(address, person)
        val regexCandidates = listOf(phone)
        val renderer = RecordingRenderer(calls)
        val pipeline = pipeline(
            calls = calls,
            nerCandidates = nerCandidates,
            regexCandidates = regexCandidates,
            validate = { received ->
                assertEquals(regexCandidates, received)
                received
            },
            resolve = { received ->
                assertEquals(nerCandidates + regexCandidates, received)
                received
            },
            renderer = renderer,
        )

        val masked = runSuspend { pipeline.mask(text) }

        assertEquals(listOf("ner", "regex", "rule", "resolver", "renderer"), calls)
        assertEquals(nerCandidates + regexCandidates, renderer.received)
        assertEquals("[PERSON] 전화 [PHONE_NUMBER] 주소 [ADDRESS]", masked)
    }

    @Test
    fun `no candidates returns the original text through the full pipeline`() {
        val calls = mutableListOf<String>()
        val text = "마스킹할 개인정보가 없습니다."
        val pipeline = pipeline(calls, emptyList(), emptyList())

        assertEquals(text, runSuspend { pipeline.mask(text) })
        assertEquals(listOf("ner", "regex", "rule", "resolver", "renderer"), calls)
    }

    @Test
    fun `unsorted candidates from different sources are rendered by original offsets`() {
        val calls = mutableListOf<String>()
        val text = "서울의 김민수 계좌는 123-456입니다"
        val address = candidate(text, "서울", MaskType.ADDRESS, MaskSource.NER)
        val person = candidate(text, "김민수", MaskType.PERSON, MaskSource.NER)
        val account = candidate(text, "123-456", MaskType.ACCOUNT_NUMBER, MaskSource.RULE)
        val pipeline = pipeline(
            calls = calls,
            nerCandidates = listOf(person, address),
            regexCandidates = listOf(candidate(text, "123-456", MaskType.ACCOUNT_NUMBER, MaskSource.REGEX)),
            validate = { listOf(account) },
            resolve = { it.reversed() },
        )

        assertEquals(
            "[ADDRESS]의 [PERSON] 계좌는 [ACCOUNT_NUMBER]입니다",
            runSuspend { pipeline.mask(text) },
        )
    }

    @Test
    fun `resolver owns overlap handling before renderer`() {
        val calls = mutableListOf<String>()
        val text = "김민수0101234"
        val person = MaskCandidate(0, 3, MaskType.PERSON, MaskSource.NER)
        val phone = MaskCandidate(2, text.length, MaskType.PHONE_NUMBER, MaskSource.REGEX)
        var resolverSawOverlap = false
        val renderer = RecordingRenderer(calls)
        val pipeline = pipeline(
            calls = calls,
            nerCandidates = listOf(person),
            regexCandidates = listOf(phone),
            resolve = { received ->
                resolverSawOverlap = received[1].start < received[0].endExclusive
                listOf(person)
            },
            renderer = renderer,
        )

        assertEquals("[PERSON]0101234", runSuspend { pipeline.mask(text) })
        assertTrue(resolverSawOverlap)
        assertEquals(listOf(person), renderer.received)
    }

    @Test
    fun `renderer rejects overlap leaked by resolver`() {
        val text = "김민수0101234"
        val person = MaskCandidate(0, 3, MaskType.PERSON, MaskSource.NER)
        val phone = MaskCandidate(2, text.length, MaskType.PHONE_NUMBER, MaskSource.REGEX)
        val pipeline = pipeline(
            calls = mutableListOf(),
            nerCandidates = listOf(person),
            regexCandidates = listOf(phone),
            resolve = { it },
        )

        assertThrows(IllegalArgumentException::class.java) {
            runSuspend { pipeline.mask(text) }
        }
    }

    private fun pipeline(
        calls: MutableList<String>,
        nerCandidates: List<MaskCandidate>,
        regexCandidates: List<MaskCandidate>,
        validate: (List<MaskCandidate>) -> List<MaskCandidate> = { it },
        resolve: (List<MaskCandidate>) -> List<MaskCandidate> = { it },
        renderer: MaskedTextRenderer = RecordingRenderer(calls),
    ) = MaskingPipeline(
        nerDetector = object : NerCandidateDetector {
            override suspend fun detect(text: String): List<MaskCandidate> {
                calls += "ner"
                return nerCandidates
            }
        },
        regexDetector = object : RegexCandidateDetector {
            override fun detect(text: String): List<MaskCandidate> {
                calls += "regex"
                return regexCandidates
            }
        },
        ruleEngine = object : NumberMaskingRuleEngine {
            override fun validate(text: String, candidate: List<MaskCandidate>): List<MaskCandidate> {
                calls += "rule"
                return validate(candidate)
            }
        },
        conflictResolver = object : CandidateConflictResolver {
            override fun resolve(candidates: List<MaskCandidate>): List<MaskCandidate> {
                calls += "resolver"
                return resolve(candidates)
            }
        },
        renderer = renderer,
    )

    private fun candidate(
        text: String,
        value: String,
        type: MaskType,
        source: MaskSource,
    ): MaskCandidate {
        val start = text.indexOf(value)
        check(start >= 0)
        return MaskCandidate(start, start + value.length, type, source)
    }

    private fun <T> runSuspend(block: suspend () -> T): T {
        var completed: Result<T>? = null
        block.startCoroutine(object : Continuation<T> {
            override val context = EmptyCoroutineContext
            override fun resumeWith(result: Result<T>) {
                completed = result
            }
        })
        return requireNotNull(completed) { "Test coroutine unexpectedly suspended" }.getOrThrow()
    }

    private class RecordingRenderer(
        private val calls: MutableList<String>,
    ) : MaskedTextRenderer {
        private val delegate = DefaultMaskedTextRenderer()
        var received: List<MaskCandidate>? = null
            private set

        override fun render(text: String, candidate: List<MaskCandidate>): String {
            calls += "renderer"
            received = candidate
            return delegate.render(text, candidate)
        }
    }
}
