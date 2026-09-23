package com.example.pic_ai_app.masking.ner

import java.io.Reader

internal data class KoElectraToken(
    val id: Long,
    val value: String,
    val start: Int,
    val endExclusive: Int,
)

internal data class KoElectraEncoding(
    val tokens: List<KoElectraToken>,
) {
    val inputIds: LongArray = tokens.map { it.id }.toLongArray()
    val attentionMask: LongArray = LongArray(tokens.size) { 1L }
}

/**
 * Offset-preserving implementation of the model's BertNormalizer,
 * BertPreTokenizer, WordPiece model, and single-sequence template processor.
 *
 * The tokenizer never truncates. The detector will split its output into model
 * windows in a later step. All offsets index the original Kotlin [String], so
 * they are UTF-16 indices even when the input contains supplementary code points.
 */
internal class KoElectraTokenizer private constructor(
    private val vocabulary: Map<String, Int>,
) {
    fun encode(text: String): KoElectraEncoding {
        val output = ArrayList<KoElectraToken>()
        output += specialToken(CLS)
        tokenizeWithAddedTokens(text, output)
        output += specialToken(SEP)
        return KoElectraEncoding(output)
    }

    private fun tokenizeWithAddedTokens(
        text: String,
        output: MutableList<KoElectraToken>,
    ) {
        var normalStart = 0
        var index = 0
        while (index < text.length) {
            val added = ADDED_TOKENS.firstOrNull { text.startsWith(it, index) }
            if (added == null) {
                index += Character.charCount(Character.codePointAt(text, index))
                continue
            }
            tokenizeNormalRange(text, normalStart, index, output)
            output += token(added, index, index + added.length)
            index += added.length
            normalStart = index
        }
        tokenizeNormalRange(text, normalStart, text.length, output)
    }

    private fun tokenizeNormalRange(
        text: String,
        rangeStart: Int,
        rangeEnd: Int,
        output: MutableList<KoElectraToken>,
    ) {
        val units = ArrayList<NormalizedUnit>()
        var index = rangeStart
        while (index < rangeEnd) {
            val codePoint = Character.codePointAt(text, index)
            val next = index + Character.charCount(codePoint)
            when {
                isRemovedByBertCleanText(codePoint) -> Unit
                isWhitespace(codePoint) -> units += NormalizedUnit(' '.code, index, next)
                else -> units += NormalizedUnit(codePoint, index, next)
            }
            index = next
        }

        val current = ArrayList<NormalizedUnit>()
        fun flush() {
            if (current.isNotEmpty()) {
                wordPiece(BasicToken(current.toList()), output)
                current.clear()
            }
        }
        for (unit in units) {
            when {
                unit.codePoint == ' '.code -> flush()
                isChineseCharacter(unit.codePoint) || isPunctuation(unit.codePoint) -> {
                    flush()
                    wordPiece(BasicToken(listOf(unit)), output)
                }
                else -> current += unit
            }
        }
        flush()
    }

    private fun wordPiece(
        basic: BasicToken,
        output: MutableList<KoElectraToken>,
    ) {
        if (basic.units.size > MAX_INPUT_CHARS_PER_WORD) {
            output += token(UNK, basic.start, basic.endExclusive)
            return
        }

        val pieces = ArrayList<KoElectraToken>()
        var start = 0
        while (start < basic.units.size) {
            var end = basic.units.size
            var match: String? = null
            while (start < end) {
                val candidate = buildString {
                    if (start > 0) append(CONTINUATION_PREFIX)
                    for (index in start until end) appendCodePoint(basic.units[index].codePoint)
                }
                if (candidate in vocabulary) {
                    match = candidate
                    break
                }
                end--
            }
            if (match == null) {
                output += token(UNK, basic.start, basic.endExclusive)
                return
            }
            pieces += token(
                value = match,
                start = basic.units[start].start,
                endExclusive = basic.units[end - 1].endExclusive,
            )
            start = end
        }
        output += pieces
    }

    private fun specialToken(value: String): KoElectraToken = token(value, 0, 0)

    private fun token(
        value: String,
        start: Int,
        endExclusive: Int,
    ): KoElectraToken = KoElectraToken(
        id = vocabulary.getValue(value).toLong(),
        value = value,
        start = start,
        endExclusive = endExclusive,
    )

    private data class NormalizedUnit(
        val codePoint: Int,
        val start: Int,
        val endExclusive: Int,
    )

    private data class BasicToken(
        val units: List<NormalizedUnit>,
    ) {
        val start: Int = units.first().start
        val endExclusive: Int = units.last().endExclusive
    }

    companion object {
        private const val PAD = "[PAD]"
        private const val UNK = "[UNK]"
        private const val CLS = "[CLS]"
        private const val SEP = "[SEP]"
        private const val MASK = "[MASK]"
        private const val CONTINUATION_PREFIX = "##"
        private const val MAX_INPUT_CHARS_PER_WORD = 100
        private val ADDED_TOKENS = listOf(PAD, UNK, CLS, SEP, MASK)

        fun fromVocab(reader: Reader): KoElectraTokenizer {
            val tokens = reader.buffered().use { it.readLines() }
            require(tokens.size == 35_000) { "Expected 35000 vocabulary entries, got ${tokens.size}" }
            val vocabulary = tokens.withIndex().associate { (id, token) -> token to id }
            require(vocabulary.size == tokens.size) { "Vocabulary contains duplicate tokens" }
            require(vocabulary[PAD] == 0)
            require(vocabulary[UNK] == 1)
            require(vocabulary[CLS] == 2)
            require(vocabulary[SEP] == 3)
            require(vocabulary[MASK] == 4)
            return KoElectraTokenizer(vocabulary)
        }

        private fun isRemovedByBertCleanText(codePoint: Int): Boolean {
            if (codePoint == 0 || codePoint == 0xfffd) return true
            return when (Character.getType(codePoint)) {
                Character.CONTROL.toInt(),
                Character.FORMAT.toInt(),
                Character.PRIVATE_USE.toInt(),
                Character.SURROGATE.toInt(),
                -> codePoint != '\t'.code && codePoint != '\n'.code && codePoint != '\r'.code
                else -> false
            }
        }

        private fun isWhitespace(codePoint: Int): Boolean =
            codePoint == ' '.code ||
                codePoint == '\t'.code ||
                codePoint == '\n'.code ||
                codePoint == '\r'.code ||
                Character.isWhitespace(codePoint) ||
                Character.isSpaceChar(codePoint)

        private fun isPunctuation(codePoint: Int): Boolean {
            if (codePoint in 33..47 || codePoint in 58..64 ||
                codePoint in 91..96 || codePoint in 123..126
            ) {
                return true
            }
            return when (Character.getType(codePoint)) {
                Character.CONNECTOR_PUNCTUATION.toInt(),
                Character.DASH_PUNCTUATION.toInt(),
                Character.START_PUNCTUATION.toInt(),
                Character.END_PUNCTUATION.toInt(),
                Character.INITIAL_QUOTE_PUNCTUATION.toInt(),
                Character.FINAL_QUOTE_PUNCTUATION.toInt(),
                Character.OTHER_PUNCTUATION.toInt(),
                -> true
                else -> false
            }
        }

        private fun isChineseCharacter(codePoint: Int): Boolean =
            codePoint in 0x4e00..0x9fff ||
                codePoint in 0x3400..0x4dbf ||
                codePoint in 0x20000..0x2a6df ||
                codePoint in 0x2a700..0x2b73f ||
                codePoint in 0x2b740..0x2b81f ||
                codePoint in 0x2b820..0x2ceaf ||
                codePoint in 0xf900..0xfaff ||
                codePoint in 0x2f800..0x2fa1f
    }
}
