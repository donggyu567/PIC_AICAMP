package com.example.pic_ai_app.masking.regex

internal object NumberChange {
    private val changes = mapOf(
        "공" to "0", "영" to "0",
        "일" to "1", "하나" to "1",
        "이" to "2", "둘" to "2",
        "삼" to "3", "셋" to "3",
        "사" to "4", "넷" to "4",
        "오" to "5", "다섯" to "5",
        "육" to "6", "여섯" to "6",
        "칠" to "7", "일곱" to "7",
        "팔" to "8", "여덟" to "8",
        "구" to "9", "아홉" to "9",
    )

    val expressions: Set<String>
        get() = changes.keys

    private val expressionPattern = changes.keys
        .sortedByDescending { it.length }
        .joinToString("|") { Regex.escape(it) }

    private val nonAmbiguousExpressionPattern = changes.keys
        .filterNot { it == "이" }
        .sortedByDescending { it.length }
        .joinToString("|") { Regex.escape(it) }

    // "010-1234-5678이고"의 "이"는 조사로 남기고,
    // "일이삼"의 "이"는 숫자 2로 바꾼다.
    private val numberTokenPattern =
        """(?:$nonAmbiguousExpressionPattern|(?<![0-9])이)"""

    private val expressionRegex = Regex(expressionPattern)

    // 숫자 표현이 두 개 이상 이어진 구간 안에서만 변환한다.
    private val numberLikeSequence = Regex(
        """(?:[0-9]|$numberTokenPattern)""" +
            """(?:(?:[ \t._-]*)(?:[0-9]|$numberTokenPattern))+""",
    )

    data class ChangedNumberText(
        val text: String,
        val originalOffsets: List<Int>,
    )

    fun change(text: String): String = changeWithOffsets(text).text

    fun changeWithOffsets(text: String): ChangedNumberText {
        val changed = StringBuilder(text.length)
        val originalOffsets = mutableListOf(0)
        var cursor = 0

        for (sequenceMatch in numberLikeSequence.findAll(text)) {
            while (cursor < sequenceMatch.range.first) {
                changed.append(text[cursor])
                cursor += 1
                originalOffsets.add(cursor)
            }

            val sequence = sequenceMatch.value
            var localCursor = 0

            for (match in expressionRegex.findAll(sequence)) {
                while (localCursor < match.range.first) {
                    changed.append(sequence[localCursor])
                    localCursor += 1
                    cursor += 1
                    originalOffsets.add(cursor)
                }

                changed.append(changes.getValue(match.value))

                val consumedLength = match.value.length
                localCursor += consumedLength
                cursor += consumedLength
                originalOffsets.add(cursor)
            }

            while (localCursor < sequence.length) {
                changed.append(sequence[localCursor])
                localCursor += 1
                cursor += 1
                originalOffsets.add(cursor)
            }
        }

        while (cursor < text.length) {
            changed.append(text[cursor])
            cursor += 1
            originalOffsets.add(cursor)
        }

        return ChangedNumberText(
            text = changed.toString(),
            originalOffsets = originalOffsets,
        )
    }
}
