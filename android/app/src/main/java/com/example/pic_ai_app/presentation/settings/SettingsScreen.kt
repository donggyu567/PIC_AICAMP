package com.example.pic_ai_app.presentation.settings

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.app.NotificationManagerCompat
import androidx.core.net.toUri
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.pic_ai_app.BuildConfig
import com.example.pic_ai_app.R
import com.example.pic_ai_app.presentation.result.ResultDetailHeader
import com.example.pic_ai_app.ui.theme.*

internal fun Context.picAppSettingsIntent() =
    Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, "package:$packageName".toUri())

internal fun Context.openPicSystemSettings(notifications: Boolean = false) {
    if (notifications && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        try {
            startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName))
            return
        } catch (_: ActivityNotFoundException) {
            // Some devices only provide the app details page.
        }
    }
    startActivity(picAppSettingsIntent())
}

@Composable
internal fun rememberNotificationsEnabled(): Boolean {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val manager = remember(context) { NotificationManagerCompat.from(context) }
    var enabled by remember(manager) { mutableStateOf(manager.areNotificationsEnabled()) }
    DisposableEffect(owner, manager) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) enabled = manager.areNotificationsEnabled()
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }
    return enabled
}

@Composable
internal fun SettingsScreen(
    microphoneAllowed: Boolean, notificationsAllowed: Boolean,
    onBack: () -> Unit, onMicrophone: () -> Unit, onNotifications: () -> Unit,
    onData: () -> Unit, onDeveloper: (() -> Unit)? = null,
) {
    val allowed = stringResource(R.string.settings_allowed)
    val off = stringResource(R.string.settings_off)
    Surface(modifier = Modifier.fillMaxSize(), color = PicWhite, contentColor = PicNavigationSelected) {
        Column(Modifier.fillMaxSize().safeDrawingPadding(), horizontalAlignment = Alignment.CenterHorizontally) {
            ResultDetailHeader(stringResource(R.string.home_settings), onBack)
            Column(
                Modifier.widthIn(max = 480.dp).fillMaxWidth().verticalScroll(rememberScrollState())
                    .padding(horizontal = 24.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp),
            ) {
                SettingsGroup(stringResource(R.string.settings_permissions)) {
                    SettingsRow(stringResource(R.string.settings_microphone),
                        value = if (microphoneAllowed) allowed else off, onClick = onMicrophone)
                    HorizontalDivider(color = PicBorder)
                    SettingsRow(stringResource(R.string.settings_notifications),
                        value = if (notificationsAllowed) allowed else off,
                        description = if (notificationsAllowed) null else stringResource(R.string.settings_notifications_off),
                        onClick = onNotifications)
                }
                SettingsGroup(stringResource(R.string.settings_privacy)) {
                    SettingsRow(stringResource(R.string.settings_transfer), onClick = onData)
                }
                SettingsGroup(stringResource(R.string.settings_app_info)) {
                    SettingsRow(stringResource(R.string.settings_version), value = BuildConfig.VERSION_NAME)
                    if (onDeveloper != null) {
                        HorizontalDivider(color = PicBorder)
                        SettingsRow(stringResource(R.string.settings_developer), onClick = onDeveloper)
                    }
                }
            }
        }
    }
}

@Composable
private fun SettingsGroup(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, color = PicHomeBlue, fontSize = 15.sp, fontWeight = FontWeight.Bold)
        Surface(Modifier.fillMaxWidth(), color = PicWhite, contentColor = PicNavigationSelected,
            border = BorderStroke(1.dp, PicBorder), shape = RoundedCornerShape(16.dp)) {
            Column(content = content)
        }
    }
}

@Composable
private fun SettingsRow(title: String, value: String? = null, description: String? = null, onClick: (() -> Unit)? = null) {
    val action = if (onClick == null) Modifier else Modifier.clickable(role = Role.Button, onClick = onClick)
    Column(Modifier.fillMaxWidth().then(action).heightIn(min = 56.dp).padding(horizontal = 16.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.Center) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, Modifier.weight(1f), fontSize = 16.sp, fontWeight = FontWeight.Medium)
            if (value != null) Text(value, fontSize = 14.sp, color = PicHomeBlue)
            if (onClick != null) Icon(painterResource(R.drawable.result_back),
                contentDescription = null, modifier = Modifier.size(16.dp), tint = PicNavigationMuted)
        }
        if (description != null) {
            Spacer(Modifier.height(6.dp))
            Text(description, fontSize = 14.sp, lineHeight = 20.sp, color = PicMuted)
        }
    }
}

@Preview(name = "설정 · 마이크 허용, 위험 알림 꺼짐", showBackground = true, widthDp = 412, heightDp = 917)
@Composable
private fun SettingsPreview() {
    PicScreenTheme { SettingsScreen(true, false, {}, {}, {}, {}) }
}
