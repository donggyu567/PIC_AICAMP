package com.example.pic_ai_app.presentation.session

import com.example.pic_ai_app.data.consent.ConsentStatus
import com.example.pic_ai_app.presentation.preview.*

object SessionAccess {
    fun initial(consent: ConsentStatus, permission: Boolean): PreviewState = PreviewState(
        consented = consent == ConsentStatus.GRANTED,
        permissionGranted = permission,
        screen = when {
            consent != ConsentStatus.GRANTED -> Screen.WELCOME
            !permission -> Screen.PERMISSION
            else -> Screen.HOME
        },
    )

    fun permissionChanged(state: PreviewState, granted: Boolean): PreviewState {
        // Finalization already stopped input; an in-flight result can still finish.
        if (!granted && state.hasOpenAnalysis && state.phase != Phase.FINALIZING) {
            return state.copy(
                permissionGranted = false, phase = Phase.INCOMPLETE, screen = Screen.FINAL,
                error = PreviewError.PERMISSION, runId = state.runId + 1, pendingFinalSample = false,
            )
        }
        return state.copy(permissionGranted = granted)
    }
}
