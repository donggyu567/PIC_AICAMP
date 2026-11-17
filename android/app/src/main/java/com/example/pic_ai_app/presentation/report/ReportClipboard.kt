package com.example.pic_ai_app.presentation.report

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Build
import android.os.PersistableBundle
import android.widget.Toast
import androidx.annotation.StringRes

internal fun copyReportText(context: Context, label: String, text: String, @StringRes copiedMessage: Int) {
    val clipboard = context.getSystemService(ClipboardManager::class.java) ?: return
    val clip = ClipData.newPlainText(label, text)
    clip.description.extras = PersistableBundle().apply {
        putBoolean("android.content.extra.IS_SENSITIVE", true)
    }
    clipboard.setPrimaryClip(clip)
    if (Build.VERSION.SDK_INT < 33) Toast.makeText(context, copiedMessage, Toast.LENGTH_SHORT).show()
}
