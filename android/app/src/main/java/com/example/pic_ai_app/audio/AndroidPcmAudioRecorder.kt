package com.example.pic_ai_app.audio

import android.Manifest
import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.annotation.RequiresPermission
import kotlin.coroutines.coroutineContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext

class AndroidPcmAudioRecorder {
    @Volatile
    private var activeRecorder: AudioRecord? = null

    @Volatile
    private var stopRequested = false

    @SuppressLint("MissingPermission")
    @RequiresPermission(Manifest.permission.RECORD_AUDIO)
    suspend fun capture(onAudio: suspend (FloatArray) -> Unit) = withContext(Dispatchers.IO) {
        stopRequested = false
        val minimumBufferBytes = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        check(minimumBufferBytes > 0) { "Unable to determine the microphone buffer size" }
        val bufferBytes = maxOf(minimumBufferBytes, TARGET_BUFFER_BYTES)

        val recorder = AudioRecord.Builder()
            .setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(SAMPLE_RATE)
                    .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
                    .build(),
            )
            .setBufferSizeInBytes(bufferBytes * 2)
            .build()

        check(recorder.state == AudioRecord.STATE_INITIALIZED) {
            recorder.release()
            "Unable to initialize the microphone"
        }

        activeRecorder = recorder
        val pcmBuffer = ShortArray(bufferBytes / Short.SIZE_BYTES)
        try {
            recorder.startRecording()
            check(recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                "The microphone did not start recording"
            }

            while (!stopRequested) {
                coroutineContext.ensureActive()
                val sampleCount = recorder.read(
                    pcmBuffer,
                    0,
                    pcmBuffer.size,
                    AudioRecord.READ_BLOCKING,
                )
                when {
                    sampleCount > 0 -> {
                        val normalizedSamples = FloatArray(sampleCount) { index ->
                            pcmBuffer[index] / PCM_NORMALIZATION_FACTOR
                        }
                        onAudio(normalizedSamples)
                    }

                    stopRequested -> Unit
                    else -> error("Microphone read failed with code $sampleCount")
                }
            }
        } finally {
            if (recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                recorder.stop()
            }
            recorder.release()
            if (activeRecorder === recorder) activeRecorder = null
        }
    }

    fun stop() {
        stopRequested = true
        val recorder = activeRecorder ?: return
        if (recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
            runCatching { recorder.stop() }
        }
    }

    private companion object {
        const val SAMPLE_RATE = 16_000
        const val TARGET_BUFFER_BYTES = 3_200
        const val PCM_NORMALIZATION_FACTOR = 32_768.0f
    }
}
