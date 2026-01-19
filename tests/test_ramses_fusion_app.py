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
sys.modules["ramses.daemon_interface"] = MagicMock(
    RamDaemonInterface=MagicMock(instance=lambda: mock_daemon)
)

# Mock Ramses.connect to prevent the client from launching during tests
import ramses.ramses

ramses.ramses.Ramses.connect = MagicMock(return_value=True)

# Mock global 'fusion' and 'fu' objects used by the app
mock_fusion = MagicMock()
import builtins

builtins.fusion = mock_fusion
builtins.fu = mock_fusion

import importlib.util

spec = importlib.util.spec_from_file_location(
    "Ramses_Fusion", os.path.join(app_path, "Ramses-Fusion.py")
)
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
        mock_items = {"ContextLabel": MagicMock(), "RamsesVersion": MagicMock()}
        self.app.dlg = MagicMock()
        self.app.dlg.GetItems.return_value = mock_items

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item
            self.app._update_ui_state(True)

            # Check if ContextLabel was updated with mismatch warning
            call_args = mock_items["ContextLabel"].Text
            self.assertIn("PROJECT MISMATCH", call_args)

    def test_validate_publish_mismatches(self):
        """Verify technical validation of resolution and frame range before publishing."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT

        # DB Settings
        db_settings = {"width": 1920, "height": 1080, "framerate": 24.0, "frames": 100}
        self.app.ramses.host.collectItemSettings = MagicMock(return_value=db_settings)

        # 1. Test Resolution Mismatch
        comp = self.mock_fusion.GetCurrentComp()
        comp.SetPrefs({"Comp.FrameFormat.Width": 1280, "Comp.FrameFormat.Height": 720})

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item
            is_valid, msg, has_hard_error = self.app._validate_publish(
                check_preview=False, check_final=False
            )
            self.assertFalse(is_valid)
            self.assertIn("Resolution Mismatch", msg)

        # 2. Test Frame Range Mismatch
        comp.SetPrefs({"Comp.FrameFormat.Width": 1920, "Comp.FrameFormat.Height": 1080})
        comp.SetAttrs(
            {"COMPN_RenderStart": 1001.0, "COMPN_RenderEnd": 1050.0}
        )  # 50 frames instead of 100

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item
            is_valid, msg, has_hard_error = self.app._validate_publish(
                check_preview=False, check_final=False
            )
            self.assertFalse(is_valid)
            self.assertIn("Frame Range Mismatch", msg)

    def test_anchor_creation(self):
        """Verify that Setup Scene creates the correct Saver anchors."""
        # 1. Mock host to return specific paths
        self.app.ramses.host.resolvePreviewPath = MagicMock(
            return_value="D:/Previews/Shot_Preview.mov"
        )
        self.app.ramses.host.resolveFinalPath = MagicMock(
            return_value="D:/Renders/Shot_Final.mov"
        )

        # Patch apply_render_preset to avoid complex logic/hangs
        self.app.ramses.host.apply_render_preset = MagicMock()

        self.app._create_render_anchors()

        comp = self.mock_fusion.GetCurrentComp()
        preview_node = comp.FindTool("_PREVIEW")
        final_node = comp.FindTool("_FINAL")

        self.assertIsNotNone(preview_node)
        self.assertIsNotNone(final_node)

        self.assertEqual(preview_node.Clip[1], "D:/Previews/Shot_Preview.mov")
        self.assertEqual(final_node.Clip[1], "D:/Renders/Shot_Final.mov")

        # Verify preset was called
        self.assertEqual(self.app.ramses.host.apply_render_preset.call_count, 2)

        # Verify they are disabled by default
        self.assertTrue(preview_node.attrs.get("TOOLB_PassThrough"))
        self.assertTrue(final_node.attrs.get("TOOLB_PassThrough"))

    def test_anchor_validation(self):
        """Verify that publish/preview blocks if required Saver anchors are missing or disconnected."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT
        self.app.ramses.host.collectItemSettings = MagicMock(
            return_value={"width": 1920, "height": 1080, "framerate": 24.0}
        )

        comp = self.mock_fusion.GetCurrentComp()
        final_node = comp.AddTool("Saver", 0, 0)
        final_node.SetAttrs({"TOOLS_Name": "_FINAL"})
        # No input connected by default in mock

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item
            is_valid, msg, has_hard_error = self.app._validate_publish(
                check_preview=False, check_final=True
            )
            self.assertFalse(is_valid)
            self.assertIn("Disconnected Anchor", msg)

    def test_resolve_shot_path(self):
        """Verify the path resolution logic for existing files vs. predicted Ramses naming."""
        mock_shot = MagicMock()
        mock_shot.shortName.return_value = "SH010"
        mock_step = MagicMock()
        mock_step.shortName.return_value = "COMP"
        mock_step.projectShortName.return_value = "PROJ"

        # 1. Test Existing File
        mock_shot.stepFilePath.return_value = "D:/Existing/PROJ_S_SH010_COMP_v001.comp"
        with patch("os.path.exists", return_value=True):
            path, exists = self.app._resolve_shot_path(mock_shot, mock_step)
            self.assertTrue(exists)
            self.assertEqual(path, "D:/Existing/PROJ_S_SH010_COMP_v001.comp")

        # 2. Test Predicted Path (if file doesn't exist)
        mock_shot.stepFolderPath.return_value = "D:/NewFolder"
        with patch("os.path.exists", return_value=False):
            path, exists = self.app._resolve_shot_path(mock_shot, mock_step)
            self.assertFalse(exists)
            # Should predict name using Ramses convention: Project_Type_Name_Step_v-1.comp
            # (Note: fileName helper in app uses version -1 for predicted paths)
            self.assertIn("PROJ_S_SH010_COMP.comp", path)
            self.assertIn("D:/NewFolder", path)

    def test_context_caching(self):
        """Verify that Project/Shot context is cached and only re-fetched when the file path changes."""
        self.app.ramses.host.currentFilePath = MagicMock(return_value="D:/Path/A.comp")
        self.app.ramses.host.currentItem = MagicMock(
            return_value=MagicMock(name="ItemA")
        )

        # Reset call count (app init calls it once)
        self.app.ramses.host.currentItem.reset_mock()

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
        """Verify that the @requires_connection decorator blocks handlers when the Ramses Daemon is offline."""
        # 1. Force offline
        with patch.object(
            self.app.ramses.daemonInterface(), "online", return_value=False
        ):
            with patch.object(ramses.Ramses.instance(), "online", return_value=False):
                # 2. Try to call a decorated method
                # We'll use on_import as it's decorated
                self.app.ramses.host.importItem = MagicMock()
                self.app.on_import(None)

                # Should NOT have been called
                self.app.ramses.host.importItem.assert_not_called()

    def test_incremental_save_handler(self):
        """Verify that the Save Incremental handler triggers anchor synchronization and version increment."""
        self.app._sync_render_anchors = MagicMock()
        self.app.ramses.host.save = MagicMock(return_value=True)
        self.app.refresh_header = MagicMock()

        # Mock status/state for propagation check
        mock_state = MagicMock()
        mock_status = MagicMock()
        mock_status.state.return_value = mock_state

        with patch.object(
            self.app.ramses.host, "currentStatus", return_value=mock_status
        ):
            self.app.on_incremental_save(None)

            self.app._sync_render_anchors.assert_called_once()
            # Verify state propagation
            self.app.ramses.host.save.assert_called_once_with(
                incremental=True, setupFile=True, state=mock_state
            )
            self.app.refresh_header.assert_called_once()

    def test_on_note_logic(self):
        """Verify that 'Add Note' pre-fills correctly and only saves on change."""
        host = self.app.ramses.host
        mock_status = MagicMock()
        mock_status.comment.return_value = "Old Note"
        mock_state = MagicMock()
        mock_status.state.return_value = mock_state
        host.save = MagicMock(return_value=True)

        # Mock version and refresh to avoid real API/filesystem hits
        host.currentVersion = MagicMock(return_value=1)

        with patch.object(self.app, "refresh_header"):
            with patch.object(host, "currentStatus", return_value=mock_status):
                # 1. Test Cancellation (no save)
                with patch.object(host, "_request_input", return_value=None):
                    self.app.on_comment(None)
                    host.save.assert_not_called()

                # 2. Test No Change (no save)
                with patch.object(
                    host, "_request_input", return_value={"Comment": "Old Note"}
                ):
                    self.app.on_comment(None)
                    host.save.assert_not_called()

                # 3. Test Change (Save triggered with state propagation)
                with patch.object(
                    host, "_request_input", return_value={"Comment": "New Note"}
                ):
                    self.app.on_comment(None)
                    host.save.assert_called_with(
                        comment="New Note", setupFile=True, state=mock_state
                    )
                    self.app.refresh_header.assert_called_once()

    def test_role_based_ui_state(self):
        """Verify that Step Configuration is enabled/disabled based on role and users count."""
        mock_items = {
            "PubSettingsButton": MagicMock(),
            "ContextLabel": MagicMock(),
            "RamsesVersion": MagicMock(),
            "SwitchShotButton": MagicMock(),
        }
        self.app.dlg = MagicMock()
        self.app.dlg.GetItems.return_value = mock_items

        # 1. Standard Role, Multi-User -> Disabled
        mock_user = MagicMock()
        mock_user.role.return_value = ramses.UserRole.STANDARD
        self.app.ramses.user = MagicMock(return_value=mock_user)

        with patch.object(
            self.app.ramses.daemonInterface(),
            "getObjects",
            return_value=[mock_user, MagicMock()],
        ):
            # Mock valid pipeline context
            mock_item = MagicMock()
            mock_item.uuid.return_value = "item-uuid"
            # Project mismatch check needs data
            mock_project = MagicMock()
            mock_project.uuid.return_value = "proj-uuid"
            self.app.ramses.project = MagicMock(return_value=mock_project)

            with patch.object(
                self.app.ramses.host.comp, "GetData", return_value="proj-uuid"
            ):
                with patch.object(
                    RamsesFusionApp, "current_item", new_callable=PropertyMock
                ) as mock_prop:
                    mock_prop.return_value = mock_item
                    self.app._update_ui_state(True)
                    self.assertFalse(mock_items["PubSettingsButton"].Enabled)

                # 2. Lead Role, Multi-User -> Enabled
                mock_user.role.return_value = ramses.UserRole.LEAD
                with patch.object(
                    RamsesFusionApp, "current_item", new_callable=PropertyMock
                ) as mock_prop:
                    mock_prop.return_value = mock_item
                    self.app._update_ui_state(True)
                    self.assertTrue(mock_items["PubSettingsButton"].Enabled)

                # 3. Standard Role, Single-User -> Enabled
                mock_user.role.return_value = ramses.UserRole.STANDARD
                with patch.object(
                    self.app.ramses.daemonInterface(),
                    "getObjects",
                    return_value=[mock_user],
                ):  # 1 user
                    with patch.object(
                        RamsesFusionApp, "current_item", new_callable=PropertyMock
                    ) as mock_prop:
                        mock_prop.return_value = mock_item
                        self.app._update_ui_state(True)
                        self.assertTrue(mock_items["PubSettingsButton"].Enabled)

    def test_priority_and_color_rendering(self):
        """Verify that the header renders priority suffixes and Ramses colors."""
        mock_item = MagicMock()
        mock_item.shortName.return_value = "SH010"
        mock_item.projectShortName.return_value = "PROJ"

        mock_step = MagicMock()
        mock_step.name.return_value = "Compositing"
        mock_step.colorName.return_value = "#ff00ff"

        mock_state = MagicMock()
        mock_state.shortName.return_value = "WIP"
        mock_state.colorName.return_value = "#00ffff"

        mock_status = MagicMock()
        mock_status.state.return_value = mock_state
        mock_status.get.return_value = 2  # Priority Urgent

        self.app.ramses.host.currentStatus = MagicMock(return_value=mock_status)
        self.app._project_cache = MagicMock()
        self.app._project_cache.name.return_value = "My Project"

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_item_prop:
            mock_item_prop.return_value = mock_item
            with patch.object(
                RamsesFusionApp, "current_step", new_callable=PropertyMock
            ) as mock_step_prop:
                mock_step_prop.return_value = mock_step

                html = self.app._get_context_text()

                # Check Priority !!
                self.assertIn("!!", html)
                self.assertIn("#ff8800", html)  # Urgent color

                # Check Step Color
                self.assertIn("#ff00ff", html)
                self.assertIn("Compositing", html)

                # Check State Badge
                self.assertIn("#00ffff", html)
                self.assertIn("WIP", html)

                # Check Hero ID (White & Bold)
                self.assertIn("#FFF", html)
                self.assertIn("SH010", html)


if __name__ == "__main__":
    unittest.main()
