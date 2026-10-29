package com.example.pic_ai_app

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.ViewModelProvider
import com.example.pic_ai_app.presentation.session.SessionViewModel
import com.example.pic_ai_app.presentation.PicApp
import com.example.pic_ai_app.ui.theme.PicTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
        )
        val session = ViewModelProvider(this, SessionViewModel.factory(this))[SessionViewModel::class.java]
        setContent {
            PicTheme {
                PicApp(session)
            }
        }
    }
}
