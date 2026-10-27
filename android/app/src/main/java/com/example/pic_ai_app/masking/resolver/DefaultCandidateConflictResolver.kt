package com.example.pic_ai_app.masking.resolver

import com.example.pic_ai_app.masking.model.MaskCandidate

class DefaultCandidateConflictResolver :
    CandidateConflictResolver {

    override fun resolve(
        candidates: List<MaskCandidate>,
    ): List<MaskCandidate> {
        TODO("중복·겹침 정리 후 목록 반환")
    }
}