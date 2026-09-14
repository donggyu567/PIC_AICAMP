package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskType

internal class CardNumberRule : CandidateRule {
    override fun validate(text: String, candidate: MaskCandidate): MaskCandidate? {
        val value = RuleSupport.value(text, candidate)
        val digits = RuleSupport.digits(value)
        val context = RuleSupport.localContext(text, candidate)
        val cardContext = RuleSupport.containsAny(context, CARD_CONTEXT)
        val accountContext = RuleSupport.containsAny(context, ACCOUNT_CONTEXT)
        val excluded = RuleSupport.containsAny(context, EXCLUSION_CONTEXT) && !cardContext

        if (!RuleSupport.isNumberLike(value) || excluded) return null
        if (accountContext && !cardContext && digits.length in 8..20) {
            return RuleSupport.reclassify(candidate, MaskType.ACCOUNT_NUMBER)
        }
        if (cardContext && digits.length in 12..19) return candidate
        if (digits.length in 13..19 && passesLuhn(digits)) return candidate

        // A plausible card-shaped Regex result remains ambiguous, so keep it.
        return candidate.takeIf { digits.length in 13..19 }
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

    private companion object {
        val CARD_CONTEXT = setOf("카드", "결제", "유효기간", "카드번호")
        val ACCOUNT_CONTEXT = setOf("계좌", "통장", "입금", "송금", "이체")
        val EXCLUSION_CONTEXT = setOf("주문번호", "제품번호", "송장번호", "운송장", "사건번호", "접수번호")
    }
}
