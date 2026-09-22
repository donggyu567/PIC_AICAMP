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

    val expressions: Set<String>
        get() = changes.keys

    private val expressionRegex = Regex(
        changes.keys
            .sortedByDescending { it.length }
            .joinToString("|") { Regex.escape(it) },
    )

    fun change(text: String): String = expressionRegex.replace(text) { match ->
        changes.getValue(match.value)
    }
}
