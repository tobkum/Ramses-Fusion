import unittest
import sys
import os

# Setup path to import fusion_config
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
lib_path = os.path.join(project_root, "Ramses-Fusion", "lib")
if lib_path not in sys.path:
    sys.path.append(lib_path)

from fusion_config import FusionConfig

class TestFusionConfig(unittest.TestCase):

    def test_parse_simple_saver(self):
        """Test parsing a standard formatted Saver node."""
        text = """
        _PREVIEW = Saver {
            Inputs = {
                OutputFormat = Input { Value = FuID { "QuickTimeMovies" }, },
                ["QuickTimeMovies.Compression"] = Input { Value = FuID { "Apple ProRes 422_apcn" }, },
            }
        }
        """
        config = FusionConfig.parse_saver_node(text)
        self.assertIsNotNone(config)
        self.assertEqual(config["format"], "QuickTimeMovies")
        self.assertEqual(config["properties"]["QuickTimeMovies.Compression"], "Apple ProRes 422_apcn")

    def test_parse_nested_exr(self):
        """Test parsing OpenEXR format with nested Number values."""
        text = """
        _PREVIEW_1 = Saver {
            Inputs = {
                OutputFormat = Input { Value = FuID { "OpenEXRFormat" }, },
                ["OpenEXRFormat.Compression"] = Input { Value = 8, },
                ["OpenEXRFormat.ZipCompressionLevel"] = Input { 
                    Value = Number { 
                        Value = 4 
                    }, 
                },
            }
        }
        """
        config = FusionConfig.parse_saver_node(text)
        self.assertEqual(config["format"], "OpenEXRFormat")
        self.assertEqual(config["properties"]["OpenEXRFormat.Compression"], 8)
        self.assertEqual(config["properties"]["OpenEXRFormat.ZipCompressionLevel"], 4)

    def test_parse_one_liner(self):
        """Test parsing a minified/one-liner Saver node."""
        text = '_FINAL = Saver { Inputs = { OutputFormat = Input { Value = FuID { "TargaFormat" }, }, ["TargaFormat.Compression"] = Input { Value = 1, } } }'
        config = FusionConfig.parse_saver_node(text)
        self.assertEqual(config["format"], "TargaFormat")
        self.assertEqual(config["properties"]["TargaFormat.Compression"], 1)

    def test_parse_complex_nested_fuid(self):
        """Test parsing complex/weird nesting if Fusion does it."""
        text = """
        Saver {
            Inputs = {
                OutputFormat = Input { Value = FuID { "MXFFormat" }, },
                ["MXFFormat.Compression"] = Input { Value = FuID { "DNxHD HQX 1080p 10bit_AVdn" }, },
                ["MXFFormat.Advanced"] = Input { Value = 1, },
            }
        }
        """
        config = FusionConfig.parse_saver_node(text)
        self.assertEqual(config["format"], "MXFFormat")
        self.assertEqual(config["properties"]["MXFFormat.Compression"], "DNxHD HQX 1080p 10bit_AVdn")
        self.assertEqual(config["properties"]["MXFFormat.Advanced"], 1)

    def test_parse_invalid_text(self):
        """Test that invalid text returns None."""
        self.assertIsNone(FusionConfig.parse_saver_node("Not a Saver node"))
        self.assertIsNone(FusionConfig.parse_saver_node("Saver { Inputs = { } }")) # No OutputFormat

    def test_extract_block(self):
        """Test the brace extraction logic directly."""
        text = "Start { Middle { Inner } } End"
        block = FusionConfig._extract_block(text, 6) # Start at first {
        self.assertEqual(block, "{ Middle { Inner } }")

    def test_lua_to_dict_primitives(self):
        """Test the Lua tokenizer/parser with primitives."""
        lua = '{ Key = "Value", Num = 123, Bool = true }'
        data = FusionConfig._lua_to_dict(lua)
        self.assertEqual(data["Key"], "Value")
        self.assertEqual(data["Num"], 123)
        self.assertEqual(data["Bool"], True)

    def test_lua_to_dict_nested(self):
        """Test the Lua tokenizer/parser with nested tables."""
        lua = '{ Outer = { Inner = { Deep = "Core" } } }'
        data = FusionConfig._lua_to_dict(lua)
        self.assertEqual(data["Outer"]["Inner"]["Deep"], "Core")

    def test_lua_comments(self):
        """Verify that Lua comments are ignored."""
        lua = """{ 
            Key = "Value", -- This is a comment
            -- Full line comment
            Num = 42 -- Another comment
        }"""
        data = FusionConfig._lua_to_dict(lua)
        self.assertEqual(data["Key"], "Value")
        self.assertEqual(data["Num"], 42)

    def test_scientific_notation(self):
        """Verify parsing of scientific notation and negative numbers."""
        lua = '{ Gain = 1.0e-5, Blur = -4.5, Integer = 10 }'
        data = FusionConfig._lua_to_dict(lua)
        self.assertEqual(data["Gain"], 1.0e-5)
        self.assertIsInstance(data["Gain"], float)
        self.assertEqual(data["Blur"], -4.5)
        self.assertIsInstance(data["Blur"], float)
        self.assertEqual(data["Integer"], 10)
        self.assertIsInstance(data["Integer"], int)

    def test_get_extension(self):
        self.assertEqual(FusionConfig.get_extension("QuickTimeMovies"), "mov")
        self.assertEqual(FusionConfig.get_extension("OpenEXRFormat"), "exr")
        self.assertEqual(FusionConfig.get_extension("Unknown"), "")

if __name__ == "__main__":
    unittest.main()
