package com.example.pic_ai_app.presentation.components.analysis

import androidx.annotation.DrawableRes
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.ui.theme.PicHomeBlue
import com.example.pic_ai_app.ui.theme.PicWhite
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

@Composable
internal fun AnalysisCardHeader(@DrawableRes iconRes: Int, title: String, timeMillis: Long?) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(
            Modifier.size(32.dp).background(PicHomeBlue, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(iconRes), contentDescription = null, tint = PicWhite)
        }
        Text(
            title,
            Modifier.weight(1f),
            color = PicHomeBlue, fontWeight = FontWeight.Bold, fontSize = 15.sp,
        )
        timeMillis?.let { millis ->
            val time = remember(millis) {
                SimpleDateFormat("HH:mm", Locale.KOREA).apply {
                    timeZone = TimeZone.getTimeZone("Asia/Seoul")
                }.format(Date(millis))
            }
            Text(time, color = PicHomeBlue, fontWeight = FontWeight.Bold, fontSize = 15.sp)
        }
    }
}
