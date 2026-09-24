package com.example.pic_ai_app.masking.renderer

import com.example.pic_ai_app.masking.model.MaskCandidate
import com.example.pic_ai_app.masking.model.MaskSource
import com.example.pic_ai_app.masking.model.MaskType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Test

class MaskedTextRendererTest {
    private val renderer: MaskedTextRenderer = DefaultMaskedTextRenderer()

    @Test
    fun `renders one candidate`() {
        assertEquals(
            "안녕하세요 [PERSON]입니다",
            renderer.render("안녕하세요 김민수입니다", listOf(candidate(6, 9, MaskType.PERSON))),
        )
    }

    @Test
    fun `renders multiple candidate types even when input order is unsorted`() {
        val text = "김민수 010-1234-5678 서울특별시"
        val candidates = listOf(
            candidate(text.indexOf("서울"), text.length, MaskType.ADDRESS),
            candidate(0, 3, MaskType.PERSON),
            candidate(text.indexOf("010"), text.indexOf("010") + 13, MaskType.PHONE_NUMBER),
        )
        assertEquals(
            "[PERSON] [PHONE_NUMBER] [ADDRESS]",
            renderer.render(text, candidates),
        )
    }

    @Test
    fun `renders spans at the beginning middle and end`() {
        val text = "앞 중간 끝"
        assertEquals(
            "[PERSON] [ADDRESS] [EMAIL]",
            renderer.render(
                text,
                listOf(
                    candidate(0, 1, MaskType.PERSON),
                    candidate(2, 4, MaskType.ADDRESS),
                    candidate(5, 6, MaskType.EMAIL),
                ),
            ),
        )
    }

    @Test
    fun `returns the original String when there are no candidates`() {
        val text = "마스킹할 정보가 없습니다 😀"
        assertSame(text, renderer.render(text, emptyList()))
    }

    @Test
    fun `rejects a candidate outside the source text`() {
        assertThrows(IllegalArgumentException::class.java) {
            renderer.render("짧은 글", listOf(candidate(0, 10, MaskType.PERSON)))
        }
    }

    @Test
    fun `rejects overlapping candidates`() {
        assertThrows(IllegalArgumentException::class.java) {
            renderer.render(
                "0123456789",
                listOf(
                    candidate(1, 6, MaskType.PERSON),
                    candidate(4, 8, MaskType.ADDRESS),
                ),
            )
        }
    }

    @Test
    fun `uses Kotlin UTF-16 offsets for Korean and emoji`() {
        val text = "😀 김민수 님"
        assertEquals(
            "😀 [PERSON] 님",
            renderer.render(text, listOf(candidate(3, 6, MaskType.PERSON))),
        )
        assertThrows(IllegalArgumentException::class.java) {
            renderer.render(text, listOf(candidate(1, 2, MaskType.PERSON)))
        }
    }

    @Test
    fun `renders every MaskType with its exact token`() {
        val types = MaskType.entries
        val text = "가".repeat(types.size)
        val candidates = types.mapIndexed { index, type -> candidate(index, index + 1, type) }
        assertEquals(
            "[PERSON][ADDRESS][PHONE_NUMBER][RRN][CARD_NUMBER]" +
                "[ACCOUNT_NUMBER][BIRTH][EMAIL][PW]",
            renderer.render(text, candidates),
        )
    }

    private fun candidate(start: Int, endExclusive: Int, type: MaskType) = MaskCandidate(
        start = start,
        endExclusive = endExclusive,
        type = type,
        source = MaskSource.RULE,
    )
}
