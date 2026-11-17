package com.example.pic_ai_app.presentation.onboarding

import androidx.annotation.StringRes
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.zIndex
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicTheme

@Composable
internal fun VoiceDataConsentScreen(savingConsent: Boolean, onAgree: () -> Unit) {
    Column(Modifier.fillMaxSize().background(Color.White).windowInsetsPadding(
        WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal)
    )) {
        Box(
            Modifier.fillMaxWidth().zIndex(1f).shadow(4.dp).background(Color.White)
                .heightIn(min = 108.dp).statusBarsPadding().padding(horizontal = 21.dp, vertical = 14.dp),
            contentAlignment = Alignment.BottomStart,
        ) {
            Text(stringResource(R.string.voice_consent_title), fontSize = 23.sp,
                fontWeight = FontWeight.ExtraBold, color = Color.Black)
        }
        Column(
            Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                .padding(start = 28.dp, end = 29.dp, top = 14.dp, bottom = 14.dp),
        ) {
            ProvideTextStyle(TextStyle(color = Color.Black, fontSize = 18.sp, lineHeight = 30.sp)) {
                Text(stringResource(R.string.voice_consent_intro))
                ConsentSection(R.string.voice_consent_purpose, R.string.voice_consent_purpose_body)
                ConsentSection(R.string.voice_consent_information, R.string.voice_consent_information_body)
                ConsentSection(R.string.voice_consent_transfer, R.string.voice_consent_transfer_body)
                ConsentSection(R.string.voice_consent_retention, R.string.voice_consent_retention_body)
                ConsentSection(R.string.voice_consent_refusal, R.string.voice_consent_refusal_body, FontWeight.Medium)
                ConsentSection(R.string.voice_consent_withdrawal, R.string.voice_consent_withdrawal_body)
            }
        }
        Row(
            Modifier.fillMaxWidth().shadow(4.dp).background(Color.White).heightIn(min = 109.dp)
                .navigationBarsPadding()
                .toggleable(value = savingConsent, enabled = !savingConsent, role = Role.Checkbox,
                    onValueChange = { onAgree() })
                .padding(start = 42.dp, end = 32.dp, top = 20.dp, bottom = 18.dp),
        ) {
            Checkbox(checked = savingConsent, onCheckedChange = null,
                modifier = Modifier.padding(top = 4.dp).size(16.dp),
                colors = CheckboxDefaults.colors(uncheckedColor = Color.Black))
            Spacer(Modifier.width(6.dp))
            Text(stringResource(R.string.voice_consent_accept), fontSize = 20.sp, lineHeight = 24.sp,
                fontWeight = FontWeight.Medium, color = Color.Black)
        }
    }
}

@Composable
private fun ConsentSection(@StringRes title: Int, @StringRes body: Int, weight: FontWeight = FontWeight.Bold) {
    Text(stringResource(title), modifier = Modifier.padding(start = 4.dp), fontWeight = weight)
    Text(stringResource(body))
}

@Preview(name = "온보딩 - 음성데이터 전송 자세한 안내", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun VoiceDataConsentPreview() {
    PicTheme { VoiceDataConsentScreen(savingConsent = false, onAgree = {}) }
}
