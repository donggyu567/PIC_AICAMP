package com.example.pic_ai_app.masking.ner

import ai.onnxruntime.OnnxJavaType
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import android.content.res.AssetManager
import com.example.pic_ai_app.masking.model.MaskCandidate
import java.io.InputStreamReader
import java.nio.LongBuffer
import java.nio.charset.StandardCharsets

class OnDeviceNerCandidateDetector internal constructor(
    tokenizerProvider: () -> KoElectraTokenizer,
    inferenceProvider: () -> NerWindowInference,
) : NerCandidateDetector, AutoCloseable {
    constructor(assetManager: AssetManager) : this(
        tokenizerProvider = {
            assetManager.open(VOCAB_ASSET_PATH).use { input ->
                KoElectraTokenizer.fromVocab(InputStreamReader(input, StandardCharsets.UTF_8))
            }
        },
        inferenceProvider = { OrtNerWindowInference(assetManager) },
    )

    private val tokenizer = lazy(LazyThreadSafetyMode.SYNCHRONIZED, tokenizerProvider)
    private val inference = lazy(LazyThreadSafetyMode.SYNCHRONIZED, inferenceProvider)
    private val lifecycleLock = Any()
    private var closed = false

    override suspend fun detect(text: String): List<MaskCandidate> = synchronized(lifecycleLock) {
        check(!closed) { "NER detector is closed" }
        val encoding = tokenizer.value.encode(text)
        val windows = NerSlidingWindow.create(text, encoding)
        val predictions = windows.map { window ->
            NerWindowPrediction(window.index, inference.value.predict(window))
        }
        NerBioDecoder.decode(text, NerSlidingWindow.merge(windows, predictions))
    }

    internal fun modelMetadata(): NerModelMetadata = synchronized(lifecycleLock) {
        check(!closed) { "NER detector is closed" }
        inference.value.metadata
    }

    override fun close(): Unit = synchronized(lifecycleLock) {
        if (!closed) {
            closed = true
            if (inference.isInitialized()) inference.value.close()
        }
    }

    private companion object {
        const val ASSET_DIRECTORY = "models/koelectra-ko-pii-ner"
        const val VOCAB_ASSET_PATH = "$ASSET_DIRECTORY/vocab.txt"
    }
}

internal interface NerWindowInference : AutoCloseable {
    val metadata: NerModelMetadata
    fun predict(window: NerTokenWindow): IntArray
    override fun close() = Unit
}

internal data class NerTensorMetadata(
    val type: OnnxJavaType,
    val shape: LongArray,
)

internal data class NerModelMetadata(
    val inputs: Map<String, NerTensorMetadata>,
    val outputName: String,
    val output: NerTensorMetadata,
)

