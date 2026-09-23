package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType

class DefaultNumberMaskingRuleEngine :
    NumberMaskingRuleEngine {

    private val contextProcessor = RuleContextProcessor()

    private val rules: Map<MaskType, CandidateRule> = mapOf(
        MaskType.PHONE_NUMBER to PhoneNumberRule(),
        MaskType.RRN to ResidentNumberRule(),
        MaskType.CARD_NUMBER to CardNumberRule(),
        MaskType.ACCOUNT_NUMBER to AccountNumberRule(),
        MaskType.BIRTH to BirthRule(),
        MaskType.EMAIL to EmailRule(),
        MaskType.PW to PasswordRule(),
    )

    override fun validate(
        text: String,
        candidate: List<MaskCandidate>,
    ): List<MaskCandidate> = validateWithContext(
        text = text,
        candidate = candidate,
        context = RuleContext(),
    ).candidates

    override fun validateWithContext(
        text: String,
        candidate: List<MaskCandidate>,
        context: RuleContext,
    ): RuleValidationResult {
        candidate.forEach { validateRange(text, it) }

        val contextResult = contextProcessor.process(
            text = text,
            candidates = candidate,
            context = context,
        )

        val groupsByRange = contextResult.groups.associateBy { group ->
            CandidateRange(
                start = group.start,
                endExclusive = group.endExclusive,
            )
        }

        val assessedEntries = candidate.map { current ->
            val range = CandidateRange(
                start = current.start,
                endExclusive = current.endExclusive,
            )
            val group = groupsByRange.getValue(range)
            val candidateContext = CandidateRuleContext(
                typeSupported =
                    current.type in group.directlySupportedTypes ||
                        current.type in group.activeContextSupportedTypes,
            )

            val rule = rules[current.type]
                ?: throw IllegalArgumentException(
                    "Unsupported candidate type for masking rule: ${current.type}",
                )

            AssessedEntry(
                original = current,
                assessment = rule.assess(
                    text = text,
                    candidate = current,
                    context = candidateContext,
                ),
            )
        }

        val decisions = contextResult.groups.map { group ->
            val formatValidTypes = assessedEntries
                .asSequence()
                .filter { entry ->
                    entry.original.start == group.start &&
                        entry.original.endExclusive == group.endExclusive
                }
                .filter { entry -> entry.assessment.formatValid }
                .map { entry -> entry.original.type }
                .toSet()
            val contextSupportedTypes =
                group.directlySupportedTypes + group.activeContextSupportedTypes
            val supportedTypes = contextSupportedTypes intersect formatValidTypes
            val evidence = buildSet {
                if (group.directlySupportedTypes.isNotEmpty()) {
                    add(RuleEvidence.DIRECT_MARKER)
                }
                if (group.activeContextSupportedTypes.isNotEmpty()) {
                    add(RuleEvidence.ACTIVE_CONTEXT)
                }
                if (formatValidTypes.isNotEmpty()) {
                    add(RuleEvidence.FORMAT)
                }
                if (group.excludedTypes.isNotEmpty()) {
                    add(RuleEvidence.NEGATION)
                }
            }

            RuleCandidateDecision(
                start = group.start,
                endExclusive = group.endExclusive,
                possibleTypes = group.possibleTypes,
                formatValidTypes = formatValidTypes,
                supportedTypes = supportedTypes,
                excludedTypes = group.excludedTypes,
                evidence = evidence,
            )
        }

        val excludedTypesByRange = contextResult.groups.associate { group ->
            CandidateRange(group.start, group.endExclusive) to group.excludedTypes
        }

        val validatedCandidates = assessedEntries
            .filter { entry -> entry.assessment.accepted }
            .filterNot { entry ->
                val range = CandidateRange(
                    entry.original.start,
                    entry.original.endExclusive,
                )
                entry.original.type in excludedTypesByRange.getValue(range)
            }
            .map { entry -> entry.original }
            .distinctBy {
                CandidateKey(
                    start = it.start,
                    endExclusive = it.endExclusive,
                    type = it.type,
                    source = it.source,
                )
            }
            .sortedWith(
                compareBy<MaskCandidate> { it.start }
                    .thenBy { it.endExclusive }
                    .thenBy { it.type.ordinal }
                    .thenBy { it.source.ordinal },
            )

        return RuleValidationResult(
            candidates = validatedCandidates,
            decisions = decisions,
            updatedContext = contextResult.updatedContext,
        )
    }

    private fun validateRange(
        text: String,
        candidate: MaskCandidate,
    ) {
        require(candidate.endExclusive <= text.length) {
            "Candidate range exceeds source text length"
        }
    }

    private data class CandidateKey(
        val start: Int,
        val endExclusive: Int,
        val type: MaskType,
        val source: MaskSource,
    )

    private data class CandidateRange(
        val start: Int,
        val endExclusive: Int,
    )

    private data class AssessedEntry(
        val original: MaskCandidate,
        val assessment: CandidateRuleAssessment,
    )
}
