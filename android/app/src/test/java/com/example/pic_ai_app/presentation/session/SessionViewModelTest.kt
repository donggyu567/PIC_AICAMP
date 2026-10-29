package com.example.pic_ai_app.presentation.session

import com.example.pic_ai_app.data.consent.*
import com.example.pic_ai_app.presentation.preview.*
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SessionViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private var permission = false

    @Before fun setup() { Dispatchers.setMain(dispatcher) }
    @After fun teardown() { Dispatchers.resetMain() }

    private class Store(var stored: ConsentStatus = ConsentStatus.NOT_DECIDED) : ConsentStore {
        var readFails = false
        var writeFails = false
        var writeGate: CompletableDeferred<Unit>? = null
        override suspend fun read(): ConsentStatus {
            if (readFails) throw IOException("read")
            return stored
        }
        override suspend fun write(status: ConsentStatus) {
            writeGate?.await()
            if (writeFails) throw IOException("write")
            stored = status
        }
    }

    private fun session(store: Store, previewEnabled: Boolean = true) =
        SessionViewModel(store, { permission }, previewEnabled)

    private fun tick(vm: SessionViewModel) {
        val flow = vm.ui.value.flow
        vm.tick(flow.runId, flow.phase)
    }

    @Test fun restartReadsConsentButRequiresCurrentOsPermission() = runTest(dispatcher) {
        val store = Store(ConsentStatus.GRANTED)
        val vm = session(store)
        advanceUntilIdle()
        assertEquals(Screen.PERMISSION, vm.ui.value.flow.screen)
        assertTrue(vm.ui.value.flow.consented)
        permission = true
        vm.permissionResult()
        vm.start()
        repeat(4) { tick(vm) }
        assertEquals(1, vm.ui.value.flow.sampleCount)

        val restarted = session(store)
        advanceUntilIdle()
        assertEquals(Screen.HOME, restarted.ui.value.flow.screen)
        assertEquals(Phase.IDLE, restarted.ui.value.flow.phase)
        assertEquals(0, restarted.ui.value.flow.sampleCount)
    }

    @Test fun grantIsNotUsedBeforeWriteCompletesAndRetryCanRecover() = runTest(dispatcher) {
        permission = true
        val store = Store().apply { writeFails = true }
        val vm = session(store)
        advanceUntilIdle()
        vm.agree()
        vm.start()
        assertFalse(vm.ui.value.flow.hasOpenAnalysis)
        advanceUntilIdle()
        assertTrue(vm.ui.value.consentError)
        assertFalse(vm.ui.value.flow.consented)
        vm.start()
        assertFalse(vm.ui.value.flow.hasOpenAnalysis)
        store.writeFails = false
        vm.retryConsent()
        advanceUntilIdle()
        assertEquals(ConsentStatus.GRANTED, store.stored)
        assertEquals(Screen.HOME, vm.ui.value.flow.screen)
        vm.start()
        assertEquals(Phase.CONNECTING, vm.ui.value.flow.phase)
    }

    @Test fun savedConsentStillGoesThroughPermissionGate() = runTest(dispatcher) {
        val store = Store()
        val vm = session(store)
        advanceUntilIdle()
        vm.agree()
        advanceUntilIdle()
        assertEquals(ConsentStatus.GRANTED, store.stored)
        assertEquals(Screen.PERMISSION, vm.ui.value.flow.screen)
        vm.start()
        assertFalse(vm.ui.value.flow.hasOpenAnalysis)
    }

    @Test fun withdrawalBlocksAndClearsImmediatelyBeforeDurableWrite() = runTest(dispatcher) {
        permission = true
        val store = Store(ConsentStatus.GRANTED)
        val vm = session(store)
        advanceUntilIdle()
        vm.start()
        repeat(4) { tick(vm) }
        val previous = vm.ui.value.flow
        store.writeGate = CompletableDeferred()
        vm.withdraw()
        runCurrent()
        assertTrue(vm.ui.value.savingConsent)
        assertFalse(vm.ui.value.flow.consented)
        assertEquals(0, vm.ui.value.flow.sampleCount)
        assertTrue(vm.ui.value.flow.runId > previous.runId)
        vm.tick(previous.runId, previous.phase)
        vm.completeDeletion(vm.ui.value.flow.runId)
        vm.start()
        assertEquals(Phase.IDLE, vm.ui.value.flow.phase)
        assertEquals(Deletion.DELETING, vm.ui.value.flow.deletion)
        store.writeGate!!.complete(Unit)
        advanceUntilIdle()
        assertEquals(ConsentStatus.WITHDRAWN, store.stored)
        val restarted = session(store)
        advanceUntilIdle()
        assertEquals(Screen.WELCOME, restarted.ui.value.flow.screen)
        assertFalse(restarted.ui.value.flow.consented)
    }

    @Test fun failedWithdrawalStaysBlockedUntilRetryIsSaved() = runTest(dispatcher) {
        permission = true
        val store = Store(ConsentStatus.GRANTED).apply { writeFails = true }
        val vm = session(store)
        advanceUntilIdle()
        vm.start()
        vm.withdraw()
        advanceUntilIdle()
        val flow = vm.ui.value.flow
        vm.start()
        vm.completeDeletion(flow.runId)
        assertEquals(flow, vm.ui.value.flow)
        assertTrue(vm.ui.value.consentError)
        store.writeFails = false
        vm.retryConsent()
        advanceUntilIdle()
        vm.completeDeletion(flow.runId)
        assertEquals(Deletion.DONE, vm.ui.value.flow.deletion)
        assertEquals(ConsentStatus.WITHDRAWN, store.stored)
    }

    @Test fun latePermissionCallbackCannotRestoreWithdrawnConsent() = runTest(dispatcher) {
        val store = Store(ConsentStatus.GRANTED)
        val vm = session(store)
        advanceUntilIdle()
        assertTrue(vm.requestPermission())
        vm.withdraw()
        advanceUntilIdle()
        permission = true
        vm.permissionResult()
        vm.start()
        assertEquals(ConsentStatus.WITHDRAWN, vm.ui.value.consent)
        assertFalse(vm.ui.value.flow.consented)
        assertFalse(vm.ui.value.flow.hasOpenAnalysis)
        assertEquals(Screen.WITHDRAWAL, vm.ui.value.flow.screen)
    }

    @Test fun permissionLossPreservesResultAndInvalidatesOldCallbacks() = runTest(dispatcher) {
        permission = true
        val vm = session(Store(ConsentStatus.GRANTED))
        advanceUntilIdle()
        vm.start()
        repeat(4) { tick(vm) }
        val before = vm.ui.value.flow
        permission = false
        vm.refreshPermission()
        assertEquals(Phase.INCOMPLETE, vm.ui.value.flow.phase)
        assertEquals(Screen.FINAL, vm.ui.value.flow.screen)
        assertEquals(PreviewError.PERMISSION, vm.ui.value.flow.error)
        assertEquals(before.result, vm.ui.value.flow.result)
        vm.tick(before.runId, before.phase)
        permission = true
        vm.refreshPermission()
        assertEquals(Phase.INCOMPLETE, vm.ui.value.flow.phase)
        vm.start()
        assertEquals(Phase.CONNECTING, vm.ui.value.flow.phase)
        assertEquals(0, vm.ui.value.flow.sampleCount)
    }

    @Test fun permissionLossAfterStopDoesNotDropAlreadyPendingFinalResult() = runTest(dispatcher) {
        permission = true
        val vm = session(Store(ConsentStatus.GRANTED))
        advanceUntilIdle()
        vm.start()
        repeat(4) { tick(vm) }
        vm.finish()
        permission = false
        vm.refreshPermission()
        assertEquals(Phase.FINALIZING, vm.ui.value.flow.phase)
        tick(vm)
        assertEquals(Phase.COMPLETED, vm.ui.value.flow.phase)
        assertEquals(2, vm.ui.value.flow.sampleCount)
        assertFalse(vm.ui.value.flow.permissionGranted)
        vm.start()
        assertEquals(Screen.PERMISSION, vm.ui.value.flow.screen)
    }

    @Test fun duplicatePermissionRequestsAndDeniedCallbackDoNotGrantAccess() = runTest(dispatcher) {
        val vm = session(Store(ConsentStatus.GRANTED))
        advanceUntilIdle()
        assertTrue(vm.requestPermission())
        assertFalse(vm.requestPermission())
        vm.permissionResult()
        assertTrue(vm.ui.value.permissionDenied)
        assertFalse(vm.ui.value.flow.permissionGranted)
        vm.start()
        assertFalse(vm.ui.value.flow.hasOpenAnalysis)
    }

    @Test fun readFailureFailsClosedAndRetryReloads() = runTest(dispatcher) {
        permission = true
        val store = Store(ConsentStatus.GRANTED).apply { readFails = true }
        val vm = session(store)
        advanceUntilIdle()
        assertTrue(vm.ui.value.ready)
        assertTrue(vm.ui.value.consentError)
        assertFalse(vm.ui.value.flow.consented)
        vm.start()
        assertFalse(vm.ui.value.flow.hasOpenAnalysis)
        store.readFails = false
        vm.retryConsent()
        advanceUntilIdle()
        assertEquals(Screen.HOME, vm.ui.value.flow.screen)
    }

    @Test fun releaseModeCannotStartExampleAnalysis() = runTest(dispatcher) {
        permission = true
        val vm = session(Store(ConsentStatus.GRANTED), previewEnabled = false)
        advanceUntilIdle()
        vm.start()
        assertEquals(Phase.IDLE, vm.ui.value.flow.phase)
    }
}
