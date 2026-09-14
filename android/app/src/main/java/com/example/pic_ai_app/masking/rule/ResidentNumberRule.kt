package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

internal class ResidentNumberRule : CandidateRule {
    override fun validate(text: String, candidate: MaskCandidate): MaskCandidate? {
        val value = RuleSupport.value(text, candidate)
        val digits = RuleSupport.digits(value)
        val context = RuleSupport.localContext(text, candidate)
        val residentContext = RuleSupport.containsAny(context, RESIDENT_CONTEXT)
        val excluded = RuleSupport.containsAny(context, EXCLUSION_CONTEXT) && !residentContext

        if (!RuleSupport.isNumberLike(value) || excluded) return null
        if (isValidResidentNumberShape(digits)) return candidate

        // Invalid shapes are retained only when nearby wording still identifies an RRN.
        return candidate.takeIf { residentContext && digits.length in 12..14 }
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

    private companion object {
        val RESIDENT_CONTEXT = setOf("주민등록번호", "주민 번호", "주민번호", "신분증")
        val EXCLUSION_CONTEXT = setOf("주문번호", "제품번호", "송장번호", "운송장", "사건번호", "접수번호")
    }
}
