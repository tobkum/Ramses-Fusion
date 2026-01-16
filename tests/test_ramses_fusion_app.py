import sys
import os
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# --- 1. Setup Environment Mocks ---
sys.modules["bmd"] = MagicMock()
sys.modules["fusionscript"] = MagicMock()

# --- 2. Setup Path ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
lib_path = os.path.join(project_root, "Ramses-Fusion", "lib")
app_path = os.path.join(project_root, "Ramses-Fusion")

if lib_path not in sys.path:
    sys.path.append(lib_path)
if app_path not in sys.path:
    sys.path.append(app_path)

# Mock the Ramses Daemon and singleton
import ramses
mock_daemon = MagicMock()
mock_daemon.online.return_value = True
mock_daemon.getUser.return_value = MagicMock()
sys.modules["ramses.daemon_interface"] = MagicMock(RamDaemonInterface=MagicMock(instance=lambda: mock_daemon))

# Mock Ramses.connect to prevent the client from launching during tests
import ramses.ramses
ramses.ramses.Ramses.connect = MagicMock(return_value=True)

# Mock global 'fusion' and 'fu' objects used by the app
mock_fusion = MagicMock()
import builtins
builtins.fusion = mock_fusion
builtins.fu = mock_fusion

import importlib.util
spec = importlib.util.spec_from_file_location("Ramses_Fusion", os.path.join(app_path, "Ramses-Fusion.py"))
ram_fusion_mod = importlib.util.module_from_spec(spec)
# Add to sys.modules so it can be imported normally elsewhere if needed
sys.modules["Ramses_Fusion"] = ram_fusion_mod
spec.loader.exec_module(ram_fusion_mod)

from Ramses_Fusion import RamsesFusionApp
from tests.mocks import MockFusion

