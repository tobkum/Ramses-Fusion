import sys
import os
import unittest
from unittest.mock import MagicMock, patch

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

# Mock ramses.yaml to satisfy imports in fusion_host
sys.modules["ramses.yaml"] = MagicMock()
sys.modules["yaml"] = MagicMock()
# We need actual yaml behavior for some tests, or at least a working safe_load mock
sys.modules["yaml"].safe_load.side_effect = lambda x: x # Simple pass-through or mock return

# --- 3. Import Code Under Test ---
from fusion_host import FusionHost, FORMAT_QUICKTIME, CODEC_PRORES_422, CODEC_PRORES_422_HQ
from tests.mocks import MockFusion
from ramses import LogLevel

class TestFusionHost(unittest.TestCase):

    def setUp(self):
        self.mock_fusion = MockFusion()
        # Inject global mocks into the module namespace
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        fusion_host.fusionscript = sys.modules["fusionscript"]
        
        # Ensure yaml is mocked inside the module if it was already imported
        fusion_host.yaml = sys.modules["yaml"]
        
        self.host = FusionHost(self.mock_fusion)

    def test_initialization(self):
        """Test if the host initializes and gets version from mock."""
        self.assertEqual(self.host.hostName, "Fusion")
        self.assertEqual(self.host.hostVersion, "18.5 (Mock)")

    def test_normalize_path(self):
        """Verify path normalization (converting backslashes to forward slashes)."""
        path = "C:\\Users\\Test\\File.comp"
        expected = "C:/Users/Test/File.comp"
        self.assertEqual(self.host.normalizePath(path), expected)
        self.assertEqual(self.host.normalizePath(None), "")

    def test_current_file_path(self):
        """Verify retrieval of the current active composition file path."""
        path = self.host.currentFilePath()
        self.assertEqual(path, "D:/Projects/Test/TEST_S_Shot01_COMP_v001.comp")

    def test_sanitize_node_name(self):
        """Verify that Fusion node names are correctly sanitized (alphanumeric only)."""
        self.assertEqual(self.host._sanitizeNodeName("My Node"), "My_Node")
        self.assertEqual(self.host._sanitizeNodeName("123Node"), "R_123Node")
        self.assertEqual(self.host._sanitizeNodeName("Node!@#"), "Node___")

    def test_import_logic(self):
        """Verify Loader node creation and grid placement during batch import."""
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
        """Verify that importing a node with an existing name triggers auto-increment renaming."""
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
        """Verify that replacing a Loader correctly updates the path and renames the node."""
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
        """Verify that '_saveAs' correctly updates the active file path in Fusion."""
        target_path = "D:\\Projects\\Test\\TEST_S_Shot01_COMP_v002.comp"
        success = self.host._saveAs(target_path, None, None, 2, "Test Comment", True)
        self.assertTrue(success)
        self.assertEqual(self.host.currentFilePath(), "D:/Projects/Test/TEST_S_Shot01_COMP_v002.comp")

    def test_metadata_persistence(self):
        """Verify that Ramses Item and Project UUIDs are correctly embedded in Comp metadata."""
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
        """Verify that project settings (Resolution, FPS, Frame Ranges) are applied correctly."""
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
        """Verify '_PREVIEW' anchor discovery and automatic ProRes preset application."""
        comp = self.mock_fusion.GetCurrentComp()
        preview_node = comp.AddTool("Saver", 0, 0)
        preview_node.SetAttrs({"TOOLS_Name": "_PREVIEW"})
        
        # Mock paths
        self.host.previewPath = MagicMock(return_value="D:/Previews")
        self.host.publishFilePath = MagicMock(return_value="D:/Previews/fallback.mov")
        
        # Mock Step Settings to ensure fallback logic runs (empty settings)
        mock_step = MagicMock()
        mock_step.publishSettings.return_value = {} 
        self.host.currentStep = MagicMock(return_value=mock_step)
        
        # Mock publishInfo
        mock_info = MagicMock()
        mock_info.copy.return_value = mock_info
        # Return a name WITHOUT extension, as resolvePreviewPath appends it
        mock_info.fileName.return_value = "TEST_S_Shot01_COMP"
        self.host.publishInfo = MagicMock(return_value=mock_info)
        
        # We need to ensure the verify check passes
        self.host._verify_render_output = MagicMock(return_value=True)
        
        results = self.host._preview("D:/Previews", "TEST_S_Shot01_COMP", None, None)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "D:/Previews/TEST_S_Shot01_COMP.mov")
        self.assertEqual(preview_node.Clip[1], "D:/Previews/TEST_S_Shot01_COMP.mov")
        # Verify ProRes preset was applied
        self.assertEqual(preview_node.GetInput(f"{FORMAT_QUICKTIME}.Compression"), CODEC_PRORES_422)

    def test_publish_logic_split(self):
        """Verify the 'Split Publish' workflow (Master Render + Comp File Backup)."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.SetAttrs({"COMPS_FileName": "D:/Projects/WIP/TEST_S_Shot01_COMP_v001.comp"})
        
        final_node = comp.AddTool("Saver", 0, 0)
        final_node.SetAttrs({"TOOLS_Name": "_FINAL"})
        final_node.Clip[1] = "D:/Renders/TEST_S_Shot01_COMP.mov"
        
        # 1. Setup mock publish info
        expected_dst = "D:/Projects/Published/TEST_S_Shot01_COMP.comp"
        src_path = "D:/Projects/WIP/TEST_S_Shot01_COMP_v001.comp"
        
        mock_info = MagicMock()
        mock_info.copy.return_value = mock_info
        mock_info.filePath.return_value = expected_dst
        
        self.host._verify_render_output = MagicMock(return_value=True)
        
        # Mock os.makedirs to avoid actual folder creation during test
        with patch("os.makedirs") as mock_makedirs, \
             patch("ramses.file_manager.RamFileManager.copy") as mock_copy:
            
            published = self.host._publish(mock_info, {})
        
        # Rigorous Assertions:
        # 1. Ensure directories were explicitly created (since API is now 'dry')
        mock_makedirs.assert_called()
        
        # 2. Ensure the copy command used the correct SRC and DST
        mock_copy.assert_called_once_with(src_path, expected_dst, separateThread=False)
        
        # 3. Ensure both paths are returned in the publish list
        self.assertEqual(len(published), 2)
        self.assertIn("D:/Renders/TEST_S_Shot01_COMP.mov", published)
        self.assertIn(expected_dst, published)

    def test_publish_aborts_on_missing_anchor(self):
        """Verify that publish is aborted if no _FINAL anchor is present."""
        comp = self.mock_fusion.GetCurrentComp()
        # Ensure clean state (no tools)
        comp.tools = {} 
        comp.SetAttrs({"COMPS_FileName": "D:/Projects/WIP/TEST_S_Shot01_COMP_v001.comp"})

        mock_info = MagicMock()
        published = self.host._publish(mock_info, {})

        # Should return empty list (aborted)
        self.assertEqual(published, [])

    def test_publish_aborts_on_render_failure(self):
        """Verify that publish is aborted if the render command fails."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.SetAttrs({"COMPS_FileName": "D:/Projects/WIP/TEST_S_Shot01_COMP_v001.comp"})
        
        final_node = comp.AddTool("Saver", 0, 0)
        final_node.SetAttrs({"TOOLS_Name": "_FINAL"})

        # Mock Render failure
        comp.Render = MagicMock(return_value=False)

        mock_info = MagicMock()
        published = self.host._publish(mock_info, {})

        # Should return empty list (aborted)
        self.assertEqual(published, [])

    def test_publish_aborts_on_invalid_render_file(self):
        """Verify that publish is aborted if the rendered file is invalid (missing/size 0)."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.SetAttrs({"COMPS_FileName": "D:/Projects/WIP/TEST_S_Shot01_COMP_v001.comp"})
        
        final_node = comp.AddTool("Saver", 0, 0)
        final_node.SetAttrs({"TOOLS_Name": "_FINAL"})
        
        # Mock Render success but Verification failure
        comp.Render = MagicMock(return_value=True)
        self.host._verify_render_output = MagicMock(return_value=False)

        mock_info = MagicMock()
        published = self.host._publish(mock_info, {})

        # Should return empty list (aborted)
        self.assertEqual(published, [])

    def test_verify_render_output_sequences(self):
        """Verify that '_verify_render_output' handles image sequences with wildcards."""
        # 1. Test standard sequence (.0000.exr)
        path = "D:/Renders/shot.0000.exr"
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isdir", return_value=True), \
             patch("glob.glob", return_value=["D:/Renders/shot.0001.exr"]), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.getsize", return_value=1024):
            
            self.assertTrue(self.host._verify_render_output(path))

        # 2. Test hash sequence (.####.exr)
        path_hash = "D:/Renders/shot.####.exr"
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isdir", return_value=True), \
             patch("glob.glob", return_value=["D:/Renders/shot.1001.exr"]), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.getsize", return_value=1024):
            
            self.assertTrue(self.host._verify_render_output(path_hash))

        # 3. Test failure (no matches)
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isdir", return_value=True), \
             patch("glob.glob", return_value=[]):
            
            self.assertFalse(self.host._verify_render_output(path))

        # 4. Test failure (files exist but are 0 bytes)
        with patch("os.path.exists", return_value=False), \
             patch("os.path.isdir", return_value=True), \
             patch("glob.glob", return_value=["D:/Renders/shot.0001.exr"]), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.getsize", return_value=0):
            
            self.assertFalse(self.host._verify_render_output(path))

    def test_dry_path_resolution(self):
        """Verify that path resolution doesn't create directories (Dry Resolution)."""
        from ramses import RamFileManager
        path = "D:/NewProject/NewShot/COMP/file.comp"
        
        with patch("os.makedirs") as mock_makedirs:
            # These should NOT call makedirs
            RamFileManager.getVersionFolder(path)
            RamFileManager.getPublishFolder(path)
            
            mock_makedirs.assert_not_called()

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

    def test_defensive_dirtying(self):
        """Verify that metadata and presets only write if values actually changed."""
        mock_item = MagicMock()
        mock_item.uuid.return_value = "fixed-uuid"

        # Setup mock project to return a known UUID
        mock_project = MagicMock()
        mock_project.uuid.return_value = "fixed-project-uuid"
        mock_item.project.return_value = mock_project

        # Avoid Ramses context lookup
        self.host.currentStep = MagicMock(return_value=None)

        comp = self.mock_fusion.GetCurrentComp()
        # Pre-set both metadata values that _store_ramses_metadata might write
        comp.SetData("Ramses.ItemUUID", "fixed-uuid")
        comp.SetData("Ramses.ProjectUUID", "fixed-project-uuid")
        comp.Modified = False # Reset dirty flag

        # 1. Metadata check
        self.host._store_ramses_metadata(mock_item)
        self.assertFalse(comp.Modified, "Comp should not be dirty if metadata is identical")
        
        # 2. Render Preset check
        saver = comp.AddTool("Saver", 0, 0)
        saver.SetInput("OutputFormat", FORMAT_QUICKTIME, 0)
        saver.SetInput(f"{FORMAT_QUICKTIME}.Compression", CODEC_PRORES_422, 0)
        comp.Modified = False # Reset again
        
        self.host.apply_render_preset(saver, "preview")
        self.assertFalse(comp.Modified, "Comp should not be dirty if preset is identical")

    def test_calculate_padding_str(self):
        """Verify dynamic padding calculation based on shot frame range."""
        import ramses
        ramses.RAM_SETTINGS.userSettings = {"compStartFrame": 1001}
        
        # 1. Standard shot (e.g. 100 frames -> ends at 1100 -> 4 digits)
        mock_item = MagicMock()
        self.host.currentItem = MagicMock(return_value=mock_item)
        self.host.collectItemSettings = MagicMock(return_value={"frames": 100})
        self.assertEqual(self.host._calculate_padding_str(), "0000")
        
        # 2. Long shot (e.g. 10000 frames -> ends at 11000 -> 5 digits)
        self.host.collectItemSettings = MagicMock(return_value={"frames": 10000})
        self.assertEqual(self.host._calculate_padding_str(), "00000")

    def test_long_shot_padding(self):
        """Verify that padding scales beyond 4 digits if needed."""
        import ramses
        ramses.RAM_SETTINGS.userSettings = {"compStartFrame": 1001}
        mock_item = MagicMock()
        self.host.currentItem = MagicMock(return_value=mock_item)
        
        # Shot ending at 100,000 (1001 + 98999) -> 6 digits
        self.host.collectItemSettings = MagicMock(return_value={"frames": 99000})
        self.assertEqual(len(self.host._calculate_padding_str()), 6)

    def test_sequence_path_resolution(self):
        """Verify sequence path resolution logic (subfolders and padding)."""
        # Mock Step to return sequence config
        mock_step = MagicMock()
        # Mock _get_fusion_settings to return sequence config for 'final'
        self.host._get_fusion_settings = MagicMock(return_value={
            "final": {"format": "OpenEXRFormat", "image_sequence": True}
        })
        self.host.currentStep = MagicMock(return_value=mock_step)
        
        # Mock Project Export Path
        mock_project = MagicMock()
        mock_project.exportPath.return_value = "D:/Exports"
        import ramses
        ramses.RAMSES.project = MagicMock(return_value=mock_project)
        
        # Mock Item/Padding
        self.host._calculate_padding_str = MagicMock(return_value="0000")
        
        # Mock publishInfo
        mock_info = MagicMock()
        mock_info.copy.return_value = mock_info
        mock_info.fileName.return_value = "Shot01"
        self.host.publishInfo = MagicMock(return_value=mock_info)
        
        path = self.host.resolveFinalPath()
        
        # Should be: ExportDir / BaseName / BaseName.Padding.Ext
        expected = "D:/Exports/Shot01/Shot01.0000.exr"
        self.assertEqual(path, expected)

    def test_resolve_final_path_step_export(self):
        """Verify resolveFinalPath respects 'step' export_dest setting (Dual Export feature)."""
        # Mock Step to return step export config
        mock_step = MagicMock()
        self.host._get_fusion_settings = MagicMock(return_value={
            "final": {"format": "QuickTimeMovies", "export_dest": "step"}
        })
        self.host.currentStep = MagicMock(return_value=mock_step)
        
        # Mock Project (should be ignored when export_dest="step")
        mock_project = MagicMock()
        mock_project.exportPath.return_value = "D:/Exports"  # This should NOT be used
        import ramses
        ramses.RAMSES.project = MagicMock(return_value=mock_project)
        
        # Mock publishFilePath (the versioned _published path)
        self.host.publishFilePath = MagicMock(return_value="D:/Steps/COMP/_published/Shot01_v003.mov")
        
        path = self.host.resolveFinalPath()
        
        # Should use publishFilePath, NOT project.exportPath
        self.assertEqual(path, "D:/Steps/COMP/_published/Shot01_v003.mov")
        # Verify exportPath was NOT called (default project export bypassed)
        mock_project.exportPath.assert_not_called()

    def test_update_status_transaction(self):
        """Verify the updateStatus transaction logic (Save -> Publish -> DB Update)."""
        # Mock Daemon Connection
        self.host.testDaemonConnection = MagicMock(return_value=True)
        self.host.currentItem = MagicMock(return_value=MagicMock())
        
        # Mock Status UI result (using new 'note' key)
        mock_state = MagicMock()
        mock_state.completionRatio.return_value = 100
        self.host._statusUI = MagicMock(return_value={
            "publish": True,
            "note": "Final Render",
            "state": mock_state,
            "completionRatio": 100
        })
        
        # 1. Test Successful Transaction
        self.host.save = MagicMock(return_value=True)
        self.host.publish = MagicMock(return_value=True)
        self.host.currentVersion = MagicMock(return_value=5)
        
        mock_status = MagicMock()
        self.host.currentStatus = MagicMock(return_value=mock_status)
        
        success = self.host.updateStatus()
        
        self.assertTrue(success)
        # Verify synchronized state propagation
        self.host.save.assert_called_with(incremental=True, comment="Final Render", state=mock_state)
        self.host.publish.assert_called_with(False, incrementVersion=False, state=mock_state)
        mock_status.setState.assert_called_with(mock_state)
        mock_status.setVersion.assert_called_with(5)

        # 2. Test Abort on Save Failure
        self.host.save.return_value = False
        success = self.host.updateStatus()
        self.assertFalse(success)
        
        # 3. Test Abort on Publish Failure
        self.host.save.return_value = True
        self.host.publish.return_value = False
        success = self.host.updateStatus()
        self.assertFalse(success)

    def test_current_item_metadata_resolution(self):
        """Verify that currentItem prioritizes metadata UUIDs over file paths."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.SetData("Ramses.ItemUUID", "metadata-uuid-789")
        
        # We need to mock the DAEMON.getData call which RamObject.__init__ (via RamShot) will call
        # if create=False (default) and we provide a UUID.
        # But even better, we can mock currentItem on the super() or just mock the RamItem.fromPath
        
        from ramses import RamShot
        with patch("fusion_host.RamItem.fromPath") as mock_from_path:
            # Setup a real-ish object
            mock_item = MagicMock(spec=RamShot)
            mock_item.uuid.return_value = "metadata-uuid-789"
            
            # We mock the constructor of RamItem/RamShot if we can, 
            # but let's just mock the daemon response for the UUID
            with patch("ramses.daemon_interface.RamDaemonInterface.instance") as mock_inst:
                mock_daemon = mock_inst.return_value
                # Mock getStatus or getData to return something valid
                mock_daemon.getData.return_value = {"name": "TestShot", "shortName": "TS"}
                
                item = self.host.currentItem()
                
                # Should have prioritized the metadata UUID
                self.assertEqual(str(item.uuid()), "metadata-uuid-789")

    def test_is_fusion_step(self):
        """Verify DCC detection logic for Fusion steps."""
        mock_step = MagicMock()
        
        # 1. Test by Application Link
        mock_step.data.return_value = {"applications": ["app-uuid"]}
        with patch("ramses.daemon_interface.RamDaemonInterface.instance") as mock_inst:
            mock_daemon = mock_inst.return_value
            mock_daemon.getData.return_value = {"name": "Blackmagic Fusion"}
            
            # Ensure RAMSES.daemonInterface() returns our mock
            import ramses
            with patch.object(ramses.RAMSES, "daemonInterface", return_value=mock_daemon):
                self.assertTrue(self.host.isFusionStep(mock_step))
            
        # 2. Test by Naming
        mock_step.data.return_value = {}
        mock_step.shortName.return_value = "FUSION_COMP"
        self.assertTrue(self.host.isFusionStep(mock_step))
        
        # 3. Test by YAML settings
        mock_step.shortName.return_value = "Generic"
        mock_step.generalSettings.return_value = {"application": "Fusion"}
        self.assertTrue(self.host.isFusionStep(mock_step))
        
        # 4. Negative test
        mock_step.generalSettings.return_value = {"application": "Maya"}
        mock_step.shortName.return_value = "Modeling"
        self.assertFalse(self.host.isFusionStep(mock_step))

if __name__ == "__main__":
    unittest.main()
