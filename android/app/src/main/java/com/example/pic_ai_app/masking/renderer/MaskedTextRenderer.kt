package com.example.pic_ai_app.masking.renderer

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskType

interface MaskedTextRenderer {
    fun render(
        text: String,
        candidate: List<MaskCandidate>
    ): String
}

class DefaultMaskedTextRenderer : MaskedTextRenderer {
    override fun render(
        text: String,
        candidate: List<MaskCandidate>,
    ): String {
        if (candidate.isEmpty()) return text

        val sorted = candidate.sortedBy(MaskCandidate::start)
        var previousEnd = 0
        for ((index, item) in sorted.withIndex()) {
            require(item.endExclusive <= text.length) {
                "Candidate $index exceeds text length: [${item.start}, ${item.endExclusive})"
            }
            require(!splitsSurrogatePair(text, item.start)) {
                "Candidate $index starts inside a surrogate pair"
            }
            require(!splitsSurrogatePair(text, item.endExclusive)) {
                "Candidate $index ends inside a surrogate pair"
            }
            require(item.start >= previousEnd) {
                "Candidate $index overlaps the previous candidate"
            }
            previousEnd = item.endExclusive
        }

        return buildString {
            var sourceIndex = 0
            for (item in sorted) {
                append(text, sourceIndex, item.start)
                append(item.type.maskToken)
                sourceIndex = item.endExclusive
            }
            append(text, sourceIndex, text.length)
        }
    }

    private val MaskType.maskToken: String
        get() = when (this) {
            MaskType.PERSON -> "[PERSON]"
            MaskType.ADDRESS -> "[ADDRESS]"
            MaskType.PHONE_NUMBER -> "[PHONE_NUMBER]"
            MaskType.RRN -> "[RRN]"
            MaskType.CARD_NUMBER -> "[CARD_NUMBER]"
            MaskType.ACCOUNT_NUMBER -> "[ACCOUNT_NUMBER]"
            MaskType.BIRTH -> "[BIRTH]"
            MaskType.EMAIL -> "[EMAIL]"
            MaskType.PW -> "[PW]"
        }

    private fun splitsSurrogatePair(text: String, offset: Int): Boolean =
        offset > 0 && offset < text.length &&
            text[offset - 1].isHighSurrogate() && text[offset].isLowSurrogate()
}
