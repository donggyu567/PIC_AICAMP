package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType

internal object NumberPatterns {
    // 숫자로 시작하고 끝나는 구간을 찾는다.
    // 중간에는 숫자, 공백, 탭, 점, 밑줄, 하이픈을 허용한다.
    private val numberSequence: Regex =
        """[0-9](?:[0-9 \t._-]*[0-9])?""".toRegex()

    // 찾은 구간에서 숫자만 남긴 새 문자열을 만든다.
    private fun digitsOnly(value: String): String {
        return value.filter { character ->
            character in '0'..'9'
        }
    }

    // 변환 문자열의 탐지 위치를 원문 위치로 복원해 후보를 만든다.
    private fun toNumberCandidate(
        normalized: ChangedText,
        match: MatchResult,
        type: MaskType
    ): MaskCandidate {
        return MaskCandidate(
            start = normalized.originalOffsets[match.range.first],
            endExclusive = normalized.originalOffsets[match.range.last + 1],
            type = type,
            source = MaskSource.REGEX,
            confidence = null
        )
    }



    // 전화번호(8~11자리)
    fun detectPhoneNumbers(text: String): List<MaskCandidate> {
        if (text.isBlank()) return emptyList()

        val normalized = NumberChange.changeWithOffsets(text)

        return numberSequence.findAll(normalized.text)
            .filter { match ->
                digitsOnly(match.value).length in 8..11
            }
            .map { match ->
                toNumberCandidate(
                    normalized,
                    match,
                    MaskType.PHONE_NUMBER
                )
            }
            .toList()
    }

    // 주민등록번호(11~13자리)
    fun detectRrnNumbers(text: String): List<MaskCandidate> {
        if (text.isBlank()) return emptyList()

        val normalized = NumberChange.changeWithOffsets(text)

        return numberSequence.findAll(normalized.text)
            .filter { match ->
                digitsOnly(match.value).length in 11..13
            }
            .map { match ->
                toNumberCandidate(
                    normalized,
                    match,
                    MaskType.RRN
                )
            }
            .toList()
    }

    //카드번호(14~16자리)
    fun detectCardNumbers(text: String): List<MaskCandidate> {
        if (text.isBlank()) return emptyList()

        val normalized = NumberChange.changeWithOffsets(text)

        return numberSequence.findAll(normalized.text)
            .filter { match ->
                digitsOnly(match.value).length in 14..16
            }
            .map { match ->
                toNumberCandidate(
                    normalized,
                    match,
                    MaskType.CARD_NUMBER
                )
            }
            .toList()
    }

    // 계좌번호(9~15자리) - 계좌번호 자릿수 종류가 10자리에서 15자리까지 있음..ㅠ 그래서 계좌번호는 보통 다 붙는다고 보면 될듯..ㅠ
    fun detectAccountNumbers(text: String): List<MaskCandidate> {
        if (text.isBlank()) return emptyList()

        val normalized = NumberChange.changeWithOffsets(text)

        return numberSequence.findAll(normalized.text)
            .filter { match ->
                digitsOnly(match.value).length in 9..15
            }
            .map { match ->
                toNumberCandidate(
                    normalized,
                    match,
                    MaskType.ACCOUNT_NUMBER
                )
            }
            .toList()
    }


    // 생년월일(5~8자리 + 년/월/일)
    // 예:
    // 1995년 3월 2일
    // 95년 3월 2일
    // 3월 2일
    private val birthDateWithUnits = Regex(
        """(?:(?:\d{2}|\d{4})\s*년\s*)?\d{1,2}\s*월\s*\d{1,2}\s*일"""
    )

    fun detectBirthDates(text: String): List<MaskCandidate> {
        if (text.isBlank()) return emptyList()

        val candidates = mutableListOf<MaskCandidate>()

        // 1. "년 / 월 / 일" 표현을 직접 탐지
        birthDateWithUnits.findAll(text)
            .forEach { match ->
                candidates.add(
                    MaskCandidate(
                        start = match.range.first,
                        endExclusive = match.range.last + 1,
                        type = MaskType.BIRTH,
                        source = MaskSource.REGEX,
                        confidence = null
                    )
                )
            }

        // 2. 숫자로만 표현된 생년월일 탐지
        // 숫자 개수가 5~8자리면 BIRTH 후보로 처리
        val normalized = NumberChange.changeWithOffsets(text)

        numberSequence.findAll(normalized.text)
            .filter { match ->
                digitsOnly(match.value).length in 5..8
            }
            .map { match ->
                toNumberCandidate(
                    normalized = normalized,
                    match = match,
                    type = MaskType.BIRTH
                )
            }
            .forEach { candidate ->
                candidates.add(candidate)
            }

        return candidates
    }

}



