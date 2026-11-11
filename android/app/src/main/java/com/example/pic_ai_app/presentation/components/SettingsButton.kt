package com.example.pic_ai_app.presentation.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.PicNavigationSelected
import com.example.pic_ai_app.ui.theme.PicTheme
import com.example.pic_ai_app.ui.theme.PicWhite

@Composable
internal fun SettingsButton(onClick: () -> Unit) {
    IconButton(
        onClick = onClick,
        modifier = Modifier.size(LocalMinimumInteractiveComponentSize.current).background(PicWhite, CircleShape),
    ) {
        Icon(
            painter = painterResource(R.drawable.ic_pic_settings),
            contentDescription = stringResource(R.string.home_settings),
            modifier = Modifier.size(27.dp),
            tint = PicNavigationSelected,
        )
    }
}

@Preview(name = "설정 버튼", showBackground = true, backgroundColor = 0xFF4D6783)
@Composable
private fun SettingsButtonPreview() {
    PicTheme { SettingsButton(onClick = {}) }
}
