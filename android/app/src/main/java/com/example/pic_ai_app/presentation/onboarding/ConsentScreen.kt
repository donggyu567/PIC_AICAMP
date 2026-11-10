package com.example.pic_ai_app.presentation.onboarding

import android.Manifest.permission.POST_NOTIFICATIONS
import android.Manifest.permission.RECORD_AUDIO
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts.RequestPermission
import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.fromHtml
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicTheme
import kotlinx.coroutines.launch

@Composable
internal fun OnboardingPermissions(savingConsent: Boolean, onAgree: () -> Unit) {
    val context = LocalContext.current
    val messages = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    var requesting by rememberSaveable { mutableStateOf(false) }
    var showVoiceDataConsent by rememberSaveable { mutableStateOf(false) }

    fun hasPermission(permission: String) =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    fun finishRequest(granted: Boolean) {
        requesting = false
        messages.currentSnackbarData?.dismiss()
        showVoiceDataConsent = granted
        if (granted) return
        scope.launch {
            messages.showSnackbar(context.getString(R.string.onboarding_permission_denied))
        }
    }

    val microphone = rememberLauncherForActivityResult(RequestPermission(), ::finishRequest)
    fun requestMicrophone() {
        if (hasPermission(RECORD_AUDIO)) finishRequest(true) else microphone.launch(RECORD_AUDIO)
    }
    val notifications = rememberLauncherForActivityResult(RequestPermission()) { granted ->
        if (granted) requestMicrophone() else finishRequest(false)
    }

    if (showVoiceDataConsent) {
        BackHandler { if (!savingConsent) showVoiceDataConsent = false }
        VoiceDataConsentScreen(savingConsent = savingConsent, onAgree = {
            val notificationsAllowed = Build.VERSION.SDK_INT < 33 || hasPermission(POST_NOTIFICATIONS)
            if (notificationsAllowed && hasPermission(RECORD_AUDIO)) onAgree() else finishRequest(false)
        })
        return
    }

    ConsentScreen(
        onRequestPermissions = {
            if (!requesting) {
                requesting = true
                if (Build.VERSION.SDK_INT >= 33 && !hasPermission(POST_NOTIFICATIONS)) {
                    notifications.launch(POST_NOTIFICATIONS)
                } else {
                    requestMicrophone()
                }
            }
        },
        requesting = requesting,
        statusBanner = { SnackbarHost(messages, Modifier.padding(horizontal = 16.dp)) },
    )
}

@Composable
internal fun ConsentScreen(
    onRequestPermissions: () -> Unit,
    requesting: Boolean = false,
    statusBanner: @Composable () -> Unit = {},
) {
    BoxWithConstraints(
        Modifier.fillMaxSize().background(Color.White).safeDrawingPadding(),
        contentAlignment = Alignment.TopCenter,
    ) {
        val topSpace = (maxHeight * 0.16f).coerceAtMost(150.dp)
        val sectionSpace = (maxHeight * 0.04f).coerceIn(16.dp, 40.dp)
        Column(
            modifier = Modifier.widthIn(max = 412.dp).fillMaxSize().padding(horizontal = 30.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(
                modifier = Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Spacer(Modifier.height(topSpace))
                Text(
                    text = stringResource(R.string.onboarding_consent_title),
                    color = Color.Black, fontSize = 30.sp, lineHeight = 38.sp,
                    fontWeight = FontWeight.Bold, textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    text = stringResource(R.string.onboarding_consent_intro),
                    color = Color.DarkGray, fontSize = 20.sp, lineHeight = 26.sp,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(sectionSpace))
                ConsentNotice(R.drawable.ic_onboarding_alert, R.string.onboarding_alert_notice)
                Spacer(Modifier.height(sectionSpace))
                ConsentNotice(R.drawable.ic_onboarding_mic, R.string.onboarding_mic_notice)
                Spacer(Modifier.height(sectionSpace))
                ConsentNotice(R.drawable.ic_onboarding_data_table, R.string.onboarding_transfer_notice)
                Text(
                    text = stringResource(R.string.consent_details_hint),
                    color = Color.DarkGray,
                )
            }
            Button(
                onClick = onRequestPermissions, enabled = !requesting,
                modifier = Modifier
                    .fillMaxWidth()
                    .offset(y = (-20).dp)
                    .heightIn(min = 63.dp),
                shape = RoundedCornerShape(15.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4C6681)),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp),
            ) {
                Text(
                    text = stringResource(R.string.consent_start_pic),
                    color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold,
                )
            }
            Text(
                text = stringResource(R.string.decline),
                color = Color.DarkGray,
                fontSize = 15.sp,
            )
        }
        statusBanner()
    }
}

@Composable
private fun ConsentNotice(@DrawableRes icon: Int, @StringRes message: Int) {
    Image(painterResource(icon), contentDescription = null, modifier = Modifier.size(50.dp))
    Spacer(Modifier.height(18.dp))
    Text(
        text = AnnotatedString.fromHtml(stringResource(message)),
        color = Color(0xFF393939), fontSize = 19.sp, lineHeight = 25.sp,
        textAlign = TextAlign.Center,
    )
}

@Preview(name = "온보딩 권한동의", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun ConsentScreenPreview() {
    PicTheme {
        ConsentScreen(onRequestPermissions = {})
    }
}
