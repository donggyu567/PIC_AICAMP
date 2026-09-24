package com.example.pic_ai_app.masking.regex

internal object SpecialSymbolChange {
    private val changes = mapOf(
        "골뱅이" to "@", "골벵이" to "@", "고뱅이" to "@", "골배이" to "@", "골뱅니" to "@",
        "앳사인" to "@", "앳 사인" to "@", "앳" to "@",
        "언더스코어" to "_", "언더바" to "_",
        "하이픈" to "-", "대시" to "-",
        "플러스" to "+",
        "닷" to ".", "닫" to ".", "점" to ".", "쩜" to ".",
        "샵" to "#", "해시" to "#",
        "퍼센트" to "%",
        "별표" to "*",
    )

    private val expressionRegex = Regex(
        changes.keys
            .sortedByDescending { it.length }
            .joinToString("|") { Regex.escape(it) },
    )

    fun change(text: String): String = change(ChangedText.from(text)).text

    fun change(changedText: ChangedText): ChangedText =
        changedText.replaceMatches(expressionRegex) { match ->
            changes.getValue(match.value)
        }
}
