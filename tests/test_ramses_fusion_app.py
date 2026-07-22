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
from mocks import MockFusion


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
        
        # Standard UI Mocks to prevent dialogs during tests
        self.app.ramses.host._statusUI = MagicMock()
        self.app.ramses.host._openUI = MagicMock()
        self.app.ramses.host._saveAsUI = MagicMock()
        self.app.ramses.host._importUI = MagicMock()
        self.app.ramses.host._restoreVersionUI = MagicMock()

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
        # stepFilePath() itself validates existence internally (os.path.isfile)
        # before returning a non-empty path, so _resolve_shot_path() trusts a
        # non-empty return value directly rather than re-checking on disk.
        mock_shot.stepFilePath.return_value = "D:/Existing/PROJ_S_SH010_COMP_v001.comp"
        path, exists = self.app._resolve_shot_path(mock_shot, mock_step)
        self.assertTrue(exists)
        self.assertEqual(path, "D:/Existing/PROJ_S_SH010_COMP_v001.comp")

        # 2. Test Predicted Path (no existing file: stepFilePath() returns "")
        mock_shot.stepFilePath.return_value = ""
        mock_shot.stepFolderPath.return_value = "D:/NewFolder"
        path, exists = self.app._resolve_shot_path(mock_shot, mock_step)
        self.assertFalse(exists)
        # Normalize for cross-platform comparison
        norm_path = path.replace("\\", "/")
        # Should predict name using Ramses convention: Project_Type_Name_Step_v-1.comp
        # (Note: fileName helper in app uses version -1 for predicted paths)
        self.assertIn("PROJ_S_SH010_COMP.comp", norm_path)
        self.assertIn("D:/NewFolder", norm_path)

    def test_context_caching(self):
        """Verify that Project/Shot context is cached and only re-fetched when the file path changes."""
        self.app.ramses.host.currentFilePath = MagicMock(return_value="D:/Path/A.comp")
        self.app.ramses.host.currentItem = MagicMock(
            return_value=MagicMock(name="ItemA")
        )
        # Fix: Must also mock currentStep, otherwise _step_cache is None and cache invalidates
        self.app.ramses.host.currentStep = MagicMock(
            return_value=MagicMock(name="StepA")
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

    def test_update_context_toctou_race(self):
        """Verify _update_context skips the commit when the comp switches mid-fetch.

        The item/step were resolved for the path seen at entry (A.comp); if
        the current file changed to B.comp while those slow calls ran,
        committing them under B would pair A's item with B's path - and
        because needs_update then goes False for B, the wrong item would be
        served indefinitely. The correct behavior is to skip the commit and
        resolve cleanly for B on the next access.
        """
        # Simulate a race where the path changes while slow API calls are
        # running: entry sees A.comp, the commit-time re-check sees B.comp,
        # and the retry access sees B.comp consistently.
        self.app.ramses.host.currentFilePath = MagicMock(
            side_effect=["D:/Path/A.comp", "D:/Path/B.comp",
                         "D:/Path/B.comp", "D:/Path/B.comp"]
        )
        item_b = MagicMock(name="ItemB")
        step_b = MagicMock(name="StepB")
        self.app.ramses.host.currentItem = MagicMock(return_value=item_b)
        self.app.ramses.host.currentStep = MagicMock(return_value=step_b)

        # Clear cache to trigger update
        self.app._context_path = ""
        self.app._item_cache = None
        self.app._context_resolved = False

        path = self.app._update_context()

        # Mid-fetch switch: nothing committed, prior (empty) context returned.
        self.assertEqual(path, "")
        self.assertFalse(self.app._context_resolved)

        # Next access sees a stable B.comp and resolves it properly.
        path = self.app._update_context()
        self.assertEqual(path, "D:/Path/B.comp")
        self.assertEqual(self.app._context_path, "D:/Path/B.comp")
        self.assertIs(self.app._item_cache, item_b)
        self.assertTrue(self.app._context_resolved)

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

    def test_on_sync_handler(self):
        """Verify that on_sync correctly triggers host setup and refresh."""
        self.app.ramses.host._setupCurrentFile = MagicMock(return_value=True)
        self.app._create_render_anchors = MagicMock()
        self.app.refresh_header = MagicMock()
        
        # Trigger renamed handler
        self.app.on_sync(None)
        
        self.app.ramses.host._setupCurrentFile.assert_called_once()
        self.app._create_render_anchors.assert_called_once()
        self.app.refresh_header.assert_called_once()

    def test_on_import_handler_standard(self):
        """Verify on_import delegates to host.importItem()."""
        self.app.ramses.host.importItem = MagicMock(return_value=True)
        self.app.refresh_header = MagicMock()
        
        self.app.on_import(None)
        
        self.app.ramses.host.importItem.assert_called_once()
        self.app.refresh_header.assert_called_once()

    def test_on_note_logic(self):
        """Verify that 'Save with Note' handles comments correctly."""
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
                with patch.object(self.app, "_run_pyside_dialog", return_value=None):
                    self.app.on_comment(None)
                    host.save.assert_not_called()

                # 2. Test Comment Change (Overwrite Save)
                mock_dialog = MagicMock()
                mock_dialog.comment.return_value = "New Note"
                with patch.object(self.app, "_run_pyside_dialog", return_value=mock_dialog):
                    self.app.on_comment(None)
                    # Note: Standard dialog has no increment toggle, so incremental=False
                    host.save.assert_called_with(
                        comment="New Note", setupFile=True, incremental=False, state=mock_state
                    )
                    self.app.refresh_header.assert_called_once()
                
                # Reset mocks
                host.save.reset_mock()
                self.app.refresh_header.reset_mock()

                # 3. Test No Change (no save)
                mock_dialog.comment.return_value = "Old Note"
                with patch.object(self.app, "_run_pyside_dialog", return_value=mock_dialog):
                    self.app.on_comment(None)
                    host.save.assert_not_called()

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
                # The single-user probe is cached per session (it is a daemon
                # roundtrip); a change in user population is only picked up
                # after a forced refresh clears the cache — simulate that.
                self.app._single_user_cache = None
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

    def test_save_template_preserves_working_file_identity(self):
        """'Save as Template' must not repoint the comp at the template path
        (comp.Save(path) is a save-as): the working file is saved in place and
        the template is written as a file copy."""
        import tempfile
        import shutil
        import fusion_host as fh

        tmp = tempfile.mkdtemp()
        try:
            step = MagicMock()
            step.templatesFolderPath.return_value = tmp
            step.projectShortName.return_value = "TEST"
            step.shortName.return_value = "COMP"

            host = self.app.ramses.host
            src = "D:/proj/shot/TEST_S_SH010_COMP.comp"
            comp = MagicMock()
            comp.Save.return_value = True

            with patch.object(
                RamsesFusionApp, "current_step", new_callable=PropertyMock, return_value=step
            ), patch.object(
                type(host), "comp", new_callable=PropertyMock, return_value=comp
            ), patch.object(
                host, "currentFilePath", return_value=src
            ), patch.object(
                host, "_request_input", return_value={"Name": "MyTpl"}
            ), patch.object(fh.RamFileManager, "copy") as mock_copy:
                self.app.on_save_template(None)

            # Saved in place — never to the template path
            comp.Save.assert_called_once_with(src)
            # Template written as a copy of the working file
            mock_copy.assert_called_once()
            copy_src, copy_dst = mock_copy.call_args[0][:2]
            self.assertEqual(copy_src, src)
            self.assertTrue(
                copy_dst.replace("\\", "/").startswith(tmp.replace("\\", "/")),
                f"Template must land in the templates folder, got {copy_dst}",
            )
            self.assertTrue(copy_dst.endswith(".comp"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_save_template_distinct_names_distinct_files(self):
        """Two templates with different names must NOT collide.

        Regression: GENERAL-type RamFileInfo.fileName() omits shortName, so the
        template name has to land in the resource field. Using shortName (the
        old code) produced PROJ_G_<step>.comp for every template, silently
        overwriting the previous one."""
        import tempfile
        import shutil
        import fusion_host as fh

        tmp = tempfile.mkdtemp()
        try:
            step = MagicMock()
            step.templatesFolderPath.return_value = tmp
            step.projectShortName.return_value = "TEST"
            step.shortName.return_value = "COMP"

            host = self.app.ramses.host
            src = "D:/proj/shot/TEST_S_SH010_COMP.comp"
            comp = MagicMock()
            comp.Save.return_value = True

            dsts = []
            for tpl_name in ("Alpha", "Beta"):
                with patch.object(
                    RamsesFusionApp, "current_step", new_callable=PropertyMock, return_value=step
                ), patch.object(
                    type(host), "comp", new_callable=PropertyMock, return_value=comp
                ), patch.object(
                    host, "currentFilePath", return_value=src
                ), patch.object(
                    host, "_request_input", return_value={"Name": tpl_name}
                ), patch.object(fh.RamFileManager, "copy") as mock_copy:
                    self.app.on_save_template(None)
                    dsts.append(os.path.basename(mock_copy.call_args[0][1]))

            self.assertNotEqual(dsts[0], dsts[1],
                                f"Templates collided: both wrote {dsts[0]}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

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

    def test_validation_passes_when_anchors_connected(self):
        """Verify validation succeeds when anchors exist, are connected, and settings match."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT

        # DB Settings
        db_settings = {"width": 1920, "height": 1080, "framerate": 24.0, "frames": 100}
        self.app.ramses.host.collectItemSettings = MagicMock(return_value=db_settings)

        # Ensure host uses our mock fusion
        self.app.ramses.host.fusion = self.mock_fusion

        comp = self.mock_fusion.GetCurrentComp()

        # Set matching resolution
        comp.SetPrefs({
            "Comp.FrameFormat.Width": 1920,
            "Comp.FrameFormat.Height": 1080,
            "Comp.FrameFormat.Rate": 24.0
        })

        # Set matching frame range (1001 + 100 - 1 = 1100)
        comp.SetAttrs({
            "COMPN_RenderStart": 1001.0,
            "COMPN_RenderEnd": 1100.0
        })

        # Create CONNECTED anchor nodes
        preview_node = comp.AddTool("Saver", 0, 0)
        preview_node.SetAttrs({"TOOLS_Name": "_PREVIEW"})
        preview_node.connect_input()

        final_node = comp.AddTool("Saver", 0, 0)
        final_node.SetAttrs({"TOOLS_Name": "_FINAL"})
        final_node.connect_input()

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item

            # Test with ALL checks enabled
            is_valid, msg, has_hard_error = self.app._validate_publish(
                check_preview=True, check_final=True
            )

            self.assertTrue(is_valid, f"Validation should pass but got: {msg}")
            self.assertEqual(msg, "", "Message should be empty on success")
            self.assertFalse(has_hard_error, "Should have no hard errors")

    def test_validation_full_check_detects_all_issues(self):
        """Verify full validation detects multiple issues at once."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT

        # DB Settings
        db_settings = {"width": 1920, "height": 1080, "framerate": 24.0, "frames": 100}
        self.app.ramses.host.collectItemSettings = MagicMock(return_value=db_settings)

        # Ensure host uses our mock fusion
        self.app.ramses.host.fusion = self.mock_fusion

        comp = self.mock_fusion.GetCurrentComp()

        # Set WRONG resolution
        comp.SetPrefs({
            "Comp.FrameFormat.Width": 1280,
            "Comp.FrameFormat.Height": 720,
            "Comp.FrameFormat.Rate": 30.0  # Wrong FPS too
        })

        # Set WRONG frame range
        comp.SetAttrs({
            "COMPN_RenderStart": 1001.0,
            "COMPN_RenderEnd": 1050.0  # 50 frames instead of 100
        })

        # Create DISCONNECTED anchor nodes
        preview_node = comp.AddTool("Saver", 0, 0)
        preview_node.SetAttrs({"TOOLS_Name": "_PREVIEW"})
        # Not connected!

        final_node = comp.AddTool("Saver", 0, 0)
        final_node.SetAttrs({"TOOLS_Name": "_FINAL"})
        # Not connected!

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item

            is_valid, msg, has_hard_error = self.app._validate_publish(
                check_preview=True, check_final=True
            )

            self.assertFalse(is_valid, "Validation should fail")
            # Should detect multiple issues
            self.assertIn("Resolution Mismatch", msg)
            self.assertIn("Frame Range Mismatch", msg)
            self.assertIn("Disconnected Anchor", msg)
            # Disconnected anchors are hard errors
            self.assertTrue(has_hard_error, "Should have hard error for disconnected anchor")

    def test_validation_missing_anchor_is_hard_error(self):
        """Verify missing anchor nodes result in hard errors that block publish."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT

        db_settings = {"width": 1920, "height": 1080, "framerate": 24.0, "frames": 100}
        self.app.ramses.host.collectItemSettings = MagicMock(return_value=db_settings)

        # Ensure host uses our mock fusion
        self.app.ramses.host.fusion = self.mock_fusion

        comp = self.mock_fusion.GetCurrentComp()
        comp.SetPrefs({
            "Comp.FrameFormat.Width": 1920,
            "Comp.FrameFormat.Height": 1080,
            "Comp.FrameFormat.Rate": 24.0
        })
        comp.SetAttrs({
            "COMPN_RenderStart": 1001.0,
            "COMPN_RenderEnd": 1100.0
        })

        # NO anchor nodes created!

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item

            is_valid, msg, has_hard_error = self.app._validate_publish(
                check_preview=True, check_final=True
            )

            self.assertFalse(is_valid)
            self.assertIn("Missing Anchor", msg)
            self.assertTrue(has_hard_error, "Missing anchor should be a hard error")

    def test_validation_soft_errors_allow_override(self):
        """Verify soft errors (mismatches) don't set hard_error flag."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT

        # DB expects 1920x1080
        db_settings = {"width": 1920, "height": 1080, "framerate": 24.0, "frames": 100}
        self.app.ramses.host.collectItemSettings = MagicMock(return_value=db_settings)

        # Ensure host uses our mock fusion
        self.app.ramses.host.fusion = self.mock_fusion

        comp = self.mock_fusion.GetCurrentComp()

        # Comp has different resolution (soft error)
        comp.SetPrefs({
            "Comp.FrameFormat.Width": 2048,
            "Comp.FrameFormat.Height": 1080,
            "Comp.FrameFormat.Rate": 24.0
        })
        comp.SetAttrs({
            "COMPN_RenderStart": 1001.0,
            "COMPN_RenderEnd": 1100.0
        })

        # Anchors exist and are connected (no hard error)
        preview_node = comp.AddTool("Saver", 0, 0)
        preview_node.SetAttrs({"TOOLS_Name": "_PREVIEW"})
        preview_node.connect_input()

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item

            is_valid, msg, has_hard_error = self.app._validate_publish(
                check_preview=True, check_final=False
            )

            self.assertFalse(is_valid, "Should fail due to resolution mismatch")
            self.assertIn("Resolution Mismatch", msg)
            # But it's a soft error - user can override
            self.assertFalse(has_hard_error, "Resolution mismatch should be soft error")


class TestValidationEdgeCases(unittest.TestCase):
    """Tests edge cases in validation logic."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        ram_fusion_mod.fusion = self.mock_fusion
        ram_fusion_mod.fu = self.mock_fusion
        ram_fusion_mod.bmd = sys.modules["bmd"]

        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]

        self.app = RamsesFusionApp()
        
        # Standard UI Mocks to prevent dialogs during tests
        self.app.ramses.host._statusUI = MagicMock()
        self.app.ramses.host._openUI = MagicMock()
        self.app.ramses.host._saveAsUI = MagicMock()
        self.app.ramses.host._importUI = MagicMock()
        self.app.ramses.host._restoreVersionUI = MagicMock()
        # Ensure host uses our mock fusion
        self.app.ramses.host.fusion = self.mock_fusion

    def test_validation_skips_frame_check_for_assets(self):
        """Verify frame range validation is skipped for Asset items (not Shots)."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.ASSET  # Not a shot

        db_settings = {"width": 1920, "height": 1080, "framerate": 24.0}
        self.app.ramses.host.collectItemSettings = MagicMock(return_value=db_settings)

        comp = self.mock_fusion.GetCurrentComp()
        comp.SetPrefs({
            "Comp.FrameFormat.Width": 1920,
            "Comp.FrameFormat.Height": 1080,
            "Comp.FrameFormat.Rate": 24.0
        })

        # Frame range doesn't match, but shouldn't matter for assets
        comp.SetAttrs({
            "COMPN_RenderStart": 1.0,
            "COMPN_RenderEnd": 10.0
        })

        # Connected anchor
        preview_node = comp.AddTool("Saver", 0, 0)
        preview_node.SetAttrs({"TOOLS_Name": "_PREVIEW"})
        preview_node.connect_input()

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item

            is_valid, msg, _ = self.app._validate_publish(
                check_preview=True, check_final=False
            )

            # Should pass - frame range check skipped for assets
            self.assertTrue(is_valid, f"Assets should skip frame check, got: {msg}")

    def test_validation_handles_missing_db_settings(self):
        """Verify validation handles gracefully when DB settings are incomplete."""
        mock_item = MagicMock()
        mock_item.itemType.return_value = ramses.ItemType.SHOT

        # Empty/incomplete settings
        self.app.ramses.host.collectItemSettings = MagicMock(return_value={})

        comp = self.mock_fusion.GetCurrentComp()
        comp.SetPrefs({
            "Comp.FrameFormat.Width": 1920,
            "Comp.FrameFormat.Height": 1080,
            "Comp.FrameFormat.Rate": 24.0
        })

        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = mock_item

            # Should not raise an exception
            try:
                is_valid, msg, _ = self.app._validate_publish(
                    check_preview=False, check_final=False
                )
                # Validation result depends on implementation - just verify no crash
            except (KeyError, TypeError) as e:
                self.fail(f"Validation should handle missing settings gracefully: {e}")

    def test_validation_no_item_context(self):
        """Verify validation handles missing item context."""
        with patch.object(
            RamsesFusionApp, "current_item", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = None  # No current item

            # Should handle gracefully
            try:
                is_valid, msg, _ = self.app._validate_publish(
                    check_preview=False, check_final=False
                )
                # Should either pass (nothing to validate) or fail gracefully
            except (AttributeError, TypeError) as e:
                self.fail(f"Validation should handle missing item gracefully: {e}")


class TestForeignAssigneeNote(unittest.TestCase):
    """The status-line reminder that flags a shot assigned to someone else."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        ram_fusion_mod.fusion = self.mock_fusion
        ram_fusion_mod.fu = self.mock_fusion
        ram_fusion_mod.bmd = sys.modules["bmd"]
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        self.app = RamsesFusionApp()

    def _status(self, assignee):
        st = MagicMock()
        st.get.return_value = assignee  # status.get("assignedUser", "")
        return st

    def _set_local_user(self, uuid):
        me = MagicMock()
        me.uuid.return_value = uuid
        self.app.ramses.user = MagicMock(return_value=me)

    def test_none_status_yields_empty(self):
        self._set_local_user("me")
        self.assertEqual(self.app._foreign_assignee_note(None), "")

    def test_unassigned_sentinels_yield_empty(self):
        """Empty / none / unassigned (any case) are all 'up for grabs'."""
        self._set_local_user("me")
        for val in ("", "none", "unassigned", "None", "UNASSIGNED"):
            self.assertEqual(
                self.app._foreign_assignee_note(self._status(val)), "",
                msg=f"{val!r} should read as unassigned",
            )

    def test_assigned_to_me_yields_empty(self):
        """Never warn about your own shot."""
        self._set_local_user("me-uuid")
        self.assertEqual(
            self.app._foreign_assignee_note(self._status("me-uuid")), ""
        )

    def test_assigned_to_other_names_them(self):
        self._set_local_user("me-uuid")
        with patch.object(ramses, "RamUser") as MockUser:
            MockUser.return_value.name.return_value = "Jane Doe"
            note = self.app._foreign_assignee_note(self._status("other-uuid"))
        self.assertEqual(note, "assigned to Jane Doe")

    def test_lookup_failure_is_silent(self):
        """A broken user lookup must never break the action being annotated."""
        self._set_local_user("me-uuid")
        with patch.object(ramses, "RamUser", side_effect=RuntimeError("boom")):
            note = self.app._foreign_assignee_note(self._status("other-uuid"))
        self.assertEqual(note, "")


class TestFusionFileFormats(unittest.TestCase):
    """host.fusionFileFormats() reads the mergeable extensions from the linked
    RamApplication's fileFormats, with a safe .comp fallback."""

    def setUp(self):
        self.mock_fusion = MockFusion()
        ram_fusion_mod.fusion = self.mock_fusion
        ram_fusion_mod.fu = self.mock_fusion
        ram_fusion_mod.bmd = sys.modules["bmd"]
        import fusion_host
        fusion_host.bmd = sys.modules["bmd"]
        self.fusion_host = fusion_host
        self.app = RamsesFusionApp()
        self.host = self.app.ramses.host

    def _step_with_apps(self, app_uuids):
        step = MagicMock()
        step.data.return_value = {"applications": list(app_uuids)}
        return step

    def test_reads_fileformats_from_fusion_app(self):
        self.host.currentStep = MagicMock(return_value=self._step_with_apps(["u1"]))
        with patch.object(self.fusion_host, "RAMSES") as R:
            R.daemonInterface.return_value.getData.return_value = {
                "name": "Fusion", "fileFormats": ["comp"]
            }
            self.assertEqual(self.host.fusionFileFormats(), {".comp"})

    def test_normalizes_dot_and_case(self):
        self.host.currentStep = MagicMock(return_value=self._step_with_apps(["u1"]))
        with patch.object(self.fusion_host, "RAMSES") as R:
            R.daemonInterface.return_value.getData.return_value = {
                "name": "Blackmagic Fusion", "fileFormats": [".COMP", "setting"]
            }
            self.assertEqual(self.host.fusionFileFormats(), {".comp", ".setting"})

    def test_no_app_falls_back_to_comp(self):
        self.host.currentStep = MagicMock(return_value=self._step_with_apps([]))
        with patch.object(self.fusion_host, "RAMSES"):
            self.assertEqual(self.host.fusionFileFormats(), {".comp"})

    def test_non_fusion_app_falls_back_to_comp(self):
        self.host.currentStep = MagicMock(return_value=self._step_with_apps(["u1"]))
        with patch.object(self.fusion_host, "RAMSES") as R:
            R.daemonInterface.return_value.getData.return_value = {
                "name": "Nuke", "fileFormats": ["nk"]
            }
            self.assertEqual(self.host.fusionFileFormats(), {".comp"})

    def test_lookup_error_falls_back(self):
        self.host.currentStep = MagicMock(return_value=self._step_with_apps(["u1"]))
        with patch.object(self.fusion_host, "RAMSES") as R:
            R.daemonInterface.return_value.getData.side_effect = RuntimeError("boom")
            self.assertEqual(self.host.fusionFileFormats(), {".comp"})


if __name__ == "__main__":
    unittest.main()
