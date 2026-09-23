package com.example.pic_ai_app.masking.regex

internal object EnglishChange {
    private val changes = mapOf(
        "에이" to "a",
        "비" to "b",
        "씨" to "c", "시" to "c",
        "디" to "d",
        "이" to "e",
        "에프" to "f",
        "지" to "g",
        "에이치" to "h", "에치" to "h",
        "아이" to "i",
        "제이" to "j",
        "케이" to "k",
        "엘" to "l",
        "엠" to "m",
        "엔" to "n",
        "오" to "o",
        "피" to "p",
        "큐" to "q",
        "알" to "r", "아르" to "r",
        "에스" to "s",
        "티" to "t",
        "유" to "u",
        "브이" to "v",
        "더블유" to "w", "더블류" to "w",
        "엑스" to "x",
        "와이" to "y",
        "제트" to "z",
    )

    private val expressionPattern = changes.keys
        .sortedByDescending { it.length }
        .joinToString("|") { Regex.escape(it) }

    private val expressionRegex = Regex(expressionPattern)

    // "에이비씨", "에이 비 씨"처럼 이어진 영문 발음을 하나의 구간으로 찾는다.
    // 변환 여부는 구간 내부가 아니라 구간 전체의 앞뒤 문자를 보고 결정한다.
    private val expressionSequenceRegex = Regex(
        """(?:$expressionPattern)(?:[ \t]*(?:$expressionPattern))*""",
    )

    fun change(text: String): String = change(ChangedText.from(text)).text

    fun change(changedText: ChangedText): ChangedText {
        val text = changedText.text

        return changedText.replaceMatches(expressionSequenceRegex) { sequenceMatch ->
            val before = text.previousNonGap(sequenceMatch.range.first)
            val after = text.nextNonGap(sequenceMatch.range.last + 1)

            val beforeIsHangul = before?.isHangul() == true
            val afterIsHangul = after?.isHangul() == true
            val beforeIsEmailCharacter = before?.isAsciiEmailCharacter() == true
            val afterIsEmailCharacter = after?.isAsciiEmailCharacter() == true

            val shouldChange =
                (!beforeIsHangul && !afterIsHangul) ||
                    (beforeIsHangul && afterIsEmailCharacter) ||
                    (beforeIsEmailCharacter && afterIsHangul)

            if (!shouldChange) {
                return@replaceMatches sequenceMatch.value
            }

            expressionRegex.replace(sequenceMatch.value) { expressionMatch ->
                changes.getValue(expressionMatch.value)
            }
        }
    }

    private fun String.previousNonGap(startIndex: Int): Char? {
        var index = startIndex - 1
        while (index >= 0 && this[index].isGap()) {
            index -= 1
        }
        return getOrNull(index)
    }

    private fun String.nextNonGap(startIndex: Int): Char? {
        var index = startIndex
        while (index < length && this[index].isGap()) {
            index += 1
        }
        return getOrNull(index)
    }

    private fun Char.isGap(): Boolean = this == ' ' || this == '\t'

    private fun Char.isHangul(): Boolean = this in '\uAC00'..'\uD7A3'

    private fun Char.isAsciiEmailCharacter(): Boolean =
        this in 'a'..'z' ||
            this in 'A'..'Z' ||
            this in '0'..'9' ||
            this in ".!#$%&'*+/=?^_`{|}~-@"
}