class TestRamsesFusionApp(unittest.TestCase):

    def setUp(self):
        self.mock_fusion = MockFusion()
        # Inject global fusion/fu into the module namespace
        ram_fusion_mod.fusion = self.mock_fusion
        ram_fusion_mod.fu = self.mock_fusion
        ram_fusion_mod.bmd = sys.modules["bmd"]
        
        # Inject bmd into fusion_host as well
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        
        self.app = RamsesFusionApp()

    def test_project_mismatch_detection(self):
        """Verify that the app detects when a file belongs to a different project."""
        mock_item = MagicMock()
        mock_project = MagicMock()
        mock_project.uuid.return_value = "project-A"
        
        # 1. Setup Active Project in Ramses
        ramses.Ramses.instance().project = MagicMock(return_value=mock_project)
        
        # 2. Set different Project UUID in Comp Metadata
        self.mock_fusion.GetCurrentComp().SetData("Ramses.ProjectUUID", "project-B")
        
        # We need to mock _update_ui_state to check mismatch flag indirectly or mock GetItems
        mock_items = {
            "ContextLabel": MagicMock(),
            "RamsesVersion": MagicMock()
        }
        self.app.dlg = MagicMock()
        self.app.dlg.GetItems.return_value = mock_items
        
        with patch.object(RamsesFusionApp, 'current_item', new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_item
            self.app._update_ui_state(True)
            
            # Check if ContextLabel was updated with mismatch warning
            call_args = mock_items["ContextLabel"].Text
            self.assertIn("PROJECT MISMATCH", call_args)

    def test_validate_publish_mismatches(self):
        """Test validation of resolution and frame range before publishing."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT
        
        # DB Settings
        db_settings = {
            "width": 1920,
            "height": 1080,
            "framerate": 24.0,
            "frames": 100
        }
        self.app.ramses.host.collectItemSettings = MagicMock(return_value=db_settings)
        
        # 1. Test Resolution Mismatch
        comp = self.mock_fusion.GetCurrentComp()
        comp.SetPrefs({"Comp.FrameFormat.Width": 1280, "Comp.FrameFormat.Height": 720})
        
        with patch.object(RamsesFusionApp, 'current_item', new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_item
            is_valid, msg = self.app._validate_publish(check_preview=False, check_final=False)
            self.assertFalse(is_valid)
            self.assertIn("Resolution Mismatch", msg)
            
        # 2. Test Frame Range Mismatch
        comp.SetPrefs({"Comp.FrameFormat.Width": 1920, "Comp.FrameFormat.Height": 1080})
        comp.SetAttrs({"COMPN_RenderStart": 1001.0, "COMPN_RenderEnd": 1050.0}) # 50 frames instead of 100
        
        with patch.object(RamsesFusionApp, 'current_item', new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_item
            is_valid, msg = self.app._validate_publish(check_preview=False, check_final=False)
            self.assertFalse(is_valid)
            self.assertIn("Frame Range Mismatch", msg)

    def test_anchor_creation(self):
        """Verify that Setup Scene creates the correct Saver anchors."""
        # 1. Mock host to return specific paths
        self.app.ramses.host.resolvePreviewPath = MagicMock(return_value="D:/Previews/Shot_Preview.mov")
        self.app.ramses.host.resolveFinalPath = MagicMock(return_value="D:/Renders/Shot_Final.mov")
        
        self.app._create_render_anchors()
        
        comp = self.mock_fusion.GetCurrentComp()
        preview_node = comp.FindTool("_PREVIEW")
        final_node = comp.FindTool("_FINAL")
        
        self.assertIsNotNone(preview_node)
        self.assertIsNotNone(final_node)
        
        self.assertEqual(preview_node.Clip[1], "D:/Previews/Shot_Preview.mov")
        self.assertEqual(final_node.Clip[1], "D:/Renders/Shot_Final.mov")
        
        # Verify they are disabled by default
        self.assertTrue(preview_node.attrs.get("TOOLB_PassThrough"))
        self.assertTrue(final_node.attrs.get("TOOLB_PassThrough"))

    def test_anchor_validation(self):
        """Verify that publish fails if anchors are disconnected."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT
        self.app.ramses.host.collectItemSettings = MagicMock(return_value={"width": 1920, "height": 1080, "framerate": 24.0})
        
        comp = self.mock_fusion.GetCurrentComp()
        final_node = comp.AddTool("Saver", 0, 0)
        final_node.SetAttrs({"TOOLS_Name": "_FINAL"})
        # No input connected by default in mock
        
        with patch.object(RamsesFusionApp, 'current_item', new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_item
            is_valid, msg = self.app._validate_publish(check_preview=False, check_final=True)
            self.assertFalse(is_valid)
            self.assertIn("Disconnected Anchor", msg)

    def test_resolve_shot_path(self):
        """Test the path resolution logic for existing vs predicted shots."""
        mock_shot = MagicMock()
        mock_shot.shortName.return_value = "SH010"
        mock_step = MagicMock()
        mock_step.shortName.return_value = "COMP"
        mock_step.projectShortName.return_value = "PROJ"
        
        # 1. Test Existing File
        mock_shot.stepFilePath.return_value = "D:/Existing/PROJ_S_SH010_COMP_v001.comp"
        with patch('os.path.exists', return_value=True):
            path, exists = self.app._resolve_shot_path(mock_shot, mock_step)
            self.assertTrue(exists)
            self.assertEqual(path, "D:/Existing/PROJ_S_SH010_COMP_v001.comp")

        # 2. Test Predicted Path (if file doesn't exist)
        mock_shot.stepFolderPath.return_value = "D:/NewFolder"
        with patch('os.path.exists', return_value=False):
            path, exists = self.app._resolve_shot_path(mock_shot, mock_step)
            self.assertFalse(exists)
            # Should predict name using Ramses convention: Project_Type_Name_Step_v-1.comp
            # (Note: fileName helper in app uses version -1 for predicted paths)
            self.assertIn("PROJ_S_SH010_COMP.comp", path)
            self.assertIn("D:/NewFolder", path)

    def test_context_caching(self):
        """Verify that context is cached and only re-fetched when the path changes."""
        self.app.ramses.host.currentFilePath = MagicMock(return_value="D:/Path/A.comp")
        self.app.ramses.host.currentItem = MagicMock(return_value=MagicMock(name="ItemA"))
        
        # First call
        path1 = self.app._update_context()
        self.assertEqual(path1, "D:/Path/A.comp")
        self.assertEqual(self.app.ramses.host.currentItem.call_count, 1)
        
        # Second call with same path (should use cache)
        path2 = self.app._update_context()
        self.assertEqual(self.app.ramses.host.currentItem.call_count, 1)
        
        # Third call with new path (should invalid cache)
        self.app.ramses.host.currentFilePath.return_value = "D:/Path/B.comp"
        path3 = self.app._update_context()
        self.assertEqual(self.app.ramses.host.currentItem.call_count, 2)

    def test_requires_connection_decorator(self):
        """Verify that handlers are blocked if the Ramses connection is lost."""
        # 1. Force offline
        self.app.ramses.daemonInterface().online.return_value = False
        ramses.Ramses.instance().online = MagicMock(return_value=False)
        
        # 2. Try to call a decorated method
        # We'll use on_import as it's decorated
        self.app.ramses.host.importItem = MagicMock()
        self.app.on_import(None)
        
        # Should NOT have been called
        self.app.ramses.host.importItem.assert_not_called()

    def test_incremental_save_handler(self):
        """Verify that incremental save triggers anchor sync and host save."""
        self.app._sync_render_anchors = MagicMock()
        self.app.ramses.host.save = MagicMock(return_value=True)
        self.app.refresh_header = MagicMock()
        
        self.app.on_incremental_save(None)
        
        self.app._sync_render_anchors.assert_called_once()
        self.app.ramses.host.save.assert_called_once_with(incremental=True, setupFile=True)
        self.app.refresh_header.assert_called_once()

if __name__ == "__main__":
    unittest.main()
