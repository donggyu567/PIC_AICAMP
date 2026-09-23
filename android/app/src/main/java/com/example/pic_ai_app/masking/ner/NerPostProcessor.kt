package com.example.pic_ai_app.masking.ner

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import kotlin.math.min

internal data class NerTokenWindow(
    val index: Int,
    val contentStart: Int,
    val contentEndExclusive: Int,
    val modelTokens: List<KoElectraToken>,
) {
    val contentSize: Int = contentEndExclusive - contentStart
    val inputIds: LongArray = modelTokens.map { it.id }.toLongArray()
    val attentionMask: LongArray = LongArray(modelTokens.size) { 1L }
}

internal data class NerWindowPrediction(
    val windowIndex: Int,
    val labelIds: IntArray,
)

internal data class NerTokenPrediction(
    val globalTokenIndex: Int,
    val token: KoElectraToken,
    val labelId: Int,
    val sourceWindowIndex: Int,
)

internal object NerSlidingWindow {
    const val MODEL_TOKEN_LIMIT = 512
    const val CONTENT_TOKEN_LIMIT = 510
    const val OVERLAP = 64
    const val STRIDE = CONTENT_TOKEN_LIMIT - OVERLAP

    fun create(
        text: String,
        encoding: KoElectraEncoding,
    ): List<NerTokenWindow> {
        require(encoding.tokens.size >= 2) { "Encoding must contain CLS and SEP" }
        val cls = encoding.tokens.first()
        val sep = encoding.tokens.last()
        require(cls.value == "[CLS]" && cls.start == 0 && cls.endExclusive == 0) {
            "Encoding must start with synthetic CLS"
        }
        require(sep.value == "[SEP]" && sep.start == 0 && sep.endExclusive == 0) {
            "Encoding must end with synthetic SEP"
        }
        val content = encoding.tokens.subList(1, encoding.tokens.lastIndex)
        validateContentTokens(text, content)

        if (content.size <= CONTENT_TOKEN_LIMIT) {
            return listOf(window(0, 0, content.size, cls, sep, content))
        }

        val windows = ArrayList<NerTokenWindow>()
        var start = 0
        while (start < content.size) {
            val endExclusive = min(start + CONTENT_TOKEN_LIMIT, content.size)
            windows += window(windows.size, start, endExclusive, cls, sep, content)
            if (endExclusive == content.size) break
            start += STRIDE
        }
        return windows
    }

    fun merge(
        windows: List<NerTokenWindow>,
        predictions: List<NerWindowPrediction>,
    ): List<NerTokenPrediction> {
        require(windows.isNotEmpty()) { "At least one window is required" }
        require(predictions.size == windows.size) { "Each window must have one prediction" }
        val tokenCount = windows.maxOf { it.contentEndExclusive }
        val selected = arrayOfNulls<SelectedPrediction>(tokenCount)

        for ((window, prediction) in windows.zip(predictions)) {
            require(prediction.windowIndex == window.index) {
                "Prediction ${prediction.windowIndex} does not match window ${window.index}"
            }
            require(prediction.labelIds.size == window.modelTokens.size) {
                "Window ${window.index} expected ${window.modelTokens.size} labels, got ${prediction.labelIds.size}"
            }
            prediction.labelIds.forEach(NerLabelSchema::requireValid)
            for (localIndex in 0 until window.contentSize) {
                val globalIndex = window.contentStart + localIndex
                val context = min(localIndex, window.contentSize - 1 - localIndex)
                val candidate = SelectedPrediction(
                    prediction = NerTokenPrediction(
                        globalTokenIndex = globalIndex,
                        token = window.modelTokens[localIndex + 1],
                        labelId = prediction.labelIds[localIndex + 1],
                        sourceWindowIndex = window.index,
                    ),
                    minimumContext = context,
                    windowContentSize = window.contentSize,
                )
                val current = selected[globalIndex]
                if (current == null || candidate.hasMoreContextThan(current)) {
                    selected[globalIndex] = candidate
                }
            }
        }

        return selected.mapIndexed { index, value ->
            requireNotNull(value) { "No prediction covers global token $index" }.prediction
        }
    }

