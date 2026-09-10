package com.example.pic_ai_app.masking

import com.example.pic_ai_app.masking.ner.NerCandidateDetector
import com.example.pic_ai_app.masking.regex.RegexCandidateDetector
import com.example.pic_ai_app.masking.rule.NumberMaskingRuleEngine
import com.example.pic_ai_app.masking.resolver.CandidateConflictResolver
import com.example.pic_ai_app.masking.renderer.MaskedTextRenderer

class MaskingPipeline(
    private val nerDetector: NerCandidateDetector,
    private val regexDetector : RegexCandidateDetector,
    private val ruleEngine : NumberMaskingRuleEngine,
    private val conflictResolver: CandidateConflictResolver,
    private val renderer: MaskedTextRenderer,
){
    suspend fun mask(text: String): String {
        val nerCandidates = nerDetector.detect(text)

        val regexCandidates = regexDetector.detect(text)

        val validatedCandidates =
            ruleEngine.validate(text, regexCandidates)

        val resolvedCandidates = conflictResolver.resolve(
            nerCandidates + validatedCandidates
        )

        return renderer.render(text, resolvedCandidates)
    }
}