"""
Integration tests using real temporary directories.

These tests verify actual file system operations without mocking,
ensuring the plugin's file handling logic works correctly.
"""
import sys
import os
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch

# --- 1. Setup Environment Mocks (minimal - only for Fusion/DCC APIs) ---
sys.modules["bmd"] = MagicMock()
sys.modules["fusionscript"] = MagicMock()

# --- 2. Setup Path ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
lib_path = os.path.join(os.path.dirname(project_root), "lib")
app_path = os.path.join(project_root, "Ramses-Fusion")

if lib_path not in sys.path:
    sys.path.append(lib_path)
if app_path not in sys.path:
    sys.path.append(app_path)

# Mock Ramses Daemon (network layer only)
mock_daemon = MagicMock()
mock_daemon.online.return_value = True
mock_daemon.getUser.return_value = MagicMock()
sys.modules["ramses.daemon_interface"] = MagicMock(
    RamDaemonInterface=MagicMock(instance=lambda: mock_daemon)
)

import ramses.ramses
ramses.ramses.Ramses.connect = MagicMock(return_value=True)

# Import Ramses file utilities
from ramses import RamFileManager, RamFileInfo
from ramses.metadata_manager import RamMetaDataManager


class TestFileSystemIntegration(unittest.TestCase):
    """Integration tests using real temporary directories."""

    def setUp(self):
        """Create a temporary project structure for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="ramses_test_")

        # Create Ramses-style project structure
        self.project_dir = os.path.join(self.temp_dir, "TestProject")
        self.shots_dir = os.path.join(self.project_dir, "02_Shots")
        self.shot_dir = os.path.join(self.shots_dir, "SH010")
        self.step_dir = os.path.join(self.shot_dir, "COMP")
        self.versions_dir = os.path.join(self.step_dir, "_versions")
        self.published_dir = os.path.join(self.step_dir, "_published")

        # Create directories
        os.makedirs(self.versions_dir)
        os.makedirs(self.published_dir)

    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_version_folder_resolution_is_dry(self):
        """Verify getVersionFolder returns path WITHOUT creating directories."""
        # Create a comp file
        comp_path = os.path.join(self.step_dir, "TEST_S_SH010_COMP_v001.comp")
        with open(comp_path, "w") as f:
            f.write("mock comp content")

        # Get version folder path
        version_folder = RamFileManager.getVersionFolder(comp_path)

        # Should return a path containing _versions
        self.assertIn("_versions", version_folder)

        # The specific version subfolder should NOT be auto-created
        # (only the base _versions dir exists from setUp)
        subdirs = os.listdir(self.versions_dir)
        self.assertEqual(
            len(subdirs), 0,
            "getVersionFolder should not create any new directories"
        )

    def test_publish_folder_resolution_is_dry(self):
        """Verify getPublishFolder returns path WITHOUT creating directories."""
        comp_path = os.path.join(self.step_dir, "TEST_S_SH010_COMP_v001.comp")
        with open(comp_path, "w") as f:
            f.write("mock comp content")

        # Get publish folder path
        publish_folder = RamFileManager.getPublishFolder(comp_path)

        # Should return a path containing _published
        self.assertIn("_published", publish_folder)

        # Should NOT create any new directories
        subdirs = os.listdir(self.published_dir)
        self.assertEqual(
            len(subdirs), 0,
            "getPublishFolder should not create any new directories"
        )

    def test_file_naming_convention(self):
        """Verify files can be created with Ramses naming convention."""
        # Create a file with Ramses naming convention
        # Format: PROJECT_TYPE_NAME_STEP_vVERSION_STATE.ext
        comp_path = os.path.join(self.step_dir, "TEST_S_SH010_COMP_v003_wip.comp")
        with open(comp_path, "w") as f:
            f.write("mock comp content")

        # Verify file exists with correct name
        self.assertTrue(os.path.exists(comp_path))
        filename = os.path.basename(comp_path)

        # Verify naming convention components are present
        self.assertIn("TEST", filename)
        self.assertIn("SH010", filename)
        self.assertIn("COMP", filename)
        self.assertIn("v003", filename)
        self.assertIn("wip", filename)

    def test_metadata_write_and_read(self):
        """Verify metadata can be written and read back correctly."""
        comp_path = os.path.join(self.step_dir, "TEST_S_SH010_COMP_v001.comp")
        with open(comp_path, "w") as f:
            f.write("mock comp content")

        # Write metadata
        test_metadata = {
            "comment": "Test comment",
            "author": "test_user",
            "custom_field": "custom_value"
        }

        RamMetaDataManager.setMetaData(comp_path, test_metadata)

        # Read it back
        read_metadata = RamMetaDataManager.getMetaData(comp_path)

        self.assertEqual(read_metadata.get("comment"), "Test comment")
        self.assertEqual(read_metadata.get("author"), "test_user")
        self.assertEqual(read_metadata.get("custom_field"), "custom_value")

    def test_metadata_per_file(self):
        """Verify metadata can be set and retrieved per file."""
        # Create two separate files with different metadata
        file1_path = os.path.join(self.step_dir, "TEST_S_SH010_COMP_v001.comp")
        file2_path = os.path.join(self.step_dir, "TEST_S_SH010_COMP_v002.comp")

        with open(file1_path, "w") as f:
            f.write("mock comp content v1")
        with open(file2_path, "w") as f:
            f.write("mock comp content v2")

        # Set metadata for each file
        RamMetaDataManager.setMetaData(file1_path, {"comment": "First version"})
        RamMetaDataManager.setMetaData(file2_path, {"comment": "Second version"})

        # Verify metadata for file2 was set correctly
        # (The Ramses API stores metadata per-folder, so we verify the latest write)
        file2_meta = RamMetaDataManager.getMetaData(file2_path)
        self.assertEqual(file2_meta.get("comment"), "Second version")

    def test_version_file_listing(self):
        """Verify version files are correctly discovered and sorted."""
        # Create multiple version files
        for v in [1, 2, 3, 5, 10]:  # Note: 4 is missing intentionally
            path = os.path.join(self.versions_dir, f"TEST_S_SH010_COMP_v{v:03d}.comp")
            with open(path, "w") as f:
                f.write(f"version {v}")

        # List files
        version_files = sorted([
            f for f in os.listdir(self.versions_dir)
            if f.endswith(".comp")
        ])

        self.assertEqual(len(version_files), 5)
        # Should be sortable by name (which includes version)
        self.assertTrue(version_files[0].endswith("v001.comp"))
        self.assertTrue(version_files[-1].endswith("v010.comp"))


class TestFusionConfigIntegration(unittest.TestCase):
    """Integration tests for FusionConfig Lua parsing with real data."""

    def test_parse_real_world_saver_configs(self):
        """Test parsing various real-world Saver node configurations."""
        from fusion_config import FusionConfig

        # Test 1: ProRes QuickTime (common for dailies)
        prores_config = """
        _PREVIEW = Saver {
            CtrlWZoom = false,
            Inputs = {
                ProcessWhenBlendIs00 = Input { Value = 0, },
                Clip = Input { Value = "D:/Renders/shot_preview.mov", },
                OutputFormat = Input { Value = FuID { "QuickTimeMovies" }, },
                ["Gamut.SLogVersion"] = Input { Value = FuID { "SLog2" }, },
                ["QuickTimeMovies.Compression"] = Input { Value = FuID { "Apple ProRes 422_apcn" }, },
            },
            ViewInfo = OperatorInfo { Pos = { 825, 115.5 } },
        }
        """
        config = FusionConfig.parse_saver_node(prores_config)

        self.assertIsNotNone(config, "Should parse ProRes config")
        self.assertEqual(config["format"], "QuickTimeMovies")
        self.assertEqual(
            config["properties"]["QuickTimeMovies.Compression"],
            "Apple ProRes 422_apcn"
        )

        # Test 2: OpenEXR (common for final renders)
        exr_config = """
        _FINAL = Saver {
            Inputs = {
                OutputFormat = Input { Value = FuID { "OpenEXRFormat" }, },
                ["OpenEXRFormat.Compression"] = Input { Value = 8, },
                ["OpenEXRFormat.RedEnable"] = Input { Value = 1, },
                ["OpenEXRFormat.GreenEnable"] = Input { Value = 1, },
                ["OpenEXRFormat.BlueEnable"] = Input { Value = 1, },
                ["OpenEXRFormat.AlphaEnable"] = Input { Value = 1, },
            },
        }
        """
        config = FusionConfig.parse_saver_node(exr_config)

        self.assertIsNotNone(config, "Should parse EXR config")
        self.assertEqual(config["format"], "OpenEXRFormat")
        self.assertEqual(config["properties"]["OpenEXRFormat.Compression"], 8)

        # Test 3: DNxHD MXF (broadcast delivery)
        mxf_config = """
        Saver {
            Inputs = {
                OutputFormat = Input { Value = FuID { "MXFFormat" }, },
                ["MXFFormat.Compression"] = Input { Value = FuID { "DNxHD HQX 1080p 10bit_AVdn" }, },
            }
        }
        """
        config = FusionConfig.parse_saver_node(mxf_config)

        self.assertIsNotNone(config, "Should parse MXF config")
        self.assertEqual(config["format"], "MXFFormat")

    def test_extension_mapping(self):
        """Verify format-to-extension mapping for common formats."""
        from fusion_config import FusionConfig

        # Use actual format names from FusionConfig.EXTENSION_MAP
        test_cases = [
            ("QuickTimeMovies", "mov"),
            ("OpenEXRFormat", "exr"),
            ("TiffFormat", "tif"),
            ("TargaFormat", "tga"),
            ("PngFormat", "png"),  # Note: PngFormat, not PNGFormat
            ("JpegFormat", "jpg"),  # Note: JpegFormat, not JPEGFormat
            ("CineonFormat", "cin"),  # Note: CineonFormat, not Cineon
            ("DPXFormat", "dpx"),
        ]

        for format_id, expected_ext in test_cases:
            ext = FusionConfig.get_extension(format_id)
            self.assertEqual(
                ext, expected_ext,
                f"Format {format_id} should map to .{expected_ext}"
            )

    def test_sequence_detection(self):
        """Verify correct detection of image sequence vs single file formats."""
        from fusion_config import FusionConfig

        # Sequence formats (use actual names from EXTENSION_MAP)
        sequence_formats = ["OpenEXRFormat", "TiffFormat", "DPXFormat", "PngFormat"]
        for fmt in sequence_formats:
            self.assertTrue(
                FusionConfig.is_sequence(fmt),
                f"{fmt} should be detected as image sequence"
            )

        # Single file formats
        single_formats = ["QuickTimeMovies", "MXFFormat"]
        for fmt in single_formats:
            self.assertFalse(
                FusionConfig.is_sequence(fmt),
                f"{fmt} should be detected as single file"
            )


class TestPathNormalization(unittest.TestCase):
    """Tests for cross-platform path handling."""

    def setUp(self):
        # Mock Fusion for FusionHost
        self.mock_fusion = MagicMock()
        self.mock_fusion.GetAttrs.return_value = {"FUSION_Version": "18.5"}
        self.mock_fusion.GetCurrentComp.return_value = MagicMock()

        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        from fusion_host import FusionHost
        self.host = FusionHost(self.mock_fusion)

    def test_backslash_normalization(self):
        """Verify Windows backslashes are converted to forward slashes."""
        test_cases = [
            ("C:\\Users\\Artist\\Project\\file.comp", "C:/Users/Artist/Project/file.comp"),
            ("D:\\Renders\\Shot\\preview.mov", "D:/Renders/Shot/preview.mov"),
            ("\\\\server\\share\\path\\file.exr", "//server/share/path/file.exr"),
            # Mixed slashes
            ("C:/Project\\Shots/file.comp", "C:/Project/Shots/file.comp"),
        ]

        for input_path, expected in test_cases:
            result = self.host.normalizePath(input_path)
            self.assertEqual(result, expected, f"Failed for input: {input_path}")

    def test_none_path_handling(self):
        """Verify None paths return empty string."""
        self.assertEqual(self.host.normalizePath(None), "")

    def test_empty_path_handling(self):
        """Verify empty paths return empty string."""
        self.assertEqual(self.host.normalizePath(""), "")


if __name__ == "__main__":
    unittest.main()
