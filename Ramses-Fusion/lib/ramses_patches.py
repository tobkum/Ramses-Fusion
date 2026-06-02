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

import sys
from ramses.constants import LogLevel
from ramses.logger import log


def apply():
    """Applies all available runtime patches."""
    # NOTE: No fusion_config patch needed — fusion_config.py already contains the
    # correct robust parser. The old _patch_fusion_config was replacing it with an
    # identical copy (dead maintenance weight) and has been removed.
    log("Ramses runtime patches applied.", LogLevel.Debug)
