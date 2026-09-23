package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskType

data class RuleValidationResult(
    val candidates: List<MaskCandidate>,
    val decisions: List<RuleCandidateDecision>,
    val updatedContext: RuleContext,
)

data class RuleCandidateDecision(
    val start: Int,
    val endExclusive: Int,
    val possibleTypes: Set<MaskType>,
    val formatValidTypes: Set<MaskType>,
    val supportedTypes: Set<MaskType>,
    val excludedTypes: Set<MaskType>,
    val evidence: Set<RuleEvidence>,
) {
    init {
        require(start >= 0) {
            "Rule decision start must not be negative"
        }
        require(endExclusive > start) {
            "Rule decision endExclusive must be greater than start"
        }
        require(possibleTypes.isNotEmpty()) {
            "Rule decision must contain at least one possible type"
        }
        require(formatValidTypes.all(possibleTypes::contains)) {
            "Format-valid types must be included in possible types"
        }
        require(supportedTypes.all(formatValidTypes::contains)) {
            "Supported types must pass format validation"
        }
        require(excludedTypes.all(possibleTypes::contains)) {
            "Excluded types must be included in possible types"
        }
        require(supportedTypes.intersect(excludedTypes).isEmpty()) {
            "A Rule type cannot be supported and excluded at the same time"
        }
    }

    val noDecision: Boolean
        get() = supportedTypes.isEmpty() && excludedTypes.isEmpty()
}

enum class RuleEvidence {
    DIRECT_MARKER,
    ACTIVE_CONTEXT,
    FORMAT,
    NEGATION,
}
