package com.example.pic_ai_app.presentation.session

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.pic_ai_app.BuildConfig
import com.example.pic_ai_app.data.consent.*
import com.example.pic_ai_app.presentation.preview.*
import java.io.IOException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SessionUiState(
    val flow: PreviewState = PreviewState(),
    val ready: Boolean = false,
    val consent: ConsentStatus = ConsentStatus.NOT_DECIDED,
    val savingConsent: Boolean = false,
    val pendingConsent: ConsentStatus? = null,
    val consentError: Boolean = false,
    val permissionRequestPending: Boolean = false,
    val permissionDenied: Boolean = false,
    val declined: Boolean = false,
)

class SessionViewModel(
    private val consentStore: ConsentStore,
    private val hasMicrophonePermission: () -> Boolean,
    private val previewEnabled: Boolean,
) : ViewModel() {
    private val mutableUi = MutableStateFlow(SessionUiState())
    val ui = mutableUi.asStateFlow()

    init { loadConsent() }

    private fun loadConsent() {
        mutableUi.update { it.copy(ready = false, consentError = false) }
        viewModelScope.launch {
            try {
                val consent = consentStore.read()
                mutableUi.value = SessionUiState(
                    flow = SessionAccess.initial(consent, hasMicrophonePermission()),
                    ready = true, consent = consent,
                )
            } catch (_: IOException) {
                mutableUi.value = SessionUiState(ready = true, consentError = true)
            }
        }
    }

    private fun changeFlow(transform: (PreviewState) -> PreviewState) {
        mutableUi.update { it.copy(flow = transform(it.flow)) }
    }

    fun refreshPermission() {
        val granted = hasMicrophonePermission()
        mutableUi.update { current ->
            val flow = SessionAccess.permissionChanged(current.flow, granted)
            current.copy(
                flow = if (granted && current.consent == ConsentStatus.GRANTED &&
                    current.pendingConsent == null && flow.screen == Screen.PERMISSION) {
                    PreviewFlow.allowPermission(flow)
                } else flow,
                permissionDenied = if (granted) false else current.permissionDenied,
            )
        }
    }

    fun agree() {
        if (!ui.value.ready || ui.value.savingConsent) return
        persistConsent(ConsentStatus.GRANTED)
    }

    fun decline() {
        if (!ui.value.ready || ui.value.savingConsent) return
        mutableUi.update {
            it.copy(
                consent = ConsentStatus.NOT_DECIDED, declined = true,
                flow = SessionAccess.initial(ConsentStatus.NOT_DECIDED, hasMicrophonePermission())
                    .copy(runId = it.flow.runId + 1),
            )
        }
        persistConsent(ConsentStatus.NOT_DECIDED)
    }

    fun withdraw() {
        if (!ui.value.ready || ui.value.savingConsent) return
        // Block callbacks immediately, before the durable write finishes.
        mutableUi.update { it.copy(consent = ConsentStatus.WITHDRAWN, flow = PreviewFlow.withdraw(it.flow)) }
        persistConsent(ConsentStatus.WITHDRAWN)
    }

    private fun persistConsent(choice: ConsentStatus) {
        mutableUi.update { it.copy(savingConsent = true, pendingConsent = choice, consentError = false) }
        viewModelScope.launch {
            try {
                consentStore.write(choice)
                mutableUi.update { current ->
                    val granted = hasMicrophonePermission()
                    val flow = if (choice == ConsentStatus.GRANTED) {
                        PreviewFlow.agree(current.flow.copy(permissionGranted = granted))
                    } else current.flow.copy(consented = false, permissionGranted = granted)
                    current.copy(
                        flow = flow, consent = choice, savingConsent = false,
                        pendingConsent = null, consentError = false,
                        declined = if (choice == ConsentStatus.GRANTED) false else current.declined,
                    )
                }
            } catch (_: IOException) {
                mutableUi.update { it.copy(savingConsent = false, consentError = true) }
            }
        }
    }

    fun retryConsent() {
        if (!ui.value.ready || ui.value.savingConsent) return
        ui.value.pendingConsent?.let { persistConsent(it) } ?: loadConsent()
    }

    fun requestPermission(): Boolean {
        val current = ui.value
        if (!current.ready || current.savingConsent || current.pendingConsent != null || current.permissionRequestPending) return false
        if (current.consent != ConsentStatus.GRANTED) {
            openConsent()
            return false
        }
        if (hasMicrophonePermission()) {
            changeFlow(PreviewFlow::allowPermission)
            return false
        }
        mutableUi.update { it.copy(permissionRequestPending = true, permissionDenied = false) }
        return true
    }

    fun permissionResult() {
        refreshPermission()
        val granted = hasMicrophonePermission()
        mutableUi.update { current ->
            current.copy(
                permissionRequestPending = false, permissionDenied = !granted,
                flow = if (granted && current.ready && current.consent == ConsentStatus.GRANTED &&
                    current.pendingConsent == null && current.flow.screen == Screen.PERMISSION) {
                    PreviewFlow.allowPermission(current.flow)
                } else current.flow,
            )
        }
    }

    fun start() {
        refreshPermission()
        val current = ui.value
        if (!previewEnabled || !current.ready || current.savingConsent || current.pendingConsent != null) return
        changeFlow(PreviewFlow::start)
    }

    fun openConsent() {
        if (ui.value.savingConsent) return
        mutableUi.update { it.copy(declined = false, flow = it.flow.copy(screen = Screen.CONSENT)) }
    }

    fun deferPermission() {
        if (!ui.value.permissionRequestPending) changeFlow { it.copy(screen = Screen.HOME) }
    }

    fun openData() = changeFlow(PreviewFlow::openData)
    fun showHome() = changeFlow { it.copy(screen = Screen.HOME) }
    fun showDeletion() = changeFlow { it.copy(screen = Screen.WITHDRAWAL) }
    fun toggleDetails() = changeFlow { it.copy(screen = if (it.screen == Screen.DETAILS) Screen.ANALYSIS else Screen.DETAILS) }
    fun back() { if (!ui.value.savingConsent) changeFlow(PreviewFlow::back) }
    fun finish() = changeFlow(PreviewFlow::finish)

    fun selectScenario(scenario: Scenario) {
        if (!ui.value.flow.hasOpenAnalysis) changeFlow { it.copy(scenario = scenario) }
    }

    fun retryDeletion() {
        if (ui.value.pendingConsent == null) changeFlow(PreviewFlow::retryDeletion)
    }

    fun tick(runId: Long, phase: Phase) {
        if (previewEnabled && ui.value.pendingConsent == null) changeFlow { PreviewFlow.tick(it, runId, phase) }
    }

    fun completeDeletion(runId: Long) {
        if (previewEnabled && ui.value.pendingConsent == null) changeFlow { PreviewFlow.completeDeletion(it, runId) }
    }

    companion object {
        fun factory(context: Context): ViewModelProvider.Factory {
            val application = context.applicationContext
            return object : ViewModelProvider.Factory {
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    require(modelClass.isAssignableFrom(SessionViewModel::class.java))
                    @Suppress("UNCHECKED_CAST")
                    return SessionViewModel(
                        DataStoreConsentStore(application),
                        { ContextCompat.checkSelfPermission(application, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED },
                        BuildConfig.DEBUG,
                    ) as T
                }
            }
        }
    }
}
