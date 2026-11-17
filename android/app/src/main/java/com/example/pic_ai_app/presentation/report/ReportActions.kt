package com.example.pic_ai_app.presentation.report

import android.content.Context
import android.widget.Toast
import androidx.annotation.StringRes
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.report.ReportAndroidActions
import com.example.pic_ai_app.data.report.ReportDestination

internal fun openReportDestination(context: Context, destination: ReportDestination) {
    if (!ReportAndroidActions.open(context, destination)) {
        Toast.makeText(context, R.string.report_no_external_app, Toast.LENGTH_SHORT).show()
    }
}

internal fun copyReportText(context: Context, label: String, text: String, @StringRes message: Int): Boolean {
    if (!ReportAndroidActions.copy(context, label, text)) return false
    Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
    return true
}
