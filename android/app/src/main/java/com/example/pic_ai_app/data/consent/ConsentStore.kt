package com.example.pic_ai_app.data.consent

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first

enum class ConsentStatus { NOT_DECIDED, GRANTED, WITHDRAWN }

interface ConsentStore {
    suspend fun read(): ConsentStatus
    suspend fun write(status: ConsentStatus)
}

private val Context.consentDataStore by preferencesDataStore(name = "data_consent")

class DataStoreConsentStore(context: Context) : ConsentStore {
    private val applicationContext = context.applicationContext
    private val statusKey = stringPreferencesKey("status")

    override suspend fun read(): ConsentStatus = when (applicationContext.consentDataStore.data.first()[statusKey]) {
        ConsentStatus.GRANTED.name -> ConsentStatus.GRANTED
        ConsentStatus.WITHDRAWN.name -> ConsentStatus.WITHDRAWN
        else -> ConsentStatus.NOT_DECIDED
    }

    override suspend fun write(status: ConsentStatus) {
        applicationContext.consentDataStore.edit { preferences ->
            preferences[statusKey] = status.name
        }
    }
}
