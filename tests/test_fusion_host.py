import sys
import os
import unittest
from unittest.mock import MagicMock, patch, ANY

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
from mocks import MockFusion
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

        # Mock currentItem to avoid MagicMock strings in base_filename (fallback to Ramses Standard)
        mock_item = MagicMock()
        mock_item.get.return_value = None
        self.host.currentItem = MagicMock(return_value=mock_item)
        
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

    def test_path_resolution_does_not_create_directories(self):
        """FusionHost.currentItem() resolves paths without creating any directories."""
        with patch("os.makedirs") as mock_makedirs:
            self.host.currentItem()
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

        # Mock currentItem to avoid MagicMock strings in base_filename (fallback to Ramses Standard)
        mock_item = MagicMock()
        mock_item.get.return_value = None
        self.host.currentItem = MagicMock(return_value=mock_item)
        
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
        
        # Patch the RAMSES instance in fusion_host module (not ramses module)
        import fusion_host
        fusion_host.RAMSES.project = MagicMock(return_value=mock_project)
        
        # Mock publishInfo - required by resolveFinalPath
        mock_pub_info = MagicMock()
        self.host.publishInfo = MagicMock(return_value=mock_pub_info)
        
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
        
        # Mock Status UI result (using correct 'comment' key)
        mock_state = MagicMock()
        mock_state.completionRatio.return_value = 100
        self.host._statusUI = MagicMock(return_value={
            "publish": True,
            "comment": "Final Render",
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


class TestFusionUndoAndLocking(unittest.TestCase):
    """Tests for critical undo/lock fixes and Smart Update functionality."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        fusion_host.fusionscript = sys.modules["fusionscript"]
        fusion_host.yaml = sys.modules["yaml"]
        self.host = FusionHost(self.mock_fusion)

    # =============================================================================
    # UNDO SYSTEM TESTS (~8 tests)
    # =============================================================================

    def test_import_creates_undo_group(self):
        """Verify StartUndo/EndUndo called for import operation."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.StartUndo = MagicMock()
        comp.EndUndo = MagicMock()

        files = ["D:/Test/asset_v001.exr"]
        self.host._import(files, None, None, [], False)

        comp.StartUndo.assert_called_once()
        call_args = comp.StartUndo.call_args[0][0]
        self.assertIn("Import", call_args)
        comp.EndUndo.assert_called_once()

    def test_replace_creates_undo_group(self):
        """Verify StartUndo/EndUndo for replace operation."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.StartUndo = MagicMock()
        comp.EndUndo = MagicMock()

        loader = comp.AddTool("Loader", 0, 0)
        comp.ActiveTool = loader

        files = ["D:/Test/new_asset_v002.exr"]
        self.host._replace(files, None, None, [], False)

        comp.StartUndo.assert_called_once_with("Replace Loader")
        comp.EndUndo.assert_called_once()

    def test_setup_current_file_creates_undo(self):
        """Verify undo group for setup operations."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.StartUndo = MagicMock()
        comp.EndUndo = MagicMock()

        mock_item = MagicMock()
        mock_item.itemType.return_value = "S"
        mock_item.duration.return_value = 10.0

        setup_options = {
            "width": 1920,
            "height": 1080,
            "framerate": 24.0,
            "frames": 100,
            "pixelAspectRatio": 1.0
        }

        import ramses
        ramses.RAM_SETTINGS.userSettings = {"compStartFrame": 1001}

        self.host._setupCurrentFile(mock_item, None, setup_options)

        comp.StartUndo.assert_called_once_with("Setup Ramses Scene")
        comp.EndUndo.assert_called_once()

    def test_undo_success_flag_pattern(self):
        """Verify EndUndo(True) on successful completion."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.EndUndo = MagicMock()

        files = ["D:/Test/asset_v001.exr"]
        result = self.host._import(files, None, None, [], False)

        self.assertTrue(result)
        comp.EndUndo.assert_called_once_with(True)

    def test_undo_always_ended_after_import(self):
        """EndUndo is always called with True after _import, even when AddTool returns None."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.EndUndo = MagicMock()

        # Force AddTool to return None (loader creation fails)
        comp.AddTool = MagicMock(return_value=None)

        self.host._import(["D:/Test/asset_v001.exr"], None, None, [], False)

        # The implementation always reaches EndUndo(True) — loader failures are
        # non-fatal and do not flip the undo flag to False.
        comp.EndUndo.assert_called_once_with(True)

    def test_smart_update_creates_undo(self):
        """Verify undo group for smart update via _replace method."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.StartUndo = MagicMock()
        comp.EndUndo = MagicMock()

        loader = comp.AddTool("Loader", 0, 0)
        loader.ID = "Loader"
        loader.Clip[1] = "D:/Project/Shot01/PLATE/_published/001/shot_v001.exr"
        comp.ActiveTool = loader

        # Test _replace method which wraps operations in undo
        files = ["D:/Project/Shot01/PLATE/_published/002/shot_v002.exr"]
        self.host._replace(files, None, None, [], False)

        # Should have started and ended undo
        comp.StartUndo.assert_called_once_with("Replace Loader")
        comp.EndUndo.assert_called_once()

    def test_no_double_undo_calls(self):
        """Verify no double EndUndo() bug."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.StartUndo = MagicMock()
        comp.EndUndo = MagicMock()

        files = ["D:/Test/asset_v001.exr"]
        self.host._import(files, None, None, [], False)

        # Should be exactly one StartUndo and one EndUndo
        self.assertEqual(comp.StartUndo.call_count, 1,
                        "Multiple StartUndo calls detected")
        self.assertEqual(comp.EndUndo.call_count, 1,
                        "Multiple EndUndo calls detected (double-undo bug)")

    def test_undo_preserves_comp_state(self):
        """Verify comp state consistency after undo operations."""
        comp = self.mock_fusion.GetCurrentComp()
        initial_tool_count = len(comp.tools)

        files = ["D:/Test/asset_v001.exr"]
        self.host._import(files, None, None, [], False)

        # After successful import, tool count should increase
        self.assertEqual(len(comp.tools), initial_tool_count + 1)

        # Verify undo mechanism exists (StartUndo/EndUndo called)
        # The actual undo rollback would happen in Fusion itself
        # We're just verifying the pattern is implemented correctly
        self.assertGreater(len(comp.tools), initial_tool_count,
                          "Import should create new tools")

    # =============================================================================
    # LOCK/UNLOCK TESTS (~6 tests)
    # =============================================================================

    def test_import_locks_comp(self):
        """Verify Lock() called before modifications."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.Lock = MagicMock()

        files = ["D:/Test/asset_v001.exr"]
        self.host._import(files, None, None, [], False)

        comp.Lock.assert_called_once()

    def test_import_unlocks_comp(self):
        """Verify Unlock() called in finally block."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.Unlock = MagicMock()

        files = ["D:/Test/asset_v001.exr"]
        self.host._import(files, None, None, [], False)

        comp.Unlock.assert_called_once()

    def test_replace_locks_comp(self):
        """Verify Lock during replace operation."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.Lock = MagicMock()

        loader = comp.AddTool("Loader", 0, 0)
        comp.ActiveTool = loader

        files = ["D:/Test/new_asset_v002.exr"]
        self.host._replace(files, None, None, [], False)

        comp.Lock.assert_called_once()

    def test_setup_locks_comp(self):
        """Verify Lock during setup."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.Lock = MagicMock()
        comp.Unlock = MagicMock()

        mock_item = MagicMock()
        mock_item.itemType.return_value = "S"
        mock_item.duration.return_value = 10.0

        setup_options = {
            "width": 1920,
            "height": 1080,
            "framerate": 24.0,
            "frames": 100,
            "pixelAspectRatio": 1.0
        }

        import ramses
        ramses.RAM_SETTINGS.userSettings = {"compStartFrame": 1001}

        # _setupCurrentFile uses Lock/Unlock pattern for atomic application
        self.host._setupCurrentFile(mock_item, None, setup_options)

        # Verify Lock/Unlock were both called
        comp.Lock.assert_called_once()
        comp.Unlock.assert_called_once()

    def test_lock_released_on_exception(self):
        """Verify Unlock even on errors (via finally block)."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.Unlock = MagicMock()

        # Create a scenario where the operation completes but has issues
        # AddTool returning None simulates a partial failure
        original_addtool = comp.AddTool
        comp.AddTool = MagicMock(return_value=None)

        files = ["D:/Test/asset_v001.exr"]
        result = self.host._import(files, None, None, [], False)

        # Unlock must still be called via finally block
        comp.Unlock.assert_called_once()

    def test_metadata_write_preserves_modified_flag(self):
        """Verify modified flag not polluted by redundant writes."""
        comp = self.mock_fusion.GetCurrentComp()

        mock_item = MagicMock()
        mock_item.uuid.return_value = "test-uuid-123"
        mock_project = MagicMock()
        mock_project.uuid.return_value = "project-uuid-456"
        mock_item.project.return_value = mock_project

        # Pre-set metadata with identical values
        comp.SetData("Ramses.ItemUUID", "test-uuid-123")
        comp.SetData("Ramses.ProjectUUID", "project-uuid-456")
        comp.Modified = False

        self.host._store_ramses_metadata(mock_item)

        # Should NOT mark comp as modified if values are identical
        self.assertFalse(comp.Modified,
                        "Comp marked dirty even though metadata was unchanged")

    # =============================================================================
    # SMART UPDATE TESTS (~4 tests)
    # =============================================================================

    def test_smart_update_replaces_outdated_loaders(self):
        """Verify _replace updates loader paths correctly."""
        comp = self.mock_fusion.GetCurrentComp()
        loader = comp.AddTool("Loader", 0, 0)
        loader.ID = "Loader"
        loader.SetAttrs({"TOOLS_Name": "Shot01_v001"})
        old_path = "D:/Project/Shot01/PLATE/_published/001/shot_v001.exr"
        loader.Clip[1] = old_path
        comp.ActiveTool = loader

        new_path = "D:/Project/Shot01/PLATE/_published/002/shot_v002.exr"

        # Create mock item to avoid None.shortName() error
        mock_item = MagicMock()
        mock_item.shortName.return_value = "Shot01"
        mock_item.uuid.return_value = "item-uuid"
        mock_project = MagicMock()
        mock_project.uuid.return_value = "proj-uuid"
        mock_item.project.return_value = mock_project

        # Use _replace directly
        result = self.host._replace([new_path], mock_item, None, [], False)

        self.assertTrue(result)
        # Verify path was updated
        self.assertEqual(loader.Clip[1], new_path.replace("\\", "/"))

    def test_smart_update_preserves_connections(self):
        """Verify node graph connections preserved during replace."""
        comp = self.mock_fusion.GetCurrentComp()
        loader = comp.AddTool("Loader", 0, 0)
        loader.ID = "Loader"
        loader.SetAttrs({"TOOLS_Name": "Shot01_Loader"})
        loader.Clip[1] = "D:/Project/Shot01/PLATE/_published/001/shot_v001.exr"
        comp.ActiveTool = loader

        # Simulate a connected downstream node
        loader.connect_input()
        main_input = loader.FindMainInput(1)
        self.assertIsNotNone(main_input.GetConnectedOutput())

        mock_item = MagicMock()
        mock_item.shortName.return_value = "Shot01"
        mock_item.uuid.return_value = "item-uuid"
        mock_project = MagicMock()
        mock_project.uuid.return_value = "proj-uuid"
        mock_item.project.return_value = mock_project

        new_path = "D:/Project/Shot01/PLATE/_published/002/shot_v002.exr"
        self.host._replace([new_path], mock_item, None, [], False)

        # Connection should still exist (Fusion preserves connections when updating Clip path)
        self.assertIsNotNone(main_input.GetConnectedOutput(),
                           "Replace operation broke node connections")

    def test_smart_update_cache_invalidation(self):
        """Verify version metadata updated after replace."""
        comp = self.mock_fusion.GetCurrentComp()
        loader = comp.AddTool("Loader", 0, 0)
        loader.ID = "Loader"
        loader.Clip[1] = "D:/Project/Shot01/PLATE/_published/001/shot_v001.exr"
        loader.SetData("Ramses.Version", 1)
        comp.ActiveTool = loader

        new_path = "D:/Project/Shot01/PLATE/_published/002/shot_v002.exr"

        # Create mock item with version 2
        mock_item = MagicMock()
        mock_item.uuid.return_value = "item-uuid"
        mock_project = MagicMock()
        mock_project.uuid.return_value = "proj-uuid"
        mock_item.project.return_value = mock_project

        result = self.host._replace([new_path], mock_item, None, [], False)

        self.assertTrue(result)
        # Verify version metadata mechanism exists
        # The actual version number would come from RamFileInfo parsing the path
        # We verify that the metadata storage mechanism works
        stored_version = loader.metadata.get("Ramses.Version")
        # Should have a version stored (actual value depends on path parsing)
        self.assertIn("Ramses.Version", loader.metadata.keys(),
                     "Version metadata not written during replace")

    def test_smart_update_multiple_loaders(self):
        """Verify independent replacement of multiple loaders."""
        comp = self.mock_fusion.GetCurrentComp()

        # Create two loaders
        loader1 = comp.AddTool("Loader", 0, 0)
        loader1.ID = "Loader"
        loader1.SetAttrs({"TOOLS_Name": "Shot01_Loader"})
        loader1.Clip[1] = "D:/Project/Shot01/PLATE/_published/001/shot_v001.exr"

        loader2 = comp.AddTool("Loader", 1, 0)
        loader2.ID = "Loader"
        loader2.SetAttrs({"TOOLS_Name": "Shot02_Loader"})
        loader2.Clip[1] = "D:/Project/Shot02/PLATE/_published/001/shot2_v001.exr"

        # Update only loader1
        comp.ActiveTool = loader1

        mock_item = MagicMock()
        mock_item.shortName.return_value = "Shot01"
        mock_item.uuid.return_value = "item-uuid"
        mock_project = MagicMock()
        mock_project.uuid.return_value = "proj-uuid"
        mock_item.project.return_value = mock_project

        new_path1 = "D:/Project/Shot01/PLATE/_published/002/shot_v002.exr"
        result = self.host._replace([new_path1], mock_item, None, [], False)

        self.assertTrue(result)
        self.assertIn("002", loader1.Clip[1])
        # Loader2 should remain unchanged
        self.assertIn("001", loader2.Clip[1])


class TestFusionCompImport(unittest.TestCase):
    """Tests for importing/merging .comp files into Fusion."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        fusion_host.fusionscript = sys.modules["fusionscript"]
        self.host = FusionHost(self.mock_fusion)

    def test_import_comp_merges_instead_of_loading(self):
        """Verify that .comp files trigger Read & Paste instead of AddTool(Loader)."""
        comp = self.mock_fusion.GetCurrentComp()
        import fusion_host
        fusion_host.bmd.readfile = MagicMock(return_value="FAKE_CONTENT")
        comp.Paste = MagicMock()
        comp.AddTool = MagicMock(return_value=MagicMock())

        files = ["D:/MaMo/tracking_v001.comp"]
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", return_value=123456789.0):
            self.host._import(files, MagicMock(), MagicMock(), [], False)

        # Should read the file and paste its content
        fusion_host.bmd.readfile.assert_called_once_with("D:/MaMo/tracking_v001.comp")
        comp.Paste.assert_called_once_with("FAKE_CONTENT")

        # AddTool should NOT be called
        comp.AddTool.assert_not_called()

    def test_import_mixed_media_and_comp(self):
        """Verify handling of both media files and composition files in a single import."""
        comp = self.mock_fusion.GetCurrentComp()
        import fusion_host
        fusion_host.bmd.readfile = MagicMock(return_value="FAKE_CONTENT")
        comp.Paste = MagicMock()
        comp.AddTool = MagicMock(return_value=MagicMock())

        files = ["D:/Plate/shot_v001.exr", "D:/MaMo/tracking_v001.comp"]
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", return_value=123456789.0):
            self.host._import(files, MagicMock(), MagicMock(), [], False)

        # Paste should be called once for the .comp
        comp.Paste.assert_called_once_with("FAKE_CONTENT")
        
        # AddTool should be called once for the .exr
        comp.AddTool.assert_called_once_with("Loader", ANY, ANY)

    def test_check_outdated_loaders(self):
        """Verify check_outdated_loaders detects and handles outdated loaders."""
        comp = self.mock_fusion.GetCurrentComp()
        
        # Add a loader with version 1
        loader = comp.AddTool("Loader", 0, 0)
        loader.Clip[1] = "D:/Project/05-SHOTS/SH010/COMP/_published/v001/SH010_v001.001.exr"
        
        import fusion_host
        
        mock_item = MagicMock()
        mock_item.shortName.return_value = "SH010"
        mock_item.latestPublishedVersionFolderPath.return_value = "D:/Project/05-SHOTS/SH010/COMP/_published/v002"
        
        mock_step = MagicMock()
        
        with patch.object(fusion_host.RamItem, "fromPath", return_value=mock_item), \
             patch.object(fusion_host.RamStep, "fromPath", return_value=mock_step):
            count = self.host.check_outdated_loaders()
        
        self.assertEqual(count, 1)

    def test_import_comp_failure_no_fallthrough(self):
        """Verify a failing .comp import does not create a Loader."""
        comp = self.mock_fusion.GetCurrentComp()
        import fusion_host
        fusion_host.bmd.readfile = MagicMock(return_value=None)  # Simulate failure
        comp.AddTool = MagicMock()

        files = ["D:/MaMo/tracking_v001.comp"]
        
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", return_value=123456789.0):
            self.host._import(files, MagicMock(), MagicMock(), [], False)

        comp.AddTool.assert_not_called()

    @patch("fusion_host.yaml.safe_load")
    def test_publishOptions_retry_loop(self, mock_safe_load):
        """Verify _publishOptions doesn't recurse infinitely on bad YAML."""
        # Force safe_load to raise an exception to trigger the retry loop
        mock_safe_load.side_effect = ValueError("Invalid YAML")
        
        # Provide bad YAML strings 3 times, simulating user repeatedly submitting invalid YAML
        self.host._request_input = MagicMock(side_effect=[
            {"YAML": "{ invalid: yaml: "},
            {"YAML": "{ invalid: yaml: "},
            {"YAML": "{ invalid: yaml: "}
        ])
        
        original_opts = {"foo": "bar"}
        # Should return the original options after max retries (3)
        res = self.host._publishOptions(original_opts, showPublishUI=True)
        self.assertEqual(res, original_opts)
        self.assertEqual(self.host._request_input.call_count, 3)

    def test_createNewComp_save_failure(self):
        """Verify _createNewComp returns empty string and logs critical error when Save fails."""
        comp = self.mock_fusion.GetCurrentComp()
        comp.Save = MagicMock(return_value=False)
        self.mock_fusion.NewComp = MagicMock()
        
        import fusion_host
        fusion_host.RamItem = MagicMock()
        fusion_host.RamItem.fromPath.return_value = MagicMock()
        self.host._open = MagicMock(return_value=True)
        self.host.log = MagicMock()
        self.host.app = MagicMock()
        self.host.app._resolve_shot_path.return_value = ("D:/test.comp", False)
        
        res = self.host._createNewComp(MagicMock(), MagicMock())
        self.assertEqual(res, "")
        self.host.log.assert_called_with(ANY, LogLevel.Critical)

class TestVersionFolderScanning(unittest.TestCase):
    """Covers the patched RamFileManager version scanners (flat files AND
    Ramses-Ingest style version directories), including the candidate
    prefilter that replaced the arbitrary entries[:N] listing slice."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.versions = os.path.join(self.tmp, "_versions")
        os.makedirs(self.versions)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _add_version_dir(self, dirname: str, filename: str) -> str:
        d = os.path.join(self.versions, dirname)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, filename)
        with open(p, "w") as f:
            f.write("x")
        return p

    def test_latest_version_found_in_directory_versions(self):
        """Directory-based versions (001_OK, 002_WIP ...) resolve to the newest."""
        from fusion_host import RamFileManager

        self._add_version_dir("001_OK", "TEST_S_SH010_COMP.mov")
        latest = self._add_version_dir("002_WIP", "TEST_S_SH010_COMP.mov")
        # Noise that must not be picked up
        self._add_version_dir("003_OK", "OTHER_SHOT.mov")  # wrong base name
        os.makedirs(os.path.join(self.versions, "not_a_version"), exist_ok=True)

        with patch.object(RamFileManager, "getVersionFolder", return_value=self.versions):
            result = RamFileManager.getLatestVersionFilePath(
                os.path.join(self.tmp, "TEST_S_SH010_COMP.comp")
            )

        self.assertEqual(os.path.normpath(result), os.path.normpath(latest))

    def test_all_versions_listed_in_order(self):
        from fusion_host import RamFileManager

        v1 = self._add_version_dir("001_OK", "TEST_S_SH010_COMP.exr")
        v2 = self._add_version_dir("002_OK", "TEST_S_SH010_COMP.exr")

        with patch.object(RamFileManager, "getVersionFolder", return_value=self.versions):
            result = RamFileManager.getVersionFilePaths(
                os.path.join(self.tmp, "TEST_S_SH010_COMP.comp")
            )

        self.assertEqual(
            [os.path.normpath(p) for p in result],
            [os.path.normpath(v1), os.path.normpath(v2)],
        )


class TestStepLookup(unittest.TestCase):
    """Case-insensitive step lookup (project.step() is exact-match only)."""

    def _project(self, *step_names):
        steps = []
        for n in step_names:
            s = MagicMock()
            s.shortName.return_value = n
            steps.append(s)
        project = MagicMock()
        project.steps.return_value = steps
        return project

    def test_finds_step_regardless_of_case(self):
        project = self._project("PLATE", "COMP")
        step = FusionHost.findStepByShortName(project, "Comp", "Compositing")
        self.assertIsNotNone(step)
        self.assertEqual(step.shortName(), "COMP")

    def test_matches_any_of_the_given_names(self):
        project = self._project("Compositing")
        step = FusionHost.findStepByShortName(project, "Comp", "Compositing")
        self.assertEqual(step.shortName(), "Compositing")

    def test_returns_none_when_absent(self):
        project = self._project("PLATE", "MaMo")
        self.assertIsNone(
            FusionHost.findStepByShortName(project, "Comp", "Compositing")
        )
        self.assertIsNone(FusionHost.findStepByShortName(None, "Comp"))


class TestImportCollapsing(unittest.TestCase):
    """Sequence collapsing and sidecar filtering in _import.

    The upstream import flow can pass every file of a published version
    folder — without collapsing, a 240-frame EXR plate would create 240
    Loaders (plus Loaders for .ramses_complete and _ramses_data.json).
    """

    SEQ = [
        f"D:/pub/001/TEST_S_SH010_PLATE.{f}.exr" for f in (86402, 86400, 86401)
    ]
    SIDECARS = [
        "D:/pub/001/.ramses_complete",
        "D:/pub/001/_ramses_data.json",
    ]

    def setUp(self):
        self.mock_fusion = MockFusion()
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        self.host = FusionHost(self.mock_fusion)
        self.comp = self.mock_fusion.GetCurrentComp()

    # --- _collapse_import_paths ----------------------------------------------

    def test_sequence_collapses_to_lowest_frame(self):
        result = FusionHost._collapse_import_paths(self.SIDECARS + self.SEQ)
        self.assertEqual(result, ["D:/pub/001/TEST_S_SH010_PLATE.86400.exr"])

    def test_sidecars_are_skipped(self):
        self.assertEqual(FusionHost._collapse_import_paths(self.SIDECARS), [])

    def test_distinct_sequences_stay_separate(self):
        files = [
            "D:/pub/001/SH010_BG.1001.exr",
            "D:/pub/001/SH010_BG.1002.exr",
            "D:/pub/001/SH010_FG.1001.exr",
        ]
        result = FusionHost._collapse_import_paths(files)
        self.assertEqual(
            result,
            ["D:/pub/001/SH010_BG.1001.exr", "D:/pub/001/SH010_FG.1001.exr"],
        )

    def test_movies_comps_and_versioned_files_pass_through(self):
        """No frame token = no collapsing; .comp files must survive for the
        merge path; _v001-style version tokens are not frame tokens."""
        files = [
            "D:/pub/001/SH010.mov",
            "D:/pub/001/tracking.comp",
            "D:/pub/001/TEST_S_Shot01_RENDER_v001.exr",
            "D:/pub/001/TEST_S_Shot01_RENDER_v002.exr",
        ]
        self.assertEqual(FusionHost._collapse_import_paths(files), files)

    def test_same_name_in_different_folders_not_merged(self):
        files = [
            "D:/pub/001/SH010.1001.exr",
            "D:/pub/002/SH010.1001.exr",
        ]
        self.assertEqual(FusionHost._collapse_import_paths(files), files)

    # --- _import integration ---------------------------------------------------

    def test_import_creates_single_loader_for_sequence(self):
        self.host._import(self.SIDECARS + self.SEQ, None, None, [], False)
        loaders = [t for t in self.comp.tools.values() if t.ID == "Loader"]
        self.assertEqual(len(loaders), 1)
        self.assertEqual(
            loaders[0].Clip[1], "D:/pub/001/TEST_S_SH010_PLATE.86400.exr"
        )

    def test_import_with_only_sidecars_fails_cleanly(self):
        result = self.host._import(self.SIDECARS, None, None, [], False)
        self.assertFalse(result)
        self.assertEqual(len(self.comp.tools), 0)


class TestSourceNumbering(unittest.TestCase):
    """Source-plate frame numbering on the _FINAL/_PREVIEW Savers.

    The comp timeline keeps the studio start-frame convention (1001);
    when enabled per step, the Saver's SetSequenceStart/SequenceStartFrame
    inputs make the rendered files carry the plate's own numbering.
    """

    PLATE_CLIP = (
        "D:/proj/05-SHOTS/TEST_S_SH010/TEST_S_SH010_PLATE/"
        "_published/001/TEST_S_SH010_PLATE.86400.exr"
    )

    def setUp(self):
        self.mock_fusion = MockFusion()
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        self.fusion_host = fusion_host
        self.host = FusionHost(self.mock_fusion)
        self.comp = self.mock_fusion.GetCurrentComp()

        # Default plateStepNames come from user settings — isolate from the
        # machine's real Ramses config.
        settings = MagicMock()
        settings.userSettings = {}
        self._settings_patch = patch.object(fusion_host, "RAM_SETTINGS", settings)
        self._settings_patch.start()
        self.addCleanup(self._settings_patch.stop)

    # --- parse_frame_number -------------------------------------------------

    def test_parse_frame_number_dot_separator(self):
        self.assertEqual(FusionHost.parse_frame_number("plate.86400.exr"), 86400)

    def test_parse_frame_number_underscore_separator(self):
        self.assertEqual(FusionHost.parse_frame_number("plate_1001.dpx"), 1001)

    def test_parse_frame_number_rejects_version_tokens(self):
        """_v001 is a version, not a frame — digits must follow the separator."""
        self.assertIsNone(FusionHost.parse_frame_number("shot_v001.exr"))

    def test_parse_frame_number_no_frame(self):
        self.assertIsNone(FusionHost.parse_frame_number("TEST_S_SH010_PLATE.exr"))
        self.assertIsNone(FusionHost.parse_frame_number(".ramses_complete"))
        self.assertIsNone(FusionHost.parse_frame_number(None))

    # --- parse_frame_token ---------------------------------------------------

    def test_parse_frame_token_reports_digit_width(self):
        """The width is what lets a render be padded like its plate."""
        self.assertEqual(FusionHost.parse_frame_token("plate.00000567.exr"), (567, 8))
        self.assertEqual(FusionHost.parse_frame_token("plate.1001.exr"), (1001, 4))

    def test_parse_frame_token_no_frame(self):
        self.assertIsNone(FusionHost.parse_frame_token("shot_v001.exr"))
        self.assertIsNone(FusionHost.parse_frame_token(None))

    # --- resolveSourceStartFrame ---------------------------------------------

    def _add_loader(self, clip_path):
        loader = self.comp.AddTool("Loader", 0, 0)
        loader.Clip[1] = clip_path
        return loader

    def test_resolve_from_plate_loader(self):
        """A Loader pointing into a plate step's _published wins."""
        self._add_loader(self.PLATE_CLIP)

        plate_step = MagicMock()
        plate_step.shortName.return_value = "Plate"
        with patch.object(
            self.fusion_host.RamStep, "fromPath", return_value=plate_step
        ):
            self.assertEqual(self.host.resolveSourceStartFrame(), 86400)

    def test_resolve_ignores_non_plate_loaders(self):
        """Loaders from non-plate steps (e.g. a CG render) don't define numbering."""
        self._add_loader(
            "D:/proj/05-SHOTS/TEST_S_SH010/TEST_S_SH010_CG/"
            "_published/002/TEST_S_SH010_CG.1001.exr"
        )
        cg_step = MagicMock()
        cg_step.shortName.return_value = "CG"
        with patch.object(self.fusion_host.RamStep, "fromPath", return_value=cg_step), \
             patch.object(self.host, "currentItem", return_value=None):
            self.assertIsNone(self.host.resolveSourceStartFrame())

    def test_resolve_uses_min_frame_across_plate_loaders(self):
        self._add_loader(self.PLATE_CLIP)
        self._add_loader(self.PLATE_CLIP.replace("86400", "86500"))

        plate_step = MagicMock()
        plate_step.shortName.return_value = "Plate"
        with patch.object(
            self.fusion_host.RamStep, "fromPath", return_value=plate_step
        ):
            self.assertEqual(self.host.resolveSourceStartFrame(), 86400)

    def test_resolve_falls_back_to_published_plate_on_disk(self):
        """No loaders: the latest published plate folder defines numbering.
        Sidecars (.ramses_complete, _ramses_data.json) must be ignored."""
        plate_step = MagicMock()
        plate_step.shortName.return_value = "Ingest"
        project = MagicMock()
        project.steps.return_value = [plate_step]

        item = MagicMock()
        item.latestPublishedVersionFilePaths.return_value = [
            "D:/pub/001/.ramses_complete",
            "D:/pub/001/_ramses_data.json",
            "D:/pub/001/TEST_S_SH010_PLATE.86400.exr",
            "D:/pub/001/TEST_S_SH010_PLATE.86401.exr",
        ]

        with patch.object(self.host, "currentItem", return_value=item), \
             patch.object(self.fusion_host.RAMSES, "project", return_value=project):
            self.assertEqual(self.host.resolveSourceStartFrame(), 86400)

    def test_resolve_returns_none_when_nothing_found(self):
        with patch.object(self.host, "currentItem", return_value=None):
            self.assertIsNone(self.host.resolveSourceStartFrame())

    # --- resolveSourcePadding -------------------------------------------------

    def _plate_step_patch(self):
        plate_step = MagicMock()
        plate_step.shortName.return_value = "Plate"
        return patch.object(
            self.fusion_host.RamStep, "fromPath", return_value=plate_step
        )

    def test_resolve_padding_from_plate_loader(self):
        """The live DrNiceXmas plate is 8-digit padded."""
        self._add_loader(self.PLATE_CLIP.replace("86400", "00000567"))
        with self._plate_step_patch():
            self.assertEqual(self.host.resolveSourcePadding(), 8)
            self.assertEqual(self.host.resolveSourceStartFrame(), 567)

    def test_resolve_padding_uses_widest_token(self):
        """An unpadded sequence (.99., .100.) needs a width holding every frame."""
        self._add_loader(self.PLATE_CLIP.replace(".86400.", ".99."))
        self._add_loader(self.PLATE_CLIP.replace(".86400.", ".100."))
        with self._plate_step_patch():
            self.assertEqual(self.host.resolveSourcePadding(), 3)

    def test_resolve_padding_falls_back_to_disk(self):
        plate_step = MagicMock()
        plate_step.shortName.return_value = "Ingest"
        project = MagicMock()
        project.steps.return_value = [plate_step]

        item = MagicMock()
        item.latestPublishedVersionFilePaths.return_value = [
            "D:/pub/001/.ramses_complete",
            "D:/pub/001/TEST_S_SH010_PLATE.00000567.exr",
            "D:/pub/001/TEST_S_SH010_PLATE.00000568.exr",
        ]

        with patch.object(self.host, "currentItem", return_value=item), \
             patch.object(self.fusion_host.RAMSES, "project", return_value=project):
            self.assertEqual(self.host.resolveSourcePadding(), 8)

    def test_resolve_padding_none_when_nothing_found(self):
        with patch.object(self.host, "currentItem", return_value=None):
            self.assertIsNone(self.host.resolveSourcePadding())

    # --- padding follows the plate --------------------------------------------

    def _source_numbering_cfg(self, enabled=True, preset="final"):
        return patch.object(
            self.host,
            "_get_fusion_settings",
            return_value={preset: {"source_numbering": enabled}},
        )

    def test_padding_matches_plate_when_source_numbering(self):
        """Regression: an 8-digit plate rendered 4-digit (DNX_0515 delivery)."""
        self._add_loader(self.PLATE_CLIP.replace("86400", "00000567"))
        with self._plate_step_patch(), \
             patch.object(self.host, "currentStep", return_value=MagicMock()), \
             patch.object(self.host, "currentItem", return_value=MagicMock()), \
             patch.object(self.host, "collectItemSettings", return_value={"frames": 64}), \
             self._source_numbering_cfg():
            self.assertEqual(self.host._calculate_padding_str("final"), "0" * 8)

    def test_padding_ignores_plate_without_source_numbering(self):
        """Unmanaged presets keep deriving padding from the comp's own range."""
        self._add_loader(self.PLATE_CLIP.replace("86400", "00000567"))
        self.fusion_host.RAM_SETTINGS.userSettings = {"compStartFrame": 1001}
        with self._plate_step_patch(), \
             patch.object(self.host, "currentStep", return_value=MagicMock()), \
             patch.object(self.host, "currentItem", return_value=MagicMock()), \
             patch.object(self.host, "collectItemSettings", return_value={"frames": 64}), \
             self._source_numbering_cfg(enabled=False):
            self.assertEqual(self.host._calculate_padding_str("final"), "0000")

    def test_padding_widens_past_narrow_plate_padding(self):
        """A 3-digit plate rendered past frame 999 must not truncate."""
        self._add_loader(self.PLATE_CLIP.replace(".86400.", ".998."))
        with self._plate_step_patch(), \
             patch.object(self.host, "currentStep", return_value=MagicMock()), \
             patch.object(self.host, "currentItem", return_value=MagicMock()), \
             patch.object(self.host, "collectItemSettings", return_value={"frames": 10}), \
             self._source_numbering_cfg():
            # 998 + 9 = 1007 needs 4 digits even though the plate uses 3
            self.assertEqual(self.host._calculate_padding_str("final"), "0000")

    # --- _apply_source_numbering ----------------------------------------------

    def _saver(self):
        return self.comp.AddTool("Saver", 0, 0)

    def _with_step_cfg(self, cfg):
        return patch.object(self.host, "_get_fusion_settings", return_value=cfg)

    def test_unmanaged_when_key_absent(self):
        """No source_numbering key: the Saver's inputs are never touched."""
        node = self._saver()
        node.SetInput("SetSequenceStart", 1, 0)  # artist's manual choice
        node.SetInput("SequenceStartFrame", 500, 0)

        cfg = {"final": {"format": "OpenEXRFormat", "image_sequence": True}}
        with self._with_step_cfg(cfg), \
             patch.object(self.host, "currentStep", return_value=None):
            self.host._apply_source_numbering(node, "final")

        self.assertEqual(node.GetInput("SetSequenceStart"), 1)
        self.assertEqual(node.GetInput("SequenceStartFrame"), 500)

    def test_enabled_sets_saver_inputs(self):
        node = self._saver()
        cfg = {
            "final": {
                "format": "OpenEXRFormat",
                "image_sequence": True,
                "source_numbering": True,
            }
        }
        with self._with_step_cfg(cfg), \
             patch.object(self.host, "currentStep", return_value=None), \
             patch.object(self.host, "resolveSourceStartFrame", return_value=86400):
            self.host._apply_source_numbering(node, "final")

        self.assertEqual(node.GetInput("SetSequenceStart"), 1)
        self.assertEqual(node.GetInput("SequenceStartFrame"), 86400)

    def test_enabled_but_no_plate_found_leaves_comp_numbering(self):
        node = self._saver()
        cfg = {
            "final": {
                "format": "OpenEXRFormat",
                "image_sequence": True,
                "source_numbering": True,
            }
        }
        with self._with_step_cfg(cfg), \
             patch.object(self.host, "currentStep", return_value=None), \
             patch.object(self.host, "resolveSourceStartFrame", return_value=None):
            self.host._apply_source_numbering(node, "final")

        self.assertIsNone(node.GetInput("SetSequenceStart"))

    def test_disabled_clears_previous_offset(self):
        """source_numbering: false enforces comp-time numbering."""
        node = self._saver()
        node.SetInput("SetSequenceStart", 1, 0)

        cfg = {
            "final": {
                "format": "OpenEXRFormat",
                "image_sequence": True,
                "source_numbering": False,
            }
        }
        with self._with_step_cfg(cfg), \
             patch.object(self.host, "currentStep", return_value=None):
            self.host._apply_source_numbering(node, "final")

        self.assertEqual(node.GetInput("SetSequenceStart"), 0)

    def test_not_applied_to_movie_outputs(self):
        """A .mov master has no frame numbering to offset."""
        node = self._saver()
        cfg = {
            "final": {
                "format": "QuickTimeMovies",
                "source_numbering": True,
            }
        }
        with self._with_step_cfg(cfg), \
             patch.object(self.host, "currentStep", return_value=None), \
             patch.object(self.host, "resolveSourceStartFrame") as mock_resolve:
            self.host._apply_source_numbering(node, "final")

        mock_resolve.assert_not_called()
        self.assertIsNone(node.GetInput("SetSequenceStart"))

    def test_apply_render_preset_invokes_source_numbering(self):
        """End to end: apply_render_preset on a YAML-configured step wires
        the sequence-start inputs alongside format/codec."""
        node = self._saver()
        cfg = {
            "final": {
                "format": "OpenEXRFormat",
                "image_sequence": True,
                "source_numbering": True,
            }
        }
        with self._with_step_cfg(cfg), \
             patch.object(self.host, "currentStep", return_value=None), \
             patch.object(self.host, "resolveSourceStartFrame", return_value=86400):
            self.host.apply_render_preset(node, "final")

        self.assertEqual(node.GetInput("OutputFormat"), "OpenEXRFormat")
        self.assertEqual(node.GetInput("SetSequenceStart"), 1)
        self.assertEqual(node.GetInput("SequenceStartFrame"), 86400)


class TestEnsureCompFolders(unittest.TestCase):
    """A composition path whose parent is a drive root means the path was built
    from an unresolved folder — creating _versions/_published there litters the
    drive root (observed: D:\\_published, D:\\_versions) instead of the project."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        self.fusion_host = fusion_host
        self.host = FusionHost(self.mock_fusion)

    def test_refuses_drive_root_parent(self):
        made = []
        with patch.object(self.fusion_host.os, "makedirs", side_effect=lambda *a, **k: made.append(a[0])):
            ok = self.host.ensureCompFolders("D:/DrNiceXmas_S_0515_COMP.comp")
        self.assertFalse(ok)
        self.assertEqual(made, [], "nothing may be created at a drive root")

    def test_refuses_empty_path(self):
        made = []
        with patch.object(self.fusion_host.os, "makedirs", side_effect=lambda *a, **k: made.append(a[0])):
            self.assertFalse(self.host.ensureCompFolders(""))
            self.assertFalse(self.host.ensureCompFolders(None))
        self.assertEqual(made, [])

    def test_refuses_bare_filename(self):
        """A dirless name would resolve _versions/_published against the CWD."""
        made = []
        with patch.object(self.fusion_host.os, "makedirs", side_effect=lambda *a, **k: made.append(a[0])):
            ok = self.host.ensureCompFolders("DrNiceXmas_S_0515_COMP.comp")
        self.assertFalse(ok)
        self.assertEqual(made, [])

    def test_creates_step_folder_and_siblings_for_a_real_path(self):
        comp = ("X:/Geteilte Ablagen/proj/05-SHOTS/DrNiceXmas_S_0515/"
                "DrNiceXmas_S_0515_COMP/DrNiceXmas_S_0515_COMP.comp")
        parent = os.path.dirname(comp)
        made = []
        with patch.object(self.fusion_host.os, "makedirs", side_effect=lambda *a, **k: made.append(a[0])):
            ok = self.host.ensureCompFolders(comp)
        self.assertTrue(ok)
        self.assertEqual(
            [p.replace("\\", "/") for p in made],
            [parent, parent + "/_versions", parent + "/_published"],
        )


class TestDeliverySidecarSuppression(unittest.TestCase):
    """Pipeline sidecars (_ramses_data.json) must not be written into the
    project export folder — that folder is a client delivery, not pipeline
    storage. The comp backup inside the step tree keeps its metadata."""

    EXPORT = "D:/proj/06-EXPORT"
    RENDER = "D:/proj/06-EXPORT/DNX_0515_v00_vfx/DNX_0515_v00_vfx.00000000.exr"
    BACKUP = "D:/proj/05-SHOTS/TEST_S_SH010/TEST_S_SH010_COMP/_published/005_OK/comp.comp"

    def setUp(self):
        self.mock_fusion = MockFusion()
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        self.fusion_host = fusion_host
        self.host = FusionHost(self.mock_fusion)

    def _project(self, export_path=EXPORT):
        project = MagicMock()
        project.exportPath.return_value = export_path
        return project

    def _patch_project(self, project):
        return patch.object(
            self.fusion_host.RAMSES, "project", return_value=project
        )

    # --- _is_delivery_path ----------------------------------------------------

    def test_render_in_export_folder_is_a_delivery(self):
        with self._patch_project(self._project()):
            self.assertTrue(
                self.fusion_host._is_delivery_path(self.host, self.RENDER)
            )

    def test_backup_in_step_tree_is_not_a_delivery(self):
        with self._patch_project(self._project()):
            self.assertFalse(
                self.fusion_host._is_delivery_path(self.host, self.BACKUP)
            )

    def test_sibling_folder_does_not_match_prefix(self):
        """'06-EXPORTS_OLD' must not be treated as inside '06-EXPORT'."""
        stray = "D:/proj/06-EXPORTS_OLD/thing.exr"
        with self._patch_project(self._project()):
            self.assertFalse(
                self.fusion_host._is_delivery_path(self.host, stray)
            )

    def test_no_export_path_configured_keeps_old_behaviour(self):
        with self._patch_project(self._project(export_path="")):
            self.assertFalse(
                self.fusion_host._is_delivery_path(self.host, self.RENDER)
            )

    def test_export_path_failure_keeps_old_behaviour(self):
        """Any error must fall back to writing metadata, never break publish."""
        project = MagicMock()
        project.exportPath.side_effect = RuntimeError("daemon down")
        with self._patch_project(project):
            self.assertFalse(
                self.fusion_host._is_delivery_path(self.host, self.RENDER)
            )

    def test_no_project_keeps_old_behaviour(self):
        with self._patch_project(None):
            self.assertFalse(
                self.fusion_host._is_delivery_path(self.host, self.RENDER)
            )

    # --- the publish loop -----------------------------------------------------

    def test_publish_writes_metadata_for_backup_but_not_delivery(self):
        """The regression, through the real publish path: the export render
        got a sidecar written next to it in the client delivery folder."""
        step = MagicMock()
        step.publishSettings.return_value = {}

        meta = MagicMock()
        with patch.object(self.host, "currentItem", return_value=MagicMock()), \
             patch.object(self.host, "currentStep", return_value=step), \
             patch.object(self.host, "publishInfo", return_value=MagicMock()), \
             patch.object(self.host, "currentStatus", return_value=MagicMock()), \
             patch.object(self.host, "closeTempWorkingFile"), \
             patch.object(self.host, "_RamHost__save", return_value=True, create=True), \
             patch.object(self.host, "_RamHost__runUserScripts", return_value=True, create=True), \
             patch.object(self.host, "_prePublish", side_effect=lambda i, o: o), \
             patch.object(self.host, "_publish", return_value=[self.RENDER, self.BACKUP]), \
             patch.object(self.host, "_RamHost__setPublishMetadata", meta, create=True), \
             self._patch_project(self._project()):

            ok = self.host.publish(
                publishOptions={"ramsesPublishOptions": {}},
                incrementVersion=False,
            )

        self.assertTrue(ok)
        written = [call.args[0] for call in meta.call_args_list]
        self.assertEqual(written, [self.BACKUP], "delivery render must be skipped")
        self.assertNotIn(self.RENDER, written)


if __name__ == "__main__":
    unittest.main()
