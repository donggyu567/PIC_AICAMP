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
import com.example.pic_ai_app.data.stt.*
import com.example.pic_ai_app.data.security.DeviceTokenStore
import com.example.pic_ai_app.domain.model.UtteranceTranscript
import com.example.pic_ai_app.masking.MaskingPipeline
import com.example.pic_ai_app.masking.TranscriptMasker
import com.example.pic_ai_app.masking.ner.OnDeviceNerCandidateDetector
import com.example.pic_ai_app.masking.regex.DefaultRegexCandidateDetector
import com.example.pic_ai_app.masking.renderer.DefaultMaskedTextRenderer
import com.example.pic_ai_app.masking.resolver.DefaultCandidateConflictResolver
import com.example.pic_ai_app.masking.rule.DefaultNumberMaskingRuleEngine
import com.example.pic_ai_app.presentation.preview.*
import java.io.IOException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException

data class SessionUiState(
    val flow: PreviewState = PreviewState(),
    val ready: Boolean = false,
    val consent: ConsentStatus = ConsentStatus.NOT_DECIDED,
    val savingConsent: Boolean = false,
    val pendingConsent: ConsentStatus? = null,
    val consentError: Boolean = false,
    val showOnboardingComplete: Boolean = false,
    val permissionRequestPending: Boolean = false,
    val permissionDenied: Boolean = false,
    val declined: Boolean = false,
    val stt: SttState = SttState(),
    val serverUrl: String = "wss://picaicamp.duckdns.org/api/v1/stt",
    val tokenMessage: String? = null,
)

