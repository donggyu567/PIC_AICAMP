package com.example.pic_ai_app.masking.resolver

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.rule.RuleValidationResult

interface CandidateConflictResolver {
    fun resolve(
        candidates : List<MaskCandidate>
    ): List<MaskCandidate>

    fun resolve(
        nerCandidates: List<MaskCandidate>,
        ruleResult: RuleValidationResult,
    ): List<MaskCandidate> = resolve(nerCandidates + ruleResult.candidates)
}
