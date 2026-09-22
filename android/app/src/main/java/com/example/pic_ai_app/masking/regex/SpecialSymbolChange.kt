package com.example.pic_ai_app.masking.regex

internal object SpecialSymbolChange {
    private val changes = mapOf(
        "골뱅이" to "@", "고뱅이" to "@", "골배이" to "@", "골뱅니" to "@",
        "앳사인" to "@", "앳 사인" to "@", "앳" to "@",
        "언더스코어" to "_", "언더바" to "_",
        "하이픈" to "-", "대시" to "-",
        "플러스" to "+",
        "닷" to ".", "점" to ".", "쩜" to ".",
        "샵" to "#", "해시" to "#",
        "퍼센트" to "%",
        "별표" to "*",
    )

    val expressions: Set<String>
        get() = changes.keys

    val emailAtExpressions: Set<String> = setOf(
        "골뱅이",
        "고뱅이",
        "골배이",
        "골뱅니",
    )

    val emailLocalSeparatorExpressions: Set<String> = setOf(
        "언더스코어",
        "언더바",
        "하이픈",
        "대시",
        "플러스",
        "닷",
        "점",
        "쩜",
        "샵",
        "해시",
        "퍼센트",
        "별표",
    )

    val emailDomainSeparatorExpressions: Set<String> = setOf(
        "닷",
        "점",
        "쩜",
    )

    private val expressionRegex = Regex(
        changes.keys
            .sortedByDescending { it.length }
            .joinToString("|") { Regex.escape(it) },
    )

    fun change(text: String): String = expressionRegex.replace(text) { match ->
        changes.getValue(match.value)
    }
}
