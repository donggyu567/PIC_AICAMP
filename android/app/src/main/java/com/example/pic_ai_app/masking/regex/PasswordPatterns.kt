package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType

internal data class PasswordPatternMatch(
    val start: Int,
    val endExclusive: Int,
    val changedValue: String,
)

internal object PasswordPatterns {
    fun findPasswords(text: String): List<PasswordPatternMatch> {
        if (text.isBlank()) return emptyList()

        val changed = changePasswordText(text)

        return password.findAll(changed.text)
            .mapNotNull { match ->
                val changedValue = match.value.removeGaps()
                if (changedValue.length !in MIN_PASSWORD_LENGTH..MAX_PASSWORD_LENGTH) {
                    return@mapNotNull null
                }

                PasswordPatternMatch(
                    start = changed.originalOffsets[match.range.first],
                    endExclusive = changed.originalOffsets[match.range.last + 1],
                    changedValue = changedValue,
                )
            }
            .distinctBy { it.start to it.endExclusive }
            .sortedBy { it.start }
            .toList()
    }

    private fun changePasswordText(text: String): ChangedText {
        var changed = ChangedText.from(text)

        changed = SpecialSymbolChange.change(changed)
        changed = NumberChange.change(changed)
        changed = EnglishChange.change(changed)

        return changed
    }

    private fun String.removeGaps(): String = filterNot { character ->
        character == ' ' || character == '\t'
    }

    private const val MIN_PASSWORD_LENGTH = 3
    private const val MAX_PASSWORD_LENGTH = 64

    // 복원된 비밀번호에서 허용하는 영문, 숫자, 특수문자다.
    private val passwordCharacter =
        """[A-Za-z0-9!@#${'$'}%^&*()_+=.\-]"""

    // 중간 공백과 탭은 원문 위치에 남겨 두고 실제 길이를 계산할 때만 제외한다.
    private val password = Regex(
        """$passwordCharacter(?:[ \t]*$passwordCharacter)*""",
    )

    fun detectPasswords(text: String): List<MaskCandidate> =
        findPasswords(text).map { match ->
            MaskCandidate(
                start = match.start,
                endExclusive = match.endExclusive,
                type = MaskType.PW,
                source = MaskSource.REGEX,
                confidence = null,
            )
        }
}
