package com.example.pic_ai_app.data.consent

import android.content.Context
import com.example.pic_ai_app.data.history.AnalysisRecord
import com.example.pic_ai_app.data.history.decodeAnalysisRecord
import com.example.pic_ai_app.data.history.encode
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
    suspend fun records(): List<AnalysisRecord> = emptyList()
    suspend fun saveRecord(record: AnalysisRecord) { throw IOException("history unavailable") }
    suspend fun deleteRecord(id: String) { throw IOException("history unavailable") }
}

private val Context.consentDataStore by preferencesDataStore(name = "data_consent")

class DataStoreConsentStore(context: Context) : ConsentStore {
    private val applicationContext = context.applicationContext
    private val statusKey = stringPreferencesKey("status")
    private val targetsKey = stringSetPreferencesKey("deletion_targets")
    private val recordPrefix = "history_record_"

    override suspend fun records(): List<AnalysisRecord> {
        val preferences = applicationContext.consentDataStore.data.first()
        if (preferences[statusKey] != ConsentStatus.GRANTED.name) return emptyList()
        return preferences.asMap().filterKeys { it.name.startsWith(recordPrefix) }.values
            .map { decodeAnalysisRecord(it as String) }.sortedByDescending { it.endedAtMillis }
    }

    override suspend fun saveRecord(record: AnalysisRecord) {
        applicationContext.consentDataStore.edit {
            if (it[statusKey] == ConsentStatus.GRANTED.name)
                it[stringPreferencesKey(recordPrefix + record.id)] = record.encode()
        }
    }

    override suspend fun deleteRecord(id: String) {
        applicationContext.consentDataStore.edit { it.remove(stringPreferencesKey(recordPrefix + id)) }
    }

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
            if (status != ConsentStatus.GRANTED) {
                preferences.asMap().keys.filter { it.name.startsWith(recordPrefix) }
                    .forEach { preferences.remove(stringPreferencesKey(it.name)) }
            }
        }
    }
}
