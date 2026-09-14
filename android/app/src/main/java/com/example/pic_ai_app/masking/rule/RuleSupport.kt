package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import kotlin.math.max
import kotlin.math.min

internal fun interface CandidateRule {
    fun validate(
        text: String,
        candidate: MaskCandidate,
    ): MaskCandidate?
}

internal object RuleSupport {
    private const val CONTEXT_RADIUS = 36
    private val sentenceBoundaries = setOf('\n', '\r', '.', '?', '!')
    private val allowedNumberCharacters = Regex("^[0-9+()\\-\\s]+$")

    fun value(text: String, candidate: MaskCandidate): String =
        text.substring(candidate.start, candidate.endExclusive)

    fun digits(value: String): String = value.filter(Char::isDigit)

    fun isNumberLike(value: String): Boolean =
        value.isNotBlank() && allowedNumberCharacters.matches(value)

    fun localContext(
        text: String,
        candidate: MaskCandidate,
    ): String {
        val roughStart = max(0, candidate.start - CONTEXT_RADIUS)
        val roughEnd = min(text.length, candidate.endExclusive + CONTEXT_RADIUS)

        val boundaryBefore = text.lastIndexOfAny(
            chars = sentenceBoundaries.toCharArray(),
            startIndex = candidate.start - 1,
        )
        val boundaryAfter = text.indexOfAny(
            chars = sentenceBoundaries.toCharArray(),
            startIndex = candidate.endExclusive,
        )

        val start = max(roughStart, boundaryBefore + 1)
        val end = if (boundaryAfter == -1) roughEnd else min(roughEnd, boundaryAfter)
        return text.substring(start, end).lowercase()
    }

    fun containsAny(context: String, keywords: Set<String>): Boolean =
        keywords.any(context::contains)

    fun reclassify(
        candidate: MaskCandidate,
        type: MaskType,
    ): MaskCandidate = candidate.copy(
        type = type,
        source = MaskSource.RULE,
        confidence = null,
    )

    fun isPlausiblePhone(digits: String): Boolean {
        val domestic = when {
            digits.startsWith("82") -> "0${digits.drop(2)}"
            else -> digits
        }
        return when {
            domestic.matches(Regex("01[016789][0-9]{7,8}")) -> true
            domestic.matches(Regex("02[0-9]{7,8}")) -> true
            domestic.matches(Regex("0[3-8][0-9][0-9]{7,8}")) -> true
            domestic.matches(Regex("1[568][0-9]{6}")) -> true
            else -> false
        }
    }

    fun isValidDate(
        year: Int,
        month: Int,
        day: Int,
    ): Boolean {
        if (year !in 1900..2099 || month !in 1..12) return false
        val leap = year % 400 == 0 || (year % 4 == 0 && year % 100 != 0)
        val daysInMonth = when (month) {
            2 -> if (leap) 29 else 28
            4, 6, 9, 11 -> 30
            else -> 31
        }
        return day in 1..daysInMonth
    }

    fun parseDate(value: String): Triple<Int, Int, Int>? {
        val groups = Regex("[0-9]+").findAll(value).map { it.value }.toList()
        if (groups.size >= 3) {
            val rawYear = groups[0].toIntOrNull() ?: return null
            val year = normalizeYear(rawYear, groups[0].length)
            val month = groups[1].toIntOrNull() ?: return null
            val day = groups[2].toIntOrNull() ?: return null
            return Triple(year, month, day)
        }

        val compact = digits(value)
        return when (compact.length) {
            8 -> Triple(
                compact.substring(0, 4).toInt(),
                compact.substring(4, 6).toInt(),
                compact.substring(6, 8).toInt(),
            )
            6 -> Triple(
                normalizeYear(compact.substring(0, 2).toInt(), 2),
                compact.substring(2, 4).toInt(),
                compact.substring(4, 6).toInt(),
            )
            else -> null
        }
    }

    private fun normalizeYear(year: Int, length: Int): Int = when {
        length >= 4 -> year
        year <= 30 -> 2000 + year
        else -> 1900 + year
    }
}
