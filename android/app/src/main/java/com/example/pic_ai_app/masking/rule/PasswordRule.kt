package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import com.example.pic_ai_app.masking.regex.PasswordPatterns

internal class PasswordRule {
    fun detect(text: String): List<MaskCandidate> = PasswordPatterns.findPasswords(text)
        .map { match ->
            MaskCandidate(
                start = match.start,
                endExclusive = match.endExclusive,
                type = MaskType.PW,
                source = MaskSource.RULE,
                confidence = null,
            )
        }
        .toList()
}