class SessionViewModel(
    private val consentStore: ConsentStore,
    private val hasMicrophonePermission: () -> Boolean,
    private val previewEnabled: Boolean,
    private val liveEnabled: Boolean = false,
    private val masker: TranscriptMasker? = null,
    private val closeMasker: () -> Unit = {},
    private val deleteFromServer: (suspend (String, String) -> Unit)? = null,
    private val tokenStore: DeviceTokenStore? = null,
) : ViewModel() {
    private val mutableUi = MutableStateFlow(SessionUiState())
    val ui = mutableUi.asStateFlow()
    private var registrationJob: Job? = null
    val deletionRetryAvailable get() = true
    private val riskClient = RiskAnalysisClient { url -> if (liveEnabled) checkNotNull(tokenStore).forServer(url) else null }
    private val sttSession by lazy {
        SttSession(viewModelScope, hasMicrophonePermission, mask = { text, conversation, utterance ->
            val activeMasker = checkNotNull(masker)
            activeMasker.mask(UtteranceTranscript.unmasked(conversation, utterance, text))
        }, analyze = { url, utterance ->
            consentStore.register(DeletionTarget(url, utterance.conversationId))
            riskClient.analyze(url, utterance)
        }, finalize = riskClient::finish, recover = riskClient::recover,
            tokenForServer = { url -> if (liveEnabled) checkNotNull(tokenStore).forServer(url) else null }) { state -> mutableUi.update { it.copy(stt = state) } }
    }

    init { loadConsent() }

    private fun loadConsent() {
        mutableUi.update { it.copy(ready = false, consentError = false) }
        viewModelScope.launch {
            try {
                val consent = consentStore.read()
                val pending = liveEnabled && consent == ConsentStatus.WITHDRAWN && consentStore.deletionTargets().isNotEmpty()
                mutableUi.value = SessionUiState(
                    flow = SessionAccess.initial(consent, hasMicrophonePermission()).let { flow ->
                        if (liveEnabled && consent == ConsentStatus.WITHDRAWN)
                            flow.copy(deletion = if (pending) Deletion.PENDING else Deletion.DONE) else flow
                    },
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
        if (!granted && liveEnabled && ui.value.flow.hasOpenAnalysis) sttSession.abort()
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
        if (!ui.value.ready || ui.value.savingConsent ||
            ui.value.flow.deletion in listOf(Deletion.DELETING, Deletion.PENDING)) return
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
        registrationJob?.cancel()
        if (liveEnabled) sttSession.abort()
        // Block callbacks immediately, before the durable write finishes.
        mutableUi.update { it.copy(consent = ConsentStatus.WITHDRAWN, flow = PreviewFlow.withdraw(it.flow).let { flow ->
            if (liveEnabled) flow.copy(deletion = Deletion.DELETING) else flow
        }) }
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
                        showOnboardingComplete = choice == ConsentStatus.GRANTED,
                        pendingConsent = null, consentError = false,
                        declined = if (choice == ConsentStatus.GRANTED) false else current.declined,
                    )
                }
                if (liveEnabled && choice == ConsentStatus.WITHDRAWN) deleteTrackedSessions()
            } catch (_: IOException) {
                mutableUi.update { it.copy(savingConsent = false, consentError = true) }
            }
        }
    }

    private suspend fun deleteTrackedSessions() {
        try {
            for (target in consentStore.deletionTargets()) {
                (deleteFromServer ?: riskClient::withdraw)(target.serverUrl, target.conversationId)
                consentStore.removeTarget(target)
            }
            changeFlow { it.copy(deletion = Deletion.DONE) }
        } catch (cancelled: kotlinx.coroutines.CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            changeFlow { it.copy(deletion = Deletion.PENDING) }
        }
    }

    fun dismissOnboardingComplete() {
        mutableUi.update { it.copy(showOnboardingComplete = false) }
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
        if ((!previewEnabled && !liveEnabled) || !current.ready || current.savingConsent || current.pendingConsent != null) return
        val next = PreviewFlow.start(current.flow)
        changeFlow { next }
        if (liveEnabled && next.phase == Phase.CONNECTING && !current.flow.hasOpenAnalysis) {
            mutableUi.update { it.copy(stt = SttState(phase = SttPhase.CONNECTING)) }
            registrationJob = viewModelScope.launch {
                try {
                    val store = checkNotNull(tokenStore)
                    val existing = try { store.forServer(current.serverUrl) } catch (_: IOException) { null }
                    if (existing == null) {
                        if (store.hasSavedToken() && consentStore.deletionTargets().isNotEmpty())
                            throw IOException("기존 서버 기록을 먼저 삭제해야 합니다.")
                        val token = riskClient.registerDevice(current.serverUrl)
                        if (ui.value.consent != ConsentStatus.GRANTED || ui.value.flow.runId != next.runId) return@launch
                        store.save(current.serverUrl, token)
                    }
                    if (ui.value.consent == ConsentStatus.GRANTED && ui.value.flow.runId == next.runId)
                        sttSession.start(current.serverUrl)
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    if (ui.value.flow.runId == next.runId && ui.value.consent == ConsentStatus.GRANTED)
                        mutableUi.update { it.copy(stt = SttState(phase = SttPhase.ERROR, error = "기기 등록에 실패했습니다. 연결 상태와 기존 기록을 확인해 주세요.")) }
                }
            }
        }
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
    fun finish() {
        if (liveEnabled) {
            if (registrationJob?.isActive == true) {
                registrationJob?.cancel()
                mutableUi.update { it.copy(stt = SttState(phase = SttPhase.STOPPED)) }
                return
            }
            sttSession.stop()
        } else {
            changeFlow(PreviewFlow::finish)
        }
    }

    fun updateServerUrl(value: String) {
        if (!ui.value.flow.hasOpenAnalysis) mutableUi.update { it.copy(serverUrl = value) }
    }

    fun saveDeviceToken(token: String) {
        if (!liveEnabled || ui.value.flow.hasOpenAnalysis) return
        viewModelScope.launch {
            try {
                if (consentStore.deletionTargets().isNotEmpty() && checkNotNull(tokenStore).hasSavedToken()) {
                    // 인증 정보 교체로 기존 삭제 대상에 접근하지 못하는 상황을 막는다.
                    try {
                        val existing = checkNotNull(tokenStore).forServer(ui.value.serverUrl)
                        if (existing != token) throw IOException("저장된 통화가 있어 인증 정보를 바꿀 수 없습니다.")
                    } catch (error: IOException) { throw error }
                }
                checkNotNull(tokenStore).save(ui.value.serverUrl, token.trim())
                mutableUi.update { it.copy(tokenMessage = "기기 인증 정보를 저장했습니다.") }
            } catch (_: Exception) {
                mutableUi.update { it.copy(tokenMessage = "인증 정보를 저장하지 못했습니다. 서버 주소와 기존 통화 기록을 확인해 주세요.") }
            }
        }
    }

    fun retryAnalysis() { if (liveEnabled) sttSession.retryAnalysis() }

    fun retryFinish() { if (liveEnabled) sttSession.retryFinish() }

    fun leaveStt() {
        registrationJob?.cancel()
        if (liveEnabled) sttSession.abort()
        changeFlow { it.copy(screen = Screen.HOME, phase = Phase.IDLE, error = null, sampleCount = 0) }
    }

    fun selectScenario(scenario: Scenario) {
        if (!ui.value.flow.hasOpenAnalysis) changeFlow { it.copy(scenario = scenario) }
    }

    fun retryDeletion() {
        if (ui.value.pendingConsent != null || ui.value.flow.deletion != Deletion.PENDING) return
        if (!liveEnabled) changeFlow(PreviewFlow::retryDeletion)
        else {
            changeFlow { it.copy(deletion = Deletion.DELETING) }
            viewModelScope.launch { deleteTrackedSessions() }
        }
    }

    fun tick(runId: Long, phase: Phase) {
        if (previewEnabled && !liveEnabled && ui.value.pendingConsent == null) changeFlow { PreviewFlow.tick(it, runId, phase) }
    }

    fun completeDeletion(runId: Long) {
        if (previewEnabled && !liveEnabled && ui.value.pendingConsent == null) changeFlow { PreviewFlow.completeDeletion(it, runId) }
    }

    override fun onCleared() {
        if (liveEnabled) sttSession.abort()
        closeMasker()
        super.onCleared()
    }

    companion object {
        fun factory(context: Context): ViewModelProvider.Factory {
            val application = context.applicationContext
            return object : ViewModelProvider.Factory {
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    require(modelClass.isAssignableFrom(SessionViewModel::class.java))
                    @Suppress("UNCHECKED_CAST")
                    val ner = OnDeviceNerCandidateDetector(application.assets)
                    val masker = TranscriptMasker(MaskingPipeline(
                        ner, DefaultRegexCandidateDetector(), DefaultNumberMaskingRuleEngine(),
                        DefaultCandidateConflictResolver(), DefaultMaskedTextRenderer(),
                    ))
                    return SessionViewModel(
                        DataStoreConsentStore(application),
                        { ContextCompat.checkSelfPermission(application, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED },
                        BuildConfig.DEBUG,
                        liveEnabled = true,
                        masker = masker,
                        closeMasker = ner::close,
                        tokenStore = DeviceTokenStore(application),
                    ) as T
                }
            }
        }
    }
}
