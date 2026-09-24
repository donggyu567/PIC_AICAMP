package com.example.pic_ai_app.masking.runtime

import ai.onnxruntime.OnnxJavaType
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.pic_ai_app.stt.SherpaOnnxStreamingSttEngine
import java.nio.LongBuffer
import java.security.MessageDigest
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Staged source: install into app/src/androidTest only AFTER binding ELF verification. */
@RunWith(AndroidJUnit4::class)
class OrtSherpaRuntimeSmokeTest {
    @Test
    fun sherpaFirstThenNerInferenceWhileRecognizerIsAlive() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val stt = SherpaOnnxStreamingSttEngine(context.assets)
        try {
            stt.initialize()
            stt.startStream()
            runNerInference()
            stt.acceptAudio(FloatArray(16_000))
            stt.finishStream()
        } finally {
            stt.close()
        }
    }

    @Test
    fun nerFirstThenSherpaInitialization() {
        runNerInference()
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val stt = SherpaOnnxStreamingSttEngine(context.assets)
        try {
            stt.initialize()
            stt.startStream()
            stt.acceptAudio(FloatArray(16_000))
            runNerInference()
        } finally {
            stt.close()
        }
    }

    private fun runNerInference() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val model = context.assets.open("models/koelectra-ko-pii-ner/model.onnx").use { it.readBytes() }
        val hash = MessageDigest.getInstance("SHA-256").digest(model)
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        assertEquals("7794bdaa2daaa524d1e7f5e4f80e6b62c6fe3bf36d7a9175f4cd4c011837ddc3", hash)
        // OrtEnvironment is process-wide; per-test tensors, results, sessions and options are closed.
        val environment = OrtEnvironment.getEnvironment()
        assertEquals("1.27.1", environment.version)
        OrtSession.SessionOptions().use { options ->
            options.setIntraOpNumThreads(1)
            options.setInterOpNumThreads(1)
            // Default CPU provider, no NNAPI/GPU provider registration.
            environment.createSession(model, options).use { session ->
                assertEquals(setOf("input_ids", "attention_mask"), session.inputInfo.keys)
                assertEquals(setOf("logits"), session.outputInfo.keys)
                for (node in session.inputInfo.values) {
                    val info = node.info as TensorInfo
                    assertEquals(OnnxJavaType.INT64, info.type)
                    assertEquals(2, info.shape.size)
                }
                val outputInfo = session.outputInfo.getValue("logits").info as TensorInfo
                assertEquals(OnnxJavaType.FLOAT, outputInfo.type)
                assertEquals(3, outputInfo.shape.size)
                assertEquals(59L, outputInfo.shape[2])

                val ids = longArrayOf(2, 1, 1, 3) // CLS, UNK, UNK, SEP; deliberately no tokenizer.
                val shape = longArrayOf(1, ids.size.toLong())
                OnnxTensor.createTensor(environment, LongBuffer.wrap(ids), shape).use { input ->
                    OnnxTensor.createTensor(environment, LongBuffer.wrap(LongArray(ids.size) { 1L }), shape).use { mask ->
                        session.run(mapOf("input_ids" to input, "attention_mask" to mask)).use { result ->
                            val logits = result.get("logits")
                                .orElseThrow { IllegalStateException("Missing logits") } as OnnxTensor
                            assertArrayEquals(longArrayOf(1, ids.size.toLong(), 59), logits.info.shape)
                            val values = logits.floatBuffer
                            assertEquals(ids.size * 59, values.remaining())
                            while (values.hasRemaining()) assertTrue(values.get().isFinite())
                        }
                    }
                }
            }
        }
    }
}
