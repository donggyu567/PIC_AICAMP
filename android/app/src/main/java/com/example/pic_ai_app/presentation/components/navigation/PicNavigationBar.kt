package com.example.pic_ai_app.presentation.components.navigation

import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pic_ai_app.R
import com.example.pic_ai_app.ui.theme.*

enum class PicTab(@StringRes val label: Int, @DrawableRes val icon: Int) {
    Home(R.string.tab_home, R.drawable.ic_pic_home),
    Analysis(R.string.tab_analysis, R.drawable.ic_pic_bar_chart),
    History(R.string.tab_history, R.drawable.ic_pic_folder),
    Report(R.string.tab_report, R.drawable.ic_pic_report),
}

@Composable
fun PicNavigationBar(
    selectedTab: PicTab,
    onTabSelected: (PicTab) -> Unit,
    availableTabs: Set<PicTab> = PicTab.entries.toSet(),
) {
    Column {
        HorizontalDivider(color = PicBorder)
        NavigationBar(containerColor = PicWhite, tonalElevation = 0.dp) {
            PicTab.entries.forEach { tab ->
                val selected = tab == selectedTab
                NavigationBarItem(
                    modifier = Modifier.heightIn(min = LocalMinimumInteractiveComponentSize.current),
                    selected = selected,
                    enabled = tab in availableTabs,
                    onClick = { onTabSelected(tab) },
                    icon = { Icon(painterResource(tab.icon), contentDescription = null, modifier = Modifier.size(24.dp)) },
                    label = {
                        Text(stringResource(tab.label), fontSize = 11.sp,
                            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal)
                    },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = PicNavigationSelected, selectedTextColor = PicNavigationSelected,
                        unselectedIconColor = PicNavigationMuted, unselectedTextColor = PicNavigationMuted,
                        disabledIconColor = PicNavigationMuted, disabledTextColor = PicNavigationMuted,
                        indicatorColor = Color.Transparent,
                    ),
                )
            }
        }
    }
}

@Preview(name = "하단 내비게이션 · 홈 선택", widthDp = 412, showBackground = true)
@Composable
private fun PicNavigationBarPreview() {
    PicTheme {
        PicNavigationBar(
            selectedTab = PicTab.Home,
            availableTabs = setOf(PicTab.Home),
            onTabSelected = {},
        )
    }
}
