package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate

/**
 * STT 원문에서 정규식 기반 개인정보 후보를 탐지한다.
 *
 * 후보가 없거나 입력이 비어 있으면 빈 목록을 반환한다.
 * 탐지 처리에 실패하면 예외를 숨기지 않고 호출자에게 전달한다.
 */
interface RegexCandidateDetector {
    fun detect(text: String): List<MaskCandidate>
}


