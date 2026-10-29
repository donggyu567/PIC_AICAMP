package com.example.pic_ai_app.masking.ner

import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class NerPostProcessorTest {
    @Test
    fun `one model window holds up to 510 content tokens`() {
        for (size in listOf(0, 12, 510)) {
            val (text, encoding) = syntheticEncoding(size)
            val windows = NerSlidingWindow.create(text, encoding)
            assertEquals(1, windows.size)
            assertEquals(0, windows.single().contentStart)
            assertEquals(size, windows.single().contentEndExclusive)
            assertEquals(size + 2, windows.single().modelTokens.size)
            assertTrue(windows.single().modelTokens.size <= 512)
        }
    }

    @Test
    fun `long input uses 510 content overlap 64 and stride 446`() {
        val (text511, encoding511) = syntheticEncoding(511)
        val windows511 = NerSlidingWindow.create(text511, encoding511)
        assertEquals(listOf(0 to 510, 446 to 511), windows511.map { it.contentStart to it.contentEndExclusive })

        val (text957, encoding957) = syntheticEncoding(957)
        val windows957 = NerSlidingWindow.create(text957, encoding957)
        assertEquals(
            listOf(0 to 510, 446 to 956, 892 to 957),
            windows957.map { it.contentStart to it.contentEndExclusive },
        )
        assertEquals(446, NerSlidingWindow.STRIDE)
        assertEquals(64, windows957[0].contentEndExclusive - windows957[1].contentStart)
        assertEquals(64, windows957[1].contentEndExclusive - windows957[2].contentStart)
    }

    @Test
    fun `overlap prediction chooses the window with more minimum context`() {
        val (text, encoding) = syntheticEncoding(600)
        val windows = NerSlidingWindow.create(text, encoding)
        val predictions = windows.map { window ->
            prediction(window) { global ->
                when {
                    global == 450 && window.index == 0 -> "B-NAME"
                    global == 450 && window.index == 1 -> "B-ADDRESS"
                    global == 505 && window.index == 0 -> "B-NAME"
                    global == 505 && window.index == 1 -> "B-ADDRESS"
                    else -> "O"
                }
            }
        }

        val merged = NerSlidingWindow.merge(windows, predictions)
        assertEquals(NerLabelSchema.B_NAME, merged[450].labelId)
        assertEquals(0, merged[450].sourceWindowIndex)
        assertEquals(NerLabelSchema.B_ADDRESS, merged[505].labelId)
        assertEquals(1, merged[505].sourceWindowIndex)
    }

    @Test
    fun `BIO entities crossing window boundaries are decoded once globally`() {
        val (text, encoding) = syntheticEncoding(600)
        val windows = NerSlidingWindow.create(text, encoding)
        val predictions = windows.map { window ->
            prediction(window) { global ->
                when (global) {
                    444 -> "B-ADDRESS"
                    in 445..448 -> "I-ADDRESS"
                    508 -> "B-NAME"
                    in 509..511 -> "I-NAME"
                    else -> "O"
                }
            }
        }

        val candidates = NerBioDecoder.decode(text, NerSlidingWindow.merge(windows, predictions))
        assertEquals(2, candidates.size)
        assertEquals(444, candidates[0].start)
        assertEquals(449, candidates[0].endExclusive)
        assertEquals(MaskType.ADDRESS, candidates[0].type)
        assertEquals(508, candidates[1].start)
        assertEquals(512, candidates[1].endExclusive)
        assertEquals(MaskType.PERSON, candidates[1].type)
        assertEquals("가".repeat(5), text.substring(candidates[0].start, candidates[0].endExclusive))
        assertEquals("가".repeat(4), text.substring(candidates[1].start, candidates[1].endExclusive))
        assertTrue(candidates.all { it.source == MaskSource.NER })
    }

    @Test
    fun `orphan inside tags safely start new supported entities`() {
        val text = "김민 서울"
        val predictions = listOf(
            tokenPrediction(0, 0, 1, "I-NAME"),
            tokenPrediction(1, 1, 2, "I-NAME"),
            tokenPrediction(2, 3, 5, "I-ADDRESS"),
        )

        val candidates = NerBioDecoder.decode(text, predictions)
        assertEquals(listOf("김민", "서울"), candidates.map { text.substring(it.start, it.endExclusive) })
        assertEquals(listOf(MaskType.PERSON, MaskType.ADDRESS), candidates.map { it.type })
    }

    @Test
    fun `unsupported labels including SECRET do not create candidates`() {
        val text = "비밀 장소 회사"
        val predictions = listOf(
            tokenPrediction(0, 0, 2, "B-SECRET"),
            tokenPrediction(1, 3, 5, "B-PLACE"),
            tokenPrediction(2, 6, 8, "B-ORGANIZATION"),
        )
        assertTrue(NerBioDecoder.decode(text, predictions).isEmpty())
    }

    @Test
    fun `Korean and emoji spans use exact original UTF-16 substrings`() {
        val text = "😀 김민준 🚀 서울시 강남구 123"
        val tokenizer = Files.newBufferedReader(findVocab(), StandardCharsets.UTF_8).use {
            KoElectraTokenizer.fromVocab(it)
        }
        val encoding = tokenizer.encode(text)
        val windows = NerSlidingWindow.create(text, encoding)
        val predictions = windows.map { window ->
            prediction(window) { global ->
                when (encoding.tokens[global + 1].start) {
                    3 -> "B-NAME"
                    5 -> "I-NAME"
                    10 -> "B-ADDRESS"
                    12, 14, 18 -> "I-ADDRESS"
                    else -> "O"
                }
            }
        }

        val candidates = NerBioDecoder.decode(text, NerSlidingWindow.merge(windows, predictions))
        assertEquals(listOf("김민준", "서울시 강남구 123"), candidates.map { text.substring(it.start, it.endExclusive) })
        assertEquals(3, candidates[0].start)
        assertEquals(6, candidates[0].endExclusive)
        assertEquals(10, candidates[1].start)
        assertEquals(21, candidates[1].endExclusive)
    }

    @Test
    fun `invalid and surrogate-splitting offsets fail closed`() {
        val invalid = KoElectraEncoding(
            listOf(special("[CLS]", 2), KoElectraToken(100, "x", 0, 2), special("[SEP]", 3)),
        )
        assertThrows(IllegalArgumentException::class.java) {
            NerSlidingWindow.create("x", invalid)
        }

        val splitSurrogate = KoElectraEncoding(
            listOf(special("[CLS]", 2), KoElectraToken(1, "[UNK]", 1, 2), special("[SEP]", 3)),
        )
        assertThrows(IllegalArgumentException::class.java) {
            NerSlidingWindow.create("😀", splitSurrogate)
        }
    }

    private fun prediction(
        window: NerTokenWindow,
        label: (globalIndex: Int) -> String,
    ): NerWindowPrediction {
        val labels = IntArray(window.modelTokens.size) { NerLabelSchema.OUTSIDE }
        for (local in 0 until window.contentSize) {
            labels[local + 1] = labelId(label(window.contentStart + local))
        }
        return NerWindowPrediction(window.index, labels)
    }

    private fun syntheticEncoding(contentSize: Int): Pair<String, KoElectraEncoding> {
        val text = "가".repeat(contentSize)
        val tokens = ArrayList<KoElectraToken>(contentSize + 2)
        tokens += special("[CLS]", 2)
        repeat(contentSize) { index -> tokens += KoElectraToken(100L, "가", index, index + 1) }
        tokens += special("[SEP]", 3)
        return text to KoElectraEncoding(tokens)
    }

    private fun tokenPrediction(
        index: Int,
        start: Int,
        endExclusive: Int,
        label: String,
    ): NerTokenPrediction = NerTokenPrediction(
        globalTokenIndex = index,
        token = KoElectraToken(100L, "token", start, endExclusive),
        labelId = labelId(label),
        sourceWindowIndex = 0,
    )

    private fun special(value: String, id: Long) = KoElectraToken(id, value, 0, 0)

    private fun labelId(label: String): Int = when (label) {
        "O" -> NerLabelSchema.OUTSIDE
        "B-ADDRESS" -> NerLabelSchema.B_ADDRESS
        "I-ADDRESS" -> NerLabelSchema.I_ADDRESS
        "B-NAME" -> NerLabelSchema.B_NAME
        "I-NAME" -> NerLabelSchema.I_NAME
        "B-SECRET" -> 47
        "B-PLACE" -> 39
        "B-ORGANIZATION" -> 33
        else -> error("Unknown test label: $label")
    }

    private fun findVocab(): Path {
        val relative = Path.of("src/main/assets/models/koelectra-ko-pii-ner/vocab.txt")
        return listOf(relative, Path.of("app").resolve(relative), Path.of("android/app").resolve(relative))
            .firstOrNull(Files::isRegularFile)
            ?: error("Cannot locate KoELECTRA vocab")
    }
}
