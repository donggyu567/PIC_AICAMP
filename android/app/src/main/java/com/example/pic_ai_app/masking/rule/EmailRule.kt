package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.regex.EmailPatterns

internal class EmailRule : CandidateRule {
    override fun assess(
        text: String,
        candidate: MaskCandidate,
        context: CandidateRuleContext,
    ): CandidateRuleAssessment {
        val match = EmailPatterns.findEmails(text)
            .firstOrNull { email ->
                email.start == candidate.start &&
                    email.endExclusive == candidate.endExclusive
            }
            ?: return CandidateRuleAssessment(formatValid = false, accepted = false)

        val changedValue = match.changedValue.filterNot { character ->
            character == ' ' || character == '\t'
        }

        val formatValid = changedValue.length <= MAX_EMAIL_LENGTH
        return CandidateRuleAssessment(
            formatValid = formatValid,
            accepted = formatValid &&
                (EMAIL_PATTERN.matches(changedValue) || context.typeSupported),
        )
    }

    private companion object {
        const val MAX_EMAIL_LENGTH = 254
        val EMAIL_PATTERN = Regex(
            "^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@" +
                "[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?" +
                "(?:\\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$",
        )
    }
}
