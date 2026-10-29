package com.example.pic_ai_app.presentation.preview

enum class Screen { WELCOME, CONSENT, PERMISSION, HOME, ANALYSIS, DETAILS, FINAL, DATA, WITHDRAWAL }
enum class Phase { IDLE, CONNECTING, RECOGNIZING, MASKING, ANALYZING, LISTENING, FINALIZING, COMPLETED, INCOMPLETE, ERROR }
enum class Scenario { NORMAL, EMPTY, CONNECTION_ERROR, STT_ERROR, MASKING_ERROR, ANALYSIS_ERROR, FINISH_ERROR, DELETE_ERROR }
enum class PreviewError { CONNECTION, STT, MASKING, ANALYSIS, PERMISSION }
enum class Deletion { NONE, DELETING, PENDING, DONE }

data class PreviewResult(
    val score: Int,
    val level: String,
    val warning: String,
    val reason: String,
    val maskedText: String,
)

// Display fixtures only: these numbers do not implement or evaluate the risk model.
val previewResults = listOf(
    PreviewResult(47, "주의", "기관 사칭 의심 발화 감지", "금융기관 직원을 사칭하는 표현이 포함되어 있습니다.",
        "안녕하세요, 금융보안팀 [PERSON]입니다. 고객님 계좌 [ACCOUNT_NUMBER] 확인이 필요합니다."),
    PreviewResult(72, "위험", "계좌 이체 유도 표현 감지", "계좌 이체를 직접 요구하는 문구가 포함되어 있습니다.",
        "계좌 [ACCOUNT_NUMBER]로 지금 바로 이체해 주세요."),
    PreviewResult(73, "위험", "개인정보 요구 발화 감지", "인증번호를 요구하는 문구가 포함되어 있습니다.",
        "[PHONE_NUMBER]로 받은 인증번호 [OTP]를 알려 주세요."),
)

data class PreviewState(
    val screen: Screen = Screen.WELCOME,
    val returnScreen: Screen = Screen.HOME,
    val phase: Phase = Phase.IDLE,
    val scenario: Scenario = Scenario.NORMAL,
    val consented: Boolean = false,
    val permissionGranted: Boolean = false,
    val sampleCount: Int = 0,
    val runId: Long = 0,
    val error: PreviewError? = null,
    val pendingFinalSample: Boolean = false,
    val deletion: Deletion = Deletion.NONE,
    val deletionAttempts: Int = 0,
) {
    val result: PreviewResult? get() = previewResults.getOrNull(sampleCount - 1)
    val samples: List<PreviewResult> get() = previewResults.take(sampleCount)
    val hasOpenAnalysis: Boolean get() = phase !in listOf(Phase.IDLE, Phase.COMPLETED, Phase.INCOMPLETE)
    val busy: Boolean get() = phase in listOf(Phase.CONNECTING, Phase.RECOGNIZING, Phase.MASKING, Phase.ANALYZING, Phase.FINALIZING)
}

object PreviewFlow {
    fun agree(state: PreviewState) = state.copy(
        consented = true,
        screen = if (state.permissionGranted) Screen.HOME else Screen.PERMISSION,
    )

    fun allowPermission(state: PreviewState) = state.copy(permissionGranted = true, screen = Screen.HOME)

    fun start(state: PreviewState): PreviewState {
        if (state.hasOpenAnalysis || state.deletion in listOf(Deletion.DELETING, Deletion.PENDING)) return state
        if (!state.consented) return state.copy(screen = Screen.CONSENT)
        if (!state.permissionGranted) return state.copy(screen = Screen.PERMISSION)
        return state.copy(
            screen = Screen.ANALYSIS, phase = Phase.CONNECTING,
            sampleCount = 0, runId = state.runId + 1, error = null,
            pendingFinalSample = false, deletion = Deletion.NONE,
        )
    }

    fun openData(state: PreviewState) = state.copy(returnScreen = state.screen, screen = Screen.DATA)

