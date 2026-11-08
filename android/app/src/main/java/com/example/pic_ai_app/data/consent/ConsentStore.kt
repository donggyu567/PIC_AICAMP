package com.example.pic_ai_app.data.consent

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import org.json.JSONObject
import java.io.IOException
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first

enum class ConsentStatus { NOT_DECIDED, GRANTED, WITHDRAWN }

data class DeletionTarget(val serverUrl: String, val conversationId: String)

interface ConsentStore {
    suspend fun read(): ConsentStatus
    suspend fun write(status: ConsentStatus)
    suspend fun register(target: DeletionTarget) { throw IOException("session storage unavailable") }
    suspend fun deletionTargets(): Set<DeletionTarget> { throw IOException("session storage unavailable") }
    suspend fun removeTarget(target: DeletionTarget) { throw IOException("session storage unavailable") }
}

private val Context.consentDataStore by preferencesDataStore(name = "data_consent")

class DataStoreConsentStore(context: Context) : ConsentStore {
    private val applicationContext = context.applicationContext
    private val statusKey = stringPreferencesKey("status")
    private val targetsKey = stringSetPreferencesKey("deletion_targets")

    private fun encode(target: DeletionTarget) = JSONObject()
        .put("url", target.serverUrl).put("id", target.conversationId).toString()

    override suspend fun register(target: DeletionTarget) {
        applicationContext.consentDataStore.edit { preferences ->
            if (preferences[statusKey] != ConsentStatus.GRANTED.name) throw IOException("consent unavailable")
            preferences[targetsKey] = preferences[targetsKey].orEmpty() + encode(target)
        }
    }

    override suspend fun deletionTargets(): Set<DeletionTarget> {
        try {
            return applicationContext.consentDataStore.data.first()[targetsKey].orEmpty().map { raw ->
                val json = JSONObject(raw)
                DeletionTarget(json.getString("url"), json.getString("id"))
            }.toSet()
        } catch (error: Exception) {
            if (error is kotlinx.coroutines.CancellationException) throw error
            throw IOException("session storage unavailable", error)
        }
    }

    override suspend fun removeTarget(target: DeletionTarget) {
        applicationContext.consentDataStore.edit { preferences ->
            preferences[targetsKey] = preferences[targetsKey].orEmpty() - encode(target)
        }
    }

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
