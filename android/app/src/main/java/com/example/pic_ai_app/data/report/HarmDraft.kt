package com.example.pic_ai_app.data.report

data class HarmReportSuggestion(
    val claimedIdentity: String,
    val firstContact: String,
    val deception: String,
)

data class HarmDraft(
    val victimName: String = "",
    val victimBirthDate: String = "",
    val victimPhone: String = "",
    val claimedIdentity: String? = null,
    val suspectPhone: String = "",
    val messengerId: String = "",
    val bankName: String = "",
    val accountNumber: String = "",
    val accountHolder: String = "",
    val firstContact: String? = null,
    val deception: String? = null,
    val damage: String = "",
    val discoveryAndResponse: String = "",
) {
    val hasTimeline: Boolean
        get() = listOf(firstContact, deception, damage, discoveryAndResponse).any { !it.isNullOrBlank() }

    val canCopyReport: Boolean
        get() = hasTimeline || listOf(victimName, victimBirthDate, victimPhone, claimedIdentity, suspectPhone,
            messengerId, bankName, accountNumber, accountHolder).any { !it.isNullOrBlank() }

    fun withSuggestion(suggestion: HarmReportSuggestion): HarmDraft = copy(
        claimedIdentity = claimedIdentity ?: suggestion.claimedIdentity.takeIf(String::isNotBlank),
        firstContact = firstContact ?: suggestion.firstContact.takeIf(String::isNotBlank),
        deception = deception ?: suggestion.deception.takeIf(String::isNotBlank),
    )

    fun timelineText(): String = listOf(
        "최초 접촉 (일시)" to firstContact.orEmpty(),
        "기망 과정 (일시)" to deception.orEmpty(),
        "피해 발생 (일시)" to damage,
        "피해 인지 및 조치 (일시)" to discoveryAndResponse,
    ).joinToString("\n\n") { (heading, details) -> "$heading\n" + details.trim() }

    fun toReportText(): String = listOf(
        "보이스피싱 피해 경위 및 증거 요약서",
        "1. 피해자 인적사항\n성명: ${victimName.trim()}\n생년월일: ${victimBirthDate.trim()}\n연락처: ${victimPhone.trim()}",
        "2. 피의자(사기범) 정보\n사칭 기관 및 이름: ${claimedIdentity.orEmpty().trim()}\n" +
            "사용한 전화번호: ${suspectPhone.trim()}\n메신저 ID: ${messengerId.trim()}\n" +
            "피해금 입금 계좌\n은행명: ${bankName.trim()}\n계좌번호: ${accountNumber.trim()}\n예금주명: ${accountHolder.trim()}",
        "3. 시간대별 피해 발생 경위 (육하원칙 기준)\n\n" + timelineText(),
        "4. 첨부 증빙자료 목록\n보유한 증빙자료는 ECRM에서 직접 첨부합니다.",
    ).joinToString("\n\n", postfix = "\n")
}
