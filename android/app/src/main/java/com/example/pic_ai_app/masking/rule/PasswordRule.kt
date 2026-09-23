package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.regex.PasswordPatterns

internal class PasswordRule : CandidateRule {
    override fun assess(
        text: String,
        candidate: MaskCandidate,
        context: CandidateRuleContext,
    ): CandidateRuleAssessment {
        val match = PasswordPatterns.findPasswords(text)
            .firstOrNull { password ->
                password.start == candidate.start &&
                    password.endExclusive == candidate.endExclusive
            }
            ?: return CandidateRuleAssessment(formatValid = false, accepted = false)

        val value = match.changedValue
        val formatValid = value.length in CONTEXT_MIN_LENGTH..MAX_LENGTH
        val strongPasswordShape =
            value.length in STRONG_MIN_LENGTH..MAX_LENGTH &&
                value.any(Char::isLetter) &&
                value.any(Char::isDigit) &&
                value.any(::isSpecialCharacter)

        return CandidateRuleAssessment(
            formatValid = formatValid,
            accepted = formatValid &&
                (strongPasswordShape || context.typeSupported),
        )
    }

    private fun isSpecialCharacter(character: Char): Boolean =
        character in SPECIAL_CHARACTERS

    private companion object {
        const val CONTEXT_MIN_LENGTH = 3
        const val STRONG_MIN_LENGTH = 8
        const val MAX_LENGTH = 64

        val SPECIAL_CHARACTERS = setOf(
            '!', '@', '#', '$', '%', '^', '&', '*',
            '(', ')', '_', '+', '=', '.', '-',
        )
    }
}
