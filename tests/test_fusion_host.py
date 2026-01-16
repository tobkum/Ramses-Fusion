import sys
import os
import unittest
from unittest.mock import MagicMock

# --- 1. Setup Environment Mocks ---
# We must mock modules that don't exist in standard Python but are expected by the plugin
sys.modules["bmd"] = MagicMock()
sys.modules["fusionscript"] = MagicMock()

# Mock the Ramses Daemon to prevent actual socket connection attempts and timeouts
mock_daemon = MagicMock()
mock_daemon.online.return_value = True
mock_daemon.getUser.return_value = MagicMock() # Mock user to satisfy connect() check
sys.modules["ramses.daemon_interface"] = MagicMock(RamDaemonInterface=MagicMock(instance=lambda: mock_daemon))

# --- 2. Setup Path ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
lib_path = os.path.join(project_root, "Ramses-Fusion", "lib")
if lib_path not in sys.path:
    sys.path.append(lib_path)

# Mock Ramses.connect to prevent the client from launching during tests
import ramses.ramses
ramses.ramses.Ramses.connect = MagicMock(return_value=False)

# --- 3. Import Code Under Test ---
from fusion_host import FusionHost
from tests.mocks import MockFusion
from ramses import LogLevel

class TestFusionHost(unittest.TestCase):

    def setUp(self):
        self.mock_fusion = MockFusion()
        self.host = FusionHost(self.mock_fusion)

    def test_initialization(self):
        """Test if the host initializes and gets version from mock."""
        self.assertEqual(self.host.hostName, "Fusion")
        self.assertEqual(self.host.hostVersion, "18.5 (Mock)")

    def test_normalize_path(self):
        """Test path normalization (backslashes to forward slashes)."""
        path = "C:\\Users\\Test\\File.comp"
        expected = "C:/Users/Test/File.comp"
        self.assertEqual(self.host.normalizePath(path), expected)
        self.assertEqual(self.host.normalizePath(None), "")

    def test_current_file_path(self):
        """Test retrieving the current file path."""
        path = self.host.currentFilePath()
        self.assertEqual(path, "D:/Projects/Test/TEST_S_Shot01_COMP_v001.comp")

    def test_sanitize_node_name(self):
        """Test node name sanitization logic."""
        self.assertEqual(self.host._sanitizeNodeName("My Node"), "My_Node")
        self.assertEqual(self.host._sanitizeNodeName("123Node"), "R_123Node")
        self.assertEqual(self.host._sanitizeNodeName("Node!@#"), "Node___")

    def test_import_logic(self):
        """Test the _import method logic (node creation and placement)."""
        files = ["D:/Renders/TEST_S_Shot01_RENDER_v001.exr", "D:/Renders/TEST_S_Shot01_RENDER_v002.exr"]
        self.host._import(files, None, None, [], False)
        
        comp = self.mock_fusion.GetCurrentComp()
        self.assertEqual(len(comp.tools), 2)
        
        tool_names = [t.Name for t in comp.tools.values()]
        self.assertIn("TEST_S_Shot01_RENDER_v001", tool_names)
        self.assertIn("TEST_S_Shot01_RENDER_v002", tool_names)
        
        for t in comp.tools.values():
            self.assertIn(1, t.Clip)
            self.assertTrue(t.Clip[1].startswith("D:/Renders/"))

    def test_import_collision(self):
        """Test that importing nodes with existing names triggers auto-renaming."""
        comp = self.mock_fusion.GetCurrentComp()
        # Create a pre-existing tool
        comp.AddTool("Loader", 0, 0).SetAttrs({"TOOLS_Name": "AssetA"})
        
        mock_item = MagicMock()
        mock_item.shortName.return_value = "AssetA"
        
        files = ["D:/Path/To/AssetA_v001.exr"]
        self.host._import(files, mock_item, None, [], False)
        
        # Should have AssetA (original) and AssetA_1 (new)
        tool_names = [t.Name for t in comp.tools.values()]
        self.assertIn("AssetA", tool_names)
        self.assertIn("AssetA_1", tool_names)

    def test_replace_logic(self):
        """Test replacing the file path of a selected Loader node."""
        comp = self.mock_fusion.GetCurrentComp()
        loader = comp.AddTool("Loader", 0, 0)
        loader.SetAttrs({"TOOLS_Name": "OldLoader"})
        comp.ActiveTool = loader
        
        mock_item = MagicMock()
        mock_item.shortName.return_value = "NewAsset"
        
        success = self.host._replace(["D:/New/Path_v001.exr"], mock_item, None, [], False)
        
        self.assertTrue(success)
        self.assertEqual(loader.Clip[1], "D:/New/Path_v001.exr")
        # Should be renamed since "Loader" was in the name (from AddTool defaults)
        self.assertEqual(loader.Name, "NewAsset")

    def test_save_as_logic(self):
        """Test the _saveAs method."""
        target_path = "D:\\Projects\\Test\\TEST_S_Shot01_COMP_v002.comp"
        success = self.host._saveAs(target_path, None, None, 2, "Test Comment", True)
        self.assertTrue(success)
        self.assertEqual(self.host.currentFilePath(), "D:/Projects/Test/TEST_S_Shot01_COMP_v002.comp")

    def test_metadata_persistence(self):
        """Test if _store_ramses_metadata writes to Comp data."""
        mock_item = MagicMock()
        mock_item.uuid.return_value = "item-uuid-123"
        mock_project = MagicMock()
        mock_project.uuid.return_value = "project-uuid-456"
        mock_item.project.return_value = mock_project
        
        self.host._store_ramses_metadata(mock_item)
        
        comp_data = self.mock_fusion.GetCurrentComp().metadata
        self.assertEqual(comp_data.get("Ramses.ItemUUID"), "item-uuid-123")
        self.assertEqual(comp_data.get("Ramses.ProjectUUID"), "project-uuid-456")

    def test_setup_current_file(self):
        """Test applying project settings (resolution, fps, range) to the comp."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = "S" # Shot
        mock_item.duration.return_value = 10.0
        
        setup_options = {
            "width": 3840,
            "height": 2160,
            "framerate": 25.0,
            "frames": 250,
            "pixelAspectRatio": 1.0
        }
        
        # We need to mock RAM_SETTINGS for the start frame
        import ramses
        ramses.RAM_SETTINGS.userSettings = {"compStartFrame": 1001}
        
        success = self.host._setupCurrentFile(mock_item, None, setup_options)
        self.assertTrue(success)
        
        comp = self.mock_fusion.GetCurrentComp()
        prefs = comp.GetPrefs("Comp.FrameFormat")
        attrs = comp.GetAttrs()
        
        self.assertEqual(prefs["Width"], 3840)
        self.assertEqual(prefs["Rate"], 25.0)
        self.assertEqual(attrs["COMPN_GlobalStart"], 1001.0)
        self.assertEqual(attrs["COMPN_GlobalEnd"], 1250.0) # 1001 + 250 - 1

    def test_preview_logic(self):
        """Test the preview render logic including node discovery and presets."""
        comp = self.mock_fusion.GetCurrentComp()
        preview_node = comp.AddTool("Saver", 0, 0)
        preview_node.SetAttrs({"TOOLS_Name": "_PREVIEW"})
        
        # Mock folder and name
        folder = "D:/Previews"
        basename = "TEST_S_Shot01_COMP"
        
        with MagicMock() as mock_os:
            # We need to ensure the verify check passes
            self.host._verify_render_output = MagicMock(return_value=True)
            
            results = self.host._preview(folder, basename, None, None)
            
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0], "D:/Previews/TEST_S_Shot01_COMP.mov")
            self.assertEqual(preview_node.Clip[1], "D:/Previews/TEST_S_Shot01_COMP.mov")
            # Verify ProRes preset was applied
            self.assertEqual(preview_node.GetInput("QuickTimeMovies.Compression"), "Apple ProRes 422_apcn")

    def test_publish_logic_split(self):
        """Test the 'Split Publish' (Render + Backup)."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.SetAttrs({"COMPS_FileName": "D:/Projects/WIP/TEST_S_Shot01_COMP_v001.comp"})
        
        final_node = comp.AddTool("Saver", 0, 0)
        final_node.SetAttrs({"TOOLS_Name": "_FINAL"})
        final_node.Clip[1] = "D:/Renders/TEST_S_Shot01_COMP.mov"
        
        mock_info = MagicMock()
        # Mock publishFilePath to return a backup path
        self.host.publishFilePath = MagicMock(return_value="D:/Projects/Published/TEST_S_Shot01_COMP.comp")
        self.host._verify_render_output = MagicMock(return_value=True)
        
        published = self.host._publish(mock_info, {})
        
        # Should have 2 files: The render and the comp backup
        self.assertEqual(len(published), 2)
        self.assertIn("D:/Renders/TEST_S_Shot01_COMP.mov", published)
        self.assertIn("D:/Projects/Published/TEST_S_Shot01_COMP.comp", published)

    def test_logging(self):
        """Verifies that the logger outputs to stdout for INFO and above."""
        from io import StringIO
        # Redirect stdout to capture prints
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            # This should be printed (Info level)
            self.host._log("Test Info Message", LogLevel.Info)
            # This should be silenced (Debug level < Info)
            self.host._log("Test Debug Message", LogLevel.Debug)
            
            output = captured_output.getvalue()
            
            # Print to real stdout so user can see it
            sys.__stdout__.write("\n[Captured Output]:\n" + output)

            self.assertIn("[Ramses][INFO] Test Info Message", output)
            self.assertNotIn("Debug", output)
        finally:
            # Restore stdout
            sys.stdout = sys.__stdout__

if __name__ == "__main__":
    unittest.main()
