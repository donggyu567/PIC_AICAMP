package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

interface NumberMaskingRuleEngine {
    fun validate(
        text: String,
        candidate: List<MaskCandidate>
    ): List<MaskCandidate>
}

