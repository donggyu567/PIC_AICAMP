package com.example.pic_ai_app.presentation.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R

@Composable
internal fun PicHeader(onSettings: () -> Unit) {
    PicHeaderRow(trailing = { SettingsButton(onClick = onSettings) })
}

@Composable
internal fun PicHistoryHeader() {
    PicHeaderRow(history = true)
}

@Composable
private fun PicHeaderRow(history: Boolean = false, trailing: @Composable () -> Unit = {}) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(start = 12.dp, end = 12.dp, top = 20.dp)
            .heightIn(min = LocalMinimumInteractiveComponentSize.current),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        val style = TextStyle(fontSize = 40.sp, fontWeight = FontWeight.Bold,
            shadow = Shadow(Color.Black.copy(alpha = .25f), Offset(0f, 4f), 4f))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            if (history) Icon(painterResource(R.drawable.ic_pic_folder_filled), contentDescription = null,
                modifier = Modifier.size(42.dp), tint = Color.Black)
            Text(stringResource(R.string.app_name), Modifier.alignByBaseline(), color = Color.Black, style = style)
            if (history) Text(stringResource(R.string.tab_history), Modifier.alignByBaseline(),
                color = Color.Black, style = style.copy(fontSize = 32.sp))
        }
        trailing()
    }
}
