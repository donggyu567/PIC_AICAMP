package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate

class DefaultRegexCandidateDetector : RegexCandidateDetector {

    override fun detect(
        text: String,
    ): List<MaskCandidate> {
        TODO("유형별 패턴 탐지 후 후보 목록 반환")
    }
}

