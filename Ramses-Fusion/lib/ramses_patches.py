# -*- coding: utf-8 -*-
"""
Ramses Ecosystem Runtime Patches
================================

This module contains critical fixes for fragile Fusion Lua parsing.
Upstream API has been upgraded with fixes for LogLevel.Error, thread-safe daemon,
and atomic settings save.

Usage:
    import ramses_patches
    ramses_patches.apply()
"""

import os
import sys
import json
import shutil
import tempfile
from ramses.constants import LogLevel
from ramses.ram_settings import RamSettings
from ramses.logger import log


def apply():
    """Applies all available runtime patches."""
    _patch_fusion_config()
    log("Ramses runtime patches applied.", LogLevel.Debug)


# ============================================================================
# OBSOLETE PATCHES REMOVED (Fixed in Upstream API)
# ============================================================================
# - LogLevel.Error (now in constants.py:69)
# - Thread-safe daemon (now in daemon_interface.py with _socket_lock)
# - Atomic settings save (now in ram_settings.py:166-175)
# ============================================================================


def _patch_fusion_config():
    """
    Fixes MEDIUM fragility in Fusion Lua parsing.
    Hot-patches fusion_config._lua_to_dict if the module is loaded.
    """
    if "fusion_config" in sys.modules:
        sys.modules["fusion_config"]._lua_to_dict = _robust_lua_to_dict


def _robust_lua_to_dict(lua_str):
    """
    Robust parser for Fusion clipboard data (Lua tables).
    Replaces fragile regex/tokenizer logic.
    """
    lua_str = lua_str.strip()
    if not (lua_str.startswith("{") and lua_str.endswith("}")):
        return {}

    def parse_value(s, idx):
        while idx < len(s) and s[idx].isspace():
            idx += 1
        if idx >= len(s):
            return None, idx

        char = s[idx]
        if char in ('"', "'"):  # String
            end = idx + 1
            while end < len(s):
                end = s.find(char, end)
                if end == -1:
                    return None, idx
                if s[end - 1] != "\\":
                    break
                end += 1
            return s[idx + 1 : end], end + 1
        elif char == "{":  # Nested Table
            return parse_table(s, idx)
        else:  # Number/Bool/Identifier
            end = idx
            while end < len(s) and s[end] not in ",}=":
                end += 1
            val = s[idx:end].strip()
            if val == "true":
                return True, end
            if val == "false":
                return False, end
            if val == "nil":
                return None, end
            try:
                return (float(val) if "." in val else int(val)), end
            except ValueError:
                return val, end

    def parse_table(s, idx):
        idx += 1  # Skip {
        result = {}
        implicit_idx = 1
        while idx < len(s):
            while idx < len(s) and s[idx].isspace():
                idx += 1
            if idx >= len(s) or s[idx] == "}":
                return result, idx + 1

            # Detect key vs value
            key = None
            is_explicit = False

            if s[idx] == "[":  # Bracketed key: [1] or ["Key"]
                end_bracket = s.find("]", idx)
                if end_bracket != -1:
                    key_str = s[idx + 1 : end_bracket]
                    key, _ = parse_value(key_str, 0)
                    assign = end_bracket + 1
                    while assign < len(s) and s[assign].isspace():
                        assign += 1
                    if assign < len(s) and s[assign] == "=":
                        idx = assign + 1
                        is_explicit = True

            if not is_explicit:  # Identifier or Value
                val, end_val = parse_value(s, idx)
                check = end_val
                while check < len(s) and s[check].isspace():
                    check += 1
                if check < len(s) and s[check] == "=":  # It was a key
                    key = val
                    idx = check + 1
                    is_explicit = True
                else:  # It was a value
                    result[implicit_idx] = val
                    implicit_idx += 1
                    idx = end_val

            if is_explicit:
                val, idx = parse_value(s, idx)
                result[key] = val

            while idx < len(s) and (s[idx].isspace() or s[idx] == ","):
                idx += 1

        return result, idx

    res, _ = parse_table(lua_str, 0)
    return res
