package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskType

internal class AccountNumberRule : CandidateRule {
    override fun validate(text: String, candidate: MaskCandidate): MaskCandidate? {
        val value = RuleSupport.value(text, candidate)
        val digits = RuleSupport.digits(value)
        val context = RuleSupport.localContext(text, candidate)
        val accountContext = RuleSupport.containsAny(context, ACCOUNT_CONTEXT)
        val cardContext = RuleSupport.containsAny(context, CARD_CONTEXT)
        val excluded = RuleSupport.containsAny(context, EXCLUSION_CONTEXT) && !accountContext

        if (!RuleSupport.isNumberLike(value) || excluded) return null
        if (cardContext && !accountContext && digits.length in 13..19) {
            return RuleSupport.reclassify(candidate, MaskType.CARD_NUMBER)
        }

        // Domestic account formats differ by bank, so a broad length is deliberate.
        return candidate.takeIf { digits.length in 8..20 }
    }

    private companion object {
        val ACCOUNT_CONTEXT = setOf("계좌", "통장", "입금", "송금", "이체", "은행")
        val CARD_CONTEXT = setOf("카드", "결제", "유효기간", "카드번호")
        val EXCLUSION_CONTEXT = setOf("주문번호", "제품번호", "송장번호", "운송장", "사건번호", "접수번호")
    }
}
