package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate

interface RegexCandidateDetector {
    fun detect(text: String): List<MaskCandidate>
}

