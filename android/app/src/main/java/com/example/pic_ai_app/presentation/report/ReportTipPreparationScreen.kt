package com.example.pic_ai_app.presentation.report

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.data.report.ReportWorkflow
import com.example.pic_ai_app.data.report.TipCategory as SuggestedCategory
import com.example.pic_ai_app.presentation.components.navigation.PicTab

internal class ReportTipFields(suggestedCategory: SuggestedCategory? = null) {
    var selectedDate by mutableStateOf<Long?>(null)
    var isAfternoon by mutableStateOf(false)
    var hour by mutableStateOf("")
    var minute by mutableStateOf("")
    internal var first by mutableStateOf(when (suggestedCategory) {
        SuggestedCategory.Impersonation -> TipCategory.Impersonation
        SuggestedCategory.CallerIdManipulation -> TipCategory.Spoofing
        SuggestedCategory.Loan -> TipCategory.Loan
        SuggestedCategory.Advertising -> TipCategory.Advertising
        null -> null
    })
    internal var second by mutableStateOf<TipCategory?>(null)
    internal var third by mutableStateOf<TipCategory?>(null)

    @Composable
    fun categoryLabel(): String =
        listOfNotNull(first, second, third).map { stringResource(it.label) }.joinToString(" → ")
}

@Composable
internal fun ReportTipPreparationScreen(
    workflow: ReportWorkflow, fields: ReportTipFields, onChange: (ReportWorkflow) -> Unit,
    onNext: () -> Unit, onTabSelected: (PicTab) -> Unit,
    summaryNotice: @Composable () -> Unit,
) {
    val selectedDate = fields.selectedDate
    val dateText = remember(selectedDate) { selectedDate?.let(::formatReportDate).orEmpty() }
    val period = stringResource(if (fields.isAfternoon) R.string.report_pm else R.string.report_am)
    val hour = fields.hour.toIntOrNull()
    val minute = fields.minute.toIntOrNull()
    val receivedAt = if (selectedDate != null && hour != null && hour in 1..12 && minute != null && minute in 0..59) {
        "$dateText $period $hour:${minute.toString().padStart(2, '0')}"
    } else ""
    val draft = workflow.tip
    val context = LocalContext.current
    val phoneLabel = stringResource(R.string.report_phone)
    val categoryLabel = stringResource(R.string.report_category)
    val bodyLabel = stringResource(R.string.report_tip_body)
    val copyText = workflow.tipCopyText()

    ReportPreparationLayout(
        R.string.report_tip_title, R.string.report_tip_description, onTabSelected,
        onNext = {
            onChange(workflow.editTip(draft.copy(receivedAt = receivedAt)))
            onNext()
        },
        actions = {
            OutlinedButton(
                modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
                enabled = copyText.isNotBlank(),
                onClick = { copyReportText(context, bodyLabel, copyText, R.string.report_copied) },
            ) { Text(stringResource(R.string.report_copy)) }
        },
    ) {
        ReportField(phoneLabel, draft.callerNumber,
            { onChange(workflow.editTip(draft.copy(callerNumber = it))) }, R.string.report_phone_hint,
            keyboard = KeyboardType.Phone)
        ReportReceivedTimeField(
            date = selectedDate, dateText = dateText, period = period, hour = fields.hour, minute = fields.minute,
            onDateChange = { fields.selectedDate = it }, onPeriodChange = { fields.isAfternoon = it },
            onHourChange = { fields.hour = it }, onMinuteChange = { fields.minute = it },
        )
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            ReportFieldLabel(categoryLabel)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                CategoryMenu(1, fields.first, TipCategory.entries.filter { it.parent == null }, Modifier.weight(1f)) {
                    if (fields.first != it) {
                        fields.first = it
                        fields.second = null
                        fields.third = null
                    }
                }
                CategoryMenu(2, fields.second, fields.first?.children.orEmpty(), Modifier.weight(1f)) {
                    if (fields.second != it) {
                        fields.second = it
                        fields.third = null
                    }
                }
                CategoryMenu(3, fields.third, fields.second?.children.orEmpty(), Modifier.weight(1f)) { fields.third = it }
            }
        }
        summaryNotice()
        ReportField(stringResource(R.string.report_editable, bodyLabel), draft.body,
            { onChange(workflow.editTip(draft.copy(body = it))) }, R.string.report_narrative_hint, R.string.report_summary_review)
        ReportReferenceChoices(workflow, onChange)
    }
}

internal enum class TipCategory(@StringRes val label: Int, val parent: TipCategory? = null) {
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
