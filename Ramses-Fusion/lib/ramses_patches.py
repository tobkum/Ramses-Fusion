# -*- coding: utf-8 -*-
"""
Ramses Ecosystem Runtime Patches
================================

Runtime fixes for the vendored ramses-py SDK (lib/ramses/). The SDK files
themselves are deliberately never edited so they stay cleanly replaceable
from upstream — anything the SDK gets wrong is corrected here at runtime.

Applied at import time (this module):
 - DisableMakedirs / guarded os.makedirs (see below).

Applied by apply():
 - RamDaemonInterface.online: returns False on any error instead of leaking
   KeyError/socket exceptions when the daemon dies mid-reply.

Removed, because they are fixed in the vendored SDK as of Ramses-Py 30582ce
(PRs #12/#13):
 - RamMetaDataManager.getMetaData no longer prunes entries for missing files
 - RamMetaDataManager.setFileMetaData refuses to rewrite from an unreadable
   sidecar
 - RamMetaDataManager.getValue/setValue guard a falsy filePath

The daemon patch is NOT redundant and stays. Upstream's fix is narrower: it
made __testConnection() tolerate a malformed *reply*, but online() is still a
bare `return self.__testConnection()`, so anything the socket layer raises
(ConnectionResetError and friends from __post) still escapes a call that
exists only to answer "is the daemon there?". Removing this patch was tried
and the test caught it immediately.

Those patches replaced the SDK's methods wholesale, so leaving them in place
after the update would have silently overridden upstream's implementations
and masked any later improvement to them. The behaviour is still covered by
tests, which now assert it of the vendored SDK itself rather than of a patch.

NOTE: several older patches (synchronous RamFileManager.copy, robust
version file resolution, RamHost.publish state propagation) historically
live in fusion_host.py's monkey-patching section, not here.

Usage:
    import ramses_patches
    ramses_patches.apply()
"""

import os
import threading
from ramses.constants import LogLevel
from ramses.logger import log


def _patch_daemon_interface():
    """Makes RamDaemonInterface.online() never raise.

    online() is a connectivity probe and callers expect a bool. Upstream now
    guards the *shape* of the ping reply inside __testConnection(), but
    online() itself is a bare `return self.__testConnection()` and the socket
    send/recv path underneath can still raise (ConnectionResetError, and
    whatever a daemon dying mid-reply produces). Wrap it so a probe never
    takes down its caller.
    """
    from ramses.daemon_interface import RamDaemonInterface

    # This wraps the current online(), so a second apply() would wrap the
    # wrapper: Ramses-Fusion's entry script reloads its host module on every
    # launch and stacked one layer per launch before this guard existed.
    if getattr(RamDaemonInterface, "_ramses_patched", False):
        return

    _original_online = RamDaemonInterface.online

    def _patched_online(self):
        try:
            return bool(_original_online(self))
        except Exception as e:
            log("Daemon connectivity check failed: " + str(e), LogLevel.Debug)
            return False

    RamDaemonInterface.online = _patched_online
    RamDaemonInterface._ramses_patched = True


def apply():
    """Applies all available runtime patches."""
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
