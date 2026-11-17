package com.example.pic_ai_app.presentation.report

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicBorder
import com.example.pic_ai_app.ui.theme.PicMuted
import com.example.pic_ai_app.ui.theme.PicNavigationSelected
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

// Material DatePicker represents calendar days at midnight UTC.
internal fun formatReportDate(utcMillis: Long): String =
    SimpleDateFormat("yyyy.MM.dd", Locale.KOREA).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }.format(Date(utcMillis))

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ReportReceivedTimeField(
    date: Long?, dateText: String, period: String, hour: String, minute: String,
    onDateChange: (Long) -> Unit, onPeriodChange: (Boolean) -> Unit,
    onHourChange: (String) -> Unit, onMinuteChange: (String) -> Unit,
) {
    var calendarOpen by rememberSaveable { mutableStateOf(false) }
    var periodOpen by remember { mutableStateOf(false) }
    val am = stringResource(R.string.report_am)
    val pm = stringResource(R.string.report_pm)
    val shape = RoundedCornerShape(10.dp)
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        ReportFieldLabel(stringResource(R.string.report_received_time))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(
                onClick = { calendarOpen = true }, modifier = Modifier.weight(1.55f).heightIn(min = 48.dp),
                shape = shape, contentPadding = PaddingValues(horizontal = 4.dp),
            ) {
                if (date == null) {
                    Icon(painterResource(android.R.drawable.ic_menu_today),
                        contentDescription = stringResource(R.string.report_choose_date), modifier = Modifier.size(24.dp))
                } else {
                    Text(dateText, fontSize = 14.sp, textAlign = TextAlign.Center)
                }
            }
            Box(Modifier.weight(1.15f)) {
                OutlinedButton(onClick = { periodOpen = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
                    shape = shape, contentPadding = PaddingValues(horizontal = 2.dp)) {
                    Text(period, fontSize = 14.sp)
                    ExposedDropdownMenuDefaults.TrailingIcon(periodOpen)
                }
                DropdownMenu(expanded = periodOpen, onDismissRequest = { periodOpen = false }) {
                    DropdownMenuItem(text = { Text(am) }, onClick = { onPeriodChange(false); periodOpen = false })
                    DropdownMenuItem(text = { Text(pm) }, onClick = { onPeriodChange(true); periodOpen = false })
                }
            }
            TimeNumberField(hour, stringResource(R.string.report_hour), 12, ImeAction.Next, Modifier.weight(1f), onHourChange)
            TimeNumberField(minute, stringResource(R.string.report_minute), 59, ImeAction.Done, Modifier.weight(1f), onMinuteChange)
        }
        val hasPartialTime = (hour.isNotEmpty() || minute.isNotEmpty()) &&
            ((hour.toIntOrNull() ?: 0) !in 1..12 || minute.isEmpty())
        if (hasPartialTime) {
            Text(stringResource(R.string.report_time_incomplete), color = PicMuted, fontSize = 12.sp)
        }
    }
    if (calendarOpen) {
        val picker = rememberDatePickerState(initialSelectedDateMillis = date)
        DatePickerDialog(
            onDismissRequest = { calendarOpen = false },
            confirmButton = {
                TextButton(enabled = picker.selectedDateMillis != null, onClick = {
                    picker.selectedDateMillis?.let(onDateChange)
                    calendarOpen = false
                }) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = {
                TextButton(onClick = { calendarOpen = false }) { Text(stringResource(R.string.cancel)) }
            },
        ) { DatePicker(state = picker, showModeToggle = false) }
    }
}

@Composable
private fun TimeNumberField(
    value: String, unit: String, max: Int, imeAction: ImeAction, modifier: Modifier, onChange: (String) -> Unit,
) {
    BasicTextField(
        value = value, onValueChange = { input ->
            if (input.isEmpty() || (input.length <= 2 && input.all { it in '0'..'9' } && input.toInt() <= max)) {
                onChange(input)
            }
        },
        singleLine = true,
        modifier = modifier.semantics { contentDescription = unit },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = imeAction),
        textStyle = MaterialTheme.typography.bodyMedium.copy(color = PicNavigationSelected, textAlign = TextAlign.End),
        decorationBox = { input ->
            Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).border(1.dp, PicBorder, RoundedCornerShape(10.dp))
                .padding(horizontal = 6.dp), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                Box(Modifier.weight(1f)) { input() }
                Text(unit, color = PicMuted, fontSize = 14.sp)
            }
        },
    )
}
