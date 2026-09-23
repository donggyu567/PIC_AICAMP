package com.example.pic_ai_app.masking

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.ner.NerCandidateDetector
import com.example.pic_ai_app.masking.regex.RegexCandidateDetector
import com.example.pic_ai_app.masking.rule.NumberMaskingRuleEngine
import com.example.pic_ai_app.masking.rule.RuleContext
import com.example.pic_ai_app.masking.resolver.CandidateConflictResolver
import com.example.pic_ai_app.masking.renderer.MaskedTextRenderer

data class MaskingPipelineResult(
    val maskedText: String,
    val resolvedCandidates: List<MaskCandidate>,
    val updatedContext: RuleContext,
)

class MaskingPipeline(
    private val nerDetector: NerCandidateDetector,
    private val regexDetector : RegexCandidateDetector,
    private val ruleEngine : NumberMaskingRuleEngine,
    private val conflictResolver: CandidateConflictResolver,
    private val renderer: MaskedTextRenderer,
){
    suspend fun mask(text: String): String =
        maskWithContext(text, RuleContext()).maskedText

    suspend fun maskWithContext(
        text: String,
        context: RuleContext,
    ): MaskingPipelineResult {
        val nerCandidates = nerDetector.detect(text)

        val regexCandidates = regexDetector.detect(text)

        val ruleResult = ruleEngine.validateWithContext(
            text = text,
            candidate = regexCandidates,
            context = context,
        )

        val resolvedCandidates = conflictResolver.resolve(
            nerCandidates = nerCandidates,
            ruleResult = ruleResult,
        )

        return MaskingPipelineResult(
            maskedText = renderer.render(text, resolvedCandidates),
            resolvedCandidates = resolvedCandidates,
            updatedContext = ruleResult.updatedContext,
        )
    }
}
