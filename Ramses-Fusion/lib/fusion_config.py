# -*- coding: utf-8 -*-
import re

__all__ = ["FusionConfig"]


class FusionConfig:
    """Helper class for parsing Fusion Saver nodes and managing Render Configuration.
    
    Uses a robust stack-based Lua parser to handle nested structures correctly.
    """

    EXTENSION_MAP = {
        "QuickTimeMovies": {"ext": "mov", "seq": False},
        "OpenEXRFormat": {"ext": "exr", "seq": True},
        "TiffFormat": {"ext": "tif", "seq": True},
        "DPXFormat": {"ext": "dpx", "seq": True},
        "MXFFormat": {"ext": "mxf", "seq": False},
        "JpegFormat": {"ext": "jpg", "seq": True},
        "PngFormat": {"ext": "png", "seq": True},
        "TargaFormat": {"ext": "tga", "seq": True},
        "CineonFormat": {"ext": "cin", "seq": True},
        "SGIFormat": {"ext": "sgi", "seq": True},
        "AVIFormat": {"ext": "avi", "seq": False},
        "BMPFormat": {"ext": "bmp", "seq": True},
        "PhotoshopFormat": {"ext": "psd", "seq": True},
        "SoftimageFormat": {"ext": "pic", "seq": True},
        "MayaFormat": {"ext": "iff", "seq": True},
        "Jpeg2000Format": {"ext": "jp2", "seq": True}
    }

    @staticmethod
    def parse_saver_node(text: str) -> dict:
        """Parses the text content of a copied Fusion Saver node.

        Extracts the OutputFormat and all specific format properties (e.g. Compression).
        
        Args:
            text (str): The raw text from the clipboard (Lua table structure).

        Returns:
            dict: A dictionary with 'format' (str) and 'properties' (dict).
                  Returns None if the text is not a valid Saver node.
        """
        if not text or "Saver" not in text:
            return None

        # 1. Isolate the Inputs block to save parsing time and avoid noise
        # We look for 'Inputs = {' and count braces to capture the full block.
        inputs_start = text.find("Inputs = {")
        if inputs_start == -1:
            return None
            
        # Extract the Inputs block text using a brace counter
        inputs_text = FusionConfig._extract_block(text, inputs_start + 9) # +9 to skip "Inputs = "
        if not inputs_text:
            return None

        # 2. Parse the Lua Table into a Python Dictionary
        try:
            inputs_data = FusionConfig._lua_to_dict(inputs_text)
        except ValueError:
            return None
        
        config = {
            "format": "",
            "properties": {}
        }
        
        # 3. Extract Format
        # Input: OutputFormat = Input { Value = FuID { "FormatName" } }
        # Parsed: {'OutputFormat': {'Value': 'FormatName'}} (because we handle FuID unwrapping)
        
        # Helper to get value safely from our parsed structure
        def get_val(key):
            # Key can be "OutputFormat" or "['OutputFormat']" depending on tokenizer,
            # but our tokenizer strips brackets/quotes for keys.
            node = inputs_data.get(key)
            if not node: return None
            # Check for standard Input { Value = X } structure
            if isinstance(node, dict) and "Value" in node:
                return node["Value"]
            # Fallback for direct assignment
            return node

        fmt = get_val("OutputFormat")
        if not fmt:
            return None
            
        config["format"] = fmt

        # 4. Extract Properties
        # Iterate over all parsed keys
        for key, val in inputs_data.items():
            # Only keep keys relevant to the format (e.g. "QuickTimeMovies.Compression")
            # Our tokenizer handles ["Key"] by stripping quotes, so key is clean.
            if not key.startswith(config["format"]):
                continue
                
            # Flatten the value if it's inside an Input { Value = ... } structure
            final_val = val
            if isinstance(val, dict) and "Value" in val:
                final_val = val["Value"]
            
            # Additional unwrapping for weird Fusion types if missed by parser (should rely on parser though)
            config["properties"][key] = final_val

        return config

    @staticmethod
    def _extract_block(text: str, start_index: int) -> str:
        """Extracts a balanced brace block starting at `start_index`.

        Iterates through the string to find the matching closing brace `}`
        for the opening brace `{` found at or after `start_index`.
        Ignores braces that appear inside double-quoted string literals.

        Args:
            text (str): The source text.
            start_index (int): Index to start searching for the opening brace.

        Returns:
            str: The content of the block including outer braces, or None if not found/balanced.
        """
        count = 0
        found_start = False
        in_string = False
        i = start_index
        n = len(text)
        while i < n:
            char = text[i]
            if in_string:
                if char == '\\' and i + 1 < n:
                    i += 2  # skip escaped character
                    continue
                if char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == '{':
                    count += 1
                    found_start = True
                elif char == '}':
                    count -= 1
                    if found_start and count == 0:
                        return text[start_index:i + 1]
            i += 1
        return None

    @staticmethod
    def _lua_to_dict(lua_str: str) -> dict:
        """Robust mini-parser for Lua tables found in Fusion nodes.
        
        Parses a subset of Lua syntax commonly used in Fusion clipboard data.
        Handles nested tables, constructors (FuID, Number, Input), primitives,
        and scientific notation.
        """
        def tokenize(s):
            tokens = []
            i, n = 0, len(s)
            while i < n:
                char = s[i]
                if char.isspace(): i += 1; continue
                # Comment skipping
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
            # Constructor pattern: ID { ... }
            nxt = peek(1)
            if type_ == 'ID' and nxt and nxt[0] == 'OP' and nxt[1] == '{':
                func_name = val
                next_tok() # ID
                struct_data = parse_table()
                if func_name == 'FuID':
                    return struct_data[0] if isinstance(struct_data, list) and struct_data else struct_data
                if func_name == 'Number':
                    return struct_data.get('Value', struct_data) if isinstance(struct_data, dict) else struct_data
                return struct_data # Input/Clip remain as dicts for get_val()
            next_tok()
            return val

        def parse_table():
            _depth[0] += 1
            if _depth[0] > _MAX_DEPTH: raise ValueError("Nesting too deep")
            next_tok() # {
            res_dict, res_list = {}, []
            while peek():
                if peek()[0] == 'OP' and peek()[1] == '}':
                    next_tok(); _depth[0] -= 1
                    return res_list if res_list and not res_dict else res_dict
                # Lookahead for Key = Value
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

    @staticmethod
    def get_extension(format_id: str) -> str:
        """Returns the default file extension for a given Fusion Format ID."""
        fmt_info = FusionConfig.EXTENSION_MAP.get(format_id)
        if isinstance(fmt_info, dict):
            return fmt_info.get("ext", "")
        return ""

    @staticmethod
    def is_sequence(format_id: str) -> bool:
        """Returns True if the given Fusion Format ID is typically an image sequence."""
        fmt_info = FusionConfig.EXTENSION_MAP.get(format_id)
        if isinstance(fmt_info, dict):
            return fmt_info.get("seq", False)
        return False

    @staticmethod
    def apply_config(node: object, config: dict) -> bool:
        """Applies a configuration dictionary to a Saver node.

        Args:
            node (object): The Fusion Saver tool.
            config (dict): The configuration dictionary (from YAML).

        Returns:
            bool: True if applied successfully.
        """
        if not node or not config:
            return False

        target_format = config.get("format")
        if not target_format:
            return False

        # 1. Set Output Format
        current_fmt = node.GetInput("OutputFormat")
        if current_fmt != target_format:
            node.SetInput("OutputFormat", target_format, 0)
        
        # 2. Apply Properties
        props = config.get("properties", {})
        for key, value in props.items():
            # Check existing value to avoid dirtying if possible (though difficult with generic inputs)
            # We simply set it. Fusion handles the types usually.
            
            # If the value is a string, it might be a FuID or just a string. 
            # For format properties like Compression, Fusion expects the ID string.
            node.SetInput(key, value, 0)
            
        return True