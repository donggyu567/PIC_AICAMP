package com.example.pic_ai_app.presentation.report

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import androidx.compose.foundation.Canvas as ComposeCanvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import java.io.OutputStream

// A4 page dimensions in PDF points. The preview draws these same pages at screen scale.
internal class ReportDamagePdf(private val title: String, text: String) {
    companion object {
        const val WIDTH = 595
        const val HEIGHT = 842
        private const val MARGIN = 40
        private const val BODY_TOP = 85
    }

    private val body = StaticLayout.Builder.obtain(text, 0, text.length,
        TextPaint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.BLACK; textSize = 13f },
        WIDTH - MARGIN * 2).setAlignment(Layout.Alignment.ALIGN_NORMAL)
        .setLineSpacing(3f, 1f).setIncludePad(false).build()
    private val heading = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.BLACK
        textSize = 20f
        typeface = Typeface.DEFAULT_BOLD
    }
    private val pageStarts = buildList<Int> {
        add(0)
        for (line in 1 until body.lineCount) {
            if (body.getLineBottom(line) - body.getLineTop(last()) > HEIGHT - MARGIN - BODY_TOP) add(line)
        }
    }
    val pageCount: Int get() = pageStarts.size

    fun draw(canvas: Canvas, index: Int) {
        canvas.clipRect(0, 0, WIDTH, HEIGHT)
        canvas.drawColor(Color.WHITE)
        canvas.drawText(title, MARGIN.toFloat(), 58f, heading)
        val firstY = body.getLineTop(pageStarts[index])
        val endY = pageStarts.getOrNull(index + 1)?.let(body::getLineTop) ?: body.height
        val checkpoint = canvas.save()
        canvas.translate(MARGIN.toFloat(), BODY_TOP.toFloat())
        canvas.clipRect(0, 0, body.width, endY - firstY)
        canvas.translate(0f, -firstY.toFloat())
        body.draw(canvas)
        canvas.restoreToCount(checkpoint)
    }

    fun writeTo(output: OutputStream) {
        val pdf = PdfDocument()
        try {
            for (index in pageStarts.indices) {
                val page = pdf.startPage(PdfDocument.PageInfo.Builder(WIDTH, HEIGHT, index + 1).create())
                try {
                    draw(page.canvas, index)
                } finally {
                    pdf.finishPage(page)
                }
            }
            pdf.writeTo(output)
        } finally {
            pdf.close()
        }
    }
}

@Composable
internal fun ReportPdfPreview(document: ReportDamagePdf, onClose: () -> Unit) {
    AlertDialog(
        onDismissRequest = onClose, title = { Text(stringResource(R.string.report_pdf_preview)) },
        text = {
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 520.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(document.pageCount) { index ->
                    val pageLabel = stringResource(R.string.report_pdf_page, index + 1, document.pageCount)
                    Text(pageLabel, style = MaterialTheme.typography.labelSmall)
                    ComposeCanvas(Modifier.fillMaxWidth().aspectRatio(ReportDamagePdf.WIDTH.toFloat() / ReportDamagePdf.HEIGHT)
                        .semantics { contentDescription = pageLabel }) {
                        val canvas = drawContext.canvas.nativeCanvas
                        val checkpoint = canvas.save()
                        val scale = size.width / ReportDamagePdf.WIDTH
                        canvas.scale(scale, scale)
                        document.draw(canvas, index)
                        canvas.restoreToCount(checkpoint)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onClose) { Text(stringResource(R.string.close)) } },
    )
}
