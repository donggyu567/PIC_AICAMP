package com.example.pic_ai_app.stt

import android.content.res.AssetManager
import com.k2fsa.sherpa.onnx.EndpointConfig
import com.k2fsa.sherpa.onnx.EndpointRule
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OnlineModelConfig
import com.k2fsa.sherpa.onnx.OnlineRecognizer
import com.k2fsa.sherpa.onnx.OnlineRecognizerConfig
import com.k2fsa.sherpa.onnx.OnlineStream
import com.k2fsa.sherpa.onnx.OnlineTransducerModelConfig

class SherpaOnnxStreamingSttEngine(
    private val assetManager: AssetManager,
) : StreamingSttEngine {
    private var recognizer: OnlineRecognizer? = null
    private var stream: OnlineStream? = null

    @Synchronized
    override fun initialize() {
        if (recognizer != null) return

        val transducerConfig = OnlineTransducerModelConfig().apply {
            encoder = "$MODEL_DIRECTORY/encoder-epoch-99-avg-1.int8.onnx"
            decoder = "$MODEL_DIRECTORY/decoder-epoch-99-avg-1.onnx"
            joiner = "$MODEL_DIRECTORY/joiner-epoch-99-avg-1.int8.onnx"
        }
        val modelConfig = OnlineModelConfig().apply {
            transducer = transducerConfig
            tokens = "$MODEL_DIRECTORY/tokens.txt"
            numThreads = RECOGNIZER_THREADS
            provider = "cpu"
            debug = false
        }
        val endpointConfig = EndpointConfig().apply {
            // Keep the standard initial-silence and maximum-length safeguards.
            rule1 = EndpointRule(false, 2.4f, 0.0f)
            // A spoken utterance ends after 0.8 seconds of trailing silence.
            rule2 = EndpointRule(true, TRAILING_SILENCE_SECONDS, 0.0f)
            rule3 = EndpointRule(false, 0.0f, 20.0f)
        }
        val recognizerConfig = OnlineRecognizerConfig().apply {
            featConfig = FeatureConfig().apply {
                sampleRate = SAMPLE_RATE
                featureDim = 80
                dither = 0.0f
            }
            this.modelConfig = modelConfig
            this.endpointConfig = endpointConfig
            enableEndpoint = true
            decodingMethod = "greedy_search"
            maxActivePaths = 4
        }

        recognizer = OnlineRecognizer(assetManager, recognizerConfig)
    }

    @Synchronized
    override fun startStream() {
        check(stream == null) { "A recognition stream is already active" }
        stream = requireNotNull(recognizer) {
            "The recognizer must be initialized before recording"
        }.createStream()
    }

    @Synchronized
    override fun acceptAudio(samples: FloatArray): SttDecodeResult {
        if (samples.isEmpty()) return currentPartialResult()

        val activeRecognizer = requireNotNull(recognizer)
        val activeStream = requireNotNull(stream)
        activeStream.acceptWaveform(samples, SAMPLE_RATE)
        decodeAvailable(activeRecognizer, activeStream)
        return resultAfterDecode(activeRecognizer, activeStream)
    }

    @Synchronized
    override fun finishStream(): SttDecodeResult {
        val activeRecognizer = recognizer ?: return SttDecodeResult(partialText = "")
        val activeStream = stream ?: return SttDecodeResult(partialText = "")

        // Stopping the microphone supplies trailing silence so an in-progress
        // utterance follows the same endpoint rule as normal speech.
        activeStream.acceptWaveform(FloatArray(SAMPLE_RATE), SAMPLE_RATE)
        activeStream.inputFinished()
        decodeAvailable(activeRecognizer, activeStream)
        return resultAfterDecode(activeRecognizer, activeStream)
    }

    @Synchronized
    override fun stopStream() {
        stream?.release()
        stream = null
    }

    @Synchronized
    override fun close() {
        stopStream()
        recognizer?.release()
        recognizer = null
    }

    private fun decodeAvailable(
        recognizer: OnlineRecognizer,
        stream: OnlineStream,
    ) {
        while (recognizer.isReady(stream)) {
            recognizer.decode(stream)
        }
    }

    private fun resultAfterDecode(
        recognizer: OnlineRecognizer,
        stream: OnlineStream,
    ): SttDecodeResult {
        val text = recognizer.getResult(stream).text
        if (!recognizer.isEndpoint(stream)) {
            return SttDecodeResult(partialText = text)
        }

        recognizer.reset(stream)
        return SttDecodeResult(
            partialText = "",
            finalText = text.takeUnless(String::isEmpty),
            endpointDetected = true,
        )
    }

    private fun currentPartialResult(): SttDecodeResult {
        val activeRecognizer = recognizer ?: return SttDecodeResult(partialText = "")
        val activeStream = stream ?: return SttDecodeResult(partialText = "")
        return SttDecodeResult(partialText = activeRecognizer.getResult(activeStream).text)
    }

    private companion object {
        const val SAMPLE_RATE = 16_000
        const val RECOGNIZER_THREADS = 2
        const val TRAILING_SILENCE_SECONDS = 0.8f
        const val MODEL_DIRECTORY =
            "models/sherpa-onnx-streaming-zipformer-korean-2024-06-16"
    }
}
