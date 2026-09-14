package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType

internal class PasswordRule {
    fun detect(text: String): List<MaskCandidate> = CONTEXT_PATTERN.findAll(text)
        .mapNotNull { context -> valueAfter(text, context.range.last + 1) }
        .distinctBy { it.start to it.endExclusive }
        .sortedBy { it.start }
        .toList()

    private fun valueAfter(text: String, contextEnd: Int): MaskCandidate? {
        var cursor = skipWhitespace(text, contextEnd)
        if (cursor >= text.length) return null

        var hasConnector = false
        if (text[cursor] == ':' || text[cursor] == '=') {
            cursor += 1
            hasConnector = true
        } else if (text[cursor] in PARTICLES) {
            cursor += 1
            hasConnector = true
            cursor = skipWhitespace(text, cursor)
            if (cursor < text.length && (text[cursor] == ':' || text[cursor] == '=')) {
                cursor += 1
            }
        }

        cursor = skipWhitespace(text, cursor)
        if (cursor >= text.length) return null

        val openingQuote = text[cursor].takeIf { it in QUOTE_PAIRS.keys }
        val rawStart: Int
        val rawEnd: Int
        if (openingQuote != null) {
            rawStart = cursor + 1
            val closingQuote = QUOTE_PAIRS.getValue(openingQuote)
            rawEnd = text.indexOf(closingQuote, rawStart).takeIf { it >= rawStart } ?: return null
        } else {
            if (!hasConnector) return null
            rawStart = cursor
            rawEnd = findUnquotedEnd(text, rawStart)
        }

        val end = trimSpokenEnding(text, rawStart, rawEnd)
        if (end <= rawStart || end - rawStart > MAX_VALUE_LENGTH) return null
        val value = text.substring(rawStart, end)
        if (value.lowercase().let { normalized -> NEGATIVE_VALUES.any(normalized::startsWith) }) {
            return null
        }

        return MaskCandidate(
            start = rawStart,
            endExclusive = end,
            type = MaskType.PW,
            source = MaskSource.RULE,
            confidence = null,
        )
    }

    private fun skipWhitespace(text: String, from: Int): Int {
        var cursor = from
        while (cursor < text.length && text[cursor].isWhitespace()) cursor += 1
        return cursor
    }

    private fun findUnquotedEnd(text: String, start: Int): Int {
        var cursor = start
        while (cursor < text.length && !text[cursor].isWhitespace() && text[cursor] !in VALUE_BOUNDARIES) {
            cursor += 1
        }
        return cursor
    }

    private fun trimSpokenEnding(text: String, start: Int, end: Int): Int {
        val value = text.substring(start, end)
        val suffix = SPOKEN_ENDINGS.firstOrNull(value::endsWith) ?: return end
        return end - suffix.length
    }

    private companion object {
        const val MAX_VALUE_LENGTH = 64
        val CONTEXT_PATTERN = Regex(
            "(?:비밀번호|비번|패스워드|password|pin\\s*번호)",
            RegexOption.IGNORE_CASE,
        )
        val PARTICLES = setOf('은', '는', '이', '가')
        val QUOTE_PAIRS = mapOf('"' to '"', '\'' to '\'', '“' to '”', '‘' to '’')
        val VALUE_BOUNDARIES = setOf(',', '.', '?', ';', '，', '。', '？', '；')
        val SPOKEN_ENDINGS = listOf("이라고요", "이랍니다", "입니다", "이에요", "예요", "라고요")
        val NEGATIVE_VALUES = setOf(
            "기억", "변경", "재설정", "분실", "모르", "입력", "확인", "찾", "잊",
            "없", "틀", "필요", "설정", "잠금", "보내", "말해", "알려", "요청",
        )
    }
}
