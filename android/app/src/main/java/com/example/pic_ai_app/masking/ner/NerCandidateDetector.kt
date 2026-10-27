package com.example.pic_ai_app.masking.ner

import com.example.pic_ai_app.masking.model.MaskCandidate

interface NerCandidateDetector {
    suspend fun detect(text: String): List<MaskCandidate>
}