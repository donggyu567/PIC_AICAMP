package com.example.pic_ai_app.masking.ner

import com.example.pic_ai_app.masking.model.MaskCandidate

class OnDeviceNerCandidateDetector : NerCandidateDetector {

    override suspend fun detect(
        text: String,
    ): List<MaskCandidate> {
        TODO("모델 실행 후 후보 목록 반환")
    }
}