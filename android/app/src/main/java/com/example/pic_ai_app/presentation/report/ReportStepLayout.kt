package com.example.pic_ai_app.presentation.report

import androidx.annotation.StringRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.components.PicReportHeader
import com.example.pic_ai_app.presentation.components.navigation.PicNavigationBar
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.*

@Composable
internal fun ReportStepLayout(
    step: ReportStep, @StringRes title: Int, @StringRes description: Int,
    canContinue: Boolean, onNext: () -> Unit, onTabSelected: (PicTab) -> Unit,
    @StringRes primaryButtonLabel: Int = R.string.report_next,
    content: @Composable ColumnScope.() -> Unit,
) {
    Scaffold(containerColor = PicWhite, bottomBar = { PicNavigationBar(PicTab.Report, onTabSelected) }) { insets ->
        Column(Modifier.fillMaxSize().padding(insets), horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(horizontal = 24.dp)) {
                PicReportHeader()
            }
            Spacer(Modifier.height(20.dp))
            ReportStepIndicator(step, Modifier.widthIn(max = 480.dp))
            Column(
                Modifier.widthIn(max = 480.dp).fillMaxWidth().padding(start = 24.dp, top = 12.dp, end = 24.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(stringResource(title), color = PicNavigationSelected,
                    fontSize = 24.sp, lineHeight = 32.sp, fontWeight = FontWeight.Bold)
                Text(stringResource(description), color = PicMuted, fontSize = 15.sp)
            }
            content()
            Button(
                enabled = canContinue, onClick = onNext,
                modifier = Modifier.widthIn(max = 480.dp).fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 12.dp).heightIn(min = 52.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = reportActiveColor, contentColor = PicWhite),
            ) {
                Text(stringResource(primaryButtonLabel), fontSize = 16.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
internal fun ReportRadioOption(
    selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier,
    content: @Composable RowScope.() -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(), shape = RoundedCornerShape(15.dp),
        color = if (selected) Color(0xFFEEF4F8) else PicWhite,
        border = if (selected) BorderStroke(2.dp, reportActiveColor) else BorderStroke(1.dp, PicBorder),
    ) {
        Row(
            Modifier.selectable(selected = selected, role = Role.RadioButton, onClick = onSelect).padding(16.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            RadioButton(selected = selected, onClick = null,
                colors = RadioButtonDefaults.colors(selectedColor = reportActiveColor, unselectedColor = PicMuted))
            content()
        }
    }
}
