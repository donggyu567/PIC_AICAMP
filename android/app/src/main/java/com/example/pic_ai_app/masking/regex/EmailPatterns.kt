package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType

internal data class EmailPatternMatch(
    val start: Int,
    val endExclusive: Int,
    val changedValue: String,
)

internal object EmailPatterns {
    // 줄바꿈을 넘지 않도록 공백과 탭만 허용한다.
    private val gap = """[ \t]*"""

    // 이메일에서 자주 발음되는 도메인 표현을 실제 이메일 표기로 복원한다.
    private val emailChanges = mapOf(
        "점 컴" to ".com",
        "닷 컴" to ".com",
        "점컴" to ".com",
        "닷컴" to ".com",
        "컴" to "com",

        "점 네트" to ".net",
        "닷 네트" to ".net",
        "점넷" to ".net",
        "닷넷" to ".net",
        "네트" to "net",
        "넷" to "net",
        "넫" to "net",

        "지메일" to "gmail",
        "쥐메일" to "gmail",

        "네이버" to "naver",
        "내이버" to "naver",

        "다음" to "daum",
        "네이트" to "nate",
        "야후" to "yahoo",
    )

    private val emailChangeRegex = Regex(
        emailChanges.keys
            .sortedByDescending { it.length }
            .joinToString("|") { Regex.escape(it) },
    )

    // 복원이 끝난 문자열에서는 ASCII 이메일 문자만 탐지한다.
    private val emailCharacter =
        """[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]"""
    private val domainCharacter = """[A-Za-z0-9-]"""

    // NumberPatterns와 마찬가지로 변환 중 공백을 삭제하지 않고 Regex에서 허용한다.
    private val localPart =
        """$emailCharacter(?:$gap$emailCharacter)*"""
    private val domainLabel =
        """[A-Za-z0-9](?:$gap$domainCharacter)*"""

    // 도메인의 점이 빠진 STT 결과도 후보로 올리고 EmailRule에서 문맥을 확인한다.
    private val email = Regex(
        """(?<!$emailCharacter)$localPart$gap@$gap$domainLabel(?:$gap\.$gap$domainLabel)*(?!$domainCharacter)""",
        RegexOption.IGNORE_CASE,
    )

    fun findEmails(text: String): List<EmailPatternMatch> {
        if (text.isBlank()) return emptyList()

        val changed = changeEmailText(text)

        return email.findAll(changed.text)
            .map { match ->
                EmailPatternMatch(
                    start = changed.originalOffsets[match.range.first],
                    endExclusive = changed.originalOffsets[match.range.last + 1],
                    changedValue = match.value,
                )
            }
            .toList()
    }

    fun detectEmails(text: String): List<MaskCandidate> =
        findEmails(text).map { match ->
            MaskCandidate(
                start = match.start,
                endExclusive = match.endExclusive,
                type = MaskType.EMAIL,
                source = MaskSource.REGEX,
                confidence = null,
            )
        }

    private fun changeEmailText(text: String): ChangedText {
        var changed = ChangedText.from(text)

        changed = applyEmailChanges(changed)
        changed = SpecialSymbolChange.change(changed)
        changed = NumberChange.change(changed)
        changed = EnglishChange.change(changed)

        return changed
    }

    private fun applyEmailChanges(changedText: ChangedText): ChangedText =
        changedText.replaceMatches(emailChangeRegex) { match ->
            emailChanges.getValue(match.value)
        }
}
