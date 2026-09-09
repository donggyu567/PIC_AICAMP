package com.example.pic_ai_app.masking.regex

object test {
}

import java.util.regex.Pattern

object PhoneExtractor {

    // 1. 가비지 컬렉션(GC) 방지를 위해 맵과 정규식을 싱글톤(object) 내부에 한 번만 생성
    private val korNumMap = mapOf(
        "공" to "0", "영" to "0", "일" to "1", "이" to "2", "삼" to "3",
        "사" to "4", "오" to "5", "육" to "6", "칠" to "7", "팔" to "8", "구" to "9",
        "하나" to "1", "둘" to "2", "셋" to "3", "넷" to "4", "다섯" to "5",
        "여섯" to "6", "일곱" to "7", "여덟" to "8", "아홉" to "9"
    )

    // 한글 숫자 치환용 정규식 (미리 컴파일)
    private val korNumRegex = korNumMap.keys.joinToString("|").toRegex()

    // 번호 구역 추출용 정규식 (미리 컴파일)
    private val phonePattern = """0\s*1\s*[0-9-_\s]{7,13}""".toRegex()

    // 숫자 이외의 문자 제거용 정규식 (미리 컴파일)
    private val nonDigitRegex = """[^0-9]""".toRegex()

    /**
     * STT 실시간 텍스트에서 전화번호를 추출하는 메인 함수
     */
    fun extract(sttText: String): List<String> {
        if (sttText.isBlank()) return emptyList()

        // 1단계: 한글 숫자 전처리
        val convertedText = korNumRegex.replace(sttText) { matchResult ->
            korNumMap[matchResult.value] ?: matchResult.value
        }

        // 2단계 & 3단계: 패턴 매칭 및 자릿수 검증
        return phonePattern.findAll(convertedText)
            .map { matchResult ->
                matchResult.value.replace(nonDigitRegex, "")
            }
            .filter { cleanNum ->
                cleanNum.length == 10 || cleanNum.length == 11
            }
            .toList()
    }
}


