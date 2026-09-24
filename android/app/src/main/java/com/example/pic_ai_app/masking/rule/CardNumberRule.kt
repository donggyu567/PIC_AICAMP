package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

internal class CardNumberRule : CandidateRule {
    override fun assess(
        text: String,
        candidate: MaskCandidate,
        context: CandidateRuleContext,
    ): CandidateRuleAssessment {
        val value = RuleSupport.value(text, candidate)
        val digits = RuleSupport.digits(value)
        val formatValid = RuleSupport.isNumberLike(value) && digits.length in 14..16

        return CandidateRuleAssessment(
            formatValid = formatValid,
            accepted = formatValid &&
                (passesLuhn(digits) || context.typeSupported),
        )
    }

    private fun passesLuhn(digits: String): Boolean {
        var sum = 0
        var doubleDigit = false
        for (index in digits.indices.reversed()) {
            var digit = digits[index].digitToInt()
            if (doubleDigit) {
                digit *= 2
                if (digit > 9) digit -= 9
            }
            sum += digit
            doubleDigit = !doubleDigit
        }
        return sum % 10 == 0
    }
}
