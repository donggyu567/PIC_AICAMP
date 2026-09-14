package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate

class DefaultRegexCandidateDetector : RegexCandidateDetector {

    override fun detect(
        text: String,
    ): List<MaskCandidate> {
        if (text.isBlank()) return emptyList()

        return buildList {
            addAll(NumberPatterns.detectPhoneNumbers(text))
            addAll(NumberPatterns.detectRrnNumbers(text))
            addAll(NumberPatterns.detectCardNumbers(text))
            addAll(NumberPatterns.detectAccountNumbers(text))
            addAll(NumberPatterns.detectBirthDates(text))
            addAll(EmailPatterns.detectEmails(text))
        }.sortedWith(
            compareBy<MaskCandidate>(
                { it.start },
                { it.endExclusive },
                { it.type.ordinal },
            )
        )
    }
}


