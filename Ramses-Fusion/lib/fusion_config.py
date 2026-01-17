# -*- coding: utf-8 -*-
import re
import logging

class FusionConfig:
    """Helper class for parsing Fusion Saver nodes and managing Render Configuration."""

    EXTENSION_MAP = {
        "QuickTimeMovies": "mov",
        "OpenEXRFormat": "exr",
        "TiffFormat": "tif",
        "DPXFormat": "dpx",
        "MXFFormat": "mxf",
        "JpegFormat": "jpg",
        "PngFormat": "png",
        "TargaFormat": "tga",
        "CineonFormat": "cin"
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

        config = {
            "format": "",
            "properties": {}
        }

        # 1. Extract Output Format
        # Pattern: OutputFormat = Input { Value = FuID { "QuickTimeMovies" }, },
        format_match = re.search(r'OutputFormat\s*=\s*Input\s*\{\s*Value\s*=\s*FuID\s*\{\s*"([^"]+)"\s*\}\s*,?\s*\}', text)
        if format_match:
            config["format"] = format_match.group(1)
        else:
            # Helper: Try to find simple assignment if formatted differently
            simple_match = re.search(r'OutputFormat\s*=\s*FuID\s*\{\s*"([^"]+)"\s*\}', text)
            if simple_match:
                config["format"] = simple_match.group(1)

        if not config["format"]:
            return None

        # 2. Extract Properties
        # We look for inputs that start with the format name or are common parameters
        # Examples:
        # ["QuickTimeMovies.Compression"] = Input { Value = FuID { "Apple ProRes 422_apcn" }, }
        # ["OpenEXRFormat.Compression"] = Input { Value = 8, }
        # ["MXFFormat.FrameRateFps"] = Input { Value = 29.97, }
        
        # Regex to capture: Key (in brackets or plain) and the Value block
        # Key: \["?([\w\.]+)"?\]  -> Captures "QuickTimeMovies.Compression"
        # Value: Input\s*\{\s*Value\s*=\s*(.+?)\s*,?\s*\}
        
        # This is complex because the Value can be a number, a string, or a nested table (FuID).
        # We'll use a simpler approach: Iterate line by line or use specific extractors.
        
        # Refined Strategy: Find all inputs that look like format properties.
        # We scan for lines defining Inputs.
        
        prop_pattern = re.compile(r'\["([\w\.]+)"\]\s*=\s*Input\s*\{\s*Value\s*=\s*(.+?)\s*,?\s*\}')
        
        for match in prop_pattern.finditer(text):
            key = match.group(1)
            raw_value = match.group(2)
            
            # Only keep properties that belong to the detected format or generic ones we care about
            # Usually format properties start with the format name (e.g. "QuickTimeMovies.")
            if not key.startswith(config["format"]):
                continue

            # Parse the value
            # Case A: FuID { "Value" }
            fuid_match = re.search(r'FuID\s*\{\s*"([^"]+)"\s*\}', raw_value)
            if fuid_match:
                config["properties"][key] = fuid_match.group(1)
                continue
                
            # Case B: Number { Value = 4 } (Fusion sometimes wraps numbers)
            num_struct_match = re.search(r'Number\s*\{\s*Value\s*=\s*([\d\.-]+)\s*\}', raw_value)
            if num_struct_match:
                config["properties"][key] = float(num_struct_match.group(1))
                continue
                
            # Case C: Simple Number (Value = 8)
            # We check if it looks like a number
            try:
                # Remove trailing comma if captured
                clean_val = raw_value.strip().rstrip(",")
                val = float(clean_val)
                # Store as int if integer
                if val.is_integer():
                    config["properties"][key] = int(val)
                else:
                    config["properties"][key] = val
                continue
            except ValueError:
                pass
            
            # Case D: Boolean (1 or 0 usually in Fusion, or true/false)
            if raw_value.strip() in ["true", "True"]:
                config["properties"][key] = True
                continue
            if raw_value.strip() in ["false", "False"]:
                config["properties"][key] = False
                continue

        return config

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
