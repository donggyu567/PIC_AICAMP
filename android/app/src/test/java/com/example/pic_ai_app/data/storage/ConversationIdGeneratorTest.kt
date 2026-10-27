package com.example.pic_ai_app.data.storage

import java.util.Calendar
import java.util.TimeZone
import org.junit.Assert.assertEquals
import org.junit.Test

class ConversationIdGeneratorTest {
    @Test
    fun `conversation id uses button timestamp in configured local time`() {
        val seoul = TimeZone.getTimeZone("Asia/Seoul")
        val timestamp = Calendar.getInstance(seoul).run {
            clear()
            set(2026, Calendar.AUGUST, 20, 22, 46, 0)
            timeInMillis
        }

        assertEquals(
            "20260820_2246",
            ConversationIdGenerator(seoul).fromTimestamp(timestamp),
        )
    }
}
