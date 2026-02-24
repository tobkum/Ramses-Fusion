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
    Hot-patches FusionConfig._lua_to_dict with the robust index-based parser.
    """
    if "fusion_config" in sys.modules:
        fc_module = sys.modules["fusion_config"]
        fc_class = getattr(fc_module, "FusionConfig", None)
        if fc_class is not None:
            fc_class._lua_to_dict = staticmethod(_robust_lua_to_dict)


def _robust_lua_to_dict(lua_str):
    """
    Robust mini-parser for Lua tables found in Fusion nodes.
    Supports constructors, scientific notation, and Lua comments.
    """
    def tokenize(s):
        tokens = []
        i, n = 0, len(s)
        while i < n:
            char = s[i]
            if char.isspace(): i += 1; continue
            if char == '-' and i + 1 < n and s[i+1] == '-':
                j = s.find('\n', i + 2)
                if j == -1: break
                i = j + 1; continue
            if char in '{}=,': tokens.append(('OP', char)); i += 1; continue
            if char == '"':
                j = i + 1
                while j < n and s[j] != '"':
                    if s[j] == '\\' and j + 1 < n: j += 2
                    else: j += 1
                tokens.append(('STR', s[i+1:j])); i = j + 1; continue
            if char == '[':
                j = s.find(']', i)
                if j != -1:
                    inner = s[i+1:j].strip()
                    if inner.startswith('"') and inner.endswith('"'): inner = inner[1:-1]
                    tokens.append(('KEY', inner)); i = j + 1; continue
            j = i
            while j < n and (s[j].isalnum() or s[j] in '._-'): j += 1
            val = s[i:j]
            if val == 'true': tokens.append(('BOOL', True))
            elif val == 'false': tokens.append(('BOOL', False))
            elif val == 'nil': tokens.append(('NIL', None))
            else:
                try:
                    num = float(val)
                    tokens.append(('NUM', int(num) if num.is_integer() and '.' not in val and 'e' not in val.lower() else num))
                except ValueError: tokens.append(('ID', val))
            i = j
        return tokens

    tokens = tokenize(lua_str)
    n_tokens = len(tokens)
    _idx, _depth, _MAX_DEPTH = [0], [0], 64

    def peek(offset=0):
        pos = _idx[0] + offset
        return tokens[pos] if pos < n_tokens else None

    def next_tok():
        t = peek()
        if t: _idx[0] += 1
        return t

    def parse_value():
        tok = peek()
        if not tok: return None
        type_, val = tok
        if type_ == 'OP' and val == '{': return parse_table()
        nxt = peek(1)
        if type_ == 'ID' and nxt and nxt[0] == 'OP' and nxt[1] == '{':
            func_name = val
            next_tok()
            struct_data = parse_table()
            if func_name == 'FuID': return struct_data[0] if isinstance(struct_data, list) and struct_data else struct_data
            if func_name == 'Number': return struct_data.get('Value', struct_data) if isinstance(struct_data, dict) else struct_data
            return struct_data
        next_tok()
        return val

    def parse_table():
        _depth[0] += 1
        if _depth[0] > _MAX_DEPTH: raise ValueError("Nesting too deep")
        next_tok() # {
        res_dict, res_list, implicit_idx = {}, [], 1
        while peek():
            if peek()[0] == 'OP' and peek()[1] == '}':
                next_tok(); _depth[0] -= 1
                return res_list if res_list and not res_dict else res_dict
            is_assign = False
            try:
                nxt = peek(1)
                if nxt and nxt[0] == 'OP' and nxt[1] == '=': is_assign = True
            except (ValueError, IndexError): pass
            if is_assign:
                key_tok = next_tok()
                next_tok() # =
                res_dict[key_tok[1]] = parse_value()
            else:
                res_list.append(parse_value())
            if peek() and peek()[0] == 'OP' and peek()[1] == ',': next_tok()
        _depth[0] -= 1
        return res_dict

    return parse_value()
