package com.example.pic_ai_app.presentation.report

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.report.ReportWorkflow
import com.example.pic_ai_app.ui.theme.PicMuted
import com.example.pic_ai_app.ui.theme.PicNavigationSelected

@Composable
internal fun ReportReferenceChoices(workflow: ReportWorkflow, onChange: (ReportWorkflow) -> Unit) {
    val references = workflow.call?.references.orEmpty()
    if (references.isEmpty()) return
    var expanded by remember { mutableStateOf(false) }
    if (workflow.referenceIds.isNotEmpty()) {
        Text(stringResource(R.string.report_masked_transcript_heading), color = PicMuted, fontSize = 13.sp)
    }
    TextButton(onClick = { expanded = !expanded }) {
        Text(stringResource(R.string.report_reference_count, workflow.referenceIds.size))
    }
    if (expanded) {
        Text(stringResource(R.string.report_reference_note), color = PicMuted, fontSize = 12.sp)
        references.forEach { reference ->
            val id = reference.utteranceId
            val checked = id in workflow.referenceIds
            Row(
                Modifier.fillMaxWidth().heightIn(min = 44.dp).toggleable(checked, role = Role.Checkbox) {
                    onChange(workflow.selectReferences(if (it) workflow.referenceIds + id else workflow.referenceIds - id))
                },
                horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically,
            ) {
                Checkbox(checked = checked, onCheckedChange = null)
                Text(reference.maskedText, color = PicNavigationSelected, fontSize = 14.sp)
            }
        }
    }
}
