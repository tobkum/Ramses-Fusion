# -*- coding: utf-8 -*-
"""
Ramses Ecosystem Runtime Patches
================================

Runtime fixes for the vendored ramses-py SDK (lib/ramses/). The SDK files
themselves are deliberately never edited so they stay cleanly replaceable
from upstream — anything the SDK gets wrong is corrected here at runtime.

Patches applied by apply() (this module):
 - RamMetaDataManager.getMetaData: no longer prunes entries for files that
   are "missing" — pruning raced the (potentially threaded) version-copy
   and destroyed metadata for files still being written.
 - RamMetaDataManager.setFileMetaData: refuses to rewrite the sidecar from
   an empty merge base when the sidecar file exists non-empty (a transient
   corrupt read would otherwise wipe the whole folder's metadata on the
   very next write).
 - RamMetaDataManager.getValue/setValue: bail on a falsy filePath instead
   of crashing in os.path functions (copyToVersion & co. can return None).
 - RamDaemonInterface.online: returns False on any error instead of
   leaking KeyError/socket exceptions when the daemon dies mid-reply.

Applied at import time (this module):
 - DisableMakedirs / guarded os.makedirs (see below).

NOTE: several older patches (synchronous RamFileManager.copy, robust
version file resolution, RamHost.publish state propagation) historically
live in fusion_host.py's monkey-patching section, not here.

Usage:
    import ramses_patches
    ramses_patches.apply()
"""

import json
import os
import sys
import threading
import time
from ramses.constants import LogLevel
from ramses.logger import log


def _patch_metadata_manager():
    """Fixes data-loss bugs in the vendored RamMetaDataManager.

    The sidecar (_ramses_data.json) holds the metadata of EVERY file in a
    folder, and all setters are read-modify-write through getMetaData().
    Two vendored behaviors could destroy it:

    1. getMetaData() pruned entries whose file doesn't exist ON READ.
       Version backups may be copied on a background thread; the metadata
       write for the new file fires immediately, sees the in-flight file
       as "missing", prunes its (or a sibling's) entry, and the prune is
       persisted by the write. Stale entries are harmless bloat; the prune
       race is not — so the patched getMetaData never prunes.

    2. getMetaData() returns {} when the sidecar can't be parsed after
       retries (e.g. the Ramses client is writing it non-atomically at
       that moment). setFileMetaData() then merged one entry into that
       empty dict and rewrote the file — wiping every other file's
       metadata in the folder. The patched setFileMetaData refuses the
       write when the merge base is empty but the sidecar file exists
       non-empty: losing one metadata update is recoverable, losing the
       folder's whole history is not.
    """
    from ramses.metadata_manager import RamMetaDataManager

    def _patched_getMetaData(folderPath):
        """Reads the sidecar without pruning entries for missing files."""
        file = RamMetaDataManager.getMetaDataFile(folderPath)
        if not os.path.exists(file):
            return {}
        data = {}
        for _attempt in range(3):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                break
            except (json.JSONDecodeError, IOError):
                if _attempt < 2:
                    time.sleep(0.01 * (2 ** _attempt))
                    continue
                return {}
        return data

    def _patched_setFileMetaData(filePath, fileData):
        """Sets one file's metadata; refuses to clobber an unreadable sidecar."""
        if not filePath:
            log("Metadata write skipped: no file path.", LogLevel.Debug)
            return
        folderPath = os.path.dirname(filePath)
        fileName = os.path.basename(filePath)
        data = RamMetaDataManager.getMetaData(folderPath)
        metaFile = RamMetaDataManager.getMetaDataFile(folderPath)
        if not data and os.path.isfile(metaFile) and os.path.getsize(metaFile) > 2:
            log(
                "Metadata sidecar could not be read (locked or corrupt): "
                "skipping this metadata update instead of overwriting the "
                "folder's existing metadata. (" + metaFile + ")",
                LogLevel.Critical,
            )
            return
        data[fileName] = fileData
        RamMetaDataManager.setMetaData(folderPath, data)

    _original_getValue = RamMetaDataManager.getValue
    _original_setValue = RamMetaDataManager.setValue

    def _patched_getValue(filePath, key):
        # copyToVersion()/restoreVersionFile() can return None; the vendored
        # getValue/setValue crash in os.path on it (TypeError) deep inside
        # the save chain. Degrade to a no-op instead.
        if not filePath:
            return None
        return _original_getValue(filePath, key)

    def _patched_setValue(filePath, key, value):
        if not filePath:
            log("Metadata write skipped: no file path.", LogLevel.Debug)
            return
        return _original_setValue(filePath, key, value)

    RamMetaDataManager.getMetaData = staticmethod(_patched_getMetaData)
    RamMetaDataManager.setFileMetaData = staticmethod(_patched_setFileMetaData)
    RamMetaDataManager.getValue = staticmethod(_patched_getValue)
    RamMetaDataManager.setValue = staticmethod(_patched_setValue)


def _patch_daemon_interface():
    """Makes RamDaemonInterface.online() never raise.

    The vendored __testConnection subscripts the ping reply ('content',
    'ramses') without guards, and the socket send/recv paths aren't fully
    wrapped — a daemon that dies mid-reply made online() raise
    KeyError/ConnectionResetError instead of returning False, crashing
    callers that just wanted a connectivity check.
    """
    from ramses.daemon_interface import RamDaemonInterface

    _original_online = RamDaemonInterface.online

    def _patched_online(self):
        try:
            return bool(_original_online(self))
        except Exception as e:
            log("Daemon connectivity check failed: " + str(e), LogLevel.Debug)
            return False

    RamDaemonInterface.online = _patched_online


def apply():
    """Applies all available runtime patches."""
    # NOTE: No fusion_config patch needed — fusion_config.py already contains the
    # correct robust parser. The old _patch_fusion_config was replacing it with an
    # identical copy (dead maintenance weight) and has been removed.
    _patch_metadata_manager()
    _patch_daemon_interface()
    log("Ramses runtime patches applied.", LogLevel.Debug)


# ---------------------------------------------------------------------------
# os.makedirs suppression (DisableMakedirs)
# ---------------------------------------------------------------------------
# Several Ramses-Py SDK getters (RamItem.publishFolderPath, stepFilePath,
# stepFolderPath, FusionHost.resolvePreviewPath/resolveFinalPath, ...) create
# directories as a side effect of what's meant to be a read-only path lookup.
# Any UI code that just browses/lists (polling, populating a combo box or
# tree) can trigger this and litter the project with folders that shouldn't
# exist yet. Installed here (rather than in the entry script) so every
# module under lib/ - not just Ramses-Fusion.py itself - can wrap read-only
# lookups in `with DisableMakedirs():`.
_makedirs_suppressed = threading.local()
_real_makedirs = os.makedirs


def _guarded_makedirs(*args, **kwargs):
    if getattr(_makedirs_suppressed, "active", False):
        return None
    return _real_makedirs(*args, **kwargs)


os.makedirs = _guarded_makedirs


class DisableMakedirs:
    """Context manager to temporarily disable os.makedirs for the current thread.
    Prevents Ramses-Py from aggressively creating directories on read.

    Implemented as a thread-local flag flipped on a single, permanently-installed
    os.makedirs wrapper (rather than swapping the os.makedirs function object on
    each __enter__/__exit__), so concurrent DisableMakedirs blocks on different
    threads - and nested blocks on the same thread - can't race or clobber each
    other's suppression state.
    """
    def __enter__(self):
        self._prev = getattr(_makedirs_suppressed, "active", False)
        _makedirs_suppressed.active = True
        return self

    def __exit__(self, *args):
        _makedirs_suppressed.active = self._prev
