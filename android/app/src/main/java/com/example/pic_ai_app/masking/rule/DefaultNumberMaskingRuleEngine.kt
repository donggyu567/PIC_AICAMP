package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

class DefaultNumberMaskingRuleEngine :
    NumberMaskingRuleEngine {

    override fun validate(
        text: String,
        candidate: List<MaskCandidate>,
    ): List<MaskCandidate> {
        TODO("유형별 규칙으로 후보 검증 후 목록 반환")
    }
}