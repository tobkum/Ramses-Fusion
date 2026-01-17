# -*- coding: utf-8 -*-
import re

class FusionConfig:
    """Helper class for parsing Fusion Saver nodes and managing Render Configuration.
    
    Uses a robust stack-based Lua parser to handle nested structures correctly.
    """

    EXTENSION_MAP = {
        "QuickTimeMovies": "mov",
        "OpenEXRFormat": "exr",
        "TiffFormat": "tif",
        "DPXFormat": "dpx",
        "MXFFormat": "mxf",
        "JpegFormat": "jpg",
        "PngFormat": "png",
        "TargaFormat": "tga",
        "CineonFormat": "cin",
        "SGIFormat": "sgi",
        "AVIFormat": "avi",
        "BMPFormat": "bmp",
        "PhotoshopFormat": "psd",
        "SoftimageFormat": "pic",
        "MayaFormat": "iff",
        "Jpeg2000Format": "jp2"
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
        inputs_data = FusionConfig._lua_to_dict(inputs_text)
        
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
        
        Args:
            text (str): The source text.
            start_index (int): Index to start searching for the opening brace.
            
        Returns:
            str: The content of the block including outer braces, or None if not found/balanced.
        """
        count = 0
        found_start = False
        
        for i in range(start_index, len(text)):
            char = text[i]
            if char == '{':
                count += 1
                found_start = True
            elif char == '}':
                count -= 1
                if found_start and count == 0:
                    return text[start_index:i+1]
        return None

    @staticmethod
    def _lua_to_dict(lua_str: str) -> dict:
        """Robust mini-parser for Lua tables found in Fusion nodes.
        
        Parses a subset of Lua syntax commonly used in Fusion clipboard data.
        Handles:
        - Nested tables `{ ... }`
        - Key-Value assignment `Key = Value`
        - Implicit array indices `{ Val1, Val2 }`
        - Primitive types (String, Number, Bool)
        - Fusion-specific structures (`FuID { "Val" }`, `Number { Value = X }`) 
          by unwrapping them into native Python types where appropriate.
          
        Args:
            lua_str (str): The string content of a Lua table (e.g. `{ Key = ... }`).
            
        Returns:
            dict: The parsed data structure.
        """
        
        # Tokenizer
        def tokenize(s):
            tokens = []
            i = 0
            n = len(s)
            while i < n:
                char = s[i]
                
                if char.isspace():
                    i += 1
                    continue
                
                if char in '{}=,':
                    tokens.append(('OP', char))
                    i += 1
                    continue
                
                if char == '"':
                    # String literal
                    j = i + 1
                    while j < n and s[j] != '"':
                        # Handle escaped quotes if necessary (Fusion is simple usually)
                        if s[j] == '\\' and j+1 < n:
                            j += 2
                        else:
                            j += 1
                    val = s[i+1:j] # Strip quotes
                    tokens.append(('STR', val))
                    i = j + 1
                    continue
                    
                if char == '[':
                    # Key bracket ["Key"]
                    j = s.find(']', i)
                    if j != -1:
                        # Extract content inside brackets
                        inner = s[i+1:j].strip()
                        # If quoted, strip quotes
                        if inner.startswith('"') and inner.endswith('"'):
                            inner = inner[1:-1]
                        tokens.append(('KEY', inner))
                        i = j + 1
                        continue
                        
                # Identifier or Number
                j = i
                while j < n and (s[j].isalnum() or s[j] in '._-'):
                    j += 1
                
                val = s[i:j]
                
                # Check for booleans/numbers
                if val == 'true': tokens.append(('BOOL', True))
                elif val == 'false': tokens.append(('BOOL', False))
                elif val.replace('.','',1).isdigit():
                    if '.' in val: tokens.append(('NUM', float(val)))
                    else: tokens.append(('NUM', int(val)))
                else:
                    tokens.append(('ID', val))
                i = j
            return tokens

        tokens = tokenize(lua_str)
        token_iter = iter(tokens)
        current_token = [next(token_iter, None)]

        def next_tok():
            t = current_token[0]
            try:
                current_token[0] = next(token_iter)
            except StopIteration:
                current_token[0] = None
            return t
            
        def peek():
            return current_token[0]

        def parse_value():
            tok = peek()
            if not tok: return None
            
            type_, val = tok
            
            if type_ == 'OP' and val == '{':
                return parse_table()
            
            # Consume the value token
            next_tok()
            
            # Handle Function Calls like FuID { "X" } or Input { ... }
            # If we see an Identifier followed immediately by '{', it's a struct
            if type_ == 'ID' and peek() and peek()[0] == 'OP' and peek()[1] == '{':
                struct_data = parse_table() # Consumes the { ... }

                # Unwrap specific Fusion types immediately for cleaner data
                if val == 'FuID':
                    # FuID { "Value" } -> returns "Value"
                    # Usually FuID table is implicit array [1] = "Value" or just string inside?
                    # The tokenizer sees: FuID, {, STR("Val"), }
                    # parse_table returns {0: "Val"} or similar?
                    # Fusion table: { "Val" } -> Python list/dict.
                    # My parse_table returns list if indices are implicit.
                    if isinstance(struct_data, list) and len(struct_data) > 0:
                        return struct_data[0]
                    return struct_data # Fallback
                    
                if val == 'Number':
                    # Number { Value = 4 } -> returns 4
                    if isinstance(struct_data, dict) and 'Value' in struct_data:
                        return struct_data['Value']
                    return struct_data
                    
                if val == 'Input':
                    # Keep Input structure intact: { 'Value': ... }
                    return struct_data
                    
                return struct_data
                
            return val

        def parse_table():
            # Consume '{'
            next_tok()
            
            data_dict = {}
            data_list = []
            
            while peek():
                tok = peek()
                if tok[0] == 'OP' and tok[1] == '}':
                    next_tok() # Consume '}'
                    # Return list if only implicit keys, else dict
                    if data_list and not data_dict:
                        return data_list
                    return data_dict
                
                # Check for explicit Key assignment: Key = Val
                # Key can be ID or KEY token.
                key = None
                is_assignment = False
                
                # Look ahead for '=' (limited lookahead hack: consume, check, backtrack if needed? 
                # Or just assume structure). 
                # Fusion structure is predictable: Key = Val, or Val (implicit index)
                
                # We consume first token
                first = next_tok()
                
                if peek() and peek()[0] == 'OP' and peek()[1] == '=':
                    # It is a key assignment
                    next_tok() # Consume '='
                    key = first[1]
                    val = parse_value()
                    data_dict[key] = val
                else:
                    # It is an implicit value (array item)
                    # We consumed 'first' thinking it was a key, but it's actually the value (or start of it)
                    # This is tricky because parse_value expects to START at the value.
                    # We need to "put back" the token or handle it.
                    # Since we are recursive descent, explicit lookahead is cleaner.
                    # But here, let's just handle primitive value directly if we consumed it.
                    
                    # Logic fix:
                    # parse_value handles nested structs (ID + {).
                    # If 'first' was ID and next is '{', it was start of struct.
                    val = None
                    if first[0] == 'ID' and peek()[0] == 'OP' and peek()[1] == '{':
                         # Reconstruct the "ID {" sequence logic
                         struct_name = first[1]
                         struct_data = parse_table()
                         
                         # Same unwrapping logic as parse_value
                         if struct_name == 'FuID':
                             if isinstance(struct_data, list) and len(struct_data) > 0: val = struct_data[0]
                             else: val = struct_data
                         elif struct_name == 'Number':
                             if isinstance(struct_data, dict) and 'Value' in struct_data: val = struct_data['Value']
                             else: val = struct_data
                         else:
                             val = struct_data # e.g. Input { ... } or Clip { ... }
                    else:
                        # Simple primitive
                        val = first[1]
                    
                    data_list.append(val)
                
                # Consume comma if present
                if peek() and peek()[0] == 'OP' and peek()[1] == ',':
                    next_tok()
                    
            return data_dict

        # Start parsing (Lua top level is implicit table usually, or we start inside one)
        # inputs_text starts with '{'.
        return parse_value()

    @staticmethod
    def get_extension(format_id: str) -> str:
        """Returns the default file extension for a given Fusion Format ID."""
        return FusionConfig.EXTENSION_MAP.get(format_id, "")

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