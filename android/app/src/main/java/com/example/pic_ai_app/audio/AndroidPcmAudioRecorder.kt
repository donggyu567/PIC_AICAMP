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

// 마이크 → 16비트 PCM 수집 → FloatArray 변환 → onAudio 콜백 → 음성 인식 엔진
class AndroidPcmAudioRecorder {
    @Volatile
    private var activeRecorder: AudioRecord? = null     //현재 사용중인 Android 녹음 객체 보관

    @Volatile
    private var stopRequested = false                   //녹음 중단 요청 여부

    @SuppressLint("MissingPermission")
    @RequiresPermission(Manifest.permission.RECORD_AUDIO)
    //녹음을 시작하고, 중단될 때까지 오디오를 반복해서 읽어 콜백으로 전달
    suspend fun capture(onAudio: suspend (FloatArray) -> Unit) = withContext(Dispatchers.IO) {
        //중단 상태 초기화 및 버퍼 크기 설정
        stopRequested = false
        val minimumBufferBytes = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        check(minimumBufferBytes > 0) { "Unable to determine the microphone buffer size" }
        val bufferBytes = maxOf(minimumBufferBytes, TARGET_BUFFER_BYTES)

        //녹음 객체 생성
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

        //녹음 시작
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

    //stop() : 녹음 중단 요청
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
