package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DefaultRegexCandidateDetectorTest {

    private val detector: RegexCandidateDetector =
        DefaultRegexCandidateDetector()

    @Test
    fun `전화번호 표기 변형을 모두 찾는다`() {
        val phoneNumbers = listOf(
            "010-1234-5678",
            "010 1234 5678",
            "01012345678",
        )

        phoneNumbers.forEach { phoneNumber ->
            val text = "연락처는 ${phoneNumber}입니다"

            assertCandidate(
                text = text,
                expectedValue = phoneNumber,
                expectedType = MaskType.PHONE_NUMBER,
            )
        }
    }

    @Test
    fun `주민등록번호 후보를 찾는다`() {
        val text = "주민등록번호는 950302-1234567입니다"

        assertCandidate(
            text = text,
            expectedValue = "950302-1234567",
            expectedType = MaskType.RRN,
        )
    }

    @Test
    fun `같은 번호의 카드번호와 계좌번호 후보를 모두 유지한다`() {
        val value = "1234-5678-9012-34"
        val text = "번호는 ${value}입니다"
        val start = text.indexOf(value)
        val endExclusive = start + value.length

        val detectedTypes = detector.detect(text)
            .filter { candidate ->
                candidate.start == start &&
                    candidate.endExclusive == endExclusive
            }
            .map { candidate -> candidate.type }
            .toSet()

        assertEquals(
            setOf(
                MaskType.CARD_NUMBER,
                MaskType.ACCOUNT_NUMBER,
            ),
            detectedTypes,
        )
    }

    @Test
    fun `생년월일 표기 변형을 모두 찾는다`() {
        val birthValues = listOf(
            "1995년 3월 2일",
            "1995-03-02",
            "1995.03.02",
            "950302",
            "3월 2일",
        )

        birthValues.forEach { birthValue ->
            val text = "생년월일은 ${birthValue}입니다"

            assertCandidate(
                text = text,
                expectedValue = birthValue,
                expectedType = MaskType.BIRTH,
            )
        }
    }

    @Test
    fun `이메일 뒤의 문장 어미를 후보에서 제외한다`() {
        val text = "이메일은 sample@example.com입니다"

        assertCandidate(
            text = text,
            expectedValue = "sample@example.com",
            expectedType = MaskType.EMAIL,
        )
    }

    @Test
    fun `음성으로 표현된 이메일을 찾는다`() {
        val text = "이메일은 에이 비 씨 골뱅이 지메일 닷 컴입니다"

        assertCandidate(
            text = text,
            expectedValue = "에이 비 씨 골뱅이 지메일 닷 컴",
            expectedType = MaskType.EMAIL,
        )
    }

    @Test
    fun `한글 숫자를 변환한 뒤 원문 위치를 복원한다`() {
        val value = "공일공-하나둘삼사-오육칠팔"
        val text = "😀\n연락처는 ${value}입니다"

        assertCandidate(
            text = text,
            expectedValue = value,
            expectedType = MaskType.PHONE_NUMBER,
        )
    }

    @Test
    fun `한 문장에 포함된 모든 전화번호를 찾는다`() {
        val firstPhone = "010-1234-5678"
        val secondPhone = "02-1234-5678"
        val text = "첫 번째는 ${firstPhone}이고 두 번째는 ${secondPhone}입니다"

        val detectedPhoneNumbers = detector.detect(text)
            .filter { candidate ->
                candidate.type == MaskType.PHONE_NUMBER
            }
            .map { candidate ->
                text.substring(
                    candidate.start,
                    candidate.endExclusive,
                )
            }

        assertEquals(
            listOf(firstPhone, secondPhone),
            detectedPhoneNumbers,
        )
    }

    @Test
    fun `긴 숫자열의 일부를 잘라 후보로 만들지 않는다`() {
        val text = "번호는 12345678901234567890입니다"

        assertTrue(detector.detect(text).isEmpty())
    }

    @Test
    fun `빈 입력과 일반 문장은 빈 목록을 반환한다`() {
        assertTrue(detector.detect("").isEmpty())
        assertTrue(detector.detect(" \t").isEmpty())
        assertTrue(detector.detect("오늘 회의를 시작합니다").isEmpty())
    }

    @Test
    fun `연속 호출 결과가 서로 섞이지 않는다`() {
        val firstResult =
            detector.detect("연락처는 010-1234-5678입니다")

        val secondResult =
            detector.detect("개인정보가 없는 일반 문장입니다")

        assertTrue(firstResult.isNotEmpty())
        assertTrue(secondResult.isEmpty())
    }

    @Test
    fun `모든 후보가 원문 위치와 공통 데이터 형식을 지킨다`() {
        val text =
            "😀 연락처는 010-1234-5678이고 이메일은 sample@example.com입니다"

        val candidates = detector.detect(text)

        assertTrue(candidates.isNotEmpty())

        candidates.forEach { candidate ->
            assertTrue(candidate.start >= 0)
            assertTrue(candidate.endExclusive > candidate.start)
            assertTrue(candidate.endExclusive <= text.length)
            assertEquals(MaskSource.REGEX, candidate.source)
            assertNull(candidate.confidence)
        }
    }

    private fun assertCandidate(
        text: String,
        expectedValue: String,
        expectedType: MaskType,
    ): MaskCandidate {
        val expectedStart = text.indexOf(expectedValue)
        val expectedEndExclusive =
            expectedStart + expectedValue.length

        assertTrue(
            "테스트 값이 원문에 존재해야 합니다.",
            expectedStart >= 0,
        )

        val matchingCandidates = detector.detect(text)
            .filter { candidate ->
                candidate.type == expectedType &&
                    candidate.start == expectedStart &&
                    candidate.endExclusive == expectedEndExclusive
            }

        assertEquals(
            "예상한 범위와 유형의 후보가 하나여야 합니다.",
            1,
            matchingCandidates.size,
        )

        return matchingCandidates.single().also { candidate ->
            assertEquals(MaskSource.REGEX, candidate.source)
            assertNull(candidate.confidence)
            assertEquals(
                expectedValue,
                text.substring(
                    candidate.start,
                    candidate.endExclusive,
                ),
            )
        }
    }
}
