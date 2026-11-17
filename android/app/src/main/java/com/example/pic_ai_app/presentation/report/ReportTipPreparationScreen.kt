package com.example.pic_ai_app.presentation.report

import androidx.activity.compose.BackHandler
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.history.AnalysisRecord
import com.example.pic_ai_app.data.stt.SttState
import com.example.pic_ai_app.presentation.components.navigation.PicTab
import com.example.pic_ai_app.ui.theme.PicScreenTheme

@Composable
internal fun ReportTipPreparationScreen(call: AnalysisRecord, onTabSelected: (PicTab) -> Unit) {
    var phone by rememberSaveable(call.id) { mutableStateOf("") }
    var selectedDate by rememberSaveable(call.id) { mutableStateOf<Long?>(null) }
    var isAfternoon by rememberSaveable(call.id) { mutableStateOf(false) }
    var hour by rememberSaveable(call.id) { mutableStateOf("") }
    var minute by rememberSaveable(call.id) { mutableStateOf("") }
    val dateText = remember(selectedDate) { selectedDate?.let(::formatReportDate).orEmpty() }
    val period = stringResource(if (isAfternoon) R.string.report_pm else R.string.report_am)
    val hourNumber = hour.toIntOrNull()
    val minuteNumber = minute.toIntOrNull()
    val timeText = if (hourNumber != null && hourNumber in 1..12 && minuteNumber != null && minuteNumber in 0..59) {
        "$period $hourNumber:${minute.padStart(2, '0')}"
    } else ""
    val receivedAt = listOf(dateText, timeText).filter { it.isNotEmpty() }.joinToString(" ")
    var first by rememberSaveable(call.id) { mutableStateOf<TipCategory?>(null) }
    var second by rememberSaveable(call.id) { mutableStateOf<TipCategory?>(null) }
    var third by rememberSaveable(call.id) { mutableStateOf<TipCategory?>(null) }
    val category = listOfNotNull(first, second, third).map { stringResource(it.label) }.joinToString(" → ")
    var editedBody by rememberSaveable(call.id) { mutableStateOf<String?>(null) }
    val transcript = remember(call.result.maskedTexts) { call.result.maskedTexts.joinToString("\n") }
    val body = editedBody ?: transcript
    val context = LocalContext.current
    val phoneLabel = stringResource(R.string.report_phone)
    val timeLabel = stringResource(R.string.report_received_time)
    val categoryLabel = stringResource(R.string.report_category)
    val bodyLabel = stringResource(R.string.report_tip_body)
    var showGuidance by rememberSaveable(call.id) { mutableStateOf(false) }
    BackHandler(enabled = showGuidance) { showGuidance = false }
    if (showGuidance) {
        ReportTipGuidanceScreen(phone, receivedAt, category, onTabSelected)
        return
    }

    ReportPreparationLayout(R.string.report_tip_title, R.string.report_tip_description, onTabSelected,
        onNext = { showGuidance = true },
        actions = {
            OutlinedButton(
                modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
                enabled = listOf(phone, receivedAt, category, body).any { it.isNotBlank() },
                onClick = {
                    val text = reportText(phoneLabel to phone, timeLabel to receivedAt,
                        categoryLabel to category, bodyLabel to body)
                    copyReportText(context, bodyLabel, text, R.string.report_copied)
                },
            ) { Text(stringResource(R.string.report_copy)) }
        },
    ) {
        ReportField(phoneLabel, phone, { phone = it }, R.string.report_phone_hint, keyboard = KeyboardType.Phone)
        ReportReceivedTimeField(
            date = selectedDate, dateText = dateText, period = period, hour = hour, minute = minute,
            onDateChange = { selectedDate = it }, onPeriodChange = { isAfternoon = it },
            onHourChange = { hour = it }, onMinuteChange = { minute = it },
        )
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            ReportFieldLabel(categoryLabel)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                CategoryMenu(1, first, TipCategory.entries.filter { it.parent == null }, Modifier.weight(1f)) {
                    if (first != it) {
                        first = it
                        second = null
                        third = null
                    }
                }
                CategoryMenu(2, second, first?.children.orEmpty(), Modifier.weight(1f)) {
                    if (second != it) {
                        second = it
                        third = null
                    }
                }
                CategoryMenu(3, third, second?.children.orEmpty(), Modifier.weight(1f)) { third = it }
            }
        }
        ReportField(stringResource(R.string.report_editable, bodyLabel), body, { editedBody = it },
            R.string.report_narrative_hint, R.string.report_masked_tip)
    }
}

private enum class TipCategory(@StringRes val label: Int, val parent: TipCategory? = null) {
    Impersonation(R.string.report_category_impersonation),
    Spoofing(R.string.report_category_spoofing),
    Loan(R.string.report_category_loan),
    Advertising(R.string.report_category_advertising),
    Other(R.string.report_category_other),
    PublicAgency(R.string.report_category_public, Impersonation),
    Finance(R.string.report_category_finance, Impersonation),
    Unreachable(R.string.report_category_unreachable, Spoofing),
    Unassigned(R.string.report_category_unassigned, Spoofing),
    OtherSpoofing(R.string.report_category_other, Spoofing),
    Lender(R.string.report_category_lender, Loan),
    Capital(R.string.report_category_capital, Loan),
    AdultAd(R.string.report_category_adult_ad, Advertising),
    Gambling(R.string.report_category_gambling, Advertising),
    OtherAd(R.string.report_category_other_ad, Advertising),
    Prosecution(R.string.report_category_prosecution, PublicAgency),
    Police(R.string.report_category_police, PublicAgency),
    FinancialSupervisoryService(R.string.report_category_fss, PublicAgency),
    FinancialServicesCommission(R.string.report_category_fsc, PublicAgency),
    Bank(R.string.report_category_bank, Finance),
    SavingsBank(R.string.report_category_savings_bank, Finance),
    CardCompany(R.string.report_category_card_company, Finance),
    Insurer(R.string.report_category_insurer, Finance),
    Securities(R.string.report_category_securities, Finance);

    val children: List<TipCategory> get() = entries.filter { it.parent == this }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CategoryMenu(
    level: Int, selected: TipCategory?, options: List<TipCategory>, modifier: Modifier,
    onSelect: (TipCategory?) -> Unit,
) {
    var expanded by remember(options) { mutableStateOf(false) }
    val placeholder = stringResource(R.string.report_choose_category)
    val label = selected?.let { stringResource(it.label) } ?: placeholder
    val levelLabel = stringResource(R.string.report_category_level, level)
    Box(modifier) {
        OutlinedButton(
            onClick = { expanded = true }, enabled = options.isNotEmpty(),
            modifier = Modifier.fillMaxWidth().semantics { contentDescription = "$levelLabel, $label" },
            shape = RoundedCornerShape(10.dp), contentPadding = PaddingValues(horizontal = 6.dp),
        ) {
            Text(label, Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
            ExposedDropdownMenuDefaults.TrailingIcon(expanded)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(text = { Text(placeholder) }, onClick = {
                expanded = false
                onSelect(null)
            })
            options.forEach { option ->
                DropdownMenuItem(text = { Text(stringResource(option.label)) }, onClick = {
                    expanded = false
                    onSelect(option)
                })
            }
        }
    }
}

@Preview(name = "신고 03A · 제보 자료 준비", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun ReportTipPreparationPreview() {
    PicScreenTheme {
        ReportTipPreparationScreen(AnalysisRecord("preview", 0L,
            SttState(maskedTexts = listOf("안전 계좌로 돈을 옮겨 주세요."))), {})
    }
}
