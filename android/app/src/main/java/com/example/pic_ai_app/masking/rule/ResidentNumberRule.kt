package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

internal class ResidentNumberRule : CandidateRule {
    override fun assess(
        text: String,
        candidate: MaskCandidate,
        context: CandidateRuleContext,
    ): CandidateRuleAssessment {
        val value = RuleSupport.value(text, candidate)
        val digits = RuleSupport.digits(value)
        val formatValid = RuleSupport.isNumberLike(value) && digits.length in 11..13

        return CandidateRuleAssessment(
            formatValid = formatValid,
            accepted = formatValid &&
                (isValidResidentNumberShape(digits) || context.typeSupported),
        )
    }

    private fun isValidResidentNumberShape(digits: String): Boolean {
        if (digits.length != 13 || digits[6] !in '1'..'8') return false
        val yearPrefix = when (digits[6]) {
            '1', '2', '5', '6' -> 1900
            else -> 2000
        }
        val year = yearPrefix + digits.substring(0, 2).toInt()
        val month = digits.substring(2, 4).toInt()
        val day = digits.substring(4, 6).toInt()
        return RuleSupport.isValidDate(year, month, day)
    }
}
