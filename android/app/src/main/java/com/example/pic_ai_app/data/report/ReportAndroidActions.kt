package com.example.pic_ai_app.data.report

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.PersistableBundle

object ReportAndroidActions {
    fun copy(context: Context, label: String, text: String): Boolean {
        if (text.isBlank()) return false
        val clipboard = context.getSystemService(ClipboardManager::class.java) ?: return false
        val clip = ClipData.newPlainText(label, text)
        clip.description.extras = PersistableBundle().apply {
            putBoolean("android.content.extra.IS_SENSITIVE", true)
        }
        return try {
            clipboard.setPrimaryClip(clip)
            true
        } catch (_: SecurityException) {
            false
        }
    }

    fun open(activityContext: Context, destination: ReportDestination): Boolean {
        val action = when (destination) {
            ReportDestination.PhishingSos, ReportDestination.Ecrm -> Intent.ACTION_VIEW
            ReportDestination.Emergency112 -> Intent.ACTION_DIAL
        }
        return try {
            activityContext.startActivity(Intent(action, Uri.parse(destination.uri)))
            true
        } catch (_: ActivityNotFoundException) {
            false
        }
    }
}
