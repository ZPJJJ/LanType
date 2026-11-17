package com.kingzcheung.xime.clipboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Real copy identities and delayed-delivery ordering; no clipboard contents are kept by the guard. */
class ToolCabinClipPrivacyTest {
    private val privacy = ToolCabinClipPrivacy()
    private var currentCopy: Long? = 100L

    private fun open() = privacy.setOpen(true) { currentCopy }
    private fun close() = privacy.setOpen(false) { currentCopy }
    private fun classification(timestamp: Long, manualOrSearch: Boolean = false, keepSensitive: Boolean = false) =
        ClipboardManager.clipPrivacy(markedSensitive = false, passwordField = false,
            incognito = manualOrSearch || privacy.isPrivate(timestamp), keepSensitive = keepSensitive)

    @Test fun copiesDuringCabinStayPrivateEvenWithSensitiveHistoryEnabled() {
        open()
        assertEquals(ClipPrivacy.PRIVATE, classification(200L, keepSensitive = true))
    }

    @Test fun firstListenerDeliveryAfterCloseStillRejectsTheCabinCopy() {
        open()
        currentCopy = 200L // The system copy exists, but its listener has not run.
        close()
        assertEquals(ClipPrivacy.PRIVATE, classification(200L))
        assertEquals(ClipPrivacy.NORMAL, classification(201L))
    }

    @Test fun nullPayloadRetryAfterCloseAndLaterBoardReadStayPrivate() {
        open()
        currentCopy = 200L
        // The initial getPrimaryClip returned null, scheduling the real 100 ms retry.
        // Closing captures only the available description, before that retry can run.
        close()
        assertEquals(ClipPrivacy.PRIVATE, classification(200L))
        assertEquals(ClipPrivacy.PRIVATE, classification(200L))
        assertEquals(ClipPrivacy.PRIVATE, classification(200L))
    }

    @Test fun oldRetryReadingANewerOrdinaryCopyDoesNotQuarantineThatNewCopy() {
        open()
        currentCopy = 200L
        close()
        // A new copy replaced the draft before the old callback/retry reads primaryClip.
        assertEquals(ClipPrivacy.NORMAL, classification(300L))
        assertEquals(ClipPrivacy.NORMAL, classification(300L))
    }

    @Test fun deniedDescriptionQuarantinesOnceButKeepsThatCopyPrivateOnEveryReread() {
        open()
        privacy.setOpen(false) { throw SecurityException("description unavailable") }
        assertEquals(ClipPrivacy.PRIVATE, classification(200L))
        assertEquals(ClipPrivacy.PRIVATE, classification(200L))
        assertEquals(ClipPrivacy.NORMAL, classification(300L))
    }

    @Test fun missingDescriptionUsesTheSameConservativeFallback() {
        open()
        currentCopy = null
        close()
        assertEquals(ClipPrivacy.PRIVATE, classification(200L))
        assertEquals(ClipPrivacy.PRIVATE, classification(200L))
        assertEquals(ClipPrivacy.NORMAL, classification(201L))
    }

    @Test fun repeatedOpenAndCloseAreIdempotentAndDoNotCaptureLaterOrdinaryCopies() {
        var metadataReads = 0
        fun transition(value: Boolean) = privacy.setOpen(value) { metadataReads++; currentCopy }
        transition(true)
        transition(true)
        currentCopy = 200L
        transition(false)
        currentCopy = 300L
        transition(false)
        assertEquals(1, metadataReads)
        assertTrue(privacy.isPrivate(200L))
        assertFalse(privacy.isPrivate(300L))
    }

    @Test fun timestampIdentityDoesNotAssumeAMonotonicSystemClock() {
        open()
        currentCopy = 2_000L
        close()
        assertTrue(privacy.isPrivate(2_000L))
        assertFalse(privacy.isPrivate(1_000L)) // A distinct ordinary copy after a clock adjustment.
        assertFalse(privacy.isPrivate(3_000L))
        assertTrue(privacy.isPrivate(2_000L)) // Same-millisecond identities stay conservatively private.
    }

    @Test fun currentCopyMarkerSurvivesBoundedPrivateMemoryEviction() {
        open()
        currentCopy = 200L
        close()
        val memory = PrivateClipMemory(capacity = 2)
        val key = PrivateClipMemory.key(200L, "temporary draft")
        memory.remember(key)
        memory.remember(PrivateClipMemory.key(300L, "another private copy"))
        memory.remember(PrivateClipMemory.key(400L, "another private copy"))
        assertFalse(key in memory)
        assertTrue(privacy.isPrivate(200L))
        // readClipboard's existing privateClips path can remember the full identity again.
        memory.remember(key)
        assertTrue(key in memory)
    }

    @Test fun closingWithoutANewCopyConservativelyProtectsTheExistingClipboard() {
        open()
        close()
        assertTrue(privacy.isPrivate(100L))
        assertFalse(privacy.isPrivate(101L))
    }

    @Test fun manualAndSearchPrivacyStillWinOutsideTheCabin() {
        assertEquals(ClipPrivacy.NORMAL, classification(100L))
        assertEquals(ClipPrivacy.PRIVATE, classification(100L, manualOrSearch = true))
        open()
        currentCopy = 200L
        close()
        assertEquals(ClipPrivacy.PRIVATE, classification(300L, manualOrSearch = true))
        assertEquals(ClipPrivacy.NORMAL, classification(300L))
    }
}
