package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskType

private const val MAX_ACTIVE_TYPES = 3

private val SUPPORTED_CONTEXT_TYPES = setOf(
    MaskType.PHONE_NUMBER,
    MaskType.RRN,
    MaskType.CARD_NUMBER,
    MaskType.ACCOUNT_NUMBER,
    MaskType.BIRTH,
    MaskType.EMAIL,
    MaskType.PW,
)

data class RuleContext(
    val activeTypes: List<MaskType> = emptyList(),
) {
    init {
        require(activeTypes.size <= MAX_ACTIVE_TYPES) {
            "Rule context supports at most $MAX_ACTIVE_TYPES active types"
        }
        require(activeTypes.distinct().size == activeTypes.size) {
            "Rule context types must be unique"
        }
        require(activeTypes.all(SUPPORTED_CONTEXT_TYPES::contains)) {
            "Rule context contains an unsupported mask type"
        }
    }

    fun activate(type: MaskType): RuleContext {
        require(type in SUPPORTED_CONTEXT_TYPES) {
            "Unsupported Rule context type: $type"
        }

        return copy(
            activeTypes = (activeTypes - type + type)
                .takeLast(MAX_ACTIVE_TYPES),
        )
    }

    fun remove(type: MaskType): RuleContext = copy(
        activeTypes = activeTypes - type,
    )
}
