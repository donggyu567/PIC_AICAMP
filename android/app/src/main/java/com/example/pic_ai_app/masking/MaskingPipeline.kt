package com.example.pic_ai_app.masking

import com.example.pic_ai_app.masking.model.MaskingResult
import com.example.pic_ai_app.masking.ner.NerCandidateDetector
import com.example.pic_ai_app.masking.regex.RegexCandidateDetector
import com.example.pic_ai_app.masking.renderer.MaskedTextRenderer
import com.example.pic_ai_app.masking.resolver.CandidateConflictResolver
import com.example.pic_ai_app.masking.rule.NumberMaskingRuleEngine

class MaskingPipeline(
    private val nerDetector: NerCandidateDetector,
    private val regexDetector: RegexCandidateDetector,
    private val ruleEngine: NumberMaskingRuleEngine,
    private val conflictResolver: CandidateConflictResolver,
    private val renderer: MaskedTextRenderer,
) {
    suspend fun mask(text: String): MaskingResult {
        val nerCandidates = nerDetector.detect(text)

        val regexCandidates = regexDetector.detect(text)

        val validatedCandidates =
            ruleEngine.validate(text, regexCandidates)

        val resolvedCandidates = conflictResolver.resolve(
            nerCandidates + validatedCandidates
        )

        val maskedText = renderer.render(text, resolvedCandidates)

        val maskedTypes = resolvedCandidates
            .sortedBy { it.start }
            .map { it.type }
            .distinct()

        return MaskingResult(
            maskedText = maskedText,
            maskedTypes = maskedTypes,
        )
    }
}