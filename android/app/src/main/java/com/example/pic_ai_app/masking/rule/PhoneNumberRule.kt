package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

internal class PhoneNumberRule : CandidateRule {
    override fun assess(
        text: String,
        candidate: MaskCandidate,
        context: CandidateRuleContext,
    ): CandidateRuleAssessment {
        val value = RuleSupport.value(text, candidate)
        val digits = RuleSupport.digits(value)
        val formatValid = RuleSupport.isNumberLike(value) && digits.length in 8..11

        return CandidateRuleAssessment(
            formatValid = formatValid,
            accepted = formatValid &&
                (RuleSupport.isPlausiblePhone(digits) || context.typeSupported),
        )
    }
}
