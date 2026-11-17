package com.example.pic_ai_app.presentation.preview

import org.junit.Assert.*
import org.junit.Test

class PreviewFlowTest {
    private fun ready(scenario: Scenario = Scenario.NORMAL) = PreviewState(
        screen = Screen.HOME, consented = true, permissionGranted = true, scenario = scenario,
    )
    private fun next(state: PreviewState) = PreviewFlow.tick(state, state.runId, state.phase)
    private fun advance(initial: PreviewState, count: Int): PreviewState {
        var state = initial
        repeat(16) {
            if (state.sampleCount < count && PreviewFlow.delayMillis(state) != null) state = next(state)
        }
        assertEquals(count, state.sampleCount)
        return state
    }

    @Test fun startRequiresConsentAndPermission() {
        assertEquals(Screen.CONSENT, PreviewFlow.start(PreviewState()).screen)
        val agreed = PreviewFlow.agree(PreviewState())
        assertEquals(Screen.PERMISSION, PreviewFlow.start(agreed).screen)
        assertEquals(Phase.CONNECTING, PreviewFlow.start(PreviewFlow.allowPermission(agreed)).phase)
    }

    @Test fun repeatedStartDoesNotCreateAnotherAnalysis() {
        val active = PreviewFlow.start(ready())
        assertEquals(active, PreviewFlow.start(active))
        assertNull(active.result)
    }

    @Test fun dataAndDetailsReceiveResultsWithoutRestarting() {
        var state = advance(PreviewFlow.start(ready()), 1)
        val runId = state.runId
        state = PreviewFlow.openData(state.copy(screen = Screen.DETAILS))
        state = advance(state, 2)
        assertEquals(Screen.DATA, state.screen)
        assertEquals(runId, state.runId)
        state = PreviewFlow.back(state)
        assertEquals(Screen.DETAILS, state.screen)
        assertEquals(72, state.result?.score)
        assertEquals(Screen.ANALYSIS, PreviewFlow.back(state).screen)
    }

    @Test fun normalStopWaitsForTheFinalResponseAndNewAnalysisRejectsOldCallbacks() {
        val active = advance(PreviewFlow.start(ready()), 2)
        val finishing = PreviewFlow.finish(active)
        assertEquals(Phase.FINALIZING, finishing.phase)
        assertEquals(72, finishing.result?.score)
        val completed = next(finishing)
        assertEquals(Screen.FINAL, completed.screen)
        assertEquals(Phase.COMPLETED, completed.phase)
        assertEquals(73, completed.result?.score)
        val restarted = PreviewFlow.start(completed)
        assertNull(restarted.result)
        assertTrue(restarted.runId > completed.runId)
        assertEquals(restarted, PreviewFlow.tick(restarted, active.runId, Phase.ANALYZING))
    }

    @Test fun processingFailuresPreserveTheLastSuccessfulScore() {
        listOf(Scenario.STT_ERROR, Scenario.MASKING_ERROR, Scenario.ANALYSIS_ERROR).forEach { scenario ->
            var state = PreviewFlow.start(ready(scenario))
            repeat(16) { if (PreviewFlow.delayMillis(state) != null) state = next(state) }
            assertEquals(Phase.ERROR, state.phase)
            assertEquals(47, state.result?.score)
            assertFalse(state.busy)
            val final = next(PreviewFlow.finish(state))
            assertEquals(Phase.INCOMPLETE, final.phase)
            assertEquals(47, final.result?.score)
            assertEquals(1, final.sampleCount)
        }
    }

    @Test fun connectionFailureHasNoScoreOrLoadingSpinner() {
        val failed = next(PreviewFlow.start(ready(Scenario.CONNECTION_ERROR)))
        assertEquals(PreviewError.CONNECTION, failed.error)
        assertNull(failed.result)
        assertFalse(failed.busy)
    }

    @Test fun incompleteFinalizationDoesNotApplyUnfinishedResult() {
        val active = advance(PreviewFlow.start(ready(Scenario.FINISH_ERROR)), 2)
        val final = next(PreviewFlow.finish(active))
        assertEquals(Phase.INCOMPLETE, final.phase)
        assertEquals(2, final.sampleCount)
        assertEquals(72, final.result?.score)
    }

    @Test fun withdrawalDiscardsLateResponsesAndWaitsForConfirmedDeletion() {
        val active = advance(PreviewFlow.start(ready(Scenario.DELETE_ERROR)), 1)
        var state = PreviewFlow.withdraw(active)
        assertFalse(state.consented)
        assertNull(state.result)
        assertFalse(state.hasOpenAnalysis)
        assertEquals(state, PreviewFlow.tick(state, active.runId, active.phase))
        state = PreviewFlow.completeDeletion(state, state.runId)
        assertEquals(Deletion.PENDING, state.deletion)
        assertEquals(state, PreviewFlow.start(state))
        state = PreviewFlow.retryDeletion(state)
        state = PreviewFlow.completeDeletion(state, state.runId)
        assertEquals(Deletion.DONE, state.deletion)
        assertEquals(Screen.CONSENT, PreviewFlow.start(state).screen)
    }

    @Test fun silenceAndImmediateStopDoNotMeanLowRisk() {
        var silent = PreviewFlow.start(ready(Scenario.EMPTY))
        silent = next(next(silent))
        assertEquals(Phase.LISTENING, silent.phase)
        assertNull(PreviewFlow.delayMillis(silent))
        assertNull(next(PreviewFlow.finish(silent)).result)
        assertNull(next(PreviewFlow.finish(PreviewFlow.start(ready()))).result)
    }
}
