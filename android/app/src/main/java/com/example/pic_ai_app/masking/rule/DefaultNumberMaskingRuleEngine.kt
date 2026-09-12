package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType

class DefaultNumberMaskingRuleEngine :
    NumberMaskingRuleEngine {

    private val rules: Map<MaskType, CandidateRule> = mapOf(
        MaskType.PHONE_NUMBER to PhoneNumberRule(),
        MaskType.RRN to ResidentNumberRule(),
        MaskType.CARD_NUMBER to CardNumberRule(),
        MaskType.ACCOUNT_NUMBER to AccountNumberRule(),
        MaskType.BIRTH to BirthRule(),
        MaskType.EMAIL to EmailRule(),
    )
    private val passwordRule = PasswordRule()

    override fun validate(
        text: String,
        candidate: List<MaskCandidate>,
    ): List<MaskCandidate> {
        candidate.forEach { validateRange(text, it) }

        val validated = candidate.mapNotNull { current ->
            val rule = rules[current.type]
                ?: throw IllegalArgumentException(
                    "Unsupported candidate type for number masking rule: ${current.type}",
                )
            rule.validate(text, current)
        }

        return (validated + passwordRule.detect(text))
            .distinctBy {
                CandidateKey(
                    start = it.start,
                    endExclusive = it.endExclusive,
                    type = it.type,
                    source = it.source,
                )
            }
            .sortedWith(
                compareBy<MaskCandidate> { it.start }
                    .thenBy { it.endExclusive }
                    .thenBy { it.type.ordinal }
                    .thenBy { it.source.ordinal },
            )
    }

    private fun validateRange(
        text: String,
        candidate: MaskCandidate,
    ) {
        require(candidate.endExclusive <= text.length) {
            "Candidate range exceeds source text length"
        }
    }

    private data class CandidateKey(
        val start: Int,
        val endExclusive: Int,
        val type: MaskType,
        val source: MaskSource,
    )
}
