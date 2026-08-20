package com.example.pic_ai_app.data.storage

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

class ConversationIdGenerator(
    private val timeZone: TimeZone = TimeZone.getDefault(),
) {
    fun fromTimestamp(timestampMillis: Long): String =
        SimpleDateFormat(PATTERN, Locale.US).run {
            timeZone = this@ConversationIdGenerator.timeZone
            format(Date(timestampMillis))
        }

    private companion object {
        const val PATTERN = "yyyyMMdd_HHmm"
    }
}
