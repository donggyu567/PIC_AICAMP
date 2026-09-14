package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

internal class EmailRule : CandidateRule {
    override fun validate(text: String, candidate: MaskCandidate): MaskCandidate? {
        val value = RuleSupport.value(text, candidate)
        if (EMAIL_PATTERN.matches(value)) return candidate

        val context = RuleSupport.localContext(text, candidate)
        val explicitEmailContext = RuleSupport.containsAny(context, EMAIL_CONTEXT)
        // Spoken STT can turn '@' and '.' into words. Preserve the original range
        // when nearby wording still explicitly identifies an email address.
        return candidate.takeIf {
            explicitEmailContext && value.isNotBlank() && value.length <= MAX_EMAIL_LENGTH
        }
    }

    private companion object {
        const val MAX_EMAIL_LENGTH = 254
        val EMAIL_CONTEXT = setOf("이메일", "메일 주소", "email", "e-mail")
        val EMAIL_PATTERN = Regex(
            "^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@" +
                "[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?" +
                "(?:\\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$",
        )
    }
}
