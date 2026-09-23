package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

internal class BirthRule : CandidateRule {
    override fun assess(
        text: String,
        candidate: MaskCandidate,
        context: CandidateRuleContext,
    ): CandidateRuleAssessment {
        val value = RuleSupport.value(text, candidate)

        val date = RuleSupport.parseDate(value)
        val validDate = date != null &&
            RuleSupport.isValidDate(date.first, date.second, date.third)
        if (validDate) {
            return CandidateRuleAssessment(formatValid = true, accepted = true)
        }

        if (value.contains('월') && value.contains('일')) {
            val monthDay = parseMonthDay(value)
            val formatValid = monthDay != null &&
                isValidMonthDay(monthDay.first, monthDay.second)
            return CandidateRuleAssessment(
                formatValid = formatValid,
                accepted = formatValid && context.typeSupported,
            )
        }

        val formatValid = RuleSupport.isNumberLike(value) &&
            RuleSupport.digits(value).length in 5..8
        return CandidateRuleAssessment(
            formatValid = formatValid,
            accepted = formatValid && context.typeSupported,
        )
    }

    private fun parseMonthDay(value: String): Pair<Int, Int>? {
        val match = MONTH_DAY_WITH_UNITS.matchEntire(value) ?: return null
        val month = match.groupValues[1].toIntOrNull() ?: return null
        val day = match.groupValues[2].toIntOrNull() ?: return null
        return month to day
    }

    private fun isValidMonthDay(month: Int, day: Int): Boolean {
        if (month !in 1..12) return false
        val daysInMonth = when (month) {
            2 -> 29
            4, 6, 9, 11 -> 30
            else -> 31
        }
        return day in 1..daysInMonth
    }

    private companion object {
        val MONTH_DAY_WITH_UNITS = Regex(
            """^\s*([0-9]{1,2})\s*월\s*([0-9]{1,2})\s*일\s*$""",
        )
    }
}
