package com.example.pic_ai_app.presentation.report

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.*

@Composable
internal fun ReportPreparationLayout(
    @StringRes title: Int, @StringRes description: Int, onTabSelected: (PicTab) -> Unit,
    onNext: () -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
    canContinue: Boolean = true, @StringRes primaryButtonLabel: Int = R.string.report_next,
    fields: @Composable ColumnScope.() -> Unit,
) {
    ReportStepLayout(ReportStep.PrepareMaterials, title, description,
        canContinue = canContinue, onNext = onNext, onTabSelected = onTabSelected,
        primaryButtonLabel = primaryButtonLabel) {
        Column(
            Modifier.weight(1f).widthIn(max = 480.dp).fillMaxWidth()
                .verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp), content = fields,
        )
        Row(Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(horizontal = 24.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp), content = actions)
    }
}

@Composable
internal fun ReportFieldLabel(label: String) {
    Text(label, color = PicNavigationSelected, fontSize = 14.sp, fontWeight = FontWeight.Bold)
}

@Composable
internal fun ReportField(
    label: String, value: String, onEdit: (String) -> Unit, @StringRes hint: Int,
    @StringRes note: Int? = null, keyboard: KeyboardType = KeyboardType.Text,
    multiline: Boolean = note != null,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        ReportFieldLabel(label)
        OutlinedTextField(
            value = value, onValueChange = onEdit,
            modifier = Modifier.fillMaxWidth().semantics { contentDescription = label },
            placeholder = { Text(stringResource(hint), fontSize = 14.sp, color = PicMuted) },
            keyboardOptions = KeyboardOptions(keyboardType = keyboard),
            singleLine = !multiline, minLines = if (multiline) 3 else 1,
            shape = RoundedCornerShape(10.dp),
            colors = OutlinedTextFieldDefaults.colors(unfocusedBorderColor = PicBorder,
                unfocusedContainerColor = if (note == null) PicWhite else PicCard),
        )
        if (note != null) Text(stringResource(note), color = PicMuted, fontSize = 12.sp)
    }
}