    fun back(state: PreviewState) = state.copy(screen = when (state.screen) {
        Screen.DATA -> state.returnScreen
        Screen.DETAILS -> Screen.ANALYSIS
        Screen.FINAL -> Screen.HOME
        Screen.CONSENT -> Screen.WELCOME
        Screen.PERMISSION -> Screen.CONSENT
        else -> state.screen
    })

    fun finish(state: PreviewState): PreviewState {
        if (!state.hasOpenAnalysis || state.phase == Phase.FINALIZING) return state
        return state.copy(
            screen = Screen.ANALYSIS,
            phase = Phase.FINALIZING,
            pendingFinalSample = state.phase != Phase.CONNECTING && state.scenario != Scenario.EMPTY && state.error == null,
        )
    }

    fun withdraw(state: PreviewState) = state.copy(
        screen = Screen.WITHDRAWAL, returnScreen = Screen.WITHDRAWAL,
        consented = false, phase = Phase.IDLE, runId = state.runId + 1,
        sampleCount = 0, error = null, pendingFinalSample = false,
        deletion = Deletion.DELETING, deletionAttempts = 1,
    )

    fun retryDeletion(state: PreviewState) = if (state.deletion == Deletion.PENDING) {
        state.copy(deletion = Deletion.DELETING, deletionAttempts = state.deletionAttempts + 1)
    } else state

    fun completeDeletion(state: PreviewState, expectedRunId: Long): PreviewState {
        if (state.runId != expectedRunId || state.deletion != Deletion.DELETING) return state
        val pending = state.scenario == Scenario.DELETE_ERROR && state.deletionAttempts == 1
        return state.copy(deletion = if (pending) Deletion.PENDING else Deletion.DONE)
    }

    fun delayMillis(state: PreviewState): Long? = when (state.phase) {
        Phase.CONNECTING -> 1_100
        Phase.RECOGNIZING -> 1_100
        Phase.MASKING -> 700
        Phase.ANALYZING -> 1_200
        Phase.FINALIZING -> 1_800
        Phase.LISTENING -> if (state.scenario != Scenario.EMPTY && state.sampleCount < 2) 2_000 else null
        else -> null
    }

    // A stale delayed callback must not change a new or withdrawn analysis.
    fun tick(state: PreviewState, expectedRunId: Long, expectedPhase: Phase): PreviewState {
        if (state.runId != expectedRunId || state.phase != expectedPhase || !state.consented) return state
        fun failed(error: PreviewError) = state.copy(phase = Phase.ERROR, error = error)
        return when (state.phase) {
            Phase.CONNECTING -> if (state.scenario == Scenario.CONNECTION_ERROR) failed(PreviewError.CONNECTION)
                else state.copy(phase = Phase.RECOGNIZING)
            Phase.RECOGNIZING -> when {
                state.scenario == Scenario.EMPTY -> state.copy(phase = Phase.LISTENING)
                state.scenario == Scenario.STT_ERROR && state.sampleCount > 0 -> failed(PreviewError.STT)
                else -> state.copy(phase = Phase.MASKING)
            }
            Phase.MASKING -> if (state.scenario == Scenario.MASKING_ERROR && state.sampleCount > 0)
                failed(PreviewError.MASKING) else state.copy(phase = Phase.ANALYZING)
            Phase.ANALYZING -> if (state.scenario == Scenario.ANALYSIS_ERROR && state.sampleCount > 0)
                failed(PreviewError.ANALYSIS) else state.copy(phase = Phase.LISTENING, sampleCount = (state.sampleCount + 1).coerceAtMost(previewResults.size))
            Phase.LISTENING -> state.copy(phase = Phase.RECOGNIZING)
            Phase.FINALIZING -> {
                val incomplete = state.scenario == Scenario.FINISH_ERROR || state.error != null
                state.copy(
                    screen = Screen.FINAL,
                    phase = if (incomplete) Phase.INCOMPLETE else Phase.COMPLETED,
                    sampleCount = if (!incomplete && state.pendingFinalSample) (state.sampleCount + 1).coerceAtMost(previewResults.size) else state.sampleCount,
                    pendingFinalSample = false,
                )
            }
            else -> state
        }
    }
}
