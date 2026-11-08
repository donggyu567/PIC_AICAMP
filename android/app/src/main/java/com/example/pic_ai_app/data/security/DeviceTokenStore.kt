package com.example.pic_ai_app.data.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.example.pic_ai_app.BuildConfig
import java.io.IOException
import java.net.URI
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** 토큰은 Android Keystore 키로 암호화하며 서버 출처에 묶어 보관한다. */
class DeviceTokenStore(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences("device_auth", Context.MODE_PRIVATE)
    private val alias = "pic_device_token_key"

    private fun origin(url: String): String {
        val uri = URI(url)
        val scheme = when (uri.scheme?.lowercase()) {
            "ws", "http" -> "http"
            "wss", "https" -> "https"
            else -> throw IOException("서버 주소가 올바르지 않습니다.")
        }
        val host = uri.host?.lowercase() ?: throw IOException("서버 주소가 올바르지 않습니다.")
        if (uri.userInfo != null) throw IOException("서버 주소가 올바르지 않습니다.")
        if (scheme == "http" && !(BuildConfig.DEBUG && host in setOf("127.0.0.1", "localhost", "10.0.2.2")))
            throw IOException("보안 연결이 필요합니다.")
        val port = if (uri.port == -1) if (scheme == "https") 443 else 80 else uri.port
        return "$scheme://$host:$port"
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return generator.generateKey()
    }

    fun save(url: String, token: String) {
        if (!token.matches(Regex("[A-Za-z0-9_-]{43}"))) throw IOException("기기 인증 정보 형식이 올바르지 않습니다.")
        try {
            val server = origin(url)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key())
            cipher.updateAAD(server.toByteArray(Charsets.UTF_8))
            val value = Base64.encodeToString(cipher.iv + cipher.doFinal(token.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
            if (!preferences.edit().putString("origin", server).putString("token", value).commit()) throw IOException("인증 정보를 저장하지 못했습니다.")
        } catch (error: Exception) {
            if (error is IOException) throw error
            throw IOException("인증 정보를 저장하지 못했습니다.", error)
        }
    }

    fun hasSavedToken(): Boolean = preferences.contains("token")

    fun forServer(url: String): String {
        try {
            val server = origin(url)
            if (preferences.getString("origin", null) != server) throw IOException("서버에 맞는 기기 인증 정보가 없습니다.")
            val encrypted = Base64.decode(preferences.getString("token", null) ?: throw IOException("기기 인증 정보가 없습니다."), Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, encrypted.copyOfRange(0, 12)))
            cipher.updateAAD(server.toByteArray(Charsets.UTF_8))
            return cipher.doFinal(encrypted.copyOfRange(12, encrypted.size)).toString(Charsets.UTF_8)
        } catch (error: Exception) {
            if (error is IOException) throw error
            throw IOException("기기 인증 정보를 읽지 못했습니다.", error)
        }
    }
}
