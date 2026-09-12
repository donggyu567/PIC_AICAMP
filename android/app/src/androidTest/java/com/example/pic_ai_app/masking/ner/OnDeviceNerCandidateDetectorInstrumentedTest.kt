package com.example.pic_ai_app.masking.ner

import ai.onnxruntime.OnnxJavaType
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.pic_ai_app.masking.model.MaskType
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OnDeviceNerCandidateDetectorInstrumentedTest {
    @Test
    fun loadsFp32ModelValidatesMetadataAndRunsInference() = runBlocking {
        val assets = InstrumentationRegistry.getInstrumentation().targetContext.assets
        OnDeviceNerCandidateDetector(assets).use { detector ->
            val metadata = detector.modelMetadata()
            assertEquals(setOf("input_ids", "attention_mask"), metadata.inputs.keys)
            assertTrue(metadata.inputs.values.all { it.type == OnnxJavaType.INT64 })
            assertEquals("logits", metadata.outputName)
            assertEquals(OnnxJavaType.FLOAT, metadata.output.type)
            assertEquals(59L, metadata.output.shape.last())

            val text = "김민수는 서울특별시 강남구에 산다."
            val candidates = detector.detect(text)
            candidates.forEach { candidate ->
                assertTrue(candidate.start >= 0)
                assertTrue(candidate.endExclusive > candidate.start)
                assertTrue(candidate.endExclusive <= text.length)
                text.substring(candidate.start, candidate.endExclusive)
            }
            assertTrue(candidates.any {
                it.type == MaskType.PERSON && text.substring(it.start, it.endExclusive) == "김민수"
            })
            // The pinned FP32 model labels this location as PLACE, not ADDRESS.
            assertEquals(1, candidates.size)
            val addressText = "제 주소는 서울특별시 강남구 테헤란로 152입니다."
            val address = detector.detect(addressText).single()
            assertEquals(MaskType.ADDRESS, address.type)
            assertEquals(6, address.start)
            assertEquals(24, address.endExclusive)
            assertEquals("서울특별시 강남구 테헤란로 152", addressText.substring(address.start, address.endExclusive))
        }
    }

    @Test
    fun runsEveryLongInputWindowWithoutDuplicateCandidates() = runBlocking {
        val assets = InstrumentationRegistry.getInstrumentation().targetContext.assets
        val text = "오늘은 평범한 하루입니다. ".repeat(220)
        val tokenizer = assets.open("models/koelectra-ko-pii-ner/vocab.txt").reader(Charsets.UTF_8).use {
            KoElectraTokenizer.fromVocab(it)
        }
        val contentCount = tokenizer.encode(text).tokens.size - 2
        assertTrue(contentCount > 510)
        val starts = mutableListOf<Int>()
        val ends = mutableListOf<Int>()
        val ort = OrtNerWindowInference(assets)
        val recording = object : NerWindowInference by ort {
            override fun predict(window: NerTokenWindow): IntArray {
                starts += window.contentStart
                ends += window.contentEndExclusive
                return ort.predict(window)
            }
        }
        OnDeviceNerCandidateDetector({ tokenizer }, { recording }).use { detector ->
            val candidates = detector.detect(text)
            val expectedCount = 1 + (contentCount - 510 + 445) / 446
            assertEquals((0 until expectedCount).map { it * 446 }, starts)
            assertEquals(contentCount, ends.last())
            assertTrue(ends.zip(starts).all { (end, start) -> end - start <= 510 })
            assertEquals(
                candidates.size,
                candidates.map { Triple(it.start, it.endExclusive, it.type) }.distinct().size,
            )
        }
    }
}