internal class OrtNerWindowInference(
    private val assetManager: AssetManager,
) : NerWindowInference {
    private val environment = lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        OrtEnvironment.getEnvironment()
    }
    private val sessionAndMetadata = lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        val session = OrtSession.SessionOptions().use { options ->
            val model = assetManager.open(MODEL_ASSET_PATH, AssetManager.ACCESS_BUFFER).use { it.readBytes() }
            environment.value.createSession(model, options)
        }
        try {
            SessionAndMetadata(session, inspectMetadata(session))
        } catch (error: Throwable) {
            session.close()
            throw error
        }
    }

    override val metadata: NerModelMetadata
        get() = sessionAndMetadata.value.metadata

    override fun predict(window: NerTokenWindow): IntArray {
        val initialized = sessionAndMetadata.value
        val sequenceLength = window.modelTokens.size
        require(sequenceLength in 2..NerSlidingWindow.MODEL_TOKEN_LIMIT) {
            "Invalid model sequence length: $sequenceLength"
        }
        val shape = longArrayOf(1, sequenceLength.toLong())
        val tensors = LinkedHashMap<String, OnnxTensor>()
        try {
            for (inputName in initialized.metadata.inputs.keys) {
                val values = when (inputName) {
                    INPUT_IDS -> window.inputIds
                    ATTENTION_MASK -> window.attentionMask
                    else -> error("Unsupported model input: $inputName")
                }
                tensors[inputName] = OnnxTensor.createTensor(
                    environment.value,
                    LongBuffer.wrap(values),
                    shape,
                )
            }
            initialized.session.run(tensors, setOf(initialized.metadata.outputName)).use { result ->
                val output = result.get(initialized.metadata.outputName).orElseThrow {
                    IllegalStateException("Missing model output: ${initialized.metadata.outputName}")
                } as? OnnxTensor ?: error("NER output is not a tensor")
                return argmax(output, sequenceLength)
            }
        } finally {
            tensors.values.forEach(OnnxTensor::close)
        }
    }

    override fun close() {
        if (sessionAndMetadata.isInitialized()) sessionAndMetadata.value.session.close()
    }

    private fun inspectMetadata(session: OrtSession): NerModelMetadata {
        val inputInfo = session.inputInfo
        val inputs = inputInfo.mapValues { (_, node) -> node.info.toTensorMetadata() }
        require(inputs.keys == setOf(INPUT_IDS, ATTENTION_MASK)) {
            "Expected inputs [$INPUT_IDS, $ATTENTION_MASK], got ${inputs.keys}"
        }
        inputs.forEach { (name, info) ->
            require(info.type == OnnxJavaType.INT64) { "$name must be INT64, got ${info.type}" }
            requireSequenceShape(name, info.shape)
        }

        val outputInfo = session.outputInfo
        require(outputInfo.keys == setOf(LOGITS)) { "Expected output [$LOGITS], got ${outputInfo.keys}" }
        val outputName = LOGITS
        val output = outputInfo.getValue(outputName).info.toTensorMetadata()
        require(output.type == OnnxJavaType.FLOAT) { "$outputName must be FLOAT, got ${output.type}" }
        require(output.shape.size == 3) {
            "$outputName must have rank 3, got ${output.shape.contentToString()}"
        }
        require(output.shape[2] == NerLabelSchema.LABEL_COUNT.toLong()) {
            "$outputName must expose ${NerLabelSchema.LABEL_COUNT} labels, got ${output.shape.contentToString()}"
        }
        return NerModelMetadata(inputs, outputName, output)
    }

    private fun argmax(output: OnnxTensor, sequenceLength: Int): IntArray {
        val info = output.info as? TensorInfo ?: error("NER output has no tensor metadata")
        val expectedShape = longArrayOf(1, sequenceLength.toLong(), NerLabelSchema.LABEL_COUNT.toLong())
        require(info.shape.contentEquals(expectedShape)) {
            "Expected logits shape ${expectedShape.contentToString()}, got ${info.shape.contentToString()}"
        }
        require(info.type == OnnxJavaType.FLOAT) { "Expected FLOAT logits, got ${info.type}" }
        val logits = requireNotNull(output.floatBuffer) { "Unable to read FLOAT logits" }
        require(logits.remaining() == sequenceLength * NerLabelSchema.LABEL_COUNT) {
            "Unexpected logits element count: ${logits.remaining()}"
        }
        return IntArray(sequenceLength) { tokenIndex ->
            var bestLabel = 0
            var bestLogit = Float.NEGATIVE_INFINITY
            repeat(NerLabelSchema.LABEL_COUNT) { labelId ->
                val logit = logits.get()
                require(logit.isFinite()) { "Non-finite logit at token $tokenIndex, label $labelId" }
                if (logit > bestLogit) {
                    bestLogit = logit
                    bestLabel = labelId
                }
            }
            bestLabel
        }
    }

    private fun requireSequenceShape(name: String, shape: LongArray) {
        require(shape.size == 2) { "$name must have rank 2, got ${shape.contentToString()}" }
        require(shape[0] == -1L || shape[0] == 1L) {
            "$name has unsupported batch dimension: ${shape.contentToString()}"
        }
        require(shape[1] == -1L || shape[1] >= NerSlidingWindow.MODEL_TOKEN_LIMIT) {
            "$name has unsupported sequence dimension: ${shape.contentToString()}"
        }
    }

    private fun Any.toTensorMetadata(): NerTensorMetadata {
        val tensor = this as? TensorInfo ?: error("Model node is not a tensor: $this")
        return NerTensorMetadata(tensor.type, tensor.shape)
    }

    private data class SessionAndMetadata(
        val session: OrtSession,
        val metadata: NerModelMetadata,
    )

    private companion object {
        const val MODEL_ASSET_PATH = "models/koelectra-ko-pii-ner/model.onnx"
        const val INPUT_IDS = "input_ids"
        const val ATTENTION_MASK = "attention_mask"
        const val LOGITS = "logits"
    }
}
