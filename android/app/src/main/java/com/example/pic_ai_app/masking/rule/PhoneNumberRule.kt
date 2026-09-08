package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

internal class PhoneNumberRule : CandidateRule {
    override fun validate(text: String, candidate: MaskCandidate): MaskCandidate? {
        val value = RuleSupport.value(text, candidate)
        val digits = RuleSupport.digits(value)
        val context = RuleSupport.localContext(text, candidate)
        val phoneContext = RuleSupport.containsAny(context, PHONE_CONTEXT)
        val excluded = RuleSupport.containsAny(context, EXCLUSION_CONTEXT) && !phoneContext

        if (!RuleSupport.isNumberLike(value) || excluded) return null
        if (RuleSupport.isPlausiblePhone(digits)) return candidate

        // STT may damage one digit. Keep a phone-context candidate conservatively.
        return candidate.takeIf { phoneContext && digits.length in 7..15 }
    }

    private companion object {
        val PHONE_CONTEXT = setOf("전화", "연락처", "휴대폰", "핸드폰", "휴대전화", "통화")
        val EXCLUSION_CONTEXT = setOf(
            "주문번호", "제품번호", "송장번호", "운송장", "예약번호", "사건번호",
            "접수번호", "계좌", "카드", "주민등록", "주민번호",
        )
    }
}
