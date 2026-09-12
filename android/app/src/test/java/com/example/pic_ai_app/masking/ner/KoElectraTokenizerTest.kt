package com.example.pic_ai_app.masking.ner

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import java.util.Base64
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class KoElectraTokenizerTest {
    @Test
    fun `matches Python input ids tokens and UTF-16 offsets`() {
        val tokenizer = Files.newBufferedReader(findVocab(), StandardCharsets.UTF_8).use {
            KoElectraTokenizer.fromVocab(it)
        }

        for (case in readGolden()) {
            val actual = tokenizer.encode(case.text)
            assertArrayEquals(case.name, case.tokens.map { it.id }.toLongArray(), actual.inputIds)
            assertArrayEquals(case.name, LongArray(case.tokens.size) { 1L }, actual.attentionMask)
            assertEquals(case.name, case.tokens.map { it.value }, actual.tokens.map { it.value })
            assertEquals(case.name, case.tokens.map { it.start }, actual.tokens.map { it.start })
            assertEquals(
                case.name,
                case.tokens.map { it.endExclusive },
                actual.tokens.map { it.endExclusive },
            )
        }
    }

    @Test
    fun `every content offset is a valid original UTF-16 range`() {
        for (case in readGolden()) {
            for (token in case.tokens.filter { it.start != it.endExclusive }) {
                assertEquals(case.name, pythonToUtf16(case.text, token.pythonStart), token.start)
                assertEquals(case.name, pythonToUtf16(case.text, token.pythonEnd), token.endExclusive)
                assertTrue(case.name, token.start in 0 until token.endExclusive)
                assertTrue(case.name, token.endExclusive <= case.text.length)
                assertFalse(case.name, splitsSurrogatePair(case.text, token.start))
                assertFalse(case.name, splitsSurrogatePair(case.text, token.endExclusive))
                if (token.value != "[UNK]") {
                    assertEquals(
                        case.name,
                        token.value.removePrefix("##"),
                        case.text.substring(token.start, token.endExclusive),
                    )
                }
            }
        }
        val surrogate = readGolden().single { it.name == "surrogate_pairs" }
        assertTrue(surrogate.tokens.any { it.pythonEnd != it.endExclusive })
    }

    @Test
    fun `does not apply tokenizer json truncation or model length truncation`() {
        val case = readGolden().single { it.name == "over_model_limit_without_truncation" }
        assertEquals(602, case.tokens.size)
        assertTrue(case.tokens.size > 512)
        val tokenizer = Files.newBufferedReader(findVocab(), StandardCharsets.UTF_8).use {
            KoElectraTokenizer.fromVocab(it)
        }
        assertEquals(case.tokens.size, tokenizer.encode(case.text).tokens.size)
    }

    @Test
    fun `vocab is the pinned 35000 entry Python source`() {
        val bytes = Files.readAllBytes(findVocab())
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        assertEquals("6e886927dfcecd22029b1ba80c10a1374740259c1067fc3a28d964b7ae2d55a7", hash)
        assertEquals(35_000, bytes.toString(StandardCharsets.UTF_8).lineSequence().count { it.isNotEmpty() })
    }

    private fun splitsSurrogatePair(text: String, offset: Int): Boolean =
        offset > 0 && offset < text.length &&
            text[offset - 1].isHighSurrogate() && text[offset].isLowSurrogate()

    private fun pythonToUtf16(text: String, pythonIndex: Int): Int {
        var codePoints = 0
        var utf16Index = 0
        while (codePoints < pythonIndex) {
            utf16Index += Character.charCount(Character.codePointAt(text, utf16Index))
            codePoints++
        }
        return utf16Index
    }

    private fun findVocab(): Path {
        val relative = Path.of("src/main/assets/models/koelectra-ko-pii-ner/vocab.txt")
        val candidates = listOf(
            relative,
            Path.of("app").resolve(relative),
            Path.of("android/app").resolve(relative),
        )
        return candidates.firstOrNull(Files::isRegularFile)
            ?: error("Cannot locate KoELECTRA vocab from ${Path.of("").toAbsolutePath()}")
    }

    private fun readGolden(): List<GoldenCase> {
        val stream = checkNotNull(javaClass.classLoader?.getResourceAsStream("koelectra_tokenizer_golden.tsv"))
        val cases = ArrayList<GoldenCase>()
        var currentName: String? = null
        var currentText: String? = null
        var currentTokens = ArrayList<GoldenToken>()
        stream.bufferedReader(StandardCharsets.UTF_8).useLines { lines ->
            for (line in lines) {
                if (line.isBlank() || line.startsWith("#")) continue
                val fields = line.split('\t')
                when (fields[0]) {
                    "CASE" -> {
                        check(currentName == null)
                        currentName = fields[1]
                        currentText = decode(fields[2])
                    }
                    "TOKEN" -> currentTokens += GoldenToken(
                        id = fields[1].toLong(),
                        value = decode(fields[2]),
                        pythonStart = fields[3].toInt(),
                        pythonEnd = fields[4].toInt(),
                        start = fields[5].toInt(),
                        endExclusive = fields[6].toInt(),
                    )
                    "END" -> {
                        cases += GoldenCase(checkNotNull(currentName), checkNotNull(currentText), currentTokens)
                        currentName = null
                        currentText = null
                        currentTokens = ArrayList()
                    }
                    else -> error("Unknown golden fixture row: ${fields[0]}")
                }
            }
        }
        check(currentName == null)
        return cases
    }

    private fun decode(value: String): String =
        String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8)

    private data class GoldenCase(
        val name: String,
        val text: String,
        val tokens: List<GoldenToken>,
    )

    private data class GoldenToken(
        val id: Long,
        val value: String,
        val pythonStart: Int,
        val pythonEnd: Int,
        val start: Int,
        val endExclusive: Int,
    )
}
