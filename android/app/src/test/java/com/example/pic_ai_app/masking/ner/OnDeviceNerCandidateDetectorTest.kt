package com.example.pic_ai_app.masking.ner

import ai.onnxruntime.OnnxJavaType
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import kotlin.coroutines.Continuation
import kotlin.coroutines.EmptyCoroutineContext
import kotlin.coroutines.startCoroutine
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class OnDeviceNerCandidateDetectorTest {
    @Test
    fun `close before initialization prevents later resource creation`() {
        val detector = OnDeviceNerCandidateDetector(
            { throw AssertionError("Tokenizer must not be created") },
            { throw AssertionError("Inference must not be created") },
        )
        detector.close()
        detector.close()
        assertThrows(IllegalStateException::class.java) { runSuspend { detector.detect("text") } }
        assertThrows(IllegalStateException::class.java) { detector.modelMetadata() }
    }

    @Test
    fun `close waits for active inference and closes resources exactly once`() {
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val closeStarted = CountDownLatch(1)
        var closeCount = 0
        val engine = object : NerWindowInference {
            override val metadata get() = error("Not used")
            override fun predict(window: NerTokenWindow): IntArray {
                entered.countDown()
                check(release.await(5, TimeUnit.SECONDS))
                check(closeCount == 0) { "Resource closed during inference" }
                return IntArray(window.modelTokens.size)
            }
            override fun close() { closeCount++ }
        }
        val detector = OnDeviceNerCandidateDetector({ tokenizer() }, { engine })
        val executor = Executors.newFixedThreadPool(2)
        try {
            val detection = executor.submit { runSuspend { detector.detect("text") } }
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            val closing = executor.submit { closeStarted.countDown(); detector.close() }
            assertTrue(closeStarted.await(5, TimeUnit.SECONDS))
            assertThrows(TimeoutException::class.java) { closing.get(100, TimeUnit.MILLISECONDS) }
            release.countDown()
            detection.get(5, TimeUnit.SECONDS)
            closing.get(5, TimeUnit.SECONDS)
            detector.close()
            assertEquals(1, closeCount)
            assertThrows(IllegalStateException::class.java) { runSuspend { detector.detect("text") } }
        } finally {
            release.countDown()
            executor.shutdownNow()
            executor.awaitTermination(5, TimeUnit.SECONDS)
            detector.close()
        }
    }

    @Test
    fun `NAME and ADDRESS predictions preserve exact UTF-16 spans`() {
        val text = "😀 김민수는 서울특별시 강남구에 산다."
        val name = text.indexOf("김민수") until text.indexOf("김민수") + "김민수".length
        val addressStart = text.indexOf("서울특별시")
        val address = addressStart until addressStart + "서울특별시 강남구".length
        val detector = detector { window -> labelsFor(window, name, address) }

        val candidates = runSuspend { detector.detect(text) }

        assertEquals(listOf("김민수", "서울특별시 강남구"), candidates.map { text.substring(it.start, it.endExclusive) })
        assertEquals(listOf(MaskType.PERSON, MaskType.ADDRESS), candidates.map { it.type })
        assertTrue(candidates.all { it.source == MaskSource.NER })
        assertEquals(name.first, candidates[0].start)
        assertEquals(name.last + 1, candidates[0].endExclusive)
    }

    @Test
    fun `multiple windows merge duplicate predictions into one candidate`() {
        val prefix = "가 ".repeat(500)
        val text = prefix + "김민수 " + "나 ".repeat(80)
        val start = text.indexOf("김민수")
        val name = start until start + "김민수".length
        val seenWindows = mutableListOf<Int>()
        val detector = detector { window ->
            seenWindows += window.index
            labelsFor(window, name, null)
        }

        val candidates = runSuspend { detector.detect(text) }

        assertTrue(seenWindows.size > 1)
        assertEquals(1, candidates.size)
        assertEquals("김민수", text.substring(candidates.single().start, candidates.single().endExclusive))
    }

    @Test
    fun `ordinary sentence returns an empty list`() {
        val detector = detector { window -> IntArray(window.modelTokens.size) }
        assertTrue(runSuspend { detector.detect("오늘은 날씨가 맑습니다.") }.isEmpty())
    }

    @Test
    fun `tokenizer and inference are lazy and reused across detect calls`() {
        var tokenizerCreates = 0
        var inferenceCreates = 0
        val detector = OnDeviceNerCandidateDetector(
            tokenizerProvider = {
                tokenizerCreates++
                tokenizer()
            },
            inferenceProvider = {
                inferenceCreates++
                FakeInference { IntArray(it.modelTokens.size) }
            },
        )

        runSuspend { detector.detect("첫 문장") }
        runSuspend { detector.detect("두 번째 문장") }

        assertEquals(1, tokenizerCreates)
        assertEquals(1, inferenceCreates)
    }

    @Test
    fun `inference errors propagate unchanged`() {
        val expected = IllegalStateException("inference failed")
        val detector = detector { throw expected }

        val thrown = assertThrows(IllegalStateException::class.java) {
            runSuspend { detector.detect("문장") }
        }
        assertSame(expected, thrown)
    }

    private fun detector(predict: (NerTokenWindow) -> IntArray) =
        OnDeviceNerCandidateDetector({ tokenizer() }, { FakeInference(predict) })

    private fun labelsFor(
        window: NerTokenWindow,
        name: IntRange?,
        address: IntRange?,
    ): IntArray {
        val labels = IntArray(window.modelTokens.size)
        applyEntity(window, labels, name, NerLabelSchema.B_NAME, NerLabelSchema.I_NAME)
        applyEntity(window, labels, address, NerLabelSchema.B_ADDRESS, NerLabelSchema.I_ADDRESS)
        return labels
    }

    private fun applyEntity(
        window: NerTokenWindow,
        labels: IntArray,
        range: IntRange?,
        begin: Int,
        inside: Int,
    ) {
        if (range == null) return
        var started = false
        window.modelTokens.forEachIndexed { index, token ->
            if (token.start >= range.first && token.endExclusive <= range.last + 1 && token.endExclusive > token.start) {
                labels[index] = if (started) inside else begin
                started = true
            }
        }
    }

    private fun tokenizer(): KoElectraTokenizer =
        Files.newBufferedReader(findVocab(), StandardCharsets.UTF_8).use(KoElectraTokenizer::fromVocab)

    private fun findVocab(): Path {
        val relative = Path.of("src/main/assets/models/koelectra-ko-pii-ner/vocab.txt")
        return listOf(relative, Path.of("app").resolve(relative), Path.of("android/app").resolve(relative))
            .firstOrNull(Files::isRegularFile)
            ?: error("Cannot locate KoELECTRA vocab")
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

    private class FakeInference(
        private val prediction: (NerTokenWindow) -> IntArray,
    ) : NerWindowInference {
        override val metadata = NerModelMetadata(
            inputs = mapOf(
                "input_ids" to NerTensorMetadata(OnnxJavaType.INT64, longArrayOf(-1, -1)),
                "attention_mask" to NerTensorMetadata(OnnxJavaType.INT64, longArrayOf(-1, -1)),
            ),
            outputName = "logits",
            output = NerTensorMetadata(OnnxJavaType.FLOAT, longArrayOf(-1, -1, 59)),
        )

        override fun predict(window: NerTokenWindow): IntArray = prediction(window)
    }
}
