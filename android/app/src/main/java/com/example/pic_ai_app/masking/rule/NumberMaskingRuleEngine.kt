package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate

interface NumberMaskingRuleEngine {
    fun validate(
        text: String,
        candidate: List<MaskCandidate>
    ): List<MaskCandidate>

    fun validateWithContext(
        text: String,
        candidate: List<MaskCandidate>,
        context: RuleContext,
    ): RuleValidationResult = RuleValidationResult(
        candidates = validate(text, candidate),
        decisions = emptyList(),
        updatedContext = context,
    )
}

