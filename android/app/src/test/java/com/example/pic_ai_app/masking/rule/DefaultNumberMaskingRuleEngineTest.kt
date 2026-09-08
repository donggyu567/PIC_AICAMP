package com.example.pic_ai_app.masking.rule

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class DefaultNumberMaskingRuleEngineTest {
    private val ruleEngine = DefaultNumberMaskingRuleEngine()

    @Test
    fun `keeps a valid phone number without changing its source or range`() {
        val text = "연락처는 010-1234-5678입니다"
        val input = candidate(text, "010-1234-5678", MaskType.PHONE_NUMBER)

        assertEquals(listOf(input), ruleEngine.validate(text, listOf(input)))
    }

    @Test
    fun `removes a phone candidate in an explicit order-number context`() {
        val text = "주문번호는 12345678입니다"
        val input = candidate(text, "12345678", MaskType.PHONE_NUMBER)

        assertTrue(ruleEngine.validate(text, listOf(input)).isEmpty())
    }

    @Test
    fun `keeps a valid resident number shape`() {
        val text = "값은 900101-1234567입니다"
        val input = candidate(text, "900101-1234567", MaskType.RRN)

        assertEquals(listOf(input), ruleEngine.validate(text, listOf(input)))
    }

    @Test
    fun `keeps an STT-damaged resident number in explicit context`() {
        val text = "주민등록번호는 900132-1234567입니다"
        val input = candidate(text, "900132-1234567", MaskType.RRN)

        assertEquals(listOf(input), ruleEngine.validate(text, listOf(input)))
    }

    @Test
    fun `removes an ordinary schedule date misclassified as birth`() {
        val text = "회의는 1995년 3월 2일입니다"
        val input = candidate(text, "1995년 3월 2일", MaskType.BIRTH)

        assertTrue(ruleEngine.validate(text, listOf(input)).isEmpty())
    }

    @Test
    fun `keeps a birth date when local wording identifies it`() {
        val text = "생년월일은 1995년 3월 2일입니다"
        val input = candidate(text, "1995년 3월 2일", MaskType.BIRTH)

        assertEquals(listOf(input), ruleEngine.validate(text, listOf(input)))
    }

    @Test
    fun `reclassifies a card-shaped candidate in account context`() {
        val text = "입금할 계좌는 1234-5678-9012-3456입니다"
        val input = candidate(text, "1234-5678-9012-3456", MaskType.CARD_NUMBER)

        val result = ruleEngine.validate(text, listOf(input)).single()

        assertEquals(MaskType.ACCOUNT_NUMBER, result.type)
        assertEquals(MaskSource.RULE, result.source)
        assertEquals(input.start, result.start)
        assertEquals(input.endExclusive, result.endExclusive)
    }

    @Test
    fun `keeps a Luhn-valid card number`() {
        val text = "번호는 4111-1111-1111-1111입니다"
        val input = candidate(text, "4111-1111-1111-1111", MaskType.CARD_NUMBER)

        assertEquals(listOf(input), ruleEngine.validate(text, listOf(input)))
    }

    @Test
    fun `keeps a plausible account number`() {
        val text = "계좌는 123-456-789012입니다"
        val input = candidate(text, "123-456-789012", MaskType.ACCOUNT_NUMBER)

        assertEquals(listOf(input), ruleEngine.validate(text, listOf(input)))
    }

    @Test
    fun `keeps a valid email without changing its characters`() {
        val text = "주소는 user.name+pic@example.co.kr입니다"
        val input = candidate(text, "user.name+pic@example.co.kr", MaskType.EMAIL)

        assertEquals(listOf(input), ruleEngine.validate(text, listOf(input)))
    }

    @Test
    fun `keeps an STT-damaged email only with explicit email context`() {
        val text = "이메일은 user at example dot com입니다"
        val input = candidate(text, "user at example dot com", MaskType.EMAIL)

        assertEquals(listOf(input), ruleEngine.validate(text, listOf(input)))
    }

    @Test
    fun `removes a malformed email without email context`() {
        val text = "회의 주제는 user at example dot com입니다"
        val input = candidate(text, "user at example dot com", MaskType.EMAIL)

        assertTrue(ruleEngine.validate(text, listOf(input)).isEmpty())
    }

    @Test
    fun `detects an explicit password value even when Regex candidates are empty`() {
        val text = "비밀번호: Abc123!"

        val result = ruleEngine.validate(text, emptyList()).single()

        assertEquals("Abc123!", text.substring(result.start, result.endExclusive))
        assertEquals(MaskType.PW, result.type)
        assertEquals(MaskSource.RULE, result.source)
        assertEquals(null, result.confidence)
    }

    @Test
    fun `extracts a spoken Korean password value without its sentence ending`() {
        val text = "비밀번호는 사과입니다."

        val result = ruleEngine.validate(text, emptyList()).single()

        assertEquals("사과", text.substring(result.start, result.endExclusive))
    }

    @Test
    fun `does not create a password candidate for a value-free mention`() {
        val text = "비밀번호가 기억나지 않습니다"

        assertTrue(ruleEngine.validate(text, emptyList()).isEmpty())
    }

    @Test
    fun `throws when a candidate range exceeds the source text`() {
        val text = "010"
        val invalid = MaskCandidate(
            start = 0,
            endExclusive = 4,
            type = MaskType.PHONE_NUMBER,
            source = MaskSource.REGEX,
        )

        assertThrows(IllegalArgumentException::class.java) {
            ruleEngine.validate(text, listOf(invalid))
        }
    }

    @Test
    fun `throws for a candidate type outside the Rule contract`() {
        val text = "홍길동"
        val input = candidate(text, "홍길동", MaskType.PERSON)

        assertThrows(IllegalArgumentException::class.java) {
            ruleEngine.validate(text, listOf(input))
        }
    }

    private fun candidate(
        text: String,
        value: String,
        type: MaskType,
    ): MaskCandidate {
        val start = text.indexOf(value)
        require(start >= 0)
        return MaskCandidate(
            start = start,
            endExclusive = start + value.length,
            type = type,
            source = MaskSource.REGEX,
        )
    }
}