    private fun window(
        index: Int,
        start: Int,
        endExclusive: Int,
        cls: KoElectraToken,
        sep: KoElectraToken,
        content: List<KoElectraToken>,
    ): NerTokenWindow {
        val tokens = ArrayList<KoElectraToken>(endExclusive - start + 2)
        tokens += cls
        tokens += content.subList(start, endExclusive)
        tokens += sep
        require(tokens.size <= MODEL_TOKEN_LIMIT)
        return NerTokenWindow(index, start, endExclusive, tokens)
    }

    private data class SelectedPrediction(
        val prediction: NerTokenPrediction,
        val minimumContext: Int,
        val windowContentSize: Int,
    ) {
        fun hasMoreContextThan(other: SelectedPrediction): Boolean =
            minimumContext > other.minimumContext ||
                minimumContext == other.minimumContext && windowContentSize > other.windowContentSize
    }
}

internal object NerBioDecoder {
    fun decode(
        text: String,
        predictions: List<NerTokenPrediction>,
    ): List<MaskCandidate> {
        validateContentTokens(text, predictions.map { it.token })
        predictions.forEachIndexed { index, prediction ->
            require(prediction.globalTokenIndex == index) {
                "Predictions must be in complete global token order"
            }
        }

        val candidates = ArrayList<MaskCandidate>()
        var active: ActiveEntity? = null

        fun finishActive() {
            val entity = active ?: return
            candidates += MaskCandidate(
                start = entity.start,
                endExclusive = entity.endExclusive,
                type = entity.type,
                source = MaskSource.NER,
            )
            active = null
        }

        for (prediction in predictions) {
            val tag = SupportedTag.parse(prediction.labelId)
            if (tag == null) {
                finishActive()
                continue
            }
            val current = active
            if (tag.prefix == BioPrefix.INSIDE && current?.type == tag.type) {
                current.endExclusive = prediction.token.endExclusive
            } else {
                // B-* always starts a new entity. An orphan or type-changing I-*
                // is handled as a safe new entity start.
                finishActive()
                active = ActiveEntity(
                    start = prediction.token.start,
                    endExclusive = prediction.token.endExclusive,
                    type = tag.type,
                )
            }
        }
        finishActive()
        return candidates
    }

    private data class ActiveEntity(
        val start: Int,
        var endExclusive: Int,
        val type: MaskType,
    )

    private enum class BioPrefix { BEGIN, INSIDE }

    private data class SupportedTag(
        val prefix: BioPrefix,
        val type: MaskType,
    ) {
        companion object {
            fun parse(labelId: Int): SupportedTag? = when (labelId) {
                NerLabelSchema.B_NAME -> SupportedTag(BioPrefix.BEGIN, MaskType.PERSON)
                NerLabelSchema.I_NAME -> SupportedTag(BioPrefix.INSIDE, MaskType.PERSON)
                NerLabelSchema.B_ADDRESS -> SupportedTag(BioPrefix.BEGIN, MaskType.ADDRESS)
                NerLabelSchema.I_ADDRESS -> SupportedTag(BioPrefix.INSIDE, MaskType.ADDRESS)
                else -> null
            }
        }
    }
}

internal object NerLabelSchema {
    const val LABEL_COUNT = 59
    const val OUTSIDE = 0
    const val B_ADDRESS = 3
    const val I_ADDRESS = 4
    const val B_NAME = 31
    const val I_NAME = 32

    fun requireValid(labelId: Int) {
        require(labelId in 0 until LABEL_COUNT) { "Invalid NER label ID: $labelId" }
    }
}

private fun validateContentTokens(
    text: String,
    tokens: List<KoElectraToken>,
) {
    var previousEnd = 0
    for ((index, token) in tokens.withIndex()) {
        require(token.start >= 0 && token.endExclusive > token.start && token.endExclusive <= text.length) {
            "Invalid offset for global token $index: [${token.start}, ${token.endExclusive})"
        }
        require(token.start >= previousEnd) { "Token offsets are not monotonic at global token $index" }
        require(!splitsSurrogatePair(text, token.start)) {
            "Token $index starts inside a surrogate pair"
        }
        require(!splitsSurrogatePair(text, token.endExclusive)) {
            "Token $index ends inside a surrogate pair"
        }
        previousEnd = token.endExclusive
    }
}

private fun splitsSurrogatePair(text: String, offset: Int): Boolean =
    offset > 0 && offset < text.length &&
        text[offset - 1].isHighSurrogate() && text[offset].isLowSurrogate()
