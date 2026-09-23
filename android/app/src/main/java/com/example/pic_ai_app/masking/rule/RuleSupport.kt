package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskType
import com.example.pic_ai_app.masking.regex.NumberChange

internal data class CandidateRuleContext(
    val typeSupported: Boolean,
)

internal data class CandidateRuleAssessment(
    val formatValid: Boolean,
    val accepted: Boolean,
) {
    init {
        require(!accepted || formatValid) {
            "An accepted candidate must have a valid format"
        }
    }
}

internal fun interface CandidateRule {
    fun assess(
        text: String,
        candidate: MaskCandidate,
        context: CandidateRuleContext,
    ): CandidateRuleAssessment
}

internal enum class RuleMarkerAction {
    ACTIVATE,
    REMOVE,
    IGNORE,
}

internal data class RuleTypeMarker(
    val start: Int,
    val endExclusive: Int,
    val type: MaskType,
    val action: RuleMarkerAction,
)

internal object RuleSupport {
    private val sentenceBoundaries = setOf('\n', '\r', '.', '?', '!')
    private val allowedNumberCharacters = Regex("""^[0-9+()._\-\s]+$""")

    private data class TypeMarkerDefinition(
        val type: MaskType,
        val regex: Regex,
    )

    private data class RawTypeMarker(
        val start: Int,
        val endExclusive: Int,
        val type: MaskType,
    )

    private val typeMarkerDefinitions = listOf(
        TypeMarkerDefinition(
            type = MaskType.PHONE_NUMBER,
            regex = Regex("""(?:휴대폰\s*번호|핸드폰\s*번호|전화번호|연락처)"""),
        ),
        TypeMarkerDefinition(
            type = MaskType.RRN,
            regex = Regex("""(?:주민등록번호|주민번호)"""),
        ),
        TypeMarkerDefinition(
            type = MaskType.CARD_NUMBER,
            regex = Regex("""카드번호"""),
        ),
        TypeMarkerDefinition(
            type = MaskType.ACCOUNT_NUMBER,
            regex = Regex("""계좌번호"""),
        ),
        TypeMarkerDefinition(
            type = MaskType.BIRTH,
            regex = Regex("""(?:생년월일|출생일|생일)"""),
        ),
        TypeMarkerDefinition(
            type = MaskType.EMAIL,
            regex = Regex("""(?:이메일\s*주소|메일\s*주소|이메일)"""),
        ),
        TypeMarkerDefinition(
            type = MaskType.PW,
            regex = Regex(
                """(?:PIN\s*번호|비밀번호|패스워드|password|비번)""",
                RegexOption.IGNORE_CASE,
            ),
        ),
    )

    private val typeNegation = Regex(
        """^\s*(?:은|는|이|가)?\s*(?:아니라|아니고|아니에요|말고)""",
    )

    private val disclosureProhibition = Regex(
        """^\s*(?:은|는|이|가|을|를)?\s*(?:(?:알려\s*주지)|보내지|말하지)\s*마세요""",
    )

    fun value(text: String, candidate: MaskCandidate): String =
        text.substring(candidate.start, candidate.endExclusive)

    fun numberValue(value: String): String = NumberChange.change(value)

    fun digits(value: String): String = numberValue(value).filter(Char::isDigit)

    fun isNumberLike(value: String): Boolean {
        val changedValue = numberValue(value)
        return changedValue.isNotBlank() && allowedNumberCharacters.matches(changedValue)
    }

    fun findTypeMarkers(text: String): List<RuleTypeMarker> {
        val rawMarkers = typeMarkerDefinitions
            .flatMap { definition ->
                definition.regex.findAll(text).map { match ->
                    RawTypeMarker(
                        start = match.range.first,
                        endExclusive = match.range.last + 1,
                        type = definition.type,
                    )
                }
            }
            .sortedWith(
                compareBy<RawTypeMarker> { it.start }
                    .thenByDescending { it.endExclusive - it.start },
            )

        val nonOverlappingMarkers = mutableListOf<RawTypeMarker>()
        rawMarkers.forEach { marker ->
            val overlapsAcceptedMarker = nonOverlappingMarkers.any { accepted ->
                marker.start < accepted.endExclusive &&
                    accepted.start < marker.endExclusive
            }
            if (!overlapsAcceptedMarker) {
                nonOverlappingMarkers += marker
            }
        }

        return nonOverlappingMarkers
            .sortedBy { it.start }
            .mapIndexed { index, marker ->
                val nextMarkerStart = nonOverlappingMarkers
                    .getOrNull(index + 1)
                    ?.start
                    ?: text.length
                val nextBoundaryStart = text.indexOfAny(
                    chars = sentenceBoundaries.toCharArray(),
                    startIndex = marker.endExclusive,
                ).takeIf { it >= 0 } ?: text.length
                val followingEnd = minOf(nextMarkerStart, nextBoundaryStart)
                val followingText = text.substring(
                    marker.endExclusive,
                    followingEnd,
                )

                val action = when {
                    typeNegation.containsMatchIn(followingText) ->
                        RuleMarkerAction.REMOVE

                    disclosureProhibition.containsMatchIn(followingText) ->
                        RuleMarkerAction.IGNORE

                    else -> RuleMarkerAction.ACTIVATE
                }

                RuleTypeMarker(
                    start = marker.start,
                    endExclusive = marker.endExclusive,
                    type = marker.type,
                    action = action,
                )
            }
    }

    fun findSentenceBoundaries(text: String): List<Int> =
        text.indices.filter { index ->
            text[index] in sentenceBoundaries
        }

    fun isPlausiblePhone(digits: String): Boolean {
        val domestic = when {
            digits.startsWith("82") -> "0${digits.drop(2)}"
            else -> digits
        }
        return when {
            domestic.matches(Regex("01[016789][0-9]{7,8}")) -> true
            domestic.matches(Regex("02[0-9]{7,8}")) -> true
            domestic.matches(Regex("0[3-8][0-9][0-9]{7,8}")) -> true
            domestic.matches(Regex("1[568][0-9]{6}")) -> true
            else -> false
        }
    }

    fun isValidDate(
        year: Int,
        month: Int,
        day: Int,
    ): Boolean {
        if (year !in 1900..2099 || month !in 1..12) return false
        val leap = year % 400 == 0 || (year % 4 == 0 && year % 100 != 0)
        val daysInMonth = when (month) {
            2 -> if (leap) 29 else 28
            4, 6, 9, 11 -> 30
            else -> 31
        }
        return day in 1..daysInMonth
    }

    fun parseDate(value: String): Triple<Int, Int, Int>? {
        val groups = Regex("[0-9]+").findAll(value).map { it.value }.toList()
        if (groups.size >= 3) {
            val rawYear = groups[0].toIntOrNull() ?: return null
            val year = normalizeYear(rawYear, groups[0].length)
            val month = groups[1].toIntOrNull() ?: return null
            val day = groups[2].toIntOrNull() ?: return null
            return Triple(year, month, day)
        }

        if (value.contains('년') || value.contains('월')) {
            return null
        }

        val compact = digits(value)
        return when (compact.length) {
            8 -> Triple(
                compact.substring(0, 4).toInt(),
                compact.substring(4, 6).toInt(),
                compact.substring(6, 8).toInt(),
            )
            6 -> Triple(
                normalizeYear(compact.substring(0, 2).toInt(), 2),
                compact.substring(2, 4).toInt(),
                compact.substring(4, 6).toInt(),
            )
            else -> null
        }
    }

    private fun normalizeYear(year: Int, length: Int): Int = when {
        length >= 4 -> year
        year <= 30 -> 2000 + year
        else -> 1900 + year
    }
}
