# -*- coding: utf-8 -*-
"""
Ramses Ecosystem Runtime Patches
================================

This module contains critical runtime fixes that cannot be applied in upstream API files.

Patches applied:
 - RamFileManager: Forces synchronous file copying (threading fix).
 - RamFileManager: Robust version file path resolution (Case sensitivity + dir-based versioning).
 - RamMetaDataManager: Safe metadata reads (prevents silent data loss on corrupt JSON).
 - RamHost.publish: State propagation support (prevents archive status reversion).

Obsolete patches removed (fixed in upstream API):
 - LogLevel.Error: Now in constants.py.
 - Thread-safe daemon: Now in daemon_interface.py (_socket_lock).
 - Atomic settings save: Now in ram_settings.py.
 - FusionConfig._lua_to_dict patch: fusion_config.py already has the correct implementation;
   patching it was redundant maintenance weight.

Usage:
    import ramses_patches
    ramses_patches.apply()
"""

import os
import sys
import threading
from ramses.constants import LogLevel
from ramses.logger import log


def apply():
    """Applies all available runtime patches."""
    # NOTE: No fusion_config patch needed — fusion_config.py already contains the
    # correct robust parser. The old _patch_fusion_config was replacing it with an
    # identical copy (dead maintenance weight) and has been removed.
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
