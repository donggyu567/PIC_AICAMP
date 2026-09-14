package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

internal class BirthRule : CandidateRule {
    override fun validate(text: String, candidate: MaskCandidate): MaskCandidate? {
        val value = RuleSupport.value(text, candidate)
        val context = RuleSupport.localContext(text, candidate)
        val birthContext = RuleSupport.containsAny(context, BIRTH_CONTEXT)
        val scheduleContext = RuleSupport.containsAny(context, SCHEDULE_CONTEXT)

        if (scheduleContext && !birthContext) return null

        val date = RuleSupport.parseDate(value)
        val validDate = date != null && RuleSupport.isValidDate(date.first, date.second, date.third)
        if (validDate) return candidate

        // Preserve an STT-damaged date only with explicit birth wording nearby.
        return candidate.takeIf { birthContext && RuleSupport.digits(value).length in 6..8 }
    }

    private companion object {
        val BIRTH_CONTEXT = setOf("생년월일", "생일", "출생", "태어난")
        val SCHEDULE_CONTEXT = setOf("회의", "일정", "예약", "행사", "배송", "납기", "방문", "재판", "약속", "공연")
    }
}
