package com.example.pic_ai_app.presentation.report

import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicMuted

@Composable
internal fun ReportSummaryNotice(loading: Boolean, onRetry: (() -> Unit)?) {
    Text(
        stringResource(if (loading) R.string.report_summary_loading else R.string.report_summary_unavailable),
        color = PicMuted, fontSize = 13.sp,
    )
    if (!loading && onRetry != null) {
        TextButton(onClick = onRetry) { Text(stringResource(R.string.report_summary_retry)) }
    }
}
