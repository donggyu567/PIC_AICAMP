package com.example.pic_ai_app.masking.regex

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType

internal object EmailPatterns {

    // 줄바꿈을 넘지 않도록 공백과 탭만 허용한다.
    private val gap = """[ \t]*"""

    // 긴 표현부터 찾고, 목록의 문자는 정규식 기호로 해석하지 않는다.
    private fun alternatives(words: List<String>): String =
        words.distinct()
            .sortedByDescending { it.length }
            .joinToString("|") { Regex.escape(it) }

    // 영어 철자로 변환하지 않고, 이메일을 읽는 표현으로 인식한다.
    private val spokenCharacter = "(?:" + alternatives(
        listOf(
            "에이", "비", "씨", "시", "디", "이", "에프", "지",
            "에이치", "에치", "아이", "제이", "케이", "엘", "엠",
            "엔", "오", "피", "큐", "알", "아르", "에스", "티",
            "유", "브이", "더블유", "더블류", "엑스", "와이", "제트",
            "공", "영", "일", "삼", "사", "육", "칠", "팔", "구",
            "하나", "둘", "셋", "넷", "다섯", "여섯", "일곱", "여덟", "아홉"
        )
    ) + "|[0-9]|(?<![A-Za-z])[A-Za-z](?![A-Za-z]))"

    // 아이디 안에서 읽을 수 있는 구분 기호
    private val localSeparator = "(?:[.!#$%&'*+/=?^_`{|}~-]|" + alternatives(
        listOf(
            "언더스코어",
            "언더바",
            "하이픈",
            "대시",
            "플러스",
            "닷",
            "점",
            "쩜",
            "샵",
            "해시",
            "퍼센트",
            "별표"
        )
    ) + ")"

    // 여러 어절은 등록된 읽기 표현과 숫자·독립된 영문 한 글자에만 허용한다.
    // 예: 에이 비 씨, 에이 b 씨, 에이 언더바 비, 에이 공 일
    private val spokenLocalPart =
        """(?:$localSeparator$gap)*$spokenCharacter(?:$gap(?:$spokenCharacter|$localSeparator))*"""

    // @를 의미하는 표현.
// STT에서 '골뱅이'가 잘못 인식되는 경우도 일부 허용한다.
    private val spokenAtMarker = alternatives(
        listOf(
            "골뱅이",
            "고뱅이",
            "골배이",
            "골뱅니"
        )
    )
    private val atMarker =
        """(?:@|$spokenAtMarker|앳${gap}사인|앳)"""

    private val atRegex = Regex(atMarker)


    // 일반 이메일 아이디에서 영문, 숫자, 허용된 특수문자를 찾는다.
    private val localCharacter = """[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]"""

    // 붙여 쓴 '민수골뱅이'에서도 골뱅이를 아이디에 포함하지 않는다.
    private val writtenLocalPart = """(?:(?!$atMarker)$localCharacter)+"""

    // 도메인의 한 구간: example, gmail, com 등
    private val writtenDomainLabel =
        """[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"""

    // 실제 점 앞뒤에는 공백을 허용하지 않는다.
    // 말로 읽은 '닷/점/쩜' 앞뒤에는 공백을 허용한다.
    private val domainSeparator = """(?:\.|$gap(?:닷|점|쩜)$gap)"""

    // 주소에 붙은 문장 끝 표현은 후보에서 제외한다.
    // 끝 표현 뒤에도 글자가 이어지면 문장 끝으로 취급하지 않는다.
    private val sentenceEnding =
        """(?:이에요|예요|입니다|이야|야|이거든요|거든요|이요|요)(?=${'$'}|[^A-Za-z0-9가-힣])"""

    // 도메인은 입력 끝, 구분자, 문장 끝 표현 또는 다른 종류의 문자 앞에서 끝난다.
    private val domainBoundary =
        """(?=${'$'}|$domainSeparator|$sentenceEnding|[^A-Za-z0-9가-힣-])"""

    // 발음형 도메인: 케이 알 에이 등
    private val spokenDomainLabel =
        """$spokenCharacter(?:$gap$spokenCharacter)*"""

    // 일반 한글 도메인도 한 어절로 허용한다. 예: 지메일, 네이버, 회사이름
    // *?는 짧은 구간부터 시도하고, 실제 끝인지는 domainBoundary로 확인한다.
    private val hangulDomainLabel =
        """[A-Za-z0-9가-힣][A-Za-z0-9가-힣-]*?"""

    private val domainLabel =
        """(?:$writtenDomainLabel|$spokenDomainLabel|$hangulDomainLabel)$domainBoundary"""

    // 원문을 직접 탐지하므로 한글 숫자 변환이나 원문 위치 복원이 필요 없다.
    // 점이 빠진 'abc@gmail'도 미탐을 줄이기 위한 후보로 반환한다.
    private val email: Regex = Regex(
        """(?<!$localCharacter)(?:$spokenLocalPart|$writtenLocalPart)$gap$atMarker$gap$domainLabel(?:$domainSeparator$domainLabel)*""",
        RegexOption.IGNORE_CASE
    )

    fun detectEmails(text: String): List<MaskCandidate> {
        if (text.isBlank()) return emptyList()
        if (!atRegex.containsMatchIn(text)) return emptyList()

        return email.findAll(text)
            .map { match ->
                MaskCandidate(
                    start = match.range.first,
                    endExclusive = match.range.last + 1,
                    type = MaskType.EMAIL,
                    source = MaskSource.REGEX,
                    confidence = null
                )
            }
            .toList()
    }
}
