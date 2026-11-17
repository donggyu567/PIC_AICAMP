package com.example.pic_ai_app.masking.regex

/** Protect explicit OTP context and the next two utterances, including spoken digit sequences. */
internal object OtpProtection {
    private val cue = Regex("""(?:인증\s*(?:번호|코드)|일회용\s*(?:번호|코드)|보안\s*(?:번호|코드)|OTP)""", RegexOption.IGNORE_CASE)
    private val digits = Regex("""(?<![0-9])[0-9](?:[ \t-]*[0-9]){2,}(?![0-9])""")
    data class Result(val text: String, val nextWindow: Int, val count: Int)

    fun protect(text: String, remaining: Int): Result {
        val hasCue = cue.containsMatchIn(text)
        if (!hasCue && remaining <= 0) return Result(text, 0, 0)
        val changed = NumberChange.changeWithOffsets(text)
        val ranges = digits.findAll(changed.text).map { match ->
            changed.originalOffsets[match.range.first] to changed.originalOffsets[match.range.last + 1]
        }.toList()
        val output = buildString {
            var cursor = 0
            for ((start, end) in ranges) {
                append(text, cursor, start)
                append("[OTP]")
                cursor = end
            }
            append(text, cursor, text.length)
        }
        return Result(output, if (hasCue) 2 else (remaining - 1).coerceAtLeast(0), ranges.size)
    }
}
