# -*- coding: utf-8 -*-
"""
Ramses Ecosystem Runtime Patches
================================

Runtime fixes for the vendored ramses-py SDK (lib/ramses/). The SDK files
themselves are deliberately never edited so they stay cleanly replaceable
from upstream — anything the SDK gets wrong is corrected here at runtime.

Applied at import time (this module):
 - DisableMakedirs / guarded os.makedirs (see below).

apply() currently installs nothing. It stays as the hook for the next patch,
and because both host modules call it at import.

Removed, because they are fixed in the vendored SDK:
 - RamMetaDataManager.getMetaData no longer prunes entries for missing files
   (Ramses-Py 30582ce, PRs #12/#13)
 - RamMetaDataManager.setFileMetaData refuses to rewrite from an unreadable
   sidecar (30582ce)
 - RamMetaDataManager.getValue/setValue guard a falsy filePath (30582ce)
 - RamDaemonInterface.online returns False instead of leaking socket
   exceptions from a call that only answers "is the daemon there?"
   (Ramses-Py d19ce44, PR #16)

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


def apply():
    """Applies all available runtime patches.

    Nothing to install at the moment. Any future patch must be idempotent:
    Ramses-Fusion's entry script reloads its host module on every launch, so
    apply() runs again in the same interpreter, and a patch that wraps the
    method it replaces used to stack one wrapper layer per launch.
    """
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
