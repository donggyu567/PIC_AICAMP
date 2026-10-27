package com.example.pic_ai_app.masking.resolver

import com.example.pic_ai_app.masking.model.MaskCandidate

interface CandidateConflictResolver {
    fun resolve(
        candidates : List<MaskCandidate>
    ): List<MaskCandidate>
}